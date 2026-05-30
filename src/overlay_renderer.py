"""
Module vẽ thông tin lên khung camera:
- Thanh trạng thái
- Thông số mắt/tư thế
- Cảnh báo màu sắc
"""

import cv2
import numpy as np
import time


class OverlayRenderer:
    def __init__(self, config):
        self.config = config

        # Font settings
        self.FONT       = cv2.FONT_HERSHEY_SIMPLEX
        self.FONT_SMALL = 0.45
        self.FONT_MED   = 0.6
        self.FONT_LARGE = 0.85

        # Màu sắc (BGR)
        self.COLOR_GREEN  = (0, 255, 100)
        self.COLOR_YELLOW = (0, 220, 255)
        self.COLOR_RED    = (50, 50, 255)
        self.COLOR_BLUE   = (255, 150, 50)
        self.COLOR_WHITE  = (240, 240, 240)
        self.COLOR_DARK   = (20, 20, 20)
        self.COLOR_BG     = (15, 15, 15)

    def draw_eye_contours(self, frame, eye_pts, color):
        """Vẽ đường viền mắt"""
        if len(eye_pts) >= 6:
            pts = np.array(eye_pts, dtype=np.int32)
            cv2.polylines(frame, [pts], True, color, 1, cv2.LINE_AA)

    def draw_status_bar(self, frame, eye_data, posture_data, session_data):
        """Vẽ thanh trạng thái ở dưới cùng"""
        h, w = frame.shape[:2]
        bar_h = 90

        # Nền mờ
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - bar_h), (w, h), self.COLOR_BG, -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Dòng phân cách
        cv2.line(frame, (0, h - bar_h), (w, h - bar_h), (60, 60, 60), 1)

        # ─── Cột 1: Thời gian ngồi ────────────────────────
        sitting_sec = session_data.get("sitting_duration", 0)
        sitting_min = int(sitting_sec // 60)
        sitting_str = f"{sitting_min:02d}:{int(sitting_sec % 60):02d}"

        sitting_color = self.COLOR_GREEN
        if sitting_sec > 40 * 60:
            sitting_color = self.COLOR_RED
        elif sitting_sec > 30 * 60:
            sitting_color = self.COLOR_YELLOW

        cv2.putText(frame, "NGOI", (10, h - 65),
                    self.FONT, self.FONT_SMALL, (140, 140, 140), 1)
        cv2.putText(frame, sitting_str, (10, h - 42),
                    self.FONT, self.FONT_MED, sitting_color, 2)

        # ─── Cột 2: Chớp mắt ──────────────────────────────
        blink_rate = eye_data.get("blink_rate", 0)
        blink_color = self.COLOR_GREEN
        if blink_rate < 10:
            blink_color = self.COLOR_RED
        elif blink_rate < 15:
            blink_color = self.COLOR_YELLOW

        cv2.putText(frame, "CHOP/PHUT", (80, h - 65),
                    self.FONT, self.FONT_SMALL, (140, 140, 140), 1)
        cv2.putText(frame, f"{blink_rate:.0f}", (80, h - 42),
                    self.FONT, self.FONT_MED, blink_color, 2)

        # ─── Cột 3: EAR (Eye Aspect Ratio) ────────────────
        ear = eye_data.get("ear", 0.3)
        ear_color = self.COLOR_GREEN if ear > 0.25 else self.COLOR_RED
        cv2.putText(frame, "EAR", (170, h - 65),
                    self.FONT, self.FONT_SMALL, (140, 140, 140), 1)
        cv2.putText(frame, f"{ear:.2f}", (170, h - 42),
                    self.FONT, self.FONT_MED, ear_color, 2)

        # ─── Cột 4: Tư thế ────────────────────────────────
        tilt  = posture_data.get("tilt_angle", 0)
        pitch = posture_data.get("pitch_angle", 0)
        posture_color = self.COLOR_RED if posture_data.get("is_bad_posture") else self.COLOR_GREEN
        posture_label = "XAU" if posture_data.get("is_bad_posture") else "TOT"

        cv2.putText(frame, "TU THE", (235, h - 65),
                    self.FONT, self.FONT_SMALL, (140, 140, 140), 1)
        cv2.putText(frame, posture_label, (235, h - 42),
                    self.FONT, self.FONT_MED, posture_color, 2)

        # ─── Cột 5: Thời gian phiên ───────────────────────
        sess_sec = session_data.get("session_duration", 0)
        sess_str = f"{int(sess_sec // 3600):02d}:{int((sess_sec % 3600) // 60):02d}:{int(sess_sec % 60):02d}"
        cv2.putText(frame, "PHIEN", (w - 120, h - 65),
                    self.FONT, self.FONT_SMALL, (140, 140, 140), 1)
        cv2.putText(frame, sess_str, (w - 120, h - 42),
                    self.FONT, self.FONT_MED, self.COLOR_WHITE, 2)

        # ─── Warnings ─────────────────────────────────────
        warnings_text = []
        if "no_blink" in eye_data.get("warnings", []):
            warnings_text.append("Chua chop mat!")
        if posture_data.get("is_bad_posture"):
            issues = posture_data.get("posture_issues", [])
            if issues:
                warnings_text.append(issues[0])

        if warnings_text:
            warn_str = " | ".join(warnings_text)
            # Flash effect
            alpha = abs(np.sin(time.time() * 3))
            warn_color = (int(50 * alpha), int(50 * alpha), int(255 * alpha + 150))
            cv2.putText(frame, f"! {warn_str}", (10, h - 18),
                        self.FONT, self.FONT_SMALL, warn_color, 1)

    def draw_title(self, frame):
        """Vẽ tiêu đề ở góc trên trái"""
        cv2.putText(frame, "EyeGuard", (10, 25),
                    self.FONT, self.FONT_MED, self.COLOR_BLUE, 2)
        cv2.putText(frame, "by AI Vision", (10, 42),
                    self.FONT, self.FONT_SMALL, (100, 100, 100), 1)

    def draw_calibration(self, frame, frames_done, frames_needed):
        """Hiển thị trạng thái calibration"""
        h, w = frame.shape[:2]
        progress = frames_done / frames_needed
        bar_w    = int(w * 0.6)
        bar_x    = (w - bar_w) // 2
        bar_y    = h // 2

        # Nền
        overlay = frame.copy()
        cv2.rectangle(overlay, (bar_x - 10, bar_y - 40), (bar_x + bar_w + 10, bar_y + 30),
                      (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        cv2.putText(frame, "Dang khoi dong... Nhin thang vao camera",
                    (bar_x, bar_y - 15), self.FONT, self.FONT_SMALL, self.COLOR_WHITE, 1)

        # Thanh progress
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 15), (40, 40, 40), -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + 15),
                      self.COLOR_GREEN, -1)

    def draw_no_face(self, frame):
        """Hiển thị khi không detect được mặt"""
        h, w = frame.shape[:2]
        cv2.putText(frame, "Khong phat hien khuon mat",
                    (w // 2 - 150, h // 2),
                    self.FONT, self.FONT_MED, self.COLOR_YELLOW, 2)

    def render(self, frame, eye_data, posture_data, session_data, face_detected, is_calibrated, calib_frames=0):
        """Hàm render chính"""
        if not face_detected:
            self.draw_title(frame)
            self.draw_no_face(frame)
            return frame

        if not is_calibrated:
            self.draw_title(frame)
            self.draw_calibration(frame, calib_frames, 30)
            return frame

        # Vẽ contour mắt
        if self.config.get("show_landmarks") and eye_data:
            left_pts  = eye_data.get("left_eye_pts", [])
            right_pts = eye_data.get("right_eye_pts", [])
            eye_color = self.COLOR_RED if eye_data.get("ear", 0.3) < 0.25 else self.COLOR_GREEN
            self.draw_eye_contours(frame, left_pts,  eye_color)
            self.draw_eye_contours(frame, right_pts, eye_color)

        # Vẽ các thành phần UI
        if self.config.get("show_stats_overlay", True):
            self.draw_status_bar(frame, eye_data or {}, posture_data or {}, session_data or {})

        self.draw_title(frame)

        return frame