#!/usr/bin/env python3
"""
Smart Trainer Launcher with GUI
Проверяет обновления и запускает основное приложение
"""
import os
import sys
import subprocess
import requests
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QMessageBox, QFrame, QGridLayout,
    QGroupBox, QTextEdit, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPoint, QPointF
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QPen, QBrush, QPolygonF


class UpdateThread(QThread):
    """Поток для проверки и выполнения обновлений"""
    progress_updated = pyqtSignal(int, str)
    update_complete = pyqtSignal(bool, str)
    log_message = pyqtSignal(str)

    def __init__(self, action):
        super().__init__()
        self.action = action  # 'check', 'update', 'install'
        self.canceled = False

    def run(self):
        try:
            if self.action == 'check':
                self.check_version()
            elif self.action == 'update':
                self.perform_update()
            elif self.action == 'install':
                self.install_requirements()
        except Exception as e:
            self.log_message.emit(f"Ошибка: {str(e)}")
            self.update_complete.emit(False, str(e))

    def check_version(self):
        """Проверяет версии приложения"""
        self.log_message.emit("Проверка текущей версии...")
        self.progress_updated.emit(20, "Проверка локальной версии")

        current_version = self.get_current_version()
        self.log_message.emit(f"Текущая версия: {current_version}")

        self.progress_updated.emit(50, "Проверка версии на GitHub")
        github_version = self.get_github_version()

        if github_version:
            self.log_message.emit(f"Версия на GitHub: {github_version}")

            if github_version == current_version:
                message = "У вас актуальная версия приложения"
                self.log_message.emit(message)
                self.update_complete.emit(True, message)
            else:
                message = f"Доступно обновление: {current_version} → {github_version}"
                self.log_message.emit(message)
                self.update_complete.emit(False, message)
        else:
            message = "Не удалось проверить версию на GitHub"
            self.log_message.emit(message)
            self.update_complete.emit(False, message)

        self.progress_updated.emit(100, "Проверка завершена")

    def perform_update(self):
        """Выполняет обновление приложения"""
        self.log_message.emit("Начало обновления...")

        # Получаем версии
        current_version = self.get_current_version()
        github_version = self.get_github_version()

        if not github_version:
            self.update_complete.emit(False, "Не удалось получить версию с GitHub")
            return

        # Создаем папку для бэкапа
        backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Файлы для обновления
        files_to_update = ['app.py', 'requirements.txt', 'launcher.py']

        # Создаем бэкапы
        self.progress_updated.emit(10, "Создание резервных копий")
        self.log_message.emit("Создание резервных копий...")

        backup_count = 0
        for filename in files_to_update:
            if os.path.exists(filename):
                import shutil
                shutil.copy2(filename, os.path.join(backup_dir, filename))
                backup_count += 1
                self.log_message.emit(f"  ✓ Создана резервная копия: {filename}")

        self.log_message.emit(f"Создано {backup_count} резервных копий")

        # Скачиваем обновления
        self.progress_updated.emit(30, "Скачивание обновлений")
        success_count = 0

        for i, filename in enumerate(files_to_update):
            if self.canceled:
                self.log_message.emit("Обновление отменено")
                self.update_complete.emit(False, "Обновление отменено")
                return

            progress = 30 + ((i + 1) * 40 // len(files_to_update))
            self.progress_updated.emit(progress, f"Скачивание {filename}")

            if self.download_file(filename):
                self.log_message.emit(f"  ✓ {filename} обновлен")
                success_count += 1
            else:
                self.log_message.emit(f"  ✗ Ошибка обновления {filename}")

        if success_count == len(files_to_update):
            # Обновляем версию
            with open("version.txt", 'w') as f:
                f.write(github_version)

            # Устанавливаем зависимости
            self.progress_updated.emit(80, "Установка зависимостей")
            self.log_message.emit("Проверка и установка зависимостей...")

            if self.install_requirements_silent():
                message = f"Приложение успешно обновлено до версии {github_version}"
                self.log_message.emit(message)
                self.log_message.emit(f"Резервные копии сохранены в: {backup_dir}")
                self.progress_updated.emit(100, "Обновление завершено")
                self.update_complete.emit(True, message)
            else:
                message = "Обновление выполнено, но возникли проблемы с зависимостями"
                self.log_message.emit(message)
                self.update_complete.emit(False, message)
        else:
            # Восстанавливаем из бэкапа
            self.progress_updated.emit(90, "Восстановление из резервной копии")
            self.log_message.emit("Ошибка при обновлении! Восстанавливаю из резервной копии...")

            restore_count = 0
            for filename in files_to_update:
                backup_path = os.path.join(backup_dir, filename)
                if os.path.exists(backup_path):
                    import shutil
                    shutil.copy2(backup_path, filename)
                    restore_count += 1
                    self.log_message.emit(f"  Восстановлен: {filename}")

            message = f"Восстановлено {restore_count} файлов из резервной копии"
            self.log_message.emit(message)
            self.update_complete.emit(False, "Ошибка обновления. Восстановлено из резервной копии.")

    def install_requirements(self):
        """Устанавливает зависимости"""
        self.log_message.emit("Проверка и установка модулей...")
        self.progress_updated.emit(30, "Чтение requirements.txt")

        if not os.path.exists("requirements.txt"):
            self.log_message.emit("Файл requirements.txt не найден")
            self.update_complete.emit(False, "Файл requirements.txt не найден")
            return

        try:
            with open("requirements.txt", 'r') as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            if not requirements:
                self.log_message.emit("Нет модулей для установки")
                self.update_complete.emit(True, "Нет модулей для установки")
                return

            self.progress_updated.emit(50, f"Установка {len(requirements)} модулей")
            self.log_message.emit(f"Найдено {len(requirements)} модулей для установки")

            for i, req in enumerate(requirements):
                if self.canceled:
                    self.log_message.emit("Установка отменена")
                    self.update_complete.emit(False, "Установка отменена")
                    return

                progress = 50 + ((i + 1) * 40 // len(requirements))
                self.progress_updated.emit(progress, f"Установка {req}")
                self.log_message.emit(f"  Установка: {req}")

                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", req],
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
                    self.log_message.emit(f"  ✓ Установлен: {req}")
                except subprocess.CalledProcessError:
                    self.log_message.emit(f"  ✗ Ошибка установки: {req}")

            self.progress_updated.emit(100, "Установка завершена")
            self.log_message.emit("Все модули успешно установлены")
            self.update_complete.emit(True, "Модули успешно установлены")

        except Exception as e:
            self.log_message.emit(f"Ошибка: {str(e)}")
            self.update_complete.emit(False, f"Ошибка установки: {str(e)}")

    def install_requirements_silent(self):
        """Устанавливает зависимости без вывода"""
        try:
            if os.path.exists("requirements.txt"):
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
                return True
        except:
            return False
        return True

    def get_current_version(self):
        """Получает текущую версию приложения"""
        version_file = "version.txt"
        current_version = "1.0.0"

        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    current_version = f.read().strip()
            except:
                pass

        return current_version

    def get_github_version(self):
        """Получает версию с GitHub"""
        try:
            version_url = "https://raw.githubusercontent.com/DenisASUTP/OP_4/main/version.txt"
            response = requests.get(version_url, timeout=10)
            if response.status_code == 200:
                return response.text.strip()
        except Exception as e:
            self.log_message.emit(f"Ошибка получения версии с GitHub: {str(e)}")

        return None

    def download_file(self, filename):
        """Скачивает файл с GitHub"""
        try:
            url = f"https://raw.githubusercontent.com/DenisASUTP/OP_4/main/{filename}"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)

                with open(filename, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            self.log_message.emit(f"Ошибка скачивания {filename}: {str(e)}")

        return False


class StyledButton(QPushButton):
    """Стилизованная кнопка"""

    def __init__(self, text, color="#FF6B00", parent=None):
        super().__init__(text, parent)
        self.normal_color = color
        self.hover_color = self.adjust_color(color, 1.2)
        self.pressed_color = self.adjust_color(color, 0.8)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.normal_color};
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {self.hover_color};
            }}
            QPushButton:pressed {{
                background-color: {self.pressed_color};
            }}
            QPushButton:disabled {{
                background-color: #555;
                color: #888;
            }}
        """)

    def adjust_color(self, color, factor):
        """Изменяет яркость цвета"""
        qcolor = QColor(color)
        h, s, l, a = qcolor.getHslF()
        l = min(0.9, max(0.1, l * factor))
        qcolor.setHslF(h, s, l, a)
        return qcolor.name()


class WelcomeScreen(QWidget):
    """Экран приветствия"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # Заголовок
        title = QLabel("SMART TRAINER LAUNCHER")
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setStyleSheet("color: #FF6B00; margin: 30px;")
        title.setAlignment(Qt.AlignCenter)

        # Подзаголовок
        subtitle = QLabel("Управление и обновление приложения")
        subtitle.setFont(QFont("Arial", 16))
        subtitle.setStyleSheet("color: #CCCCCC; margin: 10px;")
        subtitle.setAlignment(Qt.AlignCenter)

        # Иконка
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(200, 200)
        icon_label.setStyleSheet("""
            background-color: #2D2D2D;
            border-radius: 100px;
            border: 4px solid #FF6B00;
        """)

        # Создаем простую иконку через QPixmap
        self.create_icon(icon_label)

        # Информация о версии
        self.version_label = QLabel("Версия: проверка...")
        self.version_label.setFont(QFont("Arial", 12))
        self.version_label.setStyleSheet("color: #888888; margin: 20px;")
        self.version_label.setAlignment(Qt.AlignCenter)

        # Кнопки
        buttons_layout = QGridLayout()
        buttons_layout.setSpacing(20)

        self.btn_check = StyledButton("Проверить\nобновления", "#1976D2")
        self.btn_check.clicked.connect(self.parent.show_update_screen)

        self.btn_launch = StyledButton("Запустить\nприложение", "#4CAF50")
        self.btn_launch.clicked.connect(self.parent.launch_application)

        self.btn_install = StyledButton("Установить\nмодули", "#9C27B0")
        self.btn_install.clicked.connect(self.parent.show_install_screen)

        self.btn_exit = StyledButton("Выход", "#555555")
        self.btn_exit.clicked.connect(QApplication.instance().quit)

        buttons_layout.addWidget(self.btn_check, 0, 0)
        buttons_layout.addWidget(self.btn_launch, 0, 1)
        buttons_layout.addWidget(self.btn_install, 1, 0)
        buttons_layout.addWidget(self.btn_exit, 1, 1)

        # Информация
        info_label = QLabel(
            "© 2024 Smart Trainer System\n"
            "GitHub: DenisASUTP/OP_4"
        )
        info_label.setFont(QFont("Arial", 9))
        info_label.setStyleSheet("color: #666666; margin-top: 30px;")
        info_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        layout.addWidget(icon_label)
        layout.addStretch(1)
        layout.addWidget(self.version_label)
        layout.addLayout(buttons_layout)
        layout.addStretch(2)
        layout.addWidget(info_label)

        self.setLayout(layout)

    def create_icon(self, label):
        """Создает иконку для лаунчера"""
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Оранжевый круг
        painter.setBrush(QBrush(QColor(255, 107, 0)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(20, 20, 160, 160)

        # Белая стрелка - рисуем с помощью drawPolygon с QPointF
        points = [
            QPointF(100, 60),
            QPointF(140, 100),
            QPointF(100, 140),
            QPointF(100, 120),
            QPointF(60, 120),
            QPointF(60, 80),
            QPointF(100, 80)
        ]

        polygon = QPolygonF(points)
        painter.setBrush(QBrush(Qt.white))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawPolygon(polygon)

        painter.end()
        label.setPixmap(pixmap)

    def update_version_info(self, version):
        """Обновляет информацию о версии"""
        self.version_label.setText(f"Версия: {version}")


class UpdateScreen(QWidget):
    """Экран обновления"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)

        # Заголовок
        title = QLabel("Обновление приложения")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setStyleSheet("color: #FF6B00; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)

        # Информация о версиях
        versions_group = QGroupBox("Информация о версиях")
        versions_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #CCCCCC;
                border: 2px solid #444;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        versions_layout = QGridLayout()

        self.current_label = QLabel("Текущая версия: проверка...")
        self.current_label.setFont(QFont("Arial", 11))
        self.current_label.setStyleSheet("color: #CCCCCC;")

        self.github_label = QLabel("Версия на GitHub: проверка...")
        self.github_label.setFont(QFont("Arial", 11))
        self.github_label.setStyleSheet("color: #CCCCCC;")

        self.status_label = QLabel("Статус: ожидание проверки")
        self.status_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.status_label.setStyleSheet("color: #FF6B00;")

        versions_layout.addWidget(QLabel("Локальная:"), 0, 0)
        versions_layout.addWidget(self.current_label, 0, 1)
        versions_layout.addWidget(QLabel("GitHub:"), 1, 0)
        versions_layout.addWidget(self.github_label, 1, 1)
        versions_layout.addWidget(QLabel("Статус:"), 2, 0)
        versions_layout.addWidget(self.status_label, 2, 1)

        versions_group.setLayout(versions_layout)

        # Прогресс
        self.progress_label = QLabel("Готов к работе")
        self.progress_label.setFont(QFont("Arial", 11))
        self.progress_label.setStyleSheet("color: #CCCCCC; margin-top: 20px;")
        self.progress_label.setAlignment(Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
                color: white;
                height: 25px;
                margin: 10px 0;
            }
            QProgressBar::chunk {
                background-color: #FF6B00;
                border-radius: 3px;
            }
        """)

        # Лог
        log_group = QGroupBox("Лог операций")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #CCCCCC;
                border: 2px solid #444;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)

        # Кнопки
        buttons_layout = QHBoxLayout()

        self.btn_check = StyledButton("Проверить", "#1976D2")
        self.btn_check.clicked.connect(self.parent.start_check)

        self.btn_update = StyledButton("Обновить", "#4CAF50")
        self.btn_update.clicked.connect(self.parent.start_update)
        self.btn_update.setEnabled(False)

        self.btn_back = StyledButton("Назад", "#555555")
        self.btn_back.clicked.connect(self.parent.show_welcome_screen)

        self.btn_cancel = StyledButton("Отмена", "#D32F2F")
        self.btn_cancel.clicked.connect(self.parent.cancel_operation)
        self.btn_cancel.setEnabled(False)

        buttons_layout.addWidget(self.btn_check)
        buttons_layout.addWidget(self.btn_update)
        buttons_layout.addWidget(self.btn_back)
        buttons_layout.addWidget(self.btn_cancel)

        layout.addWidget(title)
        layout.addWidget(versions_group)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(log_group)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def add_log(self, message):
        """Добавляет сообщение в лог"""
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def clear_log(self):
        """Очищает лог"""
        self.log_text.clear()

    def set_versions(self, current, github):
        """Устанавливает информацию о версиях"""
        self.current_label.setText(f"Текущая версия: {current}")
        self.github_label.setText(f"Версия на GitHub: {github}")

    def set_status(self, status, color="#FF6B00"):
        """Устанавливает статус"""
        self.status_label.setText(f"Статус: {status}")
        self.status_label.setStyleSheet(f"color: {color};")

    def set_progress(self, value, text):
        """Устанавливает прогресс"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)

    def set_buttons_state(self, checking=False, updating=False):
        """Устанавливает состояние кнопок"""
        self.btn_check.setEnabled(not (checking or updating))
        self.btn_update.setEnabled(not (checking or updating))
        self.btn_back.setEnabled(not (checking or updating))
        self.btn_cancel.setEnabled(checking or updating)


class InstallScreen(QWidget):
    """Экран установки модулей"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)

        # Заголовок
        title = QLabel("Установка модулей")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setStyleSheet("color: #FF6B00; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)

        # Описание
        description = QLabel(
            "Эта функция установит все необходимые Python модули,\n"
            "указанные в файле requirements.txt"
        )
        description.setFont(QFont("Arial", 11))
        description.setStyleSheet("color: #CCCCCC; margin-bottom: 20px;")
        description.setAlignment(Qt.AlignCenter)

        # Информация о requirements.txt
        req_group = QGroupBox("Информация о requirements.txt")
        req_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #CCCCCC;
                border: 2px solid #444;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        req_layout = QVBoxLayout()

        self.req_status_label = QLabel("Проверка файла...")
        self.req_status_label.setFont(QFont("Arial", 11))
        self.req_status_label.setStyleSheet("color: #CCCCCC;")

        self.req_modules_label = QLabel("Модули: загрузка...")
        self.req_modules_label.setFont(QFont("Arial", 11))
        self.req_modules_label.setStyleSheet("color: #CCCCCC;")

        req_layout.addWidget(self.req_status_label)
        req_layout.addWidget(self.req_modules_label)
        req_group.setLayout(req_layout)

        # Прогресс
        self.progress_label = QLabel("Готов к установке")
        self.progress_label.setFont(QFont("Arial", 11))
        self.progress_label.setStyleSheet("color: #CCCCCC; margin-top: 20px;")
        self.progress_label.setAlignment(Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
                color: white;
                height: 25px;
                margin: 10px 0;
            }
            QProgressBar::chunk {
                background-color: #9C27B0;
                border-radius: 3px;
            }
        """)

        # Лог
        log_group = QGroupBox("Лог установки")
        log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #CCCCCC;
                border: 2px solid #444;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)

        # Кнопки
        buttons_layout = QHBoxLayout()

        self.btn_check_req = StyledButton("Проверить", "#1976D2")
        self.btn_check_req.clicked.connect(self.parent.check_requirements)

        self.btn_install = StyledButton("Установить", "#9C27B0")
        self.btn_install.clicked.connect(self.parent.start_install)

        self.btn_back = StyledButton("Назад", "#555555")
        self.btn_back.clicked.connect(self.parent.show_welcome_screen)

        self.btn_cancel = StyledButton("Отмена", "#D32F2F")
        self.btn_cancel.clicked.connect(self.parent.cancel_operation)
        self.btn_cancel.setEnabled(False)

        buttons_layout.addWidget(self.btn_check_req)
        buttons_layout.addWidget(self.btn_install)
        buttons_layout.addWidget(self.btn_back)
        buttons_layout.addWidget(self.btn_cancel)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(req_group)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(log_group)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def add_log(self, message):
        """Добавляет сообщение в лог"""
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def clear_log(self):
        """Очищает лог"""
        self.log_text.clear()

    def set_req_info(self, exists, modules):
        """Устанавливает информацию о requirements.txt"""
        if exists:
            self.req_status_label.setText("Файл requirements.txt найден")
            self.req_status_label.setStyleSheet("color: #4CAF50;")

            if modules:
                self.req_modules_label.setText(f"Модулей для установки: {len(modules)}")
                modules_text = ", ".join(modules[:5]) + ("..." if len(modules) > 5 else "")
                self.req_modules_label.setToolTip(f"Модули: {modules_text}")
            else:
                self.req_modules_label.setText("Нет модулей для установки")
                self.req_modules_label.setStyleSheet("color: #FF9800;")
        else:
            self.req_status_label.setText("Файл requirements.txt не найден")
            self.req_status_label.setStyleSheet("color: #F44336;")
            self.req_modules_label.setText("")

    def set_progress(self, value, text):
        """Устанавливает прогресс"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)

    def set_buttons_state(self, installing=False):
        """Устанавливает состояние кнопок"""
        self.btn_check_req.setEnabled(not installing)
        self.btn_install.setEnabled(not installing)
        self.btn_back.setEnabled(not installing)
        self.btn_cancel.setEnabled(installing)


class SmartTrainerLauncher(QWidget):
    """Основной класс лаунчера"""

    def __init__(self):
        super().__init__()
        self.update_thread = None
        self.init_ui()
        self.check_current_version()

        # Таймер для периодической проверки версии
        self.version_timer = QTimer()
        self.version_timer.timeout.connect(self.check_current_version)
        self.version_timer.start(30000)  # Каждые 30 секунд

    def init_ui(self):
        self.setWindowTitle("Smart Trainer Launcher")
        self.setFixedSize(800, 700)

        # Устанавливаем темную тему
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
        """)

        # Основной стек экранов
        self.stacked_widget = QStackedWidget()

        # Создаем экраны
        self.welcome_screen = WelcomeScreen(self)
        self.update_screen = UpdateScreen(self)
        self.install_screen = InstallScreen(self)

        self.stacked_widget.addWidget(self.welcome_screen)
        self.stacked_widget.addWidget(self.update_screen)
        self.stacked_widget.addWidget(self.install_screen)

        layout = QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)

        self.show_welcome_screen()

    def show_welcome_screen(self):
        """Показывает экран приветствия"""
        self.stacked_widget.setCurrentWidget(self.welcome_screen)

    def show_update_screen(self):
        """Показывает экран обновления"""
        self.update_screen.clear_log()
        self.update_screen.set_versions("проверка...", "проверка...")
        self.update_screen.set_status("ожидание проверки")
        self.update_screen.set_progress(0, "Готов к работе")
        self.update_screen.set_buttons_state()
        self.stacked_widget.setCurrentWidget(self.update_screen)

    def show_install_screen(self):
        """Показывает экран установки"""
        self.install_screen.clear_log()
        self.install_screen.set_progress(0, "Готов к работе")
        self.install_screen.set_buttons_state()
        self.check_requirements()
        self.stacked_widget.setCurrentWidget(self.install_screen)

    def check_current_version(self):
        """Проверяет текущую версию для отображения на welcome screen"""
        version = self.get_current_version()
        self.welcome_screen.update_version_info(version)

    def get_current_version(self):
        """Получает текущую версию"""
        version_file = "version.txt"
        current_version = "1.0.0"

        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    current_version = f.read().strip()
            except:
                pass

        return current_version

    def start_check(self):
        """Начинает проверку обновлений"""
        self.update_screen.clear_log()
        self.update_screen.set_buttons_state(checking=True)

        self.update_thread = UpdateThread('check')
        self.update_thread.progress_updated.connect(self.update_screen.set_progress)
        self.update_thread.log_message.connect(self.update_screen.add_log)
        self.update_thread.update_complete.connect(self.on_check_complete)
        self.update_thread.start()

    def start_update(self):
        """Начинает обновление"""
        reply = QMessageBox.question(
            self, "Подтверждение обновления",
            "Вы уверены, что хотите обновить приложение?\n"
            "Будут созданы резервные копии файлов.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.update_screen.clear_log()
            self.update_screen.set_buttons_state(updating=True)

            self.update_thread = UpdateThread('update')
            self.update_thread.progress_updated.connect(self.update_screen.set_progress)
            self.update_thread.log_message.connect(self.update_screen.add_log)
            self.update_thread.update_complete.connect(self.on_update_complete)
            self.update_thread.start()

    def start_install(self):
        """Начинает установку модулей"""
        self.install_screen.clear_log()
        self.install_screen.set_buttons_state(installing=True)

        self.update_thread = UpdateThread('install')
        self.update_thread.progress_updated.connect(self.install_screen.set_progress)
        self.update_thread.log_message.connect(self.install_screen.add_log)
        self.update_thread.update_complete.connect(self.on_install_complete)
        self.update_thread.start()

    def check_requirements(self):
        """Проверяет файл requirements.txt"""
        try:
            if os.path.exists("requirements.txt"):
                with open("requirements.txt", 'r') as f:
                    modules = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                self.install_screen.set_req_info(True, modules)
            else:
                self.install_screen.set_req_info(False, [])
        except Exception as e:
            self.install_screen.set_req_info(False, [])
            self.install_screen.add_log(f"Ошибка чтения requirements.txt: {e}")

    @pyqtSlot(bool, str)
    def on_check_complete(self, success, message):
        """Обрабатывает завершение проверки"""
        self.update_screen.set_buttons_state()

        if success:
            self.update_screen.set_status("Актуальная версия", "#4CAF50")
        else:
            self.update_screen.set_status("Доступно обновление", "#FF9800")
            if "Доступно обновление" in message:
                self.update_screen.btn_update.setEnabled(True)

        # Обновляем информацию о версиях
        current_version = self.get_current_version()
        github_version = self.get_github_version()

        self.update_screen.set_versions(current_version, github_version or "не доступна")

        self.update_screen.add_log(f"✓ {message}")

    @pyqtSlot(bool, str)
    def on_update_complete(self, success, message):
        """Обрабатывает завершение обновления"""
        self.update_screen.set_buttons_state()

        if success:
            self.update_screen.set_status("Обновление успешно", "#4CAF50")
            QMessageBox.information(self, "Обновление завершено",
                                    "Приложение успешно обновлено!\n"
                                    "Рекомендуется перезапустить лаунчер.")
        else:
            self.update_screen.set_status("Ошибка обновления", "#F44336")

        # Обновляем информацию о версиях
        current_version = self.get_current_version()
        github_version = self.get_github_version()

        self.update_screen.set_versions(current_version, github_version or "не доступна")
        self.update_screen.btn_update.setEnabled(False)

        # Обновляем версию на welcome screen
        self.check_current_version()

    @pyqtSlot(bool, str)
    def on_install_complete(self, success, message):
        """Обрабатывает завершение установки"""
        self.install_screen.set_buttons_state()

        if success:
            self.install_screen.set_progress(100, "Установка завершена")
            QMessageBox.information(self, "Установка завершена",
                                    "Модули успешно установлены!")
        else:
            self.install_screen.set_progress(0, "Ошибка установки")

    def cancel_operation(self):
        """Отменяет текущую операцию"""
        if self.update_thread and self.update_thread.isRunning():
            self.update_thread.canceled = True
            self.update_thread.quit()
            self.update_thread.wait()

            if self.stacked_widget.currentWidget() == self.update_screen:
                self.update_screen.set_buttons_state()
                self.update_screen.add_log("Операция отменена пользователем")
            elif self.stacked_widget.currentWidget() == self.install_screen:
                self.install_screen.set_buttons_state()
                self.install_screen.add_log("Операция отменена пользователем")

    def get_github_version(self):
        """Получает версию с GitHub"""
        try:
            version_url = "https://raw.githubusercontent.com/DenisASUTP/OP_4/main/version.txt"
            response = requests.get(version_url, timeout=10)
            if response.status_code == 200:
                return response.text.strip()
        except:
            return None

    def launch_application(self):
        """Запускает основное приложение"""
        if not os.path.exists("app.py"):
            QMessageBox.critical(self, "Ошибка", "Файл app.py не найден!")
            return

        try:
            # Закрываем лаунчер
            self.hide()

            # Запускаем приложение
            subprocess.Popen([sys.executable, "app.py"])

            # Даем время приложению запуститься
            QTimer.singleShot(1000, QApplication.instance().quit)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка запуска", f"Не удалось запустить приложение:\n{str(e)}")
            self.show()


def main():
    """Основная функция"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Устанавливаем темную палитру
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(255, 107, 0))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)

    launcher = SmartTrainerLauncher()
    launcher.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()