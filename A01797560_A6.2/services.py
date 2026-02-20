"""
services.py

Implementar la capa de reglas de negocio del sistema de reservaciones,
orquestando los repositorios de persistencia (archivos JSON) y los
modelos de dominio (Hotel, Customer, Reservation).

Objetivos principales (alineados con los requisitos del ejercicio):
    - Métodos con persistencia para Hotels, Customer y Reservation
    - Centralizar reglas de negocio:
    - Comunicación clara de errores mediante excepciones semánticas
    - Mantener separación de responsabilidades

"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Iterable, List, Optional, Tuple

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


# ----------
# Utilidades internas (reglas de fechas y solapamientos)
# ----------

def _validate_dates(check_in: date, check_out: date) -> None:
    if not isinstance(check_in, date) or not isinstance(check_out, date):
        raise ValidationError("check_in y check_out deben ser datetime.date")
    if not (check_in < check_out):
        raise ValidationError("check_in debe ser anterior a check_out")


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """Retorna True si los rangos [a_start, a_end) y [b_start, b_end) se solapan."""
    # No hay solape si uno termina antes o empieza después del otro:
    return not (a_end <= b_start or a_start >= b_end)


def _active_reservations(reservations: Iterable[Reservation])\
        -> List[Reservation]:
    """Filtra reservas con status ACTIVE."""
    return [r for r in reservations if r.status == "ACTIVE"]


def _current_active_for_hotel(
    reservations: Iterable[Reservation],
    today: Optional[date] = None,
) -> List[Reservation]:
    """
    Reservas ACTIVAS 'en curso' hoy. Útil para restricciones
    al eliminar/modificar hotel.
    Por simplicidad, consideramos activas si check_in <= today < check_out.
    """
    if today is None:
        today = date.today()
    return [
        r for r in _active_reservations(reservations)
        if r.check_in <= today < r.check_out
    ]


def _active_overlaps_for_hotel(
    reservations: Iterable[Reservation],
    check_in: date,
    check_out: date,
) -> List[Reservation]:
    """Reservas ACTIVAS que se solapan con [check_in, check_out)."""
    _validate_dates(check_in, check_out)
    return [
        r for r in _active_reservations(reservations)
        if _overlaps(r.check_in, r.check_out, check_in, check_out)
    ]


# ---------- Servicios ----------

class HotelService:
    """
    Reglas de negocio para Hoteles y Reservas asociadas a hoteles.
    - Crea/actualiza/borra hoteles
    - Muestra hoteles
    - Reserva habitación (verifica disponibilidad por solapamientos)
    - Cancela reserva
    """

    def __init__(
        self,
        hotels: HotelRepository,
        customers: CustomerRepository,
        reservations: ReservationRepository,
    ) -> None:
        self._hotels = hotels
        self._customers = customers
        self._reservations = reservations

    # --------- HOTELS ----------

    def create_hotel(
        self,
        hotel_id: str,
        name: str,
        city: str,
        total_rooms: int,
        address: Optional[str] = None,
        rating: Optional[float] = None,
    ) -> Hotel:
        """Crea un hotel nuevo. Lanza DuplicateIdError si el
        ID ya existe."""
        if self._hotels.get_by_id(hotel_id) is not None:
            raise DuplicateIdError(f"Hotel '{hotel_id}' ya existe")

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
        hotel = self._hotels.get_by_id(hotel_id)
        if hotel is None:
            raise NotFoundError(f"Hotel '{hotel_id}' no existe")
        return hotel

    def list_hotels(self) -> List[Hotel]:
        return self._hotels.list_all()

    def update_hotel(
        self,
        hotel_id: str,
        *,
        name: Optional[str] = None,
        city: Optional[str] = None,
        total_rooms: Optional[int] = None,
        address: Optional[str] = None,
        rating: Optional[float] = None,
    ) -> Hotel:
        """
        Modifica datos del hotel.
        Regla: total_rooms no puede quedar por debajo de la
        ocupación ACTUAL (hoy).
        """
        hotel = self.get_hotel(hotel_id)

        # Si se actualiza total_rooms, validar contra ocupación actual
        if total_rooms is not None:
            if not isinstance(total_rooms, int) or total_rooms <= 0:
                raise ValidationError("total_rooms debe ser entero positivo")
            # Ocupación actual (hoy)
            current = _current_active_for_hotel(
                self._reservations.list_by_hotel(hotel_id)
            )
            if len(current) > total_rooms:
                raise BusinessRuleError(
                    "No se puede reducir total_rooms por debajo de la ocupación actual "
                    f"({len(current)})"
                )

        updated = replace(
            hotel,
            name=name if name is not None else hotel.name,
            city=city if city is not None else hotel.city,
            total_rooms=total_rooms if total_rooms is not None else hotel.total_rooms,
            address=address if address is not None else hotel.address,
            rating=rating if rating is not None else hotel.rating,
        )
        # Revalidación del modelo (replace no llama __post_init__,
        # pero el dataclass ya fue válido;
        # aquí hacemos un truco forzando creación equivalante si deseas
        # revalidar estrictamente)
        Hotel.from_dict(updated.to_dict())

        self._hotels.upsert(updated)
        return updated

    def delete_hotel(self, hotel_id: str) -> None:
        """
        Elimina un hotel.
        Regla: NO permitir si hay reservas ACTIVAS actuales (hoy)
        o futuras.
        """
        # Confirma existencia
        _ = self.get_hotel(hotel_id)

        active_or_future = [
            r for r in _active_reservations(self._reservations.list_by_hotel(hotel_id))
            if r.check_out > date.today()
        ]
        if active_or_future:
            raise BusinessRuleError(
                "No se puede eliminar un hotel con reservas activas "
                "(presentes o futuras)"
            )

        ok = self._hotels.delete(hotel_id)
        if not ok:
            # Raza de condición extremadamente rara si otro
            # proceso borró entre get/delete
            raise NotFoundError(
                f"Hotel '{hotel_id}' no existe"
                "(eliminado concurrentemente)")

    # ---------- RESERVATIONS ----------

    def reserve_room(
        self,
        customer_id: str,
        hotel_id: str,
        check_in: date,
        check_out: date,
        *,
        reservation_id: Optional[str] = None,
        room_number: Optional[int] = None,
    ) -> Reservation:
        """
        Crea una reserva si hay disponibilidad para [check_in, check_out).
        Disponibilidad: total_rooms - reservas_activas_solapadas > 0
        """
        _validate_dates(check_in, check_out)
        hotel = self.get_hotel(hotel_id)
        customer = self._customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer '{customer_id}' no existe")

        solapadas = _active_overlaps_for_hotel(
            self._reservations.list_by_hotel(hotel_id),
            check_in,
            check_out,
        )
        disponibles = hotel.total_rooms - len(solapadas)
        if disponibles <= 0:
            raise BusinessRuleError(
                "No hay habitaciones disponibles para esas fechas")

        rid = reservation_id or generate_id("RES")
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
        res = self._reservations.get_by_id(reservation_id)
        if res is None:
            raise NotFoundError(f"Reservation '{reservation_id}' no existe")
        if res.status == "CANCELED":
            raise ConflictError("La reserva ya está cancelada")

        canceled = replace(res, status="CANCELED")
        self._reservations.upsert(canceled)
        return canceled


class CustomerService:
    """
    Reglas de negocio para Clientes.
    - Crea/actualiza/borra clientes
    - Muestra clientes
    Restricción: no eliminar cliente con reservas ACTIVAS (presentes o futuras).
    """

    def __init__(
        self,
        customers: CustomerRepository,
        reservations: ReservationRepository,
    ) -> None:
        self._customers = customers
        self._reservations = reservations

    # ---------- CUSTOMERS ----------

    def create_customer(
        self,
        customer_id: str,
        full_name: str,
        email: str,
        phone: Optional[str] = None,
    ) -> Customer:
        if self._customers.get_by_id(customer_id) is not None:
            raise DuplicateIdError(f"Customer '{customer_id}' ya existe")
        customer = Customer(
            customer_id=customer_id,
            full_name=full_name,
            email=email,
            phone=phone,
        )
        self._customers.upsert(customer)
        return customer

    def get_customer(self, customer_id: str) -> Customer:
        c = self._customers.get_by_id(customer_id)
        if c is None:
            raise NotFoundError(f"Customer '{customer_id}' no existe")
        return c

    def list_customers(self) -> List[Customer]:
        return self._customers.list_all()

    def update_customer(
        self,
        customer_id: str,
        *,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Customer:
        c = self.get_customer(customer_id)
        updated = Customer(
            customer_id=c.customer_id,
            full_name=full_name if full_name is not None else c.full_name,
            email=email if email is not None else c.email,
            phone=phone if phone is not None else c.phone,
        )
        # Valida modelo
        Customer.from_dict(updated.to_dict())
        self._customers.upsert(updated)
        return updated

    def delete_customer(self, customer_id: str) -> None:
        # Confirma existencia
        _ = self.get_customer(customer_id)

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
            raise NotFoundError(
                f"Customer '{customer_id}' no existe (eliminado concurrentemente)"
            )


class ReservationService:
    """
    Capa delgada para consultas/operaciones de reservas.
    La creación/cancelación delega en HotelService para
    centralizar disponibilidad.
    """

    def __init__(
        self,
        reservations: ReservationRepository,
        hotel_service: HotelService,
    ) -> None:
        self._reservations = reservations
        self._hotel_service = hotel_service

    def get_reservation(self, reservation_id: str) -> Reservation:
        r = self._reservations.get_by_id(reservation_id)
        if r is None:
            raise NotFoundError(f"Reservation '{reservation_id}' no existe")
        return r

    def list_by_hotel(self, hotel_id: str) -> List[Reservation]:
        return self._reservations.list_by_hotel(hotel_id)

    def list_by_customer(self, customer_id: str) -> List[Reservation]:
        return self._reservations.list_by_customer(customer_id)

    # Atajos que delegan en HotelService
    def create(
        self,
        customer_id: str,
        hotel_id: str,
        check_in: date,
        check_out: date,
        *,
        reservation_id: Optional[str] = None,
        room_number: Optional[int] = None,
    ) -> Reservation:
        return self._hotel_service.reserve_room(
            customer_id=customer_id,
            hotel_id=hotel_id,
            check_in=check_in,
            check_out=check_out,
            reservation_id=reservation_id,
            room_number=room_number,
        )

    def cancel(self, reservation_id: str) -> Reservation:
        return self._hotel_service.cancel_reservation(reservation_id)
