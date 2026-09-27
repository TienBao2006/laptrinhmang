"""
server/database.py - Quản lý CSDL MySQL Workbench (Database: trainbus)
Tự động tạo database, tạo các bảng và chèn dữ liệu mẫu theo yêu cầu trong result.txt.
"""

import os
import sys
import hashlib
import time
import json
from datetime import datetime
import threading
import pymysql
import pymysql.cursors

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from common.constants import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB,
    SEAT_AVAILABLE, SEAT_HOLDING, SEAT_BOOKED,
    ROLE_CUSTOMER, ROLE_DRIVER, ROLE_STAFF, ROLE_ADMIN
)

db_lock = threading.Lock()

def get_connection(with_db=True):
    """Tạo kết nối tới MySQL Server (với mã hóa UTF-8 tiếng Việt chuẩn)."""
    db_name = MYSQL_DB if with_db else None
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=db_name,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def hash_password(password: str) -> str:
    """Băm mật khẩu người dùng với salt để đảm bảo an toàn."""
    salt = "BUS_BOOKING_SECURE_SALT_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def init_db():
    """
    Khởi tạo CSDL MySQL trainbus và cấu trúc bảng.
    Nếu chưa có dữ liệu, tự động thêm các bảng và dữ liệu mẫu chuẩn hóa.
    """
    with db_lock:
        # 1. Tạo database nếu chưa tồn tại
        conn_init = get_connection(with_db=False)
        cur_init = conn_init.cursor()
        cur_init.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur_init.close()
        conn_init.close()

        # 2. Kết nối vào database trainbus và tạo bảng
        conn = get_connection(with_db=True)
        cur = conn.cursor()

        # Bảng 1: users (Hỗ trợ 4 Roles: Customer, Driver, Staff, Admin + trạng thái khóa is_active)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(128) NOT NULL,
                fullname VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                email VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'Customer',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Bảng 2: vehicles (Quản lý thông tin xe - STT 10)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bus_number VARCHAR(30) UNIQUE NOT NULL,
                bus_type VARCHAR(50) NOT NULL,
                total_seats INT NOT NULL,
                driver_name VARCHAR(100),
                phone VARCHAR(20),
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Bảng 3: trips (Quản lý các chuyến xe)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bus_number VARCHAR(30) NOT NULL,
                bus_type VARCHAR(50) NOT NULL,
                from_city VARCHAR(50) NOT NULL,
                to_city VARCHAR(50) NOT NULL,
                departure_time VARCHAR(50) NOT NULL,
                price INT NOT NULL,
                total_seats INT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Bảng 4: seats (Sơ đồ ghế và trạng thái giữ chỗ)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                trip_id INT NOT NULL,
                seat_number VARCHAR(10) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
                held_by_token VARCHAR(64) NULL,
                held_time DOUBLE NOT NULL DEFAULT 0,
                UNIQUE KEY unique_seat (trip_id, seat_number),
                FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Bảng 5: tickets (Lịch sử đặt vé & biên lai)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                booking_code VARCHAR(50) UNIQUE NOT NULL,
                trip_id INT NOT NULL,
                user_id INT NOT NULL,
                seats VARCHAR(255) NOT NULL,
                passenger_name VARCHAR(100) NOT NULL,
                passenger_phone VARCHAR(20) NOT NULL,
                passenger_email VARCHAR(100),
                total_amount INT NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                booking_time VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'CONFIRMED',
                FOREIGN KEY (trip_id) REFERENCES trips(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Bảng 6: notifications (Thông báo Real-time cho người dùng - STT 20)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                is_read TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Bảng 7: system_logs (Ghi nhật ký kết nối, đặt vé, lỗi - STT 28)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                log_level VARCHAR(20) NOT NULL DEFAULT 'INFO',
                action VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                client_ip VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 3. Tự động chèn dữ liệu mẫu nếu bảng users chưa có dữ liệu
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        if cur.fetchone()["cnt"] == 0:
            print("[Database] Đang khởi tạo dữ liệu mẫu vào MySQL...")
            # Tài khoản mẫu cho 4 vai trò
            cur.execute("""
                INSERT INTO users (username, password_hash, fullname, phone, email, role, is_active) VALUES
                ('admin', %s, 'Quản Trị Viên Hệ Thống', '0909123456', 'admin@trainbus.vn', %s, 1),
                ('nhanvien', %s, 'Nguyễn Thị Bích (Nhân viên vé)', '0912334455', 'staff@trainbus.vn', %s, 1),
                ('taixe', %s, 'Trần Văn Lái (Tài xế VIP)', '0988776655', 'driver@trainbus.vn', %s, 1),
                ('khachhang', %s, 'Nguyễn Văn An (Khách Hàng)', '0987654321', 'vanan@gmail.com', %s, 1)
            """, (
                hash_password("admin123"), ROLE_ADMIN,
                hash_password("123456"), ROLE_STAFF,
                hash_password("123456"), ROLE_DRIVER,
                hash_password("123456"), ROLE_CUSTOMER
            ))

        # Tự động chèn xe mẫu
        cur.execute("SELECT COUNT(*) AS cnt FROM vehicles")
        if cur.fetchone()["cnt"] == 0:
            cur.execute("""
                INSERT INTO vehicles (bus_number, bus_type, total_seats, driver_name, phone, status) VALUES
                ('29B-888.88', 'Giường nằm 34 phòng', 34, 'Trần Văn Lái', '0988776655', 'ACTIVE'),
                ('51B-123.45', 'Limousine 24 phòng VIP', 24, 'Lê Hữu Tài', '0933221144', 'ACTIVE'),
                ('43B-567.89', 'Ghế ngồi cao cấp 29 chỗ', 29, 'Phạm Văn Bác', '0905112233', 'ACTIVE'),
                ('51B-999.99', 'Giường nằm 34 phòng', 34, 'Vũ Đức Thành', '0977665544', 'ACTIVE'),
                ('29B-456.78', 'Giường nằm 34 phòng', 34, 'Đinh Tiến Dũng', '0911889900', 'ACTIVE'),
                ('49B-333.33', 'Limousine 24 phòng VIP', 24, 'Hoàng Minh Tuấn', '0944556677', 'ACTIVE')
            """)

        # Tự động chèn chuyến xe mẫu và sinh ghế
        cur.execute("SELECT COUNT(*) AS cnt FROM trips")
        if cur.fetchone()["cnt"] == 0:
            sample_trips = [
                ("29B-888.88", "Giường nằm 34 phòng", "Hà Nội", "Đà Nẵng", "19:00 28/09/2026", 350000, 34),
                ("51B-123.45", "Limousine 24 phòng VIP", "Hồ Chí Minh", "Đà Lạt", "22:30 28/09/2026", 420000, 24),
                ("43B-567.89", "Ghế ngồi cao cấp 29 chỗ", "Đà Nẵng", "Quy Nhơn", "08:00 29/09/2026", 220000, 29),
                ("51B-999.99", "Giường nằm 34 phòng", "Hồ Chí Minh", "Nha Trang", "21:00 29/09/2026", 380000, 34),
                ("29B-456.78", "Giường nằm 34 phòng", "Hà Nội", "Hồ Chí Minh", "14:00 30/09/2026", 850000, 34),
                ("49B-333.33", "Limousine 24 phòng VIP", "Đà Lạt", "Hồ Chí Minh", "13:00 30/09/2026", 420000, 24)
            ]
            for bus_num, b_type, f_city, t_city, dep_time, prc, tot_s in sample_trips:
                cur.execute("""
                    INSERT INTO trips (bus_number, bus_type, from_city, to_city, departure_time, price, total_seats)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (bus_num, b_type, f_city, t_city, dep_time, prc, tot_s))
                trip_id = cur.lastrowid
                _generate_seats_for_trip(cur, trip_id, tot_s)

        # Chèn thông báo chào mừng
        cur.execute("SELECT COUNT(*) AS cnt FROM notifications")
        if cur.fetchone()["cnt"] == 0:
            cur.execute("""
                INSERT INTO notifications (user_id, title, message) VALUES
                (NULL, 'Chào mừng đến với hệ thống TrainBus', 'Hệ thống đặt vé xe khách trực tuyến TCP Socket đã chính thức đi vào hoạt động!')
            """)

        # Ghi log khởi tạo
        log_action(cur, "SYSTEM", "Khởi tạo thành công CSDL MySQL trainbus", "127.0.0.1")

        cur.close()
        conn.close()
        print("[Database] Kết nối MySQL và khởi tạo bảng thành công.")

def _generate_seats_for_trip(cursor, trip_id: int, total_seats: int):
    """Tạo sơ đồ ghế cho chuyến xe."""
    seat_labels = []
    if total_seats == 34:
        seat_labels += [f"A{i:02d}" for i in range(1, 18)]
        seat_labels += [f"B{i:02d}" for i in range(1, 18)]
    elif total_seats == 24:
        seat_labels += [f"A{i:02d}" for i in range(1, 13)]
        seat_labels += [f"B{i:02d}" for i in range(1, 13)]
    else:
        seat_labels += [f"A{i:02d}" for i in range(1, total_seats + 1)]

    for idx, label in enumerate(seat_labels):
        status = SEAT_BOOKED if idx in (2, 5) else SEAT_AVAILABLE
        cursor.execute("""
            INSERT IGNORE INTO seats (trip_id, seat_number, status, held_by_token, held_time)
            VALUES (%s, %s, %s, NULL, 0)
        """, (trip_id, label, status))

# --- Nhật ký hệ thống (Logging - STT 28) ---
def log_action(cursor_or_none, action: str, message: str, client_ip: str = "127.0.0.1", level: str = "INFO"):
    """Ghi log vào bảng system_logs."""
    try:
        if cursor_or_none is not None:
            cursor_or_none.execute("""
                INSERT INTO system_logs (log_level, action, message, client_ip)
                VALUES (%s, %s, %s, %s)
            """, (level, action, message, client_ip))
        else:
            with db_lock:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO system_logs (log_level, action, message, client_ip)
                    VALUES (%s, %s, %s, %s)
                """, (level, action, message, client_ip))
                cur.close()
                conn.close()
    except Exception:
        pass

# --- Người dùng & Xác thực (STT 3, 4, 5, 6, 7) ---
def get_user_by_username(username: str):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

def create_user(username, password, fullname, phone, email, role=ROLE_CUSTOMER):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        try:
            pw_hash = hash_password(password)
            cur.execute("""
                INSERT INTO users (username, password_hash, fullname, phone, email, role, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (username, pw_hash, fullname, phone, email, role))
            user_id = cur.lastrowid
            log_action(cur, "REGISTER", f"Người dùng mới đăng ký: {username} ({fullname})")
            cur.close()
            conn.close()
            return True, user_id
        except pymysql.IntegrityError:
            cur.close()
            conn.close()
            return False, "Tên tài khoản đã tồn tại trên hệ thống!"
        except Exception as e:
            cur.close()
            conn.close()
            return False, str(e)

def update_user_profile(user_id: int, fullname: str, phone: str, email: str):
    """Client: Sửa thông tin cá nhân (STT 6)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users SET fullname = %s, phone = %s, email = %s WHERE id = %s
        """, (fullname, phone, email, user_id))
        log_action(cur, "UPDATE_PROFILE", f"Cập nhật thông tin User ID #{user_id}")
        cur.close()
        conn.close()
        return True, "Cập nhật thông tin thành công!"

def change_password(user_id: int, old_password: str, new_password: str):
    """Đổi mật khẩu người dùng."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row or row["password_hash"] != hash_password(old_password):
            cur.close()
            conn.close()
            return False, "Mật khẩu cũ không chính xác!"
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_password), user_id))
        log_action(cur, "CHANGE_PASSWORD", f"User #{user_id} đã đổi mật khẩu")
        cur.close()
        conn.close()
        return True, "Đổi mật khẩu thành công!"

