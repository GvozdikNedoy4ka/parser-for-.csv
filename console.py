import sys
import os
from typing import Callable, List, Optional
from pathlib import Path

#import keyboard # пытался использовать заместо msvcrt, но  моя реализация работала не коректно
import msvcrt  # для считывания конкретных символов клавиатуры (Windows) 

from data_utility import process_file, build_report, path_to_parent_dir
from sqlite_utility import SQLiteManager

MenuAction = Callable[[], None]

# Исключение для перезапуска меню при смене режима навигации
class MenuRestartException(Exception):
    """Исключение для перезапуска меню с новым режимом навигации"""
    pass

# Структура MenuItem (аналог C# структуры)
class MenuItem:
    def __init__(self, title: str, action: MenuAction):
        self.title = title
        self.action = action

class ConsoleMenu:
    def __init__(self):
        # Храним информацию о последнем проанализированном файле
        self.last_file_path: Optional[Path] = None
        self.last_report: Optional[str] = None
        self.last_delimiter: str = ";"
        
        # Текущий режим навигации: True - числами, False - клавиатурой
        self.use_number_navigation: bool = True

        # SQLite (БД хранится рядом с проектом)
        self.sqlite = SQLiteManager(path_to_parent_dir / "data.db")
        
        # Главное меню
        self.main_menu: List[MenuItem] = [
            MenuItem("Выбрать файл для анализа", self.select_file),
            MenuItem("Изменить разделитель полей", self.change_delimiter),
            MenuItem("Отчёт по последнему файлу", self.show_last_report),
            MenuItem("Пример структуры хранящейся в файле", self.show_file_structure_example),
            MenuItem("Изменить режим навигации", self.change_navigation_mode),
            MenuItem("SQLite", self.sqlite_menu),
        ]
        
        # Цвета для консоли
        self.COLORS = {
            'reset': '\033[0m',
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
        }
    
    #region Print
    def clear_screen(self) -> None:
        """Очистка экрана консоли"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_colored(self, text: str, color: str = 'reset') -> None:
        """Вывод цветного текста"""
        print(f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}")
    
    def pause(self, message: str = "Нажмите любую клавишу для продолжения...") -> None:
        """Пауза с ожиданием нажатия клавиши"""
        print(f"\n{message}")
        msvcrt.getch()
    
    def print_file(self, file_path: str) -> None:  
        """Выводит содержимое текстового файла в консоль."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                print(content)
        except FileNotFoundError:
            print(f"Файл не найден: {file_path}")    
    #endregion
    
    def select_file(self) -> None:
        """Выбор файла для анализа"""
        self.clear_screen()
        self.print_colored("=== Выбор файла для анализа ===", "cyan")
        
        # По умолчанию путь к папке примеров
        default_path = path_to_parent_dir / "examples"
        
        print(f"Введите путь к файлу для анализа (по умолчанию: {default_path}): ", end='')
        user_input = input().strip()
        
        # Если пользователь ввёл что-то
        if user_input:
            # Проверяем, содержит ли ввод разделители директорий
            if '\\' in user_input or '/' in user_input:
                # Если содержит - используем как есть (конкретная директория указана)
                file_path_str = user_input
            else:
                # Если не содержит - это просто имя файла, добавляем default_path
                file_path_str = str(default_path / user_input)
        else:
            # Если пустой ввод - используем default_path
            file_path_str = str(default_path)
        
        file_path = Path(file_path_str)
        
        if not file_path.exists():
            self.print_colored(f"Файл не найден: {file_path}", "red")
            self.pause()
            return
        
        if not file_path.is_file():
            self.print_colored(f"Указанный путь не является файлом: {file_path}", "red")
            self.pause()
            return
        
        # Используем текущий выбранный разделитель
        delimiter = self.last_delimiter
        
        # Обрабатываем файл
        self.print_colored("\nОбработка файла...", "yellow")
        
        try:
            (
                total_records,
                valid_records,
                invalid_records,
                values,
                errors,
            ) = process_file(file_path, delimiter)
            
            # Формируем отчёт
            report = build_report(
                total_records=total_records,
                valid_records=valid_records,
                invalid_records=invalid_records,
                values=values,
                errors=errors,
            )
            
            # Сохраняем информацию о последнем файле
            self.last_file_path = file_path
            self.last_report = report
            self.last_delimiter = delimiter
            
            # Сохраняем отчёт в файл в директории report/
            report_dir = path_to_parent_dir / "report"
            report_dir.mkdir(exist_ok=True)  # Создаём директорию, если её нет
            output_file = report_dir / f"{file_path.stem}_report.txt"
            output_file.write_text(report, encoding="utf-8")
            
            self.clear_screen()
            self.print_colored("=== Результаты анализа ===", "green")
            print(report)
            self.print_colored(f"\nОтчёт также сохранён в файл: {output_file}", "cyan")
            self.pause()
            
        except Exception as e:
            self.print_colored(f"\nОшибка при обработке файла: {e}", "red")
            self.pause()
    
    def show_last_report(self) -> None:
        """Показать отчёт по последнему файлу"""
        self.clear_screen()
        
        # Если не было запуска первого анализа
        if self.last_report is None or self.last_file_path is None:
            self.print_colored("=== Отчёт по последнему файлу ===", "cyan")
            self.print_colored("\nФайл ещё не был проанализирован.", "red")
            self.print_colored("Сначала выберите файл для анализа.", "yellow")
            self.pause()
            return
        
        self.print_colored("=== Отчёт по последнему файлу ===", "cyan")
        self.print_colored(f"Файл: {self.last_file_path}", "yellow")
        self.print_colored(f"Разделитель: '{self.last_delimiter}'", "yellow")
        print()
        print(self.last_report)
        self.pause()
    
    def show_file_structure_example(self) -> None:
        """Показать пример структуры файла"""
        self.clear_screen()
        self.print_colored("=== Пример структуры хранящейся в файле ===", "cyan")
        print()
        
        self.print_colored("Формат записи:", "yellow")
        print("  идентификатор;название;значение")
        print()
        
        self.print_colored("Описание полей:", "yellow")
        print("  • идентификатор — строка")
        print("  • название — непустая строка")
        print("  • значение — число (допускается запятая или точка как разделитель)")
        print()
        
        
        self.print_colored("Пример корректных записей:", "green")       
        self.print_file(path_to_parent_dir / "examples" / "example_correct.txt")
        
        self.print_colored("Пример некорректных записей:", "red")
        self.print_file(path_to_parent_dir / "examples" / "example_with_errors.txt")
        
        self.print_colored("Примечания:", "yellow")
        print("  • Пустые строки игнорируются")
        print("  • Разделитель по умолчанию: точка с запятой (;)")
        print("  • Разделитель можно изменить в меню программы")
        print()
        

        self.pause()
    
    def change_delimiter(self) -> None:
        """Изменить разделитель полей"""
        self.clear_screen()
        self.print_colored("=== Изменение разделителя полей ===", "cyan")
        print()
        
        readable_delimiter = (
            "\\t" if self.last_delimiter == "\t"
            else "пробел" if self.last_delimiter == " "
            else self.last_delimiter
        )
        self.print_colored(f"Текущий разделитель: '{readable_delimiter}'", "yellow")
        print()
        
        self.print_colored("Выберите новый разделитель:", "yellow")
        print("1. Точка с запятой (;)")
        print("2. Запятая (,)")
        print("3. Табуляция (\\t)")
        print("4. Пробел")
        print("5. Ввести произвольный символ")
        print("0. Отмена")
        print()
        
        try:
            choice = input("Ваш выбор: ").strip()
            
            if choice == "0":
                self.print_colored("\nИзменения отменены", "yellow")
                self.pause()
                return
            elif choice == "1":
                self.last_delimiter = ";"
            elif choice == "2":
                self.last_delimiter = ","
            elif choice == "3":
                self.last_delimiter = "\t"
            elif choice == "4":
                self.last_delimiter = " "
            elif choice == "5":
                custom = input("Введите разделитель (один или несколько символов): ")
                if not custom:
                    self.print_colored("\nОшибка: разделитель не может быть пустым", "red")
                    self.pause()
                    return
                self.last_delimiter = custom
            else:
                self.print_colored("\nНеверный выбор, изменения не выполнены", "red")
                self.pause()
                return
            
            new_readable = (
                "\\t" if self.last_delimiter == "\t"
                else "пробел" if self.last_delimiter == " "
                else self.last_delimiter
            )
            self.print_colored(f"\nНовый разделитель установлен: '{new_readable}'", "green")
            self.pause()
        except (KeyboardInterrupt, EOFError):
            self.print_colored("\nИзменения отменены", "yellow")
            self.pause()
    
    def change_navigation_mode(self) -> None:
        """Изменение режима навигации"""
        self.clear_screen()
        self.print_colored("=== Изменение режима навигации ===", "cyan")
        print()
        
        current_mode = "числами" if self.use_number_navigation else "клавиатурой"
        self.print_colored(f"Текущий режим: Навигация {current_mode}", "yellow")
        print()
        
        self.print_colored("Выберите режим навигации:", "yellow")
        print("1. Навигация числами")
        print("2. Навигация клавиатурой")
        print("ESC. Без изменений")
        print()
        
        #region Смена режима ввода
        try:
            choice = input("Ваш выбор: ").strip()
            
            if choice == "1":
                self.use_number_navigation = True
                self.print_colored("\nРежим навигации изменён на: Навигация числами", "green")
                self.pause()
                # Выбрасываем исключение для перезапуска меню с новым режимом
                raise MenuRestartException()
            elif choice == "2":
                self.use_number_navigation = False
                self.print_colored("\nРежим навигации изменён на: Навигация клавиатурой", "green")
                self.pause()
                # Выбрасываем исключение для перезапуска меню с новым режимом
                raise MenuRestartException()
            else:
                # Любой другой ввод (включая пустой или ESC через Enter) - без изменений
                self.print_colored("\nИзменения отменены", "yellow")
                self.pause()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C или EOF - без изменений
            self.print_colored("\nИзменения отменены", "yellow")
            self.pause()

    #region SQLite, Работа с таблицей (records)
    def sqlite_menu(self) -> None:
        """
        Меню работы со структурой таблицы SQLite.

        Пункты:
          1) Добавить поле
          2) Удалить поле по названию (с подтверждением)
          3) Показать поля таблицы
          4) Вернуться в главное меню (return)
        """
        items: List[MenuItem] = [
            MenuItem("Добавить поле", self._sqlite_add_field),
            MenuItem("Удалить конкретное поле по названию", self._sqlite_drop_field),
            MenuItem("Показать какие поля есть в таблице", self._sqlite_list_fields),
            MenuItem("Работа с данными (records)", self.sqlite_records_menu),
        ]

        while True:
            self.clear_screen()
            self.print_colored("=== SQLite ===", "cyan")
            self.print_colored("Таблица: records", "yellow")
            print()

            for i, item in enumerate(items, start=1):
                print(f"{i}. {item.title}")
            print("0. Вернуться в главное меню")
            print()

            choice = input("Ваш выбор: ").strip()
            if choice == "0":
                return

            try:
                n = int(choice)
            except ValueError:
                self.print_colored("Ошибка: введите корректное число.", "red")
                self.pause()
                continue

            if 1 <= n <= len(items):
                items[n - 1].action()
                continue

            self.print_colored(f"Неверный выбор. Введите 0-{len(items)}.", "red")
            self.pause()

    def sqlite_records_menu(self) -> None:
        """
        Подменю для работы с данными таблицы records.
        """
        items: List[MenuItem] = [
            MenuItem("Добавить запись (id, name, value)", self._sqlite_add_record),
            MenuItem("Удалить записи по ID", self._sqlite_delete_records_by_id),
            MenuItem("Импортировать записи из текстового файла", self._sqlite_import_records_from_file),
            MenuItem("Показать отчёт по данным из БД", self._sqlite_show_db_report),
            MenuItem("Показать записи (первые N)", self._sqlite_show_records),
            MenuItem("Очистить таблицу records", self._sqlite_clear_records),
        ]

        while True:
            self.clear_screen()
            self.print_colored("=== SQLite: Данные (records) ===", "cyan")
            self.print_colored(f"Записей в таблице: {self.sqlite.count_records()}", "yellow")
            print()

            for i, item in enumerate(items, start=1):
                print(f"{i}. {item.title}")
            print("0. Назад (SQLite)")
            print()

            choice = input("Ваш выбор: ").strip()
            if choice == "0":
                return

            try:
                n = int(choice)
            except ValueError:
                self.print_colored("Ошибка: введите корректное число.", "red")
                self.pause()
                continue

            if 1 <= n <= len(items):
                items[n - 1].action()
                continue

            self.print_colored(f"Неверный выбор. Введите 0-{len(items)}.", "red")
            self.pause()

    def _sqlite_add_field(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Добавить поле ===", "cyan")
        print()
        name = input("Имя поля: ").strip()
        col_type = input("Тип данных (например TEXT, INTEGER, REAL, BLOB, VARCHAR): ").strip()
        raw_size = input("Размер (если нужно, иначе Enter): ").strip()

        size = None
        if raw_size:
            try:
                size = int(raw_size)
                if size <= 0:
                    raise ValueError
            except ValueError:
                self.print_colored("Ошибка: размер должен быть положительным целым числом.", "red")
                self.pause()
                return

        try:
            self.sqlite.add_column(name=name, col_type=col_type, size=size)
            self.print_colored("Поле добавлено успешно.", "green")
        except Exception as e:
            self.print_colored(f"Ошибка при добавлении поля: {e}", "red")
        self.pause()

    def _sqlite_drop_field(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Удалить поле ===", "cyan")
        print()
        name = input("Введите точное название поля для удаления: ").strip()
        if not name:
            self.print_colored("Имя поля не может быть пустым.", "red")
            self.pause()
            return

        if name.lower() == "id":
            self.print_colored('Поле "id" удалить нельзя.', "red")
            self.pause()
            return

        confirm = input(f'Вы уверены, что хотите удалить поле "{name}"? (да/нет): ').strip().lower()
        if confirm not in ("да", "д", "yes", "y"):
            self.print_colored("Удаление отменено.", "yellow")
            self.pause()
            return

        try:
            self.sqlite.drop_column(name=name)
            self.print_colored("Поле удалено успешно.", "green")
        except Exception as e:
            self.print_colored(f"Ошибка при удалении поля: {e}", "red")
        self.pause()

    def _sqlite_list_fields(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Поля таблицы records ===", "cyan")
        print()
        try:
            cols = self.sqlite.list_columns()
            if not cols:
                self.print_colored("Таблица пуста или не найдена.", "red")
            else:
                for c in cols:
                    type_part = f" ({c.col_type})" if c.col_type else ""
                    print(f"- {c.name}{type_part}")
        except Exception as e:
            self.print_colored(f"Ошибка: {e}", "red")
        self.pause()
    
    #endregion 
    
    #region SQLite, Работа с данными (records)
    def _sqlite_add_record(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Добавить запись ===", "cyan")
        print()
        record_id = input("ID (строка): ").strip()
        name = input("Название: ").strip()
        raw_value = input("Значение (число): ").strip()

        try:
            value = float(raw_value.replace(",", "."))
        except ValueError:
            self.print_colored("Ошибка: значение должно быть числом.", "red")
            self.pause()
            return

        try:
            self.sqlite.insert_record(record_id=record_id, name=name, value=value)
            self.print_colored("Запись добавлена.", "green")
        except Exception as e:
            self.print_colored(f"Ошибка при добавлении записи: {e}", "red")
        self.pause()

    def _sqlite_import_records_from_file(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Импорт из файла ===", "cyan")
        print()
        default_path = path_to_parent_dir / "examples"
        print(f"Введите путь к файлу (по умолчанию: {default_path}): ", end="")
        user_input = input().strip()

        if user_input:
            if "\\" in user_input or "/" in user_input:
                file_path_str = user_input
            else:
                file_path_str = str(default_path / user_input)
        else:
            file_path_str = str(default_path)

        file_path = Path(file_path_str)
        if not file_path.exists() or not file_path.is_file():
            self.print_colored(f"Файл не найден или это не файл: {file_path}", "red")
            self.pause()
            return

        delimiter = self.last_delimiter
        self.print_colored(f"Используется разделитель: '{delimiter}'", "yellow")
        print()

        try:
            total_records, valid_records, invalid_records, values, errors = (
                self.sqlite.import_from_text_file(file_path=file_path, delimiter=delimiter)
            )
            report = build_report(
                total_records=total_records,
                valid_records=valid_records,
                invalid_records=invalid_records,
                values=values,
                errors=errors,
            )
            self.clear_screen()
            self.print_colored("=== Результат импорта в SQLite ===", "green")
            print(report)
        except Exception as e:
            self.print_colored(f"Ошибка импорта: {e}", "red")

        self.pause()

    def _sqlite_show_db_report(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Отчёт по данным из БД ===", "cyan")
        print()
        try:
            report = self.sqlite.build_report_from_db(delimiter=self.last_delimiter)
            print(report)

            report_dir = path_to_parent_dir / "report"
            report_dir.mkdir(exist_ok=True)
            output_file = report_dir / "sqlite_records_report.txt"
            output_file.write_text(report, encoding="utf-8")
            self.print_colored(f"\nОтчёт сохранён в файл: {output_file}", "cyan")
        except Exception as e:
            self.print_colored(f"Ошибка: {e}", "red")

        self.pause()

    def _sqlite_show_records(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Показать записи ===", "cyan")
        print()
        raw_n = input("Сколько записей показать? (по умолчанию 20): ").strip()
        n = 20
        if raw_n:
            try:
                n = int(raw_n)
                if n <= 0:
                    raise ValueError
            except ValueError:
                self.print_colored("Ошибка: введите положительное целое число.", "red")
                self.pause()
                return

        try:
            rows = self.sqlite.fetch_records(limit=n)
            if not rows:
                self.print_colored("Записей нет.", "yellow")
            else:
                for i, r in enumerate(rows, start=1):
                    print(f"{i}. id={r['id']}; name={r['name']}; value={r['value']}")
        except Exception as e:
            self.print_colored(f"Ошибка: {e}", "red")

        self.pause()

    def _sqlite_clear_records(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Очистить таблицу records ===", "cyan")
        print()
        confirm = input("Вы уверены? Будут удалены ВСЕ записи. (да/нет): ").strip().lower()
        if confirm not in ("да", "д", "yes", "y"):
            self.print_colored("Очистка отменена.", "yellow")
            self.pause()
            return

        try:
            self.sqlite.clear_records()
            self.print_colored("Таблица очищена.", "green")
        except Exception as e:
            self.print_colored(f"Ошибка: {e}", "red")

        self.pause()

    def _sqlite_delete_records_by_id(self) -> None:
        self.clear_screen()
        self.print_colored("=== SQLite: Удалить записи по ID ===", "cyan")
        print()
        record_id = input("Введите ID (строка): ").strip()
        if not record_id:
            self.print_colored("ID не может быть пустым.", "red")
            self.pause()
            return

        confirm = input(
            f'Вы уверены, что хотите удалить ВСЕ записи с id="{record_id}"? (да/нет): '
        ).strip().lower()
        if confirm not in ("да", "д", "yes", "y"):
            self.print_colored("Удаление отменено.", "yellow")
            self.pause()
            return

        try:
            deleted = self.sqlite.delete_records_by_id(record_id=record_id)
            if deleted == 0:
                self.print_colored("Записей с таким ID не найдено.", "yellow")
            else:
                self.print_colored(f"Удалено записей: {deleted}", "green")
        except Exception as e:
            self.print_colored(f"Ошибка: {e}", "red")

        self.pause()
    #endregion
    
    #region Навигация
    def run_with_number_navigation(self) -> None:
        """Основной цикл с навигацией по номерам"""
        while True:
            self.clear_screen()
            self.print_colored("=== Утилита обработки данных ===", "cyan")
            self.print_colored("=" * 40, "blue")
            self.print_colored("Введите номер пункта меню для выбора.", "yellow")
            self.print_colored("=" * 40, "blue")
            
            # Выводим меню с номерами
            for i, item in enumerate(self.main_menu, 1):
                print(f"{i}. {item.title}")
            
            # Вывод пункта "Завершить работу" с номером 0
            print("0. Завершить работу программы")           
            self.print_colored("=" * 40, "blue")       
            # Показываем информацию о последнем файле, если есть
            if self.last_file_path:
                self.print_colored(f"Последний файл: {self.last_file_path.name}","magenta")
            else:
                self.print_colored("Последний файл: не выбран","magenta")
            
            # Запрашиваем ввод номера
            print()
            try:
                choice = input("Выберите пункт меню: ").strip()
                
                if choice == "0":
                    self.clear_screen()
                    self.print_colored("Завершение программы...", "green")
                    sys.exit(0)
                
                # Преобразуем ввод в число
                choice_num = int(choice)
                
                # Проверяем диапазон
                if 1 <= choice_num <= len(self.main_menu):
                    # Вызываем выбранное действие (индекс на 1 меньше номера)
                    self.main_menu[choice_num - 1].action()
                else:
                    self.print_colored(
                        f"Неверный номер. Введите число от 0 до {len(self.main_menu)}", "red" )
                    self.pause("Нажмите любую клавишу для продолжения...")
                    
            except MenuRestartException:
                # Перезапускаем меню с новым режимом навигации
                return
            except ValueError:
                self.print_colored("Ошибка: введите корректное число", "red")
                self.pause("Нажмите любую клавишу для продолжения...")
            except KeyboardInterrupt:
                self.clear_screen()
                self.print_colored("Завершение программы...", "green")
                sys.exit(0)
       
    def run_with_keyboard_navigation(self) -> None:
        """Основной цикл с навигацией стрелками"""
        current_selection = 0
        
        while True:
            self.clear_screen()
            self.print_colored("=== Утилита обработки данных ===", "cyan")
            self.print_colored("=" * 40, "blue")
            self.print_colored("Используйте ↑/↓ для навигации, Enter для выбора.", "yellow")
            self.print_colored("=" * 40, "blue")
            
            # Выводим меню с выделением текущего пункта
            for i, item in enumerate(self.main_menu):
                if i == current_selection:
                    self.print_colored(f"> {item.title}", "green")
                else:
                    print(f"  {item.title}")
            
            # Вывод пункта "Завершить работу"
            if current_selection == len(self.main_menu):
                self.print_colored("> Завершить работу программы", "red")
            else:
                print("  Завершить работу программы")
            
            self.print_colored("=" * 40, "blue")
            
            # Показываем информацию о последнем файле, если есть
            if self.last_file_path:
                self.print_colored( f"Последний файл: {self.last_file_path.name}", "magenta")
            else:
                self.print_colored( "Последний файл: не выбран", "magenta" )
            
            # Обработка нажатий клавиш
            key = msvcrt.getch()
            
            if key == b'\xe0':  # Специальная клавиша (стрелки)
                key = msvcrt.getch()
                if key == b'H':  # Стрелка вверх
                    current_selection = (current_selection - 1) % (len(self.main_menu) + 1)
                elif key == b'P':  # Стрелка вниз
                    current_selection = (current_selection + 1) % (len(self.main_menu) + 1)
            elif key == b'\r':  # Enter
                if current_selection == len(self.main_menu):
                    self.clear_screen()
                    self.print_colored("Завершение программы...", "green")
                    sys.exit(0)
                else:
                    try:
                        # Вызываем выбранное действие
                        self.main_menu[current_selection].action()
                    except MenuRestartException:
                        # Перезапускаем меню с новым режимом навигации
                        return
            elif key == b'\x1b':  # Escape
                self.clear_screen()
                self.print_colored("Завершение программы...", "green")
                sys.exit(0)
    
    #endregion
    
    def run(self) -> None:
        """Запуск меню с текущим режимом навигации"""
        if self.use_number_navigation:
            self.run_with_number_navigation()
        else:
            self.run_with_keyboard_navigation()

def main():
    """Точка входа программы"""
    try:
        menu = ConsoleMenu()    
        while True:         # используется бесконечный цикл, из-за особенности смены способа навигации  
            menu.run()
                    
    except KeyboardInterrupt:
        print("\n\nПрограмма завершена пользователем")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()
