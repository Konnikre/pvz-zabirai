"""Проверка данных, которые вводит пользователь (слой бизнес-логики)."""
import math
import re
from datetime import datetime

TRACKING_LENGTH = 13      # длина трек-номера
PICKUP_CODE_LENGTH = 4    # длина кода получения
MIN_PASSWORD_LENGTH = 6   # минимальная длина пароля
MIN_SEARCH_LENGTH = 3     # минимальная длина поискового запроса
ROLES = ("admin", "manager", "report")


def _is_digits(text, length):
    return text.isascii() and text.isdigit() and len(text) == length


def _check_amount(amount):
    """Проверка суммы к оплате. Возвращает текст ошибки или пустую строку."""
    try:
        value = float(amount.replace(",", "."))
    except ValueError:
        return "Сумма к оплате должна быть числом (0 - заказ оплачен)"
    if not math.isfinite(value):
        return "Сумма к оплате должна быть конечным числом"
    if value < 0:
        return "Сумма к оплате не может быть отрицательной"
    return ""


def _check_required(fields):
    """Проверка обязательных текстовых полей: fields - пары (значение, сообщение)."""
    return [message for value, message in fields if not value.strip()]


def validate_order(tracking, description, amount, pickup_code, cell,
                   carrier, recipient, phone):
    """Проверка формы заказа. Возвращает список ошибок (пустой - всё верно)."""
    errors = []
    if not _is_digits(tracking, TRACKING_LENGTH):
        errors.append(f"Трек-номер должен состоять ровно из {TRACKING_LENGTH} цифр")
    errors += _check_required([(description, "Укажите товар (описание заказа)")])
    amount_error = _check_amount(amount)
    if amount_error:
        errors.append(amount_error)
    if not _is_digits(pickup_code, PICKUP_CODE_LENGTH):
        errors.append(f"Код получения должен состоять из {PICKUP_CODE_LENGTH} цифр")
    if not re.fullmatch(r"[A-Za-z]-\d{1,3}", cell):
        errors.append("Ячейка указывается в формате A-12")
    errors += _check_required([(carrier, "Укажите службу доставки"),
                               (recipient, "Укажите получателя")])
    if len(re.sub(r"\D", "", phone)) not in (10, 11):
        errors.append("Телефон должен содержать 10-11 цифр")
    return errors


def validate_search(text):
    """Поиск: пустая строка допустима (показать всё), иначе не менее 3 символов."""
    if text and len(text) < MIN_SEARCH_LENGTH:
        return f"Для поиска введите не менее {MIN_SEARCH_LENGTH} символов"
    return ""


def validate_login(login_name, password):
    """Проверка формы входа: логин и пароль не должны быть пустыми."""
    if not login_name or not password:
        return "Логин и пароль не должны быть пустыми"
    return ""


def validate_dates(start, end):
    """Даты в формате ГГГГ-ММ-ДД, начало не позже окончания."""
    try:
        d1 = datetime.strptime(start, "%Y-%m-%d")
        d2 = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        return "Даты нужно вводить в формате ГГГГ-ММ-ДД"
    if d1 > d2:
        return "Дата начала не может быть позже даты окончания"
    return ""


def validate_issue(entered_code, real_code):
    """Проверка кода получения, который называет клиент."""
    if not _is_digits(entered_code, PICKUP_CODE_LENGTH):
        return f"Код получения состоит из {PICKUP_CODE_LENGTH} цифр"
    if entered_code != real_code:
        return "Неверный код получения. Заказ не выдан"
    return ""


def validate_employee(full_name, login_name, password, role):
    """Проверка формы нового сотрудника. Возвращает список ошибок."""
    errors = []
    if not full_name.strip():
        errors.append("Укажите ФИО")
    if not login_name.strip():
        errors.append("Укажите логин")
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if role not in ROLES:
        errors.append("Выберите роль")
    return errors