"""
server/business_logic.py - Xử lý nghiệp vụ chính của hệ thống đặt vé xe
Quản lý phiên làm việc, phân quyền 4 Roles (Customer, Driver, Staff, Admin),
quản lý cuộc gọi thoại Voice Call, kiểm soát Online/Offline và chống Race Condition.
"""

import uuid
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from server import database as db
from common.constants import (
    SEAT_AVAILABLE, SEAT_HOLDING, SEAT_BOOKED,
    ROLE_CUSTOMER, ROLE_DRIVER, ROLE_STAFF, ROLE_ADMIN,
    HOLD_TIMEOUT_SECONDS,
    EVENT_VOICE_CALL_INCOMING, EVENT_VOICE_CALL_ACCEPTED,
    EVENT_VOICE_CALL_REJECTED, EVENT_VOICE_CALL_ENDED,
    EVENT_NOTIFICATION
)
from common import protocol

# Quản lý phiên: token -> user_dict
active_sessions: Dict[str, Dict[str, Any]] = {}
sessions_lock = threading.Lock()

# Quản lý Client đang mở xem sơ đồ của chuyến nào: client_sock -> trip_id
client_viewing_map: Dict[Any, int] = {}
viewing_lock = threading.Lock()

# Quản lý danh sách Client đang Online: client_sock -> user_info
online_clients_map: Dict[Any, Dict[str, Any]] = {}
online_lock = threading.Lock()

# Quản lý phiên Voice Call: call_id -> {admin_sock, client_sock, caller_name, target_username, status, start_time}
active_calls: Dict[str, Dict[str, Any]] = {}
calls_lock = threading.Lock()

def create_session(user_info: dict) -> str:
    token = uuid.uuid4().hex
    with sessions_lock:
        active_sessions[token] = {
            "user_id": user_info["id"],
            "username": user_info["username"],
            "fullname": user_info["fullname"],
            "phone": user_info["phone"],
            "email": user_info["email"],
            "role": user_info["role"],
            "login_time": time.time()
        }
    return token

def get_session(token: str) -> Optional[Dict[str, Any]]:
    with sessions_lock:
        return active_sessions.get(token)

def remove_session(token: str):
    with sessions_lock:
        active_sessions.pop(token, None)

def register_online_client(client_sock, user_info: dict):
    with online_lock:
        online_clients_map[client_sock] = user_info

def unregister_online_client(client_sock):
    with online_lock:
        return online_clients_map.pop(client_sock, None)

def get_online_users_list():
    with online_lock:
        return [
            {
                "id": u.get("id"),
                "username": u.get("username"),
                "fullname": u.get("fullname"),
                "role": u.get("role"),
                "phone": u.get("phone")
            }
            for u in online_clients_map.values()
        ]

def find_client_socket_by_username(username: str):
    with online_lock:
        for sock, u in online_clients_map.items():
            if u.get("username") == username:
                return sock
    return None

def register_client_viewing(client_sock, trip_id: int):
    with viewing_lock:
        client_viewing_map[client_sock] = trip_id

def unregister_client_viewing(client_sock):
    with viewing_lock:
        client_viewing_map.pop(client_sock, None)

def get_viewers_for_trip(trip_id: int):
    with viewing_lock:
        return [sock for sock, tid in client_viewing_map.items() if tid == trip_id]

# --- Xác thực & Quản lý tài khoản (STT 3, 4, 5, 6, 7) ---
def handle_login(username, password, client_sock=None):
    user = db.get_user_by_username(username)
    if not user:
        return False, "Tài khoản không tồn tại trên hệ thống!", None

    if not user.get("is_active", 1):
        return False, "Tài khoản của bạn đã bị Quản trị viên KHÓA tạm thời!", None

    if user["password_hash"] != db.hash_password(password):
        return False, "Mật khẩu không chính xác!", None

    token = create_session(user)
    user_data = {
        "id": user["id"],
        "username": user["username"],
        "fullname": user["fullname"],
        "phone": user["phone"],
        "email": user["email"],
        "role": user["role"],
        "token": token
    }
    if client_sock:
        register_online_client(client_sock, user_data)
    return True, "Đăng nhập thành công!", user_data

def handle_register(username, password, fullname, phone, email):
    if not username or not password or not fullname:
        return False, "Vui lòng nhập đầy đủ thông tin bắt buộc!"
    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự!"
    return db.create_user(username, password, fullname, phone, email, ROLE_CUSTOMER)

