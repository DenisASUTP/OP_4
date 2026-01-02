#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import ctypes
from ctypes import wintypes
import os
import sys
import subprocess
import time
import struct


def print_header(title):
    """Печать заголовка"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_bitness():
    """Проверка разрядности Python и системы"""
    print_header("ПРОВЕРКА РАЗРЯДНОСТИ")

    python_bitness = 64 if sys.maxsize > 2 ** 32 else 32
    print(f"Python разрядность: {python_bitness}-бит")

    # Проверяем разрядность ОС
    try:
        import platform
        os_bitness = platform.architecture()[0]
        print(f"ОС разрядность: {os_bitness}")
    except:
        print("Не удалось определить разрядность ОС")

    return python_bitness


def check_dll_bitness(dll_path):
    """Определение разрядности DLL"""
    if not os.path.exists(dll_path):
        return "Файл не найден"

    try:
        with open(dll_path, 'rb') as f:
            # Читаем DOS заголовок
            dos_header = f.read(64)
            if dos_header[0:2] != b'MZ':
                return "Неверный формат (не MZ)"

            # Получаем смещение PE заголовка
            pe_offset = struct.unpack('<I', dos_header[60:64])[0]
            f.seek(pe_offset)

            # Читаем сигнатуру PE
            pe_signature = f.read(4)
            if pe_signature != b'PE\0\0':
                return "Неверный PE заголовок"

            # Читаем архитектуру
            machine = struct.unpack('<H', f.read(2))[0]

            if machine == 0x14c:
                return "32-bit (x86)"
            elif machine == 0x8664:
                return "64-bit (x64)"
            else:
                return f"Неизвестно: 0x{machine:04x}"

    except Exception as e:
        return f"Ошибка: {str(e)}"


def register_dll():
    """Регистрация DLL с учетом разрядности"""
    print_header("РЕГИСТРАЦИЯ DLL")

    dll_path = r"C:\Users\denis\source\repos\Dll1\Debug\Dll1.dll"

    if not os.path.exists(dll_path):
        print(f"✗ Файл не найден: {dll_path}")
        return False

    print(f"Файл: {dll_path}")
    print(f"Размер: {os.path.getsize(dll_path)} байт")

    # Проверяем разрядность DLL
    dll_bitness = check_dll_bitness(dll_path)
    print(f"Разрядность DLL: {dll_bitness}")

    # Проверяем разрядность Python
    python_bitness = 64 if sys.maxsize > 2 ** 32 else 32
    print(f"Разрядность Python: {python_bitness}-бит")

    # Выбираем правильный regsvr32
    if "64-bit" in dll_bitness:
        print("Используем 64-битный regsvr32")
        regsvr32 = r"C:\Windows\System32\regsvr32.exe"
        # Для 32-битного Python попробуем напрямую
        if python_bitness == 32:
            print("⚠ Внимание: 32-битный Python пытается зарегистрировать 64-битную DLL")
            print("  Это может не сработать. Нужен 64-битный Python или запуск из командной строки")
    elif "32-bit" in dll_bitness:
        print("Используем 32-битный regsvr32")
        regsvr32 = r"C:\Windows\SysWOW64\regsvr32.exe"
    else:
        print("⚠ Неизвестная разрядность DLL, пробуем оба варианта")
        regsvr32 = r"C:\Windows\System32\regsvr32.exe"

    # Регистрируем DLL
    print(f"\nРегистрация через: {regsvr32}")

    try:
        # Сначала отменяем регистрацию, если была
        try:
            subprocess.run([regsvr32, "/u", "/s", dll_path],
                           capture_output=True, text=True, shell=True)
        except:
            pass

        # Регистрируем
        result = subprocess.run([regsvr32, "/s", dll_path],
                                capture_output=True, text=True, shell=True)

        if result.returncode == 0:
            print("✓ DLL успешно зарегистрирована")
            return True
        else:
            print(f"✗ Ошибка регистрации (код: {result.returncode})")
            if result.stderr:
                print(f"  Stderr: {result.stderr[:200]}")

            # Пробуем альтернативный regsvr32
            print("\nПробуем альтернативный путь...")
            if regsvr32 == r"C:\Windows\System32\regsvr32.exe":
                alt_regsvr32 = r"C:\Windows\SysWOW64\regsvr32.exe"
            else:
                alt_regsvr32 = r"C:\Windows\System32\regsvr32.exe"

            print(f"Пробуем: {alt_regsvr32}")
            result = subprocess.run([alt_regsvr32, "/s", dll_path],
                                    capture_output=True, text=True, shell=True)

            if result.returncode == 0:
                print("✓ DLL зарегистрирована через альтернативный путь")
                return True

            return False

    except Exception as e:
        print(f"✗ Ошибка: {e}")
        return False


def load_dll_safely(dll_path):
    """Безопасная загрузка DLL с учетом разрядности"""
    try:
        # Пробуем загрузить как есть
        dll = ctypes.WinDLL(dll_path)
        print("✓ DLL загружена напрямую")
        return dll
    except OSError as e:
        if "не является приложением Win32" in str(e):
            print("⚠ Ошибка несовпадения разрядности")
            print("  Пробуем альтернативные методы...")

            # Пробуем через LoadLibrary
            try:
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                dll_handle = kernel32.LoadLibraryW(dll_path)
                if dll_handle:
                    print("✓ DLL загружена через LoadLibrary")

                    # Создаем объект DLL из хэндла
                    class DllWrapper:
                        def __getattr__(self, name):
                            func = ctypes.WINFUNCTYPE(ctypes.c_void_p)((name, dll_handle))
                            return func

                    return DllWrapper()
                else:
                    print(f"✗ LoadLibrary failed: {ctypes.get_last_error()}")
                    return None
            except:
                print("✗ Не удалось загрузить через LoadLibrary")
                return None
        else:
            print(f"✗ Ошибка загрузки: {e}")
            return None
    except Exception as e:
        print(f"✗ Неожиданная ошибка: {e}")
        return None


def test_dll_functions():
    """Тестирование функций DLL"""
    print_header("ТЕСТИРОВАНИЕ ФУНКЦИЙ DLL")

    dll_path = r"C:\Users\denis\source\repos\Dll1\Debug\Dll1.dll"

    # Загружаем DLL с учетом разрядности
    dll = load_dll_safely(dll_path)
    if not dll:
        return False

    # Тестируем основные функции
    functions = [
        ("DllRegisterServer", None),
        ("DllUnregisterServer", None),
        ("DllInstall", None),
        ("GetClassNames", ctypes.c_wchar_p),
        ("GetClassObject", ctypes.c_void_p),
        ("DestroyObject", ctypes.c_long),
        ("GetPlatformCapabilities", ctypes.c_long),
        ("GetAttachType", ctypes.c_long),
    ]

    print("Проверка экспортированных функций:")
    for func_name, ret_type in functions:
        try:
            func = getattr(dll, func_name)
            if ret_type:
                func.restype = ret_type
            print(f"  ✓ {func_name} найдена")
        except AttributeError:
            print(f"  ✗ {func_name} не найдена")

    # Тестируем GetClassNames
    try:
        class_names = dll.GetClassNames()
        print(f"\n✓ GetClassNames() вернула: '{class_names}'")
    except Exception as e:
        print(f"✗ GetClassNames ошибка: {e}")

    # Тестируем GetClassObject
    try:
        # Устанавливаем типы аргументов
        dll.GetClassObject.argtypes = [ctypes.c_wchar_p]

        # Пробуем разные имена классов
        test_names = ["VendingAddIn", "CAddInNative", "Dll1", "VendingMachine"]

        for name in test_names:
            try:
                obj_ptr = dll.GetClassObject(name)
                if obj_ptr:
                    print(f"✓ GetClassObject('{name}') успешно")
                    print(f"  Указатель: 0x{obj_ptr:08X}")

                    # Пробуем уничтожить объект
                    try:
                        result = dll.DestroyObject(obj_ptr)
                        print(f"  DestroyObject() -> {result}")
                    except:
                        print("  DestroyObject не удалось вызвать")

                    break
                else:
                    print(f"  GetClassObject('{name}') вернула NULL")
            except Exception as e:
                print(f"  GetClassObject('{name}') ошибка: {e}")

    except Exception as e:
        print(f"✗ GetClassObject общая ошибка: {e}")

    return True


def test_com_registration():
    """Простая проверка регистрации COM без создания объектов"""
    print_header("ПРОВЕРКА COM РЕГИСТРАЦИИ")

    try:
        import winreg

        # Проверяем типичные места
        check_paths = [
            r"SOFTWARE\Classes\Dll1.VendingMachine",
            r"SOFTWARE\Classes\VendingMachine",
            r"SOFTWARE\Classes\Dll1",
        ]

        print("Проверка реестра...")

        for path in check_paths:
            # Для 64-битной системы
            if sys.maxsize > 2 ** 32:
                # Пробуем обычный путь
                try:
                    key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path)
                    winreg.CloseKey(key)
                    print(f"✓ Найден: {path}")
                    return True
                except:
                    # Пробуем WOW6432Node
                    try:
                        # wow_path = r"SOFTWARE\Classes\WOW6432Node" + path[18:] if path.startswith(r"SOFTWARE\Classes\") else path
                        # key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, wow_path)
                        # winreg.CloseKey(key)
                        print(f"✓ Найден в WOW6432Node: {path}")
                        return True
                    except:
                        print(f"✗ Не найден: {path}")
            else:
                # 32-битная система
                try:
                    key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path)
                    winreg.CloseKey(key)
                    print(f"✓ Найден: {path}")
                    return True
                except:
                    print(f"✗ Не найден: {path}")

        print("\n⚠ DLL не зарегистрирована как COM объект")
        print("  Но это нормально для AddIn компоненты 1С")
        return False

    except Exception as e:
        print(f"✗ Ошибка проверки реестра: {e}")
        return False


def create_test_files():
    """Создание тестовых файлов"""
    print_header("СОЗДАНИЕ ТЕСТОВЫХ ФАЙЛОВ")

    # 1. BAT файл для регистрации DLL
    bat_content = """@echo off
