"""Общая подготовка: временная база данных и тестовые данные для каждого теста."""
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

import backup
import db
import reports
import restore
from auth import hash_password

TODAY = date.today()


def iso(days):
    """Дата сегодня + days дней в формате ГГГГ-ММ-ДД."""
    return (TODAY + timedelta(days=days)).isoformat()


class DbTestCase(unittest.TestCase):
    """Каждый тест работает с новой пустой БД в папке TEMP."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pvz_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = os.path.join(self.tmp, "pvz.db")
        for target, name, value in (
                (db, "get_db_path", lambda: self.db_path),
                (backup, "get_db_path", lambda: self.db_path),
                (restore, "get_db_path", lambda: self.db_path),
                (backup, "BACKUP_DIR", os.path.join(self.tmp, "backups")),
                (restore, "BACKUP_DIR", os.path.join(self.tmp, "backups")),
                (reports, "REPORTS_DIR", os.path.join(self.tmp, "reports"))):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        db.set_read_only(False)
        self.addCleanup(db.set_read_only, False)
        db.init_db()
        self.fill()

    # ---- тестовые данные -------------------------------------------------
    def fill(self):
        conn = db.get_connection()
        try:
            conn.executemany("INSERT INTO carriers (name) VALUES (?)", [("Ozon",), ("Wildberries",)])
            conn.executemany("INSERT INTO recipients (full_name, phone) VALUES (?, ?)",
                             [("Петров Сергей Иванович", "+7 (900) 000-00-01"),
                              ("Соколова Мария Андреевна", "+7 (900) 000-00-02")])
            for name, role, login, password in (("Администратор", "admin", "admin", "admin123"),
                                                ("Менеджер", "manager", "manager", "manager123"),
                                                ("Отчётность", "report", "report", "report123")):
                conn.execute("INSERT INTO employees (full_name, role, login, password_hash)"
                             " VALUES (?, ?, ?, ?)", (name, role, login, hash_password(password)))
            conn.commit()
        finally:
            conn.close()
        # 1 - на хранении, срок в запасе; 2 - срок истекает завтра; 3 - срок истёк;
        # 4 - выдан; 5 - возвращён отправителю
        self.o1 = self.add_order("2026000000001", "Куртка зимняя", 5490.0, "1111", "B-07", recipient=1, carrier=2,
                                 received=-3, until=4)
        self.o2 = self.add_order("2026000000002", "Смарт-часы", 6990.0, "2222", "A-05", recipient=2, carrier=1,
                                 received=-6, until=1)
        self.o3 = self.add_order("2026000000003", "Ботинки демисезонные", 4590.0, "3333", "B-04", recipient=2,
                                 carrier=2, received=-8, until=-1)
        self.o4 = self.add_order("2026000000004", "Чайник электрический", 2390.0, "4444", "A-04", recipient=1,
                                 carrier=1, received=-12, until=-5)
        self.issue(self.o4, days=-10, paid=2390.0)
        self.o5 = self.add_order("2026000000005", "Сумка женская", 3290.0, "5555", "B-08", recipient=1, carrier=1,
                                 received=-14, until=-7, status="returned")
        conn = db.get_connection()
        conn.execute("DELETE FROM audit_log")
        conn.commit()
        conn.close()

    def add_order(self, tracking, descr, amount, code, cell, recipient=1, carrier=1,
                  received=0, until=7, status="stored"):
        conn = db.get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO orders (tracking_number, description, amount, pickup_code, cell, status,"
                " received_date, storage_until, recipient_id, carrier_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (tracking, descr, amount, code, cell, status, iso(received), iso(until), recipient, carrier))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def issue(self, order_id, days=0, paid=0.0, employee=2):
        conn = db.get_connection()
        try:
            conn.execute("INSERT INTO issues (order_id, employee_id, issue_date, paid_amount) VALUES (?,?,?,?)",
                         (order_id, employee, iso(days), paid))
            conn.commit()
        finally:
            conn.close()

    def scalar(self, sql, params=()):
        conn = db.get_connection()
        try:
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()
