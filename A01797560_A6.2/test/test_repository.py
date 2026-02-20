"""Pruebas de persistencia en repository.py.

Valida lectura tolerante a errores (archivo inexistente, JSON corrupto,
registros inválidos omitidos) y operaciones CRUD básicas con JSON.
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta

from app.models import Hotel, Customer, Reservation
from app.repository import (
    JsonStore,
    HotelRepository,
    CustomerRepository,
    ReservationRepository,
)


class TestRepository(unittest.TestCase):
    def setUp(self):
        # Carpeta temporal por test para no tocar archivos reales.
        self.tmpdir = tempfile.TemporaryDirectory()
        base = self.tmpdir.name

        self.path_hotels = os.path.join(base, "hotels.json")
        self.path_customers = os.path.join(base, "customers.json")
        self.path_reservations = os.path.join(base, "reservations.json")

        self.hotels = HotelRepository(self.path_hotels)
        self.customers = CustomerRepository(self.path_customers)
        self.reservations = ReservationRepository(self.path_reservations)

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------- JsonStore: tolerancia a errores ----------

    def test_load_list_archivo_inexistente_regresa_vacio(self):
        # Dado un archivo inexistente
        path = os.path.join(self.tmpdir.name, "no_existe.json")
        # Cuando lo cargo
        buf = io.StringIO()
        with redirect_stdout(buf):
            data = JsonStore.load_list(path)
        out = buf.getvalue()
        # Entonces no truena, imprime WARN y regresa lista vacía
        self.assertEqual(data, [])
        self.assertIn("Archivo no encontrado", out)

    def test_load_list_json_corrupto_regresa_vacio(self):
        # Dado un archivo con JSON mal formado
        corrupt_path = os.path.join(self.tmpdir.name, "corrupt.json")
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("{ esto NO es JSON válido ")

        # Cuando lo cargo
        buf = io.StringIO()
        with redirect_stdout(buf):
            data = JsonStore.load_list(corrupt_path)
        out = buf.getvalue()

        # Entonces imprime ERROR y devuelve lista vacía
        self.assertEqual(data, [])
        self.assertIn("JSON corrupto", out)

    def test_load_list_no_lista_regresa_vacio(self):
        # Dado un JSON cuya raíz NO es lista (p. ej., dict)
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

    def test_list_all_omite_registros_invalidos(self):
        # Dado un archivo con 1 hotel válido + 2 inválidos
        # - inválido1: total_rooms <= 0
        # - inválido2: falta 'name'
        raw = [
            {"hotel_id": "H1", "name": "Bueno", "city": "CDMX", "total_rooms": 10},
            {"hotel_id": "H2", "name": "Malo", "city": "CDMX", "total_rooms": 0},
            {"hotel_id": "H3", "city": "CDMX", "total_rooms": 5},
        ]
        with open(self.path_hotels, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        buf = io.StringIO()
        with redirect_stdout(buf):
            items = self.hotels.list_all()
        out = buf.getvalue()

        # Entonces sólo deja el válido (H1) y imprime WARN por los otros
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].hotel_id, "H1")
        self.assertIn("Registro inválido omitido", out)

    # ---------- CRUD básico ----------

    def test_crud_basico_hotels(self):
        # Create/Upsert
        h = Hotel(hotel_id="H1", name="Hotel", city="CDMX", total_rooms=10)
        self.hotels.upsert(h)

        # Read
        found = self.hotels.get_by_id("H1")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Hotel")

        # Update via upsert
        h2 = Hotel(hotel_id="H1", name="Hotel Renombrado", city="CDMX", total_rooms=12)
        self.hotels.upsert(h2)
        found2 = self.hotels.get_by_id("H1")
        self.assertEqual(found2.name, "Hotel Renombrado")
        self.assertEqual(found2.total_rooms, 12)

        # Delete
        deleted = self.hotels.delete("H1")
        self.assertTrue(deleted)
        self.assertIsNone(self.hotels.get_by_id("H1"))

        # Delete inexistente => False
        self.assertFalse(self.hotels.delete("H999"))

    def test_crud_basico_customers(self):
        c = Customer(customer_id="C1", full_name="Ana", email="ana@example.com")
        self.customers.upsert(c)

        found = self.customers.get_by_id("C1")
        self.assertIsNotNone(found)
        self.assertEqual(found.full_name, "Ana")

        c2 = Customer(customer_id="C1", full_name="Ana G.", email="ana@example.com")
        self.customers.upsert(c2)
        self.assertEqual(self.customers.get_by_id("C1").full_name, "Ana G.")

        self.assertTrue(self.customers.delete("C1"))
        self.assertIsNone(self.customers.get_by_id("C1"))
        self.assertFalse(self.customers.delete("C999"))

    def test_crud_basico_reservations(self):
        # Prepara dos entidades base
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

    def test_list_by_hotel_y_customer(self):
        # Prepara base
        h1 = Hotel(hotel_id="H1", name="H1", city="CDMX", total_rooms=5)
        h2 = Hotel(hotel_id="H2", name="H2", city="GDL", total_rooms=5)
        c1 = Customer(customer_id="C1", full_name="Ana", email="ana@example.com")
        c2 = Customer(customer_id="C2", full_name="Luis", email="luis@example.com")
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


if __name__ == "__main__":
    unittest.main()
