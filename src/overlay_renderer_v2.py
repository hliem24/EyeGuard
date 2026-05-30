"""
Overlay Renderer v2 – vẽ lên camera frame:
  - Skeleton tư thế (Pose landmarks)
  - HUD thống kê đẹp với gradient-like panels
  - Cảnh báo flash màu
  - Thanh tiến trình thời gian ngồi
"""

import cv2
import numpy as np
import time
import math


class OverlayRendererV2:
    def __init__(self, config: dict):
        self.config = config

        self.FONT       = cv2.FONT_HERSHEY_SIMPLEX
        self.FONT_TINY  = 0.38
        self.FONT_SMALL = 0.48
        self.FONT_MED   = 0.62
        self.FONT_LARGE = 0.85

        # Bảng màu (BGR)
        self.TEAL      = (170, 212,  0)    # #00D4AA in BGR
        self.TEAL_DIM  = ( 80, 120, 50)
        self.RED       = ( 73,  81, 248)   # #f85149
        self.YELLOW    = ( 65, 179, 227)   # #e3b341
        self.GREEN     = ( 80, 185,  63)   # #3fb950
        self.BLUE      = (255, 166,  88)   # #58a6ff
        self.WHITE     = (230, 237, 243)
        self.GRAY      = (100, 110, 120)
        self.DARK      = ( 13,  17,  23)   # #0d1117
        self.DARK2     = ( 22,  27,  34)   # #161b22
        self.PURPLE    = (204, 130, 188)

        # Skeleton connections (chỉ thân trên – phần liên quan khi ngồi làm việc)
        self.POSE_CONNECTIONS = [
            (11, 12),  # vai trái – vai phải
            (11, 13),  # vai trái – khuỷu tay trái
            (13, 15),  # khuỷu – cổ tay trái
            (12, 14),  # vai phải – khuỷu tay phải
            (14, 16),  # khuỷu – cổ tay phải
            (11, 23),  # vai trái – hông trái
            (12, 24),  # vai phải – hông phải
            (23, 24),  # hông trái – hông phải
            (7,  11),  # tai trái – vai trái
            (8,  12),  # tai phải – vai phải
        ]

    # ───────────────────────── Skeleton ────────────────────────────
    def draw_skeleton(self, frame, pose_results, body_data, warnings):
        """Vẽ skeleton tư thế lên frame"""
        if not self.config.get("show_body_skeleton", True):
            return
        if pose_results is None or not pose_results.pose_landmarks:
            return

        h, w = frame.shape[:2]
        lm = pose_results.pose_landmarks.landmark
        is_bad = body_data.get("is_bad_posture", False)

        def pt(idx):
            l = lm[idx]
            return (int(l.x * w), int(l.y * h))

        bone_color = self.RED if is_bad else self.TEAL

        # Vẽ các đường xương
        for (a, b) in self.POSE_CONNECTIONS:
            try:
                pa, pb = pt(a), pt(b)
                # Chỉ vẽ nếu cả 2 điểm trong khung hình
                if all(0 < x < w and 0 < y < h for x, y in [pa, pb]):
                    cv2.line(frame, pa, pb, bone_color, 2, cv2.LINE_AA)
            except Exception:
                pass

        # Vẽ các điểm mốc
        key_pts = [7, 8, 11, 12, 13, 14, 15, 16, 23, 24]
        for idx in key_pts:
            try:
                p = pt(idx)
                if 0 < p[0] < w and 0 < p[1] < h:
                    cv2.circle(frame, p, 4, bone_color, -1, cv2.LINE_AA)
                    cv2.circle(frame, p, 6, self.DARK, 1,  cv2.LINE_AA)
            except Exception:
                pass

        # Vẽ đường cột sống nếu có
        pts = body_data.get("pts", {})
        if "shoulder_mid" in pts and "hip_mid" in pts:
            sm = (int(pts["shoulder_mid"][0]), int(pts["shoulder_mid"][1]))
            hm = (int(pts["hip_mid"][0]),      int(pts["hip_mid"][1]))
            spine_color = self.RED if "spine_lean" in warnings else self.PURPLE
            cv2.line(frame, sm, hm, spine_color, 2, cv2.LINE_AA)
            cv2.circle(frame, sm, 6, self.PURPLE, -1, cv2.LINE_AA)

    # ───────────────────────── HUD panels ──────────────────────────
    def _draw_panel(self, frame, x, y, w, h, alpha=0.78):
        """Vẽ panel nền mờ"""
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x+w, y+h), self.DARK2, -1)
        cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)
        cv2.rectangle(frame, (x, y), (x+w, y+h), self.TEAL_DIM, 1)

    def _progress_bar(self, frame, x, y, w, h, ratio, color_good, color_warn, color_bad):
        """Vẽ thanh tiến trình"""
        cv2.rectangle(frame, (x, y), (x+w, y+h), self.DARK, -1)
        ratio = max(0.0, min(1.0, ratio))
        fill_w = int(w * ratio)
        color = color_good if ratio < 0.6 else (color_warn if ratio < 0.85 else color_bad)
        if fill_w > 0:
            cv2.rectangle(frame, (x, y), (x+fill_w, y+h), color, -1)
        cv2.rectangle(frame, (x, y), (x+w, y+h), self.GRAY, 1)

    # ───────────────────────── Top-left info ───────────────────────
    def _draw_top_left(self, frame, session_data, body_data):
        """Panel góc trên trái: logo + trạng thái ngồi + thời gian phiên"""
        h, w = frame.shape[:2]
        px, py, pw, ph = 8, 8, 180, 78
        self._draw_panel(frame, px, py, pw, ph)

        # Logo
        cv2.putText(frame, "EyeGuard", (px+8, py+20), self.FONT,
                    self.FONT_MED, self.TEAL, 2, cv2.LINE_AA)

        # Trạng thái ngồi
        sitting = body_data.get("sitting", False)
        status_txt = "DANG NGOI" if sitting else "KHONG PHAT HIEN"
        status_col = self.GREEN   if sitting else self.YELLOW
        cv2.putText(frame, status_txt, (px+8, py+40), self.FONT,
                    self.FONT_TINY, status_col, 1, cv2.LINE_AA)

        # Thời gian phiên
        sess = session_data.get("session_duration", 0)
        sess_str = f"Phien: {int(sess//3600):02d}:{int((sess%3600)//60):02d}:{int(sess%60):02d}"
        cv2.putText(frame, sess_str, (px+8, py+58), self.FONT,
                    self.FONT_TINY, self.GRAY, 1, cv2.LINE_AA)

    # ───────────────────────── Bottom HUD ──────────────────────────
    def _draw_bottom_hud(self, frame, eye_data, posture_data, body_data, session_data):
        """Panel dưới cùng: các chỉ số quan trọng"""
        fh, fw = frame.shape[:2]
        bar_h = 100
        py = fh - bar_h

        # Nền
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, py), (fw, fh), self.DARK, -1)
        cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)
        cv2.line(frame, (0, py), (fw, py), self.TEAL_DIM, 1)

        col_w = fw // 5

        # ── Cột 1: Thời gian ngồi ───────────────────────────
        self._hud_column(frame, col_w * 0 + 10, py,
                         label="NGOI LIEN TUC",
                         value=self._fmt_time(session_data.get("sitting_duration", 0)),
                         color=self._sitting_color(session_data.get("sitting_duration", 0)))
        # Thanh tiến trình ngồi (so với mốc 45 phút)
        ratio = session_data.get("sitting_duration", 0) / max(
            self.config.get("sitting_warning_min", 45) * 60, 1
        )
        self._progress_bar(frame, col_w*0+10, py+68, col_w-20, 6,
                           ratio, self.GREEN, self.YELLOW, self.RED)

        # ── Cột 2: Chớp mắt ─────────────────────────────────
        blink_rate = eye_data.get("blink_rate", 0)
        b_color = self.GREEN if blink_rate >= 15 else (self.YELLOW if blink_rate >= 10 else self.RED)
        self._hud_column(frame, col_w * 1 + 10, py,
                         label="CHOP MAT/PHUT",
                         value=f"{blink_rate:.0f}",
                         color=b_color)
        # EAR indicator
        ear = eye_data.get("ear", 0.3)
        cv2.putText(frame, f"EAR {ear:.2f}", (col_w*1+10, py+75), self.FONT,
                    self.FONT_TINY, self.GRAY, 1, cv2.LINE_AA)

        # ── Cột 3: Mắt / Chớp ───────────────────────────────
        tsb = eye_data.get("time_since_blink", 0)
        tsb_col = self.GREEN if tsb < 30 else (self.YELLOW if tsb < 60 else self.RED)
        self._hud_column(frame, col_w * 2 + 10, py,
                         label="TU LAN CHOP CUOI",
                         value=f"{int(tsb)}s",
                         color=tsb_col)
        # Biểu tượng mắt
        is_blinking = eye_data.get("is_blinking", False)
        eye_sym = "- -" if is_blinking else "O O"
        cv2.putText(frame, eye_sym, (col_w*2+10, py+75), self.FONT,
                    self.FONT_SMALL, tsb_col, 1, cv2.LINE_AA)

        # ── Cột 4: Tư thế cơ thể ────────────────────────────
        is_bad_body   = body_data.get("is_bad_posture", False)
        spine_angle   = body_data.get("spine_angle", 0)
        body_color    = self.RED if is_bad_body else self.GREEN
        body_label    = "XAU" if is_bad_body else "TOT"
        self._hud_column(frame, col_w * 3 + 10, py,
                         label="TU THE CO THE",
                         value=body_label, color=body_color)
        cv2.putText(frame, f"Cot song: {spine_angle:.0f}deg", (col_w*3+10, py+75), self.FONT,
                    self.FONT_TINY, self.GRAY, 1, cv2.LINE_AA)

        # ── Cột 5: Cảnh báo tổng hợp ────────────────────────
        all_warnings = (eye_data.get("warnings", []) +
                        posture_data.get("warnings", []) +
                        body_data.get("warnings", []))
        w_count = len(all_warnings)
        w_color = self.GREEN if w_count == 0 else (self.YELLOW if w_count == 1 else self.RED)
        self._hud_column(frame, col_w * 4 + 10, py,
                         label="CANH BAO",
                         value=str(w_count), color=w_color)
        # Phần trăm thời gian tư thế tốt
        bad_pct = body_data.get("bad_posture_pct", 0)
        cv2.putText(frame, f"Tu the xau: {bad_pct:.0f}%", (col_w*4+10, py+75), self.FONT,
                    self.FONT_TINY, self.GRAY, 1, cv2.LINE_AA)

        # ── Dòng cảnh báo flash ──────────────────────────────
        issues = (posture_data.get("posture_issues", []) +
                  body_data.get("posture_issues", []))
        if issues:
            flash = abs(math.sin(time.time() * 3))
            r = int(73  + (248-73)*flash)
            g = int(81  + (81-81)*flash)
            b = int(248 + (73-248)*flash)
            txt = "! " + issues[0]
            cv2.putText(frame, txt, (10, fh - 4), self.FONT,
                        self.FONT_TINY, (b, g, r), 1, cv2.LINE_AA)
        elif "no_blink" in eye_data.get("warnings", []):
            flash = abs(math.sin(time.time() * 2))
            a = int(100 + 155 * flash)
            cv2.putText(frame, "! Hay chop mat!", (10, fh-4), self.FONT,
                        self.FONT_TINY, (80, a, 255), 1, cv2.LINE_AA)

    def _hud_column(self, frame, x, py, label, value, color):
        """Vẽ một cột trong HUD"""
        cv2.putText(frame, label, (x, py+16), self.FONT,
                    self.FONT_TINY, self.GRAY, 1, cv2.LINE_AA)
        cv2.putText(frame, value, (x, py+52), self.FONT,
                    self.FONT_LARGE, color, 2, cv2.LINE_AA)

    # ───────────────────────── Calibration ─────────────────────────
    def draw_calibration(self, frame, progress, total=40):
        fh, fw = frame.shape[:2]
        ratio = progress / total
        bar_w = int(fw * 0.6)
        bx = (fw - bar_w) // 2
        by = fh // 2 - 30

        overlay = frame.copy()
        cv2.rectangle(overlay, (bx-20, by-50), (bx+bar_w+20, by+50), self.DARK2, -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        cv2.putText(frame, "Khoi dong... Nhin thang, ngoi dung tu the",
                    (bx, by-10), self.FONT, self.FONT_SMALL, self.TEAL, 1, cv2.LINE_AA)

        cv2.rectangle(frame, (bx, by+5), (bx+bar_w, by+20), self.DARK, -1)
        fill = int(bar_w * ratio)
        if fill > 0:
            cv2.rectangle(frame, (bx, by+5), (bx+fill, by+20), self.TEAL, -1)
        cv2.rectangle(frame, (bx, by+5), (bx+bar_w, by+20), self.TEAL_DIM, 1)
        cv2.putText(frame, f"{int(ratio*100)}%", (bx+bar_w//2-15, by+18),
                    self.FONT, self.FONT_TINY, self.WHITE, 1, cv2.LINE_AA)

    def draw_no_face(self, frame):
        fh, fw = frame.shape[:2]
        flash = abs(math.sin(time.time() * 1.5))
        a = int(100 + 127 * flash)
        cv2.putText(frame, "Khong phat hien nguoi dung...",
                    (fw//2 - 160, fh//2), self.FONT, self.FONT_MED, (a, a, a), 1, cv2.LINE_AA)

    def draw_key_hints(self, frame):
        """Góc trên phải: hướng dẫn phím tắt"""
        fh, fw = frame.shape[:2]
        hints = [("Q", "Thoat"), ("S", "Stats"), ("R", "Reset"), ("C", "Cai dat")]
        for i, (k, v) in enumerate(hints):
            x = fw - 120
            y = 24 + i * 18
            cv2.putText(frame, f"[{k}] {v}", (x, y), self.FONT,
                        self.FONT_TINY, self.GRAY, 1, cv2.LINE_AA)

    # ───────────────────────── Main render ─────────────────────────
    def render(self, frame, eye_data, posture_data, body_data,
               session_data, pose_results,
               face_detected, is_face_calibrated, calib_frames=0):

        # Skeleton tư thế
        if pose_results is not None:
            warnings = body_data.get("warnings", [])
            self.draw_skeleton(frame, pose_results, body_data, warnings)

        # Không thấy mặt
        if not face_detected:
            self.draw_no_face(frame)
            self._draw_top_left(frame, session_data, body_data or {})
            self.draw_key_hints(frame)
            return frame

        # Calibration
        if not is_face_calibrated:
            self.draw_calibration(frame, calib_frames)
            self._draw_top_left(frame, session_data, body_data or {})
            return frame

        # HUD
        self._draw_top_left(frame, session_data, body_data or {})
        self._draw_bottom_hud(frame, eye_data or {}, posture_data or {}, body_data or {}, session_data or {})
        self.draw_key_hints(frame)

        return frame

    # ───────────────────────── Helpers ─────────────────────────────
    def _fmt_time(self, seconds):
        m = int(seconds // 60)
        s = int(seconds  %  60)
        return f"{m:02d}:{s:02d}"

    def _sitting_color(self, seconds):
        warn_s = self.config.get("sitting_warning_min", 45) * 60
        ratio  = seconds / max(warn_s, 1)
        if ratio < 0.6:
            return self.GREEN
        if ratio < 0.85:
            return self.YELLOW
        return self.RED