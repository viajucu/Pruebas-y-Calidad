"""compute_sales.py

Lee el catálogo de precios y un registro de ventas, calcula el costo total por
venta (admite cantidades negativas como devoluciones/ajustes), calcula el gran
total, imprime resultados en pantalla y los guarda en SalesResults.txt.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime

# Utilidades

TWOPLACES = Decimal("0.01")


def to_decimal(value: Any) -> Optional[Decimal]:
    """Intenta convertir un valor a Decimal,
    devolviendo None si no es válido."""
    if value is None:
        return None
    try:
        # Acepta números y cadenas
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def money(amount: Decimal) -> str:
    """Formatea un Decimal como moneda con 2 decimales y
    separadores de miles."""
    q = amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return f"${q:,.2f}"


# Estructuras de datos

@dataclass
class CatalogEntry:
    """Representa un ítem del catálogo."""
    key: str                 # clave de búsqueda (nombre normalizado o id)
    unit_price: Decimal
    raw: Dict[str, Any]


@dataclass
class SaleLine:
    """Representa una línea de venta ya validada."""
    product_label: str
    quantity: Decimal
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        """Representa una línea de venta ya validada."""
        return (
            self.unit_price * self.quantity
        ).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


# Carga de archivos

def load_json(path: Path) -> Any:
    """Carga JSON desde archivo y controla errores básicos."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"[ERROR] No se encontró el archivo: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON inválido en {path}: {exc}", file=sys.stderr)
        sys.exit(1)


# Normalización y construcción de catálogo

def _extract_product_fields(
    item: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], Optional[Decimal]]:
    """
    Intenta extraer (name, pid, price) desde diversas variantes de claves
    comunes en catálogos reales. Devuelve (None, None, None) si no logra
    extraer nada útil.
    """
    # Posibles claves (insensible a mayúsculas)
    lower = {k.lower(): k for k in item.keys()}

    # Nombre
    name_key_candidates = ["product", "title", "name", "nombre", "producto"]
    name: Optional[str] = None
    for c in name_key_candidates:
        if c in lower:
            name = str(item[lower[c]]).strip()
            break

    # ID
    id_key_candidates = ["id", "product_id", "sku", "codigo", "code"]
    pid: Optional[str] = None
    for c in id_key_candidates:
        if c in lower:
            pid = str(item[lower[c]]).strip()
            break

    # Precio
    price_key_candidates = ["price", "unit_price", "precio", "cost", "costo"]
    price: Optional[Decimal] = None
    for c in price_key_candidates:
        if c in lower:
            price = to_decimal(item[lower[c]])
            break

    return name, pid, price


def build_catalog(
    data: Any
) -> Tuple[Dict[str, CatalogEntry], Dict[str, CatalogEntry]]:
    """
    Construye dos índices del catálogo:
      - por nombre normalizado (lowercase): name_index
      - por id: id_index
    """
    # Si viene envuelto, intenta localizar la lista con un nombre común.
    products: Iterable[Dict[str, Any]]
    if isinstance(data, dict):
        # Claves típicas que envuelven la lista de productos
        for key in ("products", "items", "catalog", "catalogue", "lista",
                    "productos"):
            if key in data and isinstance(data[key], list):
                products = data[key]  # type: ignore[assignment]
                break
        else:
            # Si no hay envoltura clara pero es dict, asume que sus values son
            # items con forma dict.
            products = [v for v in data.values() if isinstance(v, dict)]
    elif isinstance(data, list):
        products = data
    else:
        raise ValueError(
            "Estructura de catálogo no reconocida. "
            "Debe ser lista u objeto con lista."
        )

    name_index: Dict[str, CatalogEntry] = {}
    id_index: Dict[str, CatalogEntry] = {}

    for idx, item in enumerate(products):
        if not isinstance(item, dict):
            print(
                f"[WARN] Ítem de catálogo #{idx} no es un objeto: {item!r}",
                file=sys.stderr,
            )
            continue

        name, pid, price = _extract_product_fields(item)

        if price is None or price < 0:
            print(
                f"[WARN] Precio inválido en ítem de catálogo #{idx}: {item}",
                file=sys.stderr,
            )
            continue

        if name:
            key = name.strip().lower()
            name_index[key] = CatalogEntry(
                key=key, unit_price=price, raw=item
            )

        if pid:
            id_index[pid] = CatalogEntry(
                key=pid, unit_price=price, raw=item
            )

    if not name_index and not id_index:
        raise ValueError(
            "No se pudo construir el índice del catálogo. "
            "Revisa las claves y el formato."
        )

    return name_index, id_index


