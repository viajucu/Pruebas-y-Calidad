"""
test_negatives.py

Casos NEGATIVOS:
- Modelos: validaciones (rating, room_number, fechas ISO inválidas).
- Servicios: duplicados, sin disponibilidad, conflictos, no-found, reglas.
- Persistencia: error al guardar.

Estos tests no dependen de data/ real; usan temp directories aislados.

"""


from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from typing import NamedTuple
from unittest.mock import patch

from app.errors import (
    BusinessRuleError,
    ConflictError,
    DuplicateIdError,
    NotFoundError,
    PersistenceError,
    ValidationError,
)
from app.models import Customer, Hotel, Reservation
from app.repository import (
    CustomerRepository,
    HotelRepository,
    ReservationRepository,
)
from app.services import CustomerService, HotelService, ReservationService


class Ctx(NamedTuple):
    """Contenedor de repos y servicios para reducir atributos en self."""
    hotels: HotelRepository
    customers: CustomerRepository
    reservations: ReservationRepository
    hsvc: HotelService
    csvc: CustomerService
    rsvc: ReservationService


class TestNegatives(unittest.TestCase):
    """Casos negativos para modelos, servicios y persistencia."""

    def setUp(self) -> None:
        """Crea repos aislados en tmp y construye servicios (sin data real)."""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))

        path_hotels = os.path.join(tmpdir, "hotels.json")
        path_customers = os.path.join(tmpdir, "customers.json")
        path_reservations = os.path.join(tmpdir, "reservations.json")

        hotels = HotelRepository(path_hotels)
        customers = CustomerRepository(path_customers)
        reservations = ReservationRepository(path_reservations)

        hsvc = HotelService(hotels, customers, reservations)
        csvc = CustomerService(customers, reservations)
        rsvc = ReservationService(reservations, hsvc)

        # Guardamos todo en un único atributo (evita R0902).
        self.ctx = Ctx(  # pylint: disable=attribute-defined-outside-init
            hotels=hotels,
            customers=customers,
            reservations=reservations,
            hsvc=hsvc,
            csvc=csvc,
            rsvc=rsvc,
        )
        self.tmpdir = tmpdir  # pylint: disable=attribute-defined-outside-init

    # ---------- Modelos: negativos ----------

    def test_hotel_total_rooms_cero(self) -> None:
        """Hotel con total_rooms <= 0 debe fallar."""
        with self.assertRaises(ValueError):
            _ = Hotel("H0", "X", "CDMX", 0)

    def test_customer_email_invalido(self) -> None:
        """Customer con email inválido debe fallar."""
        with self.assertRaises(ValueError):
            _ = Customer("C0", "Cliente", "no-email")

    def test_reservation_fechas_invalidas(self) -> None:
        """Reservation con check_in >= check_out debe fallar."""
        today = date.today()
        with self.assertRaises(ValueError):
            _ = Reservation("R0", "H1", "C1", today, today)

    def test_hotel_rating_fuera_de_rango(self) -> None:
        """Hotel con rating fuera de [0.0, 5.0] debe fallar."""
        with self.assertRaises(ValueError):
            _ = Hotel("H1", "Hotel", "CDMX", 5, rating=6.1)
        with self.assertRaises(ValueError):
            _ = Hotel("H2", "Hotel", "CDMX", 5, rating=-0.5)

    def test_reservation_room_number_invalido(self) -> None:
        """Reservation con room_number <= 0 debe fallar."""
        today = date.today()
        with self.assertRaises(ValueError):
            _ = Reservation(
                "R1",
                "H1",
                "C1",
                today,
                today + timedelta(days=1),
                room_number=0,
            )

    def test_reservation_from_dict_fecha_iso_invalida(self) -> None:
        """Reservation.from_dict con fechas ISO inválidas debe fallar."""
        bad = {
            "reservation_id": "R2",
            "hotel_id": "H1",
            "customer_id": "C1",
            "check_in": "2025-02-30",  # fecha inválida
            "check_out": "2025-03-02",
        }
        with self.assertRaises(ValueError):
            _ = Reservation.from_dict(bad)

    # ---------- Servicios: negativos ----------

    def test_create_hotel_duplicado(self) -> None:
        """Crear hotel duplicado debe lanzar DuplicateIdError."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 2)
        with self.assertRaises(DuplicateIdError):
            ctx.hsvc.create_hotel("H1", "Otro", "CDMX", 3)

    def test_reserve_sin_disponibilidad(self) -> None:
        """Reservar sin disponibilidad debe lanzar BusinessRuleError."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        ctx.csvc.create_customer("C1", "Ana", "ana@example.com")
        ctx.csvc.create_customer("C2", "Luis", "luis@example.com")

        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)

        _ = ctx.hsvc.reserve_room("C1", "H1", ci, co)
        with self.assertRaises(BusinessRuleError):
            _ = ctx.hsvc.reserve_room("C2", "H1", ci, co)

    def test_cancel_reservation_dos_veces_conflict(self) -> None:
        """Cancelar dos veces debe lanzar ConflictError en el segundo intento."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        ctx.csvc.create_customer("C1", "Ana", "ana@example.com")

        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)

        res = ctx.hsvc.reserve_room("C1", "H1", ci, co)
        _ = ctx.hsvc.cancel_reservation(res.reservation_id)
        with self.assertRaises(ConflictError):
            _ = ctx.hsvc.cancel_reservation(res.reservation_id)

    def test_update_hotel_bajar_de_pico_ocupacion(self) -> None:
        """Reducir total_rooms por debajo del pico debe fallar."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 2)
        ctx.csvc.create_customer("C1", "Ana", "ana@example.com")
        ctx.csvc.create_customer("C2", "Luis", "luis@example.com")

        ci = date.today() + timedelta(days=3)
        co = ci + timedelta(days=2)
        _ = ctx.hsvc.reserve_room("C1", "H1", ci, co)
        _ = ctx.hsvc.reserve_room("C2", "H1", ci, co)

        with self.assertRaises(BusinessRuleError):
            _ = ctx.hsvc.update_hotel("H1", total_rooms=1)

    def test_delete_hotel_con_reservas_activas(self) -> None:
        """Eliminar hotel con reservas activas debe fallar."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        ctx.csvc.create_customer("C1", "Ana", "ana@example.com")

        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)
        _ = ctx.hsvc.reserve_room("C1", "H1", ci, co)

        with self.assertRaises(BusinessRuleError):
            ctx.hsvc.delete_hotel("H1")

    def test_delete_customer_con_reservas_activas(self) -> None:
        """Eliminar customer con reservas activas debe fallar."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        ctx.csvc.create_customer("C1", "Ana", "ana@example.com")

        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)
        _ = ctx.hsvc.reserve_room("C1", "H1", ci, co)

        with self.assertRaises(BusinessRuleError):
            ctx.csvc.delete_customer("C1")

    def test_reserva_fechas_invalidas_en_service(self) -> None:
        """Reservar con check_in >= check_out debe lanzar ValidationError."""
        ctx = self.ctx
        ctx.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        ctx.csvc.create_customer("C1", "Ana", "ana@example.com")

        ci = date.today()
        co = ci  # inválido

        with self.assertRaises(ValidationError):
            _ = ctx.hsvc.reserve_room("C1", "H1", ci, co)

    def test_get_not_found_en_services(self) -> None:
        """Consultas not-found de hotel/cliente/reserva deben fallar."""
        ctx = self.ctx
        with self.assertRaises(NotFoundError):
            _ = ctx.hsvc.get_hotel("HNO")
        with self.assertRaises(NotFoundError):
            _ = ctx.csvc.get_customer("CNO")
        with self.assertRaises(NotFoundError):
            _ = ctx.rsvc.get_reservation("RNO")

    # ---------- Persistencia: negativos ----------

    def test_persistence_error_en_save(self) -> None:
        """Error de E/S al guardar debe lanzar PersistenceError."""
        ctx = self.ctx
        hobj = Hotel("HERR", "Hotel", "CDMX", 1)
        with patch("builtins.open", side_effect=OSError("denegado")):
            with self.assertRaises(PersistenceError):
                ctx.hotels.upsert(hobj)


if __name__ == "__main__":
    unittest.main()
