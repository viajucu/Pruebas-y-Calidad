"""
Pruebas para services.py

Cubre:
- Creación, consulta, listado y actualización de hoteles/clientes.
- Reserva con verificación de disponibilidad por solapamientos.
- Cancelación idempotente.
- Validaciones y not-found en servicios.
"""


from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

from app.errors import (
    BusinessRuleError,
    ConflictError,
    DuplicateIdError,
    NotFoundError,
    ValidationError,
)
from app.repository import (
    CustomerRepository,
    HotelRepository,
    ReservationRepository,
)
from app.services import (
    CustomerService,
    HotelService,
    ReservationService,
)


class TestServices(unittest.TestCase):
    """Suite de pruebas de la capa de servicios."""

    def setUp(self) -> None:
        """Crea repos/servicios sobre un directorio temporal por prueba."""
        # Evitamos R1732 usando mkdtemp + cleanup explícito
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        base = self.tmpdir

        hotels = HotelRepository(os.path.join(base, "hotels.json"))
        customers = CustomerRepository(os.path.join(base, "customers.json"))
        reservations = ReservationRepository(
            os.path.join(base, "reservations.json")
        )

        self.hotel_service = HotelService(hotels, customers, reservations)
        self.customer_service = CustomerService(customers, reservations)
        self.reservation_service = ReservationService(
            reservations, self.hotel_service
        )

        # Datos base comunes
        self.hotel_service.create_hotel(
            "H1", "Hotel Centro", "CDMX", total_rooms=2
        )
        self.customer_service.create_customer(
            "C1", "Ana García", "ana@example.com"
        )

        self.check_in = date.today() + timedelta(days=3)
        self.check_out = self.check_in + timedelta(days=2)

    # ---------- Hotels ----------

    def test_create_hotel_ok_y_duplicado(self) -> None:
        """Crear hotel y validar duplicado por ID."""
        created = self.hotel_service.create_hotel(
            "H2", "Hotel Norte", "GDL", 3
        )
        self.assertEqual(created.hotel_id, "H2")

        with self.assertRaises(DuplicateIdError):
            self.hotel_service.create_hotel("H2", "Hotel Norte 2", "GDL", 5)

    def test_get_y_list_hotels(self) -> None:
        """Obtener un hotel y listar hoteles."""
        hotel = self.hotel_service.get_hotel("H1")
        self.assertEqual(hotel.name, "Hotel Centro")

        all_hotels = self.hotel_service.list_hotels()
        self.assertTrue(any(x.hotel_id == "H1" for x in all_hotels))

    def test_update_hotel_no_bajar_de_ocupacion_actual(self) -> None:
        """No permitir bajar total_rooms por debajo del pico de ocupación."""
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        self.customer_service.create_customer("C2", "Luis", "luis@example.com")
        self.hotel_service.reserve_room(
            "C2", "H1", self.check_in, self.check_out
        )

        with self.assertRaises(BusinessRuleError):
            self.hotel_service.update_hotel("H1", total_rooms=1)

        updated = self.hotel_service.update_hotel("H1", total_rooms=3)
        self.assertEqual(updated.total_rooms, 3)

    def test_delete_hotel_con_reservas_activas(self) -> None:
        """No permitir eliminar hotel con reservas activas."""
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        with self.assertRaises(BusinessRuleError):
            self.hotel_service.delete_hotel("H1")

    def test_delete_hotel_ok_sin_reservas(self) -> None:
        """Permitir eliminar hotel sin reservas activas."""
        self.hotel_service.create_hotel("HX", "Temporal", "CDMX", 1)
        self.hotel_service.delete_hotel("HX")
        with self.assertRaises(NotFoundError):
            self.hotel_service.get_hotel("HX")

    # ---------- Reservations ----------

    def test_reserve_room_disponible(self) -> None:
        """Reservar cuando hay disponibilidad."""
        res = self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        self.assertEqual(res.status, "ACTIVE")

    def test_reserve_room_sin_disponibilidad(self) -> None:
        """Detectar sin disponibilidad por solapamiento."""
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        self.customer_service.create_customer("C2", "Luis", "luis@example.com")
        self.hotel_service.reserve_room(
            "C2", "H1", self.check_in, self.check_out
        )

        self.customer_service.create_customer("C3", "Eva", "eva@example.com")
        with self.assertRaises(BusinessRuleError):
            self.hotel_service.reserve_room(
                "C3", "H1", self.check_in, self.check_out
            )

    def test_cancel_reservation_y_idempotencia(self) -> None:
        """Cancelar y segunda cancelación debe fallar."""
        res = self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        canceled = self.hotel_service.cancel_reservation(res.reservation_id)
        self.assertEqual(canceled.status, "CANCELED")

        with self.assertRaises(ConflictError):
            self.hotel_service.cancel_reservation(res.reservation_id)

    def test_reservation_service_atajos(self) -> None:
        """Atajos de ReservationService: create/get/list/cancel."""
        res = self.reservation_service.create(
            "C1", "H1", self.check_in, self.check_out
        )
        self.assertEqual(res.hotel_id, "H1")

        res_got = self.reservation_service.get_reservation(res.reservation_id)
        self.assertEqual(res_got.reservation_id, res.reservation_id)

        listed_h = self.reservation_service.list_by_hotel("H1")
        self.assertTrue(
            any(x.reservation_id == res.reservation_id for x in listed_h)
        )

        listed_c = self.reservation_service.list_by_customer("C1")
        self.assertTrue(
            any(x.reservation_id == res.reservation_id for x in listed_c)
        )

        canceled = self.reservation_service.cancel(res.reservation_id)
        self.assertEqual(canceled.status, "CANCELED")

    def test_reserva_con_fechas_invalidas(self) -> None:
        """Validación de fechas (check_in >= check_out)."""
        with self.assertRaises(ValidationError):
            self.hotel_service.reserve_room(
                "C1", "H1", self.check_out, self.check_in
            )

    def test_get_reservation_not_found(self) -> None:
        """NotFound al consultar una reserva inexistente."""
        with self.assertRaises(NotFoundError):
            self.reservation_service.get_reservation("RNO")


if __name__ == "__main__":
    unittest.main()
