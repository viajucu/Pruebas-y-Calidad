"""
convertNumbers.py

Programa que convierte números decimales leídos desde un archivo de texto
a representación binaria y hexadecimal, mostrando resultados en pantalla y
guardándolos en un archivo llamado "ConvertionResults.txt".
"""

import sys
import time

RESULTS_FILENAME = "ConvertionResults.txt"
HEX_DIGITS = "0123456789ABCDEF"

# Anchos fijos para complemento a dos (solo aplican a negativos).
BIN_WIDTH = 10
HEX_WIDTH = 40


def parse_int_token(token):
    """
    Convierte un token a entero de forma segura, sin aceptar flotantes.

    Reglas:
    - Permite signo opcional + o -.
    - Debe contener solo dígitos (después del signo).

    Args:
        token (str): texto a interpretar como entero

    Returns:
        int | None: entero si es válido, None si es inválido
    """
    if not token:
        return None

    sign = 1
    start = 0

    if token[0] == "-":
        sign = -1
        start = 1
    elif token[0] == "+":
        start = 1

    if start == len(token):
        return None

    value = 0
    for ch in token[start:]:
        if ch < "0" or ch > "9":
            return None
        value = value * 10 + (ord(ch) - ord("0"))

    return sign * value


def digit_for_value(value):
    """
    Devuelve el carácter correspondiente para un valor entre 0 y 15.

    Args:
        value (int): valor del dígito (0..15)

    Returns:
        str: carácter en hexadecimal (0..9, A..F)
    """
    return HEX_DIGITS[value]


def to_base_string_unsigned(number, base):
    """
    Convierte un entero NO negativo a una cadena en la base indicada,
    usando el algoritmo básico de divisiones sucesivas.

    Restricción:
    - No usa bin(), hex() ni format().

    Args:
        number (int): entero >= 0
        base (int): base destino (2 o 16)

    Returns:
        str: representación del número en la base indicada
    """
    if number == 0:
        return "0"

    digits = []
    n = number
    while n > 0:
        remainder = n % base
        digits.append(digit_for_value(remainder))
        n //= base

    digits.reverse()
    return "".join(digits)


def pow2(width_bits):
    """
    Calcula 2 elevado a 'width_bits' usando multiplicación repetida.

    Se usa para obtener el módulo (2^N) requerido en complemento a dos,
    evitando el uso de pow().

    Args:
        width_bits (int): número de bits

    Returns:
        int: 2^width_bits
    """
    result = 1
    for _ in range(width_bits):
        result *= 2
    return result


def to_twos_complement_string(number, base, width_bits):
    """
    Convierte un entero a cadena en base 2 o 16.

    - Si number >= 0: devuelve su representación natural (sin padding).
    - Si number < 0: devuelve complemento a dos con ancho fijo 'width_bits'
      y padding para completar el tamaño requerido.

    Args:
        number (int): entero a convertir
        base (int): 2 o 16
        width_bits (int): ancho en bits para complemento a dos (negativos)

    Returns:
        str: representación en base indicada o "#VALUE!" si no cabe
    """
    if base not in (2, 16):
        raise ValueError("Solo se soporta base 2 y base 16.")

    if number >= 0:
        return to_base_string_unsigned(number, base)

    modulus = pow2(width_bits)          # 2^width_bits
    unsigned_value = modulus + number   # number es negativo

    if unsigned_value < 0:
        return "#VALUE!"

    s = to_base_string_unsigned(unsigned_value, base)

    if base == 2:
        pad_len = width_bits
    else:
        pad_len = (width_bits + 3) // 4  # bits -> dígitos hex

    if len(s) < pad_len:
        s = ("0" * (pad_len - len(s))) + s

    return s


def parse_items_from_file(file_path):
    """
    Lee el archivo y genera una lista de ítems, respetando el orden original.

    Interpretación por línea:
    - 1 token: DEC = token
    - 2+ tokens: DEC = tokens[1]

    Args:
        file_path (str): ruta del archivo a leer

    Returns:
        list[dict]: lista de ítems con:
            - line (int): número de línea
            - dec_token (str): token a convertir
            - dec_value (int | None): valor entero si es válido
    """
    items = []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line_num, line in enumerate(file, start=1):
                cleaned = line.replace(",", " ")
                tokens = cleaned.split()

                if not tokens:
                    continue

                if len(tokens) == 1:
                    dec_token = tokens[0]
                else:
                    dec_token = tokens[1]

                dec_value = parse_int_token(dec_token)
                if dec_value is None:
                    print(
                        f"[Dato inválido] línea {line_num}: "
                        f"token '{dec_token}' no es un entero válido"
                    )

                items.append(
                    {
                        "line": line_num,
                        "dec_token": dec_token,
                        "dec_value": dec_value,
                    }
                )
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise OSError(f"Error al leer el archivo '{file_path}': {exc}") from exc

    return items


def build_results_text(file_path, items, elapsed_seconds):
    """
    Construye el texto final de salida para consola y archivo de resultados.

    Formato solicitado:
    - Quita columnas ITEM e INPUT.
    - Deja únicamente: DEC, BIN, HEX.

    Args:
        file_path (str): archivo de entrada procesado
        items (list[dict]): ítems parseados en orden
        elapsed_seconds (float): tiempo transcurrido en segundos

    Returns:
        str: texto listo para imprimir y guardar
    """
    valid_count = 0
    invalid_count = 0

    lines = []
    lines.append("Resultados de Conversión (Decimal -> Binario, Hexadecimal)")
    lines.append("=" * 60)
    lines.append(f"Archivo de entrada: {file_path}")
    lines.append("")
    lines.append("DEC\tBIN\tHEX")

    for it in items:
        dec_token = it["dec_token"]
        dec_value = it["dec_value"]

        if dec_value is None:
            invalid_count += 1
            lines.append(f"{dec_token}\t#VALUE!\t#VALUE!")
            continue

        valid_count += 1
        bin_str = to_twos_complement_string(dec_value, 2, BIN_WIDTH)
        hex_str = to_twos_complement_string(dec_value, 16, HEX_WIDTH)
        lines.append(f"{dec_value}\t{bin_str}\t{hex_str}")

    lines.append("")
    lines.append(f"Elementos válidos: {valid_count}")
    lines.append(f"Elementos inválidos: {invalid_count}")
    lines.append(f"Tiempo transcurrido (segundos): {elapsed_seconds:.6f}")
    lines.append("")

    return "\n".join(lines)


def write_results_to_file(text):
    """
    Guarda el texto de resultados en el archivo ConvertionResults.txt.

    Args:
        text (str): contenido a escribir en el archivo de salida
    """
    with open(RESULTS_FILENAME, "w", encoding="utf-8") as file:
        file.write(text)


def main():
    """
    Punto de entrada principal del programa.

    - Valida argumentos de línea de comandos.
    - Lee el archivo, procesa los ítems y genera conversiones.
    - Imprime resultados y los guarda en ConvertionResults.txt.
    - Muestra el tiempo total transcurrido.
    """
    start_time = time.perf_counter()

    if len(sys.argv) < 2:
        print("Error: falta el parámetro del archivo de entrada.")
        print("Uso: python convertNumbers.py fileWithData.txt")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        items = parse_items_from_file(file_path)
    except FileNotFoundError:
        print(f"Error: archivo no encontrado: {file_path}")
        sys.exit(1)
    except OSError as exc:
        print(str(exc))
        sys.exit(1)

    elapsed = time.perf_counter() - start_time
    results_text = build_results_text(file_path, items, elapsed)

    print(results_text)
    write_results_to_file(results_text)


if __name__ == "__main__":
    main()
