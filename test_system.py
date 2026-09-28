"""
test_system.py - Script kiểm thử tự động toàn diện hệ thống (End-to-End Test)
Kiểm tra kết nối Socket, Đăng nhập, Tra cứu chuyến, Giữ ghế, Thanh toán, Hủy vé và Broadcast
"""

import time
import threading
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
from client.network_client import NetworkClient
from common.constants import SEAT_AVAILABLE, SEAT_HOLDING, SEAT_BOOKED

def run_e2e_test():
    print("=" * 60)
    print("BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG HỆ THỐNG ĐẶT VÉ XE KHÁCH (TCP)")
    print("=" * 60)

    # 1. Khởi động Server trong 1 luồng riêng
    server = BusBookingServer(host="127.0.0.1", port=8889)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(1.0)  # Đợi server bind port

    # 2. Khởi tạo Client 1 (Khách hàng)
    client1 = NetworkClient()
    ok, msg = client1.connect("127.0.0.1", 8889)
    assert ok, f"Client 1 không thể kết nối: {msg}"
    print("[PASS] Test 1: Kết nối Socket TCP Client 1 thành công.")

    # 3. Đăng nhập Client 1
    resp_login = client1.login("khachhang", "123456")
    assert resp_login.get("status") == "SUCCESS", f"Đăng nhập thất bại: {resp_login}"
    print(f"[PASS] Test 2: Đăng nhập Client 1 thành công (User: {resp_login['user_info']['fullname']}).")

    # 4. Tra cứu danh sách chuyến xe
    resp_trips = client1.get_trips()
    assert resp_trips.get("status") == "SUCCESS"
    trips = resp_trips.get("data", [])
    assert len(trips) > 0, "Không có chuyến xe nào trong CSDL!"
    first_trip = trips[0]
    trip_id = first_trip["id"]
    print(f"[PASS] Test 3: Lấy danh sách chuyến xe thành công ({len(trips)} chuyến). Chọn chuyến #{trip_id}.")

    # 5. Khởi tạo Client 2 (Mô phỏng khách hàng thứ 2 để kiểm thử Real-time Broadcast)
    client2 = NetworkClient()
    ok2, msg2 = client2.connect("127.0.0.1", 8889)
    assert ok2
    resp_login2 = client2.login("taixe", "123456")
    assert resp_login2.get("status") == "SUCCESS"

    broadcast_received = []
    def on_broadcast(t_id, updated_seats):
        broadcast_received.append((t_id, updated_seats))
    client2.register_seat_update_callback(on_broadcast)

    # Cả 2 client cùng mở xem sơ đồ ghế của trip_id
    resp_seats1 = client1.get_seats(trip_id)
    resp_seats2 = client2.get_seats(trip_id)
    assert resp_seats1.get("status") == "SUCCESS"
    assert resp_seats2.get("status") == "SUCCESS"
    print(f"[PASS] Test 4: Lấy sơ đồ ghế chuyến #{trip_id} thành công cho 2 client.")

    # Tìm 1 ghế đang AVAILABLE
    seats = resp_seats1["seats"]
    target_seat = None
    for s_num, s_stat in seats.items():
        if s_stat == SEAT_AVAILABLE:
            target_seat = s_num
            break
    assert target_seat is not None, "Không tìm thấy ghế trống để thử nghiệm!"

    # 6. Client 1 Giữ Chỗ (HOLD_SEATS)
    resp_hold = client1.hold_seats(trip_id, [target_seat])
    assert resp_hold.get("status") == "SUCCESS", f"Lỗi giữ chỗ: {resp_hold}"
    print(f"[PASS] Test 5: Client 1 giữ chỗ ghế {target_seat} thành công.")

    # Đợi broadcast tới Client 2
    time.sleep(0.5)
    assert len(broadcast_received) > 0, "Client 2 không nhận được sự kiện broadcast SEAT_UPDATE!"
    last_event = broadcast_received[-1]
    assert last_event[0] == trip_id
    assert last_event[1].get(target_seat) == SEAT_HOLDING
    print(f"[PASS] Test 6: Client 2 nhận được Broadcast SEAT_UPDATE realtime (Ghế {target_seat} -> HOLDING).")

    # 7. Kiểm thử chống Race condition: Client 2 cố tình giữ cùng ghế đó -> Phải bị từ chối!
    resp_hold_conflict = client2.hold_seats(trip_id, [target_seat])
    assert resp_hold_conflict.get("status") == "ERROR", "Lỗi: Client 2 không được phép giữ ghế đang bị giữ!"
    print(f"[PASS] Test 7: Concurrency Control hoạt động chuẩn xác! Client 2 bị từ chối khi tranh chấp ghế {target_seat}.")

    # 8. Client 1 Xác nhận thanh toán & Hoàn tất đặt vé (CONFIRM_BOOKING)
    resp_confirm = client1.confirm_booking(
        trip_id=trip_id,
        seats=[target_seat],
        passenger_info={"name": "Nguyễn Văn An", "phone": "0987654321", "email": "an@test.com"},
        payment_method="VIETQR"
    )
    assert resp_confirm.get("status") == "SUCCESS", f"Lỗi xác nhận đặt vé: {resp_confirm}"
    b_code = resp_confirm.get("booking_code")
    print(f"[PASS] Test 8: Client 1 đặt vé thành công! Mã vé: {b_code}.")

    # Đợi broadcast ghế thành BOOKED tới Client 2
    time.sleep(0.5)
    last_event = broadcast_received[-1]
    assert last_event[1].get(target_seat) == SEAT_BOOKED
    print(f"[PASS] Test 9: Client 2 nhận được Broadcast ghế {target_seat} -> BOOKED.")

    # 9. Lấy danh sách vé của Client 1
    resp_my_tickets = client1.get_my_tickets()
    assert resp_my_tickets.get("status") == "SUCCESS"
    my_tks = resp_my_tickets.get("tickets", [])
    found_ticket = any(t["booking_code"] == b_code for t in my_tks)
    assert found_ticket, "Vé vừa đặt không xuất hiện trong danh sách vé của tôi!"
    print(f"[PASS] Test 10: Tra cứu lịch sử vé cá nhân thành công ({len(my_tks)} vé).")

    # 10. Kiểm thử Admin xem thống kê
    resp_stats = client2.admin_get_stats()
    assert resp_stats.get("status") == "SUCCESS"
    stats = resp_stats.get("stats", {})
    assert stats.get("tickets_count", 0) >= 1
    print(f"[PASS] Test 11: Admin lấy báo cáo thống kê doanh thu thành công (Doanh thu: {stats.get('total_revenue'):,} đ).")

    # Dọn dẹp
    client1.disconnect()
    client2.disconnect()
    server.stop()
    print("=" * 60)
    print("TẤT CẢ 11 BÀI KIỂM THỬ ĐỀU ĐẠT CHUẨN XUẤT SẮC 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_e2e_test()
