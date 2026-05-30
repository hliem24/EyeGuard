"""
Cấu hình mặc định cho EyeGuard
"""

DEFAULT_SETTINGS = {

    # =====================================================
    # THỜI GIAN NGHỈ
    # =====================================================
    "sitting_warning_time": 45 * 60,      # 45 phút
    "eye_strain_time": 20 * 60,           # 20 phút
    "break_reminder_interval": 20,        # Quy tắc 20-20-20

    # =====================================================
    # CHỚP MẮT
    # =====================================================
    "blink_threshold": 0.25,
    "blink_ear_threshold": 0.25,
    "blink_warning_interval": 60,
    "min_blink_rate": 12,

    # =====================================================
    # TƯ THẾ
    # =====================================================
    "head_tilt_threshold": 20,
    "head_down_threshold": 15,

    # THÊM MỚI ĐỂ KHÔNG BỊ KEYERROR
    "shoulder_tilt_threshold": 10,
    "bad_posture_warn_sec": 120,

    "face_too_close_ratio": 0.35,

    # =====================================================
    # CAMERA
    # =====================================================
    "camera_index": 0,
    "camera_fps": 30,
    "frame_width": 640,
    "frame_height": 480,

    # =====================================================
    # HIỂN THỊ
    # =====================================================
    "show_camera_window": True,
    "show_landmarks": False,
    "show_stats_overlay": True,

    # =====================================================
    # THÔNG BÁO
    # =====================================================
    "enable_sound": True,
    "enable_popup": True,

    # cooldown giữa các thông báo
    "notification_cooldown": 300,

    # =====================================================
    # SESSION / MOVEMENT
    # =====================================================
    "no_movement_warning_time": 600,
    "movement_threshold": 0.02,

    # =====================================================
    # BODY TRACKING
    # =====================================================
    "enable_body_tracking": True,
    "enable_posture_detection": True,

    # =====================================================
    # LOGGING
    # =====================================================
    "log_level": "INFO",
    "log_to_file": True,
    "log_file": "logs/eyeguard.log",
}


# Alias để tương thích code cũ
CONFIG = DEFAULT_SETTINGS