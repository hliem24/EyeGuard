"""
EyeGuard Dashboard – UI fullscreen Tkinter
==========================================
Layout:
  ┌──────────────────────────────────────────────────────┐
  │  HEADER: logo + trạng thái + nút thoát              │
  ├────────────────────────┬─────────────────────────────┤
  │  Camera feed (live)    │  Panel phải (progress bar): │
  │  + skeleton overlay    │   • Sitting  progress bar   │
  │                        │   • Blink    progress bar   │
  │                        │   • Posture  progress bar   │
  │                        │   • Stepper  buổi làm việc  │
  │                        │   • 4 chỉ số mini           │
  ├────────────────────────┴─────────────────────────────┤
  │  FOOTER: 5 stat pills                               │
  └──────────────────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import math
import queue
import collections


# ── Palette ───────────────────────────────────────────────────────
BG0    = "#0d1117"
BG1    = "#161b22"
BG2    = "#21262d"
BG3    = "#30363d"
TEAL   = "#00d4aa"
TEAL_D = "#005f4e"
RED    = "#f85149"
YELLOW = "#e3b341"
GREEN  = "#3fb950"
BLUE   = "#58a6ff"
PURPLE = "#bc8cff"
FG     = "#e6edf3"
FG2    = "#8b949e"
FG3    = "#484f58"

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_LABEL  = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 10)
FONT_STAT   = ("Consolas", 16, "bold")
FONT_TINY   = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")


# ═══════════════════════════════════════════════════════════════════
# PROGRESS BAR WIDGET
# ═══════════════════════════════════════════════════════════════════
class ProgressCard(tk.Frame):
    """
    Card gồm: icon tròn + tên + progress bar + badge trạng thái.
    Giống phong cách Progress Bar Figma design.
    """

    # Mau theo muc do
    COLOR_GOOD = GREEN
    COLOR_WARN = YELLOW
    COLOR_BAD  = RED

    def __init__(self, parent, icon_text: str, title: str,
                 icon_bg: str = TEAL_D, **kw):
        super().__init__(parent, bg=BG2, **kw)

        self._title  = title
        self._ratio  = 0.0
        self._anim_ratio = 0.0

        # ── Dòng trên: icon + text + badge ───────────────────────
        top = tk.Frame(self, bg=BG2)
        top.pack(fill="x", padx=12, pady=(10, 4))

        # Icon tron
        icon_frame = tk.Frame(top, bg=icon_bg,
                              width=36, height=36)
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)
        self._icon_lbl = tk.Label(icon_frame, text=icon_text,
                                  font=("Segoe UI", 14),
                                  fg=FG, bg=icon_bg)
        self._icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Title + sub
        txt_frame = tk.Frame(top, bg=BG2)
        txt_frame.pack(side="left", padx=8, fill="x", expand=True)

        self._title_lbl = tk.Label(txt_frame, text=title,
                                   font=FONT_LABEL, fg=FG, bg=BG2,
                                   anchor="w")
        self._title_lbl.pack(anchor="w")

        self._sub_lbl = tk.Label(txt_frame, text="--",
                                 font=FONT_TINY, fg=FG2, bg=BG2,
                                 anchor="w")
        self._sub_lbl.pack(anchor="w")

        # Phan tram + badge
        right_frame = tk.Frame(top, bg=BG2)
        right_frame.pack(side="right")

        self._pct_lbl = tk.Label(right_frame, text="0%",
                                 font=FONT_MONO, fg=TEAL, bg=BG2)
        self._pct_lbl.pack(anchor="e")

        self._badge = tk.Label(right_frame, text="--",
                               font=FONT_TINY, fg=FG3, bg=BG3,
                               padx=8, pady=2)
        self._badge.pack(anchor="e", pady=(2, 0))

        # ── Track progress bar ────────────────────────────────────
        track_frame = tk.Frame(self, bg=BG3, height=8)
        track_frame.pack(fill="x", padx=12, pady=(0, 10))
        track_frame.pack_propagate(False)

        self._fill = tk.Frame(track_frame, bg=TEAL, height=8)
        self._fill.place(x=0, y=0, relheight=1.0, width=0)

        # Khoi dong animation
        self._animating = False

    def update_data(self, ratio: float, sub_text: str,
                    badge_text: str, pct_override: str = None):
        """
        ratio       : 0.0 – 1.0
        sub_text    : mo ta ngan (vd '14 phut / 45 phut')
        badge_text  : nhan trang thai ('Binh thuong', 'Can chu y', ...)
        pct_override: hien thi khac 0–100% (vd '9/phut')
        """
        self._ratio = max(0.0, min(1.0, ratio))

        # Mau theo muc do
        if ratio < 0.60:
            col = self.COLOR_GOOD
            badge_bg = "#0a2a1a"
            badge_fg = GREEN
        elif ratio < 0.85:
            col = self.COLOR_WARN
            badge_bg = "#2a1f05"
            badge_fg = YELLOW
        else:
            col = self.COLOR_BAD
            badge_bg = "#2a0a0a"
            badge_fg = RED

        self._sub_lbl.config(text=sub_text)
        self._pct_lbl.config(
            text=pct_override if pct_override else f"{int(ratio*100)}%",
            fg=col
        )
        self._badge.config(text=badge_text, bg=badge_bg, fg=badge_fg)
        self._fill.config(bg=col)

        # Animate fill width
        if not self._animating:
            self._animate_fill()

    def _animate_fill(self):
        self._animating = True
        diff = self._ratio - self._anim_ratio
        if abs(diff) > 0.005:
            self._anim_ratio += diff * 0.15
        else:
            self._anim_ratio = self._ratio
            self._animating  = False

        track_w = self._fill.master.winfo_width()
        if track_w > 1:
            self._fill.place_configure(width=int(track_w * self._anim_ratio))

        if self._animating:
            self.after(16, self._animate_fill)


# ═══════════════════════════════════════════════════════════════════
# STEPPER WIDGET
# ═══════════════════════════════════════════════════════════════════
class StepperWidget(tk.Frame):
    """
    Stepper ngang 5 buoc kem duong noi giua.
    Trang thai: 'done' | 'active' | 'warn' | 'idle'
    """

    COLORS = {
        "done":   (GREEN,  BG2,   "✓"),
        "active": (BLUE,   BG2,   ""),
        "warn":   (YELLOW, BG2,   "!"),
        "error":  (RED,    BG2,   "✕"),
        "idle":   (BG3,    FG3,   ""),
    }

    def __init__(self, parent, steps: list, **kw):
        """steps = list of (label, state)"""
        super().__init__(parent, bg=BG2, **kw)
        self._step_dots  = []
        self._step_nums  = []
        self._line_frs   = []
        self._steps      = steps

        self._build(steps)

    def _build(self, steps):
        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x", padx=12, pady=8)

        for i, (label, state) in enumerate(steps):

            col, fg, sym = self.COLORS.get(state, self.COLORS["idle"])
            num_txt      = sym if sym else str(i + 1)

            # Step item
            item = tk.Frame(row, bg=BG2)
            item.pack(side="left", fill="x", expand=True)

            # Dot
            dot = tk.Label(item, text=num_txt,
                           font=FONT_TINY, fg=fg, bg=col,
                           width=3, height=1)
            dot.pack()
            self._step_dots.append(dot)

            # Label
            lbl = tk.Label(item, text=label,
                           font=FONT_TINY, fg=FG2, bg=BG2,
                           anchor="center")
            lbl.pack()
            self._step_nums.append(lbl)

            # Line giua cac buoc
            if i < len(steps) - 1:
                line_frame = tk.Frame(row, bg=BG3, height=2, width=20)
                line_frame.pack(side="left", pady=8)
                self._line_frs.append(line_frame)

    def set_step(self, active_idx: int):
        """Cap nhat buoc hien tai."""
        steps_ref = [
            ("done"   if i < active_idx
             else "active" if i == active_idx
             else "idle")
            for i in range(len(self._step_dots))
        ]
        for i, (dot, lbl) in enumerate(
            zip(self._step_dots, self._step_nums)
        ):
            st = steps_ref[i]
            col, fg, sym = self.COLORS.get(st, self.COLORS["idle"])
            label_i = dot.cget("text")
            num_txt = sym if sym else str(i + 1)
            dot.config(text=num_txt, fg=fg, bg=col)
            lbl.config(
                fg=FG if st == "active" else FG2
            )

        for i, line in enumerate(self._line_frs):
            line.config(bg=GREEN if i < active_idx else BG3)


# ═══════════════════════════════════════════════════════════════════
# SPARKLINE
# ═══════════════════════════════════════════════════════════════════
class Sparkline(tk.Frame):
    """Mini area-chart."""

    def __init__(self, parent, spark_w=200, spark_h=36,
                 color=TEAL, **kw):
        super().__init__(parent, bg=BG2,
                         width=spark_w, height=spark_h, **kw)
        self.pack_propagate(False)
        self._sw    = spark_w
        self._sh    = spark_h
        self._color = color
        self._data  = collections.deque(maxlen=80)

        self._canvas = tk.Canvas(self, width=spark_w, height=spark_h,
                                 bg=BG2, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

    def push(self, value: float):
        self._data.append(value)
        self._draw()

    def _draw(self):
        self._canvas.delete("all")
        if len(self._data) < 2:
            return
        data   = list(self._data)
        mn, mx = min(data), max(data)
        rng    = mx - mn if mx != mn else 1
        w, h   = self._sw, self._sh

        def yx(i, v):
            x = w * i / (len(data) - 1)
            y = h - h * 0.80 * (v - mn) / rng - h * 0.10
            return x, y

        pts  = [yx(i, v) for i, v in enumerate(data)]
        poly = list(pts) + [(w, h), (0, h)]
        flat = [c for p in poly for c in p]
        self._canvas.create_polygon(
            *flat, fill=self._color, outline="", stipple="gray25"
        )
        flat_pts = [c for p in pts for c in p]
        self._canvas.create_line(
            *flat_pts, fill=self._color, width=1.5, smooth=True
        )


# ═══════════════════════════════════════════════════════════════════
# STAT PILL (footer)
# ═══════════════════════════════════════════════════════════════════
class StatPill(tk.Frame):
    def __init__(self, parent, label: str, **kw):
        super().__init__(parent, bg=BG2, **kw)
        tk.Label(self, text=label, font=FONT_TINY,
                 fg=FG3, bg=BG2, anchor="center").pack(padx=12, pady=(5,0))
        self._val = tk.Label(self, text="--", font=FONT_STAT,
                             fg=TEAL, bg=BG2, anchor="center")
        self._val.pack(padx=12, pady=(0,5))

    def update(self, value: str, color: str = TEAL):
        self._val.config(text=value, fg=color)


# ═══════════════════════════════════════════════════════════════════
# WARNING BANNER
# ═══════════════════════════════════════════════════════════════════
class WarningBanner(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG0, **kw)
        self._text = tk.Label(self, text="", font=("Segoe UI", 11, "bold"),
                              fg=YELLOW, bg=BG0, anchor="center")
        self._text.pack(fill="x", pady=4)
        self._visible  = False
        self._flash_id = None

    def show(self, msg: str, color: str = YELLOW):
        self._text.config(text=msg, fg=color)
        if not self._visible:
            self.pack(fill="x")
            self._visible = True

    def hide(self):
        if self._visible:
            self.pack_forget()
            self._visible = False


# ═══════════════════════════════════════════════════════════════════
# MAIN DASHBOARD WINDOW
# ═══════════════════════════════════════════════════════════════════
class DashboardWindow:

    def __init__(self, data_queue: queue.Queue,
                 cmd_queue: queue.Queue,
                 settings_manager=None,
                 on_open_settings=None):

        self.q_data       = data_queue
        self.q_cmd        = cmd_queue
        self.settings     = settings_manager
        self._on_settings = on_open_settings

        self.root = tk.Tk()
        self.root.title("EyeGuard – Chong moi mat & met moi")
        self.root.configure(bg=BG0)
        self.root.minsize(960, 600)
        self.root.attributes("-fullscreen", True)
        self._is_fullscreen = True

        self._build_ui()
        self._bind_keys()
        self._poll()

    # ──────────────────────────────────────────────────────────────
    # BUILD UI
    # ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = self.root

        # ── HEADER ───────────────────────────────────────────────
        hdr = tk.Frame(root, bg=BG1, height=50)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="EyeGuard", font=FONT_TITLE,
                 fg=TEAL, bg=BG1).pack(side="left", padx=18, pady=6)

        self._header_status = tk.Label(
            hdr, text="Khoi dong...", font=FONT_HEADER,
            fg=FG2, bg=BG1
        )
        self._header_status.pack(side="left", padx=10)

        btn_kw = dict(
            bg=BG2, fg=FG2, relief="flat",
            font=FONT_BTN, padx=12, pady=5,
            cursor="hand2",
            activebackground=BG3, activeforeground=FG
        )
        tk.Button(hdr, text="Cai dat",
                  command=self._open_settings,
                  **btn_kw).pack(side="right", padx=6, pady=7)
        tk.Button(hdr, text="Reset",
                  command=self._cmd_reset,
                  **btn_kw).pack(side="right", padx=2, pady=7)
        tk.Button(hdr, text="Da nghi",
                  command=self._cmd_break,
                  **{**btn_kw, "fg": TEAL}).pack(side="right", padx=2, pady=7)
        tk.Button(hdr, text="X",
                  command=self._cmd_quit,
                  **{**btn_kw, "fg": RED}).pack(side="right", padx=6, pady=7)

        # ── WARNING BANNER ────────────────────────────────────────
        self._banner = WarningBanner(root)

        # ── FOOTER – pack TRUOC body ──────────────────────────────
        footer = tk.Frame(root, bg=BG1, height=62)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Frame(footer, bg=BG3, height=1).pack(fill="x")

        pills_frame = tk.Frame(footer, bg=BG1)
        pills_frame.pack(fill="both", expand=True, padx=6)

        self._pills = {}
        pill_defs = [
            ("session", "Phien lam viec"),
            ("sitting", "Ngoi lien tuc"),
            ("blink",   "Chop mat/phut"),
            ("breaks",  "So lan nghi"),
            ("posture", "Tu the tot"),
        ]
        for key, lbl in pill_defs:
            p = StatPill(pills_frame, lbl)
            p.pack(side="left", fill="x", expand=True, padx=3)
            self._pills[key] = p

        # ── BODY ─────────────────────────────────────────────────
        body = tk.Frame(root, bg=BG0)
        body.pack(fill="both", expand=True)

        # Right panel – pack truoc
        right = tk.Frame(body, bg=BG0, width=310)
        right.pack(side="right", fill="y", padx=(4, 6), pady=6)
        right.pack_propagate(False)

        # Camera panel
        cam_frame = tk.Frame(body, bg="#000000")
        cam_frame.pack(side="left", fill="both", expand=True,
                       padx=(6, 4), pady=6)

        self._cam_label = tk.Label(cam_frame, bg="#000000",
                                   cursor="none", relief="flat")
        self._cam_label.pack(fill="both", expand=True)

        self._no_cam = tk.Label(
            cam_frame, text="Dang khoi dong camera...",
            font=("Segoe UI", 13), fg=FG3, bg="#000000"
        )

        self._build_right_panel(right)

    # ──────────────────────────────────────────────────────────────
    # RIGHT PANEL – PROGRESS BAR LAYOUT
    # ──────────────────────────────────────────────────────────────
    def _build_right_panel(self, parent):

        # Scrollable canvas de hien thi du widget
        canvas = tk.Canvas(parent, bg=BG0, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG0)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _resize)

        def _scroll_region(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _scroll_region)

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"
        ))

        pad = {"padx": 6, "pady": 3}

        # ── 1. Section: Thoi gian & Trang thai ───────────────────
        self._sec_label(inner, "Thoi gian & Trang thai")

        self._pb_sitting = ProgressCard(
            inner, icon_text="S", title="Thoi gian ngoi lien tuc",
            icon_bg="#0a2a1a"
        )
        self._pb_sitting.pack(fill="x", **pad)

        self._pb_blink = ProgressCard(
            inner, icon_text="M", title="Tan suat chop mat",
            icon_bg="#2a1f05"
        )
        self._pb_blink.pack(fill="x", **pad)

        self._pb_posture = ProgressCard(
            inner, icon_text="T", title="Tu the co the",
            icon_bg="#2a0a0a"
        )
        self._pb_posture.pack(fill="x", **pad)

        # ── 2. Sparkline chop mat ─────────────────────────────────
        self._sec_label(inner, "Lich su chop mat (30 giac gan nhat)")

        spark_card = tk.Frame(inner, bg=BG2)
        spark_card.pack(fill="x", **pad)
        self._blink_spark = Sparkline(spark_card, spark_w=280,
                                      spark_h=40, color=TEAL)
        self._blink_spark.pack(padx=6, pady=6)

        # ── 3. Stepper tien trinh ─────────────────────────────────
        self._sec_label(inner, "Tien trinh buoi lam viec")

        stepper_card = tk.Frame(inner, bg=BG2)
        stepper_card.pack(fill="x", **pad)

        self._stepper = StepperWidget(
            stepper_card,
            steps=[
                ("Bat dau",    "done"),
                ("Calibrate",  "done"),
                ("Theo doi",   "active"),
                ("Nhac nghi",  "idle"),
                ("Hoan thanh", "idle"),
            ]
        )
        self._stepper.pack(fill="x")

        # ── 4. Mini stats grid ────────────────────────────────────
        self._sec_label(inner, "Chi so hien tai")

        grid = tk.Frame(inner, bg=BG0)
        grid.pack(fill="x", **pad)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        self._ms_conf   = self._mini_stat_card(grid, "Do chac chan ngoi", 0, 0)
        self._ms_ear    = self._mini_stat_card(grid, "EAR mat",           0, 1)
        self._ms_tsb    = self._mini_stat_card(grid, "Tu chop mat cuoi",  1, 0)
        self._ms_debt   = self._mini_stat_card(grid, "No nghi",           1, 1)

        # ── 5. Trang thai tu the chi tiet ────────────────────────
        self._sec_label(inner, "Chi tiet tu the")

        pose_card = tk.Frame(inner, bg=BG2)
        pose_card.pack(fill="x", **pad)

        self._posture_rows = {}
        for key, lbl in [
            ("spine",    "Cot song"),
            ("shoulder", "Vai"),
            ("head",     "Dau / co"),
            ("distance", "Khoang cach"),
        ]:
            row = tk.Frame(pose_card, bg=BG2)
            row.pack(fill="x", padx=10, pady=2)

            tk.Label(row, text=lbl, font=FONT_LABEL, fg=FG2, bg=BG2,
                     width=12, anchor="w").pack(side="left")
            dot = tk.Label(row, text="●", font=FONT_LABEL,
                           fg=FG3, bg=BG2)
            dot.pack(side="left", padx=4)
            val = tk.Label(row, text="--", font=FONT_MONO,
                           fg=FG2, bg=BG2)
            val.pack(side="left")
            self._posture_rows[key] = (dot, val)

        tk.Frame(pose_card, bg=BG0, height=6).pack()

    def _sec_label(self, parent, text: str):
        """Tieu de section nho."""
        tk.Label(
            parent, text=text.upper(),
            font=FONT_TINY, fg=FG3, bg=BG0,
            anchor="w"
        ).pack(fill="x", padx=8, pady=(8, 2))

    def _mini_stat_card(self, parent, label: str,
                        row: int, col: int) -> tk.Label:
        """Card chi so nho trong grid 2x2."""
        card = tk.Frame(parent, bg=BG2)
        card.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

        tk.Label(card, text=label, font=FONT_TINY,
                 fg=FG3, bg=BG2, anchor="w").pack(
            anchor="w", padx=8, pady=(6, 0)
        )
        val = tk.Label(card, text="--", font=FONT_MONO,
                       fg=TEAL, bg=BG2, anchor="w")
        val.pack(anchor="w", padx=8, pady=(0, 6))
        return val

    # ──────────────────────────────────────────────────────────────
    # POLLING
    # ──────────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                data = self.q_data.get_nowait()
                self._update_ui(data)
        except queue.Empty:
            pass
        self.root.after(33, self._poll)

    # ──────────────────────────────────────────────────────────────
    # UPDATE UI
    # ──────────────────────────────────────────────────────────────
    def _update_ui(self, d: dict):

        # ── Camera ────────────────────────────────────────────────
        raw = d.get("cam_raw")
        if raw is not None:
            try:
                from PIL import Image, ImageTk
                cw = self._cam_label.winfo_width()
                ch = self._cam_label.winfo_height()
                img = raw.resize((cw, ch), Image.LANCZOS) \
                      if cw > 4 and ch > 4 else raw
                tk_img = ImageTk.PhotoImage(img)
                self._cam_label.config(image=tk_img)
                self._cam_label.image = tk_img
            except Exception:
                pass
            self._no_cam.pack_forget()
        elif d.get("cam_img") is not None:
            self._cam_label.config(image=d["cam_img"])
            self._cam_label.image = d["cam_img"]
            self._no_cam.pack_forget()
        else:
            self._no_cam.pack(fill="both", expand=True)

        # ── Header status ─────────────────────────────────────────
        state = d.get("state", "unknown")
        state_txt = {
            "sitting":  "Dang ngoi",
            "standing": "Dang dung",
            "away":     "Khong co mat",
            "unknown":  "Dang nhan dien...",
        }.get(state, state)
        self._header_status.config(
            text=f"●  {state_txt}",
            fg=d.get("state_color", FG3)
        )

        # ── Progress bar: Ngoi ───────────────────────────────────
        sit_s    = d.get("sitting_duration", 0)
        sit_prog = d.get("sitting_progress", 0.0)
        goal_m   = d.get("sitting_goal_min", 45)
        mm, ss   = int(sit_s // 60), int(sit_s % 60)
        debt_m   = int(d.get("break_debt_sec", 0) // 60)

        sit_badge = (
            "Binh thuong" if sit_prog < 0.60
            else "Can chu y" if sit_prog < 0.85
            else "Hay nghi!"
        )
        self._pb_sitting.update_data(
            ratio        = sit_prog,
            sub_text     = f"{mm} phut {ss:02d}s  /  muc tieu {goal_m} phut"
                           + (f"  |  no: {debt_m}p" if debt_m > 0 else ""),
            badge_text   = sit_badge,
            pct_override = f"{mm:02d}:{ss:02d}",
        )

        # ── Progress bar: Chop mat ────────────────────────────────
        eye    = d.get("eye", {})
        br     = eye.get("blink_rate", 0)
        ear    = eye.get("ear", 0.0)
        tsb    = eye.get("time_since_blink", 0)

        # 15+ chop/phut = tot (100%), < 5 = 0%
        blink_ratio = min(1.0, max(0.0, br / 20.0))
        blink_badge = (
            "Tot" if br >= 15
            else "Can chu y" if br >= 10
            else "Qua it!"
        )
        self._pb_blink.update_data(
            ratio        = blink_ratio,
            sub_text     = f"{br:.0f} lan/phut  (khuyen nghi: 15–20)",
            badge_text   = blink_badge,
            pct_override = f"{br:.0f}/p",
        )
        self._blink_spark.push(br)

        # ── Progress bar: Tu the ─────────────────────────────────
        body        = d.get("body", {})
        posture     = d.get("posture", {})
        bad_pct     = body.get("bad_posture_pct", 0)
        pose_ratio  = bad_pct / 100.0   # bad_pct cao = tệ = bar do
        pose_badge  = (
            "Tot" if bad_pct < 10
            else "Can chinh" if bad_pct < 40
            else "Tu the xau!"
        )
        self._pb_posture.update_data(
            ratio        = pose_ratio,
            sub_text     = f"Tu the xau: {bad_pct:.0f}% thoi gian",
            badge_text   = pose_badge,
            pct_override = f"{bad_pct:.0f}%xau",
        )

        # ── Stepper ───────────────────────────────────────────────
        # 0=start, 1=calib, 2=tracking, 3=break_reminder, 4=done
        step = 2  # mac dinh dang theo doi
        if state == "unknown":
            step = 1
        elif sit_prog >= 1.0:
            step = 3
        self._stepper.set_step(step)

        # ── Mini stats ────────────────────────────────────────────
        conf = d.get("confidence", 0.0)
        self._ms_conf.config(
            text=f"{int(conf*100)}%",
            fg=GREEN if conf > 0.65 else (YELLOW if conf > 0.4 else FG3)
        )
        self._ms_ear.config(
            text=f"{ear:.2f}",
            fg=GREEN if ear > 0.25 else RED
        )
        tsb_col = GREEN if tsb < 30 else (YELLOW if tsb < 60 else RED)
        self._ms_tsb.config(text=f"{int(tsb)}s", fg=tsb_col)
        debt_s = d.get("break_debt_sec", 0)
        self._ms_debt.config(
            text=f"{int(debt_s//60)}p" if debt_s > 0 else "0p",
            fg=RED if debt_s > 300 else (YELLOW if debt_s > 0 else GREEN)
        )

        # ── Posture detail ────────────────────────────────────────
        spine_ok    = "spine_lean"    not in body.get("warnings", [])
        shoulder_ok = "shoulder_tilt" not in body.get("warnings", [])
        head_ok     = "forward_head"  not in body.get("warnings", [])
        close_ok    = "too_close"     not in posture.get("warnings", [])

        def _pr(key, ok, good, bad):
            dot, val = self._posture_rows[key]
            col = GREEN if ok else RED
            dot.config(fg=col)
            val.config(text=good if ok else bad, fg=col)

        _pr("spine",    spine_ok,    "Thang",       "Cong")
        _pr("shoulder", shoulder_ok, "Can bang",
            f"{body.get('shoulder_tilt',0):.0f}°")
        _pr("head",     head_ok,     "Binh thuong", "Do ve truoc")
        _pr("distance", close_ok,    "OK",          "Qua gan")

        # ── Footer pills ──────────────────────────────────────────
        stats  = d.get("stats", {})
        sess_s = stats.get("session_duration", 0)
        sess_h = int(sess_s // 3600)
        sess_m = int((sess_s % 3600) // 60)

        self._pills["session"].update(f"{sess_h}:{sess_m:02d}h", BLUE)
        self._pills["sitting"].update(
            f"{int(sit_s//60)}p",
            RED if sit_prog > 0.9 else (YELLOW if sit_prog > 0.65 else TEAL)
        )
        br_col = GREEN if br >= 15 else (YELLOW if br >= 10 else RED)
        self._pills["blink"].update(f"{br:.0f}", br_col)
        self._pills["breaks"].update(
            str(stats.get("break_count", 0)), BLUE
        )
        self._pills["posture"].update(
            f"{max(0, 100-bad_pct):.0f}%",
            GREEN if bad_pct < 20 else (YELLOW if bad_pct < 40 else RED)
        )

        # ── Warning banner ────────────────────────────────────────
        warns = d.get("ui_warnings", [])
        if warns:
            w       = warns[0]
            sev_col = {"high": RED, "medium": YELLOW, "low": BLUE}.get(
                w.get("severity", "medium"), YELLOW
            )
            self._banner.show(w.get("banner_text", ""), sev_col)
            self._banner.pack(fill="x")
        else:
            self._banner.hide()

    # ──────────────────────────────────────────────────────────────
    # COMMANDS
    # ──────────────────────────────────────────────────────────────
    def _cmd_break(self):
        self.q_cmd.put({"cmd": "break"})

    def _cmd_reset(self):
        self.q_cmd.put({"cmd": "reset"})

    def _cmd_quit(self):
        self.q_cmd.put({"cmd": "quit"})
        self.root.after(300, self.root.destroy)

    def _open_settings(self):
        if self._on_settings:
            self._on_settings()

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self._toggle_fullscreen())
        self.root.bind("<F11>",    lambda e: self._toggle_fullscreen())
        self.root.bind("q",        lambda e: self._cmd_quit())
        self.root.bind("Q",        lambda e: self._cmd_quit())
        self.root.bind("r",        lambda e: self._cmd_reset())
        self.root.bind("b",        lambda e: self._cmd_break())
        self.root.bind("c",        lambda e: self._open_settings())

    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        self.root.attributes("-fullscreen", self._is_fullscreen)

    def run(self):
        self.root.mainloop()


# ── Standalone test ───────────────────────────────────────────────
if __name__ == "__main__":
    import queue, random

    q_data = queue.Queue()
    q_cmd  = queue.Queue()

    def _feed():
        t = 0
        while True:
            t += 1
            q_data.put({
                "state":            "sitting",
                "state_color":      "#00d4aa",
                "confidence":       0.7 + 0.2 * math.sin(t / 20),
                "sitting_duration": t * 3,
                "sitting_progress": min(1.0, t * 3 / 2700),
                "sitting_goal_min": 45,
                "break_debt_sec":   max(0, t * 3 - 2700),
                "eye": {
                    "blink_rate":      14 + random.uniform(-4, 4),
                    "ear":             0.28 + random.uniform(-0.05, 0.05),
                    "time_since_blink": t % 50,
                },
                "body": {
                    "warnings":        [],
                    "shoulder_tilt":   random.uniform(-5, 5),
                    "bad_posture_pct": max(0, 8 + random.uniform(-3, 3)),
                },
                "posture": {"warnings": []},
                "stats": {
                    "session_duration": t * 3 + 900,
                    "break_count":      1,
                },
                "ui_warnings": (
                    [{"severity": "high",
                      "banner_text": "Ngoi 45 phut! Hay dung day di lai."}]
                    if t > 90 else []
                ),
            })
            time.sleep(0.1)

    threading.Thread(target=_feed, daemon=True).start()
    win = DashboardWindow(q_data, q_cmd)
    win.run()