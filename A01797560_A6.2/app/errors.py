"""
errors.py

Jerarquía de excepciones para el sistema de reservaciones.
Clasifica errores por causa (validación, negocio, persistencia) y
permite mensajes claros en consola.
"""

from __future__ import annotations


class AppError(Exception):
    """Excepción base de la aplicación."""

    def __init__(
            self,
            message: str,
            *,
            cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.cause is not None:
            return f"{base} (causa: {self.cause})"
        return base


# ---------- Validación ----------


class ValidationError(AppError):
    """
    Datos inválidos a nivel de dominio/estructura (campos, tipos, rangos).
    Ejemplos:
      - total_rooms <= 0
      - email inválido
      - check_in >= check_out
    """


# ---------- Reglas de negocio ----------


class BusinessRuleError(AppError):
    """Violación de una regla de negocio."""


class NotFoundError(BusinessRuleError):
    """Entidad esperada que no existe."""


class DuplicateIdError(BusinessRuleError):
    """Intento de crear una entidad con un ID ya existente."""


class ConflictError(BusinessRuleError):
    """Conflicto de estado o recurso."""


# ---------- Persistencia / Archivos ----------


class PersistenceError(AppError):
    """Errores al interactuar con el almacenamiento (archivos)."""


class CorruptDataError(PersistenceError):
    """
    El archivo existe pero contiene datos corruptos o inválidos.
    Sugerencia: omitir registro y continuar para cumplir Req 5.
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
