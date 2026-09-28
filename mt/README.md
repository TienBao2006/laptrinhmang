# HỆ THỐNG ĐẶT VÉ XE KHÁCH QUA MẠNG (BUS BOOKING TCP SOCKET SYSTEM)
> **Đồ án môn học: Lập trình mạng (Network Programming)**  
> **Kiến trúc: Client - Server sử dụng TCP Socket với đa luồng và đồng bộ thời gian thực**

---

## I. TỔNG QUAN HỆ THỐNG
Hệ thống mô phỏng nền tảng đặt vé xe khách trực tuyến đa trạm kết nối tới máy chủ trung tâm:
- **Giao thức truyền thông:** TCP/IP (`socket.AF_INET`, `socket.SOCK_STREAM`) hướng liên kết, tin cậy tuyệt đối.
- **Đóng gói bản tin (Framing):** Kỹ thuật **Length-Prefixed Framing** (4 byte Big-Endian xác định độ dài gói tin + Payload UTF-8 JSON) giúp loại bỏ 100% hiện tượng **Dính gói (Sticky Packets)** và **Phân mảnh gói (Packet Fragmentation)** trong luồng TCP Byte Stream.
- **Xử lý Đa luồng (Multi-threading):** Mỗi kết nối máy trạm Client được máy chủ gán 1 luồng riêng biệt (`ClientHandler`).
- **Kiểm soát Tranh chấp (Concurrency & Race Condition Control):** Sử dụng khóa tương hỗ (`threading.Lock`) và giao dịch CSDL để đảm bảo không bao giờ có 2 người cùng đặt thành công 1 ghế cùng một thời điểm.
- **Đồng bộ hóa Thời gian thực (Real-time Broadcast Socket):** Khi bất kỳ client nào chọn giữ chỗ, thanh toán hoặc hủy vé, Server lập tức phát sóng sự kiện `SEAT_UPDATE` tới tất cả các Client khác đang cùng mở xem chuyến xe đó để đổi màu ghế tức thời.
- **Cơ chế Giữ chỗ tạm thời có đếm ngược (Seat Holding & Countdown Timer):** Khi khách hàng chọn ghế và tiến hành thanh toán, ghế chuyển sang trạng thái `HOLDING` trong 180 giây. Nếu khách không thanh toán hoặc ngắt kết nối đột ngột, tiến trình chạy nền `SeatTimerWorker` sẽ tự động hoàn trả ghế về `AVAILABLE`.
- **Thanh toán VietQR & Mã QR Check-in vé xe:** Sinh mã VietQR NAPAS 247 và mã QR xác thực vé điện tử thuần Python (Zero-dependency, không cần cài thư viện bên ngoài).
- **Phân quyền người dùng:** Khách hàng/tài xế dùng `run_client.py`; Admin/Staff dùng giao diện quản trị riêng qua `run_admin.py` trên máy server hoặc máy quản trị.

---

## II. CẤU TRÚC THƯ MỤC DỰ ÁN
```
DA/
├── common/
│   ├── __init__.py
│   ├── constants.py          # Hằng số chung (PORT, Trạng thái ghế, Action types, Roles)
│   ├── protocol.py           # Đóng gói/giải mã bản tin với Length-Prefixed Framing
│   └── qr_generator.py       # Bộ sinh ma trận QR và vẽ lên Canvas (Zero-dependency)
│
├── server/
│   ├── __init__.py
│   ├── server_main.py        # Entry point máy chủ TCP Socket, quản lý kết nối
│   ├── client_handler.py     # Luồng tiếp nhận và xử lý Request của từng Client
│   ├── database.py           # Quản lý CSDL SQLite (users, trips, seats, tickets)
│   ├── business_logic.py     # Nghiệp vụ đặt vé, quản lý phiên và Race Condition
│   ├── seat_timer_worker.py  # Luồng nền tự động giải phóng ghế quá hạn giữ chỗ
│   └── models.py             # Định nghĩa dataclass User, Trip, Seat, Ticket
│
├── client/
│   ├── __init__.py
│   ├── client_main.py        # Entry point máy trạm khách hàng
│   ├── network_client.py     # Quản lý Socket client, Request/Response và nhận broadcast
│   ├── gui_login.py          # Giao diện Đăng nhập / Đăng ký & Cấu hình IP/Port
│   ├── gui_booking.py        # Giao diện Tìm kiếm, Sơ đồ ghế trực quan & Thanh toán
│   ├── gui_history.py        # Giao diện Xem vé đã đặt & QR code check-in
│   └── gui_admin.py          # Giao diện quản trị, chỉ mở bằng run_admin.py
│
├── data/
│   └── bus_booking.db        # File CSDL SQLite (tự động khởi tạo khi chạy server)
│
├── run_server.py             # Script khởi động nhanh Server
├── run_admin.py              # Script khởi động giao diện quản trị
├── run_client.py             # Script khởi động nhanh Client
├── chay_server.bat           # File thực thi Windows khởi động Server
├── chay_client.bat           # File thực thi Windows khởi động Client
└── result.txt                # Bản đặc tả thiết kế chương trình ban đầu
```

---

## III. TÀI KHOẢN DÙNG THỬ MẶC ĐỊNH
Hệ thống đã tự động khởi tạo sẵn 2 tài khoản mẫu (có nút điền nhanh trên màn hình đăng nhập):