def admin_get_users():
    """Admin: Quản lý danh sách tài khoản (STT 6)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, fullname, phone, email, role, is_active, created_at FROM users ORDER BY id ASC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

def admin_update_user(user_id: int, role: str, is_active: int):
    """Admin: Phân quyền & Khóa/Mở khóa tài khoản (STT 6, 7)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET role = %s, is_active = %s WHERE id = %s", (role, is_active, user_id))
        log_action(cur, "ADMIN_UPDATE_USER", f"Admin cập nhật User #{user_id} (Role={role}, Active={is_active})")
        cur.close()
        conn.close()
        return True, "Cập nhật tài khoản thành công!"

# --- Quản lý xe (Vehicles - STT 10) ---
def get_vehicles():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM vehicles ORDER BY id ASC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

def admin_add_vehicle(bus_number, bus_type, total_seats, driver_name, phone, status="ACTIVE"):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO vehicles (bus_number, bus_type, total_seats, driver_name, phone, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (bus_number, bus_type, total_seats, driver_name, phone, status))
            vid = cur.lastrowid
            log_action(cur, "ADD_VEHICLE", f"Thêm xe mới: {bus_number} ({bus_type})")
            cur.close()
            conn.close()
            return True, vid
        except Exception as e:
            cur.close()
            conn.close()
            return False, str(e)

