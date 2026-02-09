"""
wordCount.py

Cuenta palabras distintas y sus frecuencias desde un archivo de texto.
"""

import sys
import time

RESULTS_FILENAME = "WordCountResults.txt"

# Caracteres a remover únicamente al inicio/fin del token
PUNCTUATION = ".,;:!?\"'()[]{}<>`~@#$%^&*_+=|\\/“”‘’"


def strip_edge_punctuation(token):
    """
    Elimina signos de puntuación al inicio y al final de un token
    usando bucles básicos (sin regex).

    Args:
        token (str): token original

    Returns:
        str: token sin puntuación en los extremos
    """
    if not token:
        return token

    start = 0
    end = len(token) - 1

    while start <= end and token[start] in PUNCTUATION:
        start += 1

    while end >= start and token[end] in PUNCTUATION:
        end -= 1

    return token[start:end + 1]


def is_valid_word(token):
    """
    Determina si un token es una palabra válida.

    Reglas:
    - Debe contener al menos una letra.
    - Permitidos: letras, apóstrofe (') y guion (-).
    - No se permiten dígitos.
    - Cualquier otro símbolo la hace inválida.

    Args:
        token (str): token limpio

    Returns:
        bool: True si es válido, False si no
    """
    if not token:
        return False

    has_letter = False
    for ch in token:
        if ch.isdigit():
            return False
        if ch.isalpha():
            has_letter = True
        elif ch not in ("'", "-"):
            return False

    return has_letter


def normalize_word(token):
    """
    Normaliza una palabra para el conteo (no distingue mayúsculas/minúsculas).

    Args:
        token (str): palabra válida

    Returns:
        str: palabra normalizada
    """
    return token.lower()


def parse_words_from_file(file_path):
    """
    Lee el archivo y cuenta palabras válidas.

    Returns:
        freq (dict[str, int]): palabra -> conteo
        invalid_count (int): tokens inválidos encontrados
        blank_count (int): tokens que quedaron vacíos tras quitar puntuación
    """
    freq = {}
    invalid_count = 0
    blank_count = 0

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line_num, line in enumerate(file, start=1):
                tokens = line.split()

                for raw in tokens:
                    cleaned = strip_edge_punctuation(raw)

                    # Si queda vacío tras limpiar, cuenta como "(blank)"
                    if cleaned == "":
                        blank_count += 1
                        continue

                    if not is_valid_word(cleaned):
                        invalid_count += 1
                        print(
                            f"[Dato inválido] línea {line_num}: "
                            f"token '{raw}' no es una palabra válida"
                        )
                        continue

                    word = normalize_word(cleaned)
                    freq[word] = freq.get(word, 0) + 1

    except FileNotFoundError:
        raise
    except OSError as exc:
        raise OSError(f"Error al leer el archivo '{file_path}': {exc}") from exc

    return freq, invalid_count, blank_count


def merge_sort_items_by_count(items):
    """
    Merge sort iterativo (bottom-up) para ordenar una lista de tuplas
    (palabra, conteo) por conteo descendente.

    Importante:
    - El algoritmo es ESTABLE: si hay empate en conteo, conserva el orden
      original de los elementos (orden de aparición).
    - No usa sorted() ni funciones de ordenamiento.

    Args:
        items (list[tuple[str, int]]): lista a ordenar

    Returns:
        list[tuple[str, int]]: lista ordenada por conteo (desc) y estable
    """
    n = len(items)
    if n <= 1:
        return items[:]

    src = items[:]
    dest = [None] * n
    width = 1

    while width < n:
        i = 0
        while i < n:
            left = i

            mid = i + width
            if mid > n:
                mid = n

            right = i + 2 * width
            if right > n:
                right = n

            li = left
            ri = mid
            di = left

            # Merge estable:
            # Si conteos empatan, se toma primero el elemento de la izquierda.
            while li < mid and ri < right:
                if src[li][1] >= src[ri][1]:
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


def build_results_text(freq, blank_count, elapsed_seconds):
    """
    Construye la salida con formato tipo tabla:
    - "Row Labels\tCount"
    - palabra\tconteo (ordenado por conteo; empate conserva orden de aparición)
    - "(blank)\t" (con conteo si aplica)
    - "Grand Total\tN"
    - "Time elapsed (seconds): X.XXXXXX"

    Args:
        freq (dict[str, int]): conteos por palabra
        blank_count (int): cantidad de tokens vacíos tras limpiar
        elapsed_seconds (float): tiempo transcurrido

    Returns:
        str: texto final para imprimir y guardar
    """
    lines = []
    lines.append("Row Labels\tCount")

    items = list(freq.items())
    sorted_items = merge_sort_items_by_count(items)

    total_valid = 0
    for word, count in sorted_items:
        lines.append(f"{word}\t{count}")
        total_valid += count

    if blank_count > 0:
        lines.append(f"(blank)\t{blank_count}")
        grand_total = total_valid + blank_count
    else:
        lines.append("(blank)\t")
        grand_total = total_valid

    lines.append(f"Grand Total\t{grand_total}")
    lines.append(f"Time elapsed (seconds): {elapsed_seconds:.6f}")
    lines.append("")

    return "\n".join(lines)


def write_results_to_file(text):
    """
    Escribe los resultados en el archivo WordCountResults.txt.

    Args:
        text (str): contenido a guardar
    """
    with open(RESULTS_FILENAME, "w", encoding="utf-8") as file:
        file.write(text)


def main():
    """
    Función principal:
    - Valida el argumento del archivo de entrada
    - Cuenta palabras válidas
    - Ordena por frecuencia (Count) usando merge sort estable (algoritmo básico)
    - Imprime y guarda resultados
    """
    start_time = time.perf_counter()

    if len(sys.argv) < 2:
        print("Error: falta el parámetro del archivo de entrada.")
        print("Uso: python wordCount.py fileWithData.txt")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        freq, invalid_count, blank_count = parse_words_from_file(file_path)
    except FileNotFoundError:
        print(f"Error: archivo no encontrado: {file_path}")
        sys.exit(1)
    except OSError as exc:
        print(str(exc))
        sys.exit(1)

    elapsed = time.perf_counter() - start_time
    results_text = build_results_text(freq, blank_count, elapsed)

    print(results_text)
    write_results_to_file(results_text)

    _ = invalid_count


if __name__ == "__main__":
    main()
