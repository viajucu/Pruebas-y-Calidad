"""Pruebas models.py

Cubre validaciones de dominio: Hotel.total_rooms > 0, email de Customer,
y coherencia de fechas en Reservation (check_in < check_out), además de
roundtrip de serialización a dict/JSON.
"""