"""
client/gui_booking.py - Giao diện chính sau đăng nhập
Đặt vé, sơ đồ ghế real-time, voice call 2 chiều giữa mọi client
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.constants import (
    SEAT_AVAILABLE, SEAT_HOLDING, SEAT_BOOKED,
    ROLE_ADMIN, ROLE_STAFF, ROLE_DRIVER, ROLE_CUSTOMER,
    POPULAR_CITIES, HOLD_TIMEOUT_SECONDS,
    ACTION_VOICE_CALL_ANY,
)
from common.qr_generator import draw_qr_on_canvas
from client.gui_history import HistoryWindow
from client.gui_admin import AdminWindow
from client.gui_profile import ProfileWindow
from client.voice_call import IncomingCallDialog, CallingDialog

# ── Màu sắc theme ────────────────────────────────────────────
CLR_NAV      = "#0F172A"
CLR_NAV_TXT  = "#F8FAFC"
CLR_BG       = "#F1F5F9"
CLR_CARD     = "#FFFFFF"
CLR_ACCENT   = "#0EA5E9"
CLR_GREEN    = "#10B981"
CLR_RED      = "#EF4444"
CLR_ORANGE   = "#F59E0B"
CLR_MUTED    = "#94A3B8"

ROLE_COLOR = {
    ROLE_ADMIN:    "#7C3AED",
    ROLE_STAFF:    "#0284C7",
    ROLE_DRIVER:   "#059669",
    ROLE_CUSTOMER: "#475569",
}


class BookingWindow:
    def __init__(self, root, network_client, on_logout):
        self.root      = root
        self.client    = network_client
        self.on_logout = on_logout

        self.root.title("TrainBus — Hệ Thống Đặt Vé Xe Khách")
        self.root.geometry("1240x800")
        self.root.minsize(1050, 680)
        self.root.configure(bg=CLR_BG)

        # Trạng thái ghế
        self.current_trip      = None
        self.trip_seats        = {}
        self.my_selected_seats = set()
        self.held_seats        = []
        self.is_holding        = False
        self.hold_time_left    = 0
        self.timer_job         = None
        self.seat_buttons      = {}

        # Đăng ký callbacks real-time
        self.client.register_seat_update_callback(self._on_seat_broadcast)
        self.client.register_notification_callback(self._on_notification_broadcast)
        self.client.register_voice_call_callback(self._on_voice_call_broadcast)
        self.client.register_disconnect_callback(self._on_disconnected)
        self.client.register_reconnect_callback(self._on_reconnected)

        self._build_ui()
        self._load_trips()

    # ══════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_navbar()
        self._build_main_content()

    # ── Navbar ───────────────────────────────────────────────
    def _build_navbar(self):
        nav = tk.Frame(self.root, bg=CLR_NAV, height=58)
        nav.pack(fill=tk.X)
        nav.pack_propagate(False)

        u_info = self.client.user_info or {}
        role   = u_info.get("role", ROLE_CUSTOMER)

        # Logo
        tk.Label(
            nav, text="🚌  TRAINBUS",
            font=("Segoe UI", 13, "bold"), fg=CLR_ACCENT, bg=CLR_NAV
        ).pack(side=tk.LEFT, padx=(16, 6), pady=12)

        # Trạng thái mạng
        self.lbl_net = tk.Label(
            nav, text=f"🟢 {self.client.host}:{self.client.port}",
            font=("Segoe UI", 8), fg=CLR_GREEN, bg=CLR_NAV
        )
        self.lbl_net.pack(side=tk.LEFT, padx=4)

        # Tên user + badge role
        role_bg = ROLE_COLOR.get(role, "#475569")
        tk.Label(
            nav, text=f"  {role}  ",
            font=("Segoe UI", 7, "bold"), fg="#FFFFFF", bg=role_bg
        ).pack(side=tk.LEFT, padx=(10, 2), pady=18)

        tk.Label(
            nav, text=u_info.get("fullname", "User"),
            font=("Segoe UI", 9, "bold"), fg=CLR_NAV_TXT, bg=CLR_NAV
        ).pack(side=tk.LEFT, padx=2)

        # ── Nút bên phải (pack RIGHT, thứ tự ngược) ─────────
        def nav_btn(text, bg, cmd, side=tk.RIGHT, padx=4):
            b = tk.Button(
                nav, text=text, bg=bg, fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
                padx=10, pady=5, cursor="hand2",
                activeforeground="#FFFFFF", activebackground=bg,
                command=cmd
            )
            b.pack(side=side, padx=padx, pady=10)
            return b

        nav_btn("🚪 Đăng xuất",      CLR_RED,     self._do_logout)

        if role in (ROLE_ADMIN, ROLE_STAFF):
            nav_btn("🛡️ Quản trị",   "#7C3AED",   self._open_admin)

        nav_btn("🎫 Vé của tôi",     "#0284C7",   self._open_history)
        nav_btn("📊 Tài khoản",      "#334155",   self._open_profile)
        nav_btn("🚍 Đội xe",         "#475569",   self._open_vehicles_view)

        # Nút gọi — mọi user đều thấy
        self.btn_call = nav_btn(
            "📞 Gọi hỗ trợ", "#B45309", self._open_call_dialog
        )

    # ── Layout 2 cột ─────────────────────────────────────────
    def _build_main_content(self):
        main = tk.Frame(self.root, bg=CLR_BG, padx=10, pady=8)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Cột trái ─────────────────────────────────────────
        left = tk.Frame(main, bg=CLR_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Thanh tìm kiếm
        search_card = tk.Frame(left, bg=CLR_CARD, bd=0,
                               relief=tk.FLAT, pady=8, padx=10)
        search_card.pack(fill=tk.X, pady=(0, 8))
        _card_shadow(search_card)

        tk.Label(search_card, text="Tìm chuyến xe",
                 font=("Segoe UI", 9, "bold"), fg="#1E293B",
                 bg=CLR_CARD).grid(row=0, column=0, columnspan=5,
                                    sticky=tk.W, padx=2, pady=(0, 4))

        tk.Label(search_card, text="Điểm đi:", bg=CLR_CARD,
                 font=("Segoe UI", 8)).grid(row=1, column=0, sticky=tk.W, padx=2)
        self.cb_from = ttk.Combobox(
            search_card, width=13, values=["Tất cả"] + POPULAR_CITIES)
        self.cb_from.set("Tất cả")
        self.cb_from.grid(row=1, column=1, padx=2)

        tk.Label(search_card, text="Điểm đến:", bg=CLR_CARD,
                 font=("Segoe UI", 8)).grid(row=1, column=2, sticky=tk.W, padx=2)
        self.cb_to = ttk.Combobox(
            search_card, width=13, values=["Tất cả"] + POPULAR_CITIES)
        self.cb_to.set("Tất cả")
        self.cb_to.grid(row=1, column=3, padx=2)

        tk.Button(
            search_card, text="🔍 Tìm",
            bg=CLR_ACCENT, fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT,
            padx=12, pady=3, cursor="hand2",
            command=self._load_trips
        ).grid(row=1, column=4, padx=(6, 2))

        # Bảng chuyến xe
        trip_card = tk.Frame(left, bg=CLR_CARD)
        trip_card.pack(fill=tk.BOTH, expand=True)
        _card_shadow(trip_card)

        tk.Label(trip_card, text="Danh sách chuyến xe",
                 font=("Segoe UI", 9, "bold"), fg="#1E293B",
                 bg=CLR_CARD).pack(anchor=tk.W, padx=10, pady=(8, 4))

        # Style treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Trips.Treeview",
                         background=CLR_CARD, fieldbackground=CLR_CARD,
                         rowheight=28, font=("Segoe UI", 9))
        style.configure("Trips.Treeview.Heading",
                         background="#E2E8F0", font=("Segoe UI", 8, "bold"),
                         relief=tk.FLAT)
        style.map("Trips.Treeview",
                  background=[("selected", "#DBEAFE")])

        cols = ("id", "route", "bus_type", "dep_time", "price", "avail")
        self.tree_trips = ttk.Treeview(
            trip_card, columns=cols, show="headings",
            selectmode="browse", style="Trips.Treeview"
        )
        heads = [("id","ID",38), ("route","Tuyến xe",155),
                 ("bus_type","Loại xe",130), ("dep_time","Khởi hành",115),
                 ("price","Giá vé",90), ("avail","Còn trống",72)]
        for col, text, w in heads:
            self.tree_trips.heading(col, text=text)
            anchor = tk.E if col == "price" else (tk.CENTER if col in ("id","dep_time","avail") else tk.W)
            self.tree_trips.column(col, width=w, anchor=anchor)

        sb = ttk.Scrollbar(trip_card, orient=tk.VERTICAL,
                           command=self.tree_trips.yview)
        self.tree_trips.configure(yscrollcommand=sb.set)
        self.tree_trips.pack(side=tk.LEFT, fill=tk.BOTH,
                             expand=True, padx=(8, 0), pady=(0, 8))
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 8), padx=(0, 4))
        self.tree_trips.bind("<<TreeviewSelect>>", self._on_trip_selected)

        # ── Cột phải ─────────────────────────────────────────
        right = tk.Frame(main, bg=CLR_CARD, width=520)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)
        _card_shadow(right)

        # Header sơ đồ ghế
        hdr = tk.Frame(right, bg="#0F172A", pady=10, padx=12)
        hdr.pack(fill=tk.X)

        self.lbl_trip_info = tk.Label(
            hdr, text="CHỌN CHUYẾN XE ĐỂ XEM SƠ ĐỒ GHẾ",
            font=("Segoe UI", 11, "bold"), fg=CLR_ACCENT, bg="#0F172A"
        )
        self.lbl_trip_info.pack(anchor=tk.W)

        self.lbl_trip_sub = tk.Label(
            hdr, text="Ghế đồng bộ thời gian thực qua TCP Broadcast",
            font=("Segoe UI", 8), fg=CLR_MUTED, bg="#0F172A"
        )
        self.lbl_trip_sub.pack(anchor=tk.W)

        # Chú thích ghế
        leg = tk.Frame(right, bg="#F8FAFC", pady=5)
        leg.pack(fill=tk.X)
        for color, text in [("#10B981","Trống"), ("#3B82F6","Đang chọn"),
                             ("#F59E0B","Giữ chỗ"), ("#EF4444","Đã bán")]:
            f = tk.Frame(leg, bg="#F8FAFC")
            f.pack(side=tk.LEFT, expand=True)
            tk.Label(f, bg=color, width=2, height=1,
                     relief=tk.SOLID, bd=1).pack(side=tk.LEFT, padx=3)
            tk.Label(f, text=text, font=("Segoe UI", 8),
                     bg="#F8FAFC", fg="#334155").pack(side=tk.LEFT)

        # Vùng ghế có scrollbar
        seat_outer = tk.Frame(right, bg=CLR_CARD)
        seat_outer.pack(fill=tk.BOTH, expand=True)

        seat_vsb = ttk.Scrollbar(seat_outer, orient=tk.VERTICAL)
        seat_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.seat_canvas = tk.Canvas(
            seat_outer, bg=CLR_CARD, highlightthickness=0,
            yscrollcommand=seat_vsb.set
        )
        self.seat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        seat_vsb.config(command=self.seat_canvas.yview)

        self.seat_scroll_frame = tk.Frame(self.seat_canvas, bg=CLR_CARD)
        self._seat_win_id = self.seat_canvas.create_window(
            (0, 0), window=self.seat_scroll_frame, anchor="nw"
        )
        self.seat_scroll_frame.bind(
            "<Configure>",
            lambda e: self.seat_canvas.configure(
                scrollregion=self.seat_canvas.bbox("all")
            )
        )
        self.seat_canvas.bind(
            "<Configure>",
            lambda e: self.seat_canvas.itemconfig(
                self._seat_win_id, width=e.width
            )
        )

        # Bottom bar
        self.bottom_bar = tk.Frame(right, bg="#F8FAFC",
                                   bd=1, relief=tk.SOLID,
                                   padx=12, pady=8)
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_countdown = tk.Label(
            self.bottom_bar, text="",
            font=("Segoe UI", 9, "bold"), fg="#D97706", bg="#F8FAFC"
        )
        self.lbl_countdown.pack(anchor=tk.W, pady=(0, 2))

        row_info = tk.Frame(self.bottom_bar, bg="#F8FAFC")
        row_info.pack(fill=tk.X)

        self.lbl_selected = tk.Label(
            row_info, text="Chưa chọn ghế",
            font=("Segoe UI", 9), fg="#1E293B", bg="#F8FAFC"
        )
        self.lbl_selected.pack(side=tk.LEFT)

        self.lbl_price = tk.Label(
            row_info, text="0 VNĐ",
            font=("Segoe UI", 12, "bold"), fg="#DC2626", bg="#F8FAFC"
        )
        self.lbl_price.pack(side=tk.RIGHT)

        self.btn_hold_pay = tk.Button(
            self.bottom_bar,
            text="🔒 Giữ Chỗ & Thanh Toán",
            bg="#059669", fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT, pady=8, cursor="hand2",
            state=tk.DISABLED,
            command=self._on_hold_and_pay_clicked
        )
        self.btn_hold_pay.pack(fill=tk.X, pady=(6, 0))

    # ══════════════════════════════════════════════════════════
    #  CHUYẾN XE
    # ══════════════════════════════════════════════════════════
    def _load_trips(self):
        fc = self.cb_from.get()
        tc = self.cb_to.get()
        resp = self.client.get_trips(
            from_city=fc if fc != "Tất cả" else None,
            to_city=tc   if tc != "Tất cả" else None
        )
        if resp.get("status") == "SUCCESS":
            self.tree_trips.delete(*self.tree_trips.get_children())
            for t in resp.get("data", []):
                route  = f"{t['from_city']} ➔ {t['to_city']}"
                price  = f"{t['price']:,} đ".replace(",", ".")
                avail  = f"{t['available_seats']}/{t['total_seats']}"
                self.tree_trips.insert(
                    "", tk.END, iid=str(t["id"]),
                    values=(t["id"], route, t["bus_type"],
                            t["departure_time"], price, avail)
                )

    def _on_trip_selected(self, event):
        sel = self.tree_trips.selection()
        if not sel:
            return
        if self.is_holding:
            self._cancel_hold_timer()
        trip_id = int(sel[0])
        resp = self.client.get_seats(trip_id)
        if resp.get("status") == "SUCCESS":
            self.current_trip = trip_id
            self.trip_seats   = resp.get("seats", {})
            self.my_selected_seats.clear()
            self._render_seat_map()
            self._update_summary()

    # ══════════════════════════════════════════════════════════
    #  SƠ ĐỒ GHẾ
    # ══════════════════════════════════════════════════════════
    def _render_seat_map(self):
        for w in self.seat_scroll_frame.winfo_children():
            w.destroy()
        self.seat_buttons.clear()

        vals = self.tree_trips.item(str(self.current_trip)).get("values", [])
        if vals:
            self.lbl_trip_info.config(
                text=f"CHUYẾN #{self.current_trip}: {vals[1]}")
            self.lbl_trip_sub.config(
                text=f"🚌 {vals[2]}  |  ⏰ {vals[3]}  |  💰 {vals[4]}/vé")

        seats = self.trip_seats
        wrap  = tk.Frame(self.seat_scroll_frame, bg="#F1F5F9",
                         bd=1, relief=tk.GROOVE, padx=10, pady=8)
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Buồng lái
        cab = tk.Frame(wrap, bg="#CBD5E1", height=26)
        cab.pack(fill=tk.X, pady=(0, 8))
        tk.Label(cab, text="🚗 Buồng lái",
                 font=("Segoe UI", 8, "bold"),
                 fg="#1E293B", bg="#CBD5E1").pack(side=tk.LEFT, padx=6)
        tk.Label(cab, text="🚪 Cửa",
                 font=("Segoe UI", 8, "bold"),
                 fg="#1E293B", bg="#CBD5E1").pack(side=tk.RIGHT, padx=6)

        has_two = any(s.startswith("B") for s in seats)
        if has_two:
            ff = tk.Frame(wrap, bg="#F1F5F9")
            ff.pack(fill=tk.BOTH, expand=True)
            f1 = tk.LabelFrame(ff, text="Tầng 1 (dưới)",
                                font=("Segoe UI", 8, "bold"),
                                bg=CLR_CARD, padx=6, pady=6)
            f1.pack(side=tk.LEFT, fill=tk.BOTH,
                    expand=True, padx=(0, 4))
            f2 = tk.LabelFrame(ff, text="Tầng 2 (trên)",
                                font=("Segoe UI", 8, "bold"),
                                bg=CLR_CARD, padx=6, pady=6)
            f2.pack(side=tk.RIGHT, fill=tk.BOTH,
                    expand=True, padx=(4, 0))
            self._populate_grid(f1, [s for s in sorted(seats) if s.startswith("A")])
            self._populate_grid(f2, [s for s in sorted(seats) if s.startswith("B")])
        else:
            gf = tk.Frame(wrap, bg=CLR_CARD, padx=8, pady=8)
            gf.pack(fill=tk.BOTH, expand=True)
            self._populate_grid(gf, sorted(seats), cols=4)

    def _populate_grid(self, parent, seat_list, cols=3):
        r = c = 0
        for sn in seat_list:
            st = self.trip_seats.get(sn, SEAT_AVAILABLE)
            btn = tk.Button(
                parent, text=sn, width=5, height=2,
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT, bd=1, cursor="hand2",
                command=lambda s=sn: self._on_seat_clicked(s)
            )
            btn.grid(row=r, column=c, padx=3, pady=3, sticky=tk.NSEW)
            parent.grid_columnconfigure(c, weight=1)
            self.seat_buttons[sn] = btn
            self._apply_seat_style(sn, st)
            c += 1
            if c >= cols:
                c = 0
                r += 1

    def _apply_seat_style(self, sn, status):
        btn = self.seat_buttons.get(sn)
        if not btn:
            return
        if sn in self.my_selected_seats:
            btn.config(bg="#3B82F6", fg="#FFFFFF", state=tk.NORMAL)
        elif status == SEAT_AVAILABLE:
            btn.config(bg="#10B981", fg="#FFFFFF", state=tk.NORMAL)
        elif status == SEAT_HOLDING:
            btn.config(bg="#F59E0B", fg="#1E293B", state=tk.DISABLED)
        elif status == SEAT_BOOKED:
            btn.config(bg="#EF4444", fg="#FFFFFF", state=tk.DISABLED)

    def _on_seat_clicked(self, sn):
        st = self.trip_seats.get(sn, SEAT_AVAILABLE)
        if st == SEAT_BOOKED:
            messagebox.showinfo("Ghế đã bán",
                                f"Ghế {sn} đã có người đặt!")
            return
        if st == SEAT_HOLDING and sn not in self.my_selected_seats:
            messagebox.showinfo("Ghế đang giữ",
                                f"Ghế {sn} đang được người khác giữ chỗ!")
            return
        if sn in self.my_selected_seats:
            self.my_selected_seats.remove(sn)
        else:
            self.my_selected_seats.add(sn)
        self._apply_seat_style(sn, st)
        self._update_summary()

    def _update_summary(self):
        sel   = sorted(self.my_selected_seats)
        count = len(sel)
        if count == 0:
            self.lbl_selected.config(text="Chưa chọn ghế")
            self.lbl_price.config(text="0 VNĐ")
            self.btn_hold_pay.config(state=tk.DISABLED,
                                     text="🔒 Giữ Chỗ & Thanh Toán")
        else:
            self.lbl_selected.config(
                text=f"Ghế: {', '.join(sel)}  ({count} ghế)")
            vals  = self.tree_trips.item(str(self.current_trip)).get("values", [])
            price = 350000
            if vals and len(vals) >= 5:
                raw = str(vals[4]).replace(" đ","").replace(".","").replace(",","").strip()
                if raw.isdigit():
                    price = int(raw)
            total = price * count
            self.lbl_price.config(
                text=f"{total:,} VNĐ".replace(",", "."))
            self.btn_hold_pay.config(
                state=tk.NORMAL,
                text=f"🔒 Giữ {count} ghế & Thanh Toán")

    # ══════════════════════════════════════════════════════════
    #  GIỮ CHỖ & THANH TOÁN
    # ══════════════════════════════════════════════════════════
    def _on_hold_and_pay_clicked(self):
        if not self.my_selected_seats or not self.current_trip:
            return
        seats = sorted(self.my_selected_seats)
        resp  = self.client.hold_seats(self.current_trip, seats)
        if resp.get("status") == "SUCCESS":
            self.is_holding     = True
            self.held_seats     = seats
            self.hold_time_left = resp.get("hold_timeout_seconds",
                                           HOLD_TIMEOUT_SECONDS)
            self._start_countdown()
            self._open_payment_dialog(seats)
        else:
            messagebox.showerror("Giữ chỗ thất bại",
                                 resp.get("message", "Ghế đã có người chọn trước!"))
            self._refresh_seats()

    def _start_countdown(self):
        if self.timer_job:
            self.root.after_cancel(self.timer_job)

        def tick():
            if not self.is_holding:
                self.lbl_countdown.config(text="")
                return
            if self.hold_time_left > 0:
                m, s = divmod(self.hold_time_left, 60)
                self.lbl_countdown.config(
                    text=f"⏳ Đang giữ chỗ — hết hạn sau {m:02d}:{s:02d}",
                    fg="#D97706"
                )
                self.hold_time_left -= 1
                self.timer_job = self.root.after(1000, tick)
            else:
                self.is_holding = False
                self.lbl_countdown.config(
                    text="⚠️ Hết thời gian giữ chỗ! Vui lòng chọn lại.",
                    fg=CLR_RED
                )
                messagebox.showwarning(
                    "Hết hạn giữ chỗ",
                    "Thời gian giữ chỗ đã hết.\nVui lòng chọn lại ghế!"
                )
                self._cancel_hold_timer()
                self._refresh_seats()

        tick()

    def _cancel_hold_timer(self):
        self.is_holding = False
        if self.timer_job:
            try:
                self.root.after_cancel(self.timer_job)
            except Exception:
                pass
            self.timer_job = None
        try:
            self.lbl_countdown.config(text="")
        except Exception:
            pass

    def _refresh_seats(self):
        if not self.current_trip:
            return
        resp = self.client.get_seats(self.current_trip)
        if resp.get("status") == "SUCCESS":
            self.trip_seats = resp.get("seats", {})
            self.my_selected_seats.clear()
            self._render_seat_map()
            self._update_summary()

    # ══════════════════════════════════════════════════════════
    #  DIALOG THANH TOÁN
    # ══════════════════════════════════════════════════════════
    def _open_payment_dialog(self, seats: list):
        dlg = tk.Toplevel(self.root)
        dlg.title("Thanh Toán & Xuất Vé — VietQR")
        dlg.geometry("560x680")
        dlg.resizable(False, False)
        dlg.configure(bg="#F8FAFC")
        dlg.grab_set()

        vals      = self.tree_trips.item(str(self.current_trip)).get("values", [])
        route     = vals[1] if vals else ""
        dep_time  = vals[3] if len(vals) > 3 else ""
        price_str = vals[4] if len(vals) > 4 else "350.000 đ"
        raw_price = int(str(price_str).replace(" đ","").replace(".","")
                                      .replace(",","").strip())
        total     = raw_price * len(seats)

        # Header
        hdr = tk.Frame(dlg, bg="#0F172A", height=50)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="THANH TOÁN ĐẶT VÉ TRỰC TUYẾN",
                 font=("Segoe UI", 11, "bold"), fg=CLR_ACCENT,
                 bg="#0F172A").pack(pady=13)

        body = tk.Frame(dlg, bg="#F8FAFC", padx=18, pady=8)
        body.pack(fill=tk.BOTH, expand=True)

        # Thông tin vé
        s_box = tk.LabelFrame(body, text="Thông tin chuyến",
                               font=("Segoe UI", 9, "bold"),
                               bg=CLR_CARD, padx=10, pady=6)
        s_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(s_box, text=f"{route}  |  {dep_time}",
                 font=("Segoe UI", 9), bg=CLR_CARD).pack(anchor=tk.W)
        tk.Label(s_box, text=f"Ghế: {', '.join(seats)}",
                 font=("Segoe UI", 10, "bold"), fg="#2563EB",
                 bg=CLR_CARD).pack(anchor=tk.W)
        tk.Label(s_box,
                 text=f"Tổng tiền: {total:,} VNĐ".replace(",", "."),
                 font=("Segoe UI", 11, "bold"), fg=CLR_RED,
                 bg=CLR_CARD).pack(anchor=tk.W)

        # Hành khách
        u = self.client.user_info or {}
        p_box = tk.LabelFrame(body, text="Thông tin hành khách",
                               font=("Segoe UI", 9, "bold"),
                               bg=CLR_CARD, padx=10, pady=6)
        p_box.pack(fill=tk.X, pady=(0, 8))

        def lbl_ent(parent, text, row, default=""):
            tk.Label(parent, text=text, bg=CLR_CARD,
                     font=("Segoe UI", 8)).grid(row=row, column=0,
                                                 sticky=tk.W, pady=2)
            e = ttk.Entry(parent, width=34)
            e.insert(0, default)
            e.grid(row=row, column=1, padx=6, pady=2)
            return e

        ent_name  = lbl_ent(p_box, "Họ và tên:", 0, u.get("fullname",""))
        ent_phone = lbl_ent(p_box, "Số điện thoại:", 1, u.get("phone",""))
        ent_email = lbl_ent(p_box, "Email:", 2, u.get("email",""))

        # QR
        qr_box = tk.LabelFrame(body, text="Quét mã VietQR (NAPAS 247)",
                                font=("Segoe UI", 9, "bold"),
                                bg=CLR_CARD, padx=10, pady=6)
        qr_box.pack(fill=tk.BOTH, expand=True)

        cv = tk.Canvas(qr_box, width=160, height=160,
                       bg=CLR_CARD, highlightthickness=0)
        cv.pack(side=tk.LEFT, padx=8)
        qr_text = (f"VIETQR|VCB|0909123456|{total}"
                   f"|TRAINBUS_{self.current_trip}_{'_'.join(seats)}")
        draw_qr_on_canvas(cv, qr_text, x=5, y=5, width=150)

        inf = tk.Frame(qr_box, bg=CLR_CARD)
        inf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        for txt, fg, fnt in [
            ("VIETCOMBANK", "#059669", ("Segoe UI", 9, "bold")),
            ("STK: 0909 123 456", "#1E293B", ("Segoe UI", 10, "bold")),
            ("Chủ TK: TRAINBUS",  "#1E293B", ("Segoe UI", 8)),
            (f"{total:,} đ".replace(",","."), CLR_RED, ("Segoe UI", 11, "bold")),
            (f"ND: VE_{self.current_trip}_{seats[0]}", "#2563EB", ("Segoe UI", 8,"bold")),
        ]:
            tk.Label(inf, text=txt, font=fnt, fg=fg,
                     bg=CLR_CARD).pack(anchor=tk.W, pady=1)

        # Nút xác nhận / huỷ
        btn_row = tk.Frame(dlg, bg="#F1F5F9", padx=14, pady=8)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM)

        def do_confirm():
            pdata = {
                "name":  ent_name.get().strip(),
                "phone": ent_phone.get().strip(),
                "email": ent_email.get().strip()
            }
            if not pdata["name"] or not pdata["phone"]:
                messagebox.showwarning("Thiếu thông tin",
                                       "Vui lòng nhập Họ tên và Số điện thoại!",
                                       parent=dlg)
                return
            resp = self.client.confirm_booking(
                trip_id=self.current_trip,
                seats=seats,
                passenger_info=pdata,
                payment_method="VIETQR"
            )
            if resp.get("status") == "SUCCESS":
                self._cancel_hold_timer()
                dlg.destroy()
                messagebox.showinfo(
                    "Đặt vé thành công 🎉",
                    f"Mã vé: {resp.get('booking_code')}\n"
                    f"Ghế: {resp.get('seats')}\n"
                    f"Tổng tiền: {resp.get('total_amount'):,} VNĐ\n\n"
                    f"Vé điện tử đã sẵn sàng trong 'Vé của tôi'!"
                )
                self.my_selected_seats.clear()
                self._refresh_seats()
                self._open_history()
            else:
                messagebox.showerror("Đặt vé thất bại",
                                     resp.get("message","Lỗi xác nhận!"),
                                     parent=dlg)

        def do_cancel():
            self.client.release_seats(self.current_trip, seats)
            self._cancel_hold_timer()
            dlg.destroy()
            self.my_selected_seats.clear()
            self._refresh_seats()

        tk.Button(
            btn_row, text="✅  Đã chuyển khoản — Xác nhận đặt vé",
            bg="#059669", fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=8, cursor="hand2", command=do_confirm
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        tk.Button(
            btn_row, text="❌  Huỷ",
            bg="#94A3B8", fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            pady=8, cursor="hand2", command=do_cancel
        ).pack(side=tk.RIGHT)

    # ══════════════════════════════════════════════════════════
    #  VOICE CALL — gọi tới bất kỳ user online
    # ══════════════════════════════════════════════════════════
    def _open_call_dialog(self):
        """Mở dialog chọn user online để gọi."""
        self.btn_call.config(state=tk.DISABLED, text="⏳ Đang tải...")

        def fetch():
            resp = self.client.admin_get_online_users()
            self.root.after(0, lambda: self._show_call_picker(resp))

        threading.Thread(target=fetch, daemon=True).start()

    def _show_call_picker(self, resp):
        """Hiển thị cửa sổ chọn người muốn gọi."""
        try:
            self.btn_call.config(state=tk.NORMAL, text="📞 Gọi hỗ trợ")
        except Exception:
            pass

        my_username = (self.client.user_info or {}).get("username", "")
        # Chỉ hiển thị nhân viên Chăm Sóc Khách Hàng (Admin/Staff) để khách gọi đúng người hỗ trợ
        online = [u for u in resp.get("online_users", [])
                  if u.get("username") != my_username
                  and u.get("role") in (ROLE_ADMIN, ROLE_STAFF)]

        if not online:
            messagebox.showinfo(
                "Không có nhân viên online",
                "Hiện chưa có nhân viên Chăm Sóc Khách Hàng nào đang trực tuyến.\n"
                "Vui lòng thử lại sau hoặc gọi hotline hỗ trợ!"
            )
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("📞  Gọi Nhân Viên Hỗ Trợ")
        dlg.geometry("420x460")
        dlg.resizable(False, False)
        dlg.configure(bg="#0F172A")
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        # Header
        tk.Frame(dlg, bg="#0EA5E9", height=4).pack(fill=tk.X)
        tk.Label(dlg, text="NHÂN VIÊN CHĂM SÓC KHÁCH HÀNG",
                 font=("Segoe UI", 11, "bold"), fg="#F1F5F9",
                 bg="#0F172A").pack(pady=(14, 4))
        tk.Label(dlg, text="Chọn nhân viên đang trực tuyến để được hỗ trợ",
                 font=("Segoe UI", 9), fg="#64748B",
                 bg="#0F172A").pack(pady=(0, 10))

        # Danh sách user
        list_frame = tk.Frame(dlg, bg="#1E293B")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        role_icons = {
            ROLE_ADMIN:    "🛡️",
            ROLE_STAFF:    "🎫",
            ROLE_DRIVER:   "🚌",
            ROLE_CUSTOMER: "👤",
        }
        role_colors = {
            ROLE_ADMIN:    "#7C3AED",
            ROLE_STAFF:    "#0284C7",
            ROLE_DRIVER:   "#059669",
            ROLE_CUSTOMER: "#475569",
        }

        def make_call(u):
            dlg.destroy()
            self._do_call(u["username"], u.get("fullname", u["username"]))

        for u in online:
            role  = u.get("role", ROLE_CUSTOMER)
            icon  = role_icons.get(role, "👤")
            rbg   = role_colors.get(role, "#475569")
            row   = tk.Frame(list_frame, bg="#1E293B",
                             cursor="hand2", pady=2)
            row.pack(fill=tk.X, padx=2, pady=2)

            # Avatar vòng tròn màu role
            av = tk.Label(row, text=icon,
                          font=("Segoe UI Emoji", 16),
                          fg="#FFFFFF", bg=rbg,
                          width=3, height=1)
            av.pack(side=tk.LEFT, padx=(6, 10), pady=4)

            info = tk.Frame(row, bg="#1E293B")
            info.pack(side=tk.LEFT, fill=tk.X, expand=True)

            nm = tk.Label(info,
                          text=u.get("fullname", u["username"]),
                          font=("Segoe UI", 10, "bold"),
                          fg="#F1F5F9", bg="#1E293B",
                          anchor=tk.W)
            nm.pack(fill=tk.X)

            sub = tk.Label(info,
                           text=f"@{u['username']}  •  {role}",
                           font=("Segoe UI", 8),
                           fg="#64748B", bg="#1E293B",
                           anchor=tk.W)
            sub.pack(fill=tk.X)

            # Badge "Gọi"
            call_btn = tk.Button(
                row, text="📞 Gọi",
                bg="#10B981", fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT, padx=10, pady=4,
                cursor="hand2",
                command=lambda uu=u: make_call(uu)
            )
            call_btn.pack(side=tk.RIGHT, padx=8)

            # Click cả row cũng gọi
            for widget in (row, info, nm, sub, av):
                widget.bind("<Button-1>", lambda e, uu=u: make_call(uu))
                widget.bind("<Enter>",
                            lambda e, r=row: r.config(bg="#334155"))
                widget.bind("<Leave>",
                            lambda e, r=row: r.config(bg="#1E293B"))

        # Nút đóng
        tk.Button(
            dlg, text="✕  Đóng",
            bg="#334155", fg=CLR_MUTED,
            font=("Segoe UI", 9), relief=tk.FLAT,
            pady=6, cursor="hand2",
            command=dlg.destroy
        ).pack(fill=tk.X, padx=16, pady=(0, 14))

    def _do_call(self, target_username: str, target_name: str):
        """Gửi yêu cầu gọi và mở CallingDialog (chờ bắt máy)."""
        def call_worker():
            resp = self.client.send_request({
                "action": ACTION_VOICE_CALL_ANY,
                "target_username": target_username
            })
            def on_result():
                if resp.get("status") == "SUCCESS":
                    call_id = resp.get("call_id")
                    CallingDialog(self.root, self.client,
                                  call_id, target_name, target_username)
                else:
                    messagebox.showerror(
                        "Gọi thất bại",
                        resp.get("message",
                                 "Không thể kết nối. Vui lòng thử lại!")
                    )
            self.root.after(0, on_result)

        threading.Thread(target=call_worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════
    #  REAL-TIME CALLBACKS
    # ══════════════════════════════════════════════════════════
    def _on_seat_broadcast(self, trip_id, updated_seats):
        def upd():
            if self.current_trip != trip_id:
                return
            for sn, st in updated_seats.items():
                self.trip_seats[sn] = st
                if (sn in self.my_selected_seats
                        and st != SEAT_AVAILABLE
                        and not self.is_holding):
                    self.my_selected_seats.discard(sn)
                    self._update_summary()
                self._apply_seat_style(sn, st)
        self.root.after(0, upd)

    def _on_notification_broadcast(self, title, message):
        def show():
            messagebox.showinfo(f"🔔 {title}", message)
        self.root.after(0, show)

    def _on_voice_call_broadcast(self, evt: str, msg: dict):
        """Xử lý tất cả sự kiện voice call đến từ server."""
        if evt == "VOICE_CALL_INCOMING":
            call_id         = msg.get("call_id")
            caller_name     = msg.get("caller_name", "Ai đó")
            caller_username = msg.get("caller_username", "")

            def show():
                IncomingCallDialog(
                    self.root, self.client,
                    call_id, caller_name, caller_username
                )
            self.root.after(0, show)
        # ACCEPTED / REJECTED / ENDED được xử lý bên trong
        # CallingDialog và ActiveCallDialog qua callback riêng của chúng

    def _on_disconnected(self):
        def upd():
            self.lbl_net.config(
                text="🟡 Đang kết nối lại...", fg=CLR_ORANGE)
        self.root.after(0, upd)

    def _on_reconnected(self):
        def upd():
            self.lbl_net.config(
                text=f"🟢 {self.client.host}:{self.client.port}",
                fg=CLR_GREEN)
            self._load_trips()
            self._refresh_seats()
        self.root.after(0, upd)

    # ══════════════════════════════════════════════════════════
    #  CÁC CỬA SỔ PHỤ
    # ══════════════════════════════════════════════════════════
    def _open_history(self):
        HistoryWindow(self.root, self.client)

    def _open_admin(self):
        AdminWindow(self.root, self.client)

    def _open_profile(self):
        ProfileWindow(self.root, self.client)

    def _open_vehicles_view(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🚍  Đội xe TrainBus")
        dlg.geometry("760x440")
        dlg.configure(bg="#F8FAFC")

        tk.Frame(dlg, bg=CLR_ACCENT, height=4).pack(fill=tk.X)
        tk.Label(dlg, text="DANH SÁCH ĐỘI XE KHÁCH TRAINBUS",
                 font=("Segoe UI", 12, "bold"), fg=CLR_ACCENT,
                 bg="#0F172A", pady=10).pack(fill=tk.X)

        cols = ("id","number","type","seats","driver","phone","status")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for c, t, w in [("id","ID",40),("number","Biển số",105),
                         ("type","Loại xe",155),("seats","Chỗ",55),
                         ("driver","Tài xế",140),("phone","SĐT",110),
                         ("status","Trạng thái",95)]:
            tree.heading(c, text=t)
            tree.column(c, width=w,
                        anchor=tk.CENTER if c in ("id","seats","status") else tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        resp = self.client.get_vehicles()
        if resp.get("status") == "SUCCESS":
            for v in resp.get("vehicles", []):
                tree.insert("", tk.END, values=(
                    v["id"], v["bus_number"], v["bus_type"],
                    v["total_seats"], v.get("driver_name",""),
                    v.get("phone",""), v.get("status","ACTIVE")
                ))

    def _do_logout(self):
        if not messagebox.askyesno("Đăng xuất",
                                   "Bạn chắc chắn muốn đăng xuất?"):
            return
        if self.is_holding and self.held_seats and self.current_trip:
            self.client.release_seats(self.current_trip, self.held_seats)
        self._cancel_hold_timer()
        self.client.logout()
        self.on_logout()


# ── Tiện ích tạo shadow card ─────────────────────────────────
def _card_shadow(frame: tk.Frame):
    """Thêm border nhẹ giả shadow cho card."""
    frame.config(bd=1, relief=tk.SOLID,
                 highlightbackground="#E2E8F0",
                 highlightthickness=1)
