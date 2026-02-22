"""
Pruebas para models.py

Cubre validaciones de dominio:
- Hotel.total_rooms > 0
- Email de Customer
- check_in < check_out en Reservation
- Roundtrip de serialización a dict/JSON
"""

import unittest
from datetime import date

from app.models import Customer, Hotel, Reservation


class TestModels(unittest.TestCase):
    def test_hotel_total_rooms_debe_ser_positivo(self) -> None:
        with self.assertRaises(ValueError):
            Hotel(hotel_id="H1", name="X", city="CDMX", total_rooms=0)

    def test_customer_email_invalido(self) -> None:
        with self.assertRaises(ValueError):
            Customer(customer_id="C1", full_name="Ana", email="correo_malo")

    def test_reservation_fechas_invalidas(self) -> None:
        with self.assertRaises(ValueError):
            Reservation(
                reservation_id="R1",
                hotel_id="H1",
                customer_id="C1",
                check_in=date(2026, 5, 10),
                check_out=date(2026, 5, 9),
            )

    def test_serializacion_roundtrip(self) -> None:
        h = Hotel(hotel_id="H1", name="Hotel", city="CDMX", total_rooms=10)
        c = Customer(customer_id="C1", full_name="Ana",
                     email="ana@example.com")
        r = Reservation(
            reservation_id="R1",
            hotel_id=h.hotel_id,
            customer_id=c.customer_id,
            check_in=date(2026, 5, 10),
            check_out=date(2026, 5, 12),
        )

        self.assertEqual(Hotel.from_dict(h.to_dict()).hotel_id, "H1")
        self.assertEqual(Customer.from_dict(c.to_dict()).customer_id, "C1")
        self.assertEqual(
            Reservation.from_dict(r.to_dict()).reservation_id, "R1"
        )


if __name__ == "__main__":
    unittest.main()