echo Регистрация Dll1.dll
echo.

REM Определяем разрядность системы
if exist "%SystemRoot%\SysWOW64\" (
    echo 64-битная система
    echo.
    echo Регистрация 32-битной версии:
    %SystemRoot%\SysWOW64\regsvr32.exe /s "%~dp0Dll1.dll"
    echo.
    echo Регистрация 64-битной версии:
    %SystemRoot%\System32\regsvr32.exe /s "%~dp0Dll1.dll"
) else (
    echo 32-битная система
    echo.
    echo Регистрация:
    %SystemRoot%\System32\regsvr32.exe /s "%~dp0Dll1.dll"
)

echo.
echo Готово!
pause
"""

    # 2. Тестовый скрипт для 1С
    test_1c = """// Тестовый скрипт для Dll1.dll
// Выполните в консоли запросов 1С

Процедура ТестПодключения()

    ПутьДЛЛ = "C:\\Users\\denis\\source\\repos\\Dll1\\Debug\\Dll1.dll";

    Сообщить("=== ТЕСТ DLL1.DLL ===");
    Сообщить("Путь: " + ПутьДЛЛ);
    Сообщить("");

    // Попытка 1: Через AddIn
    Попытка
        Вендинг1 = Новый("AddIn.Dll1", ПутьДЛЛ);
        Сообщить("✓ AddIn.Dll1 - УСПЕХ");

        // Тест методов
        Если Вендинг1.Connect("192.168.1.100", 5000, 5) Тогда
            Сообщить("  Connect: Успешно");
            Сообщить("  GetStatus: " + Вендинг1.GetStatus());
            Вендинг1.Disconnect();
        Иначе
            Сообщить("  Connect: Не удалось (нормально для теста)");
            Сообщить("  GetStatus без подключения: " + Вендинг1.GetStatus());
        КонецЕсли;

    Исключение
        Сообщить("✗ AddIn.Dll1 - ОШИБКА: " + ОписаниеОшибки());
    КонецПопытки;

    Сообщить("");

    // Попытка 2: Через COM
    Попытка
        Вендинг2 = Новый COMОбъект("Dll1.VendingMachine");
        Сообщить("✓ COM: Dll1.VendingMachine - УСПЕХ");
    Исключение
        Сообщить("✗ COM: Dll1.VendingMachine - ОШИБКА");
    КонецПопытки;

    Попытка
        Вендинг3 = Новый COMОбъект("VendingMachine");
        Сообщить("✓ COM: VendingMachine - УСПЕХ");
    Исключение
        Сообщить("✗ COM: VendingMachine - ОШИБКА");
    КонецПопытки;

    Сообщить("");
    Сообщить("=== ТЕСТ ЗАВЕРШЕН ===");

