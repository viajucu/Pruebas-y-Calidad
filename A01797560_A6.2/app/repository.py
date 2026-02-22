"""
repository.py

Repositorios para persistir entidades (Hotel, Customer, Reservation) en
archivos JSON.

Objetivos:
- Lectura/escritura tolerante a fallos (Req 5):
  * Archivo inexistente → lista vacía.
  * JSON corrupto → mostrar error y continuar.
  * Registro inválido → warning y omitir.
- CRUD básico sin reglas de negocio (éstas viven en services.py).
- Serialización/deserialización vía to_dict/from_dict del modelo.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List

from .errors import PersistenceError
from .models import Customer, Hotel, Reservation


# ---------- Utilidad de bajo nivel para listas JSON ----------


class JsonStore:
    """Encapsula lectura/escritura de listas en JSON
    con tolerancia a fallos."""

    @staticmethod
    def load_list(path: str) -> List[Dict[str, Any]]:
        """Carga una lista de dicts desde JSON. Tolerante a errores."""
        if not os.path.exists(path):
            print(
                f"[WARN] Archivo no encontrado: {path} — "
                "se usará lista vacía"
            )
            return []

        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            print(
                f"[ERROR] JSON corrupto en {path}: {exc} — "
                "se usará lista vacía"
            )
            return []
        except OSError as exc:
            print(
                f"[ERROR] No se pudo leer {path}: {exc} — "
                "se usará lista vacía"
            )
            return []

        if not isinstance(raw, list):
            print(
                "[ERROR] Estructura inválida en "
                f"{path}: se esperaba lista — se usará lista vacía"
            )
            return []

        return raw

    @staticmethod
    def save_list(path: str, items: List[Dict[str, Any]]) -> None:
        """Guarda una lista de dicts como JSON (falla con PersistenceError)."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(items, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise PersistenceError(
                f"No se pudo guardar el archivo {path}", cause=exc
            ) from exc


# ---------- Repositorios base y específicos ----------


class BaseRepository:
    """Base para repositorios con operaciones comunes."""

    def __init__(
        self,
        path: str,
        to_dict: Callable[[Any], Dict[str, Any]],
        from_dict: Callable[[Dict[str, Any]], Any],
        id_attr: str,
    ) -> None:
        self._path = path
        self._to_dict = to_dict
        self._from_dict = from_dict
        self._id_attr = id_attr

    # ---------- Operaciones internas ----------

    def _load_all(self) -> List[Any]:
        """Carga todos los registros del JSON, omitiendo inválidos."""
        raw_list = JsonStore.load_list(self._path)
        items: List[Any] = []
        for i, raw in enumerate(raw_list):
            try:
                item = self._from_dict(raw)
                items.append(item)
            except (ValueError, TypeError) as exc:
                print(
                    "[WARN] Registro inválido omitido en "
                    f"{self._path} (index={i}): {exc}"
                )
        return items

    def _save_all(self, items: List[Any]) -> None:
        """Persiste el arreglo completo de entidades."""
        payload = [self._to_dict(x) for x in items]
        JsonStore.save_list(self._path, payload)

    def _find_index(self, items: List[Any], entity_id: str) -> int:
        """Localiza el índice por ID o -1 si no existe."""
        for idx, item in enumerate(items):
            if str(getattr(item, self._id_attr)) == str(entity_id):
                return idx
        return -1

    # ---------- CRUD genérico ----------

    def list_all(self) -> List[Any]:
        """Devuelve todas las entidades deserializadas."""
        return self._load_all()

    def get_by_id(self, entity_id: str) -> Any | None:
        """Devuelve una entidad por ID o None."""
        for item in self._load_all():
            if str(getattr(item, self._id_attr)) == str(entity_id):
                return item
        return None

    def upsert(self, entity: Any) -> None:
        """Crea/actualiza una entidad por su ID (idempotente)."""
        items = self._load_all()
        idx = self._find_index(items, str(getattr(entity, self._id_attr)))
        if idx >= 0:
            items[idx] = entity
        else:
            items.append(entity)
        self._save_all(items)

    def delete(self, entity_id: str) -> bool:
        """Elimina por ID. True si eliminó, False si no existía."""
        items = self._load_all()
        idx = self._find_index(items, entity_id)
        if idx == -1:
            return False
        items.pop(idx)
        self._save_all(items)
        return True


class HotelRepository(BaseRepository):
    """Repositorio de hoteles."""

    def __init__(self, path: str) -> None:
        super().__init__(
            path=path,
            to_dict=lambda h: h.to_dict(),
            from_dict=Hotel.from_dict,
            id_attr="hotel_id",
        )


class CustomerRepository(BaseRepository):
    """Repositorio de clientes."""

    def __init__(self, path: str) -> None:
        super().__init__(
            path=path,
            to_dict=lambda c: c.to_dict(),
            from_dict=Customer.from_dict,
            id_attr="customer_id",
        )


class ReservationRepository(BaseRepository):
    """Repositorio de reservas (con ayudas de filtrado)."""

    def __init__(self, path: str) -> None:
        super().__init__(
            path=path,
            to_dict=lambda r: r.to_dict(),
            from_dict=Reservation.from_dict,
            id_attr="reservation_id",
        )

    def list_by_hotel(self, hotel_id: str) -> List[Reservation]:
        """Lista reservas por ID de hotel."""
        return [r for r in self.list_all() if r.hotel_id == hotel_id]

    def list_by_customer(self, customer_id: str) -> List[Reservation]:
        """Lista reservas por ID de cliente."""
        return [r for r in self.list_all() if r.customer_id == customer_id]
