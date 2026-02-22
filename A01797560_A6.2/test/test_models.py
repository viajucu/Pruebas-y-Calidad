"""
Pruebas unitarias para los modelos de dominio:
- Hotel
- Customer
- Reservation

Valida: creación correcta, validaciones (__post_init__), y
serialización/deserialización (to_dict / from_dict).
"""


from __future__ import annotations

import unittest
from datetime import date  # noqa: F401  (se usa en la prueba negativa)

from test.utils import make_reservation
from app.models import Customer, Hotel, Reservation


class TestModels(unittest.TestCase):
    """Suite de pruebas para modelos de dominio y sus validaciones."""

    def test_hotel_creacion_ok(self) -> None:
        """Crear Hotel válido y verificar campos básicos."""
        hobj = Hotel(hotel_id="H1", name="Hotel", city="CDMX", total_rooms=10)
        self.assertEqual(hobj.hotel_id, "H1")
        self.assertEqual(hobj.total_rooms, 10)

    def test_hotel_total_rooms_invalido(self) -> None:
        """Hotel total_rooms <= 0 debe fallar."""
        with self.assertRaises(ValueError):
            _ = Hotel(hotel_id="H2", name="X", city="CDMX", total_rooms=0)

    def test_hotel_from_to_dict(self) -> None:
        """Serializar y deserializar Hotel conservando campos."""
        hobj = Hotel(hotel_id="H3", name="Y", city="GDL", total_rooms=5)
        dct = hobj.to_dict()
        h2 = Hotel.from_dict(dct)
        self.assertEqual(h2.hotel_id, "H3")
        self.assertEqual(h2.total_rooms, 5)

    def test_customer_email_invalido(self) -> None:
        """Customer con email inválido debe fallar."""
        with self.assertRaises(ValueError):
            _ = Customer(customer_id="C1", full_name="Ana", email="no-email")

    def test_customer_from_to_dict(self) -> None:
        """Serializar y deserializar Customer conservando campos."""
        cobj = Customer(customer_id="C2", full_name="Luis", email="l@e.com")
        dct = cobj.to_dict()
        c2 = Customer.from_dict(dct)
        self.assertEqual(c2.customer_id, "C2")
        self.assertEqual(c2.full_name, "Luis")

    def test_reservation_creacion_ok(self) -> None:
        """Crear Reservation válida y verificar status por defecto."""
        robj = make_reservation("R1", "H1")
        self.assertEqual(robj.status, "ACTIVE")

    def test_reservation_fechas_invalidas(self) -> None:
        """Reservation con check_in >= check_out debe fallar."""
        check_in = date.today()
        check_out = check_in
        with self.assertRaises(ValueError):
            _ = Reservation(
                reservation_id="R2",
                hotel_id="H1",
                customer_id="C1",
                check_in=check_in,
                check_out=check_out,
            )

    def test_reservation_from_to_dict(self) -> None:
        """Serializar/deserializar Reservation con fechas ISO."""
        robj = make_reservation("R3", "H1")
        dct = robj.to_dict()
        r2 = Reservation.from_dict(dct)
        self.assertEqual(r2.reservation_id, "R3")
        self.assertEqual(r2.check_in, robj.check_in)
        self.assertEqual(r2.check_out, robj.check_out)


if __name__ == "__main__":
    unittest.main()
