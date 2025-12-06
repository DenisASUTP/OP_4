#!/usr/bin/env python3
import sys
import os
import sqlite3
import requests
import subprocess
import threading
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                             QHBoxLayout, QLabel, QStackedWidget, QListWidget,
                             QListWidgetItem, QProgressBar, QMessageBox, QScrollArea,
                             QGridLayout, QFrame, QDialog, QLineEdit, QFormLayout)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QIntValidator


# Заглушка для Modbus RTU
class ModbusSimulator:
    def __init__(self):
        self.current_force = 0
        self.target_force = 0
        self.position = 0
        self.is_connected = True

    def read_force_sensor(self):
        self.current_force += (self.target_force - self.current_force) * 0.1
        return self.current_force + (0.5 - (datetime.now().microsecond % 1000) / 1000.0)

    def set_target_force(self, force):
        self.target_force = force

    def get_position(self):
        self.position += 0.1
        return self.position % 100


# База данных пользователей
class UserDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('users.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rf_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                height INTEGER NOT NULL,
                fitness_level INTEGER NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                exercise_name TEXT NOT NULL,
                repetitions INTEGER,
                intensity REAL,
                duration INTEGER,
                workout_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        self.conn.commit()

    def add_user(self, rf_id, first_name, last_name, height, fitness_level):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (rf_id, first_name, last_name, height, fitness_level)
                VALUES (?, ?, ?, ?, ?)
            ''', (rf_id, first_name, last_name, height, fitness_level))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def find_user_by_rfid(self, rf_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE rf_id = ?
        ''', (rf_id,))
        return cursor.fetchone()

    def save_workout(self, user_id, exercise_name, repetitions, intensity, duration):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO workouts (user_id, exercise_name, repetitions, intensity, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, exercise_name, repetitions, intensity, duration))
        self.conn.commit()


