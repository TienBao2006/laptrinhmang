"""
client/network_client.py - Quản lý kết nối TCP Socket phía Client
Hỗ trợ Heartbeat (PING/PONG), Tự động kết nối lại (Auto Reconnect),
Request-Response đồng bộ và đa kênh sự kiện Real-time (Ghế, Thông báo, Voice Call, Online Status).
"""

import socket
import threading
import queue
import time
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import protocol
from common.constants import (
    DEFAULT_HOST, DEFAULT_PORT, HEARTBEAT_INTERVAL, RECONNECT_INTERVAL,
    SERVER_HOST, SERVER_PORT,
    EVENT_SEAT_UPDATE, EVENT_NOTIFICATION, EVENT_USER_STATUS,
    EVENT_VOICE_CALL_INCOMING, EVENT_VOICE_CALL_ACCEPTED,
    EVENT_VOICE_CALL_REJECTED, EVENT_VOICE_CALL_ENDED,
    ACTION_LOGIN, ACTION_REGISTER, ACTION_LOGOUT,
    ACTION_UPDATE_PROFILE, ACTION_CHANGE_PASSWORD, ACTION_GET_PERSONAL_STATS,
    ACTION_GET_TRIPS, ACTION_GET_SEATS, ACTION_HOLD_SEATS, ACTION_RELEASE_SEATS,
    ACTION_CONFIRM_BOOKING, ACTION_GET_MY_TICKETS, ACTION_CANCEL_TICKET,
    ACTION_GET_VEHICLES, ACTION_HEARTBEAT,
    ACTION_ADMIN_ADD_TRIP, ACTION_ADMIN_GET_ALL_TICKETS, ACTION_ADMIN_GET_STATS,
    ACTION_ADMIN_GET_USERS, ACTION_ADMIN_UPDATE_USER,
    ACTION_ADMIN_ADD_VEHICLE, ACTION_ADMIN_UPDATE_VEHICLE, ACTION_ADMIN_DELETE_VEHICLE,
    ACTION_ADMIN_GET_ONLINE_USERS, ACTION_ADMIN_SEND_NOTIFICATION,
    ACTION_ADMIN_GET_LOGS, ACTION_ADMIN_BACKUP_DB, ACTION_ADMIN_RESTORE_DB,
    ACTION_VOICE_CALL_INITIATE, ACTION_VOICE_CALL_RESPONSE, ACTION_VOICE_CALL_END,
    STATUS_ERROR, STATUS_SUCCESS
)

