# 👁️ Hệ thống nhắc nhở nghỉ ngơi thông minh · Camera + AI

<h2 align="center">
    <a href="https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin">
    🎓 Faculty of Information Technology (DaiNam University)
    </a>
</h2>

<h2 align="center">
   EyeGuard — AI-Powered Eye Strain & Posture Monitoring System
</h2>

<div align="center">
    <p align="center">
        <img src="docs/aiotlab_logo.png" width="170"/>
        <img src="docs/fitdnu_logo.png" width="180"/>
        <img src="docs/dnu_logo.png" width="200"/>
    </p>

[![AIoTLab](https://img.shields.io/badge/AIoTLab-green?style=for-the-badge)](https://www.facebook.com/DNUAIoTLab)
[![Faculty of Information Technology](https://img.shields.io/badge/Faculty%20of%20Information%20Technology-blue?style=for-the-badge)](https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin)
[![DaiNam University](https://img.shields.io/badge/DaiNam%20University-orange?style=for-the-badge)](https://dainam.edu.vn)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-teal?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10-orange?style=for-the-badge)](https://mediapipe.dev)

</div>

---

# EyeGuard 👁️🛡️
**Hệ thống nhắc nhở nghỉ ngơi thông minh** sử dụng Camera và AI — theo dõi mắt, tư thế ngồi và thời gian làm việc liên tục theo thời gian thực.

> Chỉ cần webcam laptop thông thường. Không cần phần cứng bổ sung. Chạy hoàn toàn cục bộ, bảo mật riêng tư.

---

## 🚀 Hình ảnh các chức năng

<p align="center">
  <img src="docs/project photo/1.png" alt="Dashboard tổng quan" width="800"/>
</p>
<p align="center">
  <em>ẢNH GIAO DIỆN</em>
</p>

<p align="center">
  <img src="docs/project photo/2.png" alt="Camera feed" width="700"/>
</p>
<p align="center">
  <em>ẢNH GIAO DIỆN</em>
</p>

<p align="center">
  <img src="docs/project photo/3.png" alt="Cảnh báo" width="700"/>
</p>
<p align="center">
  <em>ẢNH GIAO DIỆN</em>
</p>

<p align="center">
  <img src="docs/project photo/4.png" alt="Chỉ số mắt" width="700"/>
</p>
<p align="center">
  <em>ẢNH GIAO DIỆN</em>
</p>

---

## 📁 Cấu trúc dự án

```
eyeguard/
│
├── main.py                     # Entry point desktop (Tkinter)
├── web_server.py               # Entry point web (FastAPI + WebSocket)
├── requirements-web.txt        # Dependencies cho web version
│
├── static/
│   └── index.html              # Dashboard web (Neumorphism UI)
│
├── src/
│   ├── app.py                  # EyeGuardApp — controller chính
│   ├── eye_tracker.py          # Theo dõi mắt: EAR, blink rate
│   ├── posture_tracker.py      # Tư thế đầu: tilt, pitch, khoảng cách
│   ├── body_tracker.py         # Tư thế thân: neck lean, shoulder
│   ├── sitting_detector.py     # Nhận diện ngồi/đứng (adaptive calibration)
│   ├── session_tracker.py      # Thống kê phiên làm việc
│   ├── notification_manager.py # Quản lý thông báo hệ thống
│   ├── settings_manager.py     # Cấu hình & ngưỡng cảnh báo
│   ├── dashboard_ui.py         # Giao diện Tkinter (desktop)
│   └── settings_ui.py          # Cài đặt UI (desktop)
│
├── logs/
│   └── eyeguard.log            # Log hệ thống
│
└── README.md
```

---

## 🚀 Cách chạy — 3 bước

### Bước 1: Cài đặt môi trường

```bash
# Yêu cầu Python 3.10+
python --version

# Tạo virtual environment (khuyến nghị)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Cài dependencies
pip install -r requirements-web.txt
```

---

### Bước 2: Chạy Server

```bash
# Cách 1 — Đơn giản nhất
uvicorn web_server:app --host 0.0.0.0 --port 8000

# Cách 2 — Có auto-reload khi phát triển
uvicorn web_server:app --host 0.0.0.0 --port 8000 --reload

# Cách 3 — Desktop app (Tkinter, không cần trình duyệt)
python main.py
```

> ⚠️ **Lưu ý**: Luôn dùng `--workers 1` vì camera là thiết bị singleton, không thể chia sẻ giữa nhiều process.

---

### Bước 3: Mở Dashboard

Mở trình duyệt: **http://localhost:8000**

Nhấn nút **▶ BẮT ĐẦU** để kích hoạt camera và bắt đầu theo dõi.

---

## 🧠 Tính năng chính

| Tính năng | Mô tả | Công nghệ |
|---|---|---|
| 👁️ Theo dõi mắt | EAR, đếm nháy mắt, cảnh báo mắt khô | MediaPipe Face Mesh |
| 🪑 Nhận diện ngồi/đứng | Adaptive calibration theo người dùng | MediaPipe Pose + Z-score |
| 🧍 Phân tích tư thế | Neck lean, shoulder tilt, head tilt | MediaPipe Pose + Face Mesh |
| ⏱️ Quy tắc 20-20-20 | Nhắc nhở nghỉ mắt đúng giờ | SessionTracker |
| 📊 Dashboard realtime | Camera feed + số liệu cập nhật liên tục | FastAPI + WebSocket |
| 🔔 Thông báo thông minh | Phân 3 mức: cao / trung bình / thấp | NotificationManager |
| ⚙️ Cấu hình linh hoạt | Tuỳ chỉnh ngưỡng cảnh báo theo nhu cầu | SettingsManager |

---

## 🏗️ Kiến trúc hệ thống

```
Browser ←──── WebSocket ────→ FastAPI (Main Thread)
                                      │
                               Broadcaster (asyncio)
                                      │  Queue
                               Worker Thread
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                  MediaPipe Face Mesh        MediaPipe Pose
                         │                         │
                  EyeTracker               SittingDetector
                  PostureTracker           BodyTracker
                         │                         │
                         └────────────┬────────────┘
                                   Camera
                               (Webcam laptop)
```

**Luồng xử lý mỗi frame:**
```
Đọc frame → Flip mirror → BGR→RGB
      ↓
MediaPipe Face Mesh + Pose (song song)
      ↓
Cập nhật tất cả trackers
      ↓
Vẽ skeleton + HUD lên frame
      ↓
Encode JPEG (quality 70) → base64
      ↓
Đóng gói JSON payload → Queue
      ↓
WebSocket → Browser (~30fps)
```

---

## 🤖 Thuật toán SittingDetector

Bộ phát hiện ngồi/đứng sử dụng **4 tín hiệu kết hợp** với adaptive calibration:

```
Tín hiệu                  Trọng số   Ý nghĩa
──────────────────────────────────────────────────
Face Size (shoulder width)    4      Gần camera = ngồi
Shoulder Height               2      Vai thấp = ngồi
Nose-to-Shoulder Distance     2      Khoảng cách nhỏ = ngồi
Face Continuity               1      Liên tục hiện diện
Head Stability                1      Đầu ổn định = ngồi
```

**50 frame đầu** → học baseline cá nhân (không cảnh báo)  
**Sau calibration** → dùng z-score để phát hiện lệch khỏi "tư thế bình thường" của chính người đó

---

## 📡 REST API

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/` | Dashboard HTML |
| `POST` | `/api/start` | Bắt đầu tracking camera |
| `POST` | `/api/stop` | Dừng tracking |
| `POST` | `/api/break` | Đánh dấu nghỉ giải lao |
| `POST` | `/api/reset` | Reset phiên làm việc |
| `GET` | `/api/status` | Lấy trạng thái hiện tại (JSON) |
| `GET` | `/api/settings` | Lấy cài đặt |
| `POST` | `/api/settings` | Cập nhật cài đặt |
| `WS` | `/ws` | WebSocket stream realtime |

---

## ⚙️ Cấu hình

Chỉnh ngưỡng cảnh báo trong `SettingsManager` hoặc qua API:

| Tham số | Mặc định | Mô tả |
|---|---|---|
| `sitting_warning_min` | 45 | Phút ngồi liên tục trước khi cảnh báo |
| `eye_strain_time` | 1200 | Giây liên tục nhìn màn hình (quy tắc 20 phút) |
| `blink_ear_threshold` | 0.25 | Ngưỡng EAR để phát hiện nháy mắt |
| `camera_index` | 0 | Index webcam (0 = camera mặc định) |
| `notification_cooldown` | 300 | Giây giữa 2 cảnh báo cùng loại |
| `bad_posture_warn_sec` | 120 | Giây tư thế xấu trước khi cảnh báo |

---

## 🔔 Các loại cảnh báo

```
🔴 CAO       Ngồi quá X phút — hãy đứng dậy đi lại
🟠 TRUNG BÌNH  Tư thế xấu kéo dài — chỉnh lại tư thế
🟠 TRUNG BÌNH  Ít cử động — hãy vươn vai
🔵 THẤP      Không nháy mắt — mắt đang khô
🔵 THẤP      20 phút trôi qua — nhìn xa 20 giây
```

---

## 🌐 Deploy với Nginx (Production)

```nginx
server {
    listen 80;
    server_name eyeguard.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

---

## 📦 Dependencies

| Thư viện | Phiên bản | Dùng cho |
|---|---|---|
| `mediapipe` | 0.10+ | Face Mesh 478 điểm + Pose 33 điểm |
| `opencv-python` | 4.8+ | Đọc camera, xử lý ảnh, encode JPEG |
| `fastapi` | 0.110+ | Web server, REST API, WebSocket |
| `uvicorn` | 0.29+ | ASGI server |
| `Pillow` | 10.0+ | Xử lý ảnh cho desktop version |
| `numpy` | latest | Tính toán ma trận, thống kê |

---

## ⚠️ Lưu ý

- Camera phải gắn vào **máy chạy server** (không phải browser)
- Dùng `--workers 1` — camera không chia sẻ được giữa nhiều process
- Ánh sáng đủ sáng giúp MediaPipe nhận diện chính xác hơn
- **50 frame đầu** là giai đoạn calibration — hãy ngồi đúng tư thế
- Dữ liệu camera **không gửi lên cloud**, xử lý hoàn toàn cục bộ
- **HTTPS** cần thiết nếu deploy public (webcam API yêu cầu secure context)

---

## 👜 Thông tin cá nhân

**Họ tên**: Nguyễn Hoàng Liêm.  
**Lớp**: CNTT 16-03.  
**Email**: liemnguyenhoang22@gmail.com.

© 2026 AIoTLab, Faculty of Information Technology, DaiNam University. All rights reserved.

---