"""
client/voice_call.py - Giao diện Voice Call 2 chiều giữa mọi client
Hỗ trợ: Đổ chuông, Chấp nhận/Từ chối, Kết thúc từ cả 2 phía, Waveform animation
"""

import tkinter as tk
from tkinter import messagebox
import time
import math
import threading


# ─────────────────────────────────────────────────────────────
#  Tiện ích giao diện chung
# ─────────────────────────────────────────────────────────────
def _role_badge_color(role: str) -> str:
    return {
        "Admin":    "#7C3AED",
        "Staff":    "#0284C7",
        "Driver":   "#059669",
        "Customer": "#475569",
    }.get(role, "#334155")


# ─────────────────────────────────────────────────────────────
#  IncomingCallDialog — hiển thị khi có cuộc gọi đến
# ─────────────────────────────────────────────────────────────
class IncomingCallDialog(tk.Toplevel):
    """Hộp thoại đổ chuông khi có cuộc gọi đến từ bất kỳ user nào."""

    BG = "#0F172A"
    RING_COLORS = ["#38BDF8", "#10B981", "#F59E0B", "#E879F9"]

    def __init__(self, parent, client, call_id: str,
                 caller_name: str, caller_username: str = ""):
        super().__init__(parent)
        self.client          = client
        self.call_id         = call_id
        self.caller_name     = caller_name
        self.caller_username = caller_username

        self.title("📞  Cuộc gọi đến")
        self.geometry("400x320")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.attributes("-topmost", True)
        self.grab_set()

        self._ring_phase = 0
        self._ringing    = True
        self._answered   = False

        self._build_ui()
        self._tick_ring()

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        # Icon nhấp nháy
        self.lbl_icon = tk.Label(
            self, text="📞", font=("Segoe UI Emoji", 52),
            fg="#38BDF8", bg=self.BG
        )
        self.lbl_icon.pack(pady=(22, 4))

        tk.Label(
            self, text="CÓ CUỘC GỌI ĐẾN",
            font=("Segoe UI", 11, "bold"), fg="#F1F5F9", bg=self.BG
        ).pack()

        # Tên + username người gọi
        tk.Label(
            self, text=self.caller_name,
            font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg=self.BG
        ).pack(pady=(6, 0))

        if self.caller_username:
            tk.Label(
                self, text=f"@{self.caller_username}",
                font=("Segoe UI", 9), fg="#64748B", bg=self.BG
            ).pack()

        # Trạng thái đang đổ chuông
        self.lbl_status = tk.Label(
            self, text="🔔  Đang đổ chuông...",
            font=("Segoe UI", 9, "italic"), fg="#94A3B8", bg=self.BG
        )
        self.lbl_status.pack(pady=(8, 12))

        # Nút Nhận / Từ chối
        btn_frame = tk.Frame(self, bg=self.BG)
        btn_frame.pack(fill=tk.X, padx=36, pady=4)

        tk.Button(
            btn_frame, text="✅  Nhận", bg="#10B981", fg="#FFFFFF",
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2", activebackground="#059669",
            command=self._on_accept
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Button(
            btn_frame, text="❌  Từ chối", bg="#EF4444", fg="#FFFFFF",
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2", activebackground="#DC2626",
            command=self._on_reject
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0))

    # ── Animation ───────────────────────────────────────────
    def _tick_ring(self):
        if not self._ringing:
            return
        color = self.RING_COLORS[self._ring_phase % len(self.RING_COLORS)]
        try:
            self.lbl_icon.config(fg=color)
        except tk.TclError:
            return
        self._ring_phase += 1
        self.after(420, self._tick_ring)

    # ── Handlers ────────────────────────────────────────────
    def _on_accept(self):
        if self._answered:
            return
        self._answered = True
        self._ringing  = False
        self.client.voice_call_response(self.call_id, accept=True)
        parent = self.master
        self.destroy()
        ActiveCallDialog(parent, self.client, self.call_id,
                         self.caller_name, self.caller_username, is_caller=False)

    def _on_reject(self):
        if self._answered:
            return
        self._answered = True
        self._ringing  = False
        self.client.voice_call_response(self.call_id, accept=False)
        self.destroy()


