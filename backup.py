"""Резервное копирование БД: копия «на лету», журнал и ротация копий."""
import logging
import os
import sqlite3
from datetime import date
from pathlib import Path

from db import BASE_DIR, get_db_path

BACKUP_DIR = os.path.join(BASE_DIR, "backups")
KEEP = 5                                   # сколько копий хранить

logger = logging.getLogger("backup")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(os.path.join(BASE_DIR, "backup.log"), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def make_backup():
    """Создаёт копию БД в папке backups/. Возвращает "OK" или текст ошибки."""
    db_path = get_db_path()
    prefix = Path(db_path).stem                     # например, "pvz"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f"{prefix}_{date.today()}.db")

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)                             # копирование "на лету"
        status = "OK"
        logger.info("Копия создана: %s", target)
    except sqlite3.Error as e:
        status = f"ERROR: {e}"
        logger.error("Ошибка копирования: %s", e)
    finally:
        dst.close()
        src.close()

    write_history(db_path, target, status)
    rotate(prefix)
    return status


def write_history(db_path, target, status):
    """Запись результата в таблицу backup_history."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO backup_history (file_name, status) VALUES (?, ?)",
                     (os.path.basename(target), status))
        conn.commit()
    except sqlite3.Error as e:
        logger.error("Не удалось записать историю: %s", e)
    finally:
        conn.close()


def rotate(prefix):
    """Оставляем KEEP последних копий, старые удаляем."""
    files = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith(prefix + "_") and f.endswith(".db"))
    for old in files[:-KEEP]:
        os.remove(os.path.join(BACKUP_DIR, old))
        logger.info("Удалена старая копия: %s", old)


if __name__ == "__main__":
    print(make_backup())