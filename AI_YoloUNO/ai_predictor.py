# ai_predictor.py

import time
import json
import torch
import numpy as np
import smtplib
from email.mime.text import MIMEText
import torch.nn as nn
import torch.nn.functional as F
from collections import deque

# ——————————————
# 1) Cấu hình chung
# ——————————————
BUFFER_FILE    = "buffer.json"  # dùng chung với data_collector
TEMP_THRESHOLD  = 25.0
HUMI_THRESHOLD  = 65.0
LIGHT_THRESHOLD = 2000.0   # ngưỡng cảnh báo cho giá trị dự đoán

# Thông tin gửi email (App Password đã được tạo)
EMAIL_HOST     = "smtp.gmail.com"
EMAIL_PORT     = 587
EMAIL_USER     = "hideinyourheart123@gmail.com"
EMAIL_PASS     = "hjpfificaozzjmej"  # App Password 16 ký tự
EMAIL_RECEIVER = "hideinyourheart123@gmail.com"

# ——————————————
# 2) Định nghĩa mạng CNN (1D)
# ——————————————
class CNNPredictor(nn.Module):
    def __init__(self, input_channels=3, sequence_length=20):
        super(CNNPredictor, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=input_channels, out_channels=512, kernel_size=3)
        self.pool  = nn.MaxPool1d(kernel_size=3)
        conv_output_size = ((sequence_length - 3 + 1) // 3) * 512
        self.fc1 = nn.Linear(conv_output_size, 256)
        self.fc2 = nn.Linear(256, input_channels)

    def forward(self, x):
        # x: (batch_size, 20, 3) → permute → (batch_size, 3, 20)
        x = x.permute(0, 2, 1)
        x = F.relu(self.conv1(x))   # (batch_size,512,18)
        x = self.pool(x)            # (batch_size,512,6)
        x = x.flatten(start_dim=1)  # (batch_size, 3072)
        x = F.relu(self.fc1(x))     # (batch_size, 256)
        out = self.fc2(x)           # (batch_size, 3)
        return out

# Load model
model = CNNPredictor(input_channels=3, sequence_length=20)
state_dict = torch.load('./model.pth', map_location=torch.device('cpu'))
model.load_state_dict(state_dict)
model.eval()

# ——————————————
# 3) Hàm đọc toàn bộ buffer.json vào deque(maxlen=20)
# ——————————————
def load_buffer(buffer_file):
    """
    Đọc file JSON (list dict). Nếu list có <20 phần tử, raise ValueError.
    Trả về deque(buffer_list, maxlen=20).
    """
    with open(buffer_file, "r", encoding="utf-8") as f:
        buffer_list = json.load(f)

    if not isinstance(buffer_list, list) or len(buffer_list) < 20:
        raise ValueError(f"File {buffer_file} phải có tối thiểu 20 phần tử, hiện có {len(buffer_list)}")
    # Chỉ sử dụng 20 phần tử cuối cùng nếu file có >20 (thường không xảy ra vì data_collector luôn giới hạn maxlen=20)
    last_20 = buffer_list[-20:]
    dq = deque(last_20, maxlen=20)
    return dq

# ——————————————
# 4) Hàm ghi deque vào buffer.json (ghi đè)
# ——————————————
def save_buffer(buffer_deque, buffer_file):
    with open(buffer_file, "w", encoding="utf-8") as f:
        json.dump(list(buffer_deque), f, ensure_ascii=False, indent=2)
    print(f"[AI_PREDICTOR] Đã cập nhật buffer ({len(buffer_deque)} phần tử) vào {buffer_file}")

# ——————————————
# 5) Hàm gửi email cảnh báo
# ——————————————
def send_alert_email(temp, humi, light):
    body = (
        f"Alert from AI predictor:\n"
        f"  Predicted Temperature: {temp:.2f} °C\n"
        f"  Predicted Humidity:    {humi:.2f} %\n"
        f"  Predicted Light:       {light:.2f} lux\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = "AI Alert Notification"
    msg["From"]    = EMAIL_USER
    msg["To"]      = EMAIL_RECEIVER

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    print("[AI_PREDICTOR] Email alert sent.")

# ——————————————
# 6) Hàm convert deque thành numpy array (20,3) cho model
# ——————————————
def deque_to_array(buffer_deque):
    """
    Input: deque 20 phần tử, mỗi phần tử dict có keys "temperature","humidity","light"
    Trả về numpy array shape (20,3) float32, theo thứ tự deque.
    """
    arr = np.zeros((20, 3), dtype=np.float32)
    for i, entry in enumerate(buffer_deque):
        arr[i, 0] = float(entry.get("temperature", 0.0))
        arr[i, 1] = float(entry.get("humidity",    0.0))
        arr[i, 2] = float(entry.get("light",       0.0))
    return arr

# ——————————————
# 7) Vòng lặp chính
# ——————————————
def main_loop(poll_interval_s=5):
    print(f"[AI_PREDICTOR] Bắt đầu chạy mỗi {poll_interval_s}s…")
    while True:
        try:
            # A) Load deque từ buffer.json (đảm bảo có 20 phần tử)
            buffer_deque = load_buffer(BUFFER_FILE)

            # B) In debug buffer telemetry ban đầu
            print("[AI_PREDICTOR] Buffer telemetry (20 mẫu):")
            for idx, entry in enumerate(buffer_deque, 1):
                t = entry.get("temperature", 0.0)
                h = entry.get("humidity", 0.0)
                l = entry.get("light", 0.0)
                print(f"  #{idx}: T={t:.2f}, H={h:.2f}, L={l:.2f}")

            # C) Chuyển deque → numpy array → torch tensor
            arr = deque_to_array(buffer_deque)                # shape (20,3)
            input_tensor = torch.from_numpy(arr).unsqueeze(0)  # shape (1,20,3)

            # D) Inference
            with torch.no_grad():
                pred = model(input_tensor).squeeze(0).numpy()  # shape (3,)

            tmp_pred   = float(pred[0])
            humi_pred  = float(pred[1])
            light_pred = float(pred[2])
            print(f"[AI_PREDICTOR][PRED] T={tmp_pred:.2f}, H={humi_pred:.2f}, L={light_pred:.2f}")

            # E) Tạo entry mới từ giá trị prediction, gán timestamp hiện tại
            new_entry = {
                "ts": int(time.time() * 1000),
                "temperature": tmp_pred,
                "humidity":    humi_pred,
                "light":       light_pred
            }

            # F) Pop phần tử cũ nhất (deque maxlen=20 tự làm) và append prediction
            buffer_deque.append(new_entry)
            # [Lưu ý] Khi append, deque tự xoá phần tử #0 nếu đã đầy 20

            # G) Ghi đè buffer.json
            save_buffer(buffer_deque, BUFFER_FILE)

            # H) In debug buffer đã cập nhật
            print(f"[AI_PREDICTOR] Sau khi append prediction, buffer hiện có {len(buffer_deque)} phần tử:")
            for idx, entry in enumerate(buffer_deque, 1):
                t = entry.get("temperature", 0.0)
                h = entry.get("humidity", 0.0)
                l = entry.get("light", 0.0)
                ts = entry.get("ts", 0)
                marker = "(PRED)" if idx == len(buffer_deque) else ""
                print(f"  #{idx} ts={ts}: T={t:.2f}, H={h:.2f}, L={l:.2f} {marker}")

            # I) Nếu giá trị dự đoán vượt ngưỡng, gửi email
            if (tmp_pred > TEMP_THRESHOLD or
                humi_pred > HUMI_THRESHOLD or
                light_pred > LIGHT_THRESHOLD):
                send_alert_email(tmp_pred, humi_pred, light_pred)

        except FileNotFoundError:
            print(f"[AI_PREDICTOR] File {BUFFER_FILE} chưa tồn tại. Đợi vòng sau…")
        except ValueError as ve:
            print(f"[AI_PREDICTOR] Buffer không đủ 20 mẫu ({ve}). Đợi vòng sau…")
        except Exception as e:
            print(f"[AI_PREDICTOR][ERROR] {e}")

        time.sleep(poll_interval_s)

if __name__ == "__main__":
    main_loop(poll_interval_s=5)