# ─────────────────────────────────────────────────────────────
#  CallingDialog — hiển thị phía người GỌI khi đang chờ bắt máy
# ─────────────────────────────────────────────────────────────
class CallingDialog(tk.Toplevel):
    """Cửa sổ chờ đối phương bắt máy (phía người gọi)."""

    BG = "#0F172A"

    def __init__(self, parent, client, call_id: str, callee_name: str, callee_username: str = ""):
        super().__init__(parent)
        self.client           = client
        self.call_id          = call_id
        self.callee_name      = callee_name
        self.callee_username  = callee_username

        self.title("📞  Đang gọi...")
        self.geometry("380x270")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._waiting  = True
        self._dot_cnt  = 0

        self._build_ui()
        self._tick_dots()

        # Lắng nghe ACCEPTED / REJECTED từ server
        self.client.register_voice_call_callback(self._on_voice_event)

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        self.lbl_icon = tk.Label(
            self, text="📲", font=("Segoe UI Emoji", 48),
            fg="#38BDF8", bg=self.BG
        )
        self.lbl_icon.pack(pady=(22, 4))

        tk.Label(
            self, text="Đang gọi tới",
            font=("Segoe UI", 10), fg="#94A3B8", bg=self.BG
        ).pack()

        tk.Label(
            self, text=self.callee_name,
            font=("Segoe UI", 14, "bold"), fg="#F1F5F9", bg=self.BG
        ).pack(pady=(4, 0))

        if self.callee_username:
            tk.Label(
                self, text=f"@{self.callee_username}",
                font=("Segoe UI", 9), fg="#64748B", bg=self.BG
            ).pack()

        self.lbl_dots = tk.Label(
            self, text="Đang đổ chuông...",
            font=("Segoe UI", 9, "italic"), fg="#94A3B8", bg=self.BG
        )
        self.lbl_dots.pack(pady=(10, 14))

        tk.Button(
            self, text="📵  Huỷ cuộc gọi", bg="#EF4444", fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=8, padx=20, cursor="hand2", activebackground="#DC2626",
            command=self._on_cancel
        ).pack()

    # ── Animation ───────────────────────────────────────────
    def _tick_dots(self):
        if not self._waiting:
            return
        dots = "." * (self._dot_cnt % 4)
        try:
            self.lbl_dots.config(text=f"Đang đổ chuông{dots}")
        except tk.TclError:
            return
        self._dot_cnt += 1
        self.after(500, self._tick_dots)

    # ── Handlers ────────────────────────────────────────────
    def _on_cancel(self):
        if not self._waiting:
            return
        self._waiting = False
        self.client.voice_call_end(self.call_id)
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _on_voice_event(self, evt: str, msg: dict):
        if msg.get("call_id") != self.call_id:
            return

        def _handle():
            if not self._waiting:
                return
            self._waiting = False

            if evt == "VOICE_CALL_ACCEPTED":
                parent = self.master
                try:
                    self.destroy()
                except tk.TclError:
                    pass
                ActiveCallDialog(parent, self.client, self.call_id,
                                 self.callee_name, self.callee_username, is_caller=True)

            elif evt == "VOICE_CALL_REJECTED":
                try:
                    messagebox.showinfo(
                        "Cuộc gọi bị từ chối",
                        f"{self.callee_name} đã từ chối cuộc gọi.",
                        parent=self
                    )
                    self.destroy()
                except tk.TclError:
                    pass

            elif evt == "VOICE_CALL_ENDED":
                try:
                    self.destroy()
                except tk.TclError:
                    pass

        try:
            self.after(0, _handle)
        except tk.TclError:
            pass