# Диалог регистрации нового пользователя
class RegistrationDialog(QDialog):
    def __init__(self, rf_id, parent=None):
        super().__init__(parent)
        self.rf_id = rf_id
        self.setWindowTitle("Регистрация нового пользователя")
        self.setFixedSize(400, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
                color: white;
            }
            QLabel {
                color: #CCCCCC;
            }
            QLineEdit {
                background-color: #3D3D3D;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #FF6B00;
            }
        """)

        layout = QVBoxLayout()

        title = QLabel(f"Регистрация карты: {rf_id}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #FF6B00;")
        title.setAlignment(Qt.AlignCenter)

        form_layout = QFormLayout()

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("Введите имя")

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Введите фамилию")

        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("Рост в см")
        self.height_input.setValidator(QIntValidator(100, 250))

        self.fitness_input = QLineEdit()
        self.fitness_input.setPlaceholderText("Уровень (1-6)")
        self.fitness_input.setValidator(QIntValidator(1, 6))

        form_layout.addRow("Имя:", self.first_name_input)
        form_layout.addRow("Фамилия:", self.last_name_input)
        form_layout.addRow("Рост (см):", self.height_input)
        form_layout.addRow("Уровень подготовки (1-6):", self.fitness_input)

        buttons_layout = QHBoxLayout()

        self.btn_register = QPushButton("Зарегистрировать")
        self.btn_register.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        self.btn_register.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        buttons_layout.addWidget(self.btn_register)
        buttons_layout.addWidget(self.btn_cancel)

        layout.addWidget(title)
        layout.addLayout(form_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        # Проверяем заполнение полей
        self.first_name_input.textChanged.connect(self.check_fields)
        self.last_name_input.textChanged.connect(self.check_fields)
        self.height_input.textChanged.connect(self.check_fields)
        self.fitness_input.textChanged.connect(self.check_fields)
        self.check_fields()

    def check_fields(self):
        all_filled = (self.first_name_input.text().strip() != "" and
                      self.last_name_input.text().strip() != "" and
                      self.height_input.text().strip() != "" and
                      self.fitness_input.text().strip() != "")
        self.btn_register.setEnabled(all_filled)

    def get_user_data(self):
        return {
            'rf_id': self.rf_id,
            'first_name': self.first_name_input.text().strip(),
            'last_name': self.last_name_input.text().strip(),
            'height': int(self.height_input.text()),
            'fitness_level': int(self.fitness_input.text())
        }


# Диалог обновления
class UpdateDialog(QDialog):
    update_progress = pyqtSignal(int)
    update_message = pyqtSignal(str)
    update_finished = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обновление приложения")
        self.setFixedSize(400, 200)
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D2D;
                color: white;
            }
        """)

        layout = QVBoxLayout()

        self.title_label = QLabel("Проверка обновлений...")
        self.title_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.title_label.setStyleSheet("color: #FF6B00;")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.message_label = QLabel("Подключение к репозиторию...")
        self.message_label.setAlignment(Qt.AlignCenter)

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
            }
        """)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

        self.update_progress.connect(self.progress_bar.setValue)
        self.update_message.connect(self.message_label.setText)
        self.update_finished.connect(self.on_update_finished)

        self.is_cancelled = False

    def on_update_finished(self, success):
        if success:
            self.title_label.setText("Обновление завершено!")
            self.message_label.setText("Приложение будет перезапущено")
            self.cancel_button.setText("Закрыть")
        else:
            self.title_label.setText("Ошибка обновления")
            self.cancel_button.setText("Закрыть")

    def reject(self):
        self.is_cancelled = True
        super().reject()


# Экран приветствия
class WelcomeScreen(QWidget):
    def __init__(self, user_data, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.user_data = user_data
        self.initUI()

        # Автоматический переход через 3 секунды
        QTimer.singleShot(3000, self.go_to_exercises)

    def initUI(self):
        layout = QVBoxLayout()

        # Приветствие
        welcome_text = QLabel(f"Здравствуйте, {self.user_data['first_name']} {self.user_data['last_name']}!")
        welcome_text.setFont(QFont("Arial", 24, QFont.Bold))
        welcome_text.setStyleSheet("color: #FF6B00;")
        welcome_text.setAlignment(Qt.AlignCenter)

        # Комплимент
        compliment = QLabel("Вы как всегда отлично выглядите!")
        compliment.setFont(QFont("Arial", 18))
        compliment.setStyleSheet("color: #4CAF50;")
        compliment.setAlignment(Qt.AlignCenter)

        # Информация о пользователе
        info_text = QLabel(f"Рост: {self.user_data['height']} см | Уровень: {self.user_data['fitness_level']}")
        info_text.setFont(QFont("Arial", 14))
        info_text.setStyleSheet("color: #CCCCCC;")
        info_text.setAlignment(Qt.AlignCenter)

        # Инструкция
        instruction = QLabel("Переход к выбору упражнений через 3 секунды...")
        instruction.setFont(QFont("Arial", 12))
        instruction.setStyleSheet("color: #888;")
        instruction.setAlignment(Qt.AlignCenter)

        # Кнопка перехода сейчас
        btn_now = QPushButton("Начать сейчас")
        btn_now.setFont(QFont("Arial", 14))
        btn_now.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 5px;
                margin: 20px;
            }
            QPushButton:pressed {
                background-color: #45a049;
            }
        """)
        btn_now.clicked.connect(self.go_to_exercises)

        layout.addStretch()
        layout.addWidget(welcome_text)
        layout.addWidget(compliment)
        layout.addWidget(info_text)
        layout.addStretch()
        layout.addWidget(instruction)
        layout.addWidget(btn_now)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #1E1E1E;")

    def go_to_exercises(self):
        if self.parent:
            self.parent.show_exercise_screen()


