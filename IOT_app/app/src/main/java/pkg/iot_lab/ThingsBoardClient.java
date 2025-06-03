package pkg.iot_lab;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * ThingsBoardClient: Dùng OkHttp để gọi REST API lấy telemetry và gửi RPC.
 */
public class ThingsBoardClient {
    private static final String TAG = "ThingsBoardClient";

    // Thay bằng Device ID của bạn (lấy từ Dashboard → Device → Details → Device ID)
    private static final String DEVICE_ID = "088c5570-1053-11f0-a887-6d1a184f2bb5";

    // Access Token của Device (mạch ESP32) – dùng chung cho REST và MQTT trên mạch
    private static final String DEVICE_TOKEN = "bjdomgwyqp8odbxpoagg";

    // Địa chỉ ThingsBoard (Core IoT)
    private static final String TB_HOST = "https://app.coreiot.io";

    // OkHttp client
    private final OkHttpClient httpClient;

    public ThingsBoardClient() {
        httpClient = new OkHttpClient.Builder().build();
    }

    /**
     * 1) Lấy giá trị telemetry gần nhất của temperature, humidity, light.
     *    Gọi callback onSuccess(Map<String, String>) hoặc onFailure().
     */
    public void getLatestTelemetry(final TelemetryCallback callback) {
        // URL: https://app.coreiot.io/api/plugins/telemetry/DEVICE/{DEVICE_ID}/values/timeseries?keys=temperature,humidity,light
        String url = TB_HOST
                + "/api/plugins/telemetry/DEVICE/"
                + DEVICE_ID
                + "/values/timeseries?keys=temperature,humidity,light";

        Request request = new Request.Builder()
                .url(url)
                .addHeader("X-Authorization", "Bearer " + DEVICE_TOKEN)
                .addHeader("Content-Type", "application/json")
                .get()
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                callback.onFailure(e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) {
                    callback.onFailure("HTTP error code: " + response.code());
                    return;
                }
                try {
                    String body = response.body().string();
                    JSONObject json = new JSONObject(body);

                    // Kết quả JSON dạng:
                    // {
                    //   "temperature": [ { "ts":..., "value":"24.30" } ],
                    //   "humidity":    [ { "ts":..., "value":"55.20" } ],
                    //   "light":       [ { "ts":..., "value":"123.40" } ]
                    // }
                    Map<String, String> result = new HashMap<>();
                    if (json.has("temperature")) {
                        JSONArray arrT = json.getJSONArray("temperature");
                        if (arrT.length() > 0) {
                            result.put("temperature", arrT.getJSONObject(0).getString("value"));
                        }
                    }
                    if (json.has("humidity")) {
                        JSONArray arrH = json.getJSONArray("humidity");
                        if (arrH.length() > 0) {
                            result.put("humidity", arrH.getJSONObject(0).getString("value"));
                        }
                    }
                    if (json.has("light")) {
                        JSONArray arrL = json.getJSONArray("light");
                        if (arrL.length() > 0) {
                            result.put("light", arrL.getJSONObject(0).getString("value"));
                        }
                    }

                    callback.onSuccess(result);
                } catch (Exception e) {
                    callback.onFailure(e.getMessage());
                }
            }
        });
    }

    /**
     * 2) Gửi RPC oneway để điều khiển LED hoặc FAN.
     *    methodName = "setLED" hoặc "setFan"
     *    param = true (bật) hoặc false (tắt)
     */
    public void sendCommand(final String methodName, final boolean param, final RpcCallback callback) {
        // URL: https://app.coreiot.io/api/plugins/rpc/oneway/{DEVICE_ID}
        String url = TB_HOST + "/api/plugins/rpc/oneway/" + DEVICE_ID;

        // JSON body:
        // { "method": "setLED", "params": true }
        JSONObject bodyJson = new JSONObject();
        try {
            bodyJson.put("method", methodName);
            bodyJson.put("params", param);
        } catch (Exception e) {
            callback.onFailure(e.getMessage());
            return;
        }

        MediaType mediaType = MediaType.parse("application/json");
        RequestBody requestBody = RequestBody.create(bodyJson.toString(), mediaType);

        Request request = new Request.Builder()
                .url(url)
                .addHeader("X-Authorization", "Bearer " + DEVICE_TOKEN)
                .addHeader("Content-Type", "application/json")
                .post(requestBody)
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                callback.onFailure(e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    callback.onSuccess("Sent RPC: " + methodName + " → " + param);
                } else {
                    callback.onFailure("HTTP error code: " + response.code());
                }
            }
        });
    }

    // Callback để trả về kết quả get telemetry
    public interface TelemetryCallback {
        void onSuccess(Map<String, String> telemetryData);
        void onFailure(String error);
    }

    // Callback để trả về kết quả send RPC
    public interface RpcCallback {
        void onSuccess(String msg);
        void onFailure(String error);
    }
}
