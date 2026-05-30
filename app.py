"""
EyeGuard App v3
- MediaPipe Face Mesh + Pose
- SittingDetector  (nhan dien ngoi thong minh – 5 tin hieu)
- DashboardWindow  (UI fullscreen Tkinter)
- SettingsManager / SettingsWindow
- BodyTracker, EyeTracker, PostureTracker
"""

import cv2
import time
import logging
import sys
import os
import threading
import queue

# =========================================================
# FIX IMPORT PATH
# =========================================================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# =========================================================
# IMPORT MODULES
# =========================================================
from src.eye_tracker          import EyeTracker
from src.posture_tracker      import PostureTracker
from src.session_tracker      import SessionTracker
from src.notification_manager import NotificationManager
from src.body_tracker         import BodyTracker
from src.settings_manager     import SettingsManager
from src.sitting_detector     import SittingDetector
from src.dashboard_ui         import DashboardWindow


# =========================================================
# LOGGING
# =========================================================
def setup_logging(cfg):

    os.makedirs("logs", exist_ok=True)

    handlers = [logging.StreamHandler(sys.stdout)]

    if cfg.get("log_to_file", True):
        handlers.append(
            logging.FileHandler(
                cfg.get("log_file", "logs/eyeguard.log"),
                encoding="utf-8"
            )
        )

    logging.basicConfig(
        level=getattr(logging, cfg.get("log_level", "INFO")),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers
    )


