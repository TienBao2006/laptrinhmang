"""
run_server.py - Khởi động Máy chủ Đặt vé xe khách TCP Socket
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from server.server_main import BusBookingServer

if __name__ == "__main__":
    print("[*] Đang khởi động Bus Booking TCP Server...")
    server = BusBookingServer(host="0.0.0.0", port=8888)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