class NetworkClient:
    def __init__(self):
        self.sock = None
        self.host = SERVER_HOST   # Lấy từ common/constants.py — sửa SERVER_HOST ở đó
        self.port = SERVER_PORT   # Lấy từ common/constants.py — sửa SERVER_PORT ở đó
        self.is_connected = False
        self.auto_reconnect_enabled = True
        self.token = None
        self.user_info = None

        self.send_lock = threading.Lock()
        self.response_queue = queue.Queue()
        self.listen_thread = None
        self.heartbeat_thread = None
        self.reconnect_thread = None

        # Danh sách hàm callback nhận sự kiện broadcast
        self.seat_update_callbacks = []
        self.disconnect_callbacks = []
        self.reconnect_callbacks = []
        self.notification_callbacks = []
        self.user_status_callbacks = []
        self.voice_call_callbacks = []

    def connect(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> tuple:
        """Kết nối tới máy chủ TCP Socket."""
        self.disconnect(clear_reconnect=False)
        self.host = host
        self.port = port

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self.is_connected = True

            # Khởi động luồng lắng nghe tin nhắn từ Server
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()

            # Khởi động luồng Heartbeat (STT 21)
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()

            return True, f"Kết nối thành công tới máy chủ {host}:{port}"
        except Exception as e:
            self.is_connected = False
            return False, f"Không thể kết nối tới {host}:{port}: {e}"

    def disconnect(self, clear_reconnect=True):
        """Đóng kết nối Socket an toàn."""
        self.is_connected = False
        if clear_reconnect:
            self.auto_reconnect_enabled = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _listen_loop(self):
        """Luồng chạy nền liên tục nhận dữ liệu từ Server."""
        while self.is_connected:
            try:
                msg = protocol.recv_msg(self.sock)
                if msg is None:
                    break

                # Xử lý các sự kiện Real-time Broadcast
                if "event" in msg:
                    evt = msg["event"]
                    if evt == EVENT_SEAT_UPDATE:
                        trip_id = msg.get("trip_id")
                        updated_seats = msg.get("updated_seats", {})
                        for cb in self.seat_update_callbacks:
                            try:
                                cb(trip_id, updated_seats)
                            except Exception:
                                pass

                    elif evt == EVENT_NOTIFICATION:
                        for cb in self.notification_callbacks:
                            try:
                                cb(msg.get("title"), msg.get("message"))
                            except Exception:
                                pass

                    elif evt == EVENT_USER_STATUS:
                        for cb in self.user_status_callbacks:
                            try:
                                cb(msg.get("username"), msg.get("status"))
                            except Exception:
                                pass

                    elif evt in (EVENT_VOICE_CALL_INCOMING, EVENT_VOICE_CALL_ACCEPTED,
                                 EVENT_VOICE_CALL_REJECTED, EVENT_VOICE_CALL_ENDED):
                        for cb in self.voice_call_callbacks:
                            try:
                                cb(evt, msg)
                            except Exception:
                                pass
                else:
                    # Bản tin phản hồi cho Request
                    self.response_queue.put(msg)

            except Exception:
                break

        self.is_connected = False
        for cb in self.disconnect_callbacks:
            try:
                cb()
            except Exception:
                pass

        # Kích hoạt Auto Reconnect (STT 22) nếu được bật
        if self.auto_reconnect_enabled:
            self._start_auto_reconnect()

    def _heartbeat_loop(self):
        """Gửi PING định kỳ kiểm tra kết nối (STT 21)."""
        while self.is_connected:
            time.sleep(HEARTBEAT_INTERVAL)
            if self.is_connected and self.sock:
                try:
                    with self.send_lock:
                        protocol.send_msg(self.sock, {"action": ACTION_HEARTBEAT, "time": time.time()})
                except Exception:
                    break

    def _start_auto_reconnect(self):
        """Tự động kết nối lại khi mất mạng (STT 22)."""
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            return

        def reconnect_worker():
            print("[Auto Reconnect] Đang thử kết nối lại máy chủ...")
            while not self.is_connected and self.auto_reconnect_enabled:
                time.sleep(RECONNECT_INTERVAL)
                ok, _ = self.connect(self.host, self.port)
                if ok:
                    print("[Auto Reconnect] Đã kết nối lại thành công!")
                    # Tự động đăng nhập lại nếu có thông tin phiên cũ
                    if self.user_info:
                        self.login(self.user_info.get("username"), "")
                    for cb in self.reconnect_callbacks:
                        try:
                            cb()
                        except Exception:
                            pass
                    break

        self.reconnect_thread = threading.Thread(target=reconnect_worker, daemon=True)
        self.reconnect_thread.start()

    def send_request(self, payload: dict, timeout: float = 8.0) -> dict:
        """Gửi yêu cầu tới Server và chờ nhận bản tin phản hồi."""
        if not self.is_connected or not self.sock:
            return {"status": STATUS_ERROR, "message": "Chưa kết nối tới máy chủ!"}

        with self.send_lock:
            while not self.response_queue.empty():
                try:
                    self.response_queue.get_nowait()
                except queue.Empty:
                    break

            if self.token and "token" not in payload:
                payload["token"] = self.token

            sent = protocol.send_msg(self.sock, payload)
            if not sent:
                self.is_connected = False
                return {"status": STATUS_ERROR, "message": "Lỗi gửi gói tin tới máy chủ!"}

            try:
                resp = self.response_queue.get(timeout=timeout)
                return resp
            except queue.Empty:
                return {"status": STATUS_ERROR, "message": "Hết thời gian chờ phản hồi từ máy chủ!"}

    # --- Các hàm nghiệp vụ ---
    def login(self, username, password):
        req = {"action": ACTION_LOGIN, "username": username, "password": password}
        resp = self.send_request(req)
        if resp.get("status") == "SUCCESS":
            self.token = resp.get("token")
            self.user_info = resp.get("user_info")
        return resp

    def register(self, username, password, fullname, phone, email):
        req = {
            "action": ACTION_REGISTER, "username": username, "password": password,
            "fullname": fullname, "phone": phone, "email": email
        }
        return self.send_request(req)

    def logout(self):
        req = {"action": ACTION_LOGOUT}
        resp = self.send_request(req)
        self.token = None
        self.user_info = None
        return resp

    def update_profile(self, fullname, phone, email):
        req = {"action": ACTION_UPDATE_PROFILE, "fullname": fullname, "phone": phone, "email": email}
        resp = self.send_request(req)
        if resp.get("status") == "SUCCESS" and self.user_info:
            self.user_info["fullname"] = fullname
            self.user_info["phone"] = phone
            self.user_info["email"] = email
        return resp

    def change_password(self, old_password, new_password):
        req = {"action": ACTION_CHANGE_PASSWORD, "old_password": old_password, "new_password": new_password}
        return self.send_request(req)

    def get_personal_stats(self):
        req = {"action": ACTION_GET_PERSONAL_STATS}
        return self.send_request(req)

    def get_trips(self, from_city=None, to_city=None, date=None):
        req = {"action": ACTION_GET_TRIPS, "from_city": from_city, "to_city": to_city, "date": date}
        return self.send_request(req)

    def get_seats(self, trip_id: int):
        req = {"action": ACTION_GET_SEATS, "trip_id": trip_id}
        return self.send_request(req)

    def hold_seats(self, trip_id: int, seats: list):
        req = {"action": ACTION_HOLD_SEATS, "trip_id": trip_id, "seats": seats}
        return self.send_request(req)

    def release_seats(self, trip_id: int, seats: list):
        req = {"action": ACTION_RELEASE_SEATS, "trip_id": trip_id, "seats": seats}
        return self.send_request(req)

    def confirm_booking(self, trip_id: int, seats: list, passenger_info: dict, payment_method: str = "VIETQR"):
        req = {
            "action": ACTION_CONFIRM_BOOKING, "trip_id": trip_id,
            "seats": seats, "passenger_info": passenger_info, "payment_method": payment_method
        }
        return self.send_request(req)

    def get_my_tickets(self):
        req = {"action": ACTION_GET_MY_TICKETS}
        return self.send_request(req)

    def cancel_ticket(self, ticket_id):
        req = {"action": ACTION_CANCEL_TICKET, "ticket_id": ticket_id}
        return self.send_request(req)

    def get_vehicles(self):
        req = {"action": ACTION_GET_VEHICLES}
        return self.send_request(req)

    # --- Voice Call (STT 25, 26) ---
    def voice_call_initiate(self, target_username: str):
        req = {"action": ACTION_VOICE_CALL_INITIATE, "target_username": target_username}
        return self.send_request(req)

    def voice_call_response(self, call_id: str, accept: bool):
        req = {"action": ACTION_VOICE_CALL_RESPONSE, "call_id": call_id, "accept": accept}
        return self.send_request(req)

    def voice_call_end(self, call_id: str):
        req = {"action": ACTION_VOICE_CALL_END, "call_id": call_id}
        return self.send_request(req)

    # --- Admin / Staff APIs ---
    def admin_get_users(self):
        return self.send_request({"action": ACTION_ADMIN_GET_USERS})

    def admin_update_user(self, user_id: int, role: str, is_active: int):
        return self.send_request({"action": ACTION_ADMIN_UPDATE_USER, "user_id": user_id, "role": role, "is_active": is_active})

    def admin_add_vehicle(self, v_data: dict):
        return self.send_request({"action": ACTION_ADMIN_ADD_VEHICLE, "vehicle_data": v_data})

    def admin_update_vehicle(self, v_id: int, v_data: dict):
        return self.send_request({"action": ACTION_ADMIN_UPDATE_VEHICLE, "vehicle_id": v_id, "vehicle_data": v_data})

    def admin_delete_vehicle(self, v_id: int):
        return self.send_request({"action": ACTION_ADMIN_DELETE_VEHICLE, "vehicle_id": v_id})

    def admin_get_online_users(self):
        return self.send_request({"action": ACTION_ADMIN_GET_ONLINE_USERS})

    def admin_send_notification(self, title: str, message: str):
        return self.send_request({"action": ACTION_ADMIN_SEND_NOTIFICATION, "title": title, "message": message})

    def admin_add_trip(self, trip_data: dict):
        return self.send_request({"action": ACTION_ADMIN_ADD_TRIP, "trip_data": trip_data})

    def admin_get_all_tickets(self):
        return self.send_request({"action": ACTION_ADMIN_GET_ALL_TICKETS})

    def admin_get_stats(self):
        return self.send_request({"action": ACTION_ADMIN_GET_STATS})

    def admin_get_logs(self, limit=50):
        return self.send_request({"action": ACTION_ADMIN_GET_LOGS, "limit": limit})

    def admin_backup_db(self):
        return self.send_request({"action": ACTION_ADMIN_BACKUP_DB})

    def admin_restore_db(self, backup_data: dict):
        return self.send_request({"action": ACTION_ADMIN_RESTORE_DB, "backup_data": backup_data})

    # --- Quản lý Callbacks ---
    def register_seat_update_callback(self, cb):
        if cb not in self.seat_update_callbacks:
            self.seat_update_callbacks.append(cb)

    def unregister_seat_update_callback(self, cb):
        if cb in self.seat_update_callbacks:
            self.seat_update_callbacks.remove(cb)

    def register_notification_callback(self, cb):
        if cb not in self.notification_callbacks:
            self.notification_callbacks.append(cb)

    def register_user_status_callback(self, cb):
        if cb not in self.user_status_callbacks:
            self.user_status_callbacks.append(cb)

    def register_voice_call_callback(self, cb):
        if cb not in self.voice_call_callbacks:
            self.voice_call_callbacks.append(cb)

    def register_disconnect_callback(self, cb):
        if cb not in self.disconnect_callbacks:
            self.disconnect_callbacks.append(cb)

    def register_reconnect_callback(self, cb):
        if cb not in self.reconnect_callbacks:
            self.reconnect_callbacks.append(cb)
