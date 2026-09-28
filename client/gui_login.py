"""
client/gui_login.py - Giao diện Đăng nhập / Đăng ký (Dành cho Khách hàng & Tài xế)
IP/Port cấu hình tại common/constants.py (SERVER_HOST, SERVER_PORT)

Lưu ý: Tài khoản Admin / Staff đăng nhập qua run_admin.py (gui_login_admin.py).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

# ── Màu theme ────────────────────────────────────────────────
CLR_BG      = "#F1F5F9"
CLR_CARD    = "#FFFFFF"
CLR_NAV     = "#0F172A"
CLR_ACCENT  = "#0EA5E9"
CLR_GREEN   = "#059669"
CLR_RED     = "#EF4444"
CLR_MUTED   = "#94A3B8"
CLR_BORDER  = "#E2E8F0"
CLR_TEXT    = "#1E293B"
CLR_SUB     = "#64748B"

# Chỉ giữ Khách hàng và Tài xế — Admin/Staff dùng run_admin.py
ROLE_QUICK = [
    ("👤", "Khách hàng", "khachhang", "123456", "#475569"),
    ("🚌", "Tài xế",     "taixe",     "123456", "#059669"),
]


class LoginWindow:
    def __init__(self, root, network_client, on_login_success):
        self.root             = root
        self.client           = network_client
        self.on_login_success = on_login_success

        self.root.title("TrainBus — Đăng Nhập Khách Hàng")
        self.root.geometry("520x640")
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
        self._build_tabs()

    # ── Header ───────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=CLR_NAV)
        hdr.pack(fill=tk.X)

        # Thanh màu accent trên cùng
        tk.Frame(hdr, bg=CLR_ACCENT, height=4).pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=CLR_NAV, pady=18)
        inner.pack()

        tk.Label(
            inner, text="🚌  TRAINBUS ONLINE 24/7",
            font=("Segoe UI", 17, "bold"), fg=CLR_ACCENT, bg=CLR_NAV
        ).pack()

        tk.Label(
            inner,
            text="Dành cho Khách hàng & Tài xế  •  Admin dùng run_admin.py",
            font=("Segoe UI", 9), fg=CLR_MUTED, bg=CLR_NAV
        ).pack(pady=(3, 0))

    # ── Thanh trạng thái kết nối ─────────────────────────────
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=CLR_CARD,
                       bd=0, highlightbackground=CLR_BORDER,
                       highlightthickness=1)
        bar.pack(fill=tk.X, padx=24, pady=(12, 0))

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
            activebackground="#0284C7",
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
            activebackground="#0284C7",
            command=self._on_retry
        )
        self.btn_retry.pack(side=tk.RIGHT)

    # ── Notebook tabs ────────────────────────────────────────
    def _build_tabs(self):
        outer = tk.Frame(self.root, bg=CLR_CARD,
                         bd=0, highlightbackground=CLR_BORDER,
                         highlightthickness=1)
        outer.pack(fill=tk.BOTH, expand=True,
                   padx=24, pady=(10, 20))

        style = ttk.Style()
        style.configure("Login.TNotebook",
                         background=CLR_CARD, borderwidth=0)
        style.configure("Login.TNotebook.Tab",
                         font=("Segoe UI", 9, "bold"),
                         padding=[20, 8],
                         background=CLR_BG, foreground=CLR_SUB)
        style.map("Login.TNotebook.Tab",
                  background=[("selected", CLR_CARD)],
                  foreground=[("selected", CLR_TEXT)])

        nb = ttk.Notebook(outer, style="Login.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.tab_login = tk.Frame(nb, bg=CLR_CARD)
        self.tab_reg   = tk.Frame(nb, bg=CLR_CARD)

        nb.add(self.tab_login, text="  Đăng Nhập  ")
        nb.add(self.tab_reg,   text="  Đăng Ký  ")

        self._build_login_tab()
        self._build_register_tab()

    # ── Tab Đăng nhập ────────────────────────────────────────
    def _build_login_tab(self):
        f = tk.Frame(self.tab_login, bg=CLR_CARD, padx=20, pady=14)
        f.pack(fill=tk.BOTH, expand=True)

        # Username
        tk.Label(f, text="Tên đăng nhập",
                 font=("Segoe UI", 9, "bold"), fg=CLR_TEXT,
                 bg=CLR_CARD).pack(anchor=tk.W)
        self.ent_user = _styled_entry(f)
        self.ent_user.pack(fill=tk.X, pady=(3, 10))
        self.ent_user.bind("<Return>", lambda e: self.ent_pass.focus())

        # Password
        tk.Label(f, text="Mật khẩu",
                 font=("Segoe UI", 9, "bold"), fg=CLR_TEXT,
                 bg=CLR_CARD).pack(anchor=tk.W)
        self.ent_pass = _styled_entry(f, show="•")
        self.ent_pass.pack(fill=tk.X, pady=(3, 16))
        self.ent_pass.bind("<Return>", lambda e: self._on_login())

        # Nút đăng nhập
        tk.Button(
            f, text="ĐĂNG NHẬP",
            bg=CLR_GREEN, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2",
            activebackground="#047857",
            command=self._on_login
        ).pack(fill=tk.X)

        # Quick fill
        sep = tk.Frame(f, bg=CLR_BORDER, height=1)
        sep.pack(fill=tk.X, pady=(16, 8))

        tk.Label(f, text="Điền nhanh tài khoản thử nghiệm:",
                 font=("Segoe UI", 8), fg=CLR_SUB,
                 bg=CLR_CARD).pack(anchor=tk.W, pady=(0, 6))

        grid = tk.Frame(f, bg=CLR_CARD)
        grid.pack(fill=tk.X)
        for i, (icon, name, user, pw, color) in enumerate(ROLE_QUICK):
            col = i % 2
            row = i // 2
            tk.Button(
                grid,
                text=f"{icon}  {name}",
                bg=color, fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT, pady=6, cursor="hand2",
                activeforeground="#FFFFFF",
                activebackground=color,
                command=lambda u=user, p=pw: self._quick_fill(u, p)
            ).grid(row=row, column=col,
                   padx=(0 if col else 0, 6 if col == 0 else 0),
                   pady=3, sticky=tk.EW)
            grid.columnconfigure(col, weight=1)

        # Ghi chú Admin dùng cổng riêng
        tk.Label(
            f,
            text="🛡️  Admin / Nhân viên? Dùng run_admin.py để đăng nhập.",
            font=("Segoe UI", 8), fg=CLR_MUTED, bg=CLR_CARD
        ).pack(anchor=tk.W, pady=(10, 0))

    # ── Tab Đăng ký ──────────────────────────────────────────
    def _build_register_tab(self):
        f = tk.Frame(self.tab_reg, bg=CLR_CARD, padx=20, pady=14)
        f.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("Họ và tên *",              "reg_name",  False),
            ("Số điện thoại",            "reg_phone", False),
            ("Email nhận vé",            "reg_email", False),
            ("Tên đăng nhập *",          "reg_user",  False),
            ("Mật khẩu * (tối thiểu 6 ký tự)", "reg_pass", True),
        ]
        for label, attr, is_pass in fields:
            tk.Label(f, text=label,
                     font=("Segoe UI", 8, "bold"), fg=CLR_TEXT,
                     bg=CLR_CARD).pack(anchor=tk.W)
            e = _styled_entry(f, show="•" if is_pass else "")
            e.pack(fill=tk.X, pady=(2, 8))
            setattr(self, attr, e)

        tk.Button(
            f, text="TẠO TÀI KHOẢN MỚI",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2",
            activebackground="#0284C7",
            command=self._on_register
        ).pack(fill=tk.X, pady=(4, 0))

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
    #  ĐĂNG NHẬP / ĐĂNG KÝ
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
                "Chưa kết nối tới máy chủ.\nVui lòng bấm 'Thử lại'!"
            )
            return
        u = self.ent_user.get().strip()
        p = self.ent_pass.get().strip()
        if not u or not p:
            messagebox.showwarning("Thiếu thông tin",
                                   "Vui lòng nhập Tên đăng nhập và Mật khẩu!")
            return

        resp = self.client.login(u, p)
        if resp.get("status") == "SUCCESS":
            info = resp["user_info"]
            messagebox.showinfo(
                "Đăng nhập thành công",
                f"Chào mừng, {info['fullname']}!\nVai trò: {info['role']}"
            )
            self.on_login_success(self.client)
        else:
            messagebox.showerror("Đăng nhập thất bại",
                                 resp.get("message", "Lỗi không xác định!"))

    def _on_register(self):
        if not self.client.is_connected:
            messagebox.showwarning("Chưa kết nối",
                                   "Chưa kết nối tới máy chủ!")
            return
        name  = self.reg_name.get().strip()
        phone = self.reg_phone.get().strip()
        email = self.reg_email.get().strip()
        user  = self.reg_user.get().strip()
        pw    = self.reg_pass.get().strip()

        if not name or not user or not pw:
            messagebox.showwarning(
                "Thiếu thông tin",
                "Vui lòng điền đầy đủ các trường bắt buộc (*)!"
            )
            return
        if len(pw) < 6:
            messagebox.showwarning("Mật khẩu yếu",
                                   "Mật khẩu phải có ít nhất 6 ký tự!")
            return

        resp = self.client.register(user, pw, name, phone, email)
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Đăng ký thành công",
                                resp.get("message",
                                         "Tài khoản đã được tạo! Hãy đăng nhập."))
            self._quick_fill(user, pw)
        else:
            messagebox.showerror("Đăng ký thất bại",
                                 resp.get("message", "Lỗi đăng ký!"))


# ── Tiện ích ─────────────────────────────────────────────────
def _styled_entry(parent, show="") -> ttk.Entry:
    """Entry có border và font chuẩn."""
    style = ttk.Style()
    style.configure("Styled.TEntry",
                     fieldbackground="#F8FAFC",
                     borderwidth=1,
                     relief="solid",
                     font=("Segoe UI", 10))
    e = ttk.Entry(parent, font=("Segoe UI", 10),
                  style="Styled.TEntry")
    if show:
        e.configure(show=show)
    return e
