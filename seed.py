"""Создание БД и заполнение тестовыми данными."""
import os
from datetime import date, timedelta

from auth import hash_password
from db import get_connection, get_db_path, init_db
from repository import STORAGE_DAYS

CARRIERS = [  # (name, phone)
    ("Ozon", "8 (800) 000-00-01"),
    ("Wildberries", "8 (800) 000-00-02"),
    ("Яндекс Маркет", "8 (800) 000-00-03"),
    ("СДЭК", "8 (800) 000-00-04"),
    ("Почта России", "8 (800) 000-00-05"),
]

RECIPIENTS = [  # (full_name, phone, email, registration_date)
    ("Петров Сергей Иванович", "+7 (900) 000-00-01", "petrov@example.com", "2026-01-15"),
    ("Соколова Мария Андреевна", "+7 (900) 000-00-02", "sokolova@example.com", "2026-02-03"),
    ("Волков Дмитрий Олегович", "+7 (900) 000-00-03", "volkov@example.com", "2026-03-11"),
    ("Морозова Елена Викторовна", "+7 (900) 000-00-04", "morozova@example.com", "2026-04-20"),
    ("Новиков Артём Павлович", "+7 (900) 000-00-05", "novikov@example.com", "2026-05-02"),
    ("Лебедева Ольга Николаевна", "+7 (900) 000-00-06", "lebedeva@example.com", "2026-05-18"),
    ("Козлов Игорь Андреевич", "+7 (900) 000-00-07", "kozlov@example.com", "2026-06-07"),
    ("Фёдорова Анна Сергеевна", "+7 (900) 000-00-08", "fedorova@example.com", "2026-06-21"),
]

EMPLOYEES = [  # (full_name, role, login, пароль)
    ("Администратор Системы", "admin", "admin", "admin123"),
    ("Смирнова Анна Петровна", "manager", "manager", "manager123"),
    ("Кузнецов Олег Сергеевич", "report", "report", "report123"),
]

# Даты задаются "сколько дней назад", чтобы в любой день запуска
# в базе были и выданные заказы, и заказы с истекающим сроком хранения.
# (товар, к оплате, ячейка, получатель, служба, статус,
#  принят дней назад, выдан дней назад)
ORDERS = [
    ("Смартфон Xiaomi Redmi 13", 14990.0, "A-01", 1, 1, "issued", 118, 115),
    ("Кроссовки беговые", 0.0, "B-03", 2, 2, "issued", 105, 103),
    ("Куртка зимняя", 5490.0, "B-07", 3, 2, "issued", 98, 94),
    ("Чайник электрический", 2390.0, "A-04", 4, 3, "issued", 90, 89),
    ("Наушники беспроводные", 0.0, "A-02", 5, 1, "issued", 84, 80),
    ("Набор посуды", 3290.0, "C-01", 1, 4, "issued", 75, 74),
    ("Платье летнее", 1790.0, "B-02", 2, 2, "issued", 66, 63),
    ("Книга «Изучаем Python»", 2100.0, "C-05", 3, 5, "issued", 60, 58),
    ("Робот-пылесос", 18900.0, "D-01", 6, 3, "issued", 52, 50),
    ("Рюкзак городской", 0.0, "B-09", 7, 2, "issued", 45, 44),
    ("Фен для волос", 3150.0, "A-06", 8, 1, "issued", 38, 36),
    ("Постельное бельё", 2790.0, "C-03", 4, 2, "issued", 31, 29),
    ("Зарядное устройство", 990.0, "A-03", 5, 4, "issued", 25, 23),
    ("Джинсы", 0.0, "B-05", 1, 1, "issued", 19, 17),
    ("Тостер", 1990.0, "A-07", 2, 3, "issued", 14, 12),
    ("Футболка (2 шт.)", 1190.0, "B-01", 3, 2, "issued", 11, 9),
    ("Книга «Простой Python»", 1890.0, "C-06", 6, 1, "issued", 9, 8),
    ("Плед флисовый", 0.0, "C-02", 7, 5, "issued", 6, 4),
    ("Ботинки демисезонные", 4590.0, "B-04", 8, 2, "stored", 8, None),    # срок истёк
    ("Смарт-часы", 6990.0, "A-05", 2, 1, "stored", 6, None),              # остался 1 день
    ("Сковорода", 1490.0, "C-04", 3, 3, "stored", 5, None),               # осталось 2 дня
    ("Куртка-ветровка", 0.0, "B-06", 4, 2, "stored", 3, None),
    ("Микроволновая печь", 7490.0, "D-02", 5, 4, "stored", 2, None),
    ("Косметический набор", 0.0, "A-08", 6, 5, "stored", 1, None),
    ("Кофемашина", 24900.0, "D-03", 7, 3, "stored", 0, None),
    ("Сумка женская", 3290.0, "B-08", 1, 2, "returned", 14, None),
]


def seed():
    """Создаёт таблицы и заполняет их тестовыми данными."""
    init_db()
    conn = get_connection()
    today = date.today()
    try:
        conn.executemany("INSERT INTO carriers (name, phone) VALUES (?, ?)", CARRIERS)
        conn.executemany("INSERT INTO recipients (full_name, phone, email, registration_date) "
                         "VALUES (?, ?, ?, ?)", RECIPIENTS)
        for full_name, role, login, password in EMPLOYEES:
            conn.execute("INSERT INTO employees (full_name, role, login, password_hash) "
                         "VALUES (?, ?, ?, ?)", (full_name, role, login, hash_password(password)))
        for n, (descr, amount, cell, recipient, carrier, status,
                received_ago, issued_ago) in enumerate(ORDERS, start=1):
            received = today - timedelta(days=received_ago)
            until = received + timedelta(days=STORAGE_DAYS)
            tracking = f"2026{n:09d}"                      # 13 цифр
            code = str(1000 + (n * 1379) % 9000)           # код получения, 4 цифры
            # выданные заказы сначала принимаются "на хранение", потом выдаются
            conn.execute(
                "INSERT INTO orders (tracking_number, description, amount, pickup_code, cell,"
                " status, received_date, storage_until, recipient_id, carrier_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tracking, descr, amount, code, cell,
                 "returned" if status == "returned" else "stored",
                 received.isoformat(), until.isoformat(), recipient, carrier))
            if status == "issued":
                employee = 1 if n % 5 == 0 else 2
                issue_date = (today - timedelta(days=issued_ago)).isoformat()
                # триггер trg_issues_after_insert сам переведёт заказ в статус "выдан"
                conn.execute("INSERT INTO issues (order_id, employee_id, issue_date, paid_amount)"
                             " VALUES (?, ?, ?, ?)",
                             (n, employee, issue_date, amount))
        conn.execute("DELETE FROM audit_log")     # начинаем работу с чистым журналом
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    path = get_db_path()
    if os.path.exists(path):
        answer = input(f"Файл {path} уже существует. Пересоздать БД? (y/n): ")
        if answer.lower() != "y":
            raise SystemExit("Отменено")
        os.remove(path)
    seed()
    print("База данных создана и заполнена тестовыми данными")
    print("Пользователи: admin/admin123, manager/manager123, report/report123")