# Extracción de ventas

def _extract_sale_fields(
    item: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], Optional[Decimal]]:
    """
    Intenta extraer (product_name, product_id, quantity) desde diversas
    variantes de claves comunes en archivos de ventas.
    """
    lower = {k.lower(): k for k in item.keys()}

    # Producto por nombre
    product_name: Optional[str] = None
    for c in ("product", "producto", "title", "name"):
        key = c.lower()
        if key in lower:
            product_name = str(item[lower[key]]).strip()
            break

    # Producto por ID
    product_id: Optional[str] = None
    for c in ("product_id", "id", "sku", "codigo", "code"):
        key = c.lower()
        if key in lower:
            product_id = str(item[lower[key]]).strip()
            break

    # Cantidad
    quantity: Optional[Decimal] = None
    for c in ("quantity", "qty", "cantidad"):
        key = c.lower()
        if key in lower:
            quantity = to_decimal(item[lower[key]])
            break

    return product_name, product_id, quantity


def parse_sales(data: Any) -> List[Dict[str, Any]]:
    """Obtiene la lista de ventas desde el JSON,
    tolerando envolturas comunes."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("sales", "ventas", "records", "items", "data"):
            if key in data and isinstance(data[key], list):
                return data[key]
    raise ValueError(
        "Estructura de ventas no reconocida. "
        "Debe ser lista u objeto con lista."
    )


# Cálculo principal

def compute_totals(
    name_index: Dict[str, CatalogEntry],
    id_index: Dict[str, CatalogEntry],
    sales_items: Iterable[Dict[str, Any]],
) -> Tuple[List[SaleLine], List[str], Decimal]:
    """
    Recorre todas las ventas, valida datos y calcula totales.
    Devuelve (líneas válidas, errores, gran total).

    Reglas:
    - Cantidades negativas se interpretan como devoluciones/ajustes
    (se permiten y restan del total).
    - Cantidad igual a cero se reporta como advertencia y se omite.
    """
    lines: List[SaleLine] = []
    errors: List[str] = []
    grand_total = Decimal("0")

    for i, raw in enumerate(sales_items, start=1):
        if not isinstance(raw, dict):
            errors.append(
                f"Línea #{i}: registro no es objeto JSON. Valor: {raw!r}"
            )
            continue

        pname, pid, qty = _extract_sale_fields(raw)

        if qty is None:
            errors.append(
                f"Línea #{i}: cantidad inválida o ausente. Registro: {raw}"
            )
            continue
        # Cantidades negativas = devoluciones/ajustes (se permiten).
        # Cantidad cero no afecta al total; se reporta como advertencia y
        # se omite del reporte detallado.
        if qty == 0:
            errors.append(
                f"Línea #{i}: cantidad igual a cero; partida omitida. "
                f"Registro: {raw}"
            )
            continue

        entry: Optional[CatalogEntry] = None

        # Intento por ID primero si viene
        if pid and pid in id_index:
            entry = id_index[pid]
            label = (
                entry.raw.get("product")
                or entry.raw.get("name")
                or entry.raw.get("title")
                or pid
            )
            product_label = str(label)
        # Si no, intento por nombre
        elif pname:
            key = pname.strip().lower()
            if key in name_index:
                entry = name_index[key]
                product_label = pname
            else:
                entry = None
                product_label = pname
        else:
            product_label = "(desconocido)"

        if entry is None:
            errors.append(
                "Línea #"
                f"{i}: producto '{product_label}' no encontrado en el "
                "catálogo. Registro: "
                f"{raw}"
            )
            continue

        line = SaleLine(
            product_label=product_label,
            quantity=qty,
            unit_price=entry.unit_price,
        )
        lines.append(line)
        grand_total += line.line_total

    # Redondeo final del gran total a 2 decimales
    grand_total = grand_total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return lines, errors, grand_total


# Salida

def render_report(
    price_file: Path,
    sales_file: Path,
    lines: List[SaleLine],
    errors: List[str],
    grand_total: Decimal,
    elapsed_s: float,
) -> str:
    """Genera un reporte en texto."""

    header = [
        "====================== Resultados de Ventas ======================",
        f"Catálogo: {price_file}",
        f"Ventas:   {sales_file}",
        f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "------------------------------------------------------------------",
        "Convenciones: cantidades negativas = devoluciones/ajustes; "
        "0 = omitida",
        f"Partidas válidas: {len(lines)}",
        f"Errores:          {len(errors)}",
        "------------------------------------------------------------------",
    ]

    header.append(
        f"{'Producto':40s} {'Cant.':>8s} "
        f"{'P. Unitario':>14s} {'Importe':>14s}"
    )
    header.append("-----------------------------------------------------")

    body: List[str] = []
    for ln in lines:
        body.append(
            f"{ln.product_label[:40]:40s} {str(ln.quantity):>8s} "
            f"{money(ln.unit_price):>14s} {money(ln.line_total):>14s}"
        )

    footer = [
        "------------------------------------------------------------------",
        f"GRAN TOTAL: {money(grand_total)}",
        f"Tiempo de ejecución: {elapsed_s:.3f} s",
        "==================================================================",
    ]

    if errors:
        footer.append("")
        footer.append("[ERRORES]")
        for e in errors:
            footer.append(f"- {e}")

    return "\n".join(header + body + footer)


def choose_results_path(default_name: str = "SalesResults.txt") -> Path:
    """Devuelve la ruta de salida; usa ./results/ si existe, si no el cwd."""
    results_dir = Path.cwd() / "results"
    if results_dir.exists() and results_dir.is_dir():
        return results_dir / default_name
    return Path.cwd() / default_name


# ---------------------------------- Main ----------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description=(
            "Computa el total de ventas a partir de un catálogo y un "
            "registro de ventas."
        )
    )
    parser.add_argument(
        "price_catalogue",
        help=(
            "Ruta al archivo JSON del catálogo de precios "
            "(p. ej., source/TC1.ProductList.json)"
        ),
    )
    parser.add_argument(
        "sales_record",
        help=(
            "Ruta al archivo JSON del registro de ventas "
            "(p. ej., test/TC1.Sales.json)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Punto de entrada principal."""
    args = parse_args(argv)

    price_path = Path(args.price_catalogue)
    sales_path = Path(args.sales_record)

    start = time.perf_counter()
    try:
        price_json = load_json(price_path)
        sales_json = load_json(sales_path)

        name_index, id_index = build_catalog(price_json)
        sales_items = parse_sales(sales_json)

        lines, errors, grand_total = compute_totals(
            name_index, id_index, sales_items
        )
    except Exception as exc:  # Errores no recuperables
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    elapsed = time.perf_counter() - start

    # Render del reporte
    report = render_report(
        price_file=price_path,
        sales_file=sales_path,
        lines=lines,
        errors=errors,
        grand_total=grand_total,
        elapsed_s=elapsed,
    )

    # Impresión en consola
    print(report)

    # Escritura en archivo
    out_path = choose_results_path("SalesResults.txt")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        # Retroalimentación breve
        print(f"\n[INFO] Resultados guardados en: {out_path}")
    except Exception as exc:
        print(
            f"[WARN] No se pudo escribir el archivo de resultados: {exc}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
