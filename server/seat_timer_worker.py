"""
server/seat_timer_worker.py - Luồng chạy nền tự động giải phóng ghế quá hạn giữ chỗ
Theo đặc tả mục IV.1 trong result.txt: Tự động revert trạng thái ghế về AVAILABLE khi hết thời gian giữ chỗ.
"""

import time
import threading
from server import database as db
from common.constants import SEAT_AVAILABLE, HOLD_TIMEOUT_SECONDS

class SeatTimerWorker(threading.Thread):
    def __init__(self, server_instance, interval: float = 2.0):
        super().__init__(daemon=True)
        self.server = server_instance
        self.interval = interval
        self.is_running = True

    def run(self):
        print("[SeatTimerWorker] Luồng kiểm tra ghế quá hạn đã khởi động thành công.")
        while self.is_running:
            try:
                # Quét các ghế HOLDING đã quá hạn
                released_seats = db.release_expired_seats(HOLD_TIMEOUT_SECONDS)
                if released_seats:
                    # Gom nhóm theo chuyến xe để phát broadcast
                    trips_updated = {}
                    for trip_id, seat_number in released_seats:
                        if trip_id not in trips_updated:
                            trips_updated[trip_id] = {}
                        trips_updated[trip_id][seat_number] = SEAT_AVAILABLE
                        
                    for trip_id, updated_dict in trips_updated.items():
                        print(f"[SeatTimerWorker] Đã giải phóng ghế quá hạn trên chuyến #{trip_id}: {list(updated_dict.keys())}")
                        # Broadcast thông báo tới các Client đang xem chuyến xe này
                        self.server.broadcast_seat_update(trip_id, updated_dict)
                        
            except Exception as e:
                print(f"[SeatTimerWorker] Lỗi khi quét ghế: {e}")
                
            time.sleep(self.interval)

    def stop(self):
        self.is_running = False
