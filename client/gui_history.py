"""
client/gui_history.py - Giao diện Quản lý Lịch sử Vé Đã Đặt & Mã QR Check-in Tra Cứu
Theo mục III.2.d và IV.6 trong result.txt
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.qr_generator import draw_qr_on_canvas

class HistoryWindow(tk.Toplevel):
    def __init__(self, parent, network_client):
        super().__init__(parent)
        self.client = network_client
        self.title("Lịch Sử Vé Xe Đã Đặt - E-Ticket")
        self.geometry("980x640")
        self.minsize(850, 550)
        self.configure(bg="#F8FAFC")

        self.tickets = []
        self.selected_ticket = None

        self._build_ui()
        self._load_tickets()

    def _build_ui(self):
        # 1. Header
        header = tk.Frame(self, bg="#1E293B", height=65)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title = tk.Label(
            header, text="🎫 VÉ XE CỦA TÔI & MÃ CHECK-IN ĐIỆN TỬ",
            font=("Segoe UI", 14, "bold"), fg="#38BDF8", bg="#1E293B"
        )
        title.pack(side=tk.LEFT, padx=20, pady=15)

        btn_refresh = tk.Button(
            header, text="🔄 Làm mới", bg="#334155", fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=5,
            cursor="hand2", command=self._load_tickets
        )
        btn_refresh.pack(side=tk.RIGHT, padx=20)

        # 2. Body: Split Pane (Bên trái: Danh sách vé, Bên phải: Chi tiết vé Boarding Pass)
        body = tk.Frame(self, bg="#F8FAFC", padx=15, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(body, bg="#FFFFFF", bd=1, relief=tk.SOLID)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        lbl_list = tk.Label(
            left_frame, text="Danh sách vé đã đặt:",
            font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#1E293B"
        )
        lbl_list.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Bảng Treeview danh sách vé
        cols = ("code", "route", "seats", "total", "status")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("code", text="Mã vé")
        self.tree.heading("route", text="Tuyến đường")
        self.tree.heading("seats", text="Ghế")
        self.tree.heading("total", text="Tổng tiền")
        self.tree.heading("status", text="Trạng thái")

        self.tree.column("code", width=130, anchor=tk.CENTER)
        self.tree.column("route", width=140, anchor=tk.W)
        self.tree.column("seats", width=80, anchor=tk.CENTER)
        self.tree.column("total", width=100, anchor=tk.E)
        self.tree.column("status", width=90, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))

        self.tree.bind("<<TreeviewSelect>>", self._on_ticket_selected)

        # 3. Chi tiết vé bên phải (Card phong cách Boarding Pass)
        right_frame = tk.Frame(body, bg="#FFFFFF", width=380, bd=1, relief=tk.SOLID)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(0, 0))
        right_frame.pack_propagate(False)

        card_title = tk.Label(
            right_frame, text="THÔNG TIN VÉ ĐIỆN TỬ",
            font=("Segoe UI", 11, "bold"), bg="#0F172A", fg="#38BDF8", pady=8
        )
        card_title.pack(fill=tk.X)

        self.card_content = tk.Frame(right_frame, bg="#FFFFFF", padx=15, pady=10)
        self.card_content.pack(fill=tk.BOTH, expand=True)

        self.lbl_card_code = tk.Label(self.card_content, text="MÃ VÉ: ---", font=("Segoe UI", 12, "bold"), fg="#2563EB", bg="#FFFFFF")
        self.lbl_card_code.pack(anchor=tk.W, pady=(0, 5))

        self.lbl_card_route = tk.Label(self.card_content, text="Tuyến: ---", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#1E293B")
        self.lbl_card_route.pack(anchor=tk.W)

        self.lbl_card_time = tk.Label(self.card_content, text="Khởi hành: ---", font=("Segoe UI", 9), bg="#FFFFFF", fg="#475569")
        self.lbl_card_time.pack(anchor=tk.W)

        self.lbl_card_bus = tk.Label(self.card_content, text="Loại xe: ---", font=("Segoe UI", 9), bg="#FFFFFF", fg="#475569")
        self.lbl_card_bus.pack(anchor=tk.W)

        self.lbl_card_seats = tk.Label(self.card_content, text="Ghế: ---", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#059669")
        self.lbl_card_seats.pack(anchor=tk.W, pady=(5, 0))

        self.lbl_card_passenger = tk.Label(self.card_content, text="Hành khách: ---", font=("Segoe UI", 9), bg="#FFFFFF", fg="#334155")
        self.lbl_card_passenger.pack(anchor=tk.W)

        self.lbl_card_amount = tk.Label(self.card_content, text="Tổng tiền: ---", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#DC2626")
        self.lbl_card_amount.pack(anchor=tk.W, pady=(5, 5))

        self.lbl_card_status = tk.Label(self.card_content, text="Trạng thái: ---", font=("Segoe UI", 10, "bold"), bg="#FFFFFF")
        self.lbl_card_status.pack(anchor=tk.W)

        # Canvas vẽ mã QR xác thực vé
        qr_box = tk.Frame(self.card_content, bg="#FFFFFF")
        qr_box.pack(pady=10)
        
        self.qr_canvas = tk.Canvas(qr_box, width=160, height=160, bg="#FFFFFF", highlightthickness=0)
        self.qr_canvas.pack()
        
        self.lbl_qr_hint = tk.Label(self.card_content, text="Quét mã QR để Check-in lên xe", font=("Segoe UI", 8), fg="#94A3B8", bg="#FFFFFF")
        self.lbl_qr_hint.pack()

        # Nút hủy vé & Xuất file
        btn_action_box = tk.Frame(right_frame, bg="#F1F5F9", padx=10, pady=8)
        btn_action_box.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_cancel = tk.Button(
            btn_action_box, text="❌ Hủy Vé Này", bg="#EF4444", fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, pady=6, cursor="hand2",
            state=tk.DISABLED, command=self._on_cancel_ticket
        )
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_export = tk.Button(
            btn_action_box, text="💾 Lưu Hóa Đơn", bg="#0284C7", fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, pady=6, cursor="hand2",
            state=tk.DISABLED, command=self._on_export_receipt
        )
        self.btn_export.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def _load_tickets(self):
        resp = self.client.get_my_tickets()
        if resp.get("status") == "SUCCESS":
            self.tickets = resp.get("tickets", [])
            self.tree.delete(*self.tree.get_children())
            
            for t in self.tickets:
                route = f"{t.get('from_city')} ➔ {t.get('to_city')}"
                price_str = f"{t.get('total_amount', 0):,} VNĐ".replace(",", ".")
                status_vn = "ĐÃ ĐẶT" if t.get("status") == "CONFIRMED" else "ĐÃ HỦY"
                
                self.tree.insert(
                    "", tk.END, iid=str(t["id"]),
                    values=(t.get("booking_code"), route, t.get("seats"), price_str, status_vn)
                )
            
            if self.tickets:
                # Chọn dòng đầu tiên mặc định
                first_id = str(self.tickets[0]["id"])
                self.tree.selection_set(first_id)
                self.tree.focus(first_id)
                self._display_ticket(self.tickets[0])
            else:
                self._clear_ticket_display()

    def _on_ticket_selected(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        ticket_id = int(sel[0])
        for t in self.tickets:
            if t["id"] == ticket_id:
                self._display_ticket(t)
                break

    def _display_ticket(self, t):
        self.selected_ticket = t
        code = t.get("booking_code", "---")
        self.lbl_card_code.config(text=f"MÃ VÉ: {code}")
        self.lbl_card_route.config(text=f"Tuyến: {t.get('from_city')} ➔ {t.get('to_city')}")
        self.lbl_card_time.config(text=f"Khởi hành: {t.get('departure_time')}")
        self.lbl_card_bus.config(text=f"Xe: {t.get('bus_number')} ({t.get('bus_type')})")
        self.lbl_card_seats.config(text=f"Vị trí ghế: {t.get('seats')}")
        self.lbl_card_passenger.config(text=f"Hành khách: {t.get('passenger_name')} - SĐT: {t.get('passenger_phone')}")
        
        amount_str = f"{t.get('total_amount', 0):,} VNĐ".replace(",", ".")
        self.lbl_card_amount.config(text=f"Tổng tiền: {amount_str}")

        is_confirmed = (t.get("status") == "CONFIRMED")
        if is_confirmed:
            self.lbl_card_status.config(text="Trạng thái: 🟢 ĐÃ THANH TOÁN (HỢP LỆ)", fg="#059669")
            self.btn_cancel.config(state=tk.NORMAL)
            self.btn_export.config(state=tk.NORMAL)
        else:
            self.lbl_card_status.config(text="Trạng thái: 🔴 ĐÃ HỦY VÉ", fg="#DC2626")
            self.btn_cancel.config(state=tk.DISABLED)
            self.btn_export.config(state=tk.NORMAL)

        # Vẽ mã QR xác thực vé
        self.qr_canvas.delete("all")
        qr_text = f"TICKET_CHECKIN|{code}|{t.get('seats')}|{t.get('passenger_phone')}|VALID"
        draw_qr_on_canvas(self.qr_canvas, qr_text, x=10, y=10, width=140)

    def _clear_ticket_display(self):
        self.selected_ticket = None
        self.lbl_card_code.config(text="MÃ VÉ: ---")
        self.lbl_card_route.config(text="Tuyến: Chưa có vé nào")
        self.lbl_card_time.config(text="")
        self.lbl_card_bus.config(text="")
        self.lbl_card_seats.config(text="")
        self.lbl_card_passenger.config(text="")
        self.lbl_card_amount.config(text="")
        self.lbl_card_status.config(text="")
        self.qr_canvas.delete("all")
        self.btn_cancel.config(state=tk.DISABLED)
        self.btn_export.config(state=tk.DISABLED)

    def _on_cancel_ticket(self):
        if not self.selected_ticket:
            return
        
        confirm = messagebox.askyesno(
            "Xác nhận hủy vé",
            f"Bạn có chắc chắn muốn hủy vé {self.selected_ticket.get('booking_code')} không?\n"
            f"Ghế ({self.selected_ticket.get('seats')}) sẽ được giải phóng cho hành khách khác."
        )
        if not confirm:
            return

        resp = self.client.cancel_ticket(self.selected_ticket["id"])
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Thành công", resp.get("message"))
            self._load_tickets()
        else:
            messagebox.showerror("Lỗi hủy vé", resp.get("message", "Không thể hủy vé!"))

    def _on_export_receipt(self):
        if not self.selected_ticket:
            return
        t = self.selected_ticket
        code = t.get("booking_code")
        receipt_text = f"""
============================================================
              VÉ XE ĐIỆN TỬ - BIÊN LAI THANH TOÁN
============================================================
Mã vé:          {code}
Hành khách:     {t.get('passenger_name')}
Số điện thoại:  {t.get('passenger_phone')}
Email nhận vé:  {t.get('passenger_email')}
------------------------------------------------------------
Tuyến đường:    {t.get('from_city')} -> {t.get('to_city')}
Giờ khởi hành:  {t.get('departure_time')}
Biển số xe:     {t.get('bus_number')}
Loại phương tiện: {t.get('bus_type')}
Vị trí ghế ngồi: {t.get('seats')}
------------------------------------------------------------
Tổng số tiền:   {t.get('total_amount'):,} VNĐ
Phương thức TT: {t.get('payment_method')}
Thời gian đặt:  {t.get('booking_time')}
Trạng thái:     {t.get('status')}
============================================================
      Chúc quý khách có một chuyến đi an toàn & vui vẻ!
============================================================
        """
        filename = f"VeXe_{code}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(receipt_text)
            messagebox.showinfo("Xuất vé thành công", f"Đã lưu thông tin vé xe vào file:\n{filename}")
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", f"Không thể lưu file: {e}")
