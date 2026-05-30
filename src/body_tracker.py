"""
BodyTracker v2 – phân tích tư thế thân trên
=============================================

FIX so với v1:
──────────────
1. KHÔNG dùng HIP để tính spine_angle vì camera laptop không thấy hông
   → dùng EAR→SHOULDER thay thế (neck lean angle)

2. Threshold thực tế hơn:
   - shoulder_tilt    : 15° → 20° (ngồi bình thường lệch 5-10°)
   - ear_forward      : 0.12 → 0.18 (threshold cũ quá nhạy)
   - neck_lean        : thay spine_angle, threshold 25°

3. Visibility gate: bỏ qua landmark có visibility < 0.5
   → không tính điểm ảo khi MediaPipe đoán mò

4. Calibration-aware: trong 40 frame đầu KHÔNG cảnh báo
   (đang học baseline, tránh false positive ngay khi mở app)

5. Smooth window tăng từ 8 → 15 frame
"""

import time
import math
import numpy as np


class BodyTracker:

    # Landmark indices
    NOSE           = 0
    LEFT_EAR       = 7
    RIGHT_EAR      = 8
    LEFT_SHOULDER  = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP       = 23
    RIGHT_HIP      = 24

    # Calibration
    CALIBRATION_N = 40
    HISTORY_N     = 15   # smooth window (tăng từ 8)

    def __init__(self, config):
        self.config = config

        # Ngưỡng cảnh báo (nới rộng so với v1)
        self.shoulder_tilt_thresh  = config.get("shoulder_lean_threshold",   20)   # độ (v1=15)
        self.neck_lean_thresh      = config.get("spine_angle_threshold",     25)   # độ (v1=20, dùng neck thay spine)
        self.ear_forward_thresh    = config.get("ear_forward_threshold",     0.18) # (v1=0.12)
        self.shoulder_imbal_thresh = config.get("shoulder_imbalance_thresh", 0.07) # (v1=0.06)

        # Calibration
        self._calib_data  = []
        self._calibrated  = False
        self._baseline    = {}   # {"shoulder_tilt": mean, "neck_lean": mean, ...}

        # History smooth
        self._history = []

        # Tracking thời gian tư thế xấu
        self._bad_start       = None
        self._total_bad_s     = 0.0
        self._frames_bad      = 0
        self._frames_total    = 0

    # ─────────────────────────────────────────────────────────────
    def update(self, pose_results, frame_shape):

        now  = time.time()
        h, w = frame_shape[:2]

        if pose_results is None or not pose_results.pose_landmarks:
            return self._empty_result()

        lm = pose_results.pose_landmarks.landmark

        # Helper lấy tọa độ pixel + visibility
        def xy(i):
            p = lm[i]
            return (p.x * w, p.y * h)

        def vis(i):
            return getattr(lm[i], 'visibility', 0.5)

        # Visibility check vai (bắt buộc phải thấy)
        sh_vis = (vis(self.LEFT_SHOULDER) + vis(self.RIGHT_SHOULDER)) / 2
        if sh_vis < 0.45:
            return self._empty_result()

        ls  = xy(self.LEFT_SHOULDER)
        rs  = xy(self.RIGHT_SHOULDER)
        sh_mid = ((ls[0]+rs[0])/2, (ls[1]+rs[1])/2)
        sh_w   = abs(ls[0] - rs[0])

        # Tai (dùng để tính neck lean)
        ear_vis = (vis(self.LEFT_EAR) + vis(self.RIGHT_EAR)) / 2
        if ear_vis > 0.4:
            le = xy(self.LEFT_EAR)
            re = xy(self.RIGHT_EAR)
            ear_mid = ((le[0]+re[0])/2, (le[1]+re[1])/2)
        else:
            # Fallback: dùng nose
            nose = xy(self.NOSE)
            ear_mid = nose

        # ── 1. Shoulder tilt (độ nghiêng vai) ────────────────────
        # Góc đường nối 2 vai so với ngang
        sh_dy = rs[1] - ls[1]
        sh_dx = rs[0] - ls[0]
        shoulder_tilt = math.degrees(math.atan2(sh_dy, sh_dx)) if sh_dx != 0 else 0.0

        # ── 2. Neck lean (tai lệch so với vai) ───────────────────
        # Thay thế spine_angle vì không thấy hông
        # Tính góc vector (shoulder_mid → ear_mid) so với đường thẳng đứng
        neck_dx = ear_mid[0] - sh_mid[0]
        neck_dy = sh_mid[1]  - ear_mid[1]   # dương = tai cao hơn vai (bình thường)
        neck_lean = math.degrees(math.atan2(abs(neck_dx), max(neck_dy, 1)))
        # neck_lean nhỏ = đầu thẳng; lớn = đầu đổ về trước/sau

        # ── 3. Ear forward (đầu thò ra phía trước) ───────────────
        ear_forward = (ear_mid[0] - sh_mid[0]) / max(sh_w, 1)
        # Giá trị dương lớn = đầu thò ra (mirror camera)

        # ── 4. Shoulder imbalance (vai lệch độ cao) ───────────────
        shoulder_imbalance = abs(ls[1] - rs[1]) / h

        # ── 5. Head-shoulder distance (đầu gần vai = gù) ─────────
        head_sh_dist = (sh_mid[1] - ear_mid[1]) / h   # > 0 = bình thường

        raw = {
            "shoulder_tilt":      shoulder_tilt,
            "neck_lean":          neck_lean,
            "ear_forward":        ear_forward,
            "shoulder_imbalance": shoulder_imbalance,
            "head_sh_dist":       head_sh_dist,
            "sh_w_norm":          sh_w / w,
        }

        # ── Calibration (40 frame đầu) ────────────────────────────
        if not self._calibrated:
            self._calib_data.append(raw)
            if len(self._calib_data) >= self.CALIBRATION_N:
                self._finish_calibration()
            # Chưa calibrate → không cảnh báo
            return self._build_result(raw, [], [], False, 0.0, now)

        # ── Smooth ───────────────────────────────────────────────
        self._history.append(raw)
        if len(self._history) > self.HISTORY_N:
            self._history.pop(0)

        s = {k: float(np.mean([d[k] for d in self._history]))
             for k in raw}

        # ── Kiểm tra cảnh báo (dùng giá trị đã smooth) ───────────
        warnings      = []
        posture_issues = []
        self._frames_total += 1

        # a) Vai nghiêng
        # Dùng deviation so với baseline (tránh false positive khi ngồi lệch tự nhiên)
        tilt_dev = abs(s["shoulder_tilt"]) - abs(self._baseline.get("shoulder_tilt", 0))
        if abs(s["shoulder_tilt"]) > self.shoulder_tilt_thresh and tilt_dev > 5:
            direction = "trái" if s["shoulder_tilt"] > 0 else "phải"
            warnings.append("shoulder_tilt")
            posture_issues.append(f"Vai nghiêng sang {direction}")

        # b) Neck lean (cúi/đổ đầu về phía trước)
        neck_dev = s["neck_lean"] - self._baseline.get("neck_lean", 0)
        if neck_dev > self.neck_lean_thresh:
            warnings.append("neck_lean")
            posture_issues.append("Cổ/đầu đổ về phía trước")

        # c) Ear forward
        ear_dev = s["ear_forward"] - self._baseline.get("ear_forward", 0)
        if ear_dev > self.ear_forward_thresh:
            warnings.append("forward_head")
            posture_issues.append("Đầu thò ra phía trước")

        # d) Shoulder imbalance
        if s["shoulder_imbalance"] > self.shoulder_imbal_thresh:
            warnings.append("shoulder_imbalance")
            posture_issues.append("Vai không đều")

        is_bad = len(warnings) > 0

        if is_bad:
            self._frames_bad += 1
            if self._bad_start is None:
                self._bad_start = now
        else:
            if self._bad_start is not None:
                self._total_bad_s += now - self._bad_start
                self._bad_start    = None

        bad_dur = (now - self._bad_start) if self._bad_start else 0.0

        return self._build_result(s, warnings, posture_issues, is_bad, bad_dur, now)

    # ─────────────────────────────────────────────────────────────
    def _finish_calibration(self):
        """Tính baseline từ dữ liệu calibration."""
        for key in ("shoulder_tilt", "neck_lean", "ear_forward",
                    "shoulder_imbalance", "head_sh_dist"):
            vals = [d[key] for d in self._calib_data]
            self._baseline[key] = float(np.mean(vals))
        self._calibrated = True

    # ─────────────────────────────────────────────────────────────
    def _build_result(self, s, warnings, posture_issues, is_bad, bad_dur, now):

        bad_pct = (
            self._frames_bad / self._frames_total * 100
            if self._frames_total > 0 else 0.0
        )

        return {
            "shoulder_tilt":       round(s.get("shoulder_tilt", 0), 1),
            "neck_lean":           round(s.get("neck_lean",      0), 1),
            "ear_forward":         round(s.get("ear_forward",    0), 3),
            "shoulder_imbalance":  round(s.get("shoulder_imbalance", 0), 3),
            "head_sh_dist":        round(s.get("head_sh_dist",   0), 3),
            "warnings":            warnings,
            "posture_issues":      posture_issues,
            "is_bad_posture":      is_bad,
            "bad_posture_duration":round(bad_dur, 1),
            "bad_posture_pct":     round(bad_pct, 1),
            "is_calibrated":       self._calibrated,
            "calib_progress":      min(len(self._calib_data), self.CALIBRATION_N),
        }

    # ─────────────────────────────────────────────────────────────
    def _empty_result(self):
        return {
            "shoulder_tilt": 0, "neck_lean": 0, "ear_forward": 0,
            "shoulder_imbalance": 0, "head_sh_dist": 0,
            "warnings": [], "posture_issues": [],
            "is_bad_posture": False, "bad_posture_duration": 0,
            "bad_posture_pct": round(
                self._frames_bad / self._frames_total * 100
                if self._frames_total > 0 else 0, 1
            ),
            "is_calibrated":  self._calibrated,
            "calib_progress": min(len(self._calib_data), self.CALIBRATION_N),
        }