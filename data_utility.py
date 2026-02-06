import argparse
from pathlib import Path
from typing import List, Tuple, Optional

path_to_parent_dir: Path = Path(__file__).parent

class RecordValidationError(Exception):
    """Исключение для ошибок валидации одной записи."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Утилита обработки данных из текстового файла."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Путь к входному файлу с данными.",
    )
    parser.add_argument(
        "output_file",
        type=Path,
        help="Путь к выходному файлу с отчётом.",
    )
    parser.add_argument(
        "-d",
        "--delimiter",
        default=";",
        help="Символ-разделитель полей в строке (по умолчанию ';').",
    )
    return parser.parse_args()


def validate_and_parse_record(
    raw_line: str,
    line_number: int,
    delimiter: str,
) -> Tuple[bool, Optional[str], Optional[str], Optional[float], List[str]]:
    """
    Проверяет строку и возвращает результат валидации.

    Формат записи: идентификатор;название;числовое_значение
    """
    errors: List[str] = []

    # Убираем символы перевода строки по краям
    line = raw_line.strip()

    if not line:
        errors.append("пустая строка")
        return False, None, None, None, errors

    parts = line.split(delimiter)

    if len(parts) != 3:
        errors.append(
            f"ожидалось 3 поля, получено {len(parts)} (формат: id{delimiter}название{delimiter}значение)"
        )
        return False, None, None, None, errors

    raw_id, raw_name, raw_value = [p.strip() for p in parts]

    # Проверка идентификатора (в проекте ID — строка)
    if not raw_id:
        errors.append('пустое поле "идентификатор"')
        parsed_id = None
    else:
        parsed_id = raw_id

    # Проверка названия
    if not raw_name:
        errors.append('пустое поле "название"')

    # Проверка числового значения
    if not raw_value:
        errors.append('пустое поле "значение"')
        parsed_value = None
    else:
        try:
            parsed_value = float(raw_value.replace(",", "."))
        except ValueError:
            errors.append(f'значение должно быть числом, получено "{raw_value}"')
            parsed_value = None

    is_valid = not errors
    if not is_valid:
        return False, parsed_id, raw_name or None, parsed_value, errors

    return True, parsed_id, raw_name, parsed_value, errors


def process_file(
    input_path: Path,
    delimiter: str,
) -> Tuple[int, int, int, List[float], List[Tuple[int, List[str]]]]:
    """
    Обрабатывает файл построчно.

    Возвращает:
        total_records: общее количество строк (непустых)
        valid_records: количество корректных записей
        invalid_records: количество некорректных записей
        values: список числовых значений корректных записей
        errors: список ошибок (номер строки, список сообщений)
    """
    total_records = 0
    valid_records = 0
    invalid_records = 0
    values: List[float] = []
    errors: List[Tuple[int, List[str]]] = []

    with input_path.open("r", encoding="utf-8") as f:
        for idx, raw_line in enumerate(f, start=1):
            # Считаем только непустые строки как записи
            if not raw_line.strip():
                continue

            total_records += 1

            is_valid, _id, _name, value, record_errors = validate_and_parse_record(
                raw_line, idx, delimiter
            )

            if is_valid and value is not None:
                valid_records += 1
                values.append(value)
            else:
                invalid_records += 1
                if record_errors:
                    errors.append((idx, record_errors))

    return total_records, valid_records, invalid_records, values, errors


def build_report(
    total_records: int,
    valid_records: int,
    invalid_records: int,
    values: List[float],
    errors: List[Tuple[int, List[str]]],
) -> str:
    lines: List[str] = []

    lines.append("ОТЧЁТ ОБРАБОТКИ ДАННЫХ")
    lines.append("=" * 40)
    lines.append("")

    lines.append("Общая статистика:")
    lines.append(f"- Общее количество записей: {total_records}")
    lines.append(f"- Корректных записей: {valid_records}")
    lines.append(f"- Некорректных записей: {invalid_records}")
    lines.append("")

    lines.append("Агрегированная статистика по корректным записям:")
    if values:
        total = sum(values)
        minimum = min(values)
        maximum = max(values)
        average = total / len(values)

        lines.append(f"- Сумма значений: {total}")
        lines.append(f"- Минимальное значение: {minimum}")
        lines.append(f"- Максимальное значение: {maximum}")
        lines.append(f"- Среднее значение: {average}")
    else:
        lines.append("- Нет корректных записей для расчёта статистики.")

    lines.append("")
    lines.append("Ошибки:")
    if not errors:
        lines.append("- Ошибок не обнаружено.")
    else:
        for line_no, msgs in errors:
            for msg in msgs:
                lines.append(f"- Строка {line_no}: {msg}")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    input_path: Path = args.input_file
    output_path: Path = args.output_file
    delimiter: str = args.delimiter

    if not input_path.exists():
        raise FileNotFoundError(f"Входной файл не найден: {input_path}")

    (
        total_records,
        valid_records,
        invalid_records,
        values,
        errors,
    ) = process_file(input_path, delimiter)

    report = build_report(
        total_records=total_records,
        valid_records=valid_records,
        invalid_records=invalid_records,
        values=values,
        errors=errors,
    )

    # Создаём директорию для выходного файла, если нужно
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(report, encoding="utf-8")

    # Также выводим отчёт в консоль
    print(report)


if __name__ == "__main__":
    main()