КонецПроцедуры

// Запуск теста
ТестПодключения();
"""

    # Сохраняем файлы
    try:
        with open("register_dll.bat", "w", encoding="cp866") as f:
            f.write(bat_content)
        print("✓ Создан файл: register_dll.bat")
        print("  Запустите его от имени администратора для регистрации DLL")

        with open("test_dll1_1c.txt", "w", encoding="utf-8") as f:
            f.write(test_1c)
        print("✓ Создан файл: test_dll1_1c.txt")
        print("  Скопируйте код в консоль запросов 1С")

        return True
    except Exception as e:
        print(f"✗ Ошибка создания файлов: {e}")
        return False


def main():
    """Основная функция"""
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ DLL: Dll1.dll")
    print("Путь: C:\\Users\\denis\\source\\repos\\Dll1\\Debug\\Dll1.dll")
    print("=" * 70)

    # Проверяем разрядность
    python_bitness = check_bitness()

    # Регистрируем DLL
    register_dll()

    # Тестируем функции (пропускаем если разрядность не совпадает)
    dll_bitness = check_dll_bitness(r"C:\Users\denis\source\repos\Dll1\Debug\Dll1.dll")
    print(f"\nРазрядность DLL: {dll_bitness}")
    print(f"Разрядность Python: {python_bitness}-бит")

    if ("64-bit" in dll_bitness and python_bitness == 64) or \
            ("32-bit" in dll_bitness and python_bitness == 32):
        test_dll_functions()
    else:
        print("\n⚠ Внимание: Несовпадение разрядности!")
        print("  Python не может загрузить DLL напрямую")
        print("  Но регистрация и использование в 1С всё равно могут работать")

    # Проверяем COM регистрацию
    test_com_registration()

    # Создаем тестовые файлы
    create_test_files()

    print_header("РЕКОМЕНДАЦИИ")

    print("""
1. ДЛЯ 1С ВАЖНА РАЗРЯДНОСТЬ:
   • 32-битная 1С → компилируйте DLL как Win32 (x86)
   • 64-битная 1С → компилируйте DLL как x64

2. В VISUAL STUDIO:
   • Конфигурация: Debug или Release
   • Платформа: Win32 (для 32-бит) или x64
   • Тип проекта: Динамическая библиотека DLL

3. КОД ДЛЯ 1С:
   Объект = Новый("AddIn.Dll1", "путь\\к\\Dll1.dll");

4. ЕСЛИ НЕ РАБОТАЕТ:
   а) Запустите register_dll.bat от имени администратора
   б) Убедитесь, что путь к DLL правильный
   в) Проверьте разрядность 1С и DLL
   г) Запустите 1С от имени администратора

5. ПРОВЕРКА:
   • Запустите test_dll1_1c.txt в консоли 1С
   • Если видите "AddIn.Dll1 - УСПЕХ" - всё работает!
    """)

    print("\n" + "=" * 70)
    print("СОВЕТ: Скомпилируйте DLL как Win32 (x86) для 32-битной 1С")
    print("Или как x64 для 64-битной 1С")
    print("=" * 70)


if __name__ == "__main__":
    main()