def admin_update_vehicle(vehicle_id, bus_number, bus_type, total_seats, driver_name, phone, status):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE vehicles
            SET bus_number = %s, bus_type = %s, total_seats = %s, driver_name = %s, phone = %s, status = %s
            WHERE id = %s
        """, (bus_number, bus_type, total_seats, driver_name, phone, status, vehicle_id))
        log_action(cur, "UPDATE_VEHICLE", f"Cập nhật thông tin xe #{vehicle_id}")
        cur.close()
        conn.close()
        return True, "Đã cập nhật xe thành công!"

def admin_delete_vehicle(vehicle_id):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM vehicles WHERE id = %s", (vehicle_id,))
        log_action(cur, "DELETE_VEHICLE", f"Xóa xe #{vehicle_id}")
        cur.close()
        conn.close()
        return True, "Đã xóa xe thành công!"

# --- Quản lý Chuyến xe & Ghế (STT 8, 9, 11, 12, 13, 14, 15, 16) ---
def get_trips(from_city=None, to_city=None, date=None):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        query = "SELECT * FROM trips WHERE 1=1"
        params = []
        if from_city and from_city != "Tất cả":
            query += " AND from_city LIKE %s"
            params.append(f"%{from_city}%")
        if to_city and to_city != "Tất cả":
            query += " AND to_city LIKE %s"
            params.append(f"%{to_city}%")
        if date:
            query += " AND departure_time LIKE %s"
            params.append(f"%{date}%")
        query += " ORDER BY id ASC"
        cur.execute(query, params)
        trips = cur.fetchall()

        for trip in trips:
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM seats
                WHERE trip_id = %s AND status = %s
            """, (trip["id"], SEAT_AVAILABLE))
            trip["available_seats"] = cur.fetchone()["cnt"]

        cur.close()
        conn.close()
        return trips

