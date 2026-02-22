"""
seed_data.py

Script utilitario para generar datos iniciales en formato JSON dentro del
directorio 'data/'. Crea hoteles, clientes y reservas válidas utilizando
los servicios y repositorios definidos en el proyecto.

Su propósito es:
- Verificar la ejecución correcta del sistema fuera de las pruebas unitarias.
- Poblar los archivos JSON con datos reales para demostración o pruebas manuales.
- Facilitar el cumplimiento del requisito de persistencia y manejo de datos
  invalidos (Req 2 y Req 5).

Este script no forma parte de la lógica del sistema; funciona únicamente como
herramienta de apoyo para generar y validar datos persistentes.
"""

from __future__ import annotations
import os
from datetime import date, timedelta

from app.repository import HotelRepository, CustomerRepository, ReservationRepository
from app.services import HotelService, CustomerService, ReservationService


def main() -> None:
    print("=== GENERANDO DATOS DE PRUEBA EN JSON ===")

    # Ruta correcta según tu estructura:
    # A01797560_A6.2/data/
    base = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(base, exist_ok=True)

    # Crear repositorios apuntando a JSON reales
    hotels = HotelRepository(os.path.join(base, "hotels.json"))
    customers = CustomerRepository(os.path.join(base, "customers.json"))
    reservations = ReservationRepository(os.path.join(base, "reservations.json"))

    # Crear servicios
    hotel_svc = HotelService(hotels, customers, reservations)
    customer_svc = CustomerService(customers, reservations)
    reservation_svc = ReservationService(reservations, hotel_svc)

    # Crear hotel
    try:
        hotel_svc.create_hotel("H1", "Hotel Central", "CDMX", total_rooms=2)
        print("✓ Hotel H1 creado")
    except Exception as exc:
        print(f"↺ No se creó Hotel H1 (ya existía o error): {exc}")

    # Crear clientes
    for cid, name, email in [
        ("C1", "Ana García", "ana@example.com"),
        ("C2", "Luis Pérez", "luis@example.com"),
    ]:
        try:
            customer_svc.create_customer(cid, name, email)
            print(f"✓ Cliente {cid} creado")
        except Exception as exc:
            print(f"↺ Cliente {cid} no creado: {exc}")

    # Crear reservas
    check_in = date.today() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)

    try:
        r1 = reservation_svc.create("C1", "H1", check_in, check_out)
        print(f"✓ Reserva creada para C1: {r1.reservation_id}")
    except Exception as exc:
        print(f"[ERROR] No se pudo crear reserva para C1: {exc}")

    try:
        r2 = reservation_svc.create("C2", "H1", check_in, check_out)
        print(f"✓ Reserva creada para C2: {r2.reservation_id}")
    except Exception as exc:
        print(f"[ERROR] No se pudo crear reserva para C2: {exc}")

    # Resumen final
    print("\n=== RESUMEN FINAL ===")
    print(f"Hoteles: {[h.hotel_id for h in hotel_svc.list_hotels()]}")
    print(f"Clientes: {[c.customer_id for c in customer_svc.list_customers()]}")
    print(f"Reservas H1: {[r.reservation_id for r in reservation_svc.list_by_hotel('H1')]}")

    print("\nJSON generados/actualizados en:")
    print(f"  {os.path.join(base, 'hotels.json')}")
    print(f"  {os.path.join(base, 'customers.json')}")
    print(f"  {os.path.join(base, 'reservations.json')}")


if __name__ == "__main__":
    main()