def handle_update_profile(token: str, fullname: str, phone: str, email: str):
    session = get_session(token)
    if not session:
        return False, "Phiên không hợp lệ!"
    return db.update_user_profile(session["user_id"], fullname, phone, email)

def handle_change_password(token: str, old_pw: str, new_pw: str):
    session = get_session(token)
    if not session:
        return False, "Phiên không hợp lệ!"
    return db.change_password(session["user_id"], old_pw, new_pw)

def handle_get_personal_stats(token: str):
    session = get_session(token)
    if not session:
        return False, "Phiên không hợp lệ!", {}
    stats = db.get_personal_stats(session["user_id"])
    return True, "Thành công", stats

# --- Chuyến xe & Đặt vé (STT 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19) ---
def handle_get_trips(from_city=None, to_city=None, date=None):
    return db.get_trips(from_city, to_city, date)

def handle_get_seats(trip_id: int, client_sock=None):
    if client_sock:
        register_client_viewing(client_sock, trip_id)
    return db.get_seats_by_trip(trip_id)

def handle_hold_seats(trip_id: int, seats: list, token: str):
    session = get_session(token)
    if not session:
        return False, "Phiên làm việc hết hạn hoặc không hợp lệ!", None
    success, msg = db.hold_seats(trip_id, seats, token)
    if success:
        return True, msg, {s: SEAT_HOLDING for s in seats}
    return False, msg, None

def handle_release_seats(trip_id: int, seats: list, token: str):
    db.release_seats(trip_id, seats, token)
    return True, {s: SEAT_AVAILABLE for s in seats}

def handle_confirm_booking(trip_id: int, seats: list, token: str, passenger_info: dict, payment_method: str):
    session = get_session(token)
    if not session:
        return False, "Phiên làm việc hết hạn. Vui lòng đăng nhập lại!", None
    user_id = session["user_id"]
    success, result, updated = db.confirm_booking(trip_id, seats, token, passenger_info, payment_method, user_id)
    if success:
        return True, result, updated
    return False, result, None

def handle_get_my_tickets(token: str):
    session = get_session(token)
    if not session:
        return False, "Phiên không hợp lệ!", []
    return True, "Thành công", db.get_user_tickets(session["user_id"])

def handle_cancel_ticket(ticket_id: Any, token: str):
    session = get_session(token)
    if not session:
        return False, "Phiên không hợp lệ!", None
    is_admin = (session["role"] in (ROLE_ADMIN, ROLE_STAFF))
    success, res = db.cancel_ticket(ticket_id, session["user_id"], is_admin)
    if success:
        return True, "Đã hủy vé thành công. Ghế đã được giải phóng!", res
    return False, res, None

def handle_get_vehicles():
    return db.get_vehicles()

# --- Voice Call (STT 25, 26) - Mọi role đều có thể gọi cho nhau ---
def handle_voice_call_initiate(caller_sock, target_username: str, token: str):
    """Bất kỳ user nào đã đăng nhập đều có thể gọi cho user khác đang online."""
    session = get_session(token)
    if not session:
        return False, "Phiên làm việc hết hạn. Vui lòng đăng nhập lại!"

    caller_username = session["username"]
    caller_name = session["fullname"]

    if caller_username == target_username:
        return False, "Không thể tự gọi cho chính mình!"

    target_sock = find_client_socket_by_username(target_username)
    if not target_sock:
        return False, f"Người dùng '{target_username}' hiện không trực tuyến (Offline)!"

    call_id = f"CALL-{uuid.uuid4().hex[:8]}"
    with calls_lock:
        active_calls[call_id] = {
            "caller_sock": caller_sock,
            "callee_sock": target_sock,
            "caller_username": caller_username,
            "caller_name": caller_name,
            "callee_username": target_username,
            "status": "RINGING",
            "start_time": time.time()
        }

    # Gửi sự kiện đổ chuông tới người được gọi
    protocol.send_msg(target_sock, {
        "event": EVENT_VOICE_CALL_INCOMING,
        "call_id": call_id,
        "caller_name": caller_name,
        "caller_username": caller_username
    })
    return True, {"call_id": call_id, "message": f"Đang gọi tới {target_username}..."}

