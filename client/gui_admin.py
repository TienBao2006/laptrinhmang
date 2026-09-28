"""
client/gui_admin.py - Giao diện Chăm Sóc Khách Hàng (Customer Care Panel)
Dành cho Admin/Staff: xem dashboard, quản lý khách hàng, vé, online users,
gửi thông báo, thêm chuyến xe, quản lý xe, xem nhật ký hệ thống.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.constants import POPULAR_CITIES, ROLE_ADMIN, ROLE_STAFF

# ── Màu sắc theme ────────────────────────────────────────────
CLR_BG      = "#F1F5F9"
CLR_CARD    = "#FFFFFF"
CLR_NAV     = "#0F172A"
CLR_ACCENT  = "#7C3AED"   # tím — phân biệt với client (xanh)
CLR_BLUE    = "#2563EB"
CLR_GREEN   = "#059669"
CLR_RED     = "#EF4444"
CLR_ORANGE  = "#D97706"
CLR_MUTED   = "#64748B"
CLR_BORDER  = "#E2E8F0"
CLR_TEXT    = "#1E293B"
CLR_SUB     = "#64748B"


class CustomerCareWindow(tk.Toplevel):
    """
    Cửa sổ Chăm Sóc Khách Hàng cho Admin / Staff.
    Mở dưới dạng Toplevel (cửa sổ con) từ màn hình chính.
    """

    def __init__(self, parent, network_client, on_close_callback=None):
        super().__init__(parent)
        self.client = network_client
        self.on_close_callback = on_close_callback

        user_info = self.client.user_info or {}
        role = user_info.get("role", "Staff")
        fullname = user_info.get("fullname", "Nhân viên")

        self.title(f"🎧 Chăm Sóc Khách Hàng — {fullname} ({role})")
        self.geometry("1100x720")
        self.minsize(960, 640)
        self.configure(bg=CLR_BG)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._load_dashboard()

    # ══════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_header()
        self._build_notebook()

    def _build_header(self):
        header = tk.Frame(self, bg=CLR_NAV, height=62)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🎧  TRUNG TÂM CHĂM SÓC KHÁCH HÀNG — TRAINBUS",
            font=("Segoe UI", 13, "bold"), fg="#A78BFA", bg=CLR_NAV
        ).pack(side=tk.LEFT, padx=20, pady=16)

        # Badge role của nhân viên đang đăng nhập
        user_info = self.client.user_info or {}
        role = user_info.get("role", "")
        fname = user_info.get("fullname", "")
        role_color = "#7C3AED" if role == ROLE_ADMIN else "#0284C7"
        tk.Label(
            header,
            text=f"  {role}  ",
            font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg=role_color
        ).pack(side=tk.RIGHT, padx=(4, 20), pady=22)
        tk.Label(
            header,
            text=fname,
            font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg=CLR_NAV
        ).pack(side=tk.RIGHT, padx=(16, 4), pady=22)

        tk.Button(
            header, text="🔄 Làm mới",
            bg="#334155", fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=10, pady=5, cursor="hand2",
            command=self._refresh_all
        ).pack(side=tk.RIGHT, padx=8, pady=16)

    def _build_notebook(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Care.TNotebook", background=CLR_BG, tabmargins=[4, 6, 0, 0])
        style.configure("Care.TNotebook.Tab",
                        font=("Segoe UI", 9, "bold"),
                        padding=[14, 7])
        style.map("Care.TNotebook.Tab",
                  background=[("selected", CLR_ACCENT), ("!selected", "#E2E8F0")],
                  foreground=[("selected", "#FFFFFF"), ("!selected", CLR_TEXT)])

        nb = ttk.Notebook(self, style="Care.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ── Tab 1: Dashboard ────────────────────────────────
        self.tab_dash = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_dash, text="  📊 Dashboard  ")
        self._build_tab_dashboard()

        # ── Tab 2: Khách hàng ───────────────────────────────
        self.tab_users = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_users, text="  👥 Khách Hàng  ")
        self._build_tab_users()

        # ── Tab 3: Quản lý vé ───────────────────────────────
        self.tab_tickets = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_tickets, text="  🎫 Quản Lý Vé  ")
        self._build_tab_tickets()

        # ── Tab 4: Online users ─────────────────────────────
        self.tab_online = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_online, text="  🟢 Online Ngay  ")
        self._build_tab_online()

        # ── Tab 5: Gửi thông báo ────────────────────────────
        self.tab_notify = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_notify, text="  🔔 Thông Báo  ")
        self._build_tab_notify()

        # ── Tab 6: Thêm chuyến xe ───────────────────────────
        self.tab_trip = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_trip, text="  ➕ Thêm Chuyến  ")
        self._build_tab_add_trip()

        # ── Tab 7: Quản lý xe ───────────────────────────────
        self.tab_vehicles = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_vehicles, text="  🚌 Quản Lý Xe  ")
        self._build_tab_vehicles()

        # ── Tab 8: Nhật ký hệ thống ─────────────────────────
        self.tab_logs = tk.Frame(nb, bg=CLR_BG)
        nb.add(self.tab_logs, text="  📋 Nhật Ký  ")
        self._build_tab_logs()

        # Khi đổi tab → load dữ liệu tương ứng
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._notebook = nb

    # ══════════════════════════════════════════════════════════
    #  TAB 1: DASHBOARD
    # ══════════════════════════════════════════════════════════
    def _build_tab_dashboard(self):
        # KPI cards
        kpi_frame = tk.Frame(self.tab_dash, bg=CLR_BG)
        kpi_frame.pack(fill=tk.X, padx=15, pady=(15, 8))

        self.kpi_revenue = self._kpi_card(kpi_frame, "💰 TỔNG DOANH THU", "—", CLR_GREEN)
        self.kpi_revenue.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.kpi_tickets = self._kpi_card(kpi_frame, "🎫 VÉ ĐÃ BÁN", "—", CLR_BLUE)
        self.kpi_tickets.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.kpi_trips = self._kpi_card(kpi_frame, "🚌 CHUYẾN HOẠT ĐỘNG", "—", CLR_ACCENT)
        self.kpi_trips.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.kpi_users = self._kpi_card(kpi_frame, "👥 KHÁCH HÀNG", "—", CLR_ORANGE)
        self.kpi_users.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Bảng giao dịch gần đây
        lf = tk.LabelFrame(
            self.tab_dash,
            text="  Giao dịch đặt vé gần đây  ",
            font=("Segoe UI", 9, "bold"), bg=CLR_CARD, fg=CLR_TEXT,
            padx=10, pady=8
        )
        lf.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        cols = ("code", "user", "passenger", "route", "seats", "amount", "time", "status")
        self.tree_dash = ttk.Treeview(lf, columns=cols, show="headings", height=14)

        for col, txt, w in [
            ("code",      "Mã vé",      120),
            ("user",      "Tài khoản",   90),
            ("passenger", "Hành khách", 120),
            ("route",     "Tuyến xe",   160),
            ("seats",     "Ghế",         65),
            ("amount",    "Số tiền",      95),
            ("time",      "Ngày đặt",   125),
            ("status",    "Trạng thái",  90),
        ]:
            self.tree_dash.heading(col, text=txt)
            self.tree_dash.column(col, width=w,
                anchor=tk.CENTER if col in ("code","user","seats","time","status") else tk.W)

        sy = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.tree_dash.yview)
        self.tree_dash.configure(yscrollcommand=sy.set)
        self.tree_dash.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_dashboard(self):
        # Reset KPI về trạng thái đang tải
        for attr in ("kpi_revenue", "kpi_tickets", "kpi_trips", "kpi_users"):
            getattr(self, attr).val_lbl.config(text="⏳ ...")

        def fetch():
            r_stats   = self.client.admin_get_stats()
            r_tickets = self.client.admin_get_all_tickets()
            self.after(0, lambda: self._apply_dashboard(r_stats, r_tickets))

        threading.Thread(target=fetch, daemon=True).start()

    def _apply_dashboard(self, r_stats, r_tickets):
        if r_stats.get("status") == "SUCCESS":
            s = r_stats.get("stats", {})
            rev = s.get("total_revenue", 0)
            self.kpi_revenue.val_lbl.config(text=f"{rev:,} VNĐ".replace(",", "."))
            self.kpi_tickets.val_lbl.config(text=f"{s.get('tickets_count', 0)} vé")
            self.kpi_trips.val_lbl.config(text=f"{s.get('trips_count', 0)} chuyến")
            self.kpi_users.val_lbl.config(text=f"{s.get('users_count', 0)} người")
        else:
            err = r_stats.get("message", "Không kết nối được server")
            for attr in ("kpi_revenue", "kpi_tickets", "kpi_trips", "kpi_users"):
                getattr(self, attr).val_lbl.config(text=f"⚠️ {err}")

        self.tree_dash.delete(*self.tree_dash.get_children())
        if r_tickets.get("status") == "SUCCESS":
            # Chỉ hiển thị 100 vé gần nhất trên dashboard
            for t in list(reversed(r_tickets.get("tickets", [])))[:100]:
                route = f"{t.get('from_city','?')} ➔ {t.get('to_city','?')}"
                price_str = f"{t.get('total_amount', 0):,} VNĐ".replace(",", ".")
                status_txt = "✅ ĐÃ ĐẶT" if t.get("status") == "CONFIRMED" else "❌ ĐÃ HỦY"
                self.tree_dash.insert("", tk.END, values=(
                    t.get("booking_code"), t.get("username"),
                    t.get("passenger_name"), route,
                    t.get("seats"), price_str,
                    t.get("booking_time"), status_txt,
                ))
        else:
            self.tree_dash.insert("", tk.END, values=(
                "—", f"⚠️ {r_tickets.get('message','Chưa kết nối server')}",
                "", "", "", "", "", ""
            ))

    # ══════════════════════════════════════════════════════════
    #  TAB 2: KHÁCH HÀNG
    # ══════════════════════════════════════════════════════════
    def _build_tab_users(self):
        toolbar = tk.Frame(self.tab_users, bg=CLR_BG, pady=6)
        toolbar.pack(fill=tk.X, padx=15)

        tk.Button(
            toolbar, text="🔄 Tải lại",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=12, pady=5, cursor="hand2",
            command=self._load_users
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(toolbar, text="Tìm kiếm:",
                 font=("Segoe UI", 9), bg=CLR_BG).pack(side=tk.LEFT)
        self.ent_user_search = ttk.Entry(toolbar, width=22)
        self.ent_user_search.pack(side=tk.LEFT, padx=4)
        tk.Button(
            toolbar, text="🔍",
            bg="#334155", fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=8, pady=5, cursor="hand2",
            command=self._filter_users
        ).pack(side=tk.LEFT)

        # Khung chứa treeview + action panel
        body = tk.Frame(self.tab_users, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(4, 15))

        # Treeview
        cols = ("id", "username", "fullname", "phone", "email", "role", "active", "created")
        self.tree_users = ttk.Treeview(body, columns=cols, show="headings", height=16)
        for col, txt, w in [
            ("id",       "ID",           45),
            ("username", "Tài khoản",    110),
            ("fullname", "Họ tên",       150),
            ("phone",    "SĐT",           95),
            ("email",    "Email",         160),
            ("role",     "Vai trò",        90),
            ("active",   "Trạng thái",    90),
            ("created",  "Ngày tạo",     120),
        ]:
            self.tree_users.heading(col, text=txt)
            self.tree_users.column(col, width=w,
                anchor=tk.CENTER if col in ("id","role","active","created") else tk.W)

        sy = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree_users.yview)
        self.tree_users.configure(yscrollcommand=sy.set)
        self.tree_users.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        # Panel hành động (bên phải) — chỉ Admin mới thấy
        role = (self.client.user_info or {}).get("role", "")
        if role == ROLE_ADMIN:
            action_frame = tk.Frame(body, bg=CLR_CARD, bd=1, relief=tk.SOLID,
                                    padx=14, pady=12, width=190)
            action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
            action_frame.pack_propagate(False)

            tk.Label(action_frame, text="THAO TÁC",
                     font=("Segoe UI", 9, "bold"), fg=CLR_TEXT, bg=CLR_CARD
                     ).pack(anchor=tk.W, pady=(0, 10))

            tk.Label(action_frame, text="Đổi vai trò:",
                     font=("Segoe UI", 8), fg=CLR_SUB, bg=CLR_CARD
                     ).pack(anchor=tk.W, pady=(6, 2))
            self.cb_user_role = ttk.Combobox(
                action_frame, width=16, state="readonly",
                values=["Customer", "Staff", "Driver", "Admin"]
            )
            self.cb_user_role.pack(anchor=tk.W)

            tk.Label(action_frame, text="Trạng thái:",
                     font=("Segoe UI", 8), fg=CLR_SUB, bg=CLR_CARD
                     ).pack(anchor=tk.W, pady=(10, 2))
            self.cb_user_active = ttk.Combobox(
                action_frame, width=16, state="readonly",
                values=["Kích hoạt (Active)", "Khóa (Inactive)"]
            )
            self.cb_user_active.pack(anchor=tk.W)

            tk.Button(
                action_frame, text="✅ Lưu thay đổi",
                bg=CLR_GREEN, fg="#FFFFFF",
                font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                pady=7, cursor="hand2",
                command=self._save_user_change
            ).pack(fill=tk.X, pady=(16, 0))

        self._all_users_data = []
        self._users_loaded = False

    def _load_users(self):
        self._users_loaded = False
        self.tree_users.delete(*self.tree_users.get_children())
        self.tree_users.insert("", tk.END, values=("...", "⏳ Đang tải...", "", "", "", "", "", ""))

        def fetch():
            r = self.client.admin_get_users()
            self.after(0, lambda: self._apply_users(r))
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_users(self, resp):
        self._all_users_data = resp.get("users", [])
        self._users_loaded = True

        self.tree_users.delete(*self.tree_users.get_children())
        if resp.get("status") == "ERROR":
            self.tree_users.insert("", tk.END, values=(
                "—", f"⚠️ {resp.get('message','Lỗi kết nối')}", "", "", "", "", "", ""
            ))
            return
        self._render_users(self._all_users_data)

    def _render_users(self, users):
        self.tree_users.delete(*self.tree_users.get_children())
        for u in users:
            active_txt = "🟢 Hoạt động" if u.get("is_active", 1) else "🔴 Bị khóa"
            self.tree_users.insert("", tk.END, values=(
                u.get("id"), u.get("username"), u.get("fullname"),
                u.get("phone", ""), u.get("email", ""),
                u.get("role", ""), active_txt, u.get("created_at", "")
            ))

    def _filter_users(self):
        keyword = self.ent_user_search.get().strip().lower()

        # Dùng flag _users_loaded thay vì kiểm tra list rỗng
        if not getattr(self, "_users_loaded", False):
            self._load_users()
            return

        if not keyword:
            self._render_users(self._all_users_data)
            return

        def _s(v):
            return str(v).lower() if v is not None else ""
        filtered = [
            u for u in self._all_users_data
            if keyword in _s(u.get("username"))
            or keyword in _s(u.get("fullname"))
            or keyword in _s(u.get("phone"))
            or keyword in _s(u.get("email"))
        ]
        self._render_users(filtered)

    def _save_user_change(self):
        sel = self.tree_users.selection()
        if not sel:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn một khách hàng!", parent=self)
            return
        values = self.tree_users.item(sel[0], "values")
        user_id = int(values[0])

        role_val   = self.cb_user_role.get() if hasattr(self, "cb_user_role") else ""
        active_val = self.cb_user_active.get() if hasattr(self, "cb_user_active") else ""

        if not role_val and not active_val:
            messagebox.showwarning("Chưa chọn thay đổi",
                                   "Vui lòng chọn vai trò hoặc trạng thái mới!", parent=self)
            return

        new_role   = role_val or values[5]
        new_active = 0 if "Khóa" in active_val else 1

        resp = self.client.admin_update_user(user_id, new_role, new_active)
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Thành công", "Đã cập nhật tài khoản!", parent=self)
            self._load_users()
        else:
            messagebox.showerror("Lỗi", resp.get("message", "Không thể cập nhật!"), parent=self)

    # ══════════════════════════════════════════════════════════
    #  TAB 3: QUẢN LÝ VÉ
    # ══════════════════════════════════════════════════════════
    def _build_tab_tickets(self):
        toolbar = tk.Frame(self.tab_tickets, bg=CLR_BG, pady=6)
        toolbar.pack(fill=tk.X, padx=15)

        tk.Button(
            toolbar, text="🔄 Tải lại",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=12, pady=5, cursor="hand2",
            command=self._load_all_tickets
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(toolbar, text="Tìm kiếm:",
                 font=("Segoe UI", 9), bg=CLR_BG).pack(side=tk.LEFT)
        self.ent_ticket_search = ttk.Entry(toolbar, width=24)
        self.ent_ticket_search.pack(side=tk.LEFT, padx=4)
        tk.Button(
            toolbar, text="🔍",
            bg="#334155", fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=8, pady=5, cursor="hand2",
            command=self._filter_tickets
        ).pack(side=tk.LEFT, padx=(0, 16))

        # Lọc theo trạng thái
        tk.Label(toolbar, text="Trạng thái:",
                 font=("Segoe UI", 9), bg=CLR_BG).pack(side=tk.LEFT)
        self.cb_ticket_status = ttk.Combobox(
            toolbar, width=12, state="readonly",
            values=["Tất cả", "CONFIRMED", "CANCELLED"]
        )
        self.cb_ticket_status.set("Tất cả")
        self.cb_ticket_status.pack(side=tk.LEFT, padx=4)
        self.cb_ticket_status.bind("<<ComboboxSelected>>", lambda e: self._filter_tickets())

        body = tk.Frame(self.tab_tickets, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(4, 15))

        cols = ("code", "user", "passenger", "phone", "route", "seats", "amount", "time", "status")
        self.tree_tickets = ttk.Treeview(body, columns=cols, show="headings", height=16)
        for col, txt, w in [
            ("code",      "Mã vé",      125),
            ("user",      "Tài khoản",   90),
            ("passenger", "Hành khách", 120),
            ("phone",     "SĐT",         90),
            ("route",     "Tuyến xe",   150),
            ("seats",     "Ghế",         65),
            ("amount",    "Số tiền",      95),
            ("time",      "Ngày đặt",   120),
            ("status",    "Trạng thái",  90),
        ]:
            self.tree_tickets.heading(col, text=txt)
            self.tree_tickets.column(col, width=w,
                anchor=tk.CENTER if col in ("code","user","seats","time","status") else tk.W)

        sy = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree_tickets.yview)
        self.tree_tickets.configure(yscrollcommand=sy.set)
        self.tree_tickets.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        self._all_tickets_data = []
        self._tickets_loaded = False

    def _load_all_tickets(self):
        self._tickets_loaded = False
        self.tree_tickets.delete(*self.tree_tickets.get_children())
        self.tree_tickets.insert("", tk.END, values=("...", "⏳ Đang tải...", "", "", "", "", "", "", ""))

        def fetch():
            r = self.client.admin_get_all_tickets()
            self.after(0, lambda: self._apply_tickets(r))
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_tickets(self, resp):
        self._all_tickets_data = resp.get("tickets", [])
        self._tickets_loaded = True  # đánh dấu đã load xong dù rỗng hay có data

        self.tree_tickets.delete(*self.tree_tickets.get_children())

        if resp.get("status") == "ERROR":
            self.tree_tickets.insert("", tk.END, values=(
                "—", f"⚠️ {resp.get('message','Lỗi kết nối')}", "", "", "", "", "", "", ""
            ))
            return
        self._filter_tickets()

    def _filter_tickets(self):
        # Nếu chưa load lần nào thì load trước (không loop vì dùng flag riêng)
        if not getattr(self, "_tickets_loaded", False):
            self._load_all_tickets()
            return

        keyword = self.ent_ticket_search.get().strip().lower()
        status_filter = self.cb_ticket_status.get()

        result = self._all_tickets_data
        if status_filter != "Tất cả":
            result = [t for t in result if t.get("status") == status_filter]
        if keyword:
            def _s(v):
                return str(v).lower() if v is not None else ""
            result = [
                t for t in result
                if keyword in _s(t.get("booking_code"))
                or keyword in _s(t.get("username"))
                or keyword in _s(t.get("passenger_name"))
                or keyword in _s(t.get("passenger_phone"))
                or keyword in _s(t.get("from_city"))
                or keyword in _s(t.get("to_city"))
            ]

        self.tree_tickets.delete(*self.tree_tickets.get_children())

        if not result:
            # Hiện thông báo rõ ràng thay vì để trống
            if not self._all_tickets_data:
                msg = "Chưa có vé nào được đặt trong hệ thống."
            elif keyword or status_filter != "Tất cả":
                msg = "Không tìm thấy vé khớp với điều kiện tìm kiếm."
            else:
                msg = "Chưa có dữ liệu."
            self.tree_tickets.insert("", tk.END, values=(
                "—", f"ℹ️  {msg}", "", "", "", "", "", "", ""
            ))
            return

        for t in result:
            def _sv(v):
                return str(v) if v is not None else ""
            route = f"{_sv(t.get('from_city'))} ➔ {_sv(t.get('to_city'))}"
            try:
                price_str = f"{int(t.get('total_amount', 0)):,} VNĐ".replace(",", ".")
            except (ValueError, TypeError):
                price_str = "0 VNĐ"
            st_txt = "✅ ĐÃ ĐẶT" if t.get("status") == "CONFIRMED" else "❌ ĐÃ HỦY"
            self.tree_tickets.insert("", tk.END, values=(
                _sv(t.get("booking_code")), _sv(t.get("username")),
                _sv(t.get("passenger_name")), _sv(t.get("passenger_phone")),
                route, _sv(t.get("seats")), price_str,
                _sv(t.get("booking_time")), st_txt,
            ))

    # ══════════════════════════════════════════════════════════
    #  TAB 4: ONLINE NGAY
    # ══════════════════════════════════════════════════════════
    def _build_tab_online(self):
        toolbar = tk.Frame(self.tab_online, bg=CLR_BG, pady=6)
        toolbar.pack(fill=tk.X, padx=15)

        tk.Button(
            toolbar, text="🔄 Cập nhật",
            bg=CLR_GREEN, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=12, pady=5, cursor="hand2",
            command=self._load_online_users
        ).pack(side=tk.LEFT, padx=(0, 12))

        self.lbl_online_count = tk.Label(
            toolbar, text="",
            font=("Segoe UI", 9), fg=CLR_SUB, bg=CLR_BG
        )
        self.lbl_online_count.pack(side=tk.LEFT)

        body = tk.Frame(self.tab_online, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(4, 15))

        # Treeview danh sách online
        cols = ("username", "fullname", "role", "phone")
        self.tree_online = ttk.Treeview(body, columns=cols, show="headings", height=14)
        for col, txt, w in [
            ("username", "Tài khoản",  120),
            ("fullname", "Họ tên",     200),
            ("role",     "Vai trò",    100),
            ("phone",    "SĐT",        120),
        ]:
            self.tree_online.heading(col, text=txt)
            self.tree_online.column(col, width=w,
                anchor=tk.CENTER if col in ("role",) else tk.W)

        sy = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree_online.yview)
        self.tree_online.configure(yscrollcommand=sy.set)
        self.tree_online.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        # Panel gọi điện
        call_panel = tk.Frame(body, bg=CLR_CARD, bd=1, relief=tk.SOLID,
                              padx=14, pady=14, width=200)
        call_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        call_panel.pack_propagate(False)

        tk.Label(call_panel, text="GỌI KHÁCH HÀNG",
                 font=("Segoe UI", 9, "bold"), fg=CLR_TEXT, bg=CLR_CARD
                 ).pack(anchor=tk.W, pady=(0, 10))

        tk.Label(call_panel,
                 text="Chọn người dùng trong danh\nsách rồi bấm để gọi hỗ trợ.",
                 font=("Segoe UI", 8), fg=CLR_SUB, bg=CLR_CARD,
                 wraplength=170, justify=tk.LEFT
                 ).pack(anchor=tk.W, pady=(0, 14))

        tk.Button(
            call_panel, text="📞 Gọi ngay",
            bg=CLR_GREEN, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2",
            command=self._call_selected_user
        ).pack(fill=tk.X)

    def _load_online_users(self):
        self.tree_online.delete(*self.tree_online.get_children())
        self.tree_online.insert("", tk.END, values=("⏳ Đang tải...", "", "", ""))

        def fetch():
            r = self.client.admin_get_online_users()
            self.after(0, lambda: self._apply_online(r))
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_online(self, resp):
        users = resp.get("online_users", [])
        my_username = (self.client.user_info or {}).get("username", "")
        # Loại bỏ bản thân
        users = [u for u in users if u.get("username") != my_username]

        self.tree_online.delete(*self.tree_online.get_children())
        for u in users:
            self.tree_online.insert("", tk.END, values=(
                u.get("username"), u.get("fullname", ""),
                u.get("role", ""), u.get("phone", "")
            ))
        count = len(users)
        self.lbl_online_count.config(
            text=f"🟢 {count} người đang trực tuyến"
        )

    def _call_selected_user(self):
        sel = self.tree_online.selection()
        if not sel:
            messagebox.showinfo("Chưa chọn",
                                "Vui lòng chọn một người dùng trong danh sách để gọi!",
                                parent=self)
            return
        values = self.tree_online.item(sel[0], "values")
        target_username = values[0]
        target_name     = values[1] or target_username

        # Import voice_call lazily để tránh circular import
        try:
            from client.voice_call import CallingDialog
        except ImportError:
            messagebox.showerror("Lỗi", "Không tải được module voice_call!", parent=self)
            return

        def call_worker():
            from common.constants import ACTION_VOICE_CALL_ANY
            resp = self.client.send_request({
                "action": ACTION_VOICE_CALL_ANY,
                "target_username": target_username
            })

            def on_result():
                if resp.get("status") == "SUCCESS":
                    call_id = resp.get("call_id")
                    CallingDialog(self, self.client, call_id, target_name, target_username)
                else:
                    messagebox.showerror(
                        "Gọi thất bại",
                        resp.get("message", "Không thể kết nối. Vui lòng thử lại!"),
                        parent=self
                    )
            self.after(0, on_result)

        threading.Thread(target=call_worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════
    #  TAB 5: GỬI THÔNG BÁO
    # ══════════════════════════════════════════════════════════
    def _build_tab_notify(self):
        container = tk.Frame(self.tab_notify, bg=CLR_CARD, bd=1, relief=tk.SOLID,
                             padx=28, pady=24)
        container.pack(fill=tk.BOTH, expand=True, padx=40, pady=25)

        tk.Label(
            container,
            text="📢  GỬI THÔNG BÁO TỚI TẤT CẢ KHÁCH HÀNG ĐANG ONLINE",
            font=("Segoe UI", 11, "bold"), fg=CLR_TEXT, bg=CLR_CARD
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 20))

        tk.Label(container, text="Tiêu đề thông báo:",
                 font=("Segoe UI", 9, "bold"), bg=CLR_CARD
                 ).grid(row=1, column=0, sticky=tk.W, pady=6)
        self.ent_notif_title = ttk.Entry(container, width=45)
        self.ent_notif_title.grid(row=1, column=1, sticky=tk.W, pady=6, padx=(8, 0))

        tk.Label(container, text="Nội dung thông báo:",
                 font=("Segoe UI", 9, "bold"), bg=CLR_CARD
                 ).grid(row=2, column=0, sticky=tk.NW, pady=6)

        self.txt_notif_body = tk.Text(
            container, width=44, height=6,
            font=("Segoe UI", 10), relief=tk.SOLID, bd=1
        )
        self.txt_notif_body.grid(row=2, column=1, sticky=tk.W, pady=6, padx=(8, 0))

        tk.Button(
            container,
            text="📢  GỬI THÔNG BÁO NGAY",
            bg=CLR_ORANGE, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2",
            command=self._send_notification
        ).grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(20, 0))

        # Lịch sử gửi (hiển thị đơn giản)
        tk.Label(container, text="Kết quả gửi gần đây:",
                 font=("Segoe UI", 9, "bold"), fg=CLR_SUB, bg=CLR_CARD
                 ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(20, 4))

        self.lbl_notif_result = tk.Label(
            container, text="—",
            font=("Segoe UI", 9), fg=CLR_MUTED, bg=CLR_CARD,
            wraplength=500, justify=tk.LEFT
        )
        self.lbl_notif_result.grid(row=5, column=0, columnspan=2, sticky=tk.W)

    def _send_notification(self):
        title = self.ent_notif_title.get().strip()
        body  = self.txt_notif_body.get("1.0", tk.END).strip()

        if not title or not body:
            messagebox.showwarning("Thiếu nội dung",
                                   "Vui lòng nhập Tiêu đề và Nội dung thông báo!",
                                   parent=self)
            return

        def send():
            resp = self.client.admin_send_notification(title, body)
            self.after(0, lambda: self._on_notif_sent(resp, title))
        threading.Thread(target=send, daemon=True).start()

    def _on_notif_sent(self, resp, title):
        if resp.get("status") == "SUCCESS":
            self.lbl_notif_result.config(
                text=f"✅ Đã gửi thành công: \"{title}\"",
                fg=CLR_GREEN
            )
            self.ent_notif_title.delete(0, tk.END)
            self.txt_notif_body.delete("1.0", tk.END)
        else:
            self.lbl_notif_result.config(
                text=f"❌ Lỗi: {resp.get('message', 'Không gửi được!')}",
                fg=CLR_RED
            )

    # ══════════════════════════════════════════════════════════
    #  TAB 6: THÊM CHUYẾN XE
    # ══════════════════════════════════════════════════════════
    def _build_tab_add_trip(self):
        container = tk.Frame(self.tab_trip, bg=CLR_CARD, bd=1, relief=tk.SOLID,
                             padx=28, pady=24)
        container.pack(fill=tk.BOTH, expand=True, padx=40, pady=25)

        tk.Label(
            container,
            text="➕  THÊM CHUYẾN XE MỚI VÀO HỆ THỐNG",
            font=("Segoe UI", 11, "bold"), fg=CLR_TEXT, bg=CLR_CARD
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 20))

        fields = [
            (1, "Biển số xe (VD: 29B-123.45):",              "ent_bus_num",  "29B-777.99"),
            (3, "Ngày giờ khởi hành (HH:MM DD/MM/YYYY):",    "ent_dep_time", "20:00 05/10/2026"),
            (5, "Giá vé niêm yết (VNĐ):",                    "ent_price",    "350000"),
        ]
        for row, label, attr, default in fields:
            tk.Label(container, text=label,
                     font=("Segoe UI", 9, "bold"), bg=CLR_CARD
                     ).grid(row=row, column=0, sticky=tk.W, pady=6)
            ent = ttk.Entry(container, width=38)
            ent.insert(0, default)
            ent.grid(row=row, column=1, sticky=tk.W, pady=6, padx=(8, 0))
            setattr(self, attr, ent)

        # Loại xe
        tk.Label(container, text="Loại xe & Số chỗ:",
                 font=("Segoe UI", 9, "bold"), bg=CLR_CARD
                 ).grid(row=2, column=0, sticky=tk.W, pady=6)
        self.cb_bus_type = ttk.Combobox(
            container, width=36, state="readonly",
            values=["Giường nằm 34 phòng (34 chỗ)",
                    "Limousine 24 phòng VIP (24 chỗ)",
                    "Ghế ngồi cao cấp (29 chỗ)"]
        )
        self.cb_bus_type.current(0)
        self.cb_bus_type.grid(row=2, column=1, sticky=tk.W, pady=6, padx=(8, 0))

        # Điểm đi / đến
        tk.Label(container, text="Điểm khởi hành:",
                 font=("Segoe UI", 9, "bold"), bg=CLR_CARD
                 ).grid(row=4, column=0, sticky=tk.W, pady=6)
        self.cb_trip_from = ttk.Combobox(container, width=36, values=POPULAR_CITIES)
        self.cb_trip_from.set("Hà Nội")
        self.cb_trip_from.grid(row=4, column=1, sticky=tk.W, pady=6, padx=(8, 0))

        tk.Label(container, text="Điểm kết thúc:",
                 font=("Segoe UI", 9, "bold"), bg=CLR_CARD
                 ).grid(row=6, column=0, sticky=tk.W, pady=6)
        self.cb_trip_to = ttk.Combobox(container, width=36, values=POPULAR_CITIES)
        self.cb_trip_to.set("Đà Nẵng")
        self.cb_trip_to.grid(row=6, column=1, sticky=tk.W, pady=6, padx=(8, 0))

        tk.Button(
            container,
            text="➕  TẠO CHUYẾN XE VÀ KHỞI TẠO SƠ ĐỒ GHẾ",
            bg=CLR_BLUE, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=9, cursor="hand2",
            command=self._create_trip
        ).grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(24, 0))

    def _create_trip(self):
        bus_num  = self.ent_bus_num.get().strip()
        f_city   = self.cb_trip_from.get().strip()
        t_city   = self.cb_trip_to.get().strip()
        dep_time = self.ent_dep_time.get().strip()
        raw_p    = self.ent_price.get().strip()
        bus_type_raw = self.cb_bus_type.get()

        if not all([bus_num, f_city, t_city, dep_time, raw_p]):
            messagebox.showwarning("Thiếu thông tin",
                                   "Vui lòng nhập đầy đủ các trường!", parent=self)
            return
        try:
            price = int(raw_p)
        except ValueError:
            messagebox.showerror("Lỗi", "Giá vé phải là số nguyên!", parent=self)
            return

        total_seats = 34
        if "24" in bus_type_raw:
            total_seats = 24
        elif "29" in bus_type_raw:
            total_seats = 29

        trip_data = {
            "bus_number":     bus_num,
            "bus_type":       bus_type_raw.split("(")[0].strip(),
            "from_city":      f_city,
            "to_city":        t_city,
            "departure_time": dep_time,
            "price":          price,
            "total_seats":    total_seats,
        }

        def send():
            resp = self.client.admin_add_trip(trip_data)
            self.after(0, lambda: self._on_trip_created(resp))
        threading.Thread(target=send, daemon=True).start()

    def _on_trip_created(self, resp):
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Thành công", resp.get("message", "Đã tạo chuyến xe!"),
                                parent=self)
            self._load_dashboard()
        else:
            messagebox.showerror("Lỗi", resp.get("message", "Không thể tạo chuyến xe!"),
                                 parent=self)

    # ══════════════════════════════════════════════════════════
    #  TAB 7: QUẢN LÝ XE
    # ══════════════════════════════════════════════════════════
    def _build_tab_vehicles(self):
        toolbar = tk.Frame(self.tab_vehicles, bg=CLR_BG, pady=6)
        toolbar.pack(fill=tk.X, padx=15)

        tk.Button(
            toolbar, text="🔄 Tải lại",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=12, pady=5, cursor="hand2",
            command=self._load_vehicles
        ).pack(side=tk.LEFT, padx=(0, 8))

        # Chỉ Admin mới thêm/sửa/xóa xe
        role = (self.client.user_info or {}).get("role", "")
        if role == ROLE_ADMIN:
            tk.Button(
                toolbar, text="➕ Thêm xe",
                bg=CLR_GREEN, fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
                padx=12, pady=5, cursor="hand2",
                command=self._add_vehicle_dialog
            ).pack(side=tk.LEFT, padx=(0, 8))

            tk.Button(
                toolbar, text="🗑️ Xóa xe đã chọn",
                bg=CLR_RED, fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
                padx=12, pady=5, cursor="hand2",
                command=self._delete_vehicle
            ).pack(side=tk.LEFT)

        body = tk.Frame(self.tab_vehicles, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(4, 15))

        cols = ("id", "number", "type", "seats", "driver", "phone", "status")
        self.tree_vehicles = ttk.Treeview(body, columns=cols, show="headings", height=16)
        for col, txt, w in [
            ("id",     "ID",           45),
            ("number", "Biển số",     115),
            ("type",   "Loại xe",     180),
            ("seats",  "Chỗ ngồi",     75),
            ("driver", "Tài xế",      160),
            ("phone",  "SĐT TX",      115),
            ("status", "Trạng thái",   90),
        ]:
            self.tree_vehicles.heading(col, text=txt)
            self.tree_vehicles.column(col, width=w,
                anchor=tk.CENTER if col in ("id","seats","status") else tk.W)

        sy = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree_vehicles.yview)
        self.tree_vehicles.configure(yscrollcommand=sy.set)
        self.tree_vehicles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_vehicles(self):
        # Hiện trạng thái đang tải
        self.tree_vehicles.delete(*self.tree_vehicles.get_children())
        self.tree_vehicles.insert("", tk.END, values=("...", "⏳ Đang tải dữ liệu...", "", "", "", "", ""))

        def fetch():
            r = self.client.get_vehicles()
            self.after(0, lambda: self._apply_vehicles(r))
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_vehicles(self, resp):
        self.tree_vehicles.delete(*self.tree_vehicles.get_children())
        vehicles = resp.get("vehicles", [])
        if not vehicles:
            # Hiển thị dòng placeholder để user biết đang rỗng hay lỗi
            status_msg = resp.get("message", "")
            if resp.get("status") == "ERROR":
                self.tree_vehicles.insert("", tk.END, values=(
                    "—", "⚠️ Lỗi kết nối / chưa đăng nhập", status_msg, "", "", "", ""
                ))
            return
        for v in vehicles:
            self.tree_vehicles.insert("", tk.END, values=(
                v.get("id"), v.get("bus_number"), v.get("bus_type"),
                v.get("total_seats"), v.get("driver_name", ""),
                v.get("phone", ""), v.get("status", "ACTIVE")
            ))

    def _add_vehicle_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("➕ Thêm xe mới")
        dlg.geometry("420x380")
        dlg.resizable(False, False)
        dlg.configure(bg=CLR_CARD)
        dlg.grab_set()

        tk.Label(dlg, text="THÊM XE MỚI",
                 font=("Segoe UI", 11, "bold"), fg=CLR_TEXT, bg=CLR_CARD
                 ).pack(anchor=tk.W, padx=24, pady=(20, 10))

        frame = tk.Frame(dlg, bg=CLR_CARD, padx=24)
        frame.pack(fill=tk.X)

        fields_data = [
            ("Biển số xe:",      "ent_v_num",    "29B-999.00"),
            ("Loại xe:",         "ent_v_type",   "Giường nằm 34 phòng"),
            ("Số chỗ ngồi:",     "ent_v_seats",  "34"),
            ("Tên tài xế:",      "ent_v_driver", ""),
            ("SĐT tài xế:",      "ent_v_phone",  ""),
        ]
        entries = {}
        for i, (lbl, key, default) in enumerate(fields_data):
            tk.Label(frame, text=lbl,
                     font=("Segoe UI", 9), bg=CLR_CARD
                     ).grid(row=i, column=0, sticky=tk.W, pady=5)
            e = ttk.Entry(frame, width=28)
            if default:
                e.insert(0, default)
            e.grid(row=i, column=1, sticky=tk.W, pady=5, padx=(8, 0))
            entries[key] = e

        def do_add():
            try:
                seats = int(entries["ent_v_seats"].get().strip())
            except ValueError:
                messagebox.showerror("Lỗi", "Số chỗ phải là số nguyên!", parent=dlg)
                return
            v_data = {
                "bus_number":  entries["ent_v_num"].get().strip(),
                "bus_type":    entries["ent_v_type"].get().strip(),
                "total_seats": seats,
                "driver_name": entries["ent_v_driver"].get().strip(),
                "phone":       entries["ent_v_phone"].get().strip(),
            }
            if not v_data["bus_number"] or not v_data["bus_type"]:
                messagebox.showwarning("Thiếu thông tin",
                                       "Biển số và Loại xe là bắt buộc!", parent=dlg)
                return

            btn_add.config(state="disabled", text="⏳ Đang thêm...")

            def send():
                resp = self.client.admin_add_vehicle(v_data)
                self.after(0, lambda: on_result(resp))

            def on_result(resp):
                btn_add.config(state="normal", text="✅ Thêm xe")
                if resp.get("status") == "SUCCESS":
                    messagebox.showinfo("Thành công", "Đã thêm xe!", parent=dlg)
                    dlg.destroy()
                    self._load_vehicles()
                else:
                    messagebox.showerror("Lỗi",
                        resp.get("message", "Không thêm được! Kiểm tra biển số có bị trùng không."),
                        parent=dlg)

            threading.Thread(target=send, daemon=True).start()

        btn_add = tk.Button(
            dlg, text="✅ Thêm xe",
            bg=CLR_GREEN, fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=8, cursor="hand2", command=do_add
        )
        btn_add.pack(fill=tk.X, padx=24, pady=(16, 0))

    def _delete_vehicle(self):
        sel = self.tree_vehicles.selection()
        if not sel:
            messagebox.showinfo("Chưa chọn",
                                "Vui lòng chọn một xe trong danh sách!", parent=self)
            return
        values = self.tree_vehicles.item(sel[0], "values")
        v_id, v_num = int(values[0]), values[1]

        if not messagebox.askyesno(
            "Xác nhận xóa",
            f"Xóa xe {v_num} (ID={v_id}) khỏi hệ thống?\nHành động này không thể hoàn tác!",
            parent=self
        ):
            return

        resp = self.client.admin_delete_vehicle(v_id)
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Thành công", "Đã xóa xe!", parent=self)
            self._load_vehicles()
        else:
            messagebox.showerror("Lỗi", resp.get("message", "Không xóa được!"), parent=self)

    # ══════════════════════════════════════════════════════════
    #  TAB 8: NHẬT KÝ HỆ THỐNG
    # ══════════════════════════════════════════════════════════
    def _build_tab_logs(self):
        toolbar = tk.Frame(self.tab_logs, bg=CLR_BG, pady=6)
        toolbar.pack(fill=tk.X, padx=15)

        tk.Label(toolbar, text="Số bản ghi:",
                 font=("Segoe UI", 9), bg=CLR_BG).pack(side=tk.LEFT)
        self.cb_log_limit = ttk.Combobox(
            toolbar, width=8, state="readonly",
            values=["50", "100", "200", "500"]
        )
        self.cb_log_limit.set("100")
        self.cb_log_limit.pack(side=tk.LEFT, padx=4)

        tk.Button(
            toolbar, text="🔄 Tải nhật ký",
            bg="#334155", fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=12, pady=5, cursor="hand2",
            command=self._load_logs
        ).pack(side=tk.LEFT, padx=(4, 0))

        body = tk.Frame(self.tab_logs, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(4, 15))

        cols = ("id", "level", "action", "message", "ip", "time")
        self.tree_logs = ttk.Treeview(body, columns=cols, show="headings", height=16)
        for col, txt, w in [
            ("id",      "ID",        50),
            ("level",   "Mức độ",    70),
            ("action",  "Hành động", 130),
            ("message", "Nội dung",  340),
            ("ip",      "IP",         115),
            ("time",    "Thời gian", 140),
        ]:
            self.tree_logs.heading(col, text=txt)
            self.tree_logs.column(col, width=w,
                anchor=tk.CENTER if col in ("id","level","ip","time") else tk.W)

        sy = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree_logs.yview)
        self.tree_logs.configure(yscrollcommand=sy.set)
        self.tree_logs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_logs(self):
        try:
            limit = int(self.cb_log_limit.get())
        except ValueError:
            limit = 100

        self.tree_logs.delete(*self.tree_logs.get_children())
        self.tree_logs.insert("", tk.END, values=("...", "⏳ Đang tải...", "", "", "", ""))

        def fetch():
            r = self.client.admin_get_logs(limit)
            self.after(0, lambda: self._apply_logs(r))
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_logs(self, resp):
        self.tree_logs.delete(*self.tree_logs.get_children())
        if resp.get("status") == "ERROR":
            self.tree_logs.insert("", tk.END, values=(
                "—", "ERROR", "—", f"⚠️ {resp.get('message','Lỗi kết nối')}", "", ""
            ))
            return
        for log in resp.get("logs", []):
            self.tree_logs.insert("", tk.END, values=(
                log.get("id"), log.get("log_level", ""),
                log.get("action", ""), log.get("message", ""),
                log.get("client_ip", ""), log.get("created_at", "")
            ))

    # ══════════════════════════════════════════════════════════
    #  TIỆN ÍCH CHUNG
    # ══════════════════════════════════════════════════════════
    def _kpi_card(self, parent, title: str, value: str, color: str) -> tk.Frame:
        """Tạo một card KPI nhỏ."""
        f = tk.Frame(parent, bg=CLR_CARD, bd=1, relief=tk.SOLID, padx=14, pady=12)
        tk.Label(f, text=title,
                 font=("Segoe UI", 8, "bold"), fg=CLR_SUB, bg=CLR_CARD
                 ).pack(anchor=tk.W)
        val_lbl = tk.Label(f, text=value,
                           font=("Segoe UI", 14, "bold"), fg=color, bg=CLR_CARD)
        val_lbl.pack(anchor=tk.W, pady=(4, 0))
        f.val_lbl = val_lbl
        return f

    def _on_tab_changed(self, event):
        """Tải dữ liệu khi người dùng chuyển tab."""
        nb = event.widget
        idx = nb.index(nb.select())
        if idx == 0:
            self._load_dashboard()
        elif idx == 1:
            self._load_users()
        elif idx == 2:
            self._load_all_tickets()
        elif idx == 3:
            self._load_online_users()
        elif idx == 6:
            self._load_vehicles()
        elif idx == 7:
            self._load_logs()
        # Tab 4 (Thông Báo), 5 (Thêm Chuyến) không cần tải động

    def _refresh_all(self):
        """Làm mới dữ liệu trên tab hiện tại."""
        if not hasattr(self, "_notebook"):
            return
        idx = self._notebook.index(self._notebook.select())
        dispatch = {
            0: self._load_dashboard,
            1: self._load_users,
            2: self._load_all_tickets,
            3: self._load_online_users,
            6: self._load_vehicles,
            7: self._load_logs,
        }
        fn = dispatch.get(idx)
        if fn:
            fn()

    def _on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()


# ── Tương thích ngược: AdminWindow = CustomerCareWindow ──────
AdminWindow = CustomerCareWindow
