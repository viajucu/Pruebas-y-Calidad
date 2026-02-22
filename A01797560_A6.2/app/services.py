"""
Capa de reglas de negocio para el sistema de reservaciones.
Orquesta repos (archivos JSON) y modelos de dominio. Expone servicios
para hoteles, clientes y reservas.

Para cumplir Pylint:
- Se usan **kwargs** para parámetros opcionales y reducir
  'too-many-arguments' sin romper compatibilidad con los tests.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any, Iterable, List, Optional, Tuple

from .errors import (
    BusinessRuleError,
    ConflictError,
    DuplicateIdError,
    NotFoundError,
    ValidationError,
)
from .models import Customer, Hotel, Reservation, generate_id
from .repository import (
    CustomerRepository,
    HotelRepository,
    ReservationRepository,
)

# ---------- Utilidades internas ----------


def _validate_dates(check_in: date, check_out: date) -> None:
    """Valida que check_in y check_out sean date y que check_in < check_out."""
    if not isinstance(check_in, date) or not isinstance(check_out, date):
        raise ValidationError("check_in y check_out deben ser datetime.date")
    if check_in >= check_out:
        raise ValidationError("check_in debe ser anterior a check_out")


def _overlaps(
    a_start: date, a_end: date, b_start: date, b_end: date
) -> bool:
    """True si [a_start, a_end) y [b_start, b_end) se solapan."""
    return not (a_end <= b_start or a_start >= b_end)


def _active_reservations(
    reservations: Iterable[Reservation],
) -> List[Reservation]:
    """Filtra y devuelve reservas con status ACTIVE."""
    return [r for r in reservations if r.status == "ACTIVE"]


def _active_overlaps_for_hotel(
    reservations: Iterable[Reservation],
    check_in: date,
    check_out: date,
) -> List[Reservation]:
    """Reservas ACTIVAS que se solapan con [check_in, check_out)."""
    _validate_dates(check_in, check_out)
    return [
        r
        for r in _active_reservations(reservations)
        if _overlaps(r.check_in, r.check_out, check_in, check_out)
    ]


def _max_concurrent_active(reservations: Iterable[Reservation]) -> int:
    """Pico de ocupación (reservas ACTIVAS solapadas) por 'line sweep'."""
    events: List[Tuple[date, int]] = []
    for r in _active_reservations(reservations):
        events.append((r.check_in, 1))
        events.append((r.check_out, -1))
    events.sort()

    current = 0
    peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


# ---------- Servicios ----------


class HotelService:
    """Reglas de negocio para Hoteles y Reservas asociadas."""

    def __init__(
        self,
        hotels: HotelRepository,
        customers: CustomerRepository,
        reservations: ReservationRepository,
    ) -> None:
        """Inicializa el servicio con repos de hoteles/clientes/reservas."""
        self._hotels = hotels
        self._customers = customers
        self._reservations = reservations

    # ---------- HOTELS ----------

    def create_hotel(
        self,
        hotel_id: str,
        name: str,
        city: str,
        total_rooms: int,
        **kwargs: Any,
    ) -> Hotel:
        """
        Crea un hotel; falla si el ID ya existe.

        kwargs admitidos: address (str | None), rating (float | None)
        """
        if self._hotels.get_by_id(hotel_id) is not None:
            raise DuplicateIdError(f"Hotel '{hotel_id}' ya existe")

        address: Optional[str] = kwargs.get("address")
        rating: Optional[float] = kwargs.get("rating")

        hotel = Hotel(
            hotel_id=hotel_id,
            name=name,
            city=city,
            total_rooms=int(total_rooms),
            address=address,
            rating=rating,
        )
        self._hotels.upsert(hotel)
        return hotel

    def get_hotel(self, hotel_id: str) -> Hotel:
        """Obtiene un hotel por ID o lanza NotFoundError."""
        hotel = self._hotels.get_by_id(hotel_id)
        if hotel is None:
            raise NotFoundError(f"Hotel '{hotel_id}' no existe")
        return hotel

    def list_hotels(self) -> List[Hotel]:
        """Lista todos los hoteles."""
        return self._hotels.list_all()

    def update_hotel(self, hotel_id: str, **kwargs: Any) -> Hotel:
        """
        Modifica datos del hotel y valida reducción segura de total_rooms.

        kwargs admitidos: name, city, total_rooms, address, rating.
        """
        hotel = self.get_hotel(hotel_id)

        name: Optional[str] = kwargs.get("name")
        city: Optional[str] = kwargs.get("city")
        total_rooms: Optional[int] = kwargs.get("total_rooms")
        address: Optional[str] = kwargs.get("address")
        rating: Optional[float] = kwargs.get("rating")

        if total_rooms is not None:
            if not isinstance(total_rooms, int) or total_rooms <= 0:
                raise ValidationError(
                    "total_rooms debe ser entero positivo"
                )

            all_res = self._reservations.list_by_hotel(hotel_id)
            peak = _max_concurrent_active(all_res)
            if total_rooms < peak:
                raise BusinessRuleError(
                    "No se puede reducir total_rooms por debajo del pico de "
                    f"ocupación existente ({peak})"
                )

        updated = replace(
            hotel,
            name=hotel.name if name is None else name,
            city=hotel.city if city is None else city,
            total_rooms=(
                hotel.total_rooms if total_rooms is None else total_rooms
            ),
            address=hotel.address if address is None else address,
            rating=hotel.rating if rating is None else rating,
        )

        # Revalidación ligera del modelo a partir del dict
        Hotel.from_dict(updated.to_dict())

        self._hotels.upsert(updated)
        return updated

    def delete_hotel(self, hotel_id: str) -> None:
        """Elimina un hotel si no tiene reservas activas presentes/futuras."""
        _ = self.get_hotel(hotel_id)  # confirma existencia

        active_or_future = [
            r
            for r in _active_reservations(
                self._reservations.list_by_hotel(hotel_id)
            )
            if r.check_out > date.today()
        ]
        if active_or_future:
            raise BusinessRuleError(
                "No se puede eliminar un hotel con reservas activas "
                "(presentes o futuras)"
            )

        ok = self._hotels.delete(hotel_id)
        if not ok:
            # C0209: usar f-string en lugar de .format()
            raise NotFoundError(
                f"Hotel '{hotel_id}' no existe (eliminado concurrentemente)"
            )

    # ---------- RESERVATIONS ----------

    def reserve_room(
        self,
        customer_id: str,
        hotel_id: str,
        check_in: date,
        check_out: date,
        **kwargs: Any,
    ) -> Reservation:
        """
        Crea una reserva si hay disponibilidad en [check_in, check_out).

        kwargs admitidos: reservation_id (str | None),
        room_number (int | None)
        """
        _validate_dates(check_in, check_out)
        hotel = self.get_hotel(hotel_id)

        customer = self._customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer '{customer_id}' no existe")

        overlaps = _active_overlaps_for_hotel(
            self._reservations.list_by_hotel(hotel_id),
            check_in,
            check_out,
        )
        available = hotel.total_rooms - len(overlaps)
        if available <= 0:
            raise BusinessRuleError(
                "No hay habitaciones disponibles para esas fechas"
            )

        rid = kwargs.get("reservation_id") or generate_id("RES")
        room_number: Optional[int] = kwargs.get("room_number")

        reservation = Reservation(
            reservation_id=rid,
            hotel_id=hotel.hotel_id,
            customer_id=customer.customer_id,
            check_in=check_in,
            check_out=check_out,
            room_number=room_number,
            status="ACTIVE",
        )
        self._reservations.upsert(reservation)
        return reservation

    def cancel_reservation(self, reservation_id: str) -> Reservation:
        """Cancela una reserva; idempotente ante segundo intento."""
        res = self._reservations.get_by_id(reservation_id)
        if res is None:
            raise NotFoundError(f"Reservation '{reservation_id}' no existe")
        if res.status == "CANCELED":
            raise ConflictError("La reserva ya está cancelada")

        canceled = replace(res, status="CANCELED")
        self._reservations.upsert(canceled)
        return canceled


class CustomerService:
    """Reglas de negocio para Clientes."""

    def __init__(
        self,
        customers: CustomerRepository,
        reservations: ReservationRepository,
    ) -> None:
        """Inicializa el servicio con repos de clientes y reservas."""
        self._customers = customers
        self._reservations = reservations

    # ---------- CUSTOMERS ----------

    def create_customer(
        self,
        customer_id: str,
        full_name: str,
        email: str,
        **kwargs: Any,
    ) -> Customer:
        """
        Crea un cliente; falla si el ID ya existe.

        kwargs admitidos: phone (str | None)
        """
        if self._customers.get_by_id(customer_id) is not None:
            raise DuplicateIdError(f"Customer '{customer_id}' ya existe")

        phone: Optional[str] = kwargs.get("phone")
        customer = Customer(
            customer_id=customer_id,
            full_name=full_name,
            email=email,
            phone=phone,
        )
        self._customers.upsert(customer)
        return customer

    def get_customer(self, customer_id: str) -> Customer:
        """Obtiene un cliente por ID o lanza NotFoundError."""
        c = self._customers.get_by_id(customer_id)
        if c is None:
            raise NotFoundError(f"Customer '{customer_id}' no existe")
        return c

    def list_customers(self) -> List[Customer]:
        """Lista todos los clientes."""
        return self._customers.list_all()

    def update_customer(self, customer_id: str, **kwargs: Any) -> Customer:
        """
        Actualiza datos del cliente (campos opcionales).

        kwargs admitidos: full_name, email, phone
        """
        c = self.get_customer(customer_id)

        full_name: Optional[str] = kwargs.get("full_name")
        email: Optional[str] = kwargs.get("email")
        phone: Optional[str] = kwargs.get("phone")

        updated = Customer(
            customer_id=c.customer_id,
            full_name=c.full_name if full_name is None else full_name,
            email=c.email if email is None else email,
            phone=c.phone if phone is None else phone,
        )

        # Revalidación a partir del dict
        Customer.from_dict(updated.to_dict())

        self._customers.upsert(updated)
        return updated

    def delete_customer(self, customer_id: str) -> None:
        """Elimina cliente si no tiene reservas activas presentes/futuras."""
        _ = self.get_customer(customer_id)  # confirma existencia

        active_or_future = [
            r
            for r in _active_reservations(
                self._reservations.list_by_customer(customer_id)
            )
            if r.check_out > date.today()
        ]
        if active_or_future:
            raise BusinessRuleError(
                "No se puede eliminar un cliente con reservas activas "
                "(presentes o futuras)"
            )

        ok = self._customers.delete(customer_id)
        if not ok:
            # C0209: usar f-string en lugar de .format()
            raise NotFoundError(
                f"Customer '{customer_id}' no existe "
                "(eliminado concurrentemente)"
            )


class ReservationService:
    """Consultas/operaciones de reservas (atajos)."""

    def __init__(
        self,
        reservations: ReservationRepository,
        hotel_service: HotelService,
    ) -> None:
        """Inicializa el servicio con repos de reservas y servicio de hotel."""
        self._reservations = reservations
        self._hotel_service = hotel_service

    def get_reservation(self, reservation_id: str) -> Reservation:
        """Obtiene reserva por ID o lanza NotFoundError."""
        r = self._reservations.get_by_id(reservation_id)
        if r is None:
            raise NotFoundError(f"Reservation '{reservation_id}' no existe")
        return r

    def list_by_hotel(self, hotel_id: str) -> List[Reservation]:
        """Lista reservas por hotel."""
        return self._reservations.list_by_hotel(hotel_id)

    def list_by_customer(self, customer_id: str) -> List[Reservation]:
        """Lista reservas por cliente."""
        return self._reservations.list_by_customer(customer_id)

    def create(
        self,
        customer_id: str,
        hotel_id: str,
        check_in: date,
        check_out: date,
        **kwargs: Any,
    ) -> Reservation:
        """
        Crea reserva delegando en HotelService.

        kwargs admitidos: reservation_id (str | None),
        room_number (int | None)
        """
        return self._hotel_service.reserve_room(
            customer_id,
            hotel_id,
            check_in,
            check_out,
            **kwargs,
        )

    def cancel(self, reservation_id: str) -> Reservation:
        """Cancela reserva delegando en HotelService."""
        return self._hotel_service.cancel_reservation(reservation_id)
