"""
Utilidades compartidas para pruebas unitarias.

Se desactiva 'duplicate-code' en este archivo porque los helpers de test
pueden coincidir con patrones usados también en otros tests (p. ej.,
creación de Reservation con fechas y campos mínimos).
"""


from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.models import Customer, Hotel, Reservation


def make_hotel(
    hotel_id: str = "H1",
    name: str = "Hotel",
    city: str = "CDMX",
    total_rooms: int = 10,
) -> Hotel:
    """Crea un Hotel válido con valores por defecto."""
    return Hotel(
        hotel_id=hotel_id,
        name=name,
        city=city,
        total_rooms=total_rooms,
    )


def make_customer(
    customer_id: str = "C1",
    full_name: str = "Cliente",
    email: str = "cliente@example.com",
    phone: Optional[str] = None,
) -> Customer:
    """Crea un Customer válido con valores por defecto."""
    return Customer(
        customer_id=customer_id,
        full_name=full_name,
        email=email,
        phone=phone,
    )


def make_reservation(
    reservation_id: str,
    hotel_id: str,
    check_in: Optional[date] = None,
    check_out: Optional[date] = None,
    *,
    room_number: Optional[int] = None,
) -> Reservation:
    """
    Crea una Reservation válida. Si no se pasan fechas, usa hoy y hoy+1.

    Nota: customer_id se fija a 'C1' para simplificar pruebas.
    """
    if check_in is None:
        check_in = date.today()
    if check_out is None:
        check_out = check_in + timedelta(days=1)

    customer_id = "C1"
    return Reservation(
        reservation_id=reservation_id,
        hotel_id=hotel_id,
        customer_id=customer_id,
        check_in=check_in,
        check_out=check_out,
        room_number=room_number,
    )
