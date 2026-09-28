"""
client/voice_call.py - Voice Call 2 chiều có âm thanh thực sự
Dùng sounddevice (capture/playback) + UDP socket (truyền audio)

Kiến trúc:
  - Mỗi bên lắng nghe UDP port riêng (tự chọn port trống)
  - Khi cuộc gọi được chấp nhận, 2 bên trao đổi UDP port qua tín hiệu
    VOICE_CALL_ACCEPTED (server relay port info)
  - AudioEngine: thread capture mic → gửi UDP chunks → thread nhận UDP → phát loa
"""

import tkinter as tk
from tkinter import messagebox
import time
import math
import threading
import socket
import struct
import numpy as np

try:
    import sounddevice as sd
    _AUDIO_OK = True
except Exception:
    _AUDIO_OK = False

# ── Hằng số audio ────────────────────────────────────────────
SAMPLE_RATE  = 16000   # Hz — đủ nghe rõ tiếng người, nhẹ bandwidth
CHANNELS     = 1
CHUNK_FRAMES = 640     # 40ms mỗi chunk (640 / 16000)
DTYPE        = "int16"
UDP_BUF      = 8192


# ─────────────────────────────────────────────────────────────
#  AudioEngine — thu mic, gửi UDP, nhận UDP, phát loa
# ─────────────────────────────────────────────────────────────
class AudioEngine:
    """
    Quản lý toàn bộ luồng audio 2 chiều cho 1 cuộc gọi.
    Dùng UDP để truyền raw PCM int16 frames.
    """

    def __init__(self):
        self._sock        = None   # UDP socket nhận
        self._remote_addr = None   # (ip, port) của đối phương
        self._running     = False
        self._muted       = False
        self._local_port  = 0
        self._send_sock   = None

        # Playback queue nhỏ để tránh buffer underrun
        import queue
        self._play_q = queue.Queue(maxsize=20)
        self._volume = 1.0        # 0.0 – 2.0

    # ── Khởi động ─────────────────────────────────────────────
    def start(self, remote_ip: str, remote_port: int) -> int:
        """
        Bắt đầu audio engine.
        Trả về local_port để trao cho đối phương.
        """
        if not _AUDIO_OK:
            return 0

        self._remote_addr = (remote_ip, remote_port)
        self._running     = True

        # Tạo UDP socket nhận
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self._sock.bind(("0.0.0.0", 0))   # port=0 → OS tự chọn
        self._sock.settimeout(0.5)
        self._local_port = self._sock.getsockname()[1]

        # Socket gửi riêng
        self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Thread nhận + phát loa
        threading.Thread(target=self._recv_loop,    daemon=True).start()
        threading.Thread(target=self._playback_loop, daemon=True).start()
        # Thread capture mic + gửi
        threading.Thread(target=self._capture_loop,  daemon=True).start()

        return self._local_port

    def stop(self):
        self._running = False
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        try:
            if self._send_sock:
                self._send_sock.close()
        except Exception:
            pass

    def set_mute(self, muted: bool):
        self._muted = muted

    def set_volume(self, v: float):
        self._volume = max(0.0, min(2.0, v))

    @property
    def local_port(self) -> int:
        return self._local_port

    # ── Capture mic → gửi UDP ─────────────────────────────────
    def _capture_loop(self):
        if not _AUDIO_OK:
            return
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE,
                                channels=CHANNELS,
                                dtype=DTYPE,
                                blocksize=CHUNK_FRAMES) as stream:
                while self._running:
                    frames, _ = stream.read(CHUNK_FRAMES)
                    if self._muted:
                        continue
                    # Chỉ gửi khi đã biết remote port hợp lệ
                    if self._remote_addr is None or self._remote_addr[1] == 0:
                        continue
                    raw = frames.tobytes()
                    ts  = struct.pack("!I", int(time.time() * 1000) & 0xFFFFFFFF)
                    try:
                        self._send_sock.sendto(ts + raw, self._remote_addr)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[AudioEngine] capture error: {e}")

    # ── Nhận UDP ──────────────────────────────────────────────
    def _recv_loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(UDP_BUF)
                if len(data) <= 4:
                    continue
                raw = data[4:]    # bỏ 4 bytes header timestamp
                arr = np.frombuffer(raw, dtype=np.int16).copy()
                # Volume scaling
                if self._volume != 1.0:
                    arr = np.clip(arr.astype(np.float32) * self._volume,
                                  -32768, 32767).astype(np.int16)
                # Đưa vào playback queue, bỏ nếu đầy (tránh lag)
                if not self._play_q.full():
                    self._play_q.put(arr)
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue
                break

    # ── Phát loa từ queue ─────────────────────────────────────
    def _playback_loop(self):
        if not _AUDIO_OK:
            return
        try:
            def callback(outdata, frames, time_info, status):
                try:
                    arr = self._play_q.get_nowait()
                    # Đảm bảo đủ frames
                    if len(arr) < frames:
                        arr = np.pad(arr, (0, frames - len(arr)))
                    outdata[:] = arr[:frames].reshape(-1, 1)
                except Exception:
                    outdata[:] = np.zeros((frames, 1), dtype=DTYPE)

            with sd.OutputStream(samplerate=SAMPLE_RATE,
                                 channels=CHANNELS,
                                 dtype=DTYPE,
                                 blocksize=CHUNK_FRAMES,
                                 callback=callback):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[AudioEngine] playback error: {e}")


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
#  IncomingCallDialog
# ─────────────────────────────────────────────────────────────
class IncomingCallDialog(tk.Toplevel):
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

    def _build_ui(self):
        self.lbl_icon = tk.Label(
            self, text="📞", font=("Segoe UI Emoji", 52),
            fg="#38BDF8", bg=self.BG
        )
        self.lbl_icon.pack(pady=(22, 4))

        tk.Label(self, text="CÓ CUỘC GỌI ĐẾN",
                 font=("Segoe UI", 11, "bold"),
                 fg="#F1F5F9", bg=self.BG).pack()

        tk.Label(self, text=self.caller_name,
                 font=("Segoe UI", 14, "bold"),
                 fg="#38BDF8", bg=self.BG).pack(pady=(6, 0))

        if self.caller_username:
            tk.Label(self, text=f"@{self.caller_username}",
                     font=("Segoe UI", 9), fg="#64748B",
                     bg=self.BG).pack()

        self.lbl_status = tk.Label(
            self, text="🔔  Đang đổ chuông...",
            font=("Segoe UI", 9, "italic"), fg="#94A3B8", bg=self.BG
        )
        self.lbl_status.pack(pady=(8, 12))

        btn_frame = tk.Frame(self, bg=self.BG)
        btn_frame.pack(fill=tk.X, padx=36, pady=4)

        tk.Button(btn_frame, text="✅  Nhận",
                  bg="#10B981", fg="#FFFFFF",
                  font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
                  pady=9, cursor="hand2", activebackground="#059669",
                  command=self._on_accept
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Button(btn_frame, text="❌  Từ chối",
                  bg="#EF4444", fg="#FFFFFF",
                  font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
                  pady=9, cursor="hand2", activebackground="#DC2626",
                  command=self._on_reject
                  ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0))

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

    def _on_accept(self):
        if self._answered:
            return
        self._answered = True
        self._ringing  = False
        self.client.voice_call_response(self.call_id, accept=True)
        parent = self.master
        self.destroy()
        ActiveCallDialog(parent, self.client, self.call_id,
                         self.caller_name, self.caller_username,
                         is_caller=False)

    def _on_reject(self):
        if self._answered:
            return
        self._answered = True
        self._ringing  = False
        self.client.voice_call_response(self.call_id, accept=False)
        self.destroy()


