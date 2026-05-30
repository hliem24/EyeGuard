"""
Cửa sổ cài đặt EyeGuard – Tkinter
Cho phép người dùng tuỳ chỉnh:
  - Thời gian nhắc nhở (ngồi, mắt, chớp mắt, tư thế, vận động)
  - Âm thanh cảnh báo
  - Các ngưỡng phát hiện
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading


# ─────────────────────────────────────────────────────────────────
# Palette màu (dark teal theme)
# ─────────────────────────────────────────────────────────────────
BG       = "#0d1117"
BG2      = "#161b22"
BG3      = "#21262d"
ACCENT   = "#00d4aa"
ACCENT2  = "#005f4e"
FG       = "#e6edf3"
FG2      = "#8b949e"
RED      = "#f85149"
YELLOW   = "#e3b341"
GREEN    = "#3fb950"
BLUE     = "#58a6ff"
FONT     = ("Segoe UI", 10)
FONT_B   = ("Segoe UI", 10, "bold")
FONT_H   = ("Segoe UI", 13, "bold")
FONT_S   = ("Segoe UI", 9)


class RoundedLabel(tk.Canvas):
    """Label với nền bo góc"""
    def __init__(self, parent, text, bg_color=BG3, fg=FG, font=FONT, **kw):
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, bg=bg_color, **kw)
        self.create_text(10, 14, anchor="w", text=text, fill=fg, font=font)


class SliderRow(tk.Frame):
    """Một hàng slider có label + giá trị hiện tại"""
    def __init__(self, parent, label, key, min_val, max_val, unit, settings, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self.key      = key
        self.settings = settings
        self.unit     = unit
        self.var      = tk.DoubleVar(value=settings.get(key))

        # Label mô tả
        lbl = tk.Label(
            self, text=label, font=FONT,
            fg=FG2, bg=BG2, anchor="w", width=30
        )
        lbl.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        # Slider
        sl = ttk.Scale(
            self, from_=min_val, to=max_val,
            orient="horizontal", variable=self.var,
            command=self._on_change, length=180,
        )
        sl.grid(row=0, column=1, padx=4, pady=6)

        # Hiển thị giá trị
        self.val_lbl = tk.Label(
            self, text=self._fmt(), font=FONT_B,
            fg=ACCENT, bg=BG2, width=10, anchor="e"
        )
        self.val_lbl.grid(row=0, column=2, padx=(4, 8), pady=6)

        self.columnconfigure(1, weight=1)

    # =========================================================
    # FIX: Hien thi "30 giay" thay vi "0.5 phut"
    # =========================================================
    def _fmt(self):

        v    = self.var.get()
        unit = self.unit

        # Neu don vi la phut va gia tri < 1 → hien thi giay
        if unit in ("phút", "phut") and v < 1.0:

            giay = int(round(v * 60))

            return f"{giay} giây"

        # Binh thuong
        if isinstance(v, float) and v != int(v):

            return f"{v:.2f} {unit}"

        return f"{int(v)} {unit}"

    def _on_change(self, _=None):
        self.val_lbl.config(text=self._fmt())

    def value(self):
        v = self.var.get()
        return round(v, 2) if (v != int(v)) else int(v)


class ToggleRow(tk.Frame):
    def __init__(self, parent, label, key, settings, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self.key      = key
        self.settings = settings
        self.var      = tk.BooleanVar(value=bool(settings.get(key)))

        tk.Label(
            self, text=label, font=FONT, fg=FG2, bg=BG2,
            anchor="w", width=30
        ).grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        self._build_toggle()

    def _build_toggle(self):
        self.track = tk.Canvas(
            self, width=44, height=22, bg=BG2,
            highlightthickness=0, bd=0, cursor="hand2"
        )
        self.track.grid(row=0, column=1, sticky="w", padx=4)
        self.track.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self):
        self.track.delete("all")
        on  = self.var.get()
        col = ACCENT if on else BG3
        self.track.create_rounded_rect = lambda *a, **k: None  # placeholder
        self.track.create_oval(0, 0, 22, 22, fill=col, outline="")
        self.track.create_oval(22, 0, 44, 22, fill=col, outline="")
        self.track.create_rectangle(11, 0, 33, 22, fill=col, outline="")
        cx = 33 if on else 11
        self.track.create_oval(cx - 9, 2, cx + 9, 20, fill=FG, outline="")

    def _toggle(self, _=None):
        self.var.set(not self.var.get())
        self._draw()

    def value(self):
        return self.var.get()


class SettingsWindow:
    """Cửa sổ cài đặt chính"""
    def __init__(self, settings_manager, on_save_callback=None):
        self.settings = settings_manager
        self.on_save  = on_save_callback
        self.widgets  = {}
        self.window   = None

    def open(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        self._build()

    def _build(self):
        win = tk.Toplevel()
        win.title("EyeGuard – Cài đặt")
        win.configure(bg=BG)
        win.geometry("620x720")
        win.resizable(False, True)
        win.attributes("-topmost", True)
        self.window = win

        # ─── Tiêu đề ──────────────────────────────────────────────
        hdr = tk.Frame(win, bg=ACCENT2, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(
            hdr,
            text="⚙  EyeGuard – Cài đặt cảnh báo",
            font=("Segoe UI", 14, "bold"),
            fg=ACCENT, bg=ACCENT2
        ).pack(side="left", padx=20, pady=12)

        # ─── Scrollable content ────────────────────────────────────
        outer = tk.Frame(win, bg=BG)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg=BG)
        canvas_win = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_frame_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", _on_frame_resize)

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"
        ))

        # ─── Sections ─────────────────────────────────────────────
        # FIX: sitting_warning_min min=0.5 (30 giay) thay vi 10 phut
        # FIX: notification_cooldown min=10 de test
        self._section(frame, "⏰  Thời gian nhắc nhở", [
            ("Nhắc đứng dậy sau",             "sitting_warning_min",    0.5, 120, "phút"),
            ("Nhắc nghỉ mắt (20-20-20)",      "eye_strain_min",           5,  60, "phút"),
            ("Nhắc chớp mắt nếu không chớp",  "no_blink_warning_sec",    20, 180, "giây"),
            ("Nhắc tư thế xấu sau",           "bad_posture_warn_sec",    30, 300, "giây"),
            ("Nhắc vận động nếu ít di chuyển","no_movement_warn_min",    10,  60, "phút"),
            ("Thời gian chờ giữa 2 thông báo","notification_cooldown",   10, 600, "giây"),
        ])

        self._section(frame, "👁  Phát hiện mắt", [
            ("Ngưỡng EAR phát hiện chớp mắt", "blink_ear_threshold", 0.10, 0.35, ""),
            ("Tần suất chớp mắt tối thiểu",  "min_blink_rate",          5,   25, "lần/phút"),
        ])

        self._section(frame, "🪑  Phát hiện tư thế", [
            ("Góc nghiêng đầu tối đa",        "head_tilt_threshold",      5,  45, "°"),
            ("Góc nghiêng vai tối đa",        "shoulder_lean_threshold",  5,  40, "°"),
            ("Góc cột sống tối đa",           "spine_angle_threshold",    5,  45, "°"),
            ("Mặt quá gần (% khung hình)",    "face_too_close_ratio",  0.15, 0.60, ""),
        ])

        self._section_toggles(frame, "🔔  Thông báo & Giao diện", [
            ("Bật âm thanh cảnh báo",      "enable_sound"),
            ("Bật popup thông báo",         "enable_popup"),
            ("Hiện cửa sổ camera",          "show_camera_window"),
            ("Hiện thông số trên camera",   "show_stats_overlay"),
            ("Hiện bộ xương tư thế (Pose)", "show_body_skeleton"),
        ])

        self._section(frame, "🔊  Âm lượng", [
            ("Âm lượng cảnh báo", "alarm_volume", 0.0, 1.0, ""),
        ])

        # ─── Nút bấm ──────────────────────────────────────────────
        btn_frame = tk.Frame(win, bg=BG, pady=12)
        btn_frame.pack(fill="x")

        tk.Button(
            btn_frame, text="💾  Lưu cài đặt",
            font=FONT_B, bg=ACCENT, fg=BG,
            relief="flat", padx=24, pady=8,
            cursor="hand2", command=self._save
        ).pack(side="right", padx=16)

        tk.Button(
            btn_frame, text="↩  Về mặc định",
            font=FONT, bg=BG3, fg=FG2,
            relief="flat", padx=24, pady=8,
            cursor="hand2", command=self._reset
        ).pack(side="right", padx=4)

        tk.Button(
            btn_frame, text="✕  Đóng",
            font=FONT, bg=BG3, fg=FG2,
            relief="flat", padx=24, pady=8,
            cursor="hand2", command=win.destroy
        ).pack(side="left", padx=16)

    def _section(self, parent, title, rows):
        """Tạo một nhóm slider"""
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=12, pady=(16, 2))
        tk.Label(hdr, text=title, font=FONT_H, fg=ACCENT, bg=BG).pack(side="left")
        tk.Frame(hdr, bg=ACCENT2, height=1).pack(
            side="left", fill="x", expand=True, padx=8
        )

        card = tk.Frame(parent, bg=BG2, bd=0, relief="flat")
        card.pack(fill="x", padx=12, pady=4)

        for i, (label, key, mn, mx, unit) in enumerate(rows):
            row = SliderRow(card, label, key, mn, mx, unit, self.settings)
            row.pack(fill="x")
            if i < len(rows) - 1:
                tk.Frame(card, bg=BG3, height=1).pack(fill="x", padx=8)
            self.widgets[key] = row

    def _section_toggles(self, parent, title, rows):
        """Tạo một nhóm toggle"""
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=12, pady=(16, 2))
        tk.Label(hdr, text=title, font=FONT_H, fg=ACCENT, bg=BG).pack(side="left")
        tk.Frame(hdr, bg=ACCENT2, height=1).pack(
            side="left", fill="x", expand=True, padx=8
        )

        card = tk.Frame(parent, bg=BG2, bd=0, relief="flat")
        card.pack(fill="x", padx=12, pady=4)

        for i, (label, key) in enumerate(rows):
            row = ToggleRow(card, label, key, self.settings)
            row.pack(fill="x")
            if i < len(rows) - 1:
                tk.Frame(card, bg=BG3, height=1).pack(fill="x", padx=8)
            self.widgets[key] = row

    def _save(self):
        for key, widget in self.widgets.items():
            self.settings.set(key, widget.value())
        self.settings.save()
        if self.on_save:
            self.on_save(self.settings.all())
        messagebox.showinfo(
            "Đã lưu", "Cài đặt đã được lưu thành công!",
            parent=self.window
        )

    def _reset(self):
        if messagebox.askyesno(
            "Xác nhận", "Đặt lại tất cả về mặc định?",
            parent=self.window
        ):
            self.settings.reset_to_default()
            if self.on_save:
                self.on_save(self.settings.all())
            self.window.destroy()
            self._build()


def open_settings_async(settings_manager, on_save_callback=None):
    """Mở cửa sổ cài đặt trong thread riêng (không block main loop)"""
    def _run():
        win = SettingsWindow(settings_manager, on_save_callback)
        win.open()
        if win.window:
            win.window.mainloop()

    t = threading.Thread(target=_run, daemon=True)
    t.start()