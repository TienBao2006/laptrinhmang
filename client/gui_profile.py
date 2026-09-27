"""
client/gui_profile.py - Giao diện Thông Tin Cá Nhân & Thống Kê Chi Tiêu (STT 6, STT 33)
"""

import tkinter as tk
from tkinter import ttk, messagebox

class ProfileWindow(tk.Toplevel):
    def __init__(self, parent, network_client):
        super().__init__(parent)
        self.client = network_client
        self.title("Thông Tin Cá Nhân & Thống Kê Chi Tiêu")
        self.geometry("480x560")
        self.resizable(False, False)
        self.configure(bg="#F8FAFC")
        self.grab_set()

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#1E293B", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header, text="👤 THÔNG TIN TÀI KHOẢN & THỐNG KÊ",
            font=("Segoe UI", 12, "bold"), fg="#38BDF8", bg="#1E293B"
        ).pack(pady=16)

        body = tk.Frame(self, bg="#F8FAFC", padx=20, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        # 1. Thống kê cá nhân (STT 33)
        stats_frame = tk.LabelFrame(body, text="Thống kê hoạt động cá nhân (STT 33)", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", padx=10, pady=8)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_stat_tickets = tk.Label(stats_frame, text="🎫 Tổng số vé đã đặt: ...", font=("Segoe UI", 9), bg="#FFFFFF")
        self.lbl_stat_tickets.pack(anchor=tk.W)

        self.lbl_stat_spent = tk.Label(stats_frame, text="💰 Tổng tiền đã chi: ...", font=("Segoe UI", 10, "bold"), fg="#059669", bg="#FFFFFF")
        self.lbl_stat_spent.pack(anchor=tk.W, pady=2)

        self.lbl_stat_cancelled = tk.Label(stats_frame, text="❌ Số vé đã hủy: ...", font=("Segoe UI", 9), fg="#DC2626", bg="#FFFFFF")
        self.lbl_stat_cancelled.pack(anchor=tk.W)

        # 2. Cập nhật thông tin cá nhân (STT 6)
        info_frame = tk.LabelFrame(body, text="Cập nhật thông tin liên hệ (STT 6)", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", padx=10, pady=8)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(info_frame, text="Tên tài khoản:", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=0, column=0, sticky=tk.W)
        self.lbl_user = tk.Label(info_frame, text="...", font=("Segoe UI", 9, "bold"), fg="#2563EB", bg="#FFFFFF")
        self.lbl_user.grid(row=0, column=1, sticky=tk.W, pady=2)

        tk.Label(info_frame, text="Vai trò (Role):", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=1, column=0, sticky=tk.W)
        self.lbl_role = tk.Label(info_frame, text="...", font=("Segoe UI", 9, "bold"), fg="#7C3AED", bg="#FFFFFF")
        self.lbl_role.grid(row=1, column=1, sticky=tk.W, pady=2)

        tk.Label(info_frame, text="Họ và tên:", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=2, column=0, sticky=tk.W)
        self.ent_name = ttk.Entry(info_frame, width=28)
        self.ent_name.grid(row=2, column=1, pady=3)

        tk.Label(info_frame, text="Số điện thoại:", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=3, column=0, sticky=tk.W)
        self.ent_phone = ttk.Entry(info_frame, width=28)
        self.ent_phone.grid(row=3, column=1, pady=3)

        tk.Label(info_frame, text="Email:", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=4, column=0, sticky=tk.W)
        self.ent_email = ttk.Entry(info_frame, width=28)
        self.ent_email.grid(row=4, column=1, pady=3)

        btn_save_info = tk.Button(
            info_frame, text="💾 Lưu Thông Tin", bg="#2563EB", fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=10, pady=4, command=self._on_save_info
        )
        btn_save_info.grid(row=5, column=1, sticky=tk.E, pady=(5, 2))

        # 3. Đổi mật khẩu
        pw_frame = tk.LabelFrame(body, text="Đổi mật khẩu", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", padx=10, pady=8)
        pw_frame.pack(fill=tk.X)

        tk.Label(pw_frame, text="Mật khẩu hiện tại:", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=0, column=0, sticky=tk.W)
        self.ent_old_pw = ttk.Entry(pw_frame, show="•", width=28)
        self.ent_old_pw.grid(row=0, column=1, pady=2)

        tk.Label(pw_frame, text="Mật khẩu mới:", bg="#FFFFFF", font=("Segoe UI", 8)).grid(row=1, column=0, sticky=tk.W)
        self.ent_new_pw = ttk.Entry(pw_frame, show="•", width=28)
        self.ent_new_pw.grid(row=1, column=1, pady=2)

        btn_save_pw = tk.Button(
            pw_frame, text="🔑 Đổi Mật Khẩu", bg="#059669", fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=10, pady=4, command=self._on_change_pw
        )
        btn_save_pw.grid(row=2, column=1, sticky=tk.E, pady=(5, 2))

    def _load_data(self):
        u = self.client.user_info or {}
        self.lbl_user.config(text=u.get("username", ""))
        self.lbl_role.config(text=u.get("role", "Customer"))
        self.ent_name.delete(0, tk.END)
        self.ent_name.insert(0, u.get("fullname", ""))
        self.ent_phone.delete(0, tk.END)
        self.ent_phone.insert(0, u.get("phone", ""))
        self.ent_email.delete(0, tk.END)
        self.ent_email.insert(0, u.get("email", ""))

        # Tải thống kê cá nhân (STT 33)
        resp = self.client.get_personal_stats()
        if resp.get("status") == "SUCCESS":
            s = resp.get("stats", {})
            self.lbl_stat_tickets.config(text=f"🎫 Tổng số vé đã đặt: {s.get('total_tickets', 0)} vé")
            spent = s.get("total_spent", 0)
            self.lbl_stat_spent.config(text=f"💰 Tổng tiền đã chi tiêu: {spent:,} VNĐ".replace(",", "."))
            self.lbl_stat_cancelled.config(text=f"❌ Số vé đã hủy: {s.get('cancelled_tickets', 0)} vé")

    def _on_save_info(self):
        name = self.ent_name.get().strip()
        phone = self.ent_phone.get().strip()
        email = self.ent_email.get().strip()
        if not name or not phone:
            messagebox.showwarning("Thiếu dữ liệu", "Họ tên và số điện thoại không được để trống!")
            return
        resp = self.client.update_profile(name, phone, email)
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Thành công", resp.get("message"))
        else:
            messagebox.showerror("Lỗi", resp.get("message"))

    def _on_change_pw(self):
        old_p = self.ent_old_pw.get().strip()
        new_p = self.ent_new_pw.get().strip()
        if not old_p or not new_p:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập mật khẩu hiện tại và mật khẩu mới!")
            return
        if len(new_p) < 6:
            messagebox.showwarning("Mật khẩu yếu", "Mật khẩu mới phải có ít nhất 6 ký tự!")
            return
        resp = self.client.change_password(old_p, new_p)
        if resp.get("status") == "SUCCESS":
            messagebox.showinfo("Thành công", resp.get("message"))
            self.ent_old_pw.delete(0, tk.END)
            self.ent_new_pw.delete(0, tk.END)
        else:
            messagebox.showerror("Lỗi", resp.get("message"))
