#include <Arduino.h>

#define LED_PIN            48
#define FAN_PIN            10
#define LIGHT_SENSOR_PIN   1  
#define SDA_PIN            GPIO_NUM_11
#define SCL_PIN            GPIO_NUM_12

#include <WiFi.h>
#include <Arduino_MQTT_Client.h>
#include <ThingsBoard.h>
#include "DHT20.h"
#include "Wire.h"
#include <ArduinoOTA.h>

// ================================
// DHT20 & Light
// ================================
float g_temperature = NAN;
float g_humidity    = NAN;
float g_lightLevel  = 0.0;

// ================================
//  WiFi & ThingsBoard Configuration
// ================================
constexpr char WIFI_SSID[]       = "Nam Pham";
constexpr char WIFI_PASSWORD[]   = "Nam422003@";

constexpr char TOKEN[]           = "bjdomgwyqp8odbxpoagg";

constexpr char THINGSBOARD_SERVER[] = "app.coreiot.io";
constexpr uint16_t THINGSBOARD_PORT  = 1883U;

constexpr uint32_t MAX_MESSAGE_SIZE  = 1024U;
constexpr uint32_t SERIAL_DEBUG_BAUD = 115200U;

// ================================
// Shared-Attribute / RPC keys
// ================================
constexpr char BLINKING_INTERVAL_ATTR[] = "blinkingInterval";
constexpr char LED_STATE_ATTR[]         = "ledState";
constexpr char FAN_STATE_ATTR[]         = "fanState";
constexpr char LIGHT_ATTR[] = "lightLevel";
// ==========================================================

volatile bool attributesChanged = false;
volatile bool ledState          = false;
volatile bool fanState = false;
// ==========================================================

constexpr uint16_t BLINKING_INTERVAL_MS_MIN = 10U;
constexpr uint16_t BLINKING_INTERVAL_MS_MAX = 60000U;
volatile uint16_t blinkingInterval = 1000U;

uint32_t previousStateChange = 0;

constexpr int16_t telemetrySendInterval = 10000U;
uint32_t previousDataSend           = 0;

// ========================================================
constexpr std::array<const char *, 2U> SHARED_ATTRIBUTES_LIST = {
  LED_STATE_ATTR,
  BLINKING_INTERVAL_ATTR,
  FAN_STATE_ATTR,
};

// ================================
// Client WiFi, MQTT, ThingsBoard, DHT20
// ================================
WiFiClient          wifiClient;
Arduino_MQTT_Client mqttClient(wifiClient);
ThingsBoard         tb(mqttClient, MAX_MESSAGE_SIZE);

DHT20 dht20;

// ================================
// RPC callback LED
// ================================
RPC_Response setLedSwitchState(const RPC_Data &data) {
    Serial.println("Received Switch state");
    bool newState = data;
    Serial.print("Switch state change: ");
    Serial.println(newState);
    digitalWrite(LED_PIN, newState ? HIGH : LOW);
    ledState = newState;
    attributesChanged = true;
    return RPC_Response("setLedSwitchValue", newState);
}
// ================================
RPC_Response setFanSwitchState(const RPC_Data &data) {
  Serial.println("Received Fan switch state");
  bool newState = data;
  Serial.print("Fan switch state change: ");
  Serial.println(newState);
  digitalWrite(FAN_PIN, newState ? HIGH : LOW);
  fanState = newState;
  attributesChanged = true;
  return RPC_Response("setFanSwitchValue", newState);
}


const std::array<RPC_Callback, 1U> callbacks = {
  RPC_Callback{ "setLedSwitchValue", setLedSwitchState },
  RPC_Callback{ "setFanSwitchValue", setFanSwitchState }
};

