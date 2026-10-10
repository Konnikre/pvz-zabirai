"""Тесты SQL-запросов и отчётов с экспортом."""
import csv
import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date

import queries
import reports
from tests.base import DbTestCase, iso


class QueriesTests(DbTestCase):
    def setUp(self):
        super().setUp()
        self.issue(self.o1, days=-2, paid=5490.0)

    def test_orders_by_carrier(self):
        rows = queries.orders_by_carrier("Ozon")
        self.assertEqual({r["tracking_number"] for r in rows},
                         {"2026000000002", "2026000000004", "2026000000005"})
        self.assertEqual({r["status"] for r in rows}, {"На хранении", "Выдан", "Возвращён"})

    def test_orders_by_unknown_carrier(self):
        self.assertEqual(queries.orders_by_carrier("Нет такой"), [])

    def test_top10_recipients_counts_issued_orders(self):
        rows = queries.top10_recipients()
        self.assertEqual(len(rows), 1)                 # выдачи были только у получателя 1
        self.assertEqual(rows[0]["orders_count"], 2)
        self.assertEqual(rows[0]["paid"], 2390.0 + 5490.0)

    def test_revenue_for_period(self):
        self.assertEqual(queries.revenue(iso(-30), iso(0)), 7880.0)
        self.assertEqual(queries.revenue(iso(-5), iso(0)), 5490.0)
        self.assertEqual(queries.revenue(iso(1), iso(5)), 0)

    def test_revenue_period_borders_are_inclusive(self):
        self.assertEqual(queries.revenue(iso(-10), iso(-10)), 2390.0)

    def test_avg_check(self):
        self.assertAlmostEqual(queries.avg_check(), (2390.0 + 5490.0) / 2)

    def test_avg_check_without_issues_is_zero(self):
        conn = __import__("db").get_connection()
        conn.execute("DELETE FROM issues")
        conn.commit()
        conn.close()
        self.assertEqual(queries.avg_check(), 0)

    def test_expiring_orders(self):
        rows = queries.expiring_orders(2)
        # заказ 1 выдан в setUp; на хранении остались 3 (срок истёк) и 2 (остался 1 день)
        self.assertEqual([r["tracking_number"] for r in rows], ["2026000000003", "2026000000002"])

    def test_expiring_orders_wider_window(self):
        numbers = {r["tracking_number"] for r in queries.expiring_orders(10)}
        self.assertEqual(numbers, {"2026000000002", "2026000000003"})

    def test_expiring_orders_zero_days(self):
        numbers = {r["tracking_number"] for r in queries.expiring_orders(0)}
        self.assertEqual(numbers, {"2026000000003"})

    def test_issues_by_month(self):
        rows = queries.issues_by_month()
        self.assertEqual(sum(r["issued"] for r in rows), 2)
        self.assertEqual(sum(r["revenue"] for r in rows), 7880.0)

    def test_search_orders_like(self):
        self.assertEqual(len(queries.search_orders("Куртка")), 1)
        self.assertEqual(len(queries.search_orders("000000003")), 1)
        self.assertEqual(queries.search_orders("zzz"), [])

    def test_print_table_prints_rows_and_headers(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            queries.print_table(queries.search_orders("Куртка"))
        text = buffer.getvalue()
        self.assertIn("tracking_number", text)
        self.assertIn("Куртка зимняя", text)

    def test_print_table_empty(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            queries.print_table([])
        self.assertIn("нет данных", buffer.getvalue())


class ReportHelpersTests(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt_(5.0), "5.00")
        self.assertEqual(fmt_(7), "7")
        self.assertEqual(fmt_("текст"), "текст")

    def test_is_expiring(self):
        self.assertTrue(reports.is_expiring("stored", iso(-1)))      # срок истёк
        self.assertTrue(reports.is_expiring("stored", iso(0)))
        self.assertTrue(reports.is_expiring("stored", iso(2)))       # граница: 2 дня
        self.assertFalse(reports.is_expiring("stored", iso(3)))
        self.assertFalse(reports.is_expiring("issued", iso(-5)))     # не на хранении
        self.assertFalse(reports.is_expiring("stored", "не дата"))


def fmt_(value):
    return reports.fmt(value)


class ReportsTests(DbTestCase):
    def test_report_issues_totals(self):
        rep = reports.report_issues(iso(-30), iso(0))
        self.assertEqual(len(rep.rows), 1)
        self.assertEqual(rep.rows[0][1], "2026000000004")
        self.assertIn("Выдано заказов: 1", rep.total)
        self.assertIn("2390.00", rep.total)

    def test_report_issues_empty_period(self):
        rep = reports.report_issues(iso(1), iso(2))
        self.assertEqual(rep.rows, [])
        self.assertIn("0.00", rep.total)

    def test_report_top10_all_and_by_carrier(self):
        self.issue(self.o1, days=-1, paid=5490.0)
        all_rep = reports.report_top10()
        self.assertEqual(all_rep.rows[0][0], 1)                     # место
        self.assertEqual(all_rep.rows[0][1], "Петров Сергей Иванович")
        self.assertEqual(all_rep.rows[0][3], 2)                     # заказов
        ozon = reports.report_top10("Ozon")
        self.assertEqual(ozon.rows[0][3], 1)                        # у Ozon выдан только заказ 4
        self.assertEqual(reports.report_top10("Нет такой").rows, [])

    def test_report_stored_marks_expiring_rows_red(self):
        rep = reports.report_stored()
        self.assertEqual(len(rep.rows), 3)
        self.assertEqual(rep.rows[0][0], "2026000000003")            # сначала просроченный
        self.assertEqual(rep.red_rows, [0, 1])                      # срок <= 2 дней: заказы 3 и 2
        self.assertIn("Заказов на хранении: 3", rep.total)

    def test_save_csv_format(self):
        path = reports.save_csv(reports.report_stored())
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))            # BOM для Excel
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[0], ["Заказы на хранении"])
        self.assertEqual(rows[3][0], "Трек-номер")
        self.assertEqual(rows[4][0], "2026000000003")

    def test_save_html_escapes_text_and_marks_rows(self):
        rep = reports.report_stored()
        rep.title = "<script>alert(1)</script>"
        path = reports.save_html(rep)
        with open(path, encoding="utf-8") as f:
            page = f.read()
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertEqual(page.count('<tr class="low">'), 2)

    def test_file_names_contain_report_name_and_date(self):
        path = reports.save_csv(reports.report_issues(iso(-30), iso(0)))
        self.assertIn("issues_" + date.today().isoformat(), os.path.basename(path))


if __name__ == "__main__":
    unittest.main()
