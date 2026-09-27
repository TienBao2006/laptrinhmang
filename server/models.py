"""
server/models.py - Định nghĩa cấu trúc dữ liệu cho máy chủ đặt vé xe
"""

from dataclasses import dataclass
from typing import Optional, List

@dataclass
class User:
    id: int
    username: str
    password_hash: str
    fullname: str
    phone: str
    email: str
    role: str

@dataclass
class Trip:
    id: int
    bus_number: str
    bus_type: str
    from_city: str
    to_city: str
    departure_time: str
    price: int
    total_seats: int
    available_seats: int = 0

@dataclass
class Seat:
    id: int
    trip_id: int
    seat_number: str
    status: str
    held_by_token: Optional[str] = None
    held_time: Optional[float] = None

@dataclass
class Ticket:
    id: int
    booking_code: str
    trip_id: int
    user_id: int
    seats: str
    passenger_name: str
    passenger_phone: str
    passenger_email: str
    total_amount: int
    payment_method: str
    booking_time: str
    status: str