// ================================
// Shared Attributes
// ================================
void processSharedAttributes(const Shared_Attribute_Data &data) {
  for (auto it = data.begin(); it != data.end(); ++it) {
    if (strcmp(it->key().c_str(), BLINKING_INTERVAL_ATTR) == 0) {
      const uint16_t new_interval = it->value().as<uint16_t>();
      if (new_interval >= BLINKING_INTERVAL_MS_MIN && new_interval <= BLINKING_INTERVAL_MS_MAX) {
        blinkingInterval = new_interval;
        Serial.print("Blinking interval is set to: ");
        Serial.println(new_interval);
      }
    }
    else if (strcmp(it->key().c_str(), LED_STATE_ATTR) == 0) {
      ledState = it->value().as<bool>();
      digitalWrite(LED_PIN, ledState ? HIGH : LOW);
      Serial.print("LED state is set to: ");
      Serial.println(ledState);
    }
    else if (strcmp(it->key().c_str(), FAN_STATE_ATTR) == 0) {
      fanState = it->value().as<bool>();
      digitalWrite(FAN_PIN, fanState ? HIGH : LOW);
      Serial.print("FAN state is set to: ");
      Serial.println(fanState);
    }

  }
  attributesChanged = true;
}

const Shared_Attribute_Callback attributes_callback(
    &processSharedAttributes,
    SHARED_ATTRIBUTES_LIST.cbegin(),
    SHARED_ATTRIBUTES_LIST.cend()
);
const Attribute_Request_Callback attribute_shared_request_callback(
    &processSharedAttributes,
    SHARED_ATTRIBUTES_LIST.cbegin(),
    SHARED_ATTRIBUTES_LIST.cend()
);

// ================================
// Task 1: WiFi Connection
// ================================
void TaskWiFi(void *pvParameters) {
  while (true) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Connecting to AP ...");
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

      int attempt = 0;
      while (WiFi.status() != WL_CONNECTED && attempt < 10) {
        attempt++;
        Serial.print(".");
        vTaskDelay(1000 / portTICK_PERIOD_MS);
      }

      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nConnected to AP");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
      } else {
        Serial.println("\nFailed to connect!");
      }
    }
    vTaskDelay(5000 / portTICK_PERIOD_MS);
  }
}

// ================================
// Task 2: ThingsBoard Execution
// ================================
void TaskThingsboard(void *pvParameters) {
  while (true) {
    if (WiFi.status() == WL_CONNECTED) {
      if (!tb.connected()) {
        Serial.print("Connecting to: ");
        Serial.print(THINGSBOARD_SERVER);
        Serial.print(" with token ");
        Serial.println(TOKEN);

        if (!tb.connect(THINGSBOARD_SERVER, TOKEN, THINGSBOARD_PORT)) {
          Serial.println("Failed to connect");
          return;
        }

        tb.sendAttributeData("macAddress", WiFi.macAddress().c_str());

        Serial.println("Subscribing for RPC...");
        if (!tb.RPC_Subscribe(callbacks.cbegin(), callbacks.cend())) {
          Serial.println("Failed to subscribe for RPC");
          return;
        }

        if (!tb.Shared_Attributes_Subscribe(attributes_callback)) {
          Serial.println("Failed to subscribe for shared attribute updates");
          return;
        }

        Serial.println("Subscribe done");

        if (!tb.Shared_Attributes_Request(attribute_shared_request_callback)) {
          Serial.println("Failed to request for shared attributes");
          return;
        }
      }
      else {
        tb.loop();
      }
    }
    vTaskDelay(500 / portTICK_PERIOD_MS);
  }
}

