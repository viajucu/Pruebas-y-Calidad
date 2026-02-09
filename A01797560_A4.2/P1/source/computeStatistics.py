"""
computeStatistics.py

Calcula estadísticas descriptivas (media, mediana, moda, varianza poblacional y
desviación estándar poblacional) de un archivo que contiene números.

"""

import sys
import time


RESULTS_FILENAME = "StatisticsResults.txt"

# Parámetros para el metodo de Newton-Raphson (raíz cuadrada)
SQRT_TOLERANCE = 1e-12
SQRT_MAX_ITER = 50


def parse_numbers_from_file(file_path):
    """
    Lee un archivo de texto y extrae valores numéricos.

    Regla: UN NÚMERO POR LÍNEA.
    - Si la línea contiene ',' o ';' -> inválida.
    - Si la línea contiene más de un token (espacios internos) -> inválida.
    - Si no se puede convertir a float -> inválida.
    - Las líneas vacías se ignoran.

    Retorna:
        numbers (list[float]): números válidos convertidos a float
        invalid_count (int): cantidad de líneas inválidas encontradas
    """
    numbers = []
    invalid_count = 0

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line_num, line in enumerate(file, start=1):
                raw = line.strip()

                # Ignorar líneas vacías (no cuentan como inválidas)
                if not raw:
                    continue

                # Si contiene coma o punto y coma, se toma como inválida
                if "," in raw or ";" in raw:
                    invalid_count += 1
                    print(
                        f"[Dato inválido] línea {line_num}: "
                        f"'{raw}' contiene ',' o ';'"
                    )
                    continue

                # Debe haber exactamente un valor por línea
                parts = raw.split()
                if len(parts) != 1:
                    invalid_count += 1
                    print(
                        f"[Dato inválido] línea {line_num}: "
                        f"'{raw}' contiene más de un valor"
                    )
                    continue

                token = parts[0]
                try:
                    numbers.append(float(token))
                except ValueError:
                    invalid_count += 1
                    print(
                        f"[Dato inválido] línea {line_num}: "
                        f"'{raw}' no es un número"
                    )

    except FileNotFoundError:
        raise
    except OSError as exc:
        raise OSError(f"Error al leer el archivo '{file_path}': {exc}") from exc

    return numbers, invalid_count


def merge_sort_iterative(values):
    """
    Implementación iterativa (bottom-up) de Merge Sort.
    Retorna una nueva lista ordenada de forma ascendente.
    """
    n = len(values)
    if n <= 1:
        return values[:]

    src = values[:]
    dest = [0.0] * n
    width = 1

    while width < n:
        i = 0
        while i < n:
            left = i
            mid = min(i + width, n)
            right = min(i + 2 * width, n)

            li = left
            ri = mid
            di = left

            while li < mid and ri < right:
                if src[li] <= src[ri]:
                    dest[di] = src[li]
                    li += 1
                else:
                    dest[di] = src[ri]
                    ri += 1
                di += 1

            while li < mid:
                dest[di] = src[li]
                li += 1
                di += 1

            while ri < right:
                dest[di] = src[ri]
                ri += 1
                di += 1

            i += 2 * width

        src, dest = dest, src
        width *= 2

    return src


def compute_mean(values):
    """
    Calcula la media aritmética:
        media = suma / n
    """
    total = 0.0
    count = 0
    for x in values:
        total += x
        count += 1
    return total / count if count > 0 else None


def compute_median(values_sorted):
    """
    Calcula la mediana a partir de una lista ya ordenada.
    """
    n = len(values_sorted)
    if n == 0:
        return None

    mid = n // 2
    if n % 2 == 1:
        return values_sorted[mid]

    return (values_sorted[mid - 1] + values_sorted[mid]) / 2.0


def compute_mode(values):
    """
    Calcula UNA sola moda usando un diccionario de frecuencias.

    Regla:
    - Si todos aparecen una sola vez -> no hay moda (retorna None).
    - Si hay empate en frecuencia máxima -> devuelve la primera moda
      que aparece en el archivo (orden de aparición).

    Retorna:
        float | None: moda o None si no existe
    """
    if not values:
        return None

    freq = {}
    first_pos = {}
    next_pos = 0

    for x in values:
        if x not in first_pos:
            first_pos[x] = next_pos
            next_pos += 1
        freq[x] = freq.get(x, 0) + 1

    # Encontrar la frecuencia máxima
    max_count = 0
    for count in freq.values():
        if count > max_count:
            max_count = count

    if max_count <= 1:
        return None

    best_value = None
    best_index = None
    for value, count in freq.items():
        if count == max_count:
            idx = first_pos[value]
            if best_index is None or idx < best_index:
                best_index = idx
                best_value = value

    return best_value


