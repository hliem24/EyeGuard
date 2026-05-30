"""
Module theo dõi mắt:
- Tính EAR (Eye Aspect Ratio)
- Phát hiện chớp mắt
- Theo dõi tần suất chớp mắt
- Cảnh báo mỏi mắt
"""

import time
import numpy as np
from scipy.spatial import distance


class EyeTracker:

    def __init__(self, config):

        self.config = config

        # =================================================
        # CONFIG
        # =================================================
        self.blink_threshold = config.get(
            "blink_threshold",
            0.25
        )

        self.blink_warning_interval = config.get(
            "blink_warning_interval",
            60
        )

        self.min_blink_rate = config.get(
            "min_blink_rate",
            12
        )

        # =================================================
        # BLINK STATE
        # =================================================
        self.blink_count = 0

        self.total_blinks = 0

        self.last_blink_time = time.time()

        self.session_start = time.time()

        self.is_blinking = False

        # =================================================
        # EAR HISTORY
        # =================================================
        self.ear_history = []

        self.HISTORY_SIZE = 5

        # =================================================
        # STATS
        # =================================================
        self.last_minute_blinks = []

    # =====================================================
    # CALCULATE EAR
    # =====================================================
    def calculate_ear(self, eye_landmarks):

        """
        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        """

        if len(eye_landmarks) < 6:
            return 0.3

        p1, p2, p3, p4, p5, p6 = eye_landmarks[:6]

        # Vertical
        A = distance.euclidean(p2, p6)

        B = distance.euclidean(p3, p5)

        # Horizontal
        C = distance.euclidean(p1, p4)

        if C == 0:
            return 0.3

        ear = (A + B) / (2.0 * C)

        return ear

    # =====================================================
    # GET EYE LANDMARKS
    # =====================================================
    def get_eye_landmarks_from_mediapipe(
        self,
        face_landmarks,
        frame_shape
    ):

        h, w = frame_shape[:2]

        LEFT_EYE_IDX = [
            362, 385, 387,
            263, 373, 380
        ]

        RIGHT_EYE_IDX = [
            33, 160, 158,
            133, 153, 144
        ]

        def get_points(indices):

            pts = []

            for i in indices:

                x = int(
                    face_landmarks.landmark[i].x * w
                )

                y = int(
                    face_landmarks.landmark[i].y * h
                )

                pts.append((x, y))

            return pts

        left_eye = get_points(LEFT_EYE_IDX)

        right_eye = get_points(RIGHT_EYE_IDX)

        return left_eye, right_eye

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, face_landmarks, frame_shape):

        now = time.time()

        # =================================================
        # GET LANDMARKS
        # =================================================
        left_eye, right_eye = (
            self.get_eye_landmarks_from_mediapipe(
                face_landmarks,
                frame_shape
            )
        )

        # =================================================
        # EAR
        # =================================================
        left_ear = self.calculate_ear(left_eye)

        right_ear = self.calculate_ear(right_eye)

        avg_ear = (left_ear + right_ear) / 2.0

        # =================================================
        # SMOOTH EAR
        # =================================================
        self.ear_history.append(avg_ear)

        if len(self.ear_history) > self.HISTORY_SIZE:
            self.ear_history.pop(0)

        smooth_ear = np.mean(self.ear_history)

        # =================================================
        # BLINK DETECTION
        # =================================================
        blinked_now = False

        if smooth_ear < self.blink_threshold:

            if not self.is_blinking:
                self.is_blinking = True

        else:

            if self.is_blinking:

                self.is_blinking = False

                self.blink_count += 1

                self.total_blinks += 1

                self.last_blink_time = now

                self.last_minute_blinks.append(now)

                blinked_now = True

        # =================================================
        # CLEAN BLINK HISTORY
        # =================================================
        self.last_minute_blinks = [

            t for t in self.last_minute_blinks

            if now - t <= 60
        ]

        # =================================================
        # BLINK RATE
        # =================================================
        elapsed_min = (
            now - self.session_start
        ) / 60.0

        blink_rate = (
            self.total_blinks /
            max(elapsed_min, 1)
        )

        # =================================================
        # TIME SINCE BLINK
        # =================================================
        time_since_blink = (
            now - self.last_blink_time
        )

        # =================================================
        # WARNINGS
        # =================================================
        warnings = []

        # Không chớp mắt quá lâu
        if (
            time_since_blink >
            self.blink_warning_interval
        ):

            warnings.append("no_blink")

        # Tần suất chớp mắt thấp
        if (
            blink_rate < self.min_blink_rate
            and elapsed_min > 2
        ):

            warnings.append("low_blink_rate")

        # =================================================
        # RETURN
        # =================================================
        return {

            "ear": round(float(smooth_ear), 3),

            "left_ear": round(float(left_ear), 3),

            "right_ear": round(float(right_ear), 3),

            "is_blinking": self.is_blinking,

            "blinked": blinked_now,

            "blink_count": self.blink_count,

            "total_blinks": self.total_blinks,

            "blink_rate": round(blink_rate, 1),

            "time_since_blink": round(
                time_since_blink,
                1
            ),

            "warnings": warnings,

            "left_eye_pts": left_eye,

            "right_eye_pts": right_eye,
        }

    # =====================================================
    # RESET SESSION
    # =====================================================
    def reset_session(self):

        self.blink_count = 0

        self.total_blinks = 0

        self.last_blink_time = time.time()

        self.session_start = time.time()

        self.last_minute_blinks = []

        self.ear_history = []

        self.is_blinking = False