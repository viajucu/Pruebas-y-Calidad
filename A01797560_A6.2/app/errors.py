"""
errors.py

Jerarquía de excepciones para el sistema de reservaciones.

Objetivos:
- Clasificar errores por capa/causa (validación, reglas de negocio, persistencia).
- Proveer mensajes consistentes y legibles en consola.
- Permitir a servicios/repositorios reaccionar de forma específica.

"""

from __future__ import annotations


class AppError(Exception):
    """Excepción base de la aplicación (no usar directamente).
    Heredar de esta clase permite capturar 'errores de dominio' sin
    atrapar excepciones del sistema (IOError, ValueError, etc.).
    """

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def __str__(self) -> str:  # Mensaje (incluye causa si existe)
        base = super().__str__()
        if self.cause is not None:
            return f"{base} (causa: {self.cause})"
        return base


# ---------- Validación ----------#

class ValidationError(AppError):
    """Datos inválidos a nivel de dominio/estructura (campos, tipos, rangos).
    Ejemplos:
      - total_rooms <= 0
      - email con formato inválido
      - check_in >= check_out
    """


# ---------- Reglas de negocio ----------

class BusinessRuleError(AppError):
    """Violación de una regla de negocio.
    Ejemplos:
      - No hay disponibilidad para el rango de fechas
      - No se puede eliminar un hotel/cliente con reservas activas
    """


class NotFoundError(BusinessRuleError):
    """Entidad esperada que no existe (hotel/cliente/reserva no encontrado)."""


class DuplicateIdError(BusinessRuleError):
    """Intento de crear una entidad con un ID ya existente."""


class ConflictError(BusinessRuleError):
    """Conflicto de estado o recurso (p.ej. cancelar una reserva ya cancelada)."""


# ---------- Persistencia / Archivos ----------

class PersistenceError(AppError):
    """Errores al interactuar con el almacenamiento (archivos).
    Ejemplos:
      - Permisos de lectura/escritura
      - Ruta inexistente no recuperable
      - Fallo al guardar el dataset completo
    """


class CorruptDataError(PersistenceError):
    """El archivo existe pero contiene datos corruptos o registros inválidos.
    Recomendación:
      - En repository.py, atrapar registro a registro y continuar
        (imprimir warnings y omitir el registro), para cumplir Req 5.
    """


__all__ = [
    "AppError",
    "ValidationError",
    "BusinessRuleError",
    "NotFoundError",
    "DuplicateIdError",
    "ConflictError",
    "PersistenceError",
    "CorruptDataError",
]