def sqrt_newton(value):
    """
    Calcula la raíz cuadrada usando Newton-Raphson con escalado.

    Motivo:
    - Para números enormes (por ejemplo ~1e40), empezar con x=value requiere
      muchas iteraciones. El escalado lleva el valor a un rango cómodo.

    Estrategia:
    - Escribir value = scaled * (factor^2), donde scaled queda en [1, 4].
    - Calcular sqrt(value) = sqrt(scaled) * factor.
    """
    if value < 0:
        return None
    if value == 0:
        return 0.0

    scaled = value
    factor = 1.0

    # Escala hacia abajo si es muy grande
    while scaled > 4.0:
        scaled /= 4.0
        factor *= 2.0

    # Escala hacia arriba si es muy pequeño (por completitud)
    while scaled < 1.0:
        scaled *= 4.0
        factor /= 2.0

    # Newton-Raphson sobre scaled (rápida convergencia)
    x = 1.0
    for _ in range(SQRT_MAX_ITER):
        prev = x
        x = 0.5 * (x + scaled / x)
        if abs(x - prev) <= SQRT_TOLERANCE:
            break

    return x * factor


def compute_varianza_y_desv_est_poblacional(values, mean):
    """
    Calcula varianza poblacional y desviación estándar poblacional.

    Fórmulas:
        varianza = sum((x - media)^2) / n
        desviación = sqrt(varianza)
    """
    n = len(values)
    if n == 0:
        return None, None

    total_sq = 0.0
    for x in values:
        diff = x - mean
        total_sq += diff * diff

    varianza_poblacional = total_sq / n
    desv_est_poblacional = sqrt_newton(varianza_poblacional)
    return varianza_poblacional, desv_est_poblacional


def format_mode(mode_value):
    """
    Da formato a la moda para mostrar en resultados.
    """
    if mode_value is None:
        return "Sin moda (valores únicos o misma frecuencia)"
    return str(mode_value)


def write_results_to_file(text):
    """
    Escribe los resultados en el archivo StatisticsResults.txt.
    """
    with open(RESULTS_FILENAME, "w", encoding="utf-8") as file:
        file.write(text)


def build_results_text(file_path, results, elapsed_seconds):
    """
    Construye el texto final para imprimir en consola y guardar en archivo.
    """
    lines = []
    lines.append("Resultados de Estadística Descriptiva")
    lines.append("=" * 36)
    lines.append(f"Archivo de entrada: {file_path}")
    lines.append(f"Elementos válidos: {results['count_valid']}")
    lines.append(f"Elementos inválidos: {results['count_invalid']}")
    lines.append("")

    if results["count_valid"] == 0:
        lines.append("No se encontraron datos numéricos válidos.")
    else:
        lines.append(f"Media: {results['mean']}")
        lines.append(f"Mediana: {results['median']}")
        lines.append(f"Moda: {format_mode(results['mode'])}")
        lines.append(f"Varianza poblacional: {results['varianza_poblacional']}")
        lines.append(
            "Desviación estándar poblacional: "
            f"{results['desv_est_poblacional']}"
        )

    lines.append("")
    lines.append(f"Tiempo transcurrido (segundos): {elapsed_seconds:.6f}")
    lines.append("")

    return "\n".join(lines)


def main():
    """
    Función principal:
    - Lee el archivo recibido como argumento
    - Calcula estadísticas
    - Imprime y guarda resultados
    """
    start_time = time.perf_counter()

    if len(sys.argv) < 2:
        print("Error: falta el archivo de entrada.")
        print("Uso: python computeStatistics.py fileWithData.txt")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        numbers, invalid_count = parse_numbers_from_file(file_path)
    except FileNotFoundError:
        print(f"Error: no se encontró el archivo: {file_path}")
        sys.exit(1)
    except OSError as exc:
        print(str(exc))
        sys.exit(1)

    if numbers:
        sorted_numbers = merge_sort_iterative(numbers)
        mean = compute_mean(numbers)
        median = compute_median(sorted_numbers)
        mode_value = compute_mode(numbers)
        varianza_poblacional, desv_est_poblacional = (
            compute_varianza_y_desv_est_poblacional(numbers, mean)
        )
    else:
        mean = None
        median = None
        mode_value = None
        varianza_poblacional = None
        desv_est_poblacional = None

    elapsed = time.perf_counter() - start_time

    results = {
        "count_valid": len(numbers),
        "count_invalid": invalid_count,
        "mean": mean,
        "median": median,
        "mode": mode_value,
        "varianza_poblacional": varianza_poblacional,
        "desv_est_poblacional": desv_est_poblacional,
    }

    results_text = build_results_text(
        file_path=file_path,
        results=results,
        elapsed_seconds=elapsed
    )

    print(results_text)
    write_results_to_file(results_text)


if __name__ == "__main__":
    main()