# ─────────────────────────────────────────────────────────────
#  CallingDialog — phía người GỌI chờ bắt máy
# ─────────────────────────────────────────────────────────────
class CallingDialog(tk.Toplevel):
    BG = "#0F172A"

    def __init__(self, parent, client, call_id: str,
                 callee_name: str, callee_username: str = ""):
        super().__init__(parent)
        self.client          = client
        self.call_id         = call_id
        self.callee_name     = callee_name
        self.callee_username = callee_username

        self.title("📞  Đang gọi...")
        self.geometry("380x270")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._waiting = True
        self._dot_cnt = 0

        self._build_ui()
        self._tick_dots()
        self.client.register_voice_call_callback(self._on_voice_event)

    def _build_ui(self):
        self.lbl_icon = tk.Label(
            self, text="📲", font=("Segoe UI Emoji", 48),
            fg="#38BDF8", bg=self.BG
        )
        self.lbl_icon.pack(pady=(22, 4))

        tk.Label(self, text="Đang gọi tới",
                 font=("Segoe UI", 10), fg="#94A3B8", bg=self.BG).pack()
        tk.Label(self, text=self.callee_name,
                 font=("Segoe UI", 14, "bold"), fg="#F1F5F9",
                 bg=self.BG).pack(pady=(4, 0))
        if self.callee_username:
            tk.Label(self, text=f"@{self.callee_username}",
                     font=("Segoe UI", 9), fg="#64748B",
                     bg=self.BG).pack()

        self.lbl_dots = tk.Label(
            self, text="Đang đổ chuông...",
            font=("Segoe UI", 9, "italic"), fg="#94A3B8", bg=self.BG
        )
        self.lbl_dots.pack(pady=(10, 14))

        tk.Button(self, text="📵  Huỷ cuộc gọi",
                  bg="#EF4444", fg="#FFFFFF",
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                  pady=8, padx=20, cursor="hand2",
                  activebackground="#DC2626",
                  command=self._on_cancel).pack()

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
                # Lấy UDP port của đối phương (nếu server relay)
                remote_udp = msg.get("remote_udp_port", 0)
                parent = self.master
                try:
                    self.destroy()
                except tk.TclError:
                    pass
                ActiveCallDialog(parent, self.client, self.call_id,
                                 self.callee_name, self.callee_username,
                                 is_caller=True,
                                 remote_udp_port=remote_udp)

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
#  ActiveCallDialog — cửa sổ đàm thoại có âm thanh thực
# ─────────────────────────────────────────────────────────────
class ActiveCallDialog(tk.Toplevel):
    BG       = "#0F172A"
    BG_PANEL = "#1E293B"

    def __init__(self, parent, client, call_id: str,
                 remote_name: str, remote_username: str = "",
                 is_caller: bool = False,
                 remote_udp_port: int = 0):
        super().__init__(parent)
        self.client           = client
        self.call_id          = call_id
        self.remote_name      = remote_name
        self.remote_username  = remote_username
        self.is_caller        = is_caller
        self._remote_udp_port = remote_udp_port   # port UDP phía đối phương

        label = "Đang gọi cho" if is_caller else "Đang thoại với"
        self.title(f"📞  {label}: {remote_name}")
        self.geometry("460x420")
        self.resizable(False, False)
        self.configure(bg=self.BG)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_end_call)

        self._start_time = time.time()
        self._active     = True
        self._muted      = False
        self._wave_phase = 0
        self._sig_level  = 0.0   # amplitude từ mic/playback để animate

        # Audio engine
        self._audio = AudioEngine() if _AUDIO_OK else None
        self._local_udp_port = 0

        self._build_ui()
        self._start_audio()
        self._tick_timer()
        self._tick_wave()

        # Lắng nghe ENDED từ đối phương
        self.client.register_voice_call_callback(self._on_voice_event)

    # ── Khởi động audio ──────────────────────────────────────
    def _start_audio(self):
        if not self._audio:
            self._set_audio_status("⚠️  sounddevice không khả dụng", "#F59E0B")
            return

        # Lấy IP server (dùng làm IP đối phương — cùng LAN)
        remote_ip = getattr(self.client, "host", "127.0.0.1")

        if self._remote_udp_port > 0:
            # Phía người gọi: đã biết port của callee
            self._local_udp_port = self._audio.start(remote_ip, self._remote_udp_port)
            self._set_audio_status("🎙️  Âm thanh đang hoạt động", "#10B981")
        else:
            # Phía người nhận: khởi động engine trước, port đối phương chưa biết
            # → dùng port 0 tạm, sẽ cập nhật sau khi nhận VOICE_PORT event
            self._local_udp_port = self._audio.start(remote_ip, 0)
            self._set_audio_status("🎙️  Âm thanh đang hoạt động", "#10B981")

            # Gửi local UDP port tới đối phương qua signaling
            if self._local_udp_port:
                self._send_udp_port_signal()

        # Cập nhật label port
        try:
            self.lbl_port.config(
                text=f"UDP local port: {self._local_udp_port}"
            )
        except Exception:
            pass

    def _send_udp_port_signal(self):
        """Gửi local UDP port tới đối phương qua kênh signaling TCP."""
        from common.constants import ACTION_VOICE_CALL_ANY
        try:
            self.client.send_request({
                "action":         "VOICE_UDP_PORT",
                "call_id":        self.call_id,
                "udp_port":       self._local_udp_port,
            })
        except Exception:
            pass

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        tk.Frame(self, bg="#0EA5E9", height=5).pack(fill=tk.X)

        status_bar = tk.Frame(self, bg=self.BG_PANEL, pady=8)
        status_bar.pack(fill=tk.X)
        self.lbl_conn = tk.Label(
            status_bar, text="🟢  ĐANG KẾT NỐI",
            font=("Segoe UI", 9, "bold"), fg="#10B981", bg=self.BG_PANEL
        )
        self.lbl_conn.pack(side=tk.LEFT, padx=12)

        self.lbl_audio_status = tk.Label(
            status_bar, text="⏳  Đang khởi động audio...",
            font=("Segoe UI", 8), fg="#94A3B8", bg=self.BG_PANEL
        )
        self.lbl_audio_status.pack(side=tk.RIGHT, padx=12)

        # Avatar + tên + timer
        center = tk.Frame(self, bg=self.BG)
        center.pack(fill=tk.X, pady=(10, 0))

        tk.Label(center, text="👤", font=("Segoe UI Emoji", 34),
                 fg="#38BDF8", bg=self.BG).pack()
        tk.Label(center, text=self.remote_name,
                 font=("Segoe UI", 14, "bold"), fg="#F1F5F9",
                 bg=self.BG).pack(pady=(4, 0))
        if self.remote_username:
            tk.Label(center, text=f"@{self.remote_username}",
                     font=("Segoe UI", 9), fg="#64748B",
                     bg=self.BG).pack()

        self.lbl_timer = tk.Label(
            center, text="00:00",
            font=("Consolas", 20, "bold"), fg="#38BDF8", bg=self.BG
        )
        self.lbl_timer.pack(pady=(5, 0))

        # Debug port label (nhỏ, mờ)
        self.lbl_port = tk.Label(
            center, text="",
            font=("Segoe UI", 7), fg="#334155", bg=self.BG
        )
        self.lbl_port.pack()

        # Waveform
        self.canvas = tk.Canvas(
            self, width=420, height=56,
            bg=self.BG_PANEL, highlightthickness=0
        )
        self.canvas.pack(pady=8, padx=20)

        # Volume slider
        vol_row = tk.Frame(self, bg=self.BG)
        vol_row.pack(fill=tk.X, padx=30, pady=(0, 4))
        tk.Label(vol_row, text="🔊", font=("Segoe UI", 10),
                 fg="#94A3B8", bg=self.BG).pack(side=tk.LEFT)
        self.vol_slider = tk.Scale(
            vol_row, from_=0, to=200, orient=tk.HORIZONTAL,
            bg=self.BG, fg="#94A3B8", highlightthickness=0,
            troughcolor="#334155", activebackground="#38BDF8",
            command=self._on_volume_change
        )
        self.vol_slider.set(100)
        self.vol_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        tk.Label(vol_row, text="200%", font=("Segoe UI", 8),
                 fg="#64748B", bg=self.BG).pack(side=tk.RIGHT)

        # Nút điều khiển
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

    def _set_audio_status(self, text: str, color: str):
        try:
            self.lbl_audio_status.config(text=text, fg=color)
        except Exception:
            pass

    # ── Volume ───────────────────────────────────────────────
    def _on_volume_change(self, val):
        if self._audio:
            self._audio.set_volume(float(val) / 100.0)

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

        w, h  = 420, 56
        mid   = h / 2
        amp   = 2 if self._muted else max(4, min(20, self._sig_level * 20))
        color = "#475569" if self._muted else "#38BDF8"

        # Lấy amplitude từ playback queue nếu có
        if self._audio and not self._audio._play_q.empty():
            try:
                arr = self._audio._play_q.queue[0]
                self._sig_level = float(np.abs(arr).mean()) / 32768.0
            except Exception:
                pass

        pts = []
        for x in range(0, w, 4):
            y = mid + math.sin((x + self._wave_phase) * 0.10) * amp \
                    * (0.5 + 0.5 * math.sin(self._wave_phase * 0.03))
            pts += [x, y]
        if len(pts) >= 4:
            self.canvas.create_line(pts, fill=color, width=2, smooth=True)

        self._wave_phase += 6
        self.after(60, self._tick_wave)

    # ── Mute ─────────────────────────────────────────────────
    def _toggle_mute(self):
        self._muted = not self._muted
        if self._audio:
            self._audio.set_mute(self._muted)
        if self._muted:
            self.btn_mute.config(text="🔇  Mic TẮT", bg="#64748B")
        else:
            self.btn_mute.config(text="🎤  Mic BẬT", bg="#334155")

    # ── Kết thúc ─────────────────────────────────────────────
    def _on_end_call(self):
        if not self._active:
            return
        self._active = False
        if self._audio:
            self._audio.stop()
        self.client.voice_call_end(self.call_id)
        try:
            self.destroy()
        except tk.TclError:
            pass

    # ── Nhận sự kiện từ đối phương ───────────────────────────
    def _on_voice_event(self, evt: str, msg: dict):
        if msg.get("call_id") != self.call_id:
            return

        def _handle():
            if evt == "VOICE_CALL_ENDED":
                if not self._active:
                    return
                self._active = False
                if self._audio:
                    self._audio.stop()
                try:
                    messagebox.showinfo(
                        "Cuộc gọi kết thúc",
                        f"{self.remote_name} đã kết thúc cuộc gọi.",
                        parent=self
                    )
                    self.destroy()
                except tk.TclError:
                    pass

            elif evt == "VOICE_UDP_PORT":
                # Nhận UDP port của đối phương → cập nhật remote addr
                port = msg.get("udp_port", 0)
                if port and self._audio:
                    remote_ip = getattr(self.client, "host", "127.0.0.1")
                    self._audio._remote_addr = (remote_ip, port)
                    self._set_audio_status("🎙️  Âm thanh đang hoạt động", "#10B981")

        try:
            self.after(0, _handle)
        except tk.TclError:
            pass
