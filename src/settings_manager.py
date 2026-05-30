"""
Settings Manager
Quản lý đọc / ghi cài đặt JSON cho EyeGuard
"""

import json
import os


# =========================================================
# DEFAULT SETTINGS
# =========================================================
DEFAULT_SETTINGS = {

    # =====================================================
    # THỜI GIAN NHẮC NHỞ
    # =====================================================
    "sitting_warning_min": 0.5,      # 0.5 phut = 30 giay (de test)
    "eye_strain_min": 20,

    "no_blink_warning_sec": 60,

    "blink_warning_interval": 60,

    "bad_posture_warn_sec": 120,

    "no_movement_warn_min": 25,

    # =====================================================
    # EYE TRACKING
    # =====================================================
    "blink_ear_threshold": 0.25,

    "blink_threshold": 0.25,

    "min_blink_rate": 12,

    "face_too_close_ratio": 0.35,

    # =====================================================
    # HEAD / POSTURE
    # =====================================================
    "head_down_threshold": 15,

    "head_tilt_threshold": 20,

    "shoulder_lean_threshold": 15,

    "shoulder_tilt_threshold": 15,

    "spine_angle_threshold": 20,

    # =====================================================
    # CAMERA
    # =====================================================
    "camera_index": 0,

    "frame_width": 640,

    "frame_height": 480,

    "camera_fps": 30,

    # =====================================================
    # UI
    # =====================================================
    "show_camera_window": True,

    "show_landmarks": False,

    "show_body_skeleton": True,

    "show_stats_overlay": True,

    # =====================================================
    # NOTIFICATION
    # =====================================================
    "enable_sound": True,

    "enable_popup": True,

    "notification_cooldown": 300,

    "alarm_sound_type": "beep",

    "alarm_volume": 0.8,

    # =====================================================
    # LOGGING
    # =====================================================
    "log_level": "INFO",

    "log_to_file": True,

    "log_file": "logs/eyeguard.log",
}


# =========================================================
# ROOT DIRECTORY
# =========================================================
ROOT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

# =========================================================
# SETTINGS FILE
# =========================================================
SETTINGS_FILE = os.path.join(
    ROOT_DIR,
    "config",
    "user_settings.json"
)


# =========================================================
# SETTINGS MANAGER
# =========================================================
class SettingsManager:

    def __init__(self):

        self._data = dict(DEFAULT_SETTINGS)

        self.load()

    # =====================================================
    # GET
    # =====================================================
    def get(self, key, fallback=None):

        if key in self._data:

            return self._data[key]

        if fallback is not None:

            return fallback

        return DEFAULT_SETTINGS.get(key)

    # =====================================================
    # SET
    # =====================================================
    def set(self, key, value):

        self._data[key] = value

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, mapping: dict):

        self._data.update(mapping)

    # =====================================================
    # ALL SETTINGS
    # =====================================================
    def all(self) -> dict:

        return dict(self._data)

    # =====================================================
    # DERIVED TIMES (SECONDS)
    # =====================================================
    @property
    def sitting_warning_time(self) -> int:

        return int(
            self._data.get(
                "sitting_warning_min",
                0.5
            ) * 60
        )

    @property
    def eye_strain_time(self) -> int:

        return int(
            self._data.get(
                "eye_strain_min",
                20
            ) * 60
        )

    @property
    def no_movement_time(self) -> int:

        return int(
            self._data.get(
                "no_movement_warn_min",
                25
            ) * 60
        )

    # =====================================================
    # LOAD SETTINGS
    # =====================================================
    def load(self):

        if not os.path.exists(SETTINGS_FILE):

            return

        try:

            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                saved = json.load(f)

            if not isinstance(saved, dict):

                return

            # Merge với defaults
            for key, value in saved.items():

                self._data[key] = value

            print("[Settings] Da tai cai dat")

        except Exception as e:

            print(
                f"[Settings] Loi doc file: {e}"
            )

    # =====================================================
    # SAVE SETTINGS
    # =====================================================
    def save(self):

        try:

            os.makedirs(
                os.path.dirname(SETTINGS_FILE),
                exist_ok=True
            )

            with open(
                SETTINGS_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self._data,
                    f,
                    indent=4,
                    ensure_ascii=False
                )

            print("[Settings] Da luu cai dat")

        except Exception as e:

            print(
                f"[Settings] Loi luu file: {e}"
            )

    # =====================================================
    # RESET DEFAULT
    # =====================================================
    def reset_to_default(self):

        self._data = dict(DEFAULT_SETTINGS)

        self.save()

        print("[Settings] Reset mac dinh")