def get_trip_by_id(trip_id: int):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM trips WHERE id = %s", (trip_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

def get_seats_by_trip(trip_id: int):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT seat_number, status, held_by_token
            FROM seats WHERE trip_id = %s ORDER BY seat_number ASC
        """, (trip_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {row["seat_number"]: row["status"] for row in rows}

def hold_seats(trip_id: int, seat_numbers: list, token: str):
    """Giữ ghế tạm thời - Lock Transaction chống Race Condition (STT 13, 16)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        current_time = time.time()
        for seat in seat_numbers:
            cur.execute("SELECT status, held_by_token FROM seats WHERE trip_id = %s AND seat_number = %s", (trip_id, seat))
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return False, f"Ghế {seat} không tồn tại!"
            if row["status"] == SEAT_BOOKED:
                cur.close()
                conn.close()
                return False, f"Ghế {seat} đã có người đặt mua thành công!"
            if row["status"] == SEAT_HOLDING and row["held_by_token"] != token:
                cur.close()
                conn.close()
                return False, f"Ghế {seat} đang có người khác chọn giữ chỗ!"

        for seat in seat_numbers:
            cur.execute("""
                UPDATE seats SET status = %s, held_by_token = %s, held_time = %s
                WHERE trip_id = %s AND seat_number = %s
            """, (SEAT_HOLDING, token, current_time, trip_id, seat))

        log_action(cur, "HOLD_SEATS", f"Token {token[:8]} giữ tạm ghế: {seat_numbers} chuyến #{trip_id}")
        cur.close()
        conn.close()
        return True, "Giữ chỗ tạm thời thành công!"

