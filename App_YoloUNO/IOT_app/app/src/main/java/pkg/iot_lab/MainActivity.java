package pkg.iot_lab;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.github.angads25.toggle.widget.LabeledSwitch;

import java.util.Map;

public class MainActivity extends AppCompatActivity {
    private static final String TAG = "MainActivity";

    private ThingsBoardClient tbClient;
    private TextView tvTemp, tvHumi, tvLight;
    private LabeledSwitch btnLed, btnFan;

    // Handler để refresh định kỳ
    private Handler handler = new Handler(Looper.getMainLooper());
    private Runnable refreshRunnable = new Runnable() {
        @Override
        public void run() {
            fetchTelemetry();
            handler.postDelayed(this, 5000); // 5 giây/lần
        }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Ánh xạ các View
        tvTemp  = findViewById(R.id.tvTemp);
        tvHumi  = findViewById(R.id.tvHumi);
        tvLight = findViewById(R.id.tvLight);

        // Ánh xạ hai switch LED và FAN
        btnLed = findViewById(R.id.btnLed);
        btnFan = findViewById(R.id.btnFan);

        // Khởi tạo ThingsBoardClient
        tbClient = new ThingsBoardClient();

        // Khi switch LED thay đổi trạng thái (ON/OFF)
        btnLed.setOnToggledListener(new LabeledSwitch.OnToggleCallback() {
            @Override
            public void onToggle(LabeledSwitch labeledSwitch, boolean isOn) {
                // isOn == true → bật LED; isOn == false → tắt LED
                tbClient.sendCommand("setLED", isOn, new ThingsBoardClient.RpcCallback() {
                    @Override
                    public void onSuccess(String msg) {
                        Log.d(TAG, "LED RPC success: " + msg);
                    }
                    @Override
                    public void onFailure(String error) {
                        Log.e(TAG, "LED RPC failure: " + error);
                    }
                });
            }
        });

        // Khi switch FAN thay đổi trạng thái (ON/OFF)
        btnFan.setOnToggledListener(new LabeledSwitch.OnToggleCallback() {
            @Override
            public void onToggle(LabeledSwitch labeledSwitch, boolean isOn) {
                // isOn == true → bật FAN; isOn == false → tắt FAN
                tbClient.sendCommand("setFan", isOn, new ThingsBoardClient.RpcCallback() {
                    @Override
                    public void onSuccess(String msg) {
                        Log.d(TAG, "FAN RPC success: " + msg);
                    }
                    @Override
                    public void onFailure(String error) {
                        Log.e(TAG, "FAN RPC failure: " + error);
                    }
                });
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Bắt đầu auto-refresh telemetry
        handler.post(refreshRunnable);
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Dừng auto-refresh
        handler.removeCallbacks(refreshRunnable);
    }

    /**
     * Gọi ThingsBoardClient.getLatestTelemetry() rồi cập nhật UI.
     */
    private void fetchTelemetry() {
        tbClient.getLatestTelemetry(new ThingsBoardClient.TelemetryCallback() {
            @Override
            public void onSuccess(final Map<String, String> telemetryData) {
                // Callback chạy ở background thread → update UI trên UI thread
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        String t = telemetryData.get("temperature");
                        String h = telemetryData.get("humidity");
                        String l = telemetryData.get("light");
                        tvTemp.setText(t != null ? t + " °C" : "N/A");
                        tvHumi.setText(h != null ? h + " %" : "N/A");
                        tvLight.setText(l != null ? l + " lx" : "N/A");
                    }
                });
            }

            @Override
            public void onFailure(String error) {
                Log.e(TAG, "getTelemetry error: " + error);
            }
        });
    }
}
