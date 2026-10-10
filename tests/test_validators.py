"""Модульные тесты validators.py (метод «чёрного ящика»: классы эквивалентности и граничные значения)."""
import unittest

import validators as v


def order(**kw):
    data = dict(tracking="2026000000099", description="Монитор", amount="5990", pickup_code="4321",
                cell="E-01", carrier="Ozon", recipient="Петров С. И.", phone="+7 (900) 000-00-01")
    data.update(kw)
    return v.validate_order(data["tracking"], data["description"], data["amount"], data["pickup_code"],
                            data["cell"], data["carrier"], data["recipient"], data["phone"])


class ValidateOrderTests(unittest.TestCase):
    def test_valid_order_has_no_errors(self):
        self.assertEqual(order(), [])

    def test_tracking_boundaries(self):
        self.assertTrue(order(tracking="202600000009"))        # 12 цифр
        self.assertEqual(order(tracking="2026000000099"), [])  # 13 цифр
        self.assertTrue(order(tracking="20260000000999"))      # 14 цифр

    def test_tracking_rejects_letters_and_non_ascii_digits(self):
        self.assertTrue(order(tracking="2026ABC000099"))
        self.assertTrue(order(tracking="٢٠٢٦٠٠٠٠٠٠٠٠٩٩"[:13]))

    def test_description_required(self):
        self.assertTrue(order(description=""))
        self.assertTrue(order(description="   "))

    def test_amount_valid_values(self):
        for value in ("0", "0.0", "100", "100,50", "5990.99"):
            self.assertEqual(order(amount=value), [], value)

    def test_amount_negative_and_text(self):
        self.assertTrue(order(amount="-0.01"))
        self.assertTrue(order(amount="abc"))
        self.assertTrue(order(amount=""))

    def test_amount_rejects_nan_and_infinity(self):
        # DEF-02: float("nan") и float("inf") раньше проходили проверку
        for value in ("nan", "inf", "-inf", "Infinity"):
            self.assertTrue(order(amount=value), value)

    def test_pickup_code_boundaries(self):
        self.assertTrue(order(pickup_code="123"))
        self.assertEqual(order(pickup_code="1234"), [])
        self.assertTrue(order(pickup_code="12345"))
        self.assertTrue(order(pickup_code="12a4"))

    def test_cell_formats(self):
        for good in ("A-1", "A-12", "b-123", "E-01"):
            self.assertEqual(order(cell=good), [], good)
        for bad in ("A12", "AB-1", "A-1234", "A-", "-12", ""):
            self.assertTrue(order(cell=bad), bad)

    def test_carrier_and_recipient_required(self):
        self.assertTrue(order(carrier=" "))
        self.assertTrue(order(recipient=""))

    def test_phone_digit_count_boundaries(self):
        self.assertTrue(order(phone="123456789"))        # 9
        self.assertEqual(order(phone="1234567890"), [])  # 10
        self.assertEqual(order(phone="+7 900 000 00 01"), [])  # 11
        self.assertTrue(order(phone="123456789012"))     # 12

    def test_all_errors_reported_together(self):
        errors = v.validate_order("1", "", "x", "1", "?", "", "", "1")
        self.assertEqual(len(errors), 8)


class OtherValidatorsTests(unittest.TestCase):
    def test_search(self):
        self.assertEqual(v.validate_search(""), "")
        self.assertTrue(v.validate_search("ab"))
        self.assertEqual(v.validate_search("abc"), "")

    def test_login(self):
        self.assertEqual(v.validate_login("admin", "x"), "")
        self.assertTrue(v.validate_login("", "x"))
        self.assertTrue(v.validate_login("admin", ""))

    def test_dates(self):
        self.assertEqual(v.validate_dates("2026-01-01", "2026-12-31"), "")
        self.assertEqual(v.validate_dates("2026-05-05", "2026-05-05"), "")
        self.assertIn("позже", v.validate_dates("2026-12-31", "2026-01-01"))
        self.assertIn("формате", v.validate_dates("01.01.2026", "2026-12-31"))
        self.assertIn("формате", v.validate_dates("2026-02-30", "2026-03-01"))

    def test_issue_code(self):
        self.assertEqual(v.validate_issue("4321", "4321"), "")
        self.assertIn("Неверный", v.validate_issue("0000", "4321"))
        self.assertIn("4 цифр", v.validate_issue("432", "4321"))
        self.assertIn("4 цифр", v.validate_issue("43a1", "4321"))

    def test_employee(self):
        self.assertEqual(v.validate_employee("Иванов И. И.", "ivanov", "secret", "manager"), [])
        self.assertTrue(v.validate_employee("", "ivanov", "secret", "manager"))
        self.assertTrue(v.validate_employee("Иванов", " ", "secret", "manager"))
        self.assertTrue(v.validate_employee("Иванов", "ivanov", "12345", "manager"))   # 5 символов
        self.assertEqual(v.validate_employee("Иванов", "ivanov", "123456", "manager"), [])  # 6 символов
        self.assertTrue(v.validate_employee("Иванов", "ivanov", "secret", "boss"))


if __name__ == "__main__":
    unittest.main()
