from db import get_connection


def run(sql, params=()):
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


#заказы указанной службы доставки (JOIN)
def orders_by_carrier(carrier):
    return run("SELECT o.tracking_number, o.description, r.full_name AS recipient, "
               "CASE o.status WHEN 'stored' THEN 'На хранении' "
               "WHEN 'issued' THEN 'Выдан' ELSE 'Возвращён' END AS status "
               "FROM orders o "
               "JOIN recipients r ON r.id = o.recipient_id "
               "JOIN carriers c ON c.id = o.carrier_id "
               "WHERE c.name = ? ORDER BY o.received_date DESC, o.id DESC", (carrier,))


#10 получателей с наибольшим числом полученных заказов (GROUP BY + LIMIT)
def top10_recipients():
    return run("SELECT r.full_name, COUNT(*) AS orders_count, "
               "SUM(i.paid_amount) AS paid "
               "FROM issues i "
               "JOIN orders o ON o.id = i.order_id "
               "JOIN recipients r ON r.id = o.recipient_id "
               "GROUP BY r.id ORDER BY orders_count DESC, paid DESC LIMIT 10")


#сумма, принятая при выдаче заказов за период (SUM + BETWEEN)
def revenue(start, end):
    return run("SELECT COALESCE(SUM(paid_amount), 0) AS revenue FROM issues "
               "WHERE issue_date BETWEEN ? AND ?", (start, end))[0][0]


#заказы, срок хранения которых заканчивается через days дней и раньше
def expiring_orders(days=2):
    return run("SELECT tracking_number, description, storage_until FROM orders "
               "WHERE status = 'stored' AND storage_until <= date('now', 'localtime', ?) "
               "ORDER BY storage_until", (f"+{int(days)} days",))


#средняя сумма при выдаче (AVG)
def avg_check():
    return run("SELECT COALESCE(AVG(paid_amount), 0) AS avg_check FROM issues")[0][0]


#выдачи по месяцам (strftime + GROUP BY)
def issues_by_month():
    return run("SELECT strftime('%Y-%m', issue_date) AS month, "
               "COUNT(*) AS issued, SUM(paid_amount) AS revenue FROM issues "
               "GROUP BY month ORDER BY month")


#поиск по трек-номеру или названию товара (LIKE)
def search_orders(text):
    return run("SELECT tracking_number, description, cell FROM orders "
               "WHERE tracking_number LIKE ? OR description LIKE ? "
               "ORDER BY description", (f"%{text}%", f"%{text}%"))


def print_table(rows):
    """Вывод результата запроса таблицей в консоль."""
    if not rows:
        print("  (нет данных)\n")
        return
    headers = rows[0].keys()
    table = [[str(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in table)) for i, h in enumerate(headers)]
    line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    print(line)
    print("| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |")
    print(line)
    for r in table:
        print("| " + " | ".join(v.ljust(w) for v, w in zip(r, widths)) + " |")
    print(line + "\n")


if __name__ == "__main__":
    print("1. Заказы службы доставки «Ozon»")
    print_table(orders_by_carrier("Ozon"))
    print("2. Топ-10 получателей по числу заказов")
    print_table(top10_recipients())
    print("3. Принято при выдаче за 2026-01-01 - 2026-12-31:", revenue("2026-01-01", "2026-12-31"), "\n")
    print("4. Заказы, срок хранения которых истекает в ближайшие 2 дня")
    print_table(expiring_orders())
    print("5. Средняя сумма при выдаче:", round(avg_check(), 2), "\n")
    print("6. Выдачи по месяцам")
    print_table(issues_by_month())
    print("7. Поиск «Куртка»")
    print_table(search_orders("Куртка"))