# Виджет для отображения упражнения с картинкой
class ExerciseWidget(QFrame):
    def __init__(self, exercise, parent=None):
        super().__init__(parent)
        self.exercise = exercise
        self.parent = parent
        self.initUI()

    def initUI(self):
        self.setStyleSheet("""
            ExerciseWidget {
                background-color: #2D2D2D;
                border: 2px solid #444;
                border-radius: 15px;
                margin: 5px;
            }
            ExerciseWidget:hover {
                border: 2px solid #FF6B00;
                background-color: #3D3D3D;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout()
        # layout.setAlignment(Qt.AlignCenter)  # Центрируем содержимое внутри виджета
        layout.setSpacing(8)

        title = QLabel(self.exercise["name"])
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: #FF6B00; margin: 8px;")
        title.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)  # Это должно быть уже установлено
        self.image_label.setMinimumSize(250, 160)
        self.image_label.setMaximumSize(250, 160)
        self.image_label.setStyleSheet("""
            background-color: #1E1E1E;
            border: 1px solid #555;
            border-radius: 10px;
        """)

        self.load_image()

        description = QLabel(self.exercise["description"])
        description.setFont(QFont("Arial", 11))
        description.setStyleSheet("color: #CCCCCC; margin: 8px;")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignCenter)

        intensity = QLabel(f"Интенсивность: {self.exercise['intensity']}%")
        intensity.setFont(QFont("Arial", 11, QFont.Bold))
        intensity.setStyleSheet("color: #4CAF50; margin: 5px;")
        intensity.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(self.image_label)
        layout.addWidget(description)
        layout.addWidget(intensity)

        self.setLayout(layout)

    def load_image(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(script_dir, "images")
        image_path = os.path.join(images_dir, self.exercise["image"])

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Масштабируем с сохранением пропорций
                scaled_pixmap = pixmap.scaled(240, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # Создаем новый QPixmap с прозрачным фоном для центрирования
                centered_pixmap = QPixmap(240, 150)
                centered_pixmap.fill(Qt.transparent)

                # Рассчитываем позицию для центрирования
                x_offset = (240 - scaled_pixmap.width()) // 2
                y_offset = (150 - scaled_pixmap.height()) // 2

                painter = QPainter(centered_pixmap)
                painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
                painter.end()

                self.image_label.setPixmap(centered_pixmap)
            else:
                # Если ошибка загрузки, показываем текст по центру
                self.image_label.setText("Ошибка\nзагрузки\nизображения")
                self.image_label.setAlignment(Qt.AlignCenter)
        else:
            # Если файл не найден, показываем текст по центру
            self.image_label.setText("Изображение\nне найдено")
            self.image_label.setAlignment(Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.parent:
                self.parent.start_exercise(self.exercise)
        super().mousePressEvent(event)


# Основной класс приложения
class SmartTrainerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db = UserDatabase()
        self.modbus = ModbusSimulator()
        self.current_user = None
        self.current_exercise = None
        self.current_user_data = None
        self.current_rfid_input = ""  # Текущий ввод RFID
        self.rfid_input_complete = False  # Флаг завершения ввода

        # Упражнения с картинками и описаниями
        self.exercises = [
            {
                "name": "Верхняя тяга к груди",
                "image": "Chest cravings.jpg",
                "intensity": 50,
                "description": "Развивает мышцы спины и плечевого пояса"
            },
            {
                "name": "Верхняя тяга за голову",
                "image": "Chest cravings.jpg",
                "intensity": 45,
                "description": "Укрепляет верхнюю часть спины"
            },
            {
                "name": "Бабочка",
                "image": "Butterfly.jpg",
                "intensity": 55,
                "description": "Развивает и растягивает грудные мышцы"
            },
            {
                "name": "Жим от груди",
                "image": "Chest press.jpg",
                "intensity": 60,
                "description": "Укрепляет грудные мышцы и трицепсы"
            },
            {
                "name": "Разгибания ног",
                "image": "Leg extensions.jpg",
                "intensity": 65,
                "description": "Тренирует переднюю поверхность бедра"
            },
            {
                "name": "Сгибания ног",
                "image": "bending of the legs.jpg",
                "intensity": 50,
                "description": "Развивает заднюю поверхность бедра"
            },
            {
                "name": "Разгибания рук",
                "image": "Triceps.jpg",
                "intensity": 30,
                "description": "Развивает трицепсы"
            },
            {
                "name": "Сгибания рук",
                "image": "Bicep Deadlift.jpg",
                "intensity": 45,
                "description": "Развивает бицепсы"
            },
            {
                "name": "Тяга к пояснице",
                "image": "Belt pull.jpg",
                "intensity": 35,
                "description": "Развивает широчайшие мышцы спины"
            },
            {
                "name": "Отведите ноги назад",
                "image": "Swing your legs back.jpg",
                "intensity": 25,
                "description": "Развивает ягодицы, бицепс бедра и спину"
            },
            {
                "name": "Отведите ноги в сторону 1",
                "image": "Swing your legs to the side 1.jpg",
                "intensity": 25,
                "description": "Развивает внешнюю часть бедра"
            },
            {
                "name": "Отведите ноги в сторону 2",
                "image": "Swing your legs to the side 2.jpg",
                "intensity": 25,
                "description": "Развивает внутреннюю часть бедра"
            }

        ]

        self.initUI()

        # Таймер для обновления данных
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.update_sensor_data)
        self.data_timer.start(100)

    def initUI(self):
        self.setWindowTitle("Smart Trainer - Orange Pi")
        self.setGeometry(0, 0, 600, 1024)

        # Основной стек экранов
        self.stacked_widget = QStackedWidget()

        # Экран ввода RFID
        self.auth_screen = self.create_auth_screen()

        # Экран приветствия
        self.welcome_screen = None

        # Экран выбора упражнений
        self.exercise_screen = self.create_exercise_screen()

        # Экран выполнения упражнения
        self.workout_screen = self.create_workout_screen()

        self.stacked_widget.addWidget(self.auth_screen)
        self.stacked_widget.addWidget(self.exercise_screen)
        self.stacked_widget.addWidget(self.workout_screen)

        layout = QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)

        self.show_auth_screen()

    def create_auth_screen(self):
        screen = QWidget()
        layout = QVBoxLayout()

        # Заголовок
        title = QLabel("SMART TRAINER")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #FF6B00; margin: 40px;")

        # Иконка RFID
        rfid_icon = QLabel()
        rfid_pixmap = QPixmap(200, 200)
        rfid_pixmap.fill(Qt.transparent)
        painter = QPainter(rfid_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(255, 107, 0))
        painter.drawRect(50, 50, 100, 150)
        painter.setBrush(QColor(200, 200, 200))
        painter.drawRect(70, 180, 60, 20)
        painter.end()
        rfid_icon.setPixmap(rfid_pixmap)
        rfid_icon.setAlignment(Qt.AlignCenter)

        # Инструкция
        instruction = QLabel("Поднесите RFID карту или введите номер вручную 1")
        instruction.setFont(QFont("Arial", 16))
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setStyleSheet("color: white; margin: 20px;")

        # Поле ввода RFID (невидимое - для фокуса)
        self.rfid_hidden_input = QLineEdit()
        self.rfid_hidden_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: transparent;
                border: none;
                height: 1px;
                width: 1px;
            }
        """)
        self.rfid_hidden_input.setMaxLength(10)
        self.rfid_hidden_input.textChanged.connect(self.on_rfid_input_changed)
        self.rfid_hidden_input.setFocus()

        # Отображение ввода в углу
        self.input_display = QLabel("Ввод: ")
        self.input_display.setFont(QFont("Arial", 10))
        self.input_display.setStyleSheet("color: #888888;")
        self.input_display.setAlignment(Qt.AlignRight)
        self.input_display.setContentsMargins(0, 0, 20, 0)

        # Статус
        self.auth_status = QLabel("Ожидание карты...")
        self.auth_status.setFont(QFont("Arial", 14))
        self.auth_status.setAlignment(Qt.AlignCenter)
        self.auth_status.setStyleSheet("color: #CCCCCC; margin: 20px;")

        # Индикатор ввода
        self.input_indicator = QLabel("▢▢▢▢▢▢▢▢▢▢")
        self.input_indicator.setFont(QFont("Arial", 24, QFont.Bold))
        self.input_indicator.setAlignment(Qt.AlignCenter)
        self.input_indicator.setStyleSheet("color: #FF6B00; margin: 10px;")

        # Кнопка проверки обновлений
        btn_update = QPushButton("Проверить обновления")
        btn_update.setFont(QFont("Arial", 12))
        btn_update.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                margin: 10px;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        btn_update.clicked.connect(self.check_for_updates)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(rfid_icon)
        layout.addWidget(instruction)
        layout.addWidget(self.input_indicator)
        layout.addWidget(self.auth_status)
        layout.addStretch()
        layout.addWidget(btn_update)
        layout.addWidget(self.input_display)
        layout.addWidget(self.rfid_hidden_input)

        screen.setLayout(layout)
        screen.setStyleSheet("background-color: #1E1E1E;")

        # Устанавливаем фокус на поле ввода
        QTimer.singleShot(100, lambda: self.rfid_hidden_input.setFocus())

        return screen

    def on_rfid_input_changed(self, text):
        # Обновляем отображение ввода
        self.current_rfid_input = text
        self.input_display.setText(f"Ввод: {text}")

        # Обновляем индикатор
        filled = len(text)
        indicator = "█" * filled + "▢" * (10 - filled)
        self.input_indicator.setText(indicator)

        # Если введено 10 цифр - обрабатываем
        if len(text) == 10 and text.isdigit():
            self.rfid_input_complete = True
            self.auth_status.setText("Обработка карты...")
            QTimer.singleShot(500, lambda: self.process_rfid(text))

    def keyPressEvent(self, event):
        # Перехватываем нажатия клавиш для всего приложения
        key = event.key()

        # Цифровые клавиши
        if Qt.Key_0 <= key <= Qt.Key_9:
            digit = str(key - Qt.Key_0)
            current_text = self.rfid_hidden_input.text()
            if len(current_text) < 10:
                self.rfid_hidden_input.setText(current_text + digit)

        # Удаление (Backspace)
        elif key == Qt.Key_Backspace:
            current_text = self.rfid_hidden_input.text()
            if current_text:
                self.rfid_hidden_input.setText(current_text[:-1])

        # Enter (если вдруг нужно подтвердить)
        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            if len(self.current_rfid_input) == 10:
                self.process_rfid(self.current_rfid_input)

        # ESC - очистить ввод
        elif key == Qt.Key_Escape:
            self.rfid_hidden_input.clear()
            self.auth_status.setText("Ожидание карты...")

        else:
            super().keyPressEvent(event)

    def process_rfid(self, rfid):
        # Очищаем ввод после обработки
        self.rfid_hidden_input.clear()
        self.rfid_input_complete = False

        user = self.db.find_user_by_rfid(rfid)

        if user:
            # Пользователь найден
            self.current_user = user
            self.current_user_data = {
                'rf_id': user[1],
                'first_name': user[2],
                'last_name': user[3],
                'height': user[4],
                'fitness_level': user[5]
            }
            self.auth_status.setText("Пользователь найден!")
            QTimer.singleShot(1000, self.show_welcome_screen)
        else:
            # Пользователь не найден - регистрация
            self.auth_status.setText("Пользователь не найден")
            QTimer.singleShot(1000, lambda: self.register_new_user(rfid))

    def register_new_user(self, rfid):
        dialog = RegistrationDialog(rfid, self)
        if dialog.exec_() == QDialog.Accepted:
            user_data = dialog.get_user_data()
            if self.db.add_user(
                    user_data['rf_id'],
                    user_data['first_name'],
                    user_data['last_name'],
                    user_data['height'],
                    user_data['fitness_level']
            ):
                self.current_user_data = user_data
                self.auth_status.setText("Пользователь зарегистрирован!")
                QTimer.singleShot(1000, self.show_welcome_screen)
            else:
                self.auth_status.setText("Ошибка регистрации")
        else:
            self.auth_status.setText("Ожидание карты...")
            self.rfid_hidden_input.setFocus()

    def show_welcome_screen(self):
        if self.current_user_data:
            # Удаляем старый экран приветствия если есть
            if self.welcome_screen:
                self.welcome_screen.setParent(None)

            # Создаем новый экран приветствия
            self.welcome_screen = WelcomeScreen(self.current_user_data, self)

            # Добавляем в стек если еще не добавлен
            for i in range(self.stacked_widget.count()):
                if self.stacked_widget.widget(i) == self.welcome_screen:
                    break
            else:
                self.stacked_widget.insertWidget(1, self.welcome_screen)

            # Показываем экран приветствия
            self.stacked_widget.setCurrentWidget(self.welcome_screen)

    def create_exercise_screen(self):
        screen = QWidget()
        main_layout = QVBoxLayout()

        self.user_info = QLabel("Пользователь: ")
        self.user_info.setFont(QFont("Arial", 16, QFont.Bold))
        self.user_info.setAlignment(Qt.AlignCenter)
        self.user_info.setStyleSheet("color: #FF6B00; margin: 10px;")

        instruction = QLabel("Выберите упражнение (нажмите на картинку):")
        instruction.setFont(QFont("Arial", 14))
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setStyleSheet("color: #CCCCCC; margin: 10px;")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1E1E1E;
            }
            QScrollBar:vertical {
                background-color: #2D2D2D;
                width: 15px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #FF6B00;
                border-radius: 7px;
            }
        """)

        exercises_widget = QWidget()
        self.exercises_layout = QGridLayout()
        self.exercises_layout.setSpacing(8)
        self.exercises_layout.setContentsMargins(15, 15, 15, 15)

        exercises_widget.setLayout(self.exercises_layout)
        scroll_area.setWidget(exercises_widget)

        btn_back = QPushButton("Выйти")
        btn_back.setFont(QFont("Arial", 14))
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 5px;
                margin: 10px;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)
        btn_back.clicked.connect(self.show_auth_screen)

        main_layout.addWidget(self.user_info)
        main_layout.addWidget(instruction)
        main_layout.addWidget(scroll_area, 1)
        main_layout.addWidget(btn_back)

        screen.setLayout(main_layout)
        screen.setStyleSheet("background-color: #1E1E1E; color: white;")
        return screen

    def create_workout_screen(self):
        screen = QWidget()
        layout = QVBoxLayout()

        self.exercise_title = QLabel("Упражнение")
        self.exercise_title.setFont(QFont("Arial", 20, QFont.Bold))
        self.exercise_title.setAlignment(Qt.AlignCenter)
        self.exercise_title.setStyleSheet("color: #FF6B00; margin: 10px;")

        self.exercise_image = QLabel()
        self.exercise_image.setAlignment(Qt.AlignCenter)
        self.exercise_image.setMinimumSize(400, 300)
        self.exercise_image.setStyleSheet("""
            border: 2px solid #444; 
            border-radius: 10px;
            background-color: #2D2D2D;
            color: white;
            font-size: 14px;
        """)

        metrics_layout = QVBoxLayout()

        force_layout = QHBoxLayout()
        force_label = QLabel("Сила:")
        force_label.setFont(QFont("Arial", 14))
        self.force_value = QLabel("0 Н")
        self.force_value.setFont(QFont("Arial", 14, QFont.Bold))
        self.force_value.setStyleSheet("color: #FF6B00;")
        force_layout.addWidget(force_label)
        force_layout.addStretch()
        force_layout.addWidget(self.force_value)

        self.force_progress = QProgressBar()
        self.force_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 5px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #FF6B00;
            }
        """)

        reps_layout = QHBoxLayout()
        reps_label = QLabel("Повторения:")
        reps_label.setFont(QFont("Arial", 14))
        self.reps_value = QLabel("0")
        self.reps_value.setFont(QFont("Arial", 14, QFont.Bold))
        self.reps_value.setStyleSheet("color: #FF6B00;")
        reps_layout.addWidget(reps_label)
        reps_layout.addStretch()
        reps_layout.addWidget(self.reps_value)

        intensity_layout = QHBoxLayout()
        intensity_label = QLabel("Интенсивность:")
        intensity_label.setFont(QFont("Arial", 14))
        self.intensity_value = QLabel("0%")
        self.intensity_value.setFont(QFont("Arial", 14, QFont.Bold))
        self.intensity_value.setStyleSheet("color: #FF6B00;")
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addStretch()
        intensity_layout.addWidget(self.intensity_value)

        metrics_layout.addLayout(force_layout)
        metrics_layout.addWidget(self.force_progress)
        metrics_layout.addLayout(reps_layout)
        metrics_layout.addLayout(intensity_layout)

        buttons_layout = QHBoxLayout()

        btn_stop = QPushButton("Стоп")
        btn_stop.setFont(QFont("Arial", 14))
        btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #D32F2F;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #F44336;
            }
        """)
        btn_stop.clicked.connect(self.stop_workout)

        btn_back = QPushButton("Назад")
        btn_back.setFont(QFont("Arial", 14))
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)
        btn_back.clicked.connect(self.show_exercise_screen)

        buttons_layout.addWidget(btn_stop)
        buttons_layout.addWidget(btn_back)

        layout.addWidget(self.exercise_title)
        layout.addWidget(self.exercise_image)
        layout.addLayout(metrics_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        screen.setLayout(layout)
        screen.setStyleSheet("background-color: #1E1E1E; color: white;")
        return screen

    def show_auth_screen(self):
        self.stacked_widget.setCurrentIndex(0)
        self.current_user = None
        self.current_user_data = None
        self.rfid_hidden_input.clear()
        self.rfid_hidden_input.setFocus()
        self.auth_status.setText("Ожидание карты...")
        self.input_display.setText("Ввод: ")

    def show_exercise_screen(self):
        if self.current_user_data:
            # Обновляем информацию о пользователе
            self.user_info.setText(
                f"Пользователь: {self.current_user_data['first_name']} {self.current_user_data['last_name']} | "
                f"Рост: {self.current_user_data['height']}см | "
                f"Уровень: {self.current_user_data['fitness_level']}"
            )

            # Очищаем старые упражнения
            for i in reversed(range(self.exercises_layout.count())):
                self.exercises_layout.itemAt(i).widget().setParent(None)

            # Добавляем упражнения
            row = 0
            for exercise in self.exercises:
                exercise_widget = ExerciseWidget(exercise, self)
                self.exercises_layout.addWidget(exercise_widget, row, 0)
                row += 1

            self.stacked_widget.setCurrentWidget(self.exercise_screen)

    def show_workout_screen(self):
        self.stacked_widget.setCurrentWidget(self.workout_screen)

    def start_exercise(self, exercise):
        self.current_exercise = exercise
        self.start_workout(exercise)

    def start_workout(self, exercise):
        self.exercise_title.setText(exercise["name"])
        self.workout_reps = 0
        self.workout_start_time = datetime.now()

        script_dir = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(script_dir, "images")
        image_path = os.path.join(images_dir, exercise["image"])

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(350, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.exercise_image.setPixmap(scaled_pixmap)
            else:
                self.exercise_image.setText("Ошибка загрузки изображения")
        else:
            self.exercise_image.setText(f"Изображение не найдено:\n{exercise['image']}")

        self.modbus.set_target_force(exercise["intensity"])
        self.show_workout_screen()

    def update_sensor_data(self):
        if self.stacked_widget.currentIndex() == 3:  # Индекс экрана тренировки
            force = self.modbus.read_force_sensor()
            position = self.modbus.get_position()

            self.force_value.setText(f"{force:.1f} Н")
            self.force_progress.setValue(int(force))
            self.force_progress.setMaximum(100)

            if position < 5 and not hasattr(self, 'last_position'):
                self.workout_reps += 1
                self.reps_value.setText(str(self.workout_reps))

            self.intensity_value.setText(f"{self.current_exercise['intensity']}%")

    def stop_workout(self):
        if self.current_user and self.current_exercise:
            duration = (datetime.now() - self.workout_start_time).seconds
            self.db.save_workout(
                self.current_user[0],
                self.current_exercise["name"],
                self.workout_reps,
                self.current_exercise["intensity"],
                duration
            )

            QMessageBox.information(self, "Тренировка завершена",
                                    f"Упражнение: {self.current_exercise['name']}\n"
                                    f"Повторений: {self.workout_reps}\n"
                                    f"Длительность: {duration} сек")

        self.show_exercise_screen()

    def check_for_updates(self):
        """Проверка обновлений"""
        dialog = UpdateDialog(self)
        dialog.show()

        # Запускаем проверку в отдельном потоке
        thread = threading.Thread(target=self.perform_update, args=(dialog,))
        thread.daemon = True
        thread.start()

        if dialog.exec_() == QDialog.Accepted and not dialog.is_cancelled:
            # Перезапуск приложения после успешного обновления
            QMessageBox.information(self, "Перезапуск", "Приложение будет перезапущено")
            self.restart_application()

    def perform_update(self, dialog):
        """Выполнение обновления в отдельном потоке БЕЗ Git"""
        try:
            dialog.update_message.emit("Проверка подключения к GitHub...")
            dialog.update_progress.emit(10)

            # Базовый URL репозитория
            repo_url = "https://github.com/DenisASUTP/OP_4"

            # Список файлов для обновления
            files_to_update = [
                'app.py',
                'requirements.txt'
            ]

            # Проверяем доступность репозитория
            test_url = f"{repo_url}/raw/main/app.py"
            response = requests.get(test_url, timeout=10)
            if response.status_code != 200:
                dialog.update_message.emit("Ошибка подключения к GitHub")
                dialog.update_progress.emit(0)
                dialog.update_finished.emit(False)
                return

            dialog.update_message.emit("Скачивание обновлений...")
            dialog.update_progress.emit(30)

            # Получаем текущую директорию
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Скачиваем и обновляем каждый файл
            for i, filename in enumerate(files_to_update):
                dialog.update_message.emit(f"Обновление {filename}...")

                url = f"{repo_url}/raw/main/{filename}"
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    # Сохраняем новый файл
                    file_path = os.path.join(current_dir, filename)

                    # Делаем резервную копию старого файла
                    if os.path.exists(file_path):
                        backup_path = file_path + ".backup"
                        import shutil
                        shutil.copy2(file_path, backup_path)

                    # Записываем новый файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)

                    progress = 30 + ((i + 1) * 70 // len(files_to_update))
                    dialog.update_progress.emit(progress)
                else:
                    dialog.update_message.emit(f"Ошибка скачивания {filename}")
                    dialog.update_progress.emit(0)
                    dialog.update_finished.emit(False)
                    return

            dialog.update_message.emit("Обновление завершено!")
            dialog.update_progress.emit(100)
            dialog.update_finished.emit(True)

        except Exception as e:
            dialog.update_message.emit(f"Ошибка: {str(e)}")
            dialog.update_progress.emit(0)
            dialog.update_finished.emit(False)

    def restart_application(self):
        """Перезапуск приложения"""
        QApplication.quit()
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit()


def initialize_test_data():
    db = UserDatabase()

    test_users = [
        ("1234567890", "Иван", "Петров", 180, 3),
        ("0987654321", "Мария", "Сидорова", 165, 2),
        ("1122334455", "Алексей", "Павлов", 175, 4)
    ]

    for user in test_users:
        db.add_user(*user)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(script_dir, "images")

    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
        print("Создана папка images/ - добавьте туда изображения упражнений")
    else:
        available_images = os.listdir(images_dir)
        print(f"Доступные изображения: {available_images}")


if __name__ == "__main__":
    initialize_test_data()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = SmartTrainerApp()
    window.show()

    sys.exit(app.exec_())