def release_seats(trip_id: int, seat_numbers: list, token: str):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        for seat in seat_numbers:
            cur.execute("""
                UPDATE seats SET status = %s, held_by_token = NULL, held_time = 0
                WHERE trip_id = %s AND seat_number = %s AND status = %s AND held_by_token = %s
            """, (SEAT_AVAILABLE, trip_id, seat, SEAT_HOLDING, token))
        cur.close()
        conn.close()
        return True

def release_all_seats_for_token(token: str):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT trip_id, seat_number FROM seats WHERE status = %s AND held_by_token = %s", (SEAT_HOLDING, token))
        rows = cur.fetchall()
        released = [(r["trip_id"], r["seat_number"]) for r in rows]
        cur.execute("""
            UPDATE seats SET status = %s, held_by_token = NULL, held_time = 0
            WHERE status = %s AND held_by_token = %s
        """, (SEAT_AVAILABLE, SEAT_HOLDING, token))
        cur.close()
        conn.close()
        return released

def release_expired_seats(timeout_seconds: int):
    """Seat Timer Worker: Tự động giải phóng ghế hết hạn giữ (STT 14)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cutoff_time = time.time() - timeout_seconds
        cur.execute("SELECT trip_id, seat_number FROM seats WHERE status = %s AND held_time < %s", (SEAT_HOLDING, cutoff_time))
        expired = cur.fetchall()
        released = [(r["trip_id"], r["seat_number"]) for r in expired]
        if released:
            cur.execute("""
                UPDATE seats SET status = %s, held_by_token = NULL, held_time = 0
                WHERE status = %s AND held_time < %s
            """, (SEAT_AVAILABLE, SEAT_HOLDING, cutoff_time))
            log_action(cur, "TIMEOUT_SEATS", f"Giải phóng {len(released)} ghế quá hạn")
        cur.close()
        conn.close()
        return released

def confirm_booking(trip_id: int, seat_numbers: list, token: str, passenger_info: dict, payment_method: str, user_id: int):
    """Đặt vé & Thanh toán giao dịch (STT 15, 16, 17)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        for seat in seat_numbers:
            cur.execute("SELECT status, held_by_token FROM seats WHERE trip_id = %s AND seat_number = %s", (trip_id, seat))
            row = cur.fetchone()
            if not row or row["status"] == SEAT_BOOKED or (row["status"] == SEAT_HOLDING and row["held_by_token"] != token):
                cur.close()
                conn.close()
                return False, f"Ghế {seat} không hợp lệ hoặc đã bị người khác chọn!"

        cur.execute("SELECT price FROM trips WHERE id = %s", (trip_id,))
        trip_row = cur.fetchone()
        price = trip_row["price"] if trip_row else 350000
        total_amount = price * len(seat_numbers)

        date_str = datetime.now().strftime("%Y%m%d")
        import random
        booking_code = f"TKT-{date_str}-{random.randint(1000, 9999)}"

        for seat in seat_numbers:
            cur.execute("""
                UPDATE seats SET status = %s, held_by_token = NULL, held_time = 0
                WHERE trip_id = %s AND seat_number = %s
            """, (SEAT_BOOKED, trip_id, seat))

        seats_str = ", ".join(seat_numbers)
        booking_time = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        cur.execute("""
            INSERT INTO tickets (
                booking_code, trip_id, user_id, seats, passenger_name,
                passenger_phone, passenger_email, total_amount, payment_method, booking_time, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'CONFIRMED')
        """, (
            booking_code, trip_id, user_id, seats_str,
            passenger_info.get("name", "Khách Hàng"),
            passenger_info.get("phone", ""),
            passenger_info.get("email", ""),
            total_amount, payment_method, booking_time
        ))

        log_action(cur, "BOOKING", f"Đặt vé thành công: {booking_code} | Ghế: {seats_str} | Số tiền: {total_amount:,} đ")
        cur.close()
        conn.close()
        return True, {
            "booking_code": booking_code,
            "total_amount": total_amount,
            "seats": seats_str,
            "booking_time": booking_time
        }

