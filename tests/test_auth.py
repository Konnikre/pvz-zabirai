"""Модульные и интеграционные тесты auth.py."""
import unittest

import auth
from tests.base import DbTestCase


class PasswordTests(unittest.TestCase):
    def test_hash_format_is_salt_dollar_hash(self):
        stored = auth.hash_password("secret1")
        salt, digest = stored.split("$")
        self.assertEqual(len(salt), 32)      # 16 байт в hex
        self.assertEqual(len(digest), 64)    # SHA-256 в hex

    def test_same_password_gets_different_salt(self):
        self.assertNotEqual(auth.hash_password("secret1"), auth.hash_password("secret1"))

    def test_hash_with_given_salt_is_deterministic(self):
        salt = bytes(range(16))
        self.assertEqual(auth.hash_password("x", salt), auth.hash_password("x", salt))

    def test_password_is_not_stored_in_clear(self):
        self.assertNotIn("secret1", auth.hash_password("secret1"))

    def test_check_password(self):
        stored = auth.hash_password("secret1")
        self.assertTrue(auth.check_password("secret1", stored))
        self.assertFalse(auth.check_password("Secret1", stored))
        self.assertFalse(auth.check_password("", stored))


class RolesTests(unittest.TestCase):
    def test_can_edit(self):
        self.assertTrue(auth.can_edit("admin"))
        self.assertTrue(auth.can_edit("manager"))
        self.assertFalse(auth.can_edit("report"))

    def test_is_admin(self):
        self.assertTrue(auth.is_admin("admin"))
        self.assertFalse(auth.is_admin("manager"))


class LoginTests(DbTestCase):
    def test_login_success_returns_user(self):
        user = auth.login("manager", "manager123")
        self.assertEqual(user["role"], "manager")
        self.assertEqual(user["login"], "manager")
        self.assertNotIn("password_hash", user)

    def test_login_all_roles(self):
        for login, password, role in (("admin", "admin123", "admin"), ("report", "report123", "report")):
            self.assertEqual(auth.login(login, password)["role"], role)

    def test_wrong_password(self):
        self.assertIsNone(auth.login("manager", "wrong"))

    def test_unknown_user(self):
        self.assertIsNone(auth.login("nobody", "manager123"))

    def test_login_is_case_sensitive_for_password(self):
        self.assertIsNone(auth.login("manager", "MANAGER123"))

    def test_sql_injection_in_login_is_harmless(self):
        self.assertIsNone(auth.login("' OR '1'='1", "x"))
        self.assertIsNone(auth.login("manager' --", "x"))


if __name__ == "__main__":
    unittest.main()
