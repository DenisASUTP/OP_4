#!/usr/bin/env python3
"""
Smart Trainer Launcher - Стабильная версия с GUI
Автоматическая проверка обновлений и запуск приложения
"""
import os
import sys
import subprocess
import requests
import threading
import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QMessageBox, QGroupBox, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QPoint, QPointF
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QPen, QBrush, QPolygonF


class SmartTrainerLauncher(QWidget):
    """Основной класс лаунчера"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    status_signal = pyqtSignal(str)
    version_signal = pyqtSignal(str)
    complete_signal = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.current_version = "1.0.0"
        self.github_version = None
        self.auto_launch = True
        self.is_updating = False
        self.init_ui()

        # Подключаем сигналы
        self.log_signal.connect(self.add_log)
        self.progress_signal.connect(self.update_progress)
        self.status_signal.connect(self.update_status)
        self.version_signal.connect(self.update_version_display)
        self.complete_signal.connect(self.on_operation_complete)

        # Загружаем текущую версию
        self.load_current_version()

        # Запускаем таймер автостарта
        self.start_countdown()

    def init_ui(self):
        self.setWindowTitle("Smart Trainer Launcher")
        self.setFixedSize(600, 500)

        # Устанавливаем темную тему
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title = QLabel("SMART TRAINER")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: #FF6B00;")
        title.setAlignment(Qt.AlignCenter)

        # Подзаголовок
        subtitle = QLabel("Автоматический лаунчер")
        subtitle.setFont(QFont("Arial", 14))
        subtitle.setStyleSheet("color: #CCCCCC;")
        subtitle.setAlignment(Qt.AlignCenter)

        # Иконка
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(150, 150)
        self.create_icon()

        # Информация о версии
        self.version_label = QLabel("Версия: загрузка...")
        self.version_label.setFont(QFont("Arial", 12))
        self.version_label.setStyleSheet("color: #888888;")
        self.version_label.setAlignment(Qt.AlignCenter)

        # Таймер
        self.timer_label = QLabel("Автозапуск через: 3")
        self.timer_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.timer_label.setStyleSheet("color: #FF6B00;")
        self.timer_label.setAlignment(Qt.AlignCenter)

        # Статус
        self.status_label = QLabel("Готов к работе")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: #CCCCCC;")
        self.status_label.setAlignment(Qt.AlignCenter)

        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
                color: white;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #FF6B00;
                border-radius: 3px;
            }
        """)

        # Лог
        log_group = QGroupBox("Процесс")
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
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)

        # Кнопки
        buttons_layout = QHBoxLayout()

        self.btn_check = QPushButton("Проверить сейчас")
        self.btn_check.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btn_check.clicked.connect(self.on_check_now)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #444;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.btn_cancel.setEnabled(False)

        buttons_layout.addWidget(self.btn_check)
        buttons_layout.addWidget(self.btn_cancel)

        # Информация
        info_label = QLabel("© 2024 Smart Trainer System")
        info_label.setFont(QFont("Arial", 9))
        info_label.setStyleSheet("color: #666666;")
        info_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        layout.addWidget(self.icon_label, 0, Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(self.version_label)
        layout.addWidget(self.timer_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(log_group)
        layout.addLayout(buttons_layout)
        layout.addWidget(info_label)

        self.setLayout(layout)

    def create_icon(self):
        """Создает иконку"""
        pixmap = QPixmap(150, 150)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Оранжевый круг
        painter.setBrush(QBrush(QColor(255, 107, 0)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(15, 15, 120, 120)

        # Белая стрелка
        points = [
            QPointF(75, 45),
            QPointF(105, 75),
            QPointF(75, 105),
            QPointF(75, 90),
            QPointF(45, 90),
            QPointF(45, 60),
            QPointF(75, 60)
        ]

        polygon = QPolygonF(points)
        painter.setBrush(QBrush(Qt.white))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawPolygon(polygon)

        painter.end()
        self.icon_label.setPixmap(pixmap)

    def load_current_version(self):
        """Загружает текущую версию"""
        version_file = "version.txt"

        if os.path.exists(version_file):
            try:
                # Пробуем несколько кодировок
                encodings = ['utf-8', 'utf-16', 'cp1251', 'cp1252', 'latin-1']

                for encoding in encodings:
                    try:
                        with open(version_file, 'r', encoding=encoding) as f:
                            content = f.read().strip()
                            if content:
                                self.current_version = content
                                self.version_signal.emit(f"Версия: {self.current_version}")
                                break
                    except:
                        continue
            except:
                pass

        self.version_signal.emit(f"Версия: {self.current_version}")

    def start_countdown(self):
        """Запускает обратный отсчет"""
        self.countdown = 3
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)  # Каждую секунду

    def update_countdown(self):
        """Обновляет обратный отсчет"""
        if self.countdown > 0:
            self.timer_label.setText(f"Автозапуск через: {self.countdown}")
            self.countdown -= 1
        else:
            self.timer.stop()
            if self.auto_launch and not self.is_updating:
                QTimer.singleShot(1000, self.launch_application)
                # self.start_automatic_check()

    def on_check_now(self):
        """Обработчик кнопки 'Проверить сейчас'"""
        self.auto_launch = False
        self.timer.stop()
        self.timer_label.setText("Ручная проверка")
        self.start_automatic_check()

    def on_cancel(self):
        """Обработчик кнопки 'Отмена'"""
        self.is_updating = False
        self.btn_check.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_signal.emit("Операция отменена")
        self.add_log("Операция отменена пользователем")
        self.launch_application()

    def start_automatic_check(self):
        """Начинает автоматическую проверку"""
        self.is_updating = True
        self.btn_check.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        # Запускаем в отдельном потоке
        thread = threading.Thread(target=self.check_and_update)
        thread.daemon = True
        thread.start()

    def check_and_update(self):
        """Проверяет и обновляет приложение"""
        try:
            self.status_signal.emit("Проверка обновлений...")
            self.progress_signal.emit(10, "Проверка GitHub")
            self.add_log("Проверка обновлений...")

            # Проверяем версию на GitHub
            github_version = self.get_github_version()

            if github_version:
                self.add_log(f"Локальная версия: {self.current_version}")
                self.add_log(f"Версия на GitHub: {github_version}")

                if github_version == self.current_version:
                    self.add_log("У вас актуальная версия")
                    self.complete_signal.emit(True, "Версия актуальна")
                    return

                self.add_log(f"Доступно обновление: {self.current_version} → {github_version}")
                self.status_signal.emit("Скачивание обновлений...")
                self.progress_signal.emit(30, "Скачивание файлов")

                # Обновляем приложение
                if self.update_application(github_version):
                    self.complete_signal.emit(True, "Обновление завершено")
                else:
                    self.complete_signal.emit(False, "Ошибка обновления")
            else:
                self.add_log("Не удалось проверить обновления")
                self.complete_signal.emit(True, "Проверка завершена")

        except Exception as e:
            self.add_log(f"Ошибка: {str(e)}")
            self.complete_signal.emit(False, f"Ошибка: {str(e)}")

    def get_github_version(self):
        """Получает версию с GitHub"""
        try:
            version_url = "https://raw.githubusercontent.com/DenisASUTP/OP_4/main/version.txt"
            response = requests.get(version_url, timeout=10)
            if response.status_code == 200:
                return response.text.strip()
        except Exception as e:
            self.add_log(f"Ошибка подключения: {e}")
        return None

    def update_application(self, github_version):
        """Обновляет приложение"""
        try:
            # Файлы для обновления
            files_to_update = ['app.py', 'requirements.txt']

            # Скачиваем файлы
            for filename in files_to_update:
                self.add_log(f"Скачиваю {filename}...")

                if not self.download_file(filename):
                    self.add_log(f"Ошибка скачивания {filename}")
                    return False

            # Обновляем версию
            try:
                with open("version.txt", 'w', encoding='utf-8') as f:
                    f.write(github_version)
                self.current_version = github_version
                self.version_signal.emit(f"Версия: {self.current_version}")
            except:
                pass

            # Устанавливаем зависимости
            self.status_signal.emit("Установка модулей...")
            self.progress_signal.emit(80, "Установка зависимостей")

            if os.path.exists("requirements.txt"):
                self.add_log("Установка зависимостей...")
                if self.install_requirements():
                    self.add_log("Зависимости установлены")
                else:
                    self.add_log("Ошибка установки зависимостей")

            self.progress_signal.emit(100, "Готово")
            return True

        except Exception as e:
            self.add_log(f"Ошибка обновления: {e}")
            return False

    def download_file(self, filename):
        """Скачивает файл с GitHub"""
        try:
            url = f"https://raw.githubusercontent.com/DenisASUTP/OP_4/main/{filename}"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return True
        except:
            pass
        return False

    def install_requirements(self):
        """Устанавливает зависимости"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return True
        except:
            return False

    @pyqtSlot(bool, str)
    def on_operation_complete(self, success, message):
        """Обработчик завершения операции"""
        self.is_updating = False
        self.btn_check.setEnabled(True)
        self.btn_cancel.setEnabled(False)

        if success:
            self.status_signal.emit("Готово")
            self.add_log(f"✓ {message}")
        else:
            self.status_signal.emit("Ошибка")
            self.add_log(f"✗ {message}")

        # Запускаем приложение через секунду
        QTimer.singleShot(1000, self.launch_application)

    @pyqtSlot(str)
    def add_log(self, message):
        """Добавляет сообщение в лог"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
        # Автопрокрутка
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)

    @pyqtSlot(int, str)
    def update_progress(self, value, text):
        """Обновляет прогресс"""
        self.progress_bar.setValue(value)
        self.status_label.setText(text)

    @pyqtSlot(str)
    def update_status(self, text):
        """Обновляет статус"""
        self.status_label.setText(text)

    @pyqtSlot(str)
    def update_version_display(self, text):
        """Обновляет отображение версии"""
        self.version_label.setText(text)

    def launch_application(self):
        """Запускает основное приложение"""
        if not os.path.exists("app.py"):
            self.add_log("❌ Ошибка: Файл app.py не найден!")
            QMessageBox.critical(self, "Ошибка", "Файл app.py не найден!")
            return

        self.add_log("🚀 Запуск приложения...")

        try:
            # Закрываем лаунчер
            self.hide()

            # Запускаем приложение
            subprocess.Popen([sys.executable, "app.py"])

            # Закрываем лаунчер через секунду
            QTimer.singleShot(1000, QApplication.instance().quit)

        except Exception as e:
            self.add_log(f"❌ Ошибка запуска: {e}")
            QMessageBox.critical(self, "Ошибка запуска", f"Не удалось запустить приложение:\n{str(e)}")


def check_requirements():
    """Проверяет наличие необходимых модулей"""
    try:
        import PyQt5
        import requests
        return True
    except ImportError as e:
        print(f"❌ Отсутствует модуль: {e}")
        print("📦 Пробую установить необходимые модули...")

        try:
            # Пробуем установить requests
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            print("✅ Модуль requests установлен")

            # Перезапускаем лаунчер
            print("🔄 Перезапуск лаунчера...")
            subprocess.Popen([sys.executable, __file__])
            return False
        except:
            print("❌ Не удалось установить модули")
            print("   Установите вручную: pip install PyQt5 requests")
            input("Нажмите Enter для выхода...")
            return False


def main():
    """Основная функция"""
    # Проверяем наличие модулей
    if not check_requirements():
        return

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Устанавливаем темную палитру
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(45, 45, 45))
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor(255, 107, 0))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    launcher = SmartTrainerLauncher()
    launcher.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()