# --- Lịch sử vé, Hủy vé & Thống kê cá nhân (STT 18, 19, 33) ---
def get_user_tickets(user_id: int):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.*, tr.from_city, tr.to_city, tr.departure_time, tr.bus_number, tr.bus_type
            FROM tickets t
            JOIN trips tr ON t.trip_id = tr.id
            WHERE t.user_id = %s
            ORDER BY t.id DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

def cancel_ticket(ticket_id_or_code: str, user_id: int = None, is_admin: bool = False):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        if str(ticket_id_or_code).isdigit():
            cur.execute("SELECT * FROM tickets WHERE id = %s", (int(ticket_id_or_code),))
        else:
            cur.execute("SELECT * FROM tickets WHERE booking_code = %s", (str(ticket_id_or_code),))
        ticket = cur.fetchone()
        if not ticket:
            cur.close()
            conn.close()
            return False, "Không tìm thấy vé!"
        if not is_admin and user_id and ticket["user_id"] != user_id:
            cur.close()
            conn.close()
            return False, "Bạn không có quyền hủy vé này!"
        if ticket["status"] == "CANCELLED":
            cur.close()
            conn.close()
            return False, "Vé này đã hủy trước đó!"

        trip_id = ticket["trip_id"]
        seat_list = [s.strip() for s in ticket["seats"].split(",") if s.strip()]
        for s in seat_list:
            cur.execute("UPDATE seats SET status = %s, held_by_token = NULL, held_time = 0 WHERE trip_id = %s AND seat_number = %s", (SEAT_AVAILABLE, trip_id, s))

        cur.execute("UPDATE tickets SET status = 'CANCELLED' WHERE id = %s", (ticket["id"],))
        log_action(cur, "CANCEL_TICKET", f"Đã hủy vé: {ticket['booking_code']} (Ghế {ticket['seats']})")
        cur.close()
        conn.close()
        return True, {"trip_id": trip_id, "seats": seat_list}

