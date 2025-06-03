# data_collector.py

import time
import json
from collections import deque

import requests

# ——————————————
# 1) Cấu hình chung
# ——————————————
JWT_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJuYW0ucGhhbTQyMjAwM0BoY211dC5lZHUudm4iLCJ1c2VySWQiOiIxMDg2YjMwMC1lZTY3LTExZWYtODdiNS0yMWJjY2Y3ZDI5ZDUiLCJzY29wZXMiOlsiVEVOQU5UX0FETUlOIl0sInNlc3Npb25JZCI6IjU5NDM1OGNjLWZlZDctNDBlYi1iZTc2LTVkYzk2YTVlNTQ5NyIsImV4cCI6MTc0ODgzNzkzOCwiaXNzIjoiY29yZWlvdC5pbyIsImlhdCI6MTc0ODgyODkzOCwiZmlyc3ROYW1lIjoiTkFNIiwibGFzdE5hbWUiOiJQSOG6oE0gVEjDgE5IIiwiZW5hYmxlZCI6dHJ1ZSwiaXNQdWJsaWMiOmZhbHNlLCJ0ZW5hbnRJZCI6IjEwN2U0ZTkwLWVlNjctMTFlZi04N2I1LTIxYmNjZjdkMjlkNSIsImN1c3RvbWVySWQiOiIxMzgxNDAwMC0xZGQyLTExYjItODA4MC04MDgwODA4MDgwODAifQ.HWazPEXLC8kbSb9AMmcbFjZaJVTF2nQvCYvAgXMrMKerMcl5sa9rtUXm_chcWsvgdHueQfNaVxniwVGwd2JfQQ"
DEVICE_ID = "088c5570-1053-11f0-a887-6d1a184f2bb5"

BUFFER_FILE = "buffer.json"  # File sẽ chứa 20 mẫu cuối cùng

# ——————————————
# 2) Hàm fetch 1 mẫu mới nhất
# ——————————————
def fetch_latest_telemetry(entity_type, entity_id, jwt_token, keys):
    """
    Gọi: GET /api/plugins/telemetry/{entityType}/{entityId}/values/timeseries
         ?keys=…&limit=1&useStrictDataTypes=false
    Trả về JSON như:
      {
        "temperature": [{"ts":…, "value":"…"}],    # chỉ 1 phần tử
        "humidity":    [{"ts":…, "value":"…"}],    # chỉ 1 phần tử
        "light":       [{"ts":…, "value":"…"}]     # chỉ 1 phần tử
      }
    Lấy ra sample mới nhất (vì limit=1).
    """
    base_url = f"https://app.coreiot.io/api/plugins/telemetry/{entity_type}/{entity_id}/values/timeseries"
    headers = {
        "X-Authorization": f"Bearer {jwt_token}",
        "Accept":          "application/json"
    }
    params = {
        "keys": keys,
        "limit": 1,
        "useStrictDataTypes": "false"
    }
    r = requests.get(base_url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

# ——————————————
# 3) Parse JSON trả về 1 mẫu thành dict
# ——————————————
def parse_single_telemetry(js):
    """
    Input js dạng:
      {
        "temperature": [{"ts": 165..., "value":"28.50"}],
        "humidity":    [{"ts": 165..., "value":"60.10"}],
        "light":       [{"ts": 165..., "value":"150"}]
      }
    Trả về dict: {"temperature": float, "humidity": float, "light": float}
    Nếu thiếu key hoặc array rỗng, giá trị mặc định = 0.0
    """
    def get_val(arr, key):
        lst = js.get(key, [])
        if isinstance(lst, list) and len(lst) > 0:
            return float(lst[0]["value"])
        return 0.0

    return {
        "temperature": get_val(js, "temperature"),
        "humidity":    get_val(js, "humidity"),
        "light":       get_val(js, "light")
    }

# ——————————————
# 4) Ghi buffer (list[dict]) vào file JSON
# ——————————————
def save_buffer_to_file(buffer_list):
    """
    buffer_list: deque có tối đa 20 phần tử, mỗi phần tử là dict {"temperature":..,"humidity":..,"light":..}
    Ghi đè file BUFFER_FILE thành JSON.
    """
    with open(BUFFER_FILE, "w", encoding="utf-8") as f:
        json.dump(list(buffer_list), f, ensure_ascii=False, indent=2)
    print(f"[DATA_COLLECTOR] Đã ghi buffer ({len(buffer_list)} mẫu) vào {BUFFER_FILE}")

# ——————————————
# 5) Vòng lặp chính
# ——————————————
def main_loop(poll_interval_s=5):
    # Khởi buffer (deque) để giữ tối đa 20 mẫu
    buffer_deque = deque(maxlen=20)

    print(f"[DATA_COLLECTOR] Bắt đầu lấy telemetry mỗi {poll_interval_s}s…")
    while True:
        try:
            # A) Fetch 1 mẫu mới nhất
            resp_json = fetch_latest_telemetry(
                entity_type="DEVICE",
                entity_id=DEVICE_ID,
                jwt_token=JWT_TOKEN,
                keys="temperature,humidity,light"
            )

            # B) Parse thành dict với 3 giá trị float
            single = parse_single_telemetry(resp_json)
            # Ví dụ single = {"temperature": 28.50, "humidity": 60.10, "light": 150.0}
            print(f"[DATA_COLLECTOR] Mẫu mới nhận được: T={single['temperature']:.2f}, "
                  f"H={single['humidity']:.2f}, L={single['light']:.2f}")

            # C) Đẩy vào buffer deque (nếu đã 20 mẫu, deque tự xóa mẫu cũ nhất)
            buffer_deque.append(single)

            # D) Ghi toàn bộ buffer_deque (hiện có ≤20 phần tử) vào file JSON
            save_buffer_to_file(buffer_deque)

            # E) In debug nội dung buffer
            print(f"[DATA_COLLECTOR] Buffer hiện có {len(buffer_deque)} mẫu:")
            for idx, entry in enumerate(buffer_deque, 1):
                print(f"  #{idx}: T={entry['temperature']:.2f}, "
                      f"H={entry['humidity']:.2f}, L={entry['light']:.2f}")

        except Exception as e:
            print("[DATA_COLLECTOR][ERROR] Khi fetch hoặc ghi file:", e)

        # F) Chờ interval trước khi fetch tiếp
        time.sleep(poll_interval_s)

if __name__ == "__main__":
    main_loop(poll_interval_s=5)
