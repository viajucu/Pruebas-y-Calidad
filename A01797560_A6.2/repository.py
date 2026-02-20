"""
Contiene las clases de repositorio para gestionar la persistencia
de entidades (Hotel, Customer, Reservation) usando archivos JSON.

Objetivos:
    - Implementar lectura/escritura tolerante a fallos (Req 5):
        * Si el archivo no existe → lista vacía.
        * Si el JSON está corrupto → mostrar error y continuar.
        * Si un registro es inválido → mostrar warning y omitirlo.
    - Proveer CRUD básico sin reglas de negocio (eso va en services.py).
    - Serializar/deserializar entidades usando los métodos to_dict/from_dict.
    - Mantener separación limpia entre:
        * Modelos (estructura)
        * Persistencia (este módulo)
        * Servicios (reglas de negocio)
 """

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Callable, Dict, List, TypeVar

from app.errors import (
    PersistenceError,
)
from app.models import Customer, Hotel, Reservation

T = TypeVar("T")  # Tipo genérico para listas de entidades


# ---------- Utilidad de bajo nivel para persistir
# listas en JSON ----------

class JsonStore:
    """Encapsula lectura/escritura de listas en JSON con tolerancia a fallos.

    - Si el archivo no existe, retorna lista vacía.
    - Si el JSON está corrupto, imprime error y retorna lista vacía.
    - No valida registros; solo entrega el 'raw' (lista de dicts).
    """

    @staticmethod
    def load_list(path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            # No es error: el sistema puede arrancar 'en limpio'
            print(f"[WARN] Archivo no encontrado: {path} — se usará lista vacía")
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"[ERROR] JSON corrupto en {path}: {exc} — se usará lista vacía")
            return []
        except OSError as exc:
            # Error real del SO: informar y continuar con lista vacía
            print(f"[ERROR] No se pudo leer {path}: {exc} — se usará lista vacía")
            return []

        if not isinstance(raw, list):
            print(f"[ERROR] Estructura inválida en {path}: se esperaba lista — se usará lista vacía")
            return []

        return raw

    @staticmethod
    def save_list(path: str, items: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            # Aquí sí levantamos excepción porque NO pudimos persistir el dataset
            raise PersistenceError(f"No se pudo guardar el archivo {path}", cause=exc) from exc


# ---------- Repositorios: serializan/deserializan
# y exponen CRUD básico ----------

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
        """Carga todos los registros del JSON, omitiendo los inválidos (Req 5)."""
        raw_list = JsonStore.load_list(self._path)
        items: List[Any] = []
        for i, raw in enumerate(raw_list):
            try:
                item = self._from_dict(raw)
                items.append(item)
            except Exception as exc:
                # Registro inválido -> avisar y continuar
                print(f"[WARN] Registro inválido omitido en {self._path} (index={i}): {exc}")
                continue
        return items

    def _save_all(self, items: List[Any]) -> None:
        payload = [self._to_dict(x) for x in items]
        JsonStore.save_list(self._path, payload)

    def _find_index(self, items: List[Any], entity_id: str) -> int:
        for idx, item in enumerate(items):
            if str(getattr(item, self._id_attr)) == str(entity_id):
                return idx
        return -1

    # ---------- CRUD genérico ----------

    def list_all(self) -> List[Any]:
        return self._load_all()

    def get_by_id(self, entity_id: str) -> Any | None:
        for item in self._load_all():
            if str(getattr(item, self._id_attr)) == str(entity_id):
                return item
        return None

    def upsert(self, entity: Any) -> None:
        """Inserta o actualiza por ID (idempotente)."""
        items = self._load_all()
        idx = self._find_index(items, str(getattr(entity, self._id_attr)))
        if idx >= 0:
            items[idx] = entity
        else:
            items.append(entity)
        self._save_all(items)

    def delete(self, entity_id: str) -> bool:
        """Elimina por ID. Retorna True si eliminó, False si no existía."""
        items = self._load_all()
        idx = self._find_index(items, entity_id)
        if idx == -1:
            return False
        items.pop(idx)
        self._save_all(items)
        return True


# ---------- Repos específicos por entidad ----------

class HotelRepository(BaseRepository):
    def __init__(self, path: str) -> None:
        super().__init__(
            path=path,
            to_dict=lambda h: h.to_dict(),
            from_dict=Hotel.from_dict,
            id_attr="hotel_id",
        )


class CustomerRepository(BaseRepository):
    def __init__(self, path: str) -> None:
        super().__init__(
            path=path,
            to_dict=lambda c: c.to_dict(),
            from_dict=Customer.from_dict,
            id_attr="customer_id",
        )


class ReservationRepository(BaseRepository):
    def __init__(self, path: str) -> None:
        super().__init__(
            path=path,
            to_dict=lambda r: r.to_dict(),
            from_dict=Reservation.from_dict,
            id_attr="reservation_id",
        )

    # Si necesitas búsquedas por hotel/cliente, agregamos helpers:

    def list_by_hotel(self, hotel_id: str) -> List[Reservation]:
        return [r for r in self.list_all() if r.hotel_id == hotel_id]

    def list_by_customer(self, customer_id: str) -> List[Reservation]:
        return [r for r in self.list_all() if r.customer_id == customer_id]
