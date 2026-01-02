#!/usr/bin/env python3
import sys
import os
import sqlite3
from datetime import datetime

# ==============================
# УНИВЕРСАЛЬНАЯ НАСТРОЙКА QT
# ==============================
if sys.platform == "win32":
    # Для WINDOWS
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    print(f"Windows: Используем платформу 'windows'")

    # Ищем плагины Qt
    try:
        from PySide6 import QtCore

        qt_dir = os.path.dirname(QtCore.__file__)
        plugin_path = os.path.join(qt_dir, "plugins", "platforms")

        if os.path.exists(plugin_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
            print(f"Windows: Путь к плагинам: {plugin_path}")
    except ImportError:
        pass

elif sys.platform == "linux":
    # Для LINUX / ORANGE PI
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    print(f"Linux: Используем платформу 'xcb'")

    # Для Orange Pi с GUI
    if 'DISPLAY' not in os.environ:
        os.environ['DISPLAY'] = ':0'

# Импорты PySide6 ПОСЛЕ настройки переменных
from PySide6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                               QHBoxLayout, QLabel, QStackedWidget, QListWidget,
                               QListWidgetItem, QProgressBar, QMessageBox, QScrollArea,
                               QGridLayout, QFrame, QDialog, QLineEdit, QFormLayout)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QIntValidator, QBrush, QPen


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
                background-color: #F0F0F0;
                color: #333333;
            }
            QLabel {
                color: #666666;
                font-weight: 500;
            }
            QLineEdit {
                background-color: white;
                color: #333333;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: #21A038;
            }
            QLineEdit:focus {
                border: 2px solid #21A038;
                background-color: white;
            }
            QLineEdit:hover {
                border: 2px solid #B0B0B0;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        title = QLabel(f"Регистрация карты: {rf_id}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #21A038;")
        title.setAlignment(Qt.AlignCenter)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(20, 0, 20, 0)

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
        buttons_layout.setSpacing(15)

        self.btn_register = QPushButton("Зарегистрировать")
        self.btn_register.setStyleSheet("""
            QPushButton {
                background-color: #21A038;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1C8A30;
            }
            QPushButton:pressed {
                background-color: #187C28;
            }
            QPushButton:disabled {
                background-color: #E0E0E0;
                color: #999999;
            }
        """)
        self.btn_register.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                color: #666666;
                border: 2px solid #E0E0E0;
                padding: 12px 25px;
                border-radius: 8px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
                border-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #D8D8D8;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        buttons_layout.addWidget(self.btn_register)
        buttons_layout.addWidget(self.btn_cancel)

        layout.addWidget(title)
        layout.addSpacing(10)
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
        layout.setContentsMargins(30, 40, 30, 40)
        layout.setSpacing(20)

        # Логотип/иконка
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_pixmap = QPixmap(120, 120)
        logo_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(logo_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(33, 160, 56))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(10, 10, 100, 100)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(35, 35, 50, 50)
        painter.end()
        logo_label.setPixmap(logo_pixmap)

        # Приветствие
        welcome_text = QLabel(f"Здравствуйте, {self.user_data['first_name']} {self.user_data['last_name']}!")
        welcome_text.setFont(QFont("Arial", 22, QFont.Bold))
        welcome_text.setStyleSheet("color: #333333;")
        welcome_text.setAlignment(Qt.AlignCenter)

        # Комплимент
        compliment = QLabel("Рады видеть вас снова!")
        compliment.setFont(QFont("Arial", 16))
        compliment.setStyleSheet("color: #21A038;")
        compliment.setAlignment(Qt.AlignCenter)

        # Информация о пользователе
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #E8E8E8;
                border-radius: 12px;
                padding: 15px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setSpacing(30)

        height_label = QLabel(f"Рост: {self.user_data['height']} см")
        height_label.setFont(QFont("Arial", 14))
        height_label.setStyleSheet("color: #666666;")

        level_label = QLabel(f"Уровень: {self.user_data['fitness_level']}")
        level_label.setFont(QFont("Arial", 14))
        level_label.setStyleSheet("color: #666666;")

        info_layout.addStretch()
        info_layout.addWidget(height_label)
        info_layout.addWidget(level_label)
        info_layout.addStretch()

        # Инструкция
        instruction = QLabel("Переход к выбору упражнений через 3 секунды...")
        instruction.setFont(QFont("Arial", 12))
        instruction.setStyleSheet("color: #999999;")
        instruction.setAlignment(Qt.AlignCenter)

        # Кнопка перехода сейчас
        btn_now = QPushButton("Начать сейчас")
        btn_now.setFont(QFont("Arial", 14, QFont.Bold))
        btn_now.setFixedHeight(50)
        btn_now.setStyleSheet("""
            QPushButton {
                background-color: #21A038;
                color: white;
                border: none;
                border-radius: 8px;
                margin: 10px 40px;
            }
            QPushButton:hover {
                background-color: #1C8A30;
            }
            QPushButton:pressed {
                background-color: #187C28;
            }
        """)
        btn_now.clicked.connect(self.go_to_exercises)

        layout.addStretch()
        layout.addWidget(logo_label)
        layout.addWidget(welcome_text)
        layout.addWidget(compliment)
        layout.addSpacing(10)
        layout.addWidget(info_frame)
        layout.addStretch()
        layout.addWidget(instruction)
        layout.addWidget(btn_now)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #F0F0F0;")

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
                background-color: white;
                border: 2px solid #E8E8E8;
                border-radius: 12px;
                margin: 6px;
            }
            ExerciseWidget:hover {
                border: 2px solid #21A038;
                background-color: #F8FFF9;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel(self.exercise["name"])
        title.setFont(QFont("Arial", 13, QFont.Bold))
        title.setStyleSheet("color: #333333;")
        title.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(230, 150)
        self.image_label.setMaximumSize(230, 150)
        self.image_label.setStyleSheet("""
            background-color: #F0F0F0;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
        """)

        self.load_image()

        description = QLabel(self.exercise["description"])
        description.setFont(QFont("Arial", 10))
        description.setStyleSheet("color: #666666;")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignCenter)

        intensity_frame = QFrame()
        intensity_frame.setStyleSheet("""
            QFrame {
                background-color: #F0F8F2;
                border: 1px solid #D0E8D5;
                border-radius: 6px;
                padding: 5px;
            }
        """)
        intensity_layout = QHBoxLayout(intensity_frame)
        intensity_label = QLabel("Интенсивность:")
        intensity_label.setFont(QFont("Arial", 10))
        intensity_label.setStyleSheet("color: #666666;")

        intensity_value = QLabel(f"{self.exercise['intensity']}%")
        intensity_value.setFont(QFont("Arial", 10, QFont.Bold))
        intensity_value.setStyleSheet("color: #21A038;")

        intensity_layout.addStretch()
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addWidget(intensity_value)
        intensity_layout.addStretch()

        layout.addWidget(title)
        layout.addWidget(self.image_label)
        layout.addWidget(description)
        layout.addWidget(intensity_frame)

        self.setLayout(layout)

    def load_image(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        images_dir = os.path.join(script_dir, "images")
        image_path = os.path.join(images_dir, self.exercise["image"])

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(220, 140, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)

                centered_pixmap = QPixmap(220, 140)
                centered_pixmap.fill(QColor(240, 240, 240))

                x_offset = (220 - scaled_pixmap.width()) // 2
                y_offset = (140 - scaled_pixmap.height()) // 2

                painter = QPainter(centered_pixmap)
                painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
                painter.end()

                self.image_label.setPixmap(centered_pixmap)
            else:
                self.image_label.setText("Ошибка\nзагрузки\nизображения")
                self.image_label.setAlignment(Qt.AlignCenter)
                self.image_label.setStyleSheet("color: #999999;")
        else:
            self.image_label.setText("Изображение\nне найдено")
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setStyleSheet("color: #999999;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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
        self.current_rfid_input = ""
        self.rfid_input_complete = False

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

        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.update_sensor_data)
        self.data_timer.start(100)

    def initUI(self):
        self.setWindowTitle("Smart Trainer - Orange Pi")
        self.setGeometry(0, 0, 600, 1024)

        self.stacked_widget = QStackedWidget()

        self.auth_screen = self.create_auth_screen()
        self.welcome_screen = None
        self.exercise_screen = self.create_exercise_screen()
        self.workout_screen = self.create_workout_screen()

        self.stacked_widget.addWidget(self.auth_screen)
        self.stacked_widget.addWidget(self.exercise_screen)
        self.stacked_widget.addWidget(self.workout_screen)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)

        self.show_auth_screen()

    def create_auth_screen(self):
        screen = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 60, 40, 40)
        layout.setSpacing(30)

        # Верхняя часть с логотипом
        header_layout = QVBoxLayout()
        header_layout.setSpacing(20)

        # Логотип
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_pixmap = QPixmap(100, 100)
        logo_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(logo_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(33, 160, 56))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 100, 100)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(25, 25, 50, 50)
        painter.end()
        logo_label.setPixmap(logo_pixmap)

        title = QLabel("SMART TRAINER")
        title.setFont(QFont("Arial", 26, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #333333;")

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)

        # Инструкция
        instruction = QLabel("Поднесите RFID карту\nили введите номер вручную")
        instruction.setFont(QFont("Arial", 16))
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setStyleSheet("color: #666666;")
        instruction.setWordWrap(True)

        # Индикатор ввода
        self.input_indicator = QLabel("▢▢▢▢▢▢▢▢▢▢")
        self.input_indicator.setFont(QFont("Arial", 28, QFont.Bold))
        self.input_indicator.setAlignment(Qt.AlignCenter)
        self.input_indicator.setStyleSheet("color: #21A038; margin: 20px 0;")

        # Иконка RFID
        rfid_icon = QLabel()
        rfid_pixmap = QPixmap(180, 120)
        rfid_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rfid_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(33, 160, 56))
        painter.drawRoundedRect(40, 20, 100, 80, 10, 10)
        painter.setBrush(QColor(200, 200, 200))
        painter.drawRoundedRect(60, 85, 60, 15, 7, 7)
        painter.end()
        rfid_icon.setPixmap(rfid_pixmap)
        rfid_icon.setAlignment(Qt.AlignCenter)

        # Статус авторизации
        self.auth_status = QLabel("Ожидание карты...")
        self.auth_status.setFont(QFont("Arial", 14))
        self.auth_status.setAlignment(Qt.AlignCenter)
        self.auth_status.setStyleSheet("color: #666666; padding: 10px;")

        # Скрытый ввод
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

        # Отладочная информация
        self.input_display = QLabel("Ввод: ")
        self.input_display.setFont(QFont("Arial", 10))
        self.input_display.setStyleSheet("color: #999999;")
        self.input_display.setAlignment(Qt.AlignRight)
        self.input_display.setContentsMargins(0, 0, 20, 0)

        layout.addLayout(header_layout)
        layout.addStretch()
        layout.addWidget(instruction)
        layout.addWidget(self.input_indicator)
        layout.addWidget(rfid_icon)
        layout.addWidget(self.auth_status)
        layout.addStretch()
        layout.addWidget(self.input_display)
        layout.addWidget(self.rfid_hidden_input)

        screen.setLayout(layout)
        screen.setStyleSheet("background-color: #F0F0F0;")

        QTimer.singleShot(100, lambda: self.rfid_hidden_input.setFocus())

        return screen

    def on_rfid_input_changed(self, text):
        self.current_rfid_input = text
        self.input_display.setText(f"Ввод: {text}")

        filled = len(text)
        indicator = "█" * filled + "▢" * (10 - filled)
        self.input_indicator.setText(indicator)

        if len(text) == 10 and text.isdigit():
            self.rfid_input_complete = True
            self.auth_status.setText("Обработка карты...")
            QTimer.singleShot(500, lambda: self.process_rfid(text))

    def keyPressEvent(self, event):
        key = event.key()

        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            digit = str(key - Qt.Key.Key_0)
            current_text = self.rfid_hidden_input.text()
            if len(current_text) < 10:
                self.rfid_hidden_input.setText(current_text + digit)

        elif key == Qt.Key.Key_Backspace:
            current_text = self.rfid_hidden_input.text()
            if current_text:
                self.rfid_hidden_input.setText(current_text[:-1])

        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if len(self.current_rfid_input) == 10:
                self.process_rfid(self.current_rfid_input)

        elif key == Qt.Key.Key_Escape:
            self.rfid_hidden_input.clear()
            self.auth_status.setText("Ожидание карты...")

        else:
            super().keyPressEvent(event)

    def process_rfid(self, rfid):
        self.rfid_hidden_input.clear()
        self.rfid_input_complete = False

        user = self.db.find_user_by_rfid(rfid)

        if user:
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
            self.auth_status.setText("Пользователь не найден")
            QTimer.singleShot(1000, lambda: self.register_new_user(rfid))

    def register_new_user(self, rfid):
        dialog = RegistrationDialog(rfid, self)
        if dialog.exec() == QDialog.Accepted:
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
            if self.welcome_screen:
                self.welcome_screen.setParent(None)

            self.welcome_screen = WelcomeScreen(self.current_user_data, self)

            for i in range(self.stacked_widget.count()):
                if self.stacked_widget.widget(i) == self.welcome_screen:
                    break
            else:
                self.stacked_widget.insertWidget(1, self.welcome_screen)

            self.stacked_widget.setCurrentWidget(self.welcome_screen)

    def create_exercise_screen(self):
        screen = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Шапка с информацией о пользователе
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #E8E8E8;
                border-radius: 12px;
                padding: 15px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(8)

        self.user_info = QLabel("Пользователь: ")
        self.user_info.setFont(QFont("Arial", 15, QFont.Bold))
        self.user_info.setStyleSheet("color: #333333;")

        instruction = QLabel("Выберите упражнение (нажмите на картинку):")
        instruction.setFont(QFont("Arial", 13))
        instruction.setStyleSheet("color: #666666;")

        header_layout.addWidget(self.user_info)
        header_layout.addWidget(instruction)

        # Область со списком упражнений
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #F0F0F0;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #21A038;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #1C8A30;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        exercises_widget = QWidget()
        self.exercises_layout = QGridLayout()
        self.exercises_layout.setSpacing(10)
        self.exercises_layout.setContentsMargins(5, 5, 5, 5)

        exercises_widget.setLayout(self.exercises_layout)
        scroll_area.setWidget(exercises_widget)

        # Кнопка выхода
        btn_back = QPushButton("Выйти")
        btn_back.setFont(QFont("Arial", 14, QFont.Bold))
        btn_back.setFixedHeight(50)
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                color: #666666;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
                border-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #D8D8D8;
            }
        """)
        btn_back.clicked.connect(self.show_auth_screen)

        main_layout.addWidget(header_frame)
        main_layout.addWidget(scroll_area, 1)
        main_layout.addWidget(btn_back)

        screen.setLayout(main_layout)
        screen.setStyleSheet("background-color: #F0F0F0;")
        return screen

    def create_workout_screen(self):
        screen = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 30, 25, 25)
        layout.setSpacing(20)

        # Заголовок упражнения
        self.exercise_title = QLabel("Упражнение")
        self.exercise_title.setFont(QFont("Arial", 22, QFont.Bold))
        self.exercise_title.setAlignment(Qt.AlignCenter)
        self.exercise_title.setStyleSheet("color: #333333;")

        # Изображение упражнения
        self.exercise_image = QLabel()
        self.exercise_image.setAlignment(Qt.AlignCenter)
        self.exercise_image.setMinimumSize(400, 280)
        self.exercise_image.setMaximumSize(400, 280)
        self.exercise_image.setStyleSheet("""
            border: 2px solid #E8E8E8; 
            border-radius: 12px;
            background-color: white;
            color: #999999;
            font-size: 14px;
        """)

        # Панель метрик
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #E8E8E8;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        metrics_layout = QVBoxLayout(metrics_frame)
        metrics_layout.setSpacing(15)

        # Сила
        force_widget = QWidget()
        force_layout = QVBoxLayout(force_widget)
        force_layout.setSpacing(8)

        force_header = QHBoxLayout()
        force_label = QLabel("Сила:")
        force_label.setFont(QFont("Arial", 14))
        force_label.setStyleSheet("color: #666666;")

        self.force_value = QLabel("0 Н")
        self.force_value.setFont(QFont("Arial", 14, QFont.Bold))
        self.force_value.setStyleSheet("color: #21A038;")

        force_header.addWidget(force_label)
        force_header.addStretch()
        force_header.addWidget(self.force_value)

        self.force_progress = QProgressBar()
        self.force_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                text-align: center;
                color: #333333;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #21A038;
                border-radius: 4px;
            }
        """)

        force_layout.addLayout(force_header)
        force_layout.addWidget(self.force_progress)

        # Повторения
        reps_widget = QWidget()
        reps_layout = QHBoxLayout(reps_widget)
        reps_label = QLabel("Повторения:")
        reps_label.setFont(QFont("Arial", 14))
        reps_label.setStyleSheet("color: #666666;")

        self.reps_value = QLabel("0")
        self.reps_value.setFont(QFont("Arial", 14, QFont.Bold))
        self.reps_value.setStyleSheet("color: #21A038;")

        reps_layout.addWidget(reps_label)
        reps_layout.addStretch()
        reps_layout.addWidget(self.reps_value)

        # Интенсивность
        intensity_widget = QWidget()
        intensity_layout = QHBoxLayout(intensity_widget)
        intensity_label = QLabel("Интенсивность:")
        intensity_label.setFont(QFont("Arial", 14))
        intensity_label.setStyleSheet("color: #666666;")

        self.intensity_value = QLabel("0%")
        self.intensity_value.setFont(QFont("Arial", 14, QFont.Bold))
        self.intensity_value.setStyleSheet("color: #21A038;")

        intensity_layout.addWidget(intensity_label)
        intensity_layout.addStretch()
        intensity_layout.addWidget(self.intensity_value)

        metrics_layout.addWidget(force_widget)
        metrics_layout.addWidget(reps_widget)
        metrics_layout.addWidget(intensity_widget)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        btn_stop = QPushButton("Стоп")
        btn_stop.setFont(QFont("Arial", 14, QFont.Bold))
        btn_stop.setFixedHeight(50)
        btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #21A038;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1C8A30;
            }
            QPushButton:pressed {
                background-color: #187C28;
            }
        """)
        btn_stop.clicked.connect(self.stop_workout)

        btn_back = QPushButton("Назад")
        btn_back.setFont(QFont("Arial", 14, QFont.Bold))
        btn_back.setFixedHeight(50)
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                color: #666666;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
                border-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #D8D8D8;
            }
        """)
        btn_back.clicked.connect(self.show_exercise_screen)

        buttons_layout.addWidget(btn_stop)
        buttons_layout.addWidget(btn_back)

        layout.addWidget(self.exercise_title)
        layout.addWidget(self.exercise_image, 0, Qt.AlignCenter)
        layout.addWidget(metrics_frame)
        layout.addStretch()
        layout.addLayout(buttons_layout)

        screen.setLayout(layout)
        screen.setStyleSheet("background-color: #F0F0F0;")
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
            self.user_info.setText(
                f"Пользователь: {self.current_user_data['first_name']} {self.current_user_data['last_name']} | "
                f"Рост: {self.current_user_data['height']}см | "
                f"Уровень: {self.current_user_data['fitness_level']}"
            )

            for i in reversed(range(self.exercises_layout.count())):
                self.exercises_layout.itemAt(i).widget().setParent(None)

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
                scaled_pixmap = pixmap.scaled(380, 260, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                self.exercise_image.setPixmap(scaled_pixmap)
            else:
                self.exercise_image.setText("Ошибка загрузки изображения")
        else:
            self.exercise_image.setText(f"Изображение не найдено:\n{exercise['image']}")

        self.modbus.set_target_force(exercise["intensity"])
        self.show_workout_screen()

    def update_sensor_data(self):
        if self.stacked_widget.currentIndex() == 3:
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

    sys.exit(app.exec())