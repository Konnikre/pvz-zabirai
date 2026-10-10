"""Доступ к данным: заказы, справочники, выдачи, сотрудники (слой DAL)."""
import logging
import sqlite3

import auth
from db import get_connection
from models import Order

STORAGE_DAYS = 7


ORDER_BY = (" ORDER BY CASE status WHEN 'stored' THEN 0 ELSE 1 END,"
            " storage_until, id")


def _select(sql, params=()):
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        logging.error("Ошибка SELECT: %s | %s", e, sql)
        return []
    finally:
        conn.close()


def _execute(sql, params=()):
    """Выполняет INSERT / UPDATE / DELETE. Возвращает id последней записи."""
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        logging.error("Ошибка записи: %s | %s", e, sql)
        raise
    finally:
        conn.close()


class OrderRepository:
    """CRUD-операции с таблицей orders."""

    def get_all_orders(self):
        """Все заказы: сначала лежащие на хранении."""
        return _select("SELECT * FROM v_orders_full" + ORDER_BY)

    def get_order_by_id(self, order_id):
        """Возвращает Order по id или None, если заказа нет."""
        rows = _select("SELECT id, tracking_number, description, amount, pickup_code,"
                       " cell, recipient_id, carrier_id, status, received_date,"
                       " storage_until FROM orders WHERE id = ?", (order_id,))
        if not rows:
            return None
        return Order(**dict(rows[0]))

    def add_order(self, order):
        """Принимает заказ на хранение. Возвращает id нового заказа."""
        order_id = _execute(
            "INSERT INTO orders (tracking_number, description, amount, pickup_code,"
            " cell, recipient_id, carrier_id, received_date, storage_until)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, date('now', 'localtime'),"
            " date('now', 'localtime', ?))",
            (order.tracking_number, order.description, order.amount, order.pickup_code,
             order.cell, order.recipient_id, order.carrier_id,
             f"+{STORAGE_DAYS} days"))
        logging.info("Принят заказ id=%s: %s", order_id, order.tracking_number)
        return order_id

    def update_order(self, order):
        """Сохраняет изменения заказа."""
        _execute(
            "UPDATE orders SET tracking_number = ?, description = ?, amount = ?,"
            " pickup_code = ?, cell = ?, recipient_id = ?, carrier_id = ? WHERE id = ?",
            (order.tracking_number, order.description, order.amount, order.pickup_code,
             order.cell, order.recipient_id, order.carrier_id, order.id))
        logging.info("Изменён заказ id=%s", order.id)

    def delete_order(self, order_id):
        """Удаляет заказ (выданный удалить нельзя - сработает триггер)."""
        _execute("DELETE FROM orders WHERE id = ?", (order_id,))
        logging.info("Удалён заказ id=%s", order_id)

    def return_order(self, order_id):
        """Возвращает заказ отправителю. False, если заказ не на хранении."""
        order = self.get_order_by_id(order_id)
        if order is None or order.status != "stored":
            logging.warning("Возврат заказа id=%s отклонён: заказ не на хранении", order_id)
            return False
        _execute("UPDATE orders SET status = 'returned'"
                 " WHERE id = ? AND status = 'stored'", (order_id,))
        logging.info("Заказ id=%s возвращён отправителю", order_id)
        return True

    def search_orders(self, text="", recipient="", status=None):
        """Поиск по трек-номеру/товару, получателю и (необязательно) статусу."""
        sql = ("SELECT * FROM v_orders_full WHERE (tracking_number LIKE ?"
               " OR description LIKE ?) AND recipient LIKE ?")
        params = [f"%{text}%", f"%{text}%", f"%{recipient}%"]
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        return _select(sql + ORDER_BY, params)


class ReferenceRepository:
    """Справочники: службы доставки, получатели."""

    def get_carriers(self):
        """Список служб доставки (id, name)."""
        return _select("SELECT id, name FROM carriers ORDER BY name")

    def get_recipients(self):
        """Список получателей (id, full_name, phone)."""
        return _select("SELECT id, full_name, phone FROM recipients ORDER BY full_name")

    def get_or_create_carrier(self, name):
        """Ищет службу доставки по названию, если её нет - добавляет."""
        rows = _select("SELECT id FROM carriers WHERE name = ?", (name,))
        if rows:
            return rows[0]["id"]
        return _execute("INSERT INTO carriers (name) VALUES (?)", (name,))

    def get_or_create_recipient(self, full_name, phone):
        """Ищет получателя по ФИО и телефону, если его нет - добавляет."""
        rows = _select("SELECT id FROM recipients WHERE full_name = ? AND phone = ?",
                       (full_name, phone))
        if rows:
            return rows[0]["id"]
        return _execute("INSERT INTO recipients (full_name, phone) VALUES (?, ?)",
                        (full_name, phone))


class IssueRepository:
    """Выдача заказов получателям."""

    def issue_order(self, order_id, employee_id, paid_amount):
        """Оформляет выдачу заказа. Возвращает id выдачи."""
        issue_id = _execute(
            "INSERT INTO issues (order_id, employee_id, issue_date, paid_amount)"
            " VALUES (?, ?, date('now', 'localtime'), ?)",
            (order_id, employee_id, paid_amount))
        logging.info("Выдача id=%s: заказ %s, принято %s", issue_id, order_id, paid_amount)
        return issue_id


class EmployeeRepository:
    """Сотрудники (управление пользователями - только для admin)."""

    def get_employees(self):
        """Список сотрудников без хешей паролей."""
        return _select("SELECT id, full_name, login, role FROM employees ORDER BY id")

    def add_employee(self, full_name, login_name, password, role):
        """Добавляет сотрудника, пароль хранится в виде хеша."""
        return _execute(
            "INSERT INTO employees (full_name, role, login, password_hash)"
            " VALUES (?, ?, ?, ?)",
            (full_name, role, login_name, auth.hash_password(password)))