def get_personal_stats(user_id: int):
    """Client: Thống kê cá nhân (STT 33)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total_tickets FROM tickets WHERE user_id = %s", (user_id,))
        total_tickets = cur.fetchone()["total_tickets"]

        cur.execute("SELECT COALESCE(SUM(total_amount), 0) AS total_spent FROM tickets WHERE user_id = %s AND status = 'CONFIRMED'", (user_id,))
        total_spent = cur.fetchone()["total_spent"]

        cur.execute("SELECT COUNT(*) AS cancelled_tickets FROM tickets WHERE user_id = %s AND status = 'CANCELLED'", (user_id,))
        cancelled_tickets = cur.fetchone()["cancelled_tickets"]

        cur.close()
        conn.close()
        return {
            "total_tickets": total_tickets,
            "total_spent": int(total_spent),
            "cancelled_tickets": cancelled_tickets
        }

# --- Thống kê & Quản lý toàn bộ cho Admin (STT 33, 34) ---
def admin_add_trip(bus_number, bus_type, from_city, to_city, departure_time, price, total_seats):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trips (bus_number, bus_type, from_city, to_city, departure_time, price, total_seats)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (bus_number, bus_type, from_city, to_city, departure_time, price, total_seats))
        trip_id = cur.lastrowid
        _generate_seats_for_trip(cur, trip_id, total_seats)
        log_action(cur, "ADD_TRIP", f"Thêm chuyến mới #{trip_id}: {from_city} -> {to_city} ({bus_number})")
        cur.close()
        conn.close()
        return True, trip_id

def admin_get_all_tickets():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.*, u.username, tr.from_city, tr.to_city, tr.departure_time, tr.bus_number
            FROM tickets t
            JOIN users u ON t.user_id = u.id
            JOIN trips tr ON t.trip_id = tr.id
            ORDER BY t.id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

def admin_get_stats():
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM trips")
        trips_count = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM tickets WHERE status = 'CONFIRMED'")
        tickets_count = cur.fetchone()["cnt"]

        cur.execute("SELECT COALESCE(SUM(total_amount), 0) AS total FROM tickets WHERE status = 'CONFIRMED'")
        total_revenue = int(cur.fetchone()["total"])

        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        users_count = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM vehicles")
        vehicles_count = cur.fetchone()["cnt"]

        cur.close()
        conn.close()
        return {
            "trips_count": trips_count,
            "tickets_count": tickets_count,
            "total_revenue": total_revenue,
            "users_count": users_count,
            "vehicles_count": vehicles_count
        }

# --- Thông báo Real-time (STT 20) ---
def add_notification(user_id, title, message):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notifications (user_id, title, message)
            VALUES (%s, %s, %s)
        """, (user_id, title, message))
        log_action(cur, "NOTIFICATION", f"Gửi thông báo: {title}")
        cur.close()
        conn.close()
        return True

def get_notifications(user_id=None):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        if user_id:
            cur.execute("""
                SELECT * FROM notifications
                WHERE user_id IS NULL OR user_id = %s
                ORDER BY id DESC LIMIT 20
            """, (user_id,))
        else:
            cur.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

# --- Nhật ký hệ thống (Logs - STT 28) ---
def admin_get_logs(limit=50):
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

# --- Sao lưu & Khôi phục CSDL (Backup & Recovery - STT 31, 32) ---
def backup_database():
    """Sao lưu toàn bộ dữ liệu MySQL ra cấu trúc JSON (STT 31)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        backup_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tables": {}
        }
        for table in ["users", "vehicles", "trips", "seats", "tickets", "notifications", "system_logs"]:
            cur.execute(f"SELECT * FROM `{table}`")
            backup_data["tables"][table] = cur.fetchall()

        cur.close()
        conn.close()
        return backup_data

def restore_database(backup_data):
    """Khôi phục dữ liệu từ bản sao lưu JSON (STT 32)."""
    with db_lock:
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Tạm thời tắt foreign key checks để import an toàn
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table, rows in backup_data.get("tables", {}).items():
                cur.execute(f"TRUNCATE TABLE `{table}`")
                if rows:
                    cols = list(rows[0].keys())
                    cols_str = ", ".join([f"`{c}`" for c in cols])
                    val_placeholders = ", ".join(["%s" for _ in cols])
                    insert_sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({val_placeholders})"
                    val_tuples = [tuple(r[c] for c in cols) for r in rows]
                    cur.executemany(insert_sql, val_tuples)
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            log_action(cur, "RESTORE_DB", "Đã khôi phục CSDL từ file Backup thành công")
            cur.close()
            conn.close()
            return True, "Khôi phục dữ liệu thành công!"
        except Exception as e:
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            cur.close()
            conn.close()
            return False, f"Lỗi khôi phục: {e}"
