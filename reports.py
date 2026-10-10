"""Отчёты с параметрами и экспорт в CSV и HTML."""
import csv
import html
import os
from dataclasses import dataclass, field
from datetime import date, datetime

from db import BASE_DIR
from queries import run

REPORTS_DIR = os.path.join(BASE_DIR, "reports")
EXPIRING_DAYS = 2                   # осталось этого числа дней хранения и меньше - красным
ALL_CARRIERS = "Все службы доставки"


@dataclass
class Report:
    """Готовый отчёт: заголовки, строки, итог и номера строк для выделения."""

    name: str                       # короткое имя (для имени файла)
    title: str                      # заголовок отчёта
    headers: list                   # названия столбцов
    rows: list                      # строки данных
    total: str = ""                 # итоговая строка
    red_rows: list = field(default_factory=list)   # номера строк для выделения
    created: str = field(default_factory=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))


def fmt(value):
    """Числа с дробной частью выводим с двумя знаками."""
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def is_expiring(status, storage_until):
    """Заказ на хранении, у которого срок хранения почти (или уже) истёк."""
    if status != "stored":
        return False
    try:
        left = (date.fromisoformat(storage_until) - date.today()).days
    except ValueError:
        return False
    return left <= EXPIRING_DAYS


#выдачи за период (start_date, end_date)
def report_issues(start_date, end_date):
    """Отчёт «Выдачи за период»."""
    rows = run("SELECT i.issue_date, o.tracking_number, o.description, r.full_name, "
               "i.paid_amount "
               "FROM issues i "
               "JOIN orders o ON o.id = i.order_id "
               "JOIN recipients r ON r.id = o.recipient_id "
               "WHERE i.issue_date BETWEEN ? AND ? "
               "ORDER BY i.issue_date, i.id", (start_date, end_date))
    data = [tuple(r) for r in rows]
    total = sum(r[4] for r in data)
    return Report("issues", f"Выдачи за период {start_date} - {end_date}",
                  ["Дата", "Трек-номер", "Товар", "Получатель", "Принято, руб."], data,
                  f"Выдано заказов: {len(data)}. Принято при выдаче: {total:.2f} руб.")


#10 лучших получателей (carrier - название службы доставки или "Все службы доставки")
def report_top10(carrier=ALL_CARRIERS):
    """Отчёт «Топ-10 получателей» (можно отфильтровать по службе доставки)."""
    sql = ("SELECT r.full_name, r.phone, COUNT(*) AS orders_count, SUM(i.paid_amount) AS paid "
           "FROM issues i "
           "JOIN orders o ON o.id = i.order_id "
           "JOIN recipients r ON r.id = o.recipient_id "
           "JOIN carriers c ON c.id = o.carrier_id ")
    params = ()
    if carrier and carrier != ALL_CARRIERS:
        sql += "WHERE c.name = ? "
        params = (carrier,)
    sql += "GROUP BY r.id ORDER BY orders_count DESC, paid DESC LIMIT 10"
    data = [(place, *row) for place, row in enumerate(run(sql, params), start=1)]
    total = sum(r[3] for r in data)
    return Report("top10", f"Топ-10 получателей. Служба доставки: {carrier}",
                  ["Место", "Получатель", "Телефон", "Заказов", "Оплачено, руб."], data,
                  f"Заказов у получателей из топа: {total}")


#заказы на хранении
def report_stored():
    """Отчёт «Заказы на хранении» с выделением истекающих сроков."""
    rows = run("SELECT tracking_number, description, recipient, carrier, cell, amount, "
               "storage_until, days_left FROM v_stored_orders "
               "ORDER BY days_left, tracking_number")
    data = [tuple(r) for r in rows]
    red = [i for i, r in enumerate(data) if r[7] <= EXPIRING_DAYS]
    total = sum(r[5] for r in data)
    return Report("stored", "Заказы на хранении",
                  ["Трек-номер", "Товар", "Получатель", "Служба", "Ячейка",
                   "К оплате", "Хранить до", "Осталось дней"], data,
                  f"Заказов на хранении: {len(data)}, к оплате при получении: {total:.2f} руб. "
                  f"Срок истекает (или истёк): {len(red)}", red)


def _file_path(report, extension):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")   # дата формирования в имени
    return os.path.join(REPORTS_DIR, f"{report.name}_{stamp}.{extension}")


def save_csv(report):
    """Сохраняет отчёт в CSV (открывается в Excel). Возвращает путь к файлу."""
    path = _file_path(report, "csv")
    # utf-8-sig и разделитель ";" - чтобы файл правильно открылся в Excel
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([report.title])
        writer.writerow([f"Дата формирования: {report.created}"])
        writer.writerow([])
        writer.writerow(report.headers)
        for row in report.rows:
            writer.writerow([fmt(v) for v in row])
        writer.writerow([])
        writer.writerow([report.total])
    return path


def save_html(report):
    """Сохраняет отчёт в HTML-страницу. Возвращает путь к файлу."""
    path = _file_path(report, "html")
    head = "".join(f"<th>{html.escape(h)}</th>" for h in report.headers)
    body = ""
    for i, row in enumerate(report.rows):
        css = ' class="low"' if i in report.red_rows else ""
        cells = "".join(f"<td>{html.escape(fmt(v))}</td>" for v in row)
        body += f"<tr{css}>{cells}</tr>\n"
    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{html.escape(report.title)}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 30px; }}
  table {{ border-collapse: collapse; }}
  th, td {{ border: 1px solid #999; padding: 6px 10px; }}
  th {{ background: #e8e8e8; }}
  tr.low td {{ color: red; font-weight: bold; }}
</style>
</head>
<body>
<h2>{html.escape(report.title)}</h2>
<p>Дата формирования: {report.created}</p>
<table>
<tr>{head}</tr>
{body}</table>
<p><b>{html.escape(report.total)}</b></p>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


if __name__ == "__main__":
    for rep in (report_issues("2026-01-01", "2026-12-31"), report_top10(), report_stored()):
        print(save_csv(rep))
        print(save_html(rep))
