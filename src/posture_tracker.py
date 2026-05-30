"""
PostureTracker v2 – theo dõi tư thế đầu/mặt qua Face Mesh
===========================================================

FIX so với v1:
──────────────
1. face_too_close_ratio : 0.35 → 0.55  (v1 báo gần liên tục)
2. head_down_threshold  : 15   → 20    (nới rộng, camera laptop nhìn từ dưới)
3. head_tilt_threshold  : 20   → 22
4. KHÔNG cảnh báo trong 30 frame calibration đầu
5. Cảnh báo "too_close" dùng deviation so baseline (tránh false positive
   với người mặt to / ngồi gần màn hình tự nhiên)
6. posture_score 0-100 trả về để dashboard hiển thị (v1 không có)
"""

import math
import time
import numpy as np


class PostureTracker:

    CALIBRATION_FRAMES = 30
    HISTORY_SIZE       = 12   # smooth window (v1=10)

    def __init__(self, config):

        self.config = config

        # Ngưỡng
        self.head_tilt_threshold  = config.get("head_tilt_threshold",   22)   # (v1=20)
        self.head_down_threshold  = config.get("head_down_threshold",   20)   # (v1=15)
        self.face_close_ratio     = config.get("face_too_close_ratio",  0.55) # (v1=0.35)

        # Calibration
        self._calib_frames  = []
        self.is_calibrated  = False
        self.baseline_nose_y    = None
        self.baseline_face_size = None

        # Smooth
        self._history = []

        # Stats
        self._bad_start   = None
        self._total_bad_s = 0.0
        self._total_frames = 0
        self._bad_frames   = 0

    # ─────────────────────────────────────────────────────────────
    def calibrate(self, nose_y, face_size):
        self._calib_frames.append((nose_y, face_size))
        if len(self._calib_frames) >= self.CALIBRATION_FRAMES:
            self.baseline_nose_y    = float(np.mean([f[0] for f in self._calib_frames]))
            self.baseline_face_size = float(np.mean([f[1] for f in self._calib_frames]))
            self.is_calibrated = True
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    def calculate_head_tilt(self, face_landmarks, frame_shape):
        h, w = frame_shape[:2]
        lm   = face_landmarks.landmark
        left_eye  = (lm[33].x  * w, lm[33].y  * h)
        right_eye = (lm[263].x * w, lm[263].y * h)
        dy = right_eye[1] - left_eye[1]
        dx = right_eye[0] - left_eye[0]
        return math.degrees(math.atan2(dy, dx)) if dx != 0 else 0.0

    # ─────────────────────────────────────────────────────────────
    def calculate_head_pitch(self, face_landmarks, frame_shape):
        """
        Tỷ lệ vị trí mũi trong khuôn mặt (forehead→chin).
        > 0  = cúi xuống; < 0 = ngửa lên.
        FIX: nhân 80 thay vì 100 để giảm sensitivity.
        """
        h, w = frame_shape[:2]
        lm   = face_landmarks.landmark
        forehead = lm[10].y  * h
        nose     = lm[1].y   * h
        chin     = lm[152].y * h
        face_h   = chin - forehead
        if face_h == 0:
            return 0.0
        nose_ratio = (nose - forehead) / face_h
        return (nose_ratio - 0.5) * 80   # (v1 dùng *100)

    # ─────────────────────────────────────────────────────────────
    def get_face_size(self, face_landmarks, frame_shape):
        lm = face_landmarks.landmark
        xs = [l.x for l in lm]
        ys = [l.y for l in lm]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    # ─────────────────────────────────────────────────────────────
    def update(self, face_landmarks, frame_shape):

        now  = time.time()
        h, w = frame_shape[:2]
        lm   = face_landmarks.landmark

        tilt_angle  = self.calculate_head_tilt(face_landmarks, frame_shape)
        pitch_angle = self.calculate_head_pitch(face_landmarks, frame_shape)
        face_size   = self.get_face_size(face_landmarks, frame_shape)
        nose_y      = lm[1].y * h

        # Smooth
        self._history.append((tilt_angle, pitch_angle, face_size))
        if len(self._history) > self.HISTORY_SIZE:
            self._history.pop(0)

        tilt_angle  = float(np.mean([x[0] for x in self._history]))
        pitch_angle = float(np.mean([x[1] for x in self._history]))
        face_size   = float(np.mean([x[2] for x in self._history]))

        # Calibration
        if not self.is_calibrated:
            self.calibrate(nose_y, face_size)
            # Chưa xong calibration → không cảnh báo
            return self._build_result(
                tilt_angle, pitch_angle, face_size,
                [], [], False, 0.0, now
            )

        # Kiểm tra cảnh báo
        warnings       = []
        posture_issues = []
        self._total_frames += 1

        # a) Nghiêng đầu
        if abs(tilt_angle) > self.head_tilt_threshold:
            direction = "trái" if tilt_angle > 0 else "phải"
            warnings.append("head_tilt")
            posture_issues.append(f"Nghiêng đầu sang {direction}")

        # b) Cúi đầu
        if pitch_angle > self.head_down_threshold:
            warnings.append("head_down")
            posture_issues.append("Cúi đầu quá thấp")

        # c) Quá gần màn hình — dùng deviation so baseline
        #    Tránh false positive với người tự nhiên ngồi gần
        if self.baseline_face_size is not None:
            size_ratio = face_size / max(self.baseline_face_size, 0.001)
            # Nếu mặt to hơn baseline 40% → mới cảnh báo
            if size_ratio > 1.40 and face_size > self.face_close_ratio:
                warnings.append("too_close")
                posture_issues.append("Ngồi quá gần màn hình")

        is_bad = len(warnings) > 0

        if is_bad:
            self._bad_frames += 1
            if self._bad_start is None:
                self._bad_start = now
        else:
            if self._bad_start is not None:
                self._total_bad_s += now - self._bad_start
                self._bad_start    = None

        bad_dur = (now - self._bad_start) if self._bad_start else 0.0

        return self._build_result(
            tilt_angle, pitch_angle, face_size,
            warnings, posture_issues, is_bad, bad_dur, now
        )

    # ─────────────────────────────────────────────────────────────
    def _build_result(self, tilt, pitch, fsize,
                      warnings, issues, is_bad, bad_dur, now):

        bad_pct = (
            self._bad_frames / self._total_frames * 100
            if self._total_frames > 0 else 0.0
        )

        # posture_score 0-100 (100 = hoàn toàn tốt)
        penalty = len(warnings) * 20
        posture_score = max(0, 100 - penalty)

        return {
            "tilt_angle":           round(tilt,   1),
            "pitch_angle":          round(pitch,  1),
            "face_size":            round(fsize,  3),
            "posture_score":        posture_score,
            "is_bad_posture":       is_bad,
            "bad_posture_duration": round(bad_dur, 1),
            "bad_posture_pct":      round(bad_pct, 1),
            "total_bad_posture_time": round(self._total_bad_s, 1),
            "posture_issues":       issues,
            "warnings":             warnings,
            "is_calibrated":        self.is_calibrated,
        }