| Loại tài khoản | Tên đăng nhập | Mật khẩu | Quyền hạn |
| :--- | :--- | :--- | :--- |
| **Quản trị viên (Admin)** | `admin` | `admin123` | Quản trị chuyến xe, xem toàn bộ vé, thống kê doanh thu |
| **Khách hàng (User)** | `khachhang` | `123456` | Tìm chuyến, xem sơ đồ ghế realtime, giữ chỗ, thanh toán, hủy vé |

*(Người dùng cũng có thể tự đăng ký tài khoản mới ngay trên giao diện)*

---

## IV. HƯỚNG DẪN CÀI ĐẶT & CHẠY CHƯƠNG TRÌNH

### 1. Yêu cầu môi trường
- Python 3.8+ (đã tích hợp sẵn `sqlite3`, `socket`, `threading`, `tkinter`).
- **Không cần cài thêm bất kỳ thư viện bên ngoài nào (0 dependencies)**.

### 2. Khởi động Máy chủ (Server)
Mở một cửa sổ Terminal tại thư mục dự án và chạy:
```bash
python run_server.py
```
*Hoặc nháy đúp vào file `chay_server.bat` trên Windows.*

Máy chủ sẽ thông báo:
```text
======================================================================
  HỆ THỐNG MÁY CHỦ ĐẶT VÉ XE KHÁCH QUA MẠNG (TCP SOCKET SERVER)
======================================================================
[Database] CSDL đã sẵn sàng hoạt động.
[SeatTimerWorker] Luồng kiểm tra ghế quá hạn đã khởi động thành công.
[TCP Server] Đang lắng nghe kết nối tại: 0.0.0.0:8888
[TCP Server] Hỗ trợ đa luồng (Multi-threading) và Broadcast Real-time.
----------------------------------------------------------------------
```

### 3. Khởi động Máy trạm Khách hàng (Client)
Mở một cửa sổ Terminal khác (hoặc mở nhiều cửa sổ để thử nghiệm nhiều người dùng cùng lúc):
```bash
python run_client.py
```
*Hoặc nháy đúp vào file `chay_client.bat` trên Windows.*

### 4. Mở giao diện quản trị
Trên máy server hoặc máy quản trị, mở một cửa sổ Terminal khác và chạy:
```bash
python run_admin.py
```
Admin/Staff đăng nhập tại giao diện này; ứng dụng `run_client.py` chỉ dành cho khách hàng/tài xế.

---

## V. CÁCH KIỂM THỬ TÍNH NĂNG ĐỒ ÁN (DEMO SCENARIOS)

### Kịch bản 1: Kiểm thử Broadcast Thời Gian Thực (Real-time Broadcast)
1. Mở cùng lúc **2 cửa sổ Client** (Client A và Client B).
2. Ở cả 2 Client, cùng đăng nhập và chọn chuyến xe `#101` (Hà Nội - Đà Nẵng).
3. Client A nhấp chọn ghế **A08** và bấm **"🔒 Giữ Chỗ & Tiến Hành Thanh Toán"**.
4. **Quan sát Client B:** Ghế **A08** lập tức chuyển từ màu Xanh lá sang màu Vàng cam (`HOLDING`), bị khóa không cho Client B chọn, hoàn toàn tự động mà **không cần bấm F5 hay tải lại**.

### Kịch bản 2: Kiểm thử Cơ Chế Giải Phóng Ghế Quá Hạn (Seat Holding Timer)
1. Ở Client A, khi đang trong màn hình thanh toán đếm ngược (`⏳ Đang giữ chỗ...`).
2. Chờ hết thời gian hoặc tắt ứng dụng Client A (ngắt kết nối đột ngột).
3. Máy chủ phát hiện Client ngắt kết nối hoặc hết hạn `HOLD_TIMEOUT_SECONDS`, tự động hoàn lại trạng thái ghế về màu Xanh (`AVAILABLE`).
4. Client B lập tức thấy ghế **A08** mở lại màu xanh để có thể đặt.

### Kịch bản 3: Kiểm thử Thanh toán VietQR & Xem Vé Điện Tử
1. Chọn ghế và bấm giữ chỗ.
2. Kiểm tra thông tin hành khách và xem mã **VietQR** được vẽ trực tiếp trên cửa sổ.
3. Bấm **"✅ Tôi Đã Chuyển Khoản - Xác Nhận Đặt Vé"**.
4. Cửa sổ **"Vé Của Tôi"** tự động mở ra, hiển thị thẻ vé điện tử với thông tin chi tiết và mã **QR Code Check-in**.
5. Thử bấm **"❌ Hủy Vé Này"** -> Ghế trên sơ đồ lập tức được giải phóng tức thì.

### Kịch bản 4: Kiểm thử Phân quyền Quản trị (Admin Panel)
1. Mở `run_admin.py` trên máy server hoặc máy quản trị.
2. Đăng nhập bằng tài khoản `admin` / `admin123`.
3. Xem biểu đồ thống kê: Tổng doanh thu, Tổng số vé bán, Danh sách chi tiết vé toàn bộ khách hàng.
4. Chuyển sang tab **"➕ Mở Thêm Chuyến Xe Mới"** để tạo chuyến xe mới, sơ đồ ghế sẽ được tự động khởi tạo vào hệ thống CSDL.
