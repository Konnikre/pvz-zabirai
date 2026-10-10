"""Интеграционные тесты слоя доступа к данным: репозитории + SQLite + триггеры."""
import sqlite3
import unittest

import db
from models import Order
from repository import (EmployeeRepository, IssueRepository, OrderRepository,
                        ReferenceRepository, STORAGE_DAYS)
from tests.base import DbTestCase, iso


class OrderRepositoryTests(DbTestCase):
    def setUp(self):
        super().setUp()
        self.repo = OrderRepository()

    def new_order(self, **kw):
        data = dict(id=None, tracking_number="2026000000099", description="Монитор", amount=5990.0,
                    pickup_code="4321", cell="E-01", recipient_id=1, carrier_id=1)
        data.update(kw)
        return Order(**data)

    def test_add_order_sets_status_and_storage_period(self):
        order_id = self.repo.add_order(self.new_order())
        saved = self.repo.get_order_by_id(order_id)
        self.assertEqual(saved.status, "stored")
        self.assertEqual(saved.received_date, iso(0))
        self.assertEqual(saved.storage_until, iso(STORAGE_DAYS))
        self.assertEqual(saved.description, "Монитор")

    def test_add_order_duplicate_tracking_number_rolls_back(self):
        self.repo.add_order(self.new_order())
        before = len(self.repo.get_all_orders())
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_order(self.new_order())
        self.assertEqual(len(self.repo.get_all_orders()), before)

    def test_add_order_unknown_carrier_violates_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_order(self.new_order(carrier_id=999))

    def test_get_order_by_id_missing_returns_none(self):
        self.assertIsNone(self.repo.get_order_by_id(9999))

    def test_get_all_orders_sorted_stored_first_by_deadline(self):
        rows = self.repo.get_all_orders()
        self.assertEqual(len(rows), 5)
        stored = [r["status"] for r in rows[:3]]
        self.assertEqual(stored, ["stored"] * 3)
        self.assertEqual([r["id"] for r in rows[:3]], [self.o3, self.o2, self.o1])   # по сроку хранения
        self.assertEqual({r["status"] for r in rows[3:]}, {"issued", "returned"})

    def test_update_order(self):
        order = self.repo.get_order_by_id(self.o1)
        order.description = "Куртка зимняя (новая)"
        order.amount = 100.0
        self.repo.update_order(order)
        saved = self.repo.get_order_by_id(self.o1)
        self.assertEqual((saved.description, saved.amount), ("Куртка зимняя (новая)", 100.0))

    def test_delete_stored_order(self):
        self.repo.delete_order(self.o1)
        self.assertIsNone(self.repo.get_order_by_id(self.o1))

    def test_delete_issued_order_is_blocked_by_trigger(self):
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            self.repo.delete_order(self.o4)
        self.assertIn("уже выдан", str(ctx.exception))
        self.assertIsNotNone(self.repo.get_order_by_id(self.o4))

    def test_return_stored_order(self):
        self.repo.return_order(self.o3)
        self.assertEqual(self.repo.get_order_by_id(self.o3).status, "returned")

    def test_return_issued_order_does_not_change_status(self):
        self.repo.return_order(self.o4)
        self.assertEqual(self.repo.get_order_by_id(self.o4).status, "issued")

    def test_return_issued_order_is_not_logged_as_success(self):
        # DEF-01: в журнал писалось «возвращён отправителю», хотя заказ не изменился
        with self.assertLogs(level="DEBUG") as logs:
            import logging
            logging.getLogger().info("маркер")          # чтобы assertLogs не упал при отсутствии записей
            self.repo.return_order(self.o4)
        self.assertFalse([m for m in logs.output if "возвращён отправителю" in m], logs.output)

    def test_search_by_tracking_number_and_description(self):
        self.assertEqual([r["id"] for r in self.repo.search_orders("000000002")], [self.o2])
        self.assertEqual([r["id"] for r in self.repo.search_orders("Куртка")], [self.o1])

    def test_search_by_recipient_and_status(self):
        rows = self.repo.search_orders(recipient="Петров")
        self.assertEqual({r["id"] for r in rows}, {self.o1, self.o4, self.o5})
        rows = self.repo.search_orders(recipient="Петров", status="issued")
        self.assertEqual([r["id"] for r in rows], [self.o4])

    def test_search_without_filters_returns_all(self):
        self.assertEqual(len(self.repo.search_orders()), 5)

    def test_search_no_match(self):
        self.assertEqual(self.repo.search_orders("нет такого товара"), [])

    def test_search_is_safe_against_sql_injection(self):
        self.assertEqual(self.repo.search_orders("'; DROP TABLE orders; --"), [])
        self.assertEqual(len(self.repo.get_all_orders()), 5)

    @unittest.expectedFailure
    def test_search_treats_percent_as_plain_character(self):
        # DEF-03 (известный, отложен): символы % и _ работают как шаблон LIKE, а не как обычные символы
        self.assertEqual(self.repo.search_orders("%%%"), [])


