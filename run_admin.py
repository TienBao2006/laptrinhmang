"""Khởi chạy ứng dụng quản trị dành cho máy chủ/quản trị viên."""

import os
import sys
import tkinter as tk

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from client.gui_admin import CustomerCareWindow
from client.gui_login_admin import AdminLoginWindow
from client.network_client import NetworkClient


def main():
    root = tk.Tk()
    client = NetworkClient()
    current_window = {"value": None}

    def show_login():
        for widget in root.winfo_children():
            widget.destroy()
        root.deiconify()
        current_window["value"] = AdminLoginWindow(
            root, client, on_login_success=show_admin
        )

    def show_admin(network_client):
        root.withdraw()
        current_window["value"] = CustomerCareWindow(
            root, network_client, on_close_callback=on_admin_close
        )

    def on_admin_close():
        try:
            client.logout()
        except Exception:
            pass
        root.after_idle(show_login)

    def on_close():
        try:
            client.disconnect()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    show_login()
    root.mainloop()


if __name__ == "__main__":
    main()
