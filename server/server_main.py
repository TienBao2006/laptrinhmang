"""
server/server_main.py - Entry Point máy chủ TCP Socket Đặt Vé Xe Khách & Xe Lửa (TrainBus)
Quản lý kết nối mạng đa luồng, phát sóng Broadcast thời gian thực và ghi nhật ký hoạt động MySQL.
"""

import os
import sys
import socket
import threading
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from common import protocol
from common.constants import DEFAULT_PORT, EVENT_SEAT_UPDATE, EVENT_USER_STATUS
from server import database as db
from server import business_logic as bl
from server.client_handler import ClientHandler
from server.seat_timer_worker import SeatTimerWorker

class BusBookingServer:
    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_sock = None
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.is_running = False
        self.timer_worker = None

    def start(self):
        print("=" * 75)
        print("  HỆ THỐNG MÁY CHỦ ĐẶT VÉ XE KHÁCH TRAINBUS (TCP SOCKET + MYSQL WORKBENCH)")
        print("=" * 75)

        # 1. Khởi tạo CSDL MySQL trainbus
        print("[Database] Đang kết nối và khởi tạo CSDL MySQL (Database: trainbus)...")
        db.init_db()
        print("[Database] CSDL MySQL đã sẵn sàng hoạt động với đầy đủ các bảng.")

        # 2. Khởi động Timer Worker kiểm tra ghế quá hạn
        self.timer_worker = SeatTimerWorker(self, interval=2.0)
        self.timer_worker.start()

        # 3. Tạo Socket TCP Server
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(50)
            self.is_running = True
            print(f"[TCP Server] Đang lắng nghe kết nối tại: {self.host}:{self.port}")
            print(f"[TCP Server] Hỗ trợ 34 chức năng, Đa luồng, Voice Call, Real-time Broadcast.")
            print("-" * 75)

            while self.is_running:
                try:
                    client_sock, client_addr = self.server_sock.accept()
                    print(f"[+] Client mới kết nối từ IP: {client_addr[0]}, Port: {client_addr[1]}")

                    with self.clients_lock:
                        self.clients.add(client_sock)

                    handler = ClientHandler(client_sock, client_addr, self)
                    handler.start()

                except socket.error:
                    if not self.is_running:
                        break

        except Exception as e:
            print(f"[!] Lỗi khởi động Server: {e}")
        finally:
            self.stop()

    def remove_client(self, client_sock: socket.socket):
        with self.clients_lock:
            if client_sock in self.clients:
                self.clients.remove(client_sock)
                print(f"[-] Client đã thoát. Tổng số kết nối hiện tại: {len(self.clients)}")

    def broadcast_to_all(self, message: dict):
        """Phát sóng tới TẤT CẢ các Client đang kết nối."""
        with self.clients_lock:
            socks = list(self.clients)
        for s in socks:
            try:
                protocol.send_msg(s, message)
            except Exception:
                pass

    def broadcast_seat_update(self, trip_id: int, updated_seats: dict):
        """Phát sóng cập nhật trạng thái ghế tới các Client đang xem chuyến xe này."""
        message = {
            "event": EVENT_SEAT_UPDATE,
            "trip_id": trip_id,
            "updated_seats": updated_seats,
            "timestamp": time.time()
        }
        viewers = bl.get_viewers_for_trip(trip_id)
        if not viewers:
            return
        for sock in viewers:
            try:
                protocol.send_msg(sock, message)
            except Exception:
                pass

    def broadcast_user_status(self, username: str, status: str):
        """Phát sóng sự kiện Online/Offline của người dùng."""
        self.broadcast_to_all({
            "event": EVENT_USER_STATUS,
            "username": username,
            "status": status,
            "timestamp": time.time()
        })

    def stop(self):
        print("\n[Server] Đang tiến hành tắt máy chủ...")
        self.is_running = False
        if self.timer_worker:
            self.timer_worker.stop()
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        with self.clients_lock:
            for sock in list(self.clients):
                try:
                    sock.close()
                except Exception:
                    pass
            self.clients.clear()
        print("[Server] Máy chủ đã dừng an toàn.")

if __name__ == "__main__":
    server = BusBookingServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
