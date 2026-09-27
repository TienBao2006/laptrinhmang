"""
server/client_handler.py - Tiếp nhận và xử lý từng kết nối Client đa luồng (Multi-threaded)
Hỗ trợ đầy đủ 34 chức năng theo đặc tả trong result.txt
"""

import socket
import threading
from common import protocol
from common.constants import (
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
    ACTION_VOICE_CALL_ANY,
    STATUS_SUCCESS, STATUS_ERROR, HOLD_TIMEOUT_SECONDS, SEAT_AVAILABLE, EVENT_USER_STATUS
)
from server import business_logic as bl
from server import database as db

class ClientHandler(threading.Thread):
    def __init__(self, client_sock: socket.socket, client_addr: tuple, server_instance):
        super().__init__(daemon=True)
        self.sock = client_sock
        self.addr = client_addr
        self.server = server_instance
        self.token = None
        self.username = None
        self.is_running = True

    def run(self):
        print(f"[ClientHandler] Khởi tạo luồng xử lý cho Client {self.addr}")
        try:
            while self.is_running:
                req = protocol.recv_msg(self.sock)
                if req is None:
                    break

                resp = self.process_request(req)
                if resp is not None:
                    protocol.send_msg(self.sock, resp)

        except Exception as e:
            print(f"[ClientHandler] Ngoại lệ kết nối {self.addr}: {e}")
        finally:
            self.cleanup()

    def process_request(self, req: dict) -> dict:
        action = req.get("action")

        # 1. Đăng nhập (STT 4)
        if action == ACTION_LOGIN:
            success, msg, user_data = bl.handle_login(req.get("username"), req.get("password"), self.sock)
            if success:
                self.token = user_data["token"]
                self.username = user_data["username"]
                # Thông báo tới các admin về việc user này online
                self.server.broadcast_user_status(self.username, "ONLINE")
                return {
                    "status": STATUS_SUCCESS,
                    "message": msg,
                    "role": user_data["role"],
                    "token": user_data["token"],
                    "user_info": user_data
                }
            return {"status": STATUS_ERROR, "message": msg}

        # 2. Đăng ký (STT 3)
        elif action == ACTION_REGISTER:
            success, msg_or_id = bl.handle_register(
                req.get("username"), req.get("password"),
                req.get("fullname"), req.get("phone"), req.get("email")
            )
            if success:
                return {"status": STATUS_SUCCESS, "message": "Đăng ký tài khoản thành công! Bạn có thể đăng nhập ngay."}
            return {"status": STATUS_ERROR, "message": msg_or_id}

        # 3. Đăng xuất (STT 5)
        elif action == ACTION_LOGOUT:
            if self.token:
                bl.remove_session(self.token)
            bl.unregister_online_client(self.sock)
            if self.username:
                self.server.broadcast_user_status(self.username, "OFFLINE")
            self.token = None
            return {"status": STATUS_SUCCESS, "message": "Đã đăng xuất an toàn!"}

        # 4. Quản lý thông tin cá nhân & Đổi mật khẩu (STT 6)
        elif action == ACTION_UPDATE_PROFILE:
            token = req.get("token") or self.token
            success, msg = bl.handle_update_profile(token, req.get("fullname"), req.get("phone"), req.get("email"))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        elif action == ACTION_CHANGE_PASSWORD:
            token = req.get("token") or self.token
            success, msg = bl.handle_change_password(token, req.get("old_password"), req.get("new_password"))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        # 5. Thống kê cá nhân (STT 33)
        elif action == ACTION_GET_PERSONAL_STATS:
            token = req.get("token") or self.token
            success, msg, stats = bl.handle_get_personal_stats(token)
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "stats": stats, "message": msg}

        # 6. Danh sách chuyến xe & Sơ đồ ghế (STT 8, 9, 11)
        elif action == ACTION_GET_TRIPS:
            trips = bl.handle_get_trips(req.get("from_city"), req.get("to_city"), req.get("date"))
            return {"status": STATUS_SUCCESS, "data": trips}

        elif action == ACTION_GET_SEATS:
            trip_id = req.get("trip_id")
            seats = bl.handle_get_seats(trip_id, self.sock)
            return {"status": STATUS_SUCCESS, "trip_id": trip_id, "seats": seats}

        # 7. Giữ ghế & Giải phóng ghế (STT 12, 13, 14, 16)
        elif action == ACTION_HOLD_SEATS:
            trip_id = req.get("trip_id")
            seats = req.get("seats", [])
            token = req.get("token") or self.token
            success, msg, updated = bl.handle_hold_seats(trip_id, seats, token)
            if success:
                self.server.broadcast_seat_update(trip_id, updated)
                return {
                    "status": STATUS_SUCCESS,
                    "message": f"Đã giữ chỗ thành công {len(seats)} ghế. Vui lòng thanh toán trong {HOLD_TIMEOUT_SECONDS} giây.",
                    "hold_timeout_seconds": HOLD_TIMEOUT_SECONDS,
                    "updated_seats": updated
                }
            return {"status": STATUS_ERROR, "message": msg}

        elif action == ACTION_RELEASE_SEATS:
            trip_id = req.get("trip_id")
            seats = req.get("seats", [])
            token = req.get("token") or self.token
            bl.handle_release_seats(trip_id, seats, token)
            updated = {s: SEAT_AVAILABLE for s in seats}
            self.server.broadcast_seat_update(trip_id, updated)
            return {"status": STATUS_SUCCESS, "message": "Đã giải phóng ghế!", "updated_seats": updated}

        # 8. Đặt vé & Thanh toán (STT 15, 17)
        elif action == ACTION_CONFIRM_BOOKING:
            trip_id = req.get("trip_id")
            seats = req.get("seats", [])
            token = req.get("token") or self.token
            passenger_info = req.get("passenger_info", {})
            payment_method = req.get("payment_method", "VIETQR")

            success, result_or_msg, updated = bl.handle_confirm_booking(
                trip_id, seats, token, passenger_info, payment_method
            )
            if success:
                self.server.broadcast_seat_update(trip_id, updated)
                booking_code = result_or_msg["booking_code"]
                amount = result_or_msg["total_amount"]
                qr_content = f"2|99|0909123456|VIETCOMBANK|{booking_code}|{amount}|VE XE TRAINBUS {booking_code}"

                return {
                    "status": STATUS_SUCCESS,
                    "booking_code": booking_code,
                    "total_amount": amount,
                    "seats": result_or_msg["seats"],
                    "booking_time": result_or_msg["booking_time"],
                    "qr_data": qr_content,
                    "message": "Chúc mừng bạn đã đặt vé thành công!"
                }
            return {"status": STATUS_ERROR, "message": result_or_msg}

        # 9. Lịch sử vé & Hủy vé (STT 18, 19)
        elif action == ACTION_GET_MY_TICKETS:
            token = req.get("token") or self.token
            success, msg, tickets = bl.handle_get_my_tickets(token)
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "tickets": tickets}

        elif action == ACTION_CANCEL_TICKET:
            token = req.get("token") or self.token
            ticket_id = req.get("ticket_id")
            success, msg, data = bl.handle_cancel_ticket(ticket_id, token)
            if success:
                trip_id = data["trip_id"]
                updated = {s: SEAT_AVAILABLE for s in data["seats"]}
                self.server.broadcast_seat_update(trip_id, updated)
                return {"status": STATUS_SUCCESS, "message": msg}
            return {"status": STATUS_ERROR, "message": msg}

        # 10. Quản lý xe (STT 10)
        elif action == ACTION_GET_VEHICLES:
            vehicles = bl.handle_get_vehicles()
            return {"status": STATUS_SUCCESS, "vehicles": vehicles}

        # 11. Heartbeat (STT 21)
        elif action == ACTION_HEARTBEAT:
            return {"status": STATUS_SUCCESS, "event": "PONG", "time": req.get("time")}

        # 12. Voice Call (STT 25, 26) — mọi user đều có thể gọi cho nhau
        elif action == ACTION_VOICE_CALL_INITIATE or action == ACTION_VOICE_CALL_ANY:
            token = req.get("token") or self.token
            target = req.get("target_username")
            success, res = bl.handle_voice_call_initiate(self.sock, target, token)
            if success:
                return {"status": STATUS_SUCCESS, "call_id": res["call_id"], "message": res["message"]}
            return {"status": STATUS_ERROR, "message": res}

        elif action == ACTION_VOICE_CALL_RESPONSE:
            call_id = req.get("call_id")
            accept = req.get("accept", False)
            success, msg = bl.handle_voice_call_response(call_id, accept, self.sock)
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        elif action == ACTION_VOICE_CALL_END:
            call_id = req.get("call_id")
            success, msg = bl.handle_voice_call_end(call_id, self.sock)
            return {"status": STATUS_SUCCESS, "message": msg}

        # --- ADMIN / QUẢN TRỊ HỆ THỐNG (STT 6, 7, 10, 20, 27, 28, 30, 31, 32, 33, 34) ---
        elif action == ACTION_ADMIN_GET_ONLINE_USERS:
            token = req.get("token") or self.token
            users = bl.get_online_users_list()
            return {"status": STATUS_SUCCESS, "online_users": users}

        elif action == ACTION_ADMIN_GET_USERS:
            token = req.get("token") or self.token
            success, msg, users = bl.handle_admin_get_users(token)
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "users": users}

        elif action == ACTION_ADMIN_UPDATE_USER:
            token = req.get("token") or self.token
            success, msg = bl.handle_admin_update_user(token, req.get("user_id"), req.get("role"), req.get("is_active"))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        elif action == ACTION_ADMIN_ADD_VEHICLE:
            token = req.get("token") or self.token
            success, res = bl.handle_admin_add_vehicle(token, req.get("vehicle_data", {}))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": "Thêm xe thành công!" if success else str(res)}

        elif action == ACTION_ADMIN_UPDATE_VEHICLE:
            token = req.get("token") or self.token
            success, msg = bl.handle_admin_update_vehicle(token, req.get("vehicle_id"), req.get("vehicle_data", {}))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        elif action == ACTION_ADMIN_DELETE_VEHICLE:
            token = req.get("token") or self.token
            success, msg = bl.handle_admin_delete_vehicle(token, req.get("vehicle_id"))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        elif action == ACTION_ADMIN_SEND_NOTIFICATION:
            token = req.get("token") or self.token
            success, msg = bl.handle_admin_send_notification(token, req.get("title"), req.get("message"), self.server)
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        elif action == ACTION_ADMIN_ADD_TRIP:
            token = req.get("token") or self.token
            success, msg_or_id = bl.db.admin_add_trip(
                req["trip_data"]["bus_number"], req["trip_data"]["bus_type"],
                req["trip_data"]["from_city"], req["trip_data"]["to_city"],
                req["trip_data"]["departure_time"], req["trip_data"]["price"],
                req["trip_data"].get("total_seats", 34)
            )
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": f"Tạo chuyến thành công (#{msg_or_id})"}

        elif action == ACTION_ADMIN_GET_ALL_TICKETS:
            token = req.get("token") or self.token
            return {"status": STATUS_SUCCESS, "tickets": db.admin_get_all_tickets()}

        elif action == ACTION_ADMIN_GET_STATS:
            token = req.get("token") or self.token
            return {"status": STATUS_SUCCESS, "stats": db.admin_get_stats()}

        elif action == ACTION_ADMIN_GET_LOGS:
            token = req.get("token") or self.token
            return {"status": STATUS_SUCCESS, "logs": db.admin_get_logs(req.get("limit", 50))}

        elif action == ACTION_ADMIN_BACKUP_DB:
            token = req.get("token") or self.token
            success, msg, data = bl.handle_admin_backup_db(token)
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg, "backup_data": data}

        elif action == ACTION_ADMIN_RESTORE_DB:
            token = req.get("token") or self.token
            success, msg = bl.handle_admin_restore_db(token, req.get("backup_data", {}))
            return {"status": STATUS_SUCCESS if success else STATUS_ERROR, "message": msg}

        return {"status": STATUS_ERROR, "message": f"Hành động không xác định: {action}"}

    def cleanup(self):
        print(f"[ClientHandler] Đang dọn dẹp kết nối cho Client {self.addr}")
        bl.unregister_client_viewing(self.sock)
        bl.unregister_online_client(self.sock)

        if self.username:
            self.server.broadcast_user_status(self.username, "OFFLINE")

        if self.token:
            released = db.release_all_seats_for_token(self.token)
            if released:
                trips_updated = {}
                for trip_id, seat_number in released:
                    if trip_id not in trips_updated:
                        trips_updated[trip_id] = {}
                    trips_updated[trip_id][seat_number] = SEAT_AVAILABLE
                for trip_id, updated_dict in trips_updated.items():
                    self.server.broadcast_seat_update(trip_id, updated_dict)

        self.server.remove_client(self.sock)
        try:
            self.sock.close()
        except Exception:
            pass
