"""Подключение к SQLite: путь к БД, журнал приложения, режим только чтения."""
import logging
import os
import sqlite3
from configparser import ConfigParser
from pathlib import Path

#Название пункта выдачи (одно место для переименования)
APP_NAME = "ПВЗ «Забирай»"

#Папка, в которой лежит проект
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

#режим толькочтение
_read_only = False


def set_read_only(value):
    """Включает или выключает режим только чтения для новых подключений."""
    global _read_only
    _read_only = value


def get_db_path():
    """Путь к файлу БД берём из config.ini."""
    cfg = ConfigParser()
    cfg.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")
    path = cfg["db"]["path"]
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return path


def get_connection():
    """Открывает подключение к БД (в режиме чтения - если он включён)."""
    path = get_db_path()
    if _read_only:
        #открываем БД только для чтения
        conn = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row             #доступ к полям по имени
    conn.execute("PRAGMA foreign_keys = ON")   #включить внешние ключи
    return conn


def init_db():
    """Выполняет скрипт create_db.sql: таблицы, индексы, представления, триггеры."""
    with open(os.path.join(BASE_DIR, "create_db.sql"), encoding="utf-8") as f:
        script = f.read()
    conn = get_connection()
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("База данных создана")
