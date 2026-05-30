"""
Module theo dõi phiên làm việc:
- Đếm thời gian ngồi liên tục
- Phát hiện không di chuyển
- Theo dõi hoạt động của người dùng
"""

import time
import numpy as np


class SessionTracker:
    def __init__(self, config):
        self.config = config

        # Thời gian phiên
        self.session_start = time.time()
        self.sitting_start = time.time()
        self.last_user_seen = time.time()
        self.last_break_time = time.time()

        # Theo dõi chuyển động
        self.face_positions = []          # Lịch sử vị trí mặt
        self.MOVEMENT_WINDOW = 30         # Phân tích 30 giây gần nhất
        self.MOVEMENT_THRESHOLD = 0.02    # Tỷ lệ khung hình coi là "di chuyển"

        # Trạng thái
        self.user_present = False
        self.is_away = False
        self.away_start = None
        self.total_away_time = 0
        self.break_count = 0

        # Cờ thông báo (tránh spam)
        self.sitting_warned = False
        self.movement_warned = False

    def update_presence(self, face_detected):
        """Cập nhật trạng thái hiện diện của người dùng"""
        now = time.time()

        if face_detected:
            if self.is_away:
                # Người dùng quay lại
                away_duration = now - self.away_start
                self.total_away_time += away_duration
                self.is_away = False
                self.away_start = None

                # Reset sitting timer nếu nghỉ đủ lâu (>5 phút)
                if away_duration > 300:
                    self.sitting_start = now
                    self.sitting_warned = False
                    self.movement_warned = False
                    self.break_count += 1

            self.user_present = True
            self.last_user_seen = now
        else:
            # Không thấy mặt trong 3 giây → coi là đã rời đi
            if now - self.last_user_seen > 3:
                if not self.is_away:
                    self.is_away = True
                    self.away_start = now
                self.user_present = False

    def update_movement(self, face_landmarks, frame_shape):
        """
        Theo dõi chuyển động của đầu/mặt
        Lưu vị trí mũi mỗi frame để phân tích
        """
        if face_landmarks is None:
            return

        h, w = frame_shape[:2]
        nose = face_landmarks.landmark[1]
        pos = (nose.x, nose.y)  # Tọa độ chuẩn hóa 0-1

        now = time.time()
        self.face_positions.append((now, pos))

        # Chỉ giữ lịch sử trong MOVEMENT_WINDOW giây
        self.face_positions = [
            (t, p) for (t, p) in self.face_positions
            if now - t <= self.MOVEMENT_WINDOW
        ]

    def calculate_movement_score(self):
        """
        Tính điểm chuyển động (0-1)
        0 = không di chuyển, 1 = di chuyển nhiều
        """
        if len(self.face_positions) < 5:
            return 1.0  # Không đủ dữ liệu → giả sử đang di chuyển

        positions = [p for (_, p) in self.face_positions]
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]

        # Độ lệch chuẩn của vị trí
        std_x = np.std(xs)
        std_y = np.std(ys)
        movement = np.sqrt(std_x**2 + std_y**2)

        return movement

    def get_sitting_duration(self):
        """Thời gian ngồi liên tục (giây)"""
        return time.time() - self.sitting_start

    def get_session_duration(self):
        """Tổng thời gian từ khi bắt đầu"""
        return time.time() - self.session_start

    def check_warnings(self):
        """
        Kiểm tra và trả về các cảnh báo cần hiển thị
        """
        warnings = []
        now = time.time()

        sitting_sec  = self.get_sitting_duration()
        movement     = self.calculate_movement_score()

        # 1. Ngồi quá lâu
        if sitting_sec >= self.config["sitting_warning_time"] and not self.sitting_warned:
            warnings.append({
                "type": "sitting_too_long",
                "title": "⏰ Đã ngồi quá lâu!",
                "message": f"Bạn đã ngồi {int(sitting_sec//60)} phút rồi.\nHãy đứng dậy đi lại 5 phút nhé!",
                "severity": "high",
            })
            self.sitting_warned = True

        # 2. Ít di chuyển (cùng với đang ngồi >20 phút)
        if (movement < self.MOVEMENT_THRESHOLD
                and sitting_sec > 20 * 60
                and not self.movement_warned):
            warnings.append({
                "type": "no_movement",
                "title": "🚶 Hãy vận động!",
                "message": "Bạn gần như không di chuyển trong 30 phút qua.\nHãy giãn cơ hoặc đi lại một chút!",
                "severity": "medium",
            })
            self.movement_warned = True

        return warnings

    def mark_break_taken(self):
        """Ghi nhận người dùng đã nghỉ giải lao"""
        self.sitting_start = time.time()
        self.last_break_time = time.time()
        self.sitting_warned = False
        self.movement_warned = False
        self.break_count += 1

    def get_stats(self):
        """Thống kê phiên làm việc"""
        return {
            "session_duration": round(self.get_session_duration()),
            "sitting_duration": round(self.get_sitting_duration()),
            "total_away_time": round(self.total_away_time),
            "break_count": self.break_count,
            "movement_score": round(self.calculate_movement_score(), 4),
            "user_present": self.user_present,
        }