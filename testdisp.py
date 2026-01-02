#!/usr/bin/env python3
"""
display_info_win.py - Информация о дисплеях в Windows 10
Запуск: python display_info_win.py
"""

import wmi
import subprocess
import sys
import ctypes
from ctypes import wintypes
import struct


def check_admin():
    """Проверка прав администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def get_wmi_display_info():
    """Получить информацию о дисплеях через WMI"""
    print("=" * 70)
    print("ИНФОРМАЦИЯ О ДИСПЛЕЯХ (WMI)")
    print("=" * 70)

    try:
        c = wmi.WMI()

        # Информация о мониторах
        print("\n[Мониторы]:")
        for monitor in c.Win32_DesktopMonitor():
            print(f"  Название: {monitor.Name}")
            print(f"  PNP ID: {monitor.PNPDeviceID}")
            print(f"  Размер экрана: {monitor.ScreenWidth} x {monitor.ScreenHeight}")
            print(f"  Статус: {monitor.Status}")
            print()

        # Информация о видеоадаптерах
        print("\n[Видеоадаптеры]:")
        for gpu in c.Win32_VideoController():
            print(f"  Название: {gpu.Name}")
            print(f"  Текущее разрешение: {gpu.CurrentHorizontalResolution} x {gpu.CurrentVerticalResolution}")
            print(f"  Частота обновления: {gpu.CurrentRefreshRate} Hz")
            print(f"  Битов на пиксель: {gpu.CurrentBitsPerPixel}")
            print()

    except Exception as e:
        print(f"Ошибка WMI: {e}")
        print("Установите модуль: pip install wmi")


def get_edid_from_registry():
    """Получить EDID из реестра Windows"""
    print("\n" + "=" * 70)
    print("ПОПЫТКА ПРОЧИТАТЬ EDID ИЗ РЕЕСТРА")
    print("=" * 70)

    import winreg

    try:
        # Ключ реестра где хранится EDID
        key_path = r"SYSTEM\CurrentControlSet\Enum\DISPLAY"

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            while True:
                try:
                    monitor_key_name = winreg.EnumKey(key, i)
                    monitor_path = f"{key_path}\\{monitor_key_name}"

                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, monitor_path) as monitor_key:
                        j = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(monitor_key, j)
                                subkey_path = f"{monitor_path}\\{subkey_name}"

                                # Пытаемся прочитать EDID
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                                    f"{subkey_path}\\Device Parameters") as params_key:
                                    try:
                                        edid_data, reg_type = winreg.QueryValueEx(params_key, "EDID")
                                        if edid_data and len(edid_data) >= 128:
                                            print(f"\nНайден EDID для: {monitor_key_name}")
                                            print(f"  Размер EDID: {len(edid_data)} байт")
                                            # Первые 8 байт заголовка
                                            print(f"  Заголовок: {edid_data[:8].hex()}")
                                            return edid_data
                                    except:
                                        pass
                                j += 1
                            except OSError:
                                break
                    i += 1
                except OSError:
                    break

    except Exception as e:
        print(f"Ошибка чтения реестра: {e}")

    print("EDID не найден в реестре или нет прав администратора")
    return None


def parse_basic_edid(edid_data):
    """Базовый парсинг EDID"""
    if not edid_data or len(edid_data) < 128:
        return

    print("\n" + "=" * 70)
    print("БАЗОВЫЙ АНАЛИЗ EDID")
    print("=" * 70)

    # Manufacturer ID (3 буквы)
    man_id = ""
    man_bytes = edid_data[8:10]
    man_id += chr(((man_bytes[0] >> 2) & 0x1F) + ord('A') - 1)
    man_id += chr((((man_bytes[0] & 0x03) << 3) | ((man_bytes[1] >> 5) & 0x07)) + ord('A') - 1)
    man_id += chr((man_bytes[1] & 0x1F) + ord('A') - 1)

    product_code = struct.unpack('<H', edid_data[10:12])[0]
    serial = struct.unpack('<I', edid_data[12:16])[0]

    # Размер экрана в см
    width_cm = edid_data[21]
    height_cm = edid_data[22]

    print(f"  Производитель: {man_id}")
    print(f"  Код продукта: {product_code:#06x}")
    print(f"  Серийный номер: {serial}")
    print(f"  Физический размер: {width_cm} x {height_cm} см")

    # Detailed Timing Descriptor 1 (обычно нативный режим)
    offset = 54
    if len(edid_data) >= offset + 18:
        pixel_clock = struct.unpack('<H', edid_data[offset:offset + 2])[0] * 10  # kHz to 10kHz

        h_active = edid_data[offset + 2] | ((edid_data[offset + 4] & 0xF0) << 4)
        h_blank = edid_data[offset + 3] | ((edid_data[offset + 4] & 0x0F) << 8)

        v_active = edid_data[offset + 5] | ((edid_data[offset + 7] & 0xF0) << 4)
        v_blank = edid_data[offset + 6] | ((edid_data[offset + 7] & 0x0F) << 8)

        print(f"\n  [Нативный режим из EDID]:")
        print(f"    Разрешение: {h_active} x {v_active}")
        print(f"    Pixel clock: {pixel_clock / 100:.2f} MHz")
        print(f"    H-total: {h_active + h_blank}")
        print(f"    V-total: {v_active + v_blank}")


def run_powershell_command(command):
    """Выполнить PowerShell команду"""
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            encoding='cp866'  # Для русского вывода
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Ошибка: {e}"


def get_display_info_powershell():
    """Получить информацию через PowerShell"""
    print("\n" + "=" * 70)
    print("ИНФОРМАЦИЯ ЧЕРЕЗ POWERSHELL")
    print("=" * 70)

    # Текущие настройки дисплея
    print("\n[Текущие параметры дисплея]:")
    ps_cmd = '''
    Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBasicDisplayParams | ForEach-Object {
        "  Активно: $($_.Active)"
        "  Тип дисплея: $($_.VideoInputType)"
    }
    '''
    print(run_powershell_command(ps_cmd))

    # Поддерживаемые режимы
    print("\n[Поддерживаемые видеорежимы]:")
    ps_cmd = '''
    Get-WmiObject -Namespace root\\wmi -Class WmiMonitorListedSupportedSourceModes | 
    Select-Object -ExpandProperty MonitorSourceModes | 
    ForEach-Object {
        "  $($_.HorizontalActivePixels)x$($_.VerticalActivePixels) @ $($_.RefreshRate/1)Hz"
    } | Select-Object -First 10
    '''
    print(run_powershell_command(ps_cmd))


def get_display_device_info():
    """Получить информацию о устройствах отображения"""
    print("\n" + "=" * 70)
    print("УСТРОЙСТВА ОТОБРАЖЕНИЯ")
    print("=" * 70)

    ps_cmd = '''
    Get-WmiObject Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Monitor'} | 
    ForEach-Object {
        "  Устройство: $($_.Name)"
        "  ID: $($_.DeviceID)"
        "  Статус: $($_.Status)"
        ""
    }
    '''
    print(run_powershell_command(ps_cmd))


def get_current_resolution():
    """Получить текущее разрешение экрана"""
    print("\n" + "=" * 70)
    print("ТЕКУЩЕЕ РАЗРЕШЕНИЕ ЭКРАНА")
    print("=" * 70)

    try:
        user32 = ctypes.windll.user32
        screens = []

        # Мультимониторная система
        def enum_monitors_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = MONITORINFOEX()
            info.cbSize = ctypes.sizeof(MONITORINFOEX)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                screens.append({
                    'name': info.szDevice,
                    'left': info.rcMonitor.left,
                    'top': info.rcMonitor.top,
                    'right': info.rcMonitor.right,
                    'bottom': info.rcMonitor.bottom,
                    'width': info.rcMonitor.right - info.rcMonitor.left,
                    'height': info.rcMonitor.bottom - info.rcMonitor.top,
                    'primary': bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY
                })
            return True

        # Структуры Windows API
        class RECT(ctypes.Structure):
            _fields_ = [
                ('left', ctypes.c_long),
                ('top', ctypes.c_long),
                ('right', ctypes.c_long),
                ('bottom', ctypes.c_long)
            ]

        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ('cbSize', ctypes.c_ulong),
                ('rcMonitor', RECT),
                ('rcWork', RECT),
                ('dwFlags', ctypes.c_ulong),
                ('szDevice', ctypes.c_wchar * 32)
            ]

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(RECT),
            ctypes.c_double
        )

        callback = MonitorEnumProc(enum_monitors_callback)
        user32.EnumDisplayMonitors(None, None, callback, 0)

        for i, screen in enumerate(screens):
            primary = " (основной)" if screen['primary'] else ""
            print(f"  Экран {i + 1}{primary}:")
            print(f"    Разрешение: {screen['width']} x {screen['height']}")
            print(f"    Позиция: ({screen['left']}, {screen['top']})")
            print(f"    Имя устройства: {screen['name']}")
            print()

    except Exception as e:
        print(f"Ошибка получения разрешения: {e}")


def check_cru_installation():
    """Проверить наличие CRU"""
    print("\n" + "=" * 70)
    print("РЕКОМЕНДАЦИИ")
    print("=" * 70)

    print("\nДля полной диагностики EDID и таймингов:")
    print("1. Скачайте CRU (Custom Resolution Utility):")
    print("   https://www.monitortests.com/forum/Thread-Custom-Resolution-Utility-CRU")
    print("\n2. Запустите CRU.exe (не требует установки)")
    print("3. Нажмите 'Edit' рядом с вашим монитором")
    print("4. В разделе 'Detailed resolutions' увидите все тайминги")

    print("\nДля вашего дисплея с LT8619C обратите внимание на:")
    print("  - Native mode (нативный режим)")
    print("  - Pixel clock (тактовую частоту пикселей)")
    print("  - Front porch / Back porch / Sync width")
    print("  - Refresh rate (частоту обновления)")


def create_summary():
    """Создать сводку"""
    print("\n" + "=" * 70)
    print("СВОДНАЯ ИНФОРМАЦИЯ")
    print("=" * 70)

    print("\nСоберите следующие данные для настройки Orange Pi:")
    print("1. Нативное разрешение дисплея")
    print("2. Частоту обновления (обычно 60 Гц)")
    print("3. Pixel clock из CRU (в МГц)")
    print("4. Значения Front Porch/Sync Width/Back Porch")

    print("\nПример параметров для /boot/armbianEnv.txt:")
    print('  extraargs=video=HDMI-A-1:1024x600@60e')
    print('  # или с подробными параметрами:')
    print('  # extraargs=video=HDMI-A-1:drm.edid_firmware=edid/1024x600.bin')


def main():
    """Основная функция"""
    print("\n" + "=" * 70)
    print("ДИАГНОСТИКА ДИСПЛЕЯ WINDOWS 10")
    print("=" * 70)

    # Проверка прав
    if not check_admin():
        print("\nВНИМАНИЕ: Скрипт запущен без прав администратора.")
        print("Некоторые функции (чтение EDID из реестра) могут не работать.")
        print("Запустите от имени администратора для полной диагностики.")

    # Сбор информации
    get_current_resolution()
    get_wmi_display_info()
    get_display_info_powershell()
    get_display_device_info()

    # Чтение EDID (требует админ прав)
    if check_admin():
        edid_data = get_edid_from_registry()
        if edid_data:
            parse_basic_edid(edid_data)
    else:
        print("\nДля чтения EDID запустите скрипт от имени администратора")

    # Рекомендации
    check_cru_installation()
    create_summary()

    print("\n" + "=" * 70)
    print("Диагностика завершена!")
    print("=" * 70)


if __name__ == "__main__":
    # Установите зависимости: pip install wmi pywin32
    try:
        import wmi
    except ImportError:
        print("Установите модуль wmi: pip install wmi")
        sys.exit(1)

    main()