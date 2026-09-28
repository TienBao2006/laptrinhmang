"""
client/gui_login_admin.py - Giao diện Đăng nhập dành riêng cho Quản trị viên / Nhân viên
Chỉ cho phép tài khoản có vai trò Admin hoặc Staff đăng nhập.
IP/Port cấu hình tại common/constants.py (SERVER_HOST, SERVER_PORT)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

# ── Màu theme (dark admin style) ────────────────────────────
CLR_BG      = "#0F172A"
CLR_CARD    = "#1E293B"
CLR_PANEL   = "#162032"
CLR_ACCENT  = "#7C3AED"   # tím — phân biệt rõ với client (xanh)
CLR_ACCENT2 = "#6D28D9"
CLR_GREEN   = "#059669"
CLR_RED     = "#EF4444"
CLR_YELLOW  = "#D97706"
CLR_MUTED   = "#64748B"
CLR_BORDER  = "#334155"
CLR_TEXT    = "#F1F5F9"
CLR_SUB     = "#94A3B8"

# Tài khoản thử nghiệm chỉ dành cho Admin / Staff
ADMIN_QUICK = [
    ("🛡️", "Quản trị (Admin)",   "admin",    "admin123", "#7C3AED"),
    ("🎫", "Nhân viên (Staff)",   "nhanvien", "123456",   "#0284C7"),
]

ALLOWED_ROLES = {"Admin", "Staff"}


class AdminLoginWindow:
    """Cửa sổ đăng nhập dành riêng cho Admin / Staff."""

    def __init__(self, root, network_client, on_login_success):
        self.root             = root
        self.client           = network_client
        self.on_login_success = on_login_success

        self.root.title("TrainBus — Đăng Nhập Quản Trị Viên")
        self.root.geometry("480x520")
        self.root.resizable(False, False)
        self.root.configure(bg=CLR_BG)

        ttk.Style().theme_use("clam")

        self._build_ui()
        self._try_auto_connect()

    # ══════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_header()
        self._build_status_bar()
        self._build_login_form()

    # ── Header ───────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=CLR_BG)
        hdr.pack(fill=tk.X)

        # Thanh màu accent trên cùng
        tk.Frame(hdr, bg=CLR_ACCENT, height=5).pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=CLR_BG, pady=20)
        inner.pack()

        tk.Label(
            inner, text="🛡️  TRANG QUẢN TRỊ HỆ THỐNG",
            font=("Segoe UI", 16, "bold"), fg=CLR_ACCENT, bg=CLR_BG
        ).pack()

        tk.Label(
            inner,
            text="Chỉ dành cho Quản trị viên & Nhân viên — TrainBus Admin Panel",
            font=("Segoe UI", 9), fg=CLR_SUB, bg=CLR_BG
        ).pack(pady=(4, 0))

        # Dòng phân cách
        tk.Frame(inner, bg=CLR_BORDER, height=1).pack(fill=tk.X, pady=(14, 0))

    # ── Thanh trạng thái kết nối ─────────────────────────────
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=CLR_CARD,
                       bd=0, highlightbackground=CLR_BORDER,
                       highlightthickness=1)
        bar.pack(fill=tk.X, padx=24, pady=(14, 0))

        inner = tk.Frame(bar, bg=CLR_CARD, padx=14, pady=10)
        inner.pack(fill=tk.X)

        host_row = tk.Frame(inner, bg=CLR_CARD)
        host_row.pack(fill=tk.X, pady=(0, 7))

        tk.Label(
            host_row, text=f"IP máy chủ ({self.client.port})",
            font=("Segoe UI", 9, "bold"), fg=CLR_TEXT, bg=CLR_CARD
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.host_var = tk.StringVar(value=self.client.host)
        self.ent_host = ttk.Entry(
            host_row, font=("Segoe UI", 9), textvariable=self.host_var
        )
        self.ent_host.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.ent_host.bind("<Return>", lambda e: self._on_connect())

        self.btn_connect = tk.Button(
            host_row, text="Kết nối",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=10, pady=3, cursor="hand2",
            activebackground=CLR_ACCENT2,
            command=self._on_connect
        )
        self.btn_connect.pack(side=tk.RIGHT)

        status_row = tk.Frame(inner, bg=CLR_CARD)
        status_row.pack(fill=tk.X)

        self.lbl_status = tk.Label(
            status_row, text="⚪  Đang kết nối tới máy chủ...",
            font=("Segoe UI", 9), fg=CLR_SUB, bg=CLR_CARD, anchor=tk.W
        )
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_retry = tk.Button(
            status_row, text="🔄 Thử lại",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=10, pady=3, cursor="hand2",
            activebackground=CLR_ACCENT2,
            command=self._on_retry
        )
        self.btn_retry.pack(side=tk.RIGHT)

    # ── Form đăng nhập ───────────────────────────────────────
    def _build_login_form(self):
        card = tk.Frame(self.root, bg=CLR_CARD,
                        bd=0, highlightbackground=CLR_BORDER,
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=24, pady=(12, 24))

        f = tk.Frame(card, bg=CLR_CARD, padx=24, pady=20)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text="ĐĂNG NHẬP QUẢN TRỊ",
                 font=("Segoe UI", 11, "bold"), fg=CLR_TEXT, bg=CLR_CARD
                 ).pack(anchor=tk.W, pady=(0, 16))

        # Username
        tk.Label(f, text="Tên đăng nhập",
                 font=("Segoe UI", 9, "bold"), fg=CLR_SUB, bg=CLR_CARD
                 ).pack(anchor=tk.W)
        self.ent_user = _dark_entry(f)
        self.ent_user.pack(fill=tk.X, pady=(3, 12))
        self.ent_user.bind("<Return>", lambda e: self.ent_pass.focus())

        # Password
        tk.Label(f, text="Mật khẩu",
                 font=("Segoe UI", 9, "bold"), fg=CLR_SUB, bg=CLR_CARD
                 ).pack(anchor=tk.W)
        self.ent_pass = _dark_entry(f, show="•")
        self.ent_pass.pack(fill=tk.X, pady=(3, 20))
        self.ent_pass.bind("<Return>", lambda e: self._on_login())

        # Nút đăng nhập
        tk.Button(
            f, text="ĐĂNG NHẬP VÀO HỆ THỐNG QUẢN TRỊ",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=10, cursor="hand2",
            activebackground=CLR_ACCENT2,
            command=self._on_login
        ).pack(fill=tk.X)

        # Phân cách
        sep_frame = tk.Frame(f, bg=CLR_CARD)
        sep_frame.pack(fill=tk.X, pady=(18, 8))
        tk.Frame(sep_frame, bg=CLR_BORDER, height=1).pack(fill=tk.X)

        tk.Label(f, text="Tài khoản thử nghiệm:",
                 font=("Segoe UI", 8), fg=CLR_MUTED, bg=CLR_CARD
                 ).pack(anchor=tk.W, pady=(0, 6))

        # Quick fill buttons
        grid = tk.Frame(f, bg=CLR_CARD)
        grid.pack(fill=tk.X)
        for i, (icon, name, user, pw, color) in enumerate(ADMIN_QUICK):
            tk.Button(
                grid,
                text=f"{icon}  {name}",
                bg=color, fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT, pady=6, cursor="hand2",
                activeforeground="#FFFFFF",
                activebackground=color,
                command=lambda u=user, p=pw: self._quick_fill(u, p)
            ).grid(row=0, column=i, padx=(0, 6 if i == 0 else 0), sticky=tk.EW)
            grid.columnconfigure(i, weight=1)

        # Ghi chú quyền truy cập
        note = tk.Label(
            f,
            text="⚠️  Chỉ tài khoản Admin hoặc Staff mới được phép đăng nhập tại đây.",
            font=("Segoe UI", 8), fg=CLR_YELLOW, bg=CLR_CARD,
            wraplength=380, justify=tk.LEFT
        )
        note.pack(anchor=tk.W, pady=(14, 0))

    # ══════════════════════════════════════════════════════════
    #  KẾT NỐI
    # ══════════════════════════════════════════════════════════
    def _try_auto_connect(self):
        self._connect_to_host()

    def _on_connect(self):
        self._connect_to_host()

    def _connect_to_host(self):
        host = self.ent_host.get().strip()
        if not host:
            messagebox.showwarning("Thiếu địa chỉ máy chủ", "Vui lòng nhập IP hoặc tên máy chủ.", parent=self.root)
            return

        self.lbl_status.config(text="⚪  Đang kết nối tới máy chủ...", fg=CLR_SUB)
        self.btn_connect.config(state=tk.DISABLED)
        self.btn_retry.config(state=tk.DISABLED)

        def task():
            ok, msg = self.client.connect(host, self.client.port)
            self.root.after(0, lambda: self._update_status(ok))
        threading.Thread(target=task, daemon=True).start()

    def _on_retry(self):
        self._connect_to_host()

    def _update_status(self, success: bool):
        self.btn_connect.config(state=tk.NORMAL)
        self.btn_retry.config(state=tk.NORMAL)
        if success:
            self.lbl_status.config(
                text=f"🟢  Đã kết nối  —  {self.client.host}:{self.client.port}",
                fg=CLR_GREEN
            )
        else:
            self.lbl_status.config(
                text=f"🔴  Không kết nối được  —  {self.client.host}:{self.client.port}",
                fg=CLR_RED
            )

    # ══════════════════════════════════════════════════════════
    #  ĐĂNG NHẬP
    # ══════════════════════════════════════════════════════════
    def _quick_fill(self, user: str, pw: str):
        self.ent_user.delete(0, tk.END)
        self.ent_user.insert(0, user)
        self.ent_pass.delete(0, tk.END)
        self.ent_pass.insert(0, pw)
        self.ent_user.focus()

    def _on_login(self):
        if not self.client.is_connected:
            messagebox.showwarning(
                "Chưa kết nối",
                "Chưa kết nối tới máy chủ.\nVui lòng bấm 'Thử lại'!",
                parent=self.root
            )
            return

        u = self.ent_user.get().strip()
        p = self.ent_pass.get().strip()
        if not u or not p:
            messagebox.showwarning(
                "Thiếu thông tin",
                "Vui lòng nhập Tên đăng nhập và Mật khẩu!",
                parent=self.root
            )
            return

        resp = self.client.login(u, p)
        if resp.get("status") == "SUCCESS":
            info   = resp["user_info"]
            role   = info.get("role", "")

            # Kiểm tra quyền — chỉ Admin hoặc Staff mới được vào
            if role not in ALLOWED_ROLES:
                # Đăng xuất ngay để giải phóng token
                try:
                    self.client.logout()
                except Exception:
                    pass
                messagebox.showerror(
                    "Không có quyền truy cập",
                    f"Tài khoản '{u}' có vai trò '{role}'.\n"
                    "Trang này chỉ dành cho Quản trị viên (Admin) và Nhân viên (Staff).",
                    parent=self.root
                )
                return

            messagebox.showinfo(
                "Đăng nhập thành công",
                f"Chào mừng, {info['fullname']}!\nVai trò: {role}",
                parent=self.root
            )
            self.on_login_success(self.client)
        else:
            messagebox.showerror(
                "Đăng nhập thất bại",
                resp.get("message", "Lỗi không xác định!"),
                parent=self.root
            )


# ── Tiện ích ─────────────────────────────────────────────────
def _dark_entry(parent, show="") -> ttk.Entry:
    """Entry tối màu cho giao diện admin."""
    style = ttk.Style()
    style.configure("Dark.TEntry",
                    fieldbackground="#0F172A",
                    foreground="#F1F5F9",
                    borderwidth=1,
                    relief="solid",
                    font=("Segoe UI", 10))
    e = ttk.Entry(parent, font=("Segoe UI", 10), style="Dark.TEntry")
    if show:
        e.configure(show=show)
    return e
