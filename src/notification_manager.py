"""
Module quản lý thông báo:
- Popup cảnh báo với giao diện đẹp (Tkinter)
- Âm thanh cảnh báo (winsound.Beep chính, pygame fallback)
- Rung (Windows: ctypes MessageBeep / winsound)
- Chống spam thông báo

FIX LOG:
  - winsound.Beep: dùng làm backend âm thanh chính (Test 1 OK)
  - pygame: sửa lỗi "Array must be 2-dimensional for stereo mixer"
            → khởi tạo channels=2 (stereo), reshape array thành (N, 2)
  - Fallback chain: winsound.Beep → pygame → terminal bell
"""

import time
import threading
import sys


class NotificationManager:

    def __init__(self, config):

        self.config = config

        self.cooldowns     = {}        # {warning_type: last_shown_time}
        self.active_popups = set()

        self._sound_initialized = False
        self._pygame_ok         = False

        self._init_sound()

    # =========================================================
    # INIT SOUND
    # =========================================================
    def _init_sound(self):
        """Khởi tạo pygame mixer (stereo để tránh lỗi sndarray 2D)"""

        if not self.config.get("enable_sound", True):
            return

        try:
            import pygame

            # STEREO (channels=2) → sndarray yêu cầu array 2D (N, 2)
            pygame.mixer.init(
                frequency=44100,
                size=-16,
                channels=2,      # <-- FIX: stereo thay vì mono
                buffer=512
            )

            self._sound_initialized = True
            self._pygame_ok         = True

            print("[Sound] Pygame mixer khoi dong thanh cong (stereo)")

        except Exception as e:

            print(f"[Sound] Khong the khoi tao pygame: {e}")
            print("[Sound] Se dung winsound.Beep lam backend chinh")

    # =========================================================
    # VIBRATE (RUNG)
    # =========================================================
    def _vibrate(self, severity: str = "medium"):
        """
        Phat rung / tieng he thong theo muc do.
        Windows: winsound.MessageBeep
        Linux/Mac: terminal bell
        """

        def _run():

            try:
                import winsound

                beep_map = {
                    "high":   winsound.MB_ICONHAND,
                    "medium": winsound.MB_ICONEXCLAMATION,
                    "low":    winsound.MB_ICONASTERISK,
                }

                beep_type = beep_map.get(severity, winsound.MB_ICONEXCLAMATION)
                repeat    = 3 if severity == "high" else 2

                for _ in range(repeat):
                    winsound.MessageBeep(beep_type)
                    time.sleep(0.35)

            except ImportError:

                count = 3 if severity == "high" else 2
                for _ in range(count):
                    print('\a', end='', flush=True)
                    time.sleep(0.3)

            except Exception as e:

                print(f"[Vibrate] Loi: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # =========================================================
    # WINSOUND BEEP BACKEND (PRIMARY – Test 1 OK)
    # =========================================================
    def _beep_winsound(self, pattern: list):
        """
        Phat melody bang winsound.Beep (built-in Windows, Test 1 OK).
        pattern = list of (frequency_hz, duration_ms)
        Tan so hop le: 37–32767 Hz
        """

        def _run():

            try:
                import winsound

                for freq, dur_ms in pattern:
                    if freq > 0:
                        # winsound.Beep yeu cau freq 37..32767
                        freq_clamped = max(37, min(32767, freq))
                        winsound.Beep(freq_clamped, dur_ms)
                    else:
                        # Im lang / khoang cach giua notes
                        time.sleep(dur_ms / 1000)

            except ImportError:

                # Fallback: terminal bell
                print('\a', end='', flush=True)

            except Exception as e:

                print(f"[Sound/winsound] Loi: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # =========================================================
    # PYGAME BEEP BACKEND (FALLBACK – Fix stereo array)
    # =========================================================
    def _beep_pygame(self, pattern: list):
        """
        Phat melody bang pygame (fallback neu winsound khong co).
        FIX: reshape wave → (N, 2) cho stereo mixer.
        pattern = list of (frequency_hz, duration_ms)
        """

        if not self._pygame_ok:
            return

        def _run():

            try:
                import pygame
                import numpy as np

                sample_rate = 44100
                volume      = float(self.config.get("alarm_volume", 0.8))

                for freq, dur_ms in pattern:

                    if freq <= 0:
                        time.sleep(dur_ms / 1000)
                        continue

                    n_samples = int(sample_rate * dur_ms / 1000)
                    t         = np.linspace(0, dur_ms / 1000, n_samples, False)

                    # Sine wave + harmonics
                    wave  = np.sin(2 * np.pi * freq * t)
                    wave += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
                    wave += 0.1 * np.sin(2 * np.pi * freq * 3 * t)

                    # Envelope fade in/out
                    fade = min(int(n_samples * 0.05), 200)
                    if fade > 0:
                        wave[:fade]  *= np.linspace(0, 1, fade)
                        wave[-fade:] *= np.linspace(1, 0, fade)

                    wave_int = (wave * 32767 * volume).astype(np.int16)

                    # FIX: stereo → reshape thanh (N, 2)
                    # Phat ca 2 kenh (L + R) giong nhau
                    stereo = np.column_stack([wave_int, wave_int])  # shape: (N, 2)

                    sound = pygame.sndarray.make_sound(stereo)
                    sound.play()

                    pygame.time.wait(dur_ms + 30)

            except Exception as e:

                print(f"[Sound/pygame] Loi phat am thanh: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # =========================================================
    # BEEP ROUTER – tu dong chon backend
    # =========================================================
    def _beep(self, pattern: list):
        """
        Chon backend am thanh theo uu tien:
          1. winsound.Beep  (Windows built-in, Test 1 OK)
          2. pygame         (neu winsound khong co, da fix stereo)
          3. terminal bell  (fallback cuoi)
        """

        try:
            import winsound  # noqa: F401 – chi kiem tra co san hay khong
            self._beep_winsound(pattern)
        except ImportError:
            if self._pygame_ok:
                self._beep_pygame(pattern)
            else:
                print('\a', end='', flush=True)

    # =========================================================
    # PATTERN PRESETS
    # =========================================================
    def _play_pattern(self, severity: str):
        """Phat melody phu hop voi muc do canh bao."""

        patterns = {

            # High: 3 tieng cao – gap – canh bao khan cap
            "high": [
                (880, 180), (0, 60),
                (880, 180), (0, 60),
                (880, 320),
            ],

            # Medium: 2 tieng len – nhe nhang nhac nho
            "medium": [
                (660, 200), (0, 80),
                (880, 350),
            ],

            # Low: 1 tieng don gian
            "low": [
                (550, 300),
            ],
        }

        pattern = patterns.get(severity, patterns["medium"])
        self._beep(pattern)

    # =========================================================
    # COOLDOWN
    # =========================================================
    def can_show(self, warning_type):

        cooldown   = self.config.get("notification_cooldown", 300)
        last_shown = self.cooldowns.get(warning_type, 0)

        return time.time() - last_shown > cooldown

    def mark_shown(self, warning_type):

        self.cooldowns[warning_type] = time.time()

    # =========================================================
    # POPUP
    # =========================================================
    def show_popup(self, title, message, severity="medium", warning_type=None):
        """Hien thi popup Tkinter trong thread rieng"""

        if not self.config.get("enable_popup", True):
            return

        if warning_type and not self.can_show(warning_type):
            return

        if warning_type:
            self.mark_shown(warning_type)
            self.active_popups.add(warning_type)

        def _show():

            try:
                import tkinter as tk

                colors = {
                    "high":   {
                        "bg":     "#1a0505",
                        "accent": "#ff4444",
                        "btn":    "#cc0000",
                        "bar":    "#ff2222",
                    },
                    "medium": {
                        "bg":     "#0a1505",
                        "accent": "#44dd44",
                        "btn":    "#007700",
                        "bar":    "#22cc22",
                    },
                    "low":    {
                        "bg":     "#05080f",
                        "accent": "#4499ff",
                        "btn":    "#0055cc",
                        "bar":    "#2277ff",
                    },
                }

                c = colors.get(severity, colors["medium"])

                root = tk.Tk()
                root.title("EyeGuard")
                root.geometry("440x230")
                root.configure(bg=c["bg"])
                root.attributes("-topmost", True)
                root.resizable(False, False)

                # Can giua man hinh
                root.update_idletasks()
                sw = root.winfo_screenwidth()
                sh = root.winfo_screenheight()
                x  = (sw - 440) // 2
                y  = (sh - 230) // 2
                root.geometry(f"440x230+{x}+{y}")

                # Thanh mau tren cung
                tk.Frame(root, bg=c["bar"], height=6).pack(fill=tk.X)

                # Title
                tk.Label(
                    root, text=title,
                    font=("Segoe UI", 16, "bold"),
                    fg=c["accent"], bg=c["bg"],
                    pady=12,
                ).pack()

                # Message
                tk.Label(
                    root, text=message,
                    font=("Segoe UI", 11),
                    fg="#dddddd", bg=c["bg"],
                    justify=tk.CENTER,
                    wraplength=400,
                ).pack(pady=4)

                # Buttons
                btn_frame = tk.Frame(root, bg=c["bg"])
                btn_frame.pack(pady=14)

                def dismiss():
                    if warning_type:
                        self.active_popups.discard(warning_type)
                    root.destroy()

                def snooze():
                    """Nhac lai sau 5 phut"""
                    if warning_type:
                        self.cooldowns[warning_type] = (
                            time.time()
                            + 300
                            - self.config.get("notification_cooldown", 300)
                        )
                        self.active_popups.discard(warning_type)
                    root.destroy()

                tk.Button(
                    btn_frame,
                    text="✓  Da hieu",
                    font=("Segoe UI", 10, "bold"),
                    bg=c["btn"], fg="white",
                    relief=tk.FLAT, padx=22, pady=8,
                    cursor="hand2",
                    command=dismiss,
                ).pack(side=tk.LEFT, padx=8)

                tk.Button(
                    btn_frame,
                    text="⏰  Nhac sau 5p",
                    font=("Segoe UI", 10),
                    bg="#2a2a2a", fg="#aaaaaa",
                    relief=tk.FLAT, padx=22, pady=8,
                    cursor="hand2",
                    command=snooze,
                ).pack(side=tk.LEFT, padx=8)

                # Tu dong dong sau 20 giay
                root.after(
                    20000,
                    lambda: dismiss() if root.winfo_exists() else None
                )

                root.mainloop()

            except Exception as e:

                print(f"[Popup] Loi hien thi popup: {e}")

            finally:

                if warning_type:
                    self.active_popups.discard(warning_type)

        threading.Thread(target=_show, daemon=True).start()

    # =========================================================
    # NOTIFY (AM THANH + RUNG + POPUP)
    # =========================================================
    def notify(self, warning_type, title, message,
               severity="medium", with_sound=True):
        """Gui thong bao day du: melody + rung + popup"""

        if not self.can_show(warning_type):
            return

        # 1. Am thanh melody
        if with_sound and self.config.get("enable_sound", True):
            self._play_pattern(severity)

        # 2. Rung
        self._vibrate(severity)

        # 3. Popup
        self.show_popup(title, message, severity, warning_type)

    # =========================================================
    # SHORTCUTS
    # =========================================================
    def notify_sitting_too_long(self, minutes):

        self.notify(
            "sitting_too_long",
            "Ngoi qua lau!",
            f"Ban da ngoi {minutes} phut lien tuc.\n"
            f"Hay dung day di lai 5 phut de giam met moi!",
            severity="high",
        )

    def notify_eye_strain(self):

        self.notify(
            "eye_strain",
            "Mat can nghi ngoi!",
            "Ap dung quy tac 20-20-20:\n"
            "Nhin vat cach 6m trong 20 giay\n"
            "roi tiep tuc lam viec.",
            severity="medium",
        )

    def notify_no_blink(self):

        self.notify(
            "no_blink",
            "Chop mat di nao!",
            "Ban chua chop mat trong hon 1 phut.\n"
            "Hay chop mat vai lan de giu am cho mat!",
            severity="low",
        )

    def notify_bad_posture(self, issues):

        issues_text = "\n".join(f"• {i}" for i in issues)

        self.notify(
            "bad_posture",
            "Kiem tra tu the!",
            f"Phat hien tu the khong tot:\n{issues_text}\n"
            f"Hay dieu chinh lai tu the ngoi.",
            severity="medium",
        )

    def notify_no_movement(self):

        self.notify(
            "no_movement",
            "Hay van dong!",
            "Ban gan nhu khong di chuyen trong 30 phut.\n"
            "Hay gian co hoac dung day di lai mot chut!",
            severity="medium",
        )