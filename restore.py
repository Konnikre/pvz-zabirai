"""Восстановление БД из резервной копии."""
import os
import shutil
import sqlite3
import sys

from backup import BACKUP_DIR, logger
from db import get_db_path


def restore(backup_file, db_path=None):
    """Восстанавливает БД из копии. Возвращает True, если БД прошла проверку."""
    if not os.path.isfile(backup_file):
        logger.error("Файл резервной копии не найден: %s", backup_file)
        return False
    db_path = db_path or get_db_path()
    old_file = db_path + ".old"
    if os.path.exists(db_path):
        shutil.copy(db_path, old_file)
    shutil.copy(backup_file, db_path)
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError:
        result = "error"
    finally:
        conn.close()
    if result != "ok":
        if os.path.exists(old_file):
            shutil.copy(old_file, db_path)          #вернуть прежний файл
        logger.error("Восстановление из %s не удалось", backup_file)
        return False
    logger.info("БД восстановлена из %s", backup_file)
    return True


if __name__ == "__main__":
    files = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(".db"))
    if not files:
        print("Резервных копий нет")
        sys.exit(1)
    for number, name in enumerate(files, start=1):
        print(number, name)
    answer = input("Номер копии для восстановления: ").strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(files):
        print("Нужно ввести номер из списка")
        sys.exit(1)
    ok = restore(os.path.join(BACKUP_DIR, files[int(answer) - 1]))
    print("Восстановление выполнено" if ok else "Ошибка: БД повреждена")
