"""Классы данных (dataclass), соответствующие таблицам БД."""
from dataclasses import dataclass
from typing import Optional

STATUS_STORED = "stored"          # на хранении
STATUS_ISSUED = "issued"          # выдан получателю
STATUS_RETURNED = "returned"      # возвращён отправителю
STATUS_NAMES = {
    STATUS_STORED: "На хранении",
    STATUS_ISSUED: "Выдан",
    STATUS_RETURNED: "Возвращён",
}


@dataclass
class Carrier:
    """Служба доставки."""

    id: Optional[int]
    name: str
    phone: Optional[str] = None


@dataclass
class Recipient:
    """Получатель заказов (клиент пункта выдачи)."""

    id: Optional[int]
    full_name: str
    phone: str
    email: Optional[str] = None
    registration_date: Optional[str] = None


@dataclass
class Employee:
    """Сотрудник пункта выдачи."""

    id: Optional[int]
    full_name: str
    role: str
    login: str
    password_hash: str


@dataclass
class Order:
    """Заказ."""

    id: Optional[int]
    tracking_number: str
    description: str
    amount: float
    pickup_code: str
    cell: str
    recipient_id: int
    carrier_id: int
    status: str = STATUS_STORED
    received_date: Optional[str] = None
    storage_until: Optional[str] = None


@dataclass
class Issue:
    """Выдача заказа получателю."""

    id: Optional[int]
    order_id: int
    employee_id: int
    paid_amount: float
    issue_date: Optional[str] = None