# =========================================================
# MAIN APP
# =========================================================
class EyeGuardApp:

    def __init__(self):

        self.settings = SettingsManager()

        setup_logging(self.settings.all())

        self.logger = logging.getLogger("EyeGuard")

        # Camera & MediaPipe
        self.cap       = None
        self.face_mesh = None
        self.pose      = None
        self.mp_fm     = None
        self.mp_pose   = None

        self.running = False

        # Tracking data
        self.eye_data     = {}
        self.posture_data = {}
        self.body_data    = {}
        self.sit_data     = {}

        self.pose_results = None
        self.calib_frames = 0

        self.last_eye_break_notify = time.time()

        # Queue giao tiep worker <-> UI
        self.q_data = queue.Queue(maxsize=4)
        self.q_cmd  = queue.Queue()

        # Cooldown thong bao (tranh spam)
        self._last_notify: dict = {}

        self._rebuild_modules()

    # =====================================================
    # BUILD MODULES
    # =====================================================
    def _rebuild_modules(self):

        cfg = self.settings.all()

        full = {
            **cfg,

            "sitting_warning_time":
                self.settings.sitting_warning_time,

            "eye_strain_time":
                self.settings.eye_strain_time,

            "blink_threshold":
                cfg.get("blink_ear_threshold", 0.25)
        }

        self.eye_tracker     = EyeTracker(full)
        self.posture_tracker = PostureTracker(full)
        self.session_tracker = SessionTracker(full)
        self.notifier        = NotificationManager(full)
        self.body_tracker    = BodyTracker(full)
        self.sitting_det     = SittingDetector(full)

        self._cfg = full

    # =====================================================
    # SETTINGS CALLBACK
    # =====================================================
    def _on_settings_saved(self, _):

        self.logger.info("Cap nhat cai dat...")

        self._rebuild_modules()

    # =====================================================
    # MEDIAPIPE
    # =====================================================
    def _init_mediapipe(self):

        try:
            import mediapipe as mp

            self.mp_fm   = mp.solutions.face_mesh
            self.mp_pose = mp.solutions.pose

            self.face_mesh = self.mp_fm.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )

            self.pose = self.mp_pose.Pose(
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )

            self.logger.info("MediaPipe da khoi dong")

            return True

        except ImportError:

            self.logger.error(
                "Chua cai mediapipe. Chay: pip install mediapipe"
            )

            return False

    # =====================================================
    # CAMERA
    # =====================================================
    def _init_camera(self):

        idx = self.settings.get("camera_index", 0)

        self.cap = cv2.VideoCapture(idx)

        if not self.cap.isOpened():

            self.logger.error(f"Khong mo duoc camera {idx}")

            return False

        self.cap.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.settings.get("frame_width", 640)
        )

        self.cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.settings.get("frame_height", 480)
        )

        self.cap.set(
            cv2.CAP_PROP_FPS,
            self.settings.get("camera_fps", 30)
        )

        self.logger.info(f"Camera {idx} mo thanh cong")

        return True

    # =====================================================
    # PROCESS FRAME
    # =====================================================
    def _process_frame(self, frame):

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        rgb.flags.writeable = False

        face_results = self.face_mesh.process(rgb)
        pose_results = self.pose.process(rgb)

        rgb.flags.writeable = True

        face_detected = (
            face_results.multi_face_landmarks is not None
            and len(face_results.multi_face_landmarks) > 0
        )

        # SittingDetector – cap nhat moi frame (quan trong nhat)
        self.sit_data = self.sitting_det.update(
            face_detected,
            pose_results,
            frame.shape
        )

        # Session tracker bo sung (presence + movement)
        self.session_tracker.update_presence(face_detected)

        self.pose_results = pose_results

        # ================================================
        # KHONG THAY MAT
        # ================================================
        if not face_detected:

            self.eye_data     = {}
            self.posture_data = {}

            self.body_data = self.body_tracker.update(
                pose_results,
                frame.shape
            )

            return frame, False

        # ================================================
        # FACE LANDMARK
        # ================================================
        face_lm = face_results.multi_face_landmarks[0]

        self.eye_data = self.eye_tracker.update(
            face_lm,
            frame.shape
        )

        self.posture_data = self.posture_tracker.update(
            face_lm,
            frame.shape
        )

        self.body_data = self.body_tracker.update(
            pose_results,
            frame.shape
        )

        self.calib_frames = len(
            self.posture_tracker.calibration_frames
        )

        self.session_tracker.update_movement(
            face_lm,
            frame.shape
        )

        self._check_and_notify()

        return frame, True

    # =====================================================
    # NOTIFICATION
    # =====================================================
    def _check_and_notify(self):

        now = time.time()
        cfg = self._cfg
        cd  = cfg.get("notification_cooldown", 300)

        def _can(k):  return now - self._last_notify.get(k, 0) > cd
        def _mark(k): self._last_notify[k] = now

        # ── 1. Sitting warnings (tu SittingDetector) ─────────────
        for warn in self.sitting_det.check_warnings():

            if warn["type"] == "sitting_too_long" and _can("sit"):

                self.notifier.notify_sitting_too_long(
                    int(self.sitting_det.get_sitting_duration() // 60)
                )

                _mark("sit")

            elif warn["type"] == "no_movement" and _can("move"):

                self.notifier.notify_no_movement()

                _mark("move")

        # ── 2. Blink warning ─────────────────────────────────────
        if (
            "no_blink" in self.eye_data.get("warnings", [])
            and _can("blink")
        ):

            self.notifier.notify_no_blink()

            _mark("blink")

        # ── 3. Eye strain (quy tac 20-20-20) ─────────────────────
        if (
            now - self.last_eye_break_notify
            > cfg.get("eye_strain_time", 1200)
        ):

            self.notifier.notify_eye_strain()

            self.last_eye_break_notify = now

        # ── 4. Bad posture keo dai ────────────────────────────────
        bad_sec = cfg.get("bad_posture_warn_sec", 120)

        for data in [self.posture_data, self.body_data]:

            if (
                data.get("is_bad_posture")
                and data.get("bad_posture_duration", 0) > bad_sec
                and data.get("posture_issues")
                and _can("posture")
            ):

                self.notifier.notify_bad_posture(
                    data["posture_issues"]
                )

                _mark("posture")

                break

    # =====================================================
    # SETTINGS WINDOW
    # =====================================================
    def _open_settings(self):

        from src.settings_ui import SettingsWindow

        def _run():

            win = SettingsWindow(
                self.settings,
                self._on_settings_saved
            )

            win.open()

            if win.window:
                win.window.wait_window()

        threading.Thread(
            target=_run,
            daemon=True
        ).start()

    # =====================================================
    # SKELETON + HUD MINI (ve len OpenCV frame)
    # =====================================================
    def _draw_skeleton(self, frame):

        if (
            self.pose_results is None
            or not self.pose_results.pose_landmarks
        ):
            return frame

        h, w = frame.shape[:2]
        lm   = self.pose_results.pose_landmarks.landmark

        is_bad = self.body_data.get("is_bad_posture", False)
        color  = (73, 81, 248) if is_bad else (170, 212, 0)

        CONNECTIONS = [
            (11, 12), (11, 13), (13, 15),
            (12, 14), (14, 16),
            (11, 23), (12, 24), (23, 24),
            (7,  11), (8,  12),
        ]

        for a, b in CONNECTIONS:

            try:

                pa = (int(lm[a].x * w), int(lm[a].y * h))
                pb = (int(lm[b].x * w), int(lm[b].y * h))

                if (
                    lm[a].visibility > 0.4
                    and lm[b].visibility > 0.4
                    and 0 < pa[0] < w
                    and 0 < pb[0] < w
                ):

                    cv2.line(frame, pa, pb, color, 2, cv2.LINE_AA)

            except Exception:

                pass

        for idx in [7, 8, 11, 12, 13, 14, 23, 24]:

            try:

                p = (int(lm[idx].x * w), int(lm[idx].y * h))

                if (
                    lm[idx].visibility > 0.4
                    and 0 < p[0] < w
                    and 0 < p[1] < h
                ):

                    cv2.circle(frame, p, 4, color, -1, cv2.LINE_AA)

            except Exception:

                pass

        return frame

    def _draw_hud_mini(self, frame):
        """HUD toi gian o goc tren trai cua OpenCV frame."""

        h, w = frame.shape[:2]

        ov = frame.copy()
        cv2.rectangle(ov, (0, 0), (200, 68), (13, 17, 23), -1)
        cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)

        st     = self.sit_data.get("state", "unknown")
        labels = {
            "sitting":  "DANG NGOI",
            "standing": "DANG DUNG",
            "away":     "KHONG CO MAT",
            "unknown":  "DANG NHAN DIEN...",
        }
        colors = {
            "sitting":  (170, 212,  0),
            "standing": ( 88, 166, 255),
            "away":     (139, 148, 158),
            "unknown":  ( 72,  79,  88),
        }

        cv2.putText(
            frame, "EyeGuard",
            (8, 20), cv2.FONT_HERSHEY_SIMPLEX,
            0.58, (0, 212, 170), 2, cv2.LINE_AA
        )

        cv2.putText(
            frame, labels.get(st, st),
            (8, 42), cv2.FONT_HERSHEY_SIMPLEX,
            0.46, colors.get(st, (72, 79, 88)), 1, cv2.LINE_AA
        )

        conf = self.sit_data.get("confidence", 0.0)

        conf = self.sit_data.get("confidence", 0.0)
        cv2.putText(
            frame, f"conf: {conf:.2f}",
            (8, 60), cv2.FONT_HERSHEY_SIMPLEX,
            0.36, (72, 79, 88), 1, cv2.LINE_AA
        )

        # Debug pose signals
        dbg = self.sit_data.get("pose_debug", {})
        if dbg:
            sig = dbg.get("standing_signals", 0)
            sh_w = dbg.get("sh_width", 0)
            n2s  = dbg.get("nose_to_sh", 0)
            ny   = dbg.get("nose_y", 0)
            dbg_txt = f"sig:{sig} sw:{sh_w:.2f} n2s:{n2s:.2f} ny:{ny:.2f}"
            cv2.putText(
                frame, dbg_txt,
                (8, 76), cv2.FONT_HERSHEY_SIMPLEX,
                0.32, (60, 60, 100), 1, cv2.LINE_AA
            )

        return frame

    # =====================================================
    # PRINT STATS
    # =====================================================
    def _print_stats(self):

        s  = self.session_tracker.get_stats()
        bp = self.body_data.get("bad_posture_pct", 0)

        print("\n" + "=" * 45)
        print("      THONG KE PHIEN LAM VIEC")
        print("=" * 45)
        print(f" Tong thoi gian : {s['session_duration']//60} phut")
        print(f" Ngoi lien tuc  : {int(self.sitting_det.get_sitting_duration()//60)} phut")
        print(f" Tong nghi      : {s['total_away_time']//60} phut")
        print(f" So lan nghi    : {s['break_count']} lan")
        print(f" Chop mat       : {self.eye_tracker.total_blinks} lan")
        print(f" No nghi        : {int(self.sit_data.get('break_debt_sec', 0)//60)} phut")
        print(f" Tu the xau     : {bp:.0f}% thoi gian")
        print("=" * 45 + "\n")

    # =====================================================
    # BUILD UI WARNINGS (cho Dashboard banner)
    # =====================================================
    def _build_ui_warnings(self):

        warns = []
        now   = time.time()
        cd    = self._cfg.get("notification_cooldown", 300)

        def _can(k): return now - self._last_notify.get(k, 0) > cd

        sit_s = self.sitting_det.get_sitting_duration()
        sit_g = self._cfg.get("sitting_warning_time", 2700)

        if sit_s >= sit_g and _can("sit"):

            mins = int(sit_s // 60)

            warns.append({
                "severity":    "high",
                "banner_text": f"Ngoi {mins} phut! Hay dung day di lai.",
            })

        elif "no_blink" in self.eye_data.get("warnings", []):

            warns.append({
                "severity":    "low",
                "banner_text": "Hay chop mat – mat dang kho!",
            })

        for data in [self.posture_data, self.body_data]:

            if (
                data.get("is_bad_posture")
                and data.get("bad_posture_duration", 0) > 120
                and data.get("posture_issues")
            ):

                warns.append({
                    "severity":    "medium",
                    "banner_text": f"{data['posture_issues'][0]} – chinh lai tu the!",
                })

                break

        return warns

    # =====================================================
    # WORKER THREAD (camera loop)
    # =====================================================
    def _worker(self):

        while self.running:

            # ── Doc lenh tu UI ────────────────────────────────────
            try:

                cmd = self.q_cmd.get_nowait()

                if cmd["cmd"] == "quit":

                    self.running = False
                    break

                elif cmd["cmd"] == "break":

                    self.sitting_det.mark_break()
                    self.session_tracker.mark_break_taken()
                    self.eye_tracker.reset_session()
                    self.last_eye_break_notify = time.time()

                elif cmd["cmd"] == "reset":

                    self._rebuild_modules()
                    self.last_eye_break_notify = time.time()

            except Exception:

                pass

            # ── Doc frame ─────────────────────────────────────────
            ret, frame = self.cap.read()

            if not ret:

                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)

            frame, face_detected = self._process_frame(frame)

            frame = self._draw_skeleton(frame)

            frame = self._draw_hud_mini(frame)

            # ── Chuyen anh sang Tkinter ImageTk ───────────────────
            cam_raw = None
            tk_img  = None

            try:

                from PIL import Image, ImageTk

                cam_raw = Image.fromarray(
                    cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                )

                tk_img = ImageTk.PhotoImage(cam_raw)

            except Exception:

                pass

            # ── Dong goi payload gui len Dashboard ────────────────
            payload = {

                "cam_img": tk_img,
                "cam_raw": cam_raw,

                # sitting detector
                "state":            self.sit_data.get("state",            "unknown"),
                "state_color":      self.sit_data.get("state_color",      "#484f58"),
                "confidence":       self.sit_data.get("confidence",       0.0),
                "sitting_duration": self.sit_data.get("sitting_duration", 0),
                "sitting_progress": self.sit_data.get("sitting_progress", 0.0),
                "sitting_goal_min": self.settings.get("sitting_warning_min", 45),
                "break_debt_sec":   self.sit_data.get("break_debt_sec",   0),

                # trackers
                "eye":     self.eye_data,
                "posture": self.posture_data,
                "body":    self.body_data,

                # stats
                "stats": self.sit_data.get("stats", {}),

                # banner canh bao
                "ui_warnings": self._build_ui_warnings(),
            }

            try:

                # Xa queue neu day tranh lag
                while not self.q_data.empty():
                    self.q_data.get_nowait()

                self.q_data.put_nowait(payload)

            except Exception:

                pass

    # =====================================================
    # RUN
    # =====================================================
    def run(self):

        self.logger.info("EyeGuard v3 dang khoi dong...")

        if not self._init_mediapipe():
            return

        if not self._init_camera():
            return

        self.running = True

        # Khoi worker thread (camera loop)
        worker_t = threading.Thread(
            target=self._worker,
            daemon=True
        )

        worker_t.start()

        # Mo Dashboard (chay o main thread – Tkinter yeu cau)
        dashboard = DashboardWindow(
            self.q_data,
            self.q_cmd,
            settings_manager=self.settings,
            on_open_settings=self._open_settings,
        )

        self.logger.info(
            "[F11]=Fullscreen | [Esc]=Thu nho | [B]=Nghi | [C]=Settings | [Q]=Thoat"
        )

        dashboard.run()  # block cho den khi dong cua so

        # ── Cleanup ───────────────────────────────────────────────
        self.running = False

        worker_t.join(timeout=2)

        if self.cap:
            self.cap.release()

        if self.face_mesh:
            self.face_mesh.close()

        if self.pose:
            self.pose.close()

        cv2.destroyAllWindows()

        self._print_stats()


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":

    app = EyeGuardApp()

    app.run()