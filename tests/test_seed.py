"""Тест создания и заполнения БД скриптом seed.py."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import auth
import db
import seed


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pvz_seed_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        path = os.path.join(self.tmp, "pvz.db")
        patcher = mock.patch.object(db, "get_db_path", lambda: path)
        patcher.start()
        self.addCleanup(patcher.stop)
        seed.seed()

    def count(self, table, where=""):
        conn = db.get_connection()
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0]
        finally:
            conn.close()

    def test_row_counts(self):
        self.assertEqual(self.count("carriers"), 5)
        self.assertEqual(self.count("recipients"), 8)
        self.assertEqual(self.count("employees"), 3)
        self.assertEqual(self.count("orders"), 26)
        self.assertEqual(self.count("issues"), 18)

    def test_statuses(self):
        self.assertEqual(self.count("orders", "WHERE status = 'issued'"), 18)
        self.assertEqual(self.count("orders", "WHERE status = 'stored'"), 7)
        self.assertEqual(self.count("orders", "WHERE status = 'returned'"), 1)

    def test_audit_log_is_clean_after_seed(self):
        self.assertEqual(self.count("audit_log"), 0)

    def test_users_can_log_in(self):
        self.assertEqual(auth.login("admin", "admin123")["role"], "admin")
        self.assertEqual(auth.login("manager", "manager123")["role"], "manager")
        self.assertEqual(auth.login("report", "report123")["role"], "report")

    def test_tracking_numbers_are_13_digits_and_codes_4_digits(self):
        conn = db.get_connection()
        try:
            bad = conn.execute("SELECT COUNT(*) FROM orders WHERE length(tracking_number) <> 13"
                               " OR length(pickup_code) <> 4").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(bad, 0)

    def test_there_are_expiring_orders_on_any_day(self):
        conn = db.get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM v_stored_orders WHERE days_left <= 2").fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(n, 3)


if __name__ == "__main__":
    unittest.main()
