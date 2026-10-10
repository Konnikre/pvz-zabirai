"""Тесты резервного копирования, ротации и восстановления БД."""
import os
import sqlite3
import unittest
from datetime import date, timedelta

import backup
import restore
from tests.base import DbTestCase


class BackupTests(DbTestCase):
    def test_make_backup_creates_file_and_history_record(self):
        self.assertEqual(backup.make_backup(), "OK")
        name = f"pvz_{date.today()}.db"
        self.assertTrue(os.path.exists(os.path.join(backup.BACKUP_DIR, name)))
        self.assertEqual(self.scalar("SELECT status FROM backup_history WHERE file_name = ?", (name,)), "OK")

    def test_backup_contains_data(self):
        backup.make_backup()
        copy = sqlite3.connect(os.path.join(backup.BACKUP_DIR, f"pvz_{date.today()}.db"))
        try:
            self.assertEqual(copy.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 5)
        finally:
            copy.close()

    def test_rotation_keeps_only_last_files(self):
        os.makedirs(backup.BACKUP_DIR)
        for days in range(10, 0, -1):
            open(os.path.join(backup.BACKUP_DIR, f"pvz_{date.today() - timedelta(days=days)}.db"), "w").close()
        backup.make_backup()
        files = sorted(os.listdir(backup.BACKUP_DIR))
        self.assertEqual(len(files), backup.KEEP)
        self.assertEqual(files[-1], f"pvz_{date.today()}.db")      # свежая копия сохранена

    def test_rotation_ignores_foreign_files(self):
        os.makedirs(backup.BACKUP_DIR)
        other = os.path.join(backup.BACKUP_DIR, "notes.txt")
        open(other, "w").close()
        backup.rotate("pvz")
        self.assertTrue(os.path.exists(other))

    def test_second_backup_same_day_overwrites(self):
        backup.make_backup()
        backup.make_backup()
        self.assertEqual(len(os.listdir(backup.BACKUP_DIR)), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM backup_history"), 2)


class RestoreTests(DbTestCase):
    def test_restore_returns_database_to_saved_state(self):
        backup.make_backup()
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM issues")
        conn.execute("DELETE FROM orders")
        conn.commit()
        conn.close()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM orders"), 0)
        ok = restore.restore(os.path.join(backup.BACKUP_DIR, f"pvz_{date.today()}.db"))
        self.assertTrue(ok)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM orders"), 5)

    def test_restore_creates_old_copy_of_current_db(self):
        backup.make_backup()
        restore.restore(os.path.join(backup.BACKUP_DIR, f"pvz_{date.today()}.db"))
        self.assertTrue(os.path.exists(self.db_path + ".old"))

    def test_restore_from_corrupted_file_keeps_current_db(self):
        bad = os.path.join(self.tmp, "bad.db")
        with open(bad, "wb") as f:
            f.write(b"this is not a sqlite database" * 100)
        self.assertFalse(restore.restore(bad))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM orders"), 5)    # прежняя БД на месте

    def test_restore_to_explicit_path(self):
        backup.make_backup()
        target = os.path.join(self.tmp, "other.db")
        self.assertTrue(restore.restore(os.path.join(backup.BACKUP_DIR, f"pvz_{date.today()}.db"), target))
        conn = sqlite3.connect(target)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM carriers").fetchone()[0], 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
