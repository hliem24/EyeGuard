"""
SittingDetector v4 – nhận diện ngồi/đứng chính xác hơn
=========================================================

CẢI TIẾN SO VỚI v3:
─────────────────────
1. **Calibration-first**: 40 frame đầu học baseline (shoulder_y, sh_width,
   nose_to_sh) của người dùng cụ thể → không dùng threshold cứng.

2. **4 signal rõ ràng hơn**:
   - S1  face_continuity  : frame liên tiếp có mặt (bỏ weight quá cao)
   - S2  shoulder_height  : vai thấp trong frame → ngồi
   - S3  shoulder_width   : vai hẹp hơn → đứng xa; rộng hơn → ngồi gần
   - S4  nose_shoulder_gap: khoảng cách Y(mũi→vai) tương đối
                            Đứng = lớn hơn baseline; Ngồi = gần baseline

3. **Adaptive thresholds**: sau calibration dùng z-score so với baseline
   thay vì giá trị tuyệt đối.

4. **State machine chắc hơn**:
   - Yêu cầu N frame liên tiếp trước khi đổi sitting↔standing
   - Không còn "kẹt unknown"

5. **Debug payload** đầy đủ hơn để dễ tune.
"""

import time
import collections
import numpy as np


class SittingDetector:

    # ── Pose landmark indices ─────────────────────────────────────
    NOSE           = 0
    LEFT_SHOULDER  = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP       = 23
    RIGHT_HIP      = 24

    # ── Tunable constants ────────────────────────────────────────
    FACE_AWAY_TIMEOUT   = 5.0    # giây không thấy mặt → "away"
    CALIB_FRAMES        = 50     # frame thu thập baseline
    SMOOTH_WINDOW       = 20     # frame làm mượt confidence cuối
    COMMIT_FRAMES       = 10     # frame liên tiếp cùng state mới → confirm (giảm từ 12)
    MOVEMENT_WINDOW     = 60     # giây buffer micro-movement
    STABILITY_WINDOW    = 5      # giây tính độ ổn định đầu
    MIN_BREAK_RESET     = 120    # giây nghỉ tối thiểu để reset debt
    BREAK_CREDIT_RATIO  = 0.5

    # Ngưỡng z-score
    Z_STANDING_THRESHOLD = 1.8

    # Fallback khi chưa calibrate (tuyệt đối)
    # Nới rộng để hoạt động tốt với camera gần
    FALLBACK_SH_Y_SIT   = 0.35   # vai dưới 35% frame → ngồi (v4=0.42, quá cao)
    FALLBACK_NOSE_Y_SIT = 0.18

    # ─────────────────────────────────────────────────────────────
    def __init__(self, config: dict):

        self.cfg = config
        self.sitting_warn_sec = config.get("sitting_warning_time", 45 * 60)

        # Timers
        self._session_start  = time.time()
        self._sitting_start  = None
        self._away_start     = None
        self._break_start    = None
        self._last_face_seen = time.time()

        # Accumulators
        self.total_sitting_sec = 0.0
        self.total_away_sec    = 0.0
        self.break_count       = 0
        self.break_debt_sec    = 0.0

        # State machine
        self._state      = "unknown"
        self._prev_state = "unknown"

        # Commit buffer: (candidate_state, count)
        self._commit_candidate = "unknown"
        self._commit_count     = 0

        # Frame counters
        self._face_frames    = 0
        self._no_face_frames = 0

        # Signal buffers
        self._conf_buf     = collections.deque(maxlen=self.SMOOTH_WINDOW)
        self._head_buf     = collections.deque(
            maxlen=int(self.STABILITY_WINDOW * 30))
        self._movement_buf = collections.deque(
            maxlen=int(self.MOVEMENT_WINDOW * 30))

        # Calibration buffers (thu thập giá trị baseline khi ngồi)
        self._calib_sh_y      = []   # shoulder_y khi calibrate
        self._calib_sh_width  = []   # shoulder width
        self._calib_n2s       = []   # nose-to-shoulder Y dist
        self._calib_nose_y    = []   # nose_y
        self._calib_face_size = []   # face bbox size (signal chính cho camera gần)
        self._calib_frames    = 0
        self._calibrated      = False

        # Baseline stats (mean, std)
        self._bl = {}   # {"sh_y": (mean,std), "sh_w":..., "n2s":..., "face_size":...}

        # Notification flags
        self._warned_sit  = False
        self._warned_move = False
        self._last_pose_debug = {}

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════

    def update(self, face_detected: bool, pose_results, frame_shape: tuple) -> dict:

        now = time.time()

        if face_detected:
            self._last_face_seen  = now
            self._face_frames    += 1
            self._no_face_frames  = 0
        else:
            self._face_frames     = 0
            self._no_face_frames += 1

        conf = self._compute_confidence(face_detected, pose_results, frame_shape, now)
        self._conf_buf.append(conf)
        smooth_conf = float(np.mean(self._conf_buf)) if self._conf_buf else 0.0

        raw_state = self._decide_raw(face_detected, smooth_conf, now)
        confirmed = self._commit(raw_state)

        self._transition(confirmed, now)
        self._update_debt(now)

        return self._build_result(smooth_conf, now)

    # ─────────────────────────────────────────────────────────────
    def mark_break(self):
        now = time.time()
        if self._sitting_start:
            self.total_sitting_sec += now - self._sitting_start
        self._sitting_start = None
        self._break_start   = now
        self._state         = "standing"
        self._warned_sit    = False
        self._warned_move   = False
        self.break_count   += 1
        self.break_debt_sec = 0.0

    # ─────────────────────────────────────────────────────────────
    def check_warnings(self) -> list:
        if self._state != "sitting":
            return []
        warns = []
        sit_s = self.get_sitting_duration()
        if sit_s >= self.sitting_warn_sec and not self._warned_sit:
            warns.append({
                "type": "sitting_too_long",
                "severity": "high",
                "sitting_min": int(sit_s // 60),
            })
            self._warned_sit = True
        no_move_thresh = self.cfg.get("no_movement_warn_min", 25) * 60
        if (self._movement_score() < 0.008
                and sit_s > no_move_thresh
                and not self._warned_move):
            warns.append({"type": "no_movement", "severity": "medium"})
            self._warned_move = True
        return warns

    # ── Getters ───────────────────────────────────────────────────
    def get_sitting_duration(self) -> float:
        if self._state == "sitting" and self._sitting_start:
            return time.time() - self._sitting_start
        return 0.0

    def get_session_duration(self) -> float:
        return time.time() - self._session_start

    def get_state(self) -> str:
        return self._state

    def get_stats(self) -> dict:
        sit = self.get_sitting_duration()
        return {
            "session_duration":  round(self.get_session_duration()),
            "sitting_duration":  round(sit),
            "total_sitting_sec": round(self.total_sitting_sec + sit),
            "total_away_sec":    round(self.total_away_sec),
            "break_count":       self.break_count,
            "break_debt_sec":    round(self.break_debt_sec),
            "movement_score":    round(self._movement_score(), 5),
            "state":             self._state,
            "calibrated":        self._calibrated,
            "calib_frames":      self._calib_frames,
        }

    # ═══════════════════════════════════════════════════════════════
    # PRIVATE – CONFIDENCE
    # ═══════════════════════════════════════════════════════════════

    def _compute_confidence(self, face_det, pose_res, frame_shape, now) -> float:
        """
        Confidence 1.0 = chắc chắn đang ngồi, 0.0 = chắc chắn đứng/đi.

        Signal mới: S_face_size – khi ngồi gần camera laptop, mặt chiếm
        tỷ lệ lớn hơn trong frame so với khi đứng xa. Đây là signal ổn định
        nhất cho setup camera gần, không bị ảnh hưởng bởi góc camera.
        """

        face_score = min(1.0, self._face_frames / 25.0)

        if not face_det:
            self._head_buf.append((now, 0.5))
            return face_score * 0.3

        # ── Face size signal (dùng được kể cả khi không có pose) ──
        s_face = self._face_size_signal(pose_res, frame_shape, now)

        # Không có pose → chỉ dùng face signal
        if pose_res is None or not pose_res.pose_landmarks:
            self._head_buf.append((now, 0.5))
            # face_size đủ mạnh để quyết định một mình
            return float(np.clip(0.3 * face_score + 0.7 * s_face, 0.0, 1.0))

        lm   = pose_res.pose_landmarks.landmark
        h, w = frame_shape[:2]

        s2, s3, s4, s5 = self._analyze_pose(lm, w, h, now)

        # Trọng số:
        #   face_continuity(1) + face_size(4) + sh_height(2)
        #   + sh_width(1) + n2s(2) + stability(1)
        # face_size tăng lên 4 vì là signal đáng tin nhất khi camera gần
        weights = [1.0, 4.0, 2.0, 1.0, 2.0, 1.0]
        scores  = [face_score, s_face, s2, s3, s4, s5]

        conf = sum(s * wt for s, wt in zip(scores, weights)) / sum(weights)
        return float(np.clip(conf, 0.0, 1.0))

    # ─────────────────────────────────────────────────────────────
    def _face_size_signal(self, pose_res, frame_shape, now) -> float:
        """
        Tính tỷ lệ diện tích mặt / frame.
        Ngồi gần camera → mặt to → signal cao (ngồi).
        Đứng xa camera  → mặt nhỏ → signal thấp (đứng).

        Dùng khoảng cách vai để ước tính nếu có pose,
        fallback sang nose_y nếu không có.
        """
        h, w = frame_shape[:2]

        if pose_res and pose_res.pose_landmarks:
            lm     = pose_res.pose_landmarks.landmark
            sh_vis = (getattr(lm[self.LEFT_SHOULDER],  'visibility', 0.5)
                    + getattr(lm[self.RIGHT_SHOULDER], 'visibility', 0.5)) / 2

            if sh_vis > 0.35:
                # Dùng shoulder width pixel làm proxy khoảng cách người-camera
                sh_px = abs(lm[self.LEFT_SHOULDER].x - lm[self.RIGHT_SHOULDER].x) * w
                # sh_px lớn = người gần camera = đang ngồi
                # Baseline thực nghiệm: ngồi laptop ~120-250px, đứng xa ~60-120px
                face_size_proxy = sh_px / w   # normalize 0-1

                if self._calibrated and "face_size" in self._bl:
                    m, s = self._bl["face_size"]
                    z    = (face_size_proxy - m) / s
                    score = self._sigmoid(z, self.Z_STANDING_THRESHOLD)
                else:
                    # Fallback: sh_w > 0.28 → ngồi gần
                    if face_size_proxy > 0.35:   score = 0.85
                    elif face_size_proxy > 0.25: score = 0.65
                    elif face_size_proxy > 0.18: score = 0.45
                    else:                         score = 0.20

                # Đưa vào calib buffer
                if not self._calibrated:
                    self._calib_face_size.append(face_size_proxy)

                self._last_pose_debug["face_size_proxy"] = round(face_size_proxy, 3)
                return score

        # Fallback: nose_y – khi ngồi gần, mũi thường ở giữa-dưới frame
        nose_y = pose_res.pose_landmarks.landmark[self.NOSE].y \
                 if (pose_res and pose_res.pose_landmarks) else 0.5
        if nose_y > 0.35:   return 0.75
        if nose_y > 0.22:   return 0.55
        return 0.30

    # ─────────────────────────────────────────────────────────────
    def _analyze_pose(self, lm, w, h, now):
        """
        Trả về (s_shoulder_height, s_shoulder_width, s_nose_to_sh, s_stability).

        Mỗi signal: 1.0 = chắc ngồi, 0.0 = chắc đứng.
        """

        def vis(i):
            return getattr(lm[i], 'visibility', 0.5)

        sh_vis = (vis(self.LEFT_SHOULDER) + vis(self.RIGHT_SHOULDER)) / 2
        nose_y  = lm[self.NOSE].y
        sh_y    = (lm[self.LEFT_SHOULDER].y + lm[self.RIGHT_SHOULDER].y) / 2
        sh_x_l  = lm[self.LEFT_SHOULDER].x
        sh_x_r  = lm[self.RIGHT_SHOULDER].x
        sh_w    = abs(sh_x_r - sh_x_l)
        n2s     = abs(sh_y - nose_y)   # khoảng cách mũi→vai theo Y

        # Cập nhật buffer cho movement
        self._head_buf.append((now, nose_y))
        self._movement_buf.append((now, sh_y, nose_y))

        # ── Calibration (50 frame đầu) ────────────────────────────
        if not self._calibrated:
            if sh_vis > 0.4:
                self._calib_sh_y.append(sh_y)
                self._calib_sh_width.append(sh_w)
                self._calib_n2s.append(n2s)
                self._calib_nose_y.append(nose_y)
                self._calib_frames += 1

            if self._calib_frames >= self.CALIB_FRAMES:
                self._finish_calibration()

            # Fallback trong lúc chưa calibrate
            return self._fallback_signals(sh_y, sh_w, n2s, nose_y, sh_vis)

        # ── Sau calibration: dùng z-score ────────────────────────
        return self._calibrated_signals(sh_y, sh_w, n2s, nose_y, sh_vis)

    # ─────────────────────────────────────────────────────────────
    def _finish_calibration(self):
        """Tính baseline mean/std từ dữ liệu thu thập."""

        def stats(arr):
            a   = np.array(arr)
            std = float(np.std(a))
            return float(np.mean(a)), max(std, 0.01)   # tránh chia 0

        self._bl = {
            "sh_y":   stats(self._calib_sh_y),
            "sh_w":   stats(self._calib_sh_width),
            "n2s":    stats(self._calib_n2s),
            "nose_y": stats(self._calib_nose_y),
        }

        if self._calib_face_size:
            self._bl["face_size"] = stats(self._calib_face_size)

        self._calibrated = True

    # ─────────────────────────────────────────────────────────────
    def _calibrated_signals(self, sh_y, sh_w, n2s, nose_y, sh_vis):
        """
        So sánh với baseline bằng z-score.

        Đứng → vai cao hơn (sh_y nhỏ hơn baseline)
             → vai hẹp hơn (sh_w nhỏ hơn baseline)
             → mũi→vai xa hơn (n2s lớn hơn baseline)
             → mũi cao hơn (nose_y nhỏ hơn baseline)

        z > +Z_STANDING_THRESHOLD = lệch nhiều = đang đứng → score thấp
        """

        Z = self.Z_STANDING_THRESHOLD

        def z_score(val, key):
            m, s = self._bl[key]
            return (val - m) / s

        # S2: shoulder height
        # Đứng → sh_y giảm (âm z) → đứng
        z_sh_y = z_score(sh_y, "sh_y")
        # sh_y giảm nhiều → confidence giảm
        s2 = self._sigmoid(-z_sh_y, Z)

        # S3: shoulder width
        # Đứng → sh_w giảm (âm z) → đứng
        z_sh_w = z_score(sh_w, "sh_w")
        s3 = self._sigmoid(z_sh_w, Z)   # rộng hơn baseline → ngồi

        # S4: nose-to-shoulder distance
        # Đứng → n2s tăng (dương z) → đứng
        z_n2s = z_score(n2s, "n2s")
        s4 = self._sigmoid(-z_n2s, Z)

        # Visibility penalty
        if sh_vis < 0.5:
            s2 *= sh_vis / 0.5
            s3 *= sh_vis / 0.5
            s4 *= sh_vis / 0.5

        self._last_pose_debug = {
            "sh_y":    round(sh_y, 3),
            "nose_y":  round(nose_y, 3),
            "sh_w":    round(sh_w, 3),
            "n2s":     round(n2s, 3),
            "z_sh_y":  round(z_sh_y, 2),
            "z_sh_w":  round(z_sh_w, 2),
            "z_n2s":   round(z_n2s, 2),
            "s2":      round(s2, 2),
            "s3":      round(s3, 2),
            "s4":      round(s4, 2),
            "calibrated": True,
        }

        return s2, s3, s4, self._head_stability_score()

    # ─────────────────────────────────────────────────────────────
    def _fallback_signals(self, sh_y, sh_w, n2s, nose_y, sh_vis):
        """Threshold tuyệt đối khi chưa calibrate."""

        # S2: shoulder height
        # Ngồi trước laptop: vai thường ở 0.40–0.80 của frame
        if sh_y > self.FALLBACK_SH_Y_SIT:
            s2 = 0.75
        elif sh_y > 0.30:
            s2 = 0.40
        else:
            s2 = 0.15

        # S3: shoulder width
        # Ngồi gần camera: sh_w thường 0.35-0.60
        if sh_w > 0.35:
            s3 = 0.75
        elif sh_w > 0.25:
            s3 = 0.50
        else:
            s3 = 0.20

        # S4: nose-to-shoulder
        # Ngồi: n2s thường 0.10-0.30
        if n2s < 0.30:
            s4 = 0.80
        elif n2s < 0.40:
            s4 = 0.50
        else:
            s4 = 0.15

        if sh_vis < 0.5:
            s2 *= sh_vis / 0.5
            s3 *= sh_vis / 0.5
            s4 *= sh_vis / 0.5

        self._last_pose_debug = {
            "sh_y":   round(sh_y, 3),
            "nose_y": round(nose_y, 3),
            "sh_w":   round(sh_w, 3),
            "n2s":    round(n2s, 3),
            "s2": round(s2, 2),
            "s3": round(s3, 2),
            "s4": round(s4, 2),
            "calibrated": False,
        }

        return s2, s3, s4, self._head_stability_score()

    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _sigmoid(z, threshold):
        """
        Chuyển z-score thành score 0-1.
        z = 0   → 0.5 (neutral)
        z >> +threshold → gần 1.0  (chắc ngồi)
        z << -threshold → gần 0.0  (chắc đứng)
        """
        import math
        steepness = 2.5 / max(threshold, 0.1)
        return 1.0 / (1.0 + math.exp(-steepness * z))

    # ─────────────────────────────────────────────────────────────
    def _head_stability_score(self) -> float:

        if len(self._head_buf) < 5:
            return 0.6

        now    = time.time()
        recent = [ny for (t, ny) in self._head_buf if now - t <= self.STABILITY_WINDOW]

        if len(recent) < 3:
            return 0.6

        std = float(np.std(recent))

        if std < 0.010:  return 1.00
        if std < 0.020:  return 0.85
        if std < 0.035:  return 0.65
        if std < 0.055:  return 0.40
        return 0.15

    # ─────────────────────────────────────────────────────────────
    def _movement_score(self) -> float:

        if len(self._movement_buf) < 5:
            return 0.01

        now    = time.time()
        recent = [a for (t, a, b) in self._movement_buf
                  if now - t <= self.MOVEMENT_WINDOW]

        if len(recent) < 3:
            return 0.01

        return float(np.std(recent))

    # ═══════════════════════════════════════════════════════════════
    # PRIVATE – STATE MACHINE
    # ═══════════════════════════════════════════════════════════════

    def _decide_raw(self, face_det, conf, now) -> str:
        """Quyết định state thô từ confidence (chưa commit)."""

        gap = now - self._last_face_seen

        if gap > self.FACE_AWAY_TIMEOUT:
            return "away"

        if self._face_frames < 3:
            return self._state if self._state != "away" else "unknown"

        if conf >= 0.58:
            return "sitting"

        if conf <= 0.38:
            return "standing"

        # Vùng giữa [0.38, 0.58]: hysteresis
        if self._state in ("sitting", "standing"):
            return self._state

        return "unknown"

    # ─────────────────────────────────────────────────────────────
    def _commit(self, candidate: str) -> str:
        """
        Chỉ đổi state khi cùng candidate xuất hiện COMMIT_FRAMES liên tiếp.
        Tránh giật/nhấp nháy.
        """

        if candidate == self._commit_candidate:
            self._commit_count += 1
        else:
            self._commit_candidate = candidate
            self._commit_count     = 1

        # Đủ frame → confirm đổi state
        if self._commit_count >= self.COMMIT_FRAMES:
            return candidate

        # Chưa đủ → giữ state hiện tại
        return self._state

    # ─────────────────────────────────────────────────────────────
    def _transition(self, new_state: str, now: float):

        old = self._state
        if new_state == old:
            return

        if old == "sitting" and self._sitting_start:
            self.total_sitting_sec += now - self._sitting_start
            self._sitting_start     = None

        if old == "away" and self._away_start:
            away_dur             = now - self._away_start
            self.total_away_sec += away_dur
            self._away_start     = None
            if away_dur >= self.MIN_BREAK_RESET:
                self._warned_sit    = False
                self._warned_move   = False
                self.break_count   += 1
                self.break_debt_sec = 0.0

        if new_state == "sitting":
            self._sitting_start = now
            self._break_start   = None

        if new_state == "away":
            self._away_start  = now
            self._break_start = now

        if new_state == "standing":
            self._break_start = now

        self._prev_state = old
        self._state      = new_state

    # ─────────────────────────────────────────────────────────────
    def _update_debt(self, now: float):

        if self._state == "sitting":
            excess = max(0.0, self.get_sitting_duration() - self.sitting_warn_sec)
            self.break_debt_sec = excess

        elif self._state in ("away", "standing") and self._break_start:
            dt = (now - self._break_start) * self.BREAK_CREDIT_RATIO
            self.break_debt_sec = max(0.0, self.break_debt_sec - dt * 0.0167)

    # ═══════════════════════════════════════════════════════════════
    # RESULT BUILDER
    # ═══════════════════════════════════════════════════════════════

    def _build_result(self, conf: float, now: float) -> dict:

        sit_s    = self.get_sitting_duration()
        warn_s   = self.sitting_warn_sec
        progress = min(1.0, sit_s / warn_s) if warn_s > 0 else 0.0

        state_color = {
            "sitting":  "#00d4aa",
            "standing": "#58a6ff",
            "away":     "#8b949e",
            "unknown":  "#484f58",
        }.get(self._state, "#484f58")

        return {
            "state":            self._state,
            "state_color":      state_color,
            "confidence":       round(conf, 3),
            "sitting_duration": round(sit_s),
            "sitting_progress": round(progress, 3),
            "break_debt_sec":   round(self.break_debt_sec),
            "calibrated":       self._calibrated,
            "calib_progress":   min(self._calib_frames, self.CALIB_FRAMES),
            "movement_score":   round(self._movement_score(), 5),
            "pose_debug":       self._last_pose_debug,
            "stats":            self.get_stats(),
        }