class ReferenceRepositoryTests(DbTestCase):
    def test_get_carriers_sorted_by_name(self):
        names = [r["name"] for r in ReferenceRepository().get_carriers()]
        self.assertEqual(names, ["Ozon", "Wildberries"])

    def test_get_recipients(self):
        self.assertEqual(len(ReferenceRepository().get_recipients()), 2)

    def test_get_or_create_carrier_is_idempotent(self):
        refs = ReferenceRepository()
        first = refs.get_or_create_carrier("СДЭК")
        self.assertEqual(refs.get_or_create_carrier("СДЭК"), first)
        self.assertEqual(refs.get_or_create_carrier("Ozon"), 1)
        self.assertEqual(len(refs.get_carriers()), 3)

    def test_get_or_create_recipient_matches_name_and_phone(self):
        refs = ReferenceRepository()
        existing = refs.get_or_create_recipient("Петров Сергей Иванович", "+7 (900) 000-00-01")
        self.assertEqual(existing, 1)
        other_phone = refs.get_or_create_recipient("Петров Сергей Иванович", "+7 (900) 111-11-11")
        self.assertNotEqual(other_phone, 1)


class IssueRepositoryTests(DbTestCase):
    def test_issue_changes_status_and_stores_payment(self):
        issue_id = IssueRepository().issue_order(self.o1, 2, 5490.0)
        self.assertGreater(issue_id, 0)
        self.assertEqual(OrderRepository().get_order_by_id(self.o1).status, "issued")
        self.assertEqual(self.scalar("SELECT paid_amount FROM issues WHERE order_id = ?", (self.o1,)), 5490.0)
        self.assertEqual(self.scalar("SELECT issue_date FROM issues WHERE order_id = ?", (self.o1,)), iso(0))

    def test_cannot_issue_twice(self):
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            IssueRepository().issue_order(self.o4, 2, 2390.0)
        self.assertIn("не находится на хранении", str(ctx.exception))

    def test_cannot_issue_returned_order(self):
        with self.assertRaises(sqlite3.IntegrityError):
            IssueRepository().issue_order(self.o5, 2, 0.0)

    def test_cannot_issue_unknown_order(self):
        with self.assertRaises(sqlite3.IntegrityError):
            IssueRepository().issue_order(9999, 2, 0.0)

    def test_cannot_issue_with_negative_payment(self):
        with self.assertRaises(sqlite3.IntegrityError):
            IssueRepository().issue_order(self.o1, 2, -1.0)
        self.assertEqual(OrderRepository().get_order_by_id(self.o1).status, "stored")

    def test_zero_payment_for_prepaid_order(self):
        IssueRepository().issue_order(self.o1, 2, 0.0)
        self.assertEqual(OrderRepository().get_order_by_id(self.o1).status, "issued")


class EmployeeRepositoryTests(DbTestCase):
    def test_get_employees(self):
        logins = [r["login"] for r in EmployeeRepository().get_employees()]
        self.assertEqual(logins, ["admin", "manager", "report"])

    def test_add_employee_stores_hash_not_password(self):
        repo = EmployeeRepository()
        repo.add_employee("Новый Сотрудник", "newuser", "secret99", "manager")
        stored = self.scalar("SELECT password_hash FROM employees WHERE login = 'newuser'")
        self.assertIn("$", stored)
        self.assertNotIn("secret99", stored)
        import auth
        self.assertEqual(auth.login("newuser", "secret99")["role"], "manager")

    def test_duplicate_login_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            EmployeeRepository().add_employee("Дубль", "admin", "secret99", "admin")

    def test_invalid_role_rejected_by_check_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            EmployeeRepository().add_employee("Кто-то", "someone", "secret99", "boss")


class DatabaseRulesTests(DbTestCase):
    """Ограничения и триггеры схемы create_db.sql."""

    def execute(self, sql, params=()):
        conn = db.get_connection()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def test_tracking_number_length_check(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_order("12345", "Товар", 0.0, "1234", "A-01")

    def test_negative_amount_check(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_order("2026000000077", "Товар", -1.0, "1234", "A-01")

    def test_pickup_code_length_check(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_order("2026000000078", "Товар", 0.0, "12", "A-01")

    def test_invalid_status_check(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_order("2026000000079", "Товар", 0.0, "1234", "A-01", status="lost")

    def test_audit_log_records_insert_update_delete(self):
        order_id = self.add_order("2026000000080", "Аудит", 10.0, "1234", "A-01")
        self.execute("UPDATE orders SET amount = 20 WHERE id = ?", (order_id,))
        self.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        ops = [r[0] for r in db.get_connection().execute(
            "SELECT operation FROM audit_log WHERE record_id = ? AND table_name = 'orders' ORDER BY id", (order_id,))]
        self.assertEqual(ops, ["I", "U", "D"])

    def test_audit_log_keeps_old_and_new_values(self):
        self.execute("UPDATE orders SET amount = 1 WHERE id = ?", (self.o1,))
        row = db.get_connection().execute(
            "SELECT old_values, new_values FROM audit_log WHERE operation = 'U' AND record_id = ?",
            (self.o1,)).fetchone()
        self.assertIn("5490.0", row[0])
        self.assertIn("1.0", row[1])

    def test_read_only_mode_blocks_writes_but_allows_reads(self):
        db.set_read_only(True)
        self.assertEqual(len(OrderRepository().get_all_orders()), 5)
        with self.assertRaises(sqlite3.OperationalError):
            OrderRepository().return_order(self.o1)

    def test_select_error_returns_empty_list(self):
        import repository
        self.assertEqual(repository._select("SELECT * FROM no_such_table"), [])


if __name__ == "__main__":
    unittest.main()
