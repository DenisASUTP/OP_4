#!/usr/bin/env python3
import os
import sqlite3


def initialize_test_data():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()

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

    test_users = [
        ("1234567890", "Иван", "Петров", 180, 3),
        ("0987654321", "Мария", "Сидорова", 165, 2),
        ("1122334455", "Алексей", "Павлов", 175, 4)
    ]

    for user in test_users:
        try:
            cursor.execute('''
                INSERT INTO users (rf_id, first_name, last_name, height, fitness_level)
                VALUES (?, ?, ?, ?, ?)
            ''', user)
        except:
            pass

    conn.commit()
    print("Тестовые данные созданы")


if __name__ == "__main__":
    initialize_test_data()