"""Вход в систему: хеширование паролей и права ролей."""
import hashlib
import hmac
import logging
import os

from db import get_connection


def hash_password(password, salt=None):
    """Возвращает строку "соль$хеш" (SHA-256 + случайная соль)."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return salt.hex() + "$" + digest


def check_password(password, stored):
    """Сверяет пароль с сохранённой строкой "соль$хеш"."""
    salt_hex = stored.split("$")[0]
    new_hash = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(new_hash, stored)


def login(login_name, password):
    """Возвращает данные пользователя или None, если логин/пароль неверные."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, full_name, role, password_hash FROM employees WHERE login = ?",
            (login_name,)).fetchone()
    finally:
        conn.close()
    if row and check_password(password, row["password_hash"]):
        logging.info("Вход выполнен: %s (роль %s)", login_name, row["role"])
        return {"id": row["id"], "login": login_name,
                "full_name": row["full_name"], "role": row["role"]}
    logging.warning("Неудачная попытка входа: %s", login_name)
    return None


def can_edit(role):
    """Может ли роль изменять данные."""
    return role in ("admin", "manager") # report - только просмотр


def is_admin(role):
    """Является ли роль администратором."""
    return role == "admin"