# ─────────────────────────────────────────────────────────────
#  ActiveCallDialog — cửa sổ đang thoại (cả 2 phía)
# ─────────────────────────────────────────────────────────────
class ActiveCallDialog(tk.Toplevel):
    """Cửa sổ đàm thoại — dùng chung cho cả người gọi lẫn người nhận."""

    BG       = "#0F172A"
    BG_PANEL = "#1E293B"

    def __init__(self, parent, client, call_id: str,
                 remote_name: str, remote_username: str = "",
                 is_caller: bool = False):
        super().__init__(parent)
        self.client          = client
        self.call_id         = call_id
        self.remote_name     = remote_name
        self.remote_username = remote_username
        self.is_caller       = is_caller

        label = "Đang gọi cho" if is_caller else "Đang thoại với"
        self.title(f"📞  {label}: {remote_name}")
        self.geometry("440x380")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_end_call)

        self._start_time = time.time()
        self._active     = True
        self._muted      = False
        self._wave_phase = 0

        self._build_ui()
        self._tick_timer()
        self._tick_wave()

        # Đăng ký callback nhận ENDED từ đối phương
        self.client.register_voice_call_callback(self._on_voice_event)

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──────────────────────────────────────────
        hdr = tk.Frame(self, bg="#0EA5E9", height=6)
        hdr.pack(fill=tk.X)

        status_bar = tk.Frame(self, bg=self.BG_PANEL, pady=10)
        status_bar.pack(fill=tk.X)

        tk.Label(
            status_bar, text="🟢  ĐANG KẾT NỐI",
            font=("Segoe UI", 9, "bold"), fg="#10B981", bg=self.BG_PANEL
        ).pack()

        # ── Avatar & tên ────────────────────────────────────
        center = tk.Frame(self, bg=self.BG)
        center.pack(fill=tk.X, pady=(12, 0))

        avatar = tk.Label(
            center, text="👤", font=("Segoe UI Emoji", 36),
            fg="#38BDF8", bg=self.BG
        )
        avatar.pack()

        tk.Label(
            center, text=self.remote_name,
            font=("Segoe UI", 14, "bold"), fg="#F1F5F9", bg=self.BG
        ).pack(pady=(4, 0))

        if self.remote_username:
            tk.Label(
                center, text=f"@{self.remote_username}",
                font=("Segoe UI", 9), fg="#64748B", bg=self.BG
            ).pack()

        self.lbl_timer = tk.Label(
            center, text="00:00",
            font=("Consolas", 20, "bold"), fg="#38BDF8", bg=self.BG
        )
        self.lbl_timer.pack(pady=(6, 0))

        # ── Waveform canvas ──────────────────────────────────
        self.canvas = tk.Canvas(
            self, width=400, height=64,
            bg=self.BG_PANEL, highlightthickness=0
        )
        self.canvas.pack(pady=10, padx=20)

        # ── Nút điều khiển ───────────────────────────────────
        ctrl = tk.Frame(self, bg=self.BG)
        ctrl.pack(fill=tk.X, padx=30, pady=6)

        self.btn_mute = tk.Button(
            ctrl, text="🎤  Mic BẬT",
            bg="#334155", fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
            pady=8, padx=14, cursor="hand2",
            activebackground="#475569",
            command=self._toggle_mute
        )
        self.btn_mute.pack(side=tk.LEFT)

        tk.Button(
            ctrl, text="🔴  Kết thúc",
            bg="#EF4444", fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
            pady=8, padx=14, cursor="hand2",
            activebackground="#DC2626",
            command=self._on_end_call
        ).pack(side=tk.RIGHT)

    # ── Timer ────────────────────────────────────────────────
    def _tick_timer(self):
        if not self._active:
            return
        elapsed = int(time.time() - self._start_time)
        m, s = divmod(elapsed, 60)
        try:
            self.lbl_timer.config(text=f"{m:02d}:{s:02d}")
        except tk.TclError:
            return
        self.after(1000, self._tick_timer)

    # ── Waveform ─────────────────────────────────────────────
    def _tick_wave(self):
        if not self._active:
            return
        try:
            self.canvas.delete("all")
        except tk.TclError:
            return

        w, h = 400, 64
        mid   = h / 2
        amp   = 3 if self._muted else 16
        color = "#475569" if self._muted else "#38BDF8"
        pts   = []
        for x in range(0, w, 5):
            y = mid + math.sin((x + self._wave_phase) * 0.09) * amp \
                    * (0.6 + 0.4 * math.cos(self._wave_phase * 0.04))
            pts += [x, y]
        if len(pts) >= 4:
            self.canvas.create_line(pts, fill=color, width=2, smooth=True)

        self._wave_phase += 8
        self.after(60, self._tick_wave)

    # ── Mute ─────────────────────────────────────────────────
    def _toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            self.btn_mute.config(text="🔇  Mic TẮT", bg="#64748B")
        else:
            self.btn_mute.config(text="🎤  Mic BẬT", bg="#334155")

    # ── Kết thúc ─────────────────────────────────────────────
    def _on_end_call(self):
        if not self._active:
            return
        self._active = False
        self.client.voice_call_end(self.call_id)
        try:
            self.destroy()
        except tk.TclError:
            pass

    # ── Nhận sự kiện từ đối phương ───────────────────────────
    def _on_voice_event(self, evt: str, msg: dict):
        if msg.get("call_id") != self.call_id:
            return
        if evt == "VOICE_CALL_ENDED":
            def _close():
                if not self._active:
                    return
                self._active = False
                try:
                    messagebox.showinfo(
                        "Cuộc gọi kết thúc",
                        f"{self.remote_name} đã kết thúc cuộc gọi.",
                        parent=self
                    )
                    self.destroy()
                except tk.TclError:
                    pass
            try:
                self.after(0, _close)
            except tk.TclError:
                pass
