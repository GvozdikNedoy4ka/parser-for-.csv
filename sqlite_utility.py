import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ColumnInfo:
    cid: int
    name: str
    col_type: str
    notnull: int
    dflt_value: Optional[str]
    pk: int


class SQLiteManager:
    """
    Мини-обёртка над SQLite для проекта.

    Таблица `records` создаётся с базовой структурой:
      - id TEXT
      - name TEXT
      - value REAL
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_parent_dir()
        self.ensure_schema()

    def _ensure_parent_dir(self) -> None:
        if self.db_path.parent and not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        """
        Гарантирует наличие таблицы `records` с базовой структурой.

        Если таблица существует, но структура отличается (например, добавлялись/удалялись колонки),
        таблица будет удалена и создана заново с 3 базовыми полями:
          id TEXT, name TEXT, value REAL
        """
        expected = [("id", "TEXT"), ("name", "TEXT"), ("value", "REAL")]

        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name='records'
                """
            ).fetchone()

            if existing:
                cols = conn.execute("PRAGMA table_info(records)").fetchall()
                current = [(str(r["name"]), str(r["type"]).upper()) for r in cols]

                # Если структура НЕ совпадает — сбрасываем таблицу (данные будут потеряны)
                if current != expected:
                    conn.execute("DROP TABLE IF EXISTS records")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT,
                    name TEXT,
                    value REAL
                )
                """
            )

    def insert_record(
        self,
        record_id: str,
        name: str,
        value: float,
        table: str = "records",
    ) -> None:
        record_id = (record_id or "").strip()
        name = (name or "").strip()

        if not record_id:
            raise ValueError("ID не может быть пустым")
        if not name:
            raise ValueError("Название не может быть пустым")

        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO {table} (id, name, value) VALUES (?, ?, ?)",
                (record_id, name, float(value)),
            )

    def fetch_records(
        self,
        table: str = "records",
        limit: Optional[int] = None,
        offset: int = 0,
        order_by_rowid: bool = True,
    ) -> List[sqlite3.Row]:
        sql = f"SELECT * FROM {table}"
        params: List[object] = []

        if order_by_rowid:
            sql += " ORDER BY rowid"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
            if offset:
                sql += " OFFSET ?"
                params.append(int(offset))
        elif offset:
            # SQLite требует LIMIT при OFFSET
            sql += " LIMIT -1 OFFSET ?"
            params.append(int(offset))

        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def count_records(self, table: str = "records") -> int:
        with self.connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
            return int(row["cnt"]) if row is not None else 0

    def clear_records(self, table: str = "records") -> None:
        with self.connect() as conn:
            conn.execute(f"DELETE FROM {table}")

    def delete_records_by_id(self, record_id: str, table: str = "records") -> int:
        record_id = (record_id or "").strip()
        if not record_id:
            raise ValueError("ID не может быть пустым")

        with self.connect() as conn:
            cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
            # rowcount для sqlite3 корректен для DELETE
            return int(cur.rowcount or 0)

    def build_report_from_db(self, delimiter: str = ";", table: str = "records") -> str:
        """
        Читает записи из SQLite и строит отчёт через текущие функции data_utility.py.
        """
        # Локальный импорт, чтобы не создавать жёсткую связность на уровне модуля
        from data_utility import build_report, validate_and_parse_record

        rows = self.fetch_records(table=table)

        total_records = 0
        valid_records = 0
        invalid_records = 0
        values: List[float] = []
        errors: List[Tuple[int, List[str]]] = []

        for idx, row in enumerate(rows, start=1):
            line = row_to_data_utility_line(row, delimiter=delimiter)
            if not line.strip():
                continue

            total_records += 1
            is_valid, _id, _name, value, record_errors = validate_and_parse_record(
                line, idx, delimiter
            )

            if is_valid and value is not None:
                valid_records += 1
                values.append(value)
            else:
                invalid_records += 1
                if record_errors:
                    errors.append((idx, record_errors))

        return build_report(
            total_records=total_records,
            valid_records=valid_records,
            invalid_records=invalid_records,
            values=values,
            errors=errors,
        )

    def import_from_text_file(
        self,
        file_path: Path,
        delimiter: str = ";",
        table: str = "records",
    ) -> Tuple[int, int, int, List[float], List[Tuple[int, List[str]]]]:
        """
        Импортирует записи из текстового файла в SQLite.

        Возвращает такую же структуру, как data_utility.process_file:
          total_records, valid_records, invalid_records, values, errors

        В SQLite вставляются только корректные записи.
        """
        from data_utility import validate_and_parse_record

        total_records = 0
        valid_records = 0
        invalid_records = 0
        values: List[float] = []
        errors: List[Tuple[int, List[str]]] = []

        with file_path.open("r", encoding="utf-8") as f, self.connect() as conn:
            for idx, raw_line in enumerate(f, start=1):
                if not raw_line.strip():
                    continue

                total_records += 1
                is_valid, parsed_id, parsed_name, parsed_value, record_errors = (
                    validate_and_parse_record(raw_line, idx, delimiter)
                )

                if is_valid and parsed_id is not None and parsed_name is not None and parsed_value is not None:
                    valid_records += 1
                    values.append(parsed_value)
                    conn.execute(
                        f"INSERT INTO {table} (id, name, value) VALUES (?, ?, ?)",
                        (parsed_id, parsed_name, float(parsed_value)),
                    )
                else:
                    invalid_records += 1
                    if record_errors:
                        errors.append((idx, record_errors))

        return total_records, valid_records, invalid_records, values, errors

    def list_columns(self, table: str = "records") -> List[ColumnInfo]:
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        cols: List[ColumnInfo] = []
        for r in rows:
            cols.append(
                ColumnInfo(
                    cid=int(r["cid"]),
                    name=str(r["name"]),
                    col_type=str(r["type"]),
                    notnull=int(r["notnull"]),
                    dflt_value=r["dflt_value"],
                    pk=int(r["pk"]),
                )
            )
        return cols

    def add_column(
        self,
        name: str,
        col_type: str,
        size: Optional[int] = None,
        table: str = "records",
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Имя поля не может быть пустым")

        col_type = (col_type or "").strip().upper()
        if not col_type:
            raise ValueError("Тип данных не может быть пустым")

        # SQLite игнорирует длины для большинства типов, но синтаксис допустим (VARCHAR(50)).
        type_sql = f"{col_type}({int(size)})" if size is not None else col_type

        with self.connect() as conn:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN "{name}" {type_sql}')

    def drop_column(self, name: str, table: str = "records") -> None:
        name = name.strip()
        if not name:
            raise ValueError("Имя поля не может быть пустым")

        if name.lower() == "id":
            raise ValueError('Нельзя удалить поле "id"')

        # 1) Пробуем нативный DROP COLUMN (SQLite 3.35+)
        try:
            with self.connect() as conn:
                conn.execute(f'ALTER TABLE {table} DROP COLUMN "{name}"')
            return
        except sqlite3.OperationalError:
            # 2) Фоллбек: перестроение таблицы
            self._drop_column_by_rebuild(table=table, column_to_drop=name)

    def _drop_column_by_rebuild(self, table: str, column_to_drop: str) -> None:
        if column_to_drop.lower() == "id":
            raise ValueError('Нельзя удалить поле "id"')

        cols = self.list_columns(table)
        existing_names = [c.name for c in cols]

        if column_to_drop not in existing_names:
            raise ValueError(f'Поле "{column_to_drop}" не найдено в таблице {table}')

        remaining = [c for c in cols if c.name != column_to_drop]
        if not remaining:
            raise ValueError("Нельзя удалить последнее поле таблицы")

        # Собираем определения колонок (упрощённо: имя + тип; pk/notnull/default в этом проекте не критичны)
        def col_def(c: ColumnInfo) -> str:
            t = c.col_type.strip() or ""
            if t:
                return f'"{c.name}" {t}'
            return f'"{c.name}"'

        tmp_table = f"{table}__tmp_rebuild"

        create_sql = f'CREATE TABLE "{tmp_table}" ({", ".join(col_def(c) for c in remaining)})'
        col_list = ", ".join(f'"{c.name}"' for c in remaining)
        copy_sql = f'INSERT INTO "{tmp_table}" ({col_list}) SELECT {col_list} FROM "{table}"'

        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN")
            try:
                cur.execute(create_sql)
                cur.execute(copy_sql)
                cur.execute(f'DROP TABLE "{table}"')
                cur.execute(f'ALTER TABLE "{tmp_table}" RENAME TO "{table}"')
                conn.commit()
            except Exception:
                conn.rollback()
                raise


def row_to_data_utility_line(row: sqlite3.Row, delimiter: str = ";") -> str:
    """
    Преобразует запись из БД в строку формата, который понимает data_utility.validate_and_parse_record():
        id<delimiter>name<delimiter>value
    """
    _id = "" if row["id"] is None else str(row["id"])
    name = "" if row["name"] is None else str(row["name"])
    value = "" if row["value"] is None else str(row["value"])
    return f"{_id}{delimiter}{name}{delimiter}{value}"


