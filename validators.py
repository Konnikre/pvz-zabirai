import re
from datetime import datetime


def _is_digits(text, length):
    return text.isascii() and text.isdigit() and len(text) == length


def validate_order(tracking, description, amount, pickup_code, cell,
                   carrier, recipient, phone):
    """Проверка формы заказа. Возвращает список ошибок (пустой - всё верно)."""
    errors = []
    if not _is_digits(tracking, 13):
        errors.append("Трек-номер должен состоять ровно из 13 цифр")
    if not description.strip():
        errors.append("Укажите товар (описание заказа)")
    try:
        if float(amount.replace(",", ".")) < 0:
            errors.append("Сумма к оплате не может быть отрицательной")
    except ValueError:
        errors.append("Сумма к оплате должна быть числом (0 - заказ оплачен)")
    if not _is_digits(pickup_code, 4):
        errors.append("Код получения должен состоять из 4 цифр")
    if not re.fullmatch(r"[A-Za-z]-\d{1,3}", cell):
        errors.append("Ячейка указывается в формате A-12")
    if not carrier.strip():
        errors.append("Укажите службу доставки")
    if not recipient.strip():
        errors.append("Укажите получателя")
    if len(re.sub(r"\D", "", phone)) not in (10, 11):
        errors.append("Телефон должен содержать 10-11 цифр")
    return errors


def validate_search(text):
    """Поиск: пустая строка допустима (показать всё), иначе не менее 3 символов."""
    if text and len(text) < 3:
        return "Для поиска введите не менее 3 символов"
    return ""


def validate_login(login_name, password):
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
    if not _is_digits(entered_code, 4):
        return "Код получения состоит из 4 цифр"
    if entered_code != real_code:
        return "Неверный код получения. Заказ не выдан"
    return ""


def validate_employee(full_name, login_name, password, role):
    errors = []
    if not full_name.strip():
        errors.append("Укажите ФИО")
    if not login_name.strip():
        errors.append("Укажите логин")
    if len(password) < 6:
        errors.append("Пароль должен быть не короче 6 символов")
    if role not in ("admin", "manager", "report"):
        errors.append("Выберите роль")
    return errors
