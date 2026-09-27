"""
run_admin.py - Redirect sang run_client.py

Hệ thống giờ có 3 actor duy nhất: Server — Client — Admin (Chăm Sóc Khách Hàng).
Admin/Staff đăng nhập qua cùng cổng với khách hàng (run_client.py).
File này tự động khởi chạy run_client.py để tránh nhầm lẫn.
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    print("=" * 60)
    print("  ℹ️  THÔNG BÁO")
    print("  Hệ thống TrainBus hiện chỉ có 1 cổng đăng nhập duy nhất.")
    print("  Admin / Nhân viên đăng nhập tại: run_client.py")
    print("  Đang chuyển hướng...")
    print("=" * 60)

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_client.py")
    subprocess.run([sys.executable, script])
