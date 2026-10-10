"""Системные тесты: сквозные сценарии, повторяющие действия пользователя в окнах приложения
(та же последовательность вызовов validators → auth → repository → reports → backup)."""
import os
import sqlite3
import unittest

import auth
import backup
import db
import reports
import restore
import validators
from models import Order
from repository import IssueRepository, OrderRepository, ReferenceRepository
from tests.base import DbTestCase


class EndToEndTests(DbTestCase):
    """Сценарий менеджера: приём → поиск → выдача → отчёт → резервная копия."""

    def test_full_order_lifecycle(self):
        user = auth.login("manager", "manager123")
        self.assertTrue(auth.can_edit(user["role"]))

        # ввод в форме приёма
        form = dict(tracking="2026000000099", descr="Монитор", amount="5990", code="4321",
                    cell="E-01", carrier="Ozon", recipient="Петров Сергей Иванович", phone="+7 (900) 000-00-01")
        self.assertEqual(validators.validate_order(form["tracking"], form["descr"], form["amount"], form["code"],
                                                   form["cell"], form["carrier"], form["recipient"], form["phone"]), [])
        refs, orders = ReferenceRepository(), OrderRepository()
        order = Order(None, form["tracking"], form["descr"], float(form["amount"]), form["code"], form["cell"],
                      refs.get_or_create_recipient(form["recipient"], form["phone"]),
                      refs.get_or_create_carrier(form["carrier"]))
        order_id = orders.add_order(order)

        # поиск
        found = orders.search_orders("Монитор")
        self.assertEqual([r["id"] for r in found], [order_id])
        self.assertEqual(found[0]["status_text"], "На хранении")

        # неверный код получения -> выдачи нет
        self.assertTrue(validators.validate_issue("0000", order.pickup_code))
        self.assertEqual(orders.get_order_by_id(order_id).status, "stored")

        # верный код -> выдача
        self.assertEqual(validators.validate_issue("4321", order.pickup_code), "")
        IssueRepository().issue_order(order_id, user["id"], order.amount)
        self.assertEqual(orders.get_order_by_id(order_id).status, "issued")

        # отчёт видит выдачу
        rep = reports.report_issues("2000-01-01", "2999-12-31")
        self.assertIn("2026000000099", [row[1] for row in rep.rows])

        # резервная копия
        self.assertEqual(backup.make_backup(), "OK")

    def test_return_expired_order_scenario(self):
        orders = OrderRepository()
        stored_before = len(reports.report_stored().rows)
        self.assertEqual(orders.get_order_by_id(self.o3).status, "stored")
        orders.return_order(self.o3)
        self.assertEqual(orders.get_order_by_id(self.o3).status, "returned")
        self.assertEqual(len(reports.report_stored().rows), stored_before - 1)
        with self.assertRaises(sqlite3.IntegrityError):         # вернувшийся заказ выдать нельзя
            IssueRepository().issue_order(self.o3, 2, 0.0)

    def test_edit_order_then_search_by_new_data(self):
        orders = OrderRepository()
        order = orders.get_order_by_id(self.o1)
        order.description = "Пуховик"
        orders.update_order(order)
        self.assertEqual([r["id"] for r in orders.search_orders("Пуховик")], [self.o1])
        self.assertEqual(orders.search_orders("Куртка"), [])

    def test_duplicate_tracking_number_scenario(self):
        orders = OrderRepository()
        duplicate = Order(None, "2026000000001", "Копия", 1.0, "9999", "Z-99", 1, 1)
        with self.assertRaises(sqlite3.IntegrityError):
            orders.add_order(duplicate)
        self.assertEqual(len(orders.get_all_orders()), 5)

    def test_report_role_is_read_only(self):
        user = auth.login("report", "report123")
        self.assertFalse(auth.can_edit(user["role"]))
        db.set_read_only(True)
        self.assertEqual(len(OrderRepository().get_all_orders()), 5)
        with self.assertRaises(sqlite3.OperationalError):
            IssueRepository().issue_order(self.o1, user["id"], 0.0)
        self.assertEqual(len(reports.report_stored().rows), 3)    # отчёты доступны

    def test_disaster_recovery_scenario(self):
        backup.make_backup()
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP VIEW v_orders_full")                   # «поломка» БД
        conn.commit()
        conn.close()
        self.assertEqual(OrderRepository().get_all_orders(), [])  # ошибка SELECT скрыта и залогирована
        self.assertTrue(restore.restore(os.path.join(backup.BACKUP_DIR, os.listdir(backup.BACKUP_DIR)[0])))
        self.assertEqual(len(OrderRepository().get_all_orders()), 5)


if __name__ == "__main__":
    unittest.main()