// ================================
// Task 3: DHT20 Sensor
// ================================
void TaskSensor(void *pvParameters) {
  while (true) {
    if (millis() - previousDataSend > telemetrySendInterval) {
      previousDataSend = millis();

      dht20.read();
      // float temperature = dht20.getTemperature();
      // float humidity    = dht20.getHumidity();
      float temperature = random(200,400) / 10.0f;
      float humidity    = random(300,700) / 10.0f;

      g_temperature = temperature;
      g_humidity    = humidity;

      if (isnan(temperature) || isnan(humidity)) {
        Serial.println("Failed to read from DHT20 sensor!");
      } else {
        Serial.print("Temperature: ");
        Serial.print(temperature);
        Serial.print(" °C, Humidity: ");
        Serial.print(humidity);
        Serial.println(" %");

        tb.sendTelemetryData("temperature", temperature);
        tb.sendTelemetryData("humidity", humidity);
      }

      tb.sendAttributeData("rssi", WiFi.RSSI());
      tb.sendAttributeData("channel", WiFi.channel());
      tb.sendAttributeData("bssid", WiFi.BSSIDstr().c_str());
      tb.sendAttributeData("localIp", WiFi.localIP().toString().c_str());
      tb.sendAttributeData("ssid", WiFi.SSID().c_str());
    }
    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }
}

// ================================
// Task 4: LED Control
// ================================
void TaskLEDControl(void *pvParameters) {
  while (true) {
    if (attributesChanged) {
      attributesChanged = false;
      tb.sendAttributeData(LED_STATE_ATTR, digitalRead(LED_PIN) == HIGH);
    }
    tb.loop();
    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }
}

// ================================
// Task 5: FAN Control
// ================================
void TaskFanControl(void *pvParameters) {
  while (true) {
    if (attributesChanged) {
      attributesChanged = false;
      tb.sendAttributeData(FAN_STATE_ATTR, digitalRead(FAN_PIN) == HIGH);
    }
    tb.loop();
    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }
}


// ================================
// Task 6: Light Sensor
// ================================

void TaskLightSensor(void *pvParameters) {
  while (true) {
    int lux = analogRead(LIGHT_SENSOR_PIN);
    g_lightLevel = lux;

    Serial.print("Light Sensor = ");
    Serial.print(lux);

    if (WiFi.status() == WL_CONNECTED && tb.connected()) {
      tb.sendTelemetryData("light", lux);
      tb.sendAttributeData("light", lux);
    }

    vTaskDelay(pdMS_TO_TICKS(5000));  
  }
}
// ================================
// Task 7: Task Warning
// ================================
void TaskWarning(void *pvParameters) {
  while (true) {
    if (g_temperature > 30.0f || g_humidity < 45.0f) {
      digitalWrite(FAN_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);
      Serial.println("FAN and LED ON: Temperature above 30°C or Humidity below 45%");
    } else {
      digitalWrite(FAN_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
      Serial.println("FAN and LED OFF: Temperature ≤ 30°C and Humidity ≥ 45%");
    }
    vTaskDelay(pdMS_TO_TICKS(3000));  
  }
}

// ================================
// setup(): 
// ================================
void setup() {
  Serial.begin(SERIAL_DEBUG_BAUD);

  pinMode(LED_PIN, OUTPUT);
  pinMode(FAN_PIN, OUTPUT);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);
  dht20.begin();

  // ==== ADC config for Light Sensor (ESP32-S3) ====
  analogReadResolution(12);       // ADC 12-bit: 0..4095
  analogSetAttenuation(ADC_11db); 
  // ==================================================

  xTaskCreate(TaskWiFi,         "Wifi",             4096, NULL, 2, NULL);
  xTaskCreate(TaskSensor,       "Sensor Control",   4096, NULL, 2, NULL);
  xTaskCreate(TaskThingsboard,  "Thingsboard Ctrl", 4096, NULL, 2, NULL);
  xTaskCreate(TaskLEDControl,   "LED Control",      2048, NULL, 1, NULL);
  xTaskCreate(TaskFanControl,   "Fan Control",      2048, NULL, 1, NULL);
  xTaskCreate(TaskWarning,   "Fan Control",      2048, NULL, 1, NULL);
  xTaskCreate(TaskLightSensor,  "Light Sensor",     2048, NULL, 1, NULL);
}

void loop() {
  delay(10);
}
