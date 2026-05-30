"""
EyeGuard Web Server - FastAPI
Thay thế Tkinter Dashboard bằng Web Dashboard (WebSocket + HTTP API)
"""

import cv2
import time
import base64
import asyncio
import logging
import threading
import queue
import sys
import os
from contextlib import asynccontextmanager

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EyeGuard-Web")


# =========================================================
# GLOBAL APP STATE (singleton)
# =========================================================
class AppState:
    def __init__(self):
        self.running      = False
        self.q_data       = queue.Queue(maxsize=4)
        self.q_cmd        = queue.Queue()
        self.worker_thread = None
        self.eye_guard_app = None
        self.clients: list[WebSocket] = []
        self.last_payload: dict = {}

app_state = AppState()


# =========================================================
# LIFESPAN
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("EyeGuard Web Server khoi dong...")
    os.makedirs("static", exist_ok=True)
    os.makedirs("logs",   exist_ok=True)
    yield
    logger.info("EyeGuard Web Server dang tat...")
    app_state.running = False
    if app_state.worker_thread:
        app_state.worker_thread.join(timeout=3)


# =========================================================
# FASTAPI APP
# =========================================================
app = FastAPI(
    title="EyeGuard Web",
    description="Anti eye-strain & posture monitoring - Web Edition",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# =========================================================
# EYEGUARD WORKER  (chay trong thread rieng)
# =========================================================
def _run_eyeguard_worker(q_data: queue.Queue, q_cmd: queue.Queue):
    """Chay camera loop trong thread, gui payload qua queue."""
    try:
        from src.settings_manager    import SettingsManager
        from src.eye_tracker         import EyeTracker
        from src.posture_tracker     import PostureTracker
        from src.session_tracker     import SessionTracker
        from src.notification_manager import NotificationManager
        from src.body_tracker        import BodyTracker
        from src.sitting_detector    import SittingDetector
        import mediapipe as mp

        settings = SettingsManager()
        cfg = settings.all()
        full_cfg = {
            **cfg,
            "sitting_warning_time": settings.sitting_warning_time,
            "eye_strain_time":      settings.eye_strain_time,
            "blink_threshold":      cfg.get("blink_ear_threshold", 0.25),
        }

        eye_tracker     = EyeTracker(full_cfg)
        posture_tracker = PostureTracker(full_cfg)
        session_tracker = SessionTracker(full_cfg)
        notifier        = NotificationManager(full_cfg)
        body_tracker    = BodyTracker(full_cfg)
        sitting_det     = SittingDetector(full_cfg)

        mp_fm   = mp.solutions.face_mesh
        mp_pose = mp.solutions.pose

        face_mesh = mp_fm.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        pose = mp_pose.Pose(
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        cap = cv2.VideoCapture(cfg.get("camera_index", 0))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        if not cap.isOpened():
            logger.error("Khong mo duoc camera!")
            return

        last_eye_notify  = time.time()
        last_notify: dict = {}

        def _can(k):
            cd = full_cfg.get("notification_cooldown", 300)
            return time.time() - last_notify.get(k, 0) > cd

        def _mark(k):
            last_notify[k] = time.time()

        logger.info("Worker thread bat dau chay...")
        app_state.running = True

        while app_state.running:
            # ── Lenh tu API ──────────────────────────────────────
            try:
                cmd = q_cmd.get_nowait()
                if cmd["cmd"] == "quit":
                    break
                elif cmd["cmd"] == "break":
                    sitting_det.mark_break()
                    session_tracker.mark_break_taken()
                    eye_tracker.reset_session()
                    last_eye_notify = time.time()
                elif cmd["cmd"] == "reset":
                    eye_tracker.reset_session()
                    last_eye_notify = time.time()
            except Exception:
                pass

            # ── Doc frame ────────────────────────────────────────
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            face_results = face_mesh.process(rgb)
            pose_results = pose.process(rgb)
            rgb.flags.writeable = True

            face_detected = (
                face_results.multi_face_landmarks is not None
                and len(face_results.multi_face_landmarks) > 0
            )

            sit_data = sitting_det.update(face_detected, pose_results, frame.shape)
            session_tracker.update_presence(face_detected)

            eye_data     = {}
            posture_data = {}

            if face_detected:
                face_lm      = face_results.multi_face_landmarks[0]
                eye_data     = eye_tracker.update(face_lm, frame.shape)
                posture_data = posture_tracker.update(face_lm, frame.shape)
                session_tracker.update_movement(face_lm, frame.shape)

            body_data = body_tracker.update(pose_results, frame.shape)

            # ── Notifications ─────────────────────────────────────
            now = time.time()
            for warn in sitting_det.check_warnings():
                if warn["type"] == "sitting_too_long" and _can("sit"):
                    notifier.notify_sitting_too_long(
                        int(sitting_det.get_sitting_duration() // 60)
                    )
                    _mark("sit")
                elif warn["type"] == "no_movement" and _can("move"):
                    notifier.notify_no_movement()
                    _mark("move")

            if "no_blink" in eye_data.get("warnings", []) and _can("blink"):
                notifier.notify_no_blink()
                _mark("blink")

            if now - last_eye_notify > full_cfg.get("eye_strain_time", 1200):
                notifier.notify_eye_strain()
                last_eye_notify = now

            # ── Ve skeleton + HUD len frame ───────────────────────
            if pose_results and pose_results.pose_landmarks:
                h, w = frame.shape[:2]
                lm    = pose_results.pose_landmarks.landmark
                is_bad = body_data.get("is_bad_posture", False)
                color  = (73, 81, 248) if is_bad else (170, 212, 0)
                CONN = [
                    (11,12),(11,13),(13,15),(12,14),(14,16),
                    (11,23),(12,24),(23,24),(7,11),(8,12),
                ]
                for a, b in CONN:
                    try:
                        pa = (int(lm[a].x*w), int(lm[a].y*h))
                        pb = (int(lm[b].x*w), int(lm[b].y*h))
                        if lm[a].visibility>0.4 and lm[b].visibility>0.4:
                            cv2.line(frame, pa, pb, color, 2, cv2.LINE_AA)
                    except Exception:
                        pass

            # HUD mini
            ov = frame.copy()
            cv2.rectangle(ov, (0,0), (200,68), (13,17,23), -1)
            cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)
            st = sit_data.get("state","unknown")
            state_labels = {"sitting":"DANG NGOI","standing":"DANG DUNG","away":"KHONG CO MAT","unknown":"NHAN DIEN..."}
            state_colors = {"sitting":(170,212,0),"standing":(88,166,255),"away":(139,148,158),"unknown":(72,79,88)}
            cv2.putText(frame,"EyeGuard",(8,20),cv2.FONT_HERSHEY_SIMPLEX,0.58,(0,212,170),2,cv2.LINE_AA)
            cv2.putText(frame,state_labels.get(st,st),(8,42),cv2.FONT_HERSHEY_SIMPLEX,0.46,state_colors.get(st,(72,79,88)),1,cv2.LINE_AA)

            # ── Encode JPEG → base64 ──────────────────────────────
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            img_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

            # ── Xay dung warnings ─────────────────────────────────
            warnings = []
            sit_s = sitting_det.get_sitting_duration()
            sit_g = full_cfg.get("sitting_warning_time", 2700)
            if sit_s >= sit_g:
                warnings.append({"severity":"high","text":f"Ngoi {int(sit_s//60)} phut! Hay dung day di lai."})
            if "no_blink" in eye_data.get("warnings",[]):
                warnings.append({"severity":"low","text":"Hay chop mat – mat dang kho!"})
            for d in [posture_data, body_data]:
                if d.get("is_bad_posture") and d.get("bad_posture_duration",0)>120 and d.get("posture_issues"):
                    warnings.append({"severity":"medium","text":f"{d['posture_issues'][0]} – chinh lai tu the!"})
                    break

            stats = session_tracker.get_stats()

            payload = {
                "type":             "frame",
                "img":              img_b64,
                "state":            sit_data.get("state","unknown"),
                "state_color":      sit_data.get("state_color","#484f58"),
                "confidence":       round(sit_data.get("confidence",0.0), 2),
                "sitting_duration": int(sit_data.get("sitting_duration",0)),
                "sitting_progress": round(sit_data.get("sitting_progress",0.0), 2),
                "sitting_goal_min": settings.get("sitting_warning_min",45),
                "break_debt_sec":   int(sit_data.get("break_debt_sec",0)),
                "blink_rate":       round(eye_data.get("blink_rate",0.0), 1),
                "total_blinks":     eye_tracker.total_blinks,
                "ear":              round(eye_data.get("ear",0.0), 3),
                "face_detected":    face_detected,
                "posture_score":    posture_data.get("posture_score",100),
                "posture_issues":   posture_data.get("posture_issues",[]),
                "body_bad":         body_data.get("is_bad_posture",False),
                "session_minutes":  int(stats.get("session_duration",0)//60),
                "break_count":      stats.get("break_count",0),
                "warnings":         warnings,
            }

            app_state.last_payload = {k:v for k,v in payload.items() if k!="img"}

            try:
                while not q_data.empty():
                    q_data.get_nowait()
                q_data.put_nowait(payload)
            except Exception:
                pass

        cap.release()
        face_mesh.close()
        pose.close()
        logger.info("Worker thread ket thuc.")

    except Exception as e:
        logger.exception(f"Worker thread loi: {e}")
        app_state.running = False


# =========================================================
# WEBSOCKET BROADCASTER
# =========================================================
async def broadcaster():
    """Lay payload tu queue, phat toi tat ca WebSocket clients."""
    loop = asyncio.get_event_loop()

    while True:
        try:
            payload = await loop.run_in_executor(
                None,
                lambda: app_state.q_data.get(timeout=0.1)
            )

            disconnected = []

            for ws in app_state.clients[:]:
                try:
                    import json
                    await ws.send_json(payload)
                except Exception:
                    disconnected.append(ws)

            for ws in disconnected:
                if ws in app_state.clients:
                    app_state.clients.remove(ws)

        except Exception:
            await asyncio.sleep(0.05)


# =========================================================
# ROUTES
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve dashboard HTML."""
    html_path = os.path.join("static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>EyeGuard Web - static/index.html not found</h1>")


@app.post("/api/start")
async def start_tracking():
    """Bat dau camera tracking."""
    if app_state.running:
        return {"status": "already_running"}

    app_state.q_data  = queue.Queue(maxsize=4)
    app_state.q_cmd   = queue.Queue()
    app_state.running = True

    app_state.worker_thread = threading.Thread(
        target=_run_eyeguard_worker,
        args=(app_state.q_data, app_state.q_cmd),
        daemon=True,
    )
    app_state.worker_thread.start()

    asyncio.create_task(broadcaster())

    return {"status": "started"}


@app.post("/api/stop")
async def stop_tracking():
    """Dung camera tracking."""
    app_state.running = False
    app_state.q_cmd.put_nowait({"cmd": "quit"})
    return {"status": "stopped"}


@app.post("/api/break")
async def take_break():
    """Ghi nhan nghi giai lao."""
    if not app_state.running:
        raise HTTPException(status_code=400, detail="Tracking chua chay")
    app_state.q_cmd.put_nowait({"cmd": "break"})
    return {"status": "break_marked"}


@app.post("/api/reset")
async def reset_session():
    """Reset phien lam viec."""
    app_state.q_cmd.put_nowait({"cmd": "reset"})
    return {"status": "reset"}


@app.get("/api/status")
async def get_status():
    """Lay trang thai hien tai (khong can WebSocket)."""
    return {
        "running": app_state.running,
        "clients": len(app_state.clients),
        **app_state.last_payload,
    }


@app.get("/api/settings")
async def get_settings():
    """Lay cai dat hien tai."""
    try:
        from src.settings_manager import SettingsManager
        sm = SettingsManager()
        return sm.all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SettingsUpdate(BaseModel):
    key:   str
    value: object


@app.post("/api/settings")
async def update_setting(body: SettingsUpdate):
    """Cap nhat mot cai dat."""
    try:
        from src.settings_manager import SettingsManager
        sm = SettingsManager()
        sm.set(body.key, body.value)
        sm.save()
        return {"status": "saved", "key": body.key, "value": body.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket: nhan frame + data realtime."""
    await ws.accept()
    app_state.clients.append(ws)
    logger.info(f"WebSocket client ket noi. Tong: {len(app_state.clients)}")

    try:
        while True:
            # Nhan lenh tu browser (neu co)
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
                cmd  = data.get("cmd")
                if cmd in ("break", "reset", "quit"):
                    app_state.q_cmd.put_nowait({"cmd": cmd})
            except asyncio.TimeoutError:
                pass
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        if ws in app_state.clients:
            app_state.clients.remove(ws)
        logger.info(f"WebSocket client ngat ket noi. Con lai: {len(app_state.clients)}")