def handle_voice_call_response(call_id: str, accept: bool, callee_sock):
    with calls_lock:
        call = active_calls.get(call_id)
        if not call:
            return False, "Cuộc gọi không tồn tại hoặc đã kết thúc!"

        caller_sock = call["caller_sock"]
        if accept:
            call["status"] = "CONNECTED"
            call["connected_time"] = time.time()
            # Báo cho người gọi biết cuộc gọi được chấp nhận
            protocol.send_msg(caller_sock, {
                "event": EVENT_VOICE_CALL_ACCEPTED,
                "call_id": call_id,
                "callee_name": call.get("callee_username", "")
            })
            return True, "Đã chấp nhận cuộc gọi!"
        else:
            call["status"] = "REJECTED"
            protocol.send_msg(caller_sock, {
                "event": EVENT_VOICE_CALL_REJECTED,
                "call_id": call_id,
                "message": "Người dùng đã từ chối cuộc gọi."
            })
            active_calls.pop(call_id, None)
            return True, "Đã từ chối cuộc gọi!"

def handle_voice_call_end(call_id: str, from_sock):
    with calls_lock:
        call = active_calls.pop(call_id, None)
        if not call:
            return True, "Cuộc gọi đã kết thúc."

        # Xác định socket của bên còn lại
        if from_sock == call["caller_sock"]:
            other_sock = call["callee_sock"]
        else:
            other_sock = call["caller_sock"]

        try:
            protocol.send_msg(other_sock, {
                "event": EVENT_VOICE_CALL_ENDED,
                "call_id": call_id,
                "message": "Đối phương đã kết thúc cuộc gọi."
            })
        except Exception:
            pass
        return True, "Đã kết thúc cuộc gọi."

# --- Quản trị & Điều khiển toàn bộ hệ thống (STT 6, 7, 10, 20, 27, 28, 30, 31, 32, 34) ---
def is_admin(token: str) -> bool:
    session = get_session(token)
    return session is not None and session["role"] == ROLE_ADMIN

def is_staff_or_admin(token: str) -> bool:
    session = get_session(token)
    return session is not None and session["role"] in (ROLE_ADMIN, ROLE_STAFF)

def handle_admin_get_users(token: str):
    if not is_staff_or_admin(token):
        return False, "Từ chối truy cập!", []
    return True, "Thành công", db.admin_get_users()

def handle_admin_update_user(token: str, user_id: int, role: str, is_active: int):
    if not is_admin(token):
        return False, "Chỉ Admin mới có quyền cập nhật tài khoản!"
    return db.admin_update_user(user_id, role, is_active)

def handle_admin_add_vehicle(token: str, v_data: dict):
    if not is_admin(token):
        return False, "Từ chối truy cập!"
    return db.admin_add_vehicle(
        v_data.get("bus_number"), v_data.get("bus_type"),
        v_data.get("total_seats", 34), v_data.get("driver_name", ""),
        v_data.get("phone", ""), v_data.get("status", "ACTIVE")
    )

def handle_admin_update_vehicle(token: str, v_id: int, v_data: dict):
    if not is_admin(token):
        return False, "Từ chối truy cập!"
    return db.admin_update_vehicle(
        v_id, v_data.get("bus_number"), v_data.get("bus_type"),
        v_data.get("total_seats", 34), v_data.get("driver_name", ""),
        v_data.get("phone", ""), v_data.get("status", "ACTIVE")
    )

def handle_admin_delete_vehicle(token: str, v_id: int):
    if not is_admin(token):
        return False, "Từ chối truy cập!"
    return db.admin_delete_vehicle(v_id)

def handle_admin_send_notification(token: str, title: str, message: str, server_instance):
    if not is_staff_or_admin(token):
        return False, "Từ chối truy cập!"
    db.add_notification(None, title, message)
    # Broadcast tới tất cả client đang online
    server_instance.broadcast_to_all({
        "event": EVENT_NOTIFICATION,
        "title": title,
        "message": message,
        "timestamp": datetime.now().strftime("%H:%M:%S") if 'datetime' in globals() else ""
    })
    return True, "Đã gửi thông báo Real-time thành công tới toàn bộ người dùng!"

def handle_admin_get_logs(token: str, limit=50):
    if not is_admin(token):
        return False, "Từ chối truy cập!", []
    return True, "Thành công", db.admin_get_logs(limit)

def handle_admin_backup_db(token: str):
    if not is_admin(token):
        return False, "Chỉ Admin mới có quyền Backup!", {}
    data = db.backup_database()
    return True, "Sao lưu dữ liệu thành công!", data

def handle_admin_restore_db(token: str, backup_data: dict):
    if not is_admin(token):
        return False, "Chỉ Admin mới có quyền Recovery!"
    return db.restore_database(backup_data)
