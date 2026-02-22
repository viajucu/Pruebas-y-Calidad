"""
Pruebas para repository.py

Valida:
- Lectura tolerante a errores (archivo inexistente, JSON corrupto,
  raíz no lista).
- Omisión de registros inválidos.
- CRUD básico para hoteles, clientes y reservaciones.
- Manejo de error al guardar (PersistenceError) para cobertura.
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from unittest.mock import patch

from app.errors import PersistenceError
from app.models import Customer, Hotel, Reservation
from app.repository import (
    CustomerRepository,
    HotelRepository,
    JsonStore,
    ReservationRepository,
)


class TestRepository(unittest.TestCase):
    def setUp(self) -> None:
        # Carpeta temporal por test para no tocar archivos reales.
        self.tmpdir = tempfile.TemporaryDirectory()
        base = self.tmpdir.name

        self.path_hotels = os.path.join(base, "hotels.json")
        self.path_customers = os.path.join(base, "customers.json")
        self.path_reservations = os.path.join(base, "reservations.json")

        self.hotels = HotelRepository(self.path_hotels)
        self.customers = CustomerRepository(self.path_customers)
        self.reservations = ReservationRepository(self.path_reservations)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    # ---------- JsonStore: tolerancia a errores ----------

    def test_load_list_archivo_inexistente_regresa_vacio(self) -> None:
        path = os.path.join(self.tmpdir.name, "no_existe.json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            data = JsonStore.load_list(path)
        out = buf.getvalue()

        self.assertEqual(data, [])
        self.assertIn("Archivo no encontrado", out)

    def test_load_list_json_corrupto_regresa_vacio(self) -> None:
        corrupt_path = os.path.join(self.tmpdir.name, "corrupt.json")
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("{ esto NO es JSON válido ")

        buf = io.StringIO()
        with redirect_stdout(buf):
            data = JsonStore.load_list(corrupt_path)
        out = buf.getvalue()

        self.assertEqual(data, [])
        self.assertIn("JSON corrupto", out)

    def test_load_list_no_lista_regresa_vacio(self) -> None:
        p = os.path.join(self.tmpdir.name, "root_not_list.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"not": "a list"}, f)

        buf = io.StringIO()
        with redirect_stdout(buf):
            data = JsonStore.load_list(p)
        out = buf.getvalue()

        self.assertEqual(data, [])
        self.assertIn("Estructura inválida", out)

    # ---------- Repos: omitir registros inválidos ----------

    def test_list_all_omite_registros_invalidos(self) -> None:
        # 1 válido + 2 inválidos (total_rooms <= 0 y falta 'name')
        raw = [
            {"hotel_id": "H1", "name": "Bueno", "city": "CDMX",
             "total_rooms": 10},
            {"hotel_id": "H2", "name": "Malo", "city": "CDMX",
             "total_rooms": 0},
            {"hotel_id": "H3", "city": "CDMX", "total_rooms": 5},
        ]
        with open(self.path_hotels, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        buf = io.StringIO()
        with redirect_stdout(buf):
            items = self.hotels.list_all()
        out = buf.getvalue()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].hotel_id, "H1")
        self.assertIn("Registro inválido omitido", out)

    # ---------- CRUD básico ----------

    def test_crud_basico_hotels(self) -> None:
        h = Hotel(hotel_id="H1", name="Hotel", city="CDMX", total_rooms=10)
        self.hotels.upsert(h)

        found = self.hotels.get_by_id("H1")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Hotel")

        h2 = Hotel(
            hotel_id="H1",
            name="Hotel Renombrado",
            city="CDMX",
            total_rooms=12,
        )
        self.hotels.upsert(h2)
        found2 = self.hotels.get_by_id("H1")
        self.assertEqual(found2.name, "Hotel Renombrado")
        self.assertEqual(found2.total_rooms, 12)

        self.assertTrue(self.hotels.delete("H1"))
        self.assertIsNone(self.hotels.get_by_id("H1"))
        self.assertFalse(self.hotels.delete("H999"))

    def test_crud_basico_customers(self) -> None:
        c = Customer(customer_id="C1", full_name="Ana", email="ana@example.com")
        self.customers.upsert(c)

        found = self.customers.get_by_id("C1")
        self.assertIsNotNone(found)
        self.assertEqual(found.full_name, "Ana")

        c2 = Customer(
            customer_id="C1",
            full_name="Ana G.",
            email="ana@example.com",
        )
        self.customers.upsert(c2)
        self.assertEqual(self.customers.get_by_id("C1").full_name, "Ana G.")

        self.assertTrue(self.customers.delete("C1"))
        self.assertIsNone(self.customers.get_by_id("C1"))
        self.assertFalse(self.customers.delete("C999"))

    def test_crud_basico_reservations(self) -> None:
        h = Hotel(hotel_id="H1", name="Hotel", city="CDMX", total_rooms=10)
        c = Customer(customer_id="C1", full_name="Ana", email="ana@example.com")
        self.hotels.upsert(h)
        self.customers.upsert(c)

        check_in = date.today()
        check_out = check_in + timedelta(days=1)

        r = Reservation(
            reservation_id="R1",
            hotel_id="H1",
            customer_id="C1",
            check_in=check_in,
            check_out=check_out,
        )
        self.reservations.upsert(r)

        found = self.reservations.get_by_id("R1")
        self.assertIsNotNone(found)
        self.assertEqual(found.customer_id, "C1")

        self.assertTrue(self.reservations.delete("R1"))
        self.assertIsNone(self.reservations.get_by_id("R1"))
        self.assertFalse(self.reservations.delete("R999"))

    # ---------- Búsquedas auxiliares en ReservationRepository ----------

    def test_list_by_hotel_y_customer(self) -> None:
        h1 = Hotel(hotel_id="H1", name="H1", city="CDMX", total_rooms=5)
        h2 = Hotel(hotel_id="H2", name="H2", city="GDL", total_rooms=5)
        c1 = Customer(customer_id="C1", full_name="Ana",
                      email="ana@example.com")
        c2 = Customer(customer_id="C2", full_name="Luis",
                      email="luis@example.com")
        self.hotels.upsert(h1)
        self.hotels.upsert(h2)
        self.customers.upsert(c1)
        self.customers.upsert(c2)

        check_in = date.today() + timedelta(days=3)
        check_out = check_in + timedelta(days=2)

        r1 = Reservation("R1", "H1", "C1", check_in, check_out)
        r2 = Reservation("R2", "H1", "C2", check_in, check_out)
        r3 = Reservation("R3", "H2", "C1", check_in, check_out)
        self.reservations.upsert(r1)
        self.reservations.upsert(r2)
        self.reservations.upsert(r3)

        by_h1 = self.reservations.list_by_hotel("H1")
        by_c1 = self.reservations.list_by_customer("C1")

        self.assertEqual({r.reservation_id for r in by_h1}, {"R1", "R2"})
        self.assertEqual({r.reservation_id for r in by_c1}, {"R1", "R3"})

    # ---------- Cobertura extra: error de persistencia al guardar ----------

    def test_save_list_error_lanza_persistence_error(self) -> None:
        # Parchamos open() para que falle al escribir en save_list()
        h = Hotel(hotel_id="HERR", name="H", city="CDMX", total_rooms=1)
        with patch("builtins.open", side_effect=OSError("permiso denegado")):
            with self.assertRaises(PersistenceError):
                self.hotels.upsert(h)


if __name__ == "__main__":
    unittest.main()
