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


class TestNegatives(unittest.TestCase):
    """Casos negativos para modelos, servicios y persistencia."""

    def setUp(self) -> None:
        # Repos aislados en tmp para cada prueba
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

        self.path_hotels = os.path.join(self.tmpdir, "hotels.json")
        self.path_customers = os.path.join(self.tmpdir, "customers.json")
        self.path_reservations = os.path.join(self.tmpdir, "reservations.json")

        self.hotels = HotelRepository(self.path_hotels)
        self.customers = CustomerRepository(self.path_customers)
        self.reservations = ReservationRepository(self.path_reservations)

        # Servicios “a mano” (sin helpers) para mayor claridad
        from app.services import HotelService, CustomerService, ReservationService
        self.hsvc = HotelService(self.hotels, self.customers, self.reservations)
        self.csvc = CustomerService(self.customers, self.reservations)
        self.rsvc = ReservationService(self.reservations, self.hsvc)

    # ---------- Modelos: negativos ----------

    def test_hotel_total_rooms_cero(self) -> None:
        with self.assertRaises(ValueError):
            _ = Hotel("H0", "X", "CDMX", 0)

    def test_customer_email_invalido(self) -> None:
        with self.assertRaises(ValueError):
            _ = Customer("C0", "Cliente", "no-email")

    def test_reservation_fechas_invalidas(self) -> None:
        today = date.today()
        with self.assertRaises(ValueError):
            _ = Reservation("R0", "H1", "C1", today, today)

    def test_hotel_rating_fuera_de_rango(self) -> None:
        with self.assertRaises(ValueError):
            _ = Hotel("H1", "Hotel", "CDMX", 5, rating=6.1)
        with self.assertRaises(ValueError):
            _ = Hotel("H2", "Hotel", "CDMX", 5, rating=-0.5)

    def test_reservation_room_number_invalido(self) -> None:
        today = date.today()
        with self.assertRaises(ValueError):
            _ = Reservation("R1", "H1", "C1", today, today + timedelta(days=1),
                           room_number=0)

    def test_reservation_from_dict_fecha_iso_invalida(self) -> None:
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
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 2)
        with self.assertRaises(DuplicateIdError):
            self.hsvc.create_hotel("H1", "Otro", "CDMX", 3)

    def test_reserve_sin_disponibilidad(self) -> None:
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        self.csvc.create_customer("C1", "Ana", "ana@example.com")
        self.csvc.create_customer("C2", "Luis", "luis@example.com")

        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)

        _ = self.hsvc.reserve_room("C1", "H1", ci, co)
        with self.assertRaises(BusinessRuleError):
            _ = self.hsvc.reserve_room("C2", "H1", ci, co)

    def test_cancel_reservation_dos_veces_conflict(self) -> None:
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        self.csvc.create_customer("C1", "Ana", "ana@example.com")

        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)

        res = self.hsvc.reserve_room("C1", "H1", ci, co)
        _ = self.hsvc.cancel_reservation(res.reservation_id)
        with self.assertRaises(ConflictError):
            _ = self.hsvc.cancel_reservation(res.reservation_id)

    def test_update_hotel_bajar_de_pico_ocupacion(self) -> None:
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 2)
        self.csvc.create_customer("C1", "Ana", "ana@example.com")
        self.csvc.create_customer("C2", "Luis", "luis@example.com")

        ci = date.today() + timedelta(days=3)
        co = ci + timedelta(days=2)
        _ = self.hsvc.reserve_room("C1", "H1", ci, co)
        _ = self.hsvc.reserve_room("C2", "H1", ci, co)

        with self.assertRaises(BusinessRuleError):
            _ = self.hsvc.update_hotel("H1", total_rooms=1)

    def test_delete_hotel_con_reservas_activas(self) -> None:
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        self.csvc.create_customer("C1", "Ana", "ana@example.com")
        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)
        _ = self.hsvc.reserve_room("C1", "H1", ci, co)
        with self.assertRaises(BusinessRuleError):
            self.hsvc.delete_hotel("H1")

    def test_delete_customer_con_reservas_activas(self) -> None:
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        self.csvc.create_customer("C1", "Ana", "ana@example.com")
        ci = date.today() + timedelta(days=2)
        co = ci + timedelta(days=1)
        _ = self.hsvc.reserve_room("C1", "H1", ci, co)
        with self.assertRaises(BusinessRuleError):
            self.csvc.delete_customer("C1")

    def test_reserva_fechas_invalidas_en_service(self) -> None:
        self.hsvc.create_hotel("H1", "Hotel", "CDMX", 1)
        self.csvc.create_customer("C1", "Ana", "ana@example.com")
        ci = date.today()
        co = ci  # inválido
        with self.assertRaises(ValidationError):
            _ = self.hsvc.reserve_room("C1", "H1", ci, co)

    def test_get_not_found_en_services(self) -> None:
        with self.assertRaises(NotFoundError):
            _ = self.hsvc.get_hotel("HNO")
        with self.assertRaises(NotFoundError):
            _ = self.csvc.get_customer("CNO")
        from app.services import ReservationService
        rsvc = ReservationService(self.reservations, self.hsvc)
        with self.assertRaises(NotFoundError):
            _ = rsvc.get_reservation("RNO")

    # ---------- Persistencia: negativos ----------

    def test_persistence_error_en_save(self) -> None:
        hobj = Hotel("HERR", "Hotel", "CDMX", 1)
        with patch("builtins.open", side_effect=OSError("denegado")):
            with self.assertRaises(PersistenceError):
                self.hotels.upsert(hobj)


if __name__ == "__main__":
    unittest.main()
