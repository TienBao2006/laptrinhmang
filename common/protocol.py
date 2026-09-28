"""
common/protocol.py - Xử lý đóng gói & giải mã bản tin TCP Socket
Giải quyết triệt để vấn đề "Dính gói" (Sticky Packets) và "Phân mảnh gói" (Packet Fragmentation)
bằng kỹ thuật Length-Prefixed Framing (4-byte Big-Endian Length Prefix + UTF-8 JSON Payload).
"""

import json
import struct
import socket
from datetime import datetime, date, time as dt_time


class _SafeEncoder(json.JSONEncoder):
    """JSON encoder tự động chuyển datetime/date/time thành chuỗi."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%H:%M:%S %d/%m/%Y")
        if isinstance(obj, date):
            return obj.strftime("%d/%m/%Y")
        if isinstance(obj, dt_time):
            return obj.strftime("%H:%M:%S")
        # bytes, bytearray → hex string
        if isinstance(obj, (bytes, bytearray)):
            return obj.hex()
        return super().default(obj)


def send_msg(sock: socket.socket, data: dict) -> bool:
    """
    Đóng gói dữ liệu thành JSON và gửi qua TCP Socket với tiền tố độ dài 4 byte.
    Format gói tin: [4 bytes độ dài (unsigned int)] + [Chuỗi JSON UTF-8]
    Tự động chuyển datetime thành chuỗi để tránh JSONDecodeError.
    """
    try:
        json_bytes = json.dumps(data, ensure_ascii=False, cls=_SafeEncoder).encode('utf-8')
        length = len(json_bytes)
        # struct.pack('!I', length): 4 bytes unsigned int theo chuẩn mạng Big-Endian
        header = struct.pack('!I', length)
        sock.sendall(header + json_bytes)
        return True
    except (socket.error, BrokenPipeError, ConnectionResetError, OSError) as e:
        return False

def _recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Đọc chính xác num_bytes từ TCP stream.
    Nếu socket bị đóng trước khi đọc đủ, trả về None.
    """
    buffer = bytearray()
    while len(buffer) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(buffer))
            if not chunk:
                return None
            buffer.extend(chunk)
        except (socket.error, ConnectionResetError, OSError):
            return None
    return bytes(buffer)

def recv_msg(sock: socket.socket) -> dict:
    """
    Nhận 1 bản tin hoàn chỉnh từ TCP Socket:
    1. Đọc 4 byte header để biết độ dài payload.
    2. Đọc chính xác payload theo độ dài đó.
    3. Giải mã JSON UTF-8 thành Python dictionary.
    Trả về dict nếu thành công, None nếu client/server ngắt kết nối.
    """
    try:
        header = _recv_exact(sock, 4)
        if not header:
            return None
        length = struct.unpack('!I', header)[0]
        
        payload_bytes = _recv_exact(sock, length)
        if not payload_bytes:
            return None
            
        json_str = payload_bytes.decode('utf-8')
        return json.loads(json_str)
    except Exception:
        return None
