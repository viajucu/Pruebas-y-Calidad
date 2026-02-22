"""
Pruebas para services.py

Cubre:
- Creación, consulta, listado y actualización de hoteles/clientes.
- Reserva con verificación de disponibilidad por solapamientos.
- Cancelación idempotente.
- Validaciones y not-found en servicios.
"""

import os
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
    def setUp(self) -> None:
        # Carpeta temporal por test
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name

        self.hotels = HotelRepository(os.path.join(base, "hotels.json"))
        self.customers = CustomerRepository(os.path.join(base, "customers.json"))
        self.reservations = ReservationRepository(
            os.path.join(base, "reservations.json")
        )

        self.hotel_service = HotelService(
            self.hotels, self.customers, self.reservations
        )
        self.customer_service = CustomerService(
            self.customers, self.reservations
        )
        self.reservation_service = ReservationService(
            self.reservations, self.hotel_service
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

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # ---------- Hotels ----------

    def test_create_hotel_ok_y_duplicado(self) -> None:
        created = self.hotel_service.create_hotel(
            "H2", "Hotel Norte", "GDL", 3
        )
        self.assertEqual(created.hotel_id, "H2")

        with self.assertRaises(DuplicateIdError):
            self.hotel_service.create_hotel(
                "H2", "Hotel Norte 2", "GDL", 5
            )

    def test_get_y_list_hotels(self) -> None:
        hotel = self.hotel_service.get_hotel("H1")
        self.assertEqual(hotel.name, "Hotel Centro")

        all_hotels = self.hotel_service.list_hotels()
        self.assertTrue(any(x.hotel_id == "H1" for x in all_hotels))

    def test_update_hotel_no_bajar_de_ocupacion_actual(self) -> None:
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        self.customer_service.create_customer(
            "C2", "Luis", "luis@example.com"
        )
        self.hotel_service.reserve_room(
            "C2", "H1", self.check_in, self.check_out
        )

        with self.assertRaises(BusinessRuleError):
            self.hotel_service.update_hotel("H1", total_rooms=1)

        updated = self.hotel_service.update_hotel("H1", total_rooms=3)
        self.assertEqual(updated.total_rooms, 3)

    def test_delete_hotel_con_reservas_activas(self) -> None:
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        with self.assertRaises(BusinessRuleError):
            self.hotel_service.delete_hotel("H1")

    def test_delete_hotel_ok_sin_reservas(self) -> None:
        self.hotel_service.create_hotel("HX", "Temporal", "CDMX", 1)
        self.hotel_service.delete_hotel("HX")
        with self.assertRaises(NotFoundError):
            self.hotel_service.get_hotel("HX")

    # ---------- Reservations ----------

    def test_reserve_room_disponible(self) -> None:
        res = self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        self.assertEqual(res.status, "ACTIVE")

    def test_reserve_room_sin_disponibilidad(self) -> None:
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        self.customer_service.create_customer(
            "C2", "Luis", "luis@example.com"
        )
        self.hotel_service.reserve_room(
            "C2", "H1", self.check_in, self.check_out
        )

        self.customer_service.create_customer(
            "C3", "Eva", "eva@example.com"
        )
        with self.assertRaises(BusinessRuleError):
            self.hotel_service.reserve_room(
                "C3", "H1", self.check_in, self.check_out
            )

    def test_cancel_reservation_y_idempotencia(self) -> None:
        res = self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        canceled = self.hotel_service.cancel_reservation(res.reservation_id)
        self.assertEqual(canceled.status, "CANCELED")

        with self.assertRaises(ConflictError):
            self.hotel_service.cancel_reservation(res.reservation_id)

    def test_reservation_service_atajos(self) -> None:
        res = self.reservation_service.create(
            "C1", "H1", self.check_in, self.check_out
        )
        self.assertEqual(res.hotel_id, "H1")

        res_got = self.reservation_service.get_reservation(
            res.reservation_id
        )
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
        # check_in >= check_out ⇒ ValidationError
        with self.assertRaises(ValidationError):
            self.hotel_service.reserve_room(
                "C1", "H1", self.check_out, self.check_in
            )

    def test_get_reservation_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.reservation_service.get_reservation("RNO")

    # ---------- Customers ----------

    def test_create_y_get_customer(self) -> None:
        created = self.customer_service.create_customer(
            "C9", "Nuevo", "nuevo@example.com"
        )
        self.assertEqual(created.customer_id, "C9")

        got = self.customer_service.get_customer("C9")
        self.assertEqual(got.full_name, "Nuevo")

    def test_create_customer_duplicado(self) -> None:
        with self.assertRaises(DuplicateIdError):
            self.customer_service.create_customer(
                "C1", "Otro", "ana@example.com"
            )

    def test_update_customer(self) -> None:
        updated = self.customer_service.update_customer(
            "C1", full_name="Ana G."
        )
        self.assertEqual(updated.full_name, "Ana G.")

    def test_delete_customer_con_reservas_activas(self) -> None:
        self.hotel_service.reserve_room(
            "C1", "H1", self.check_in, self.check_out
        )
        with self.assertRaises(BusinessRuleError):
            self.customer_service.delete_customer("C1")

    def test_delete_customer_ok(self) -> None:
        self.customer_service.create_customer(
            "C2", "Luis", "luis@example.com"
        )
        self.customer_service.delete_customer("C2")
        with self.assertRaises(NotFoundError):
            self.customer_service.get_customer("C2")

    def test_gets_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.hotel_service.get_hotel("HNO")
        with self.assertRaises(NotFoundError):
            self.customer_service.get_customer("CNO")
        with self.assertRaises(NotFoundError):
            self.reservation_service.get_reservation("RNO")


if __name__ == "__main__":
    unittest.main()
