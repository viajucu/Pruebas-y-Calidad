"""
Script utilitario para generar datos iniciales en formato JSON dentro del
directorio 'data/'. Crea hoteles, clientes y reservas válidas utilizando
los servicios y repositorios del proyecto.

"""

from __future__ import annotations

import io
import os
import sys
import time
from contextlib import redirect_stdout
from datetime import date, timedelta, datetime

from app.errors import BusinessRuleError, DuplicateIdError, ValidationError
from app.repository import (
    HotelRepository,
    CustomerRepository,
    ReservationRepository,
)
from app.services import (
    HotelService,
    CustomerService,
    ReservationService,
)

# Directorios base
PROJECT_ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def run_seed() -> None:
    """
    Ejecuta la siembra de datos:
      - Crea hotel H1 y clientes C1, C2.
      - Intenta dos reservas para H1 en el mismo rango de fechas.
      - Muestra un resumen final.
    También imprime las rutas de los JSON generados/actualizados.
    """
    print("=== GENERANDO DATOS DE PRUEBA EN JSON ===")

    # Repositorios apuntando a archivos JSON reales
    hotels = HotelRepository(os.path.join(DATA_DIR, "hotels.json"))
    customers = CustomerRepository(os.path.join(DATA_DIR, "customers.json"))
    reservations = ReservationRepository(
        os.path.join(DATA_DIR, "reservations.json")
    )

    # Servicios
    hotel_svc = HotelService(hotels, customers, reservations)
    customer_svc = CustomerService(customers, reservations)
    reservation_svc = ReservationService(reservations, hotel_svc)

    # Semillas
    try:
        hotel_svc.create_hotel("H1", "Hotel Central", "CDMX", total_rooms=2)
        print("✓ Hotel H1 creado")
    except (DuplicateIdError, ValidationError, BusinessRuleError) as exc:
        print(f"↺ No se creó Hotel H1 (ya existía o error): {exc}")

    for cid, name, email in [
        ("C1", "Ana García", "ana@example.com"),
        ("C2", "Luis Pérez", "luis@example.com"),
    ]:
        try:
            customer_svc.create_customer(cid, name, email)
            print(f"✓ Cliente {cid} creado")
        except (DuplicateIdError, ValidationError) as exc:
            print(f"↺ Cliente {cid} no creado: {exc}")

    check_in = date.today() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)

    try:
        r1 = reservation_svc.create("C1", "H1", check_in, check_out)
        print(f"✓ Reserva creada para C1: {r1.reservation_id}")
    except (ValidationError, BusinessRuleError) as exc:
        print(f"[ERROR] No se pudo crear reserva para C1: {exc}")

    try:
        r2 = reservation_svc.create("C2", "H1", check_in, check_out)
        print(f"✓ Reserva creada para C2: {r2.reservation_id}")
    except (ValidationError, BusinessRuleError) as exc:
        print(f"[ERROR] No se pudo crear reserva para C2: {exc}")

    # Resumen
    print("\n=== RESUMEN FINAL ===")
    print(f"Hoteles: {[h.hotel_id for h in hotel_svc.list_hotels()]}")
    print(f"Clientes: {[c.customer_id for c in customer_svc.list_customers()]}")
    print(
        "Reservas H1: "
        f"{[r.reservation_id for r in reservation_svc.list_by_hotel('H1')]}"
    )

    # Rutas JSON
    print("\nJSON generados/actualizados en:")
    print(f"  {os.path.join(DATA_DIR, 'hotels.json')}")
    print(f"  {os.path.join(DATA_DIR, 'customers.json')}")
    print(f"  {os.path.join(DATA_DIR, 'reservations.json')}")

    # Info extra útil para documentación
    print("\nDirectorio de datos:", DATA_DIR)
    print("Directorio de resultados:", RESULTS_DIR)


def main() -> None:
    """
    Envuelve la ejecución para:
      - Medir el tiempo con perf_counter().
      - Capturar stdout y guardarlo en results/*.txt.
      - Mostrar el tiempo total al final.
    """
    start = time.perf_counter()

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run_seed()

    # Reenvía a consola lo capturado
    captured = buffer.getvalue()
    sys.stdout.write(captured)

    elapsed = time.perf_counter() - start
    line = f"\nTiempo total de ejecución: {elapsed:.3f} s\n"
    print(line.strip())

    # Guardado en results/<timestamp>_seed_data.txt
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"{timestamp}_seed_data.txt")

    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(captured)
            fh.write(line)
        print(f"Resultado guardado en: {out_path}")
    except OSError as exc:
        print(f"[ERROR] No se pudo escribir el archivo de resultados: {exc}")


if __name__ == "__main__":
    main()
