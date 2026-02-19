"""
Modelos de dominio para el sistema de reservaciones:
- Hotel
- Customer
- Reservation

Incluye:
- @dataclass con tipado estático.
- Validaciones estructurales en __post_init__.
- Serialización/deserialización a dict (para persistencia JSON).
- Utilidades de validación básicas (email, fechas).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Dict, Optional
import re
import uuid


# ---------- Utilidades ---------- #

_EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)


def _validate_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field_name}' no puede estar vacío.")


def _validate_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"'{field_name}' debe ser un entero positivo.")


def _validate_email(value: str) -> None:
    if not isinstance(value, str) or not _EMAIL_REGEX.match(value):
        raise ValueError("Email inválido.")


def _date_from_iso(value: str) -> date:
    """Convierte 'YYYY-MM-DD' a date. Lanza ValueError si es inválida."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception as exc:
        raise ValueError(f"Fecha inválida (esperado YYYY-MM-DD): {value}") from exc


def _date_to_iso(d: date) -> str:
    return d.isoformat()


def generate_id(prefix: str) -> str:
    """Genera IDs legibles, p. ej. 'HOTEL-<uuid4>'."""
    return f"{prefix}-{uuid.uuid4()}"


# ---------- Modelos ---------- #

@dataclass(slots=True)
class Hotel:
    """
    Representa un hotel.

    Regla: total_rooms > 0.
    """
    hotel_id: str
    name: str
    city: str
    total_rooms: int
    address: Optional[str] = None
    rating: Optional[float] = None  # 0.0 - 5.0 (no obligatorio)

    def __post_init__(self) -> None:
        _validate_non_empty(self.hotel_id, "hotel_id")
        _validate_non_empty(self.name, "name")
        _validate_non_empty(self.city, "city")
        _validate_positive_int(self.total_rooms, "total_rooms")

        if self.rating is not None:
            if not isinstance(self.rating, (int, float)) or not (0.0 <= float(self.rating) <= 5.0):
                raise ValueError("rating debe estar entre 0.0 y 5.0.")

    # ---------- Serialización ---------- #

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hotel":
        # Normaliza/valida campos mínimos esperados
        required = ("hotel_id", "name", "city", "total_rooms")
        for k in required:
            if k not in data:
                raise ValueError(f"Falta campo requerido en Hotel: {k}")
        return cls(
            hotel_id=str(data["hotel_id"]),
            name=str(data["name"]),
            city=str(data["city"]),
            total_rooms=int(data["total_rooms"]),
            address=str(data["address"]).strip() if data.get("address") else None,
            rating=float(data["rating"]) if data.get("rating") is not None else None,
        )


@dataclass(slots=True)
class Customer:
    """
    Representa un cliente.

    Reglas:
    - full_name no vacío.
    - email con formato válido.
    """
    customer_id: str
    full_name: str
    email: str
    phone: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.customer_id, "customer_id")
        _validate_non_empty(self.full_name, "full_name")
        _validate_email(self.email)

        if self.phone is not None and not isinstance(self.phone, str):
            raise ValueError("phone debe ser cadena si se proporciona.")

    # ---------- Serialización ---------- #

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Customer":
        required = ("customer_id", "full_name", "email")
        for k in required:
            if k not in data:
                raise ValueError(f"Falta campo requerido en Customer: {k}")
        return cls(
            customer_id=str(data["customer_id"]),
            full_name=str(data["full_name"]),
            email=str(data["email"]),
            phone=str(data["phone"]) if data.get("phone") else None,
        )


@dataclass(slots=True)
class Reservation:
    """
    Representa una reserva entre un Customer y un Hotel.

    Reglas:
    - check_in < check_out
    - status en {"ACTIVE", "CANCELED"}
    - hotel_id y customer_id no vacíos
    - room_number opcional pero, si se usa, entero positivo
    """
    reservation_id: str
    hotel_id: str
    customer_id: str
    check_in: date
    check_out: date
    room_number: Optional[int] = None
    status: str = field(default="ACTIVE")

    def __post_init__(self) -> None:
        _validate_non_empty(self.reservation_id, "reservation_id")
        _validate_non_empty(self.hotel_id, "hotel_id")
        _validate_non_empty(self.customer_id, "customer_id")

        if not isinstance(self.check_in, date):
            raise ValueError("check_in debe ser datetime.date.")
        if not isinstance(self.check_out, date):
            raise ValueError("check_out debe ser datetime.date.")
        if not (self.check_in < self.check_out):
            raise ValueError("check_in debe ser anterior a check_out.")

        if self.room_number is not None:
            _validate_positive_int(self.room_number, "room_number")

        if self.status not in {"ACTIVE", "CANCELED"}:
            raise ValueError("status debe ser 'ACTIVE' o 'CANCELED'.")

    # ---------- Serialización ---------- #

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convertimos fechas a ISO
        data["check_in"] = _date_to_iso(self.check_in)
        data["check_out"] = _date_to_iso(self.check_out)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reservation":
        required = (
            "reservation_id",
            "hotel_id",
            "customer_id",
            "check_in",
            "check_out",
        )
        for k in required:
            if k not in data:
                raise ValueError(f"Falta campo requerido en Reservation: {k}")

        check_in = data["check_in"]
        check_out = data["check_out"]
        # Aceptamos date o str en ISO; normalizamos
        if isinstance(check_in, str):
            check_in = _date_from_iso(check_in)
        if isinstance(check_out, str):
            check_out = _date_from_iso(check_out)

        room_number = data.get("room_number")
        if room_number is not None:
            room_number = int(room_number)

        status = data.get("status", "ACTIVE")

        return cls(
            reservation_id=str(data["reservation_id"]),
            hotel_id=str(data["hotel_id"]),
            customer_id=str(data["customer_id"]),
            check_in=check_in,     # type: ignore[arg-type]
            check_out=check_out,   # type: ignore[arg-type]
            room_number=room_number,
            status=str(status),
        )
