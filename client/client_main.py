"""
client/client_main.py - Entry Point duy nhất cho tất cả người dùng (Client GUI)
Quản lý chuyển đổi giữa màn hình Đăng nhập, Màn hình Đặt vé (Customer/Driver)
và Giao diện Chăm Sóc Khách Hàng (Admin/Staff).

Hệ thống có 3 actor: Server — Client (khách hàng) — Admin (chăm sóc khách hàng).
Tất cả đều đăng nhập qua cùng một cổng duy nhất này.
"""

import tkinter as tk
from tkinter import messagebox
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from client.network_client import NetworkClient
from client.gui_login import LoginWindow
from client.gui_booking import BookingWindow


class ClientApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.client = NetworkClient()
        self.current_window = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    def show_login(self):
        self._clear_root()
        self.root.deiconify()  # Đảm bảo cửa sổ chính hiển thị lại sau khi logout
        self.current_window = LoginWindow(
            self.root, self.client, on_login_success=self._on_login_success
        )

    def _on_login_success(self, client):
        """Chỉ cho tài khoản khách hàng và tài xế dùng ứng dụng client."""
        role = (self.client.user_info or {}).get("role", "")
        if role not in {"Customer", "Driver"}:
            try:
                self.client.logout()
            except Exception:
                pass
            messagebox.showerror(
                "Không có quyền truy cập",
                "Tài khoản quản trị/nhân viên chỉ được đăng nhập qua run_admin.py.",
                parent=self.root,
            )
            self.show_login()
            return
        self.show_booking(client)

    def show_booking(self, client):
        self._clear_root()
        self.current_window = BookingWindow(
            self.root, self.client, on_logout=self.show_login
        )

    def _clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def on_close(self):
        """Xử lý đóng ứng dụng an toàn."""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ClientApplication()
    app.run()
