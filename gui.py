import logging
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

import auth
import backup
import reports
import validators
from db import APP_NAME
from models import Order, STATUS_NAMES, STATUS_STORED
from repository import (EmployeeRepository, IssueRepository, OrderRepository,
                        ReferenceRepository)

MAX_ATTEMPTS = 3                    # число попыток ввода пароля

COLUMNS = {
    "id": ("№", 40),
    "tracking_number": ("Трек-номер", 115),
    "description": ("Товар", 210),
    "recipient": ("Получатель", 170),
    "carrier": ("Служба доставки", 120),
    "cell": ("Ячейка", 60),
    "amount": ("К оплате", 80),
    "status_text": ("Статус", 95),
    "storage_until": ("Хранить до", 90),
}

ALL_STATUSES = "Все статусы"
STATUS_CODES = {name: code for code, name in STATUS_NAMES.items()}   # "На хранении" -> "stored"

REPORT_TYPES = ["Выдачи за период", "Топ-10 получателей", "Заказы на хранении"]


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - Вход")
        self.resizable(False, False)
        self.user = None                    # сюда попадёт результат входа
        self.attempts = 0
        self.login_var = tk.StringVar()
        self.password_var = tk.StringVar()

        frame = ttk.Frame(self, padding=16)
        frame.pack()
        ttk.Label(frame, text="Логин:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.login_var, width=25).grid(row=0, column=1)
        ttk.Label(frame, text="Пароль:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.password_var, show="*",
                  width=25).grid(row=1, column=1)
        ttk.Button(frame, text="Войти", command=self.on_login).grid(
            row=2, column=0, columnspan=2, pady=(10, 0))
        self.bind("<Return>", lambda event: self.on_login())

    def on_login(self):
        login_name = self.login_var.get().strip()
        password = self.password_var.get()
        error = validators.validate_login(login_name, password)
        if error:
            messagebox.showwarning("Внимание", error)
            return
        try:
            user = auth.login(login_name, password)
        except sqlite3.Error as e:
            logging.error("Вход: ошибка БД: %s", e)
            messagebox.showerror("Ошибка", "База данных недоступна.\n"
                                 "Запустите seed.py для создания БД.")
            return
        if user:
            self.user = user
            self.destroy()
            return
        self.attempts += 1
        left = MAX_ATTEMPTS - self.attempts
        if left <= 0:
            messagebox.showerror("Доступ закрыт", "Превышено число попыток входа")
            self.destroy()
        else:
            messagebox.showerror("Ошибка", f"Неверный логин или пароль.\n"
                                 f"Осталось попыток: {left}")


class MainWindow(tk.Tk):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.can_edit = auth.can_edit(user["role"])
        self.repo = OrderRepository()
        self.refs = ReferenceRepository()
        self.title(f"{APP_NAME} - Управление заказами")
        self.geometry("1150x540")

        self.text_var = tk.StringVar()
        self.recipient_var = tk.StringVar()
        self.status_var = tk.StringVar(value=ALL_STATUSES)
        self.info_var = tk.StringVar()

        self.create_menu()
        ttk.Label(self, textvariable=self.info_var, relief="sunken",
                  anchor="w").pack(side="bottom", fill="x")
        self.create_toolbar()
        self.create_table()
        self.bind("<Return>", lambda event: self.search())
        self.reset()

    def create_menu(self):
        menubar = tk.Menu(self)
        admin = "normal" if auth.is_admin(self.user["role"]) else "disabled"
        edit = "normal" if self.can_edit else "disabled"

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Резервная копия БД", command=self.make_backup, state=admin)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        menubar.add_cascade(label="Файл", menu=file_menu)

        orders_menu = tk.Menu(menubar, tearoff=0)
        orders_menu.add_command(label="Принять заказ", command=self.add_order, state=edit)
        orders_menu.add_command(label="Изменить", command=self.edit_order, state=edit)
        orders_menu.add_command(label="Удалить", command=self.delete_order, state=edit)
        orders_menu.add_separator()
        orders_menu.add_command(label="Выдать заказ", command=self.issue_order, state=edit)
        orders_menu.add_command(label="Вернуть отправителю", command=self.return_order, state=edit)
        menubar.add_cascade(label="Заказы", menu=orders_menu)

        menubar.add_command(label="Отчёты", command=self.open_reports)
        menubar.add_command(label="Сотрудники", command=self.open_users, state=admin)
        menubar.add_command(label="О программе", command=lambda: messagebox.showinfo(
            "О программе", f"{APP_NAME}\nПункт выдачи заказов\n"
                           "Учебная практика: Python + SQLite + Tkinter"))
        self.config(menu=menubar)

    def create_toolbar(self):
        search = ttk.Frame(self, padding=8)
        search.pack(side="top", fill="x")
        ttk.Label(search, text="Трек-номер / товар:").pack(side="left")
        ttk.Entry(search, textvariable=self.text_var, width=22).pack(side="left", padx=(4, 10))
        ttk.Label(search, text="Получатель:").pack(side="left")
        ttk.Entry(search, textvariable=self.recipient_var, width=20).pack(side="left", padx=(4, 10))
        ttk.Label(search, text="Статус:").pack(side="left")
        ttk.Combobox(search, textvariable=self.status_var, state="readonly", width=14,
                     values=[ALL_STATUSES] + list(STATUS_CODES)
                     ).pack(side="left", padx=(4, 10))
        ttk.Button(search, text="Найти", command=self.search).pack(side="left")
        ttk.Button(search, text="Сбросить", command=self.reset).pack(side="left", padx=4)

        actions = ttk.Frame(self, padding=(8, 0, 8, 8))
        actions.pack(side="top", fill="x")
        buttons = (("Принять заказ", self.add_order), ("Изменить", self.edit_order),
                   ("Удалить", self.delete_order), ("Выдать заказ", self.issue_order),
                   ("Вернуть отправителю", self.return_order))
        for text, command in buttons:
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side="left", padx=(0, 4))
            if not self.can_edit:               # роль report - только просмотр
                button.state(["disabled"])

    def create_table(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ttk.Treeview(frame, columns=list(COLUMNS), show="headings")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        for col, (text, width) in COLUMNS.items():
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_by(c, False))
            self.tree.column(col, width=width)
        self.tree.tag_configure("low", foreground="red")      # срок хранения истекает
        self.tree.tag_configure("done", foreground="gray")    # выдан или возвращён
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        if self.can_edit:
            self.tree.bind("<Double-1>", lambda event: self.edit_order())

    def load_orders(self, rows):
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            if r["status"] != STATUS_STORED:
                tags = ("done",)
            elif reports.is_expiring(r["status"], r["storage_until"]):
                tags = ("low",)
            else:
                tags = ()
            self.tree.insert("", "end", tags=tags, values=(
                r["id"], r["tracking_number"], r["description"], r["recipient"],
                r["carrier"], r["cell"], f"{r['amount']:.2f}", r["status_text"],
                r["storage_until"]))
        stored = sum(1 for r in rows if r["status"] == STATUS_STORED)
        self.info_var.set(f"Пользователь: {self.user['full_name']} ({self.user['role']})"
                          f"   |   Заказов в списке: {len(rows)}   |   На хранении: {stored}")

    def sort_by(self, col, descending):
        """Сортировка по щелчку на заголовок столбца."""
        items = [(self.tree.set(i, col), i) for i in self.tree.get_children("")]
        try:
            items.sort(key=lambda x: float(x[0]), reverse=descending)   # числа
        except ValueError:
            items.sort(key=lambda x: x[0].lower(), reverse=descending)  # текст и даты
        for index, (_, item) in enumerate(items):
            self.tree.move(item, "", index)
        # следующий щелчок сортирует в обратную сторону
        self.tree.heading(col, command=lambda: self.sort_by(col, not descending))

    def get_selected_id(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите заказ в таблице")
            return None
        return int(self.tree.set(selection[0], "id"))

    def log_action(self, text):
        logging.info("Пользователь %s: %s", self.user["login"], text)

    def search(self):
        text = self.text_var.get().strip()
        recipient = self.recipient_var.get().strip()
        for value in (text, recipient):
            error = validators.validate_search(value)
            if error:
                messagebox.showwarning("Поиск", error)
                return
        status = STATUS_CODES.get(self.status_var.get())               # None - все
        self.load_orders(self.repo.search_orders(text, recipient, status))

    def reset(self):
        self.text_var.set("")
        self.recipient_var.set("")
        self.status_var.set(ALL_STATUSES)
        self.load_orders(self.repo.get_all_orders())

    def after_save(self, text):
        self.log_action(text)
        self.reset()

    def add_order(self):
        OrderForm(self, self.repo, self.refs, self.after_save)

    def edit_order(self):
        order_id = self.get_selected_id()
        if order_id is None:
            return
        order = self.repo.get_order_by_id(order_id)
        if order.status != STATUS_STORED:
            messagebox.showwarning("Изменение невозможно",
                                   "Изменять можно только заказы на хранении")
            return
        OrderForm(self, self.repo, self.refs, self.after_save, order=order)

    def delete_order(self):
        order_id = self.get_selected_id()
        if order_id is None:
            return
        number = self.tree.set(self.tree.selection()[0], "tracking_number")
        if not messagebox.askyesno("Подтверждение", f"Удалить заказ {number}?"):
            return
        try:
            self.repo.delete_order(order_id)
        except sqlite3.Error as e:
            # сработал триггер: заказ уже выдан
            messagebox.showerror("Удаление невозможно", str(e))
            return
        self.after_save(f"удалён заказ {number}")

    def issue_order(self):
        order_id = self.get_selected_id()
        if order_id is None:
            return
        order = self.repo.get_order_by_id(order_id)
        if order.status != STATUS_STORED:
            messagebox.showwarning("Выдача невозможна", "Этот заказ уже не на хранении")
            return
        recipient = self.tree.set(self.tree.selection()[0], "recipient")
        IssueForm(self, order, recipient, self.user["id"], self.after_save)

    def return_order(self):
        order_id = self.get_selected_id()
        if order_id is None:
            return
        order = self.repo.get_order_by_id(order_id)
        if order.status != STATUS_STORED:
            messagebox.showwarning("Возврат невозможен",
                                   "Вернуть можно только заказ, который лежит на хранении")
            return
        if not messagebox.askyesno("Подтверждение",
                                   f"Вернуть заказ {order.tracking_number} отправителю?"):
            return
        try:
            self.repo.return_order(order_id)
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка", f"Не удалось оформить возврат: {e}")
            return
        self.after_save(f"заказ {order.tracking_number} возвращён отправителю")

    def open_reports(self):
        ReportWindow(self, self.refs)

    def open_users(self):
        UsersWindow(self)

    def make_backup(self):
        status = backup.make_backup()
        self.log_action(f"резервная копия БД: {status}")
        if status == "OK":
            messagebox.showinfo("Резервная копия", "Копия создана в папке backups/")
        else:
            messagebox.showerror("Резервная копия", status)


class OrderForm(tk.Toplevel):
    """Приём (order=None) или редактирование заказа."""

    def __init__(self, parent, order_repo, ref_repo, on_save, order=None):
        super().__init__(parent)
        self.order_repo = order_repo
        self.ref_repo = ref_repo
        self.on_save = on_save
        self.order = order
        self.title("Редактирование заказа" if order else "Приём заказа")
        self.resizable(False, False)
        self.transient(parent)

        self.carriers = {r["name"]: r["id"] for r in ref_repo.get_carriers()}
        recipients = ref_repo.get_recipients()
        self.phones = {r["full_name"]: r["phone"] for r in recipients}   # ФИО -> телефон
        self.recipients_by_id = {r["id"]: r for r in recipients}

        self.tracking_var = tk.StringVar()
        self.descr_var = tk.StringVar()
        self.amount_var = tk.StringVar(value="0")
        self.code_var = tk.StringVar()
        self.cell_var = tk.StringVar()
        self.carrier_var = tk.StringVar()
        self.recipient_var = tk.StringVar()
        self.phone_var = tk.StringVar()

        frame = ttk.Frame(self, padding=12)
        frame.pack()
        recipient_box = ttk.Combobox(frame, textvariable=self.recipient_var,
                                     values=list(self.phones), width=39)
        recipient_box.bind("<<ComboboxSelected>>", lambda event: self.fill_phone())
        rows = [
            ("Трек-номер (13 цифр):", ttk.Entry(frame, textvariable=self.tracking_var, width=42)),
            ("Товар:", ttk.Entry(frame, textvariable=self.descr_var, width=42)),
            ("К оплате (0 - оплачен):", ttk.Entry(frame, textvariable=self.amount_var, width=42)),
            ("Код получения (4 цифры):", ttk.Entry(frame, textvariable=self.code_var, width=42)),
            ("Ячейка (например A-12):", ttk.Entry(frame, textvariable=self.cell_var, width=42)),
            # службу доставки и получателя можно выбрать из списка или ввести новых
            ("Служба доставки:", ttk.Combobox(frame, textvariable=self.carrier_var,
                                              values=list(self.carriers), width=39)),
            ("Получатель (ФИО):", recipient_box),
            ("Телефон получателя:", ttk.Entry(frame, textvariable=self.phone_var, width=42)),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=3)
            widget.grid(row=i, column=1, padx=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(rows), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(buttons, text="Сохранить", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left")

        if order:
            recipient = self.recipients_by_id.get(order.recipient_id)
            self.tracking_var.set(order.tracking_number)
            self.descr_var.set(order.description)
            self.amount_var.set(str(order.amount))
            self.code_var.set(order.pickup_code)
            self.cell_var.set(order.cell)
            self.carrier_var.set(next((n for n, i in self.carriers.items()
                                       if i == order.carrier_id), ""))
            if recipient:
                self.recipient_var.set(recipient["full_name"])
                self.phone_var.set(recipient["phone"])

        self.wait_visibility()
        self.grab_set()

    def fill_phone(self):
        """При выборе известного получателя подставляем его телефон."""
        self.phone_var.set(self.phones.get(self.recipient_var.get(), ""))

    def save(self):
        tracking = self.tracking_var.get().strip()
        descr = self.descr_var.get().strip()
        amount = self.amount_var.get().strip()
        code = self.code_var.get().strip()
        cell = self.cell_var.get().strip().upper()
        carrier = self.carrier_var.get().strip()
        recipient = self.recipient_var.get().strip()
        phone = self.phone_var.get().strip()

        errors = validators.validate_order(tracking, descr, amount, code, cell,
                                           carrier, recipient, phone)
        if errors:
            messagebox.showerror("Ошибка ввода", "\n".join(errors), parent=self)
            return

        try:
            order = Order(
                id=self.order.id if self.order else None,
                tracking_number=tracking, description=descr,
                amount=float(amount.replace(",", ".")),
                pickup_code=code, cell=cell,
                carrier_id=self.ref_repo.get_or_create_carrier(carrier),
                recipient_id=self.ref_repo.get_or_create_recipient(recipient, phone))
            if self.order:
                self.order_repo.update_order(order)
            else:
                self.order_repo.add_order(order)
        except sqlite3.IntegrityError as e:
            if "tracking_number" in str(e).lower():
                message = "Заказ с таким трек-номером уже есть в базе"
            else:
                message = f"Нарушено ограничение БД: {e}"
            messagebox.showerror("Ошибка", message, parent=self)
            return
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить заказ: {e}", parent=self)
            return

        action = "изменён" if self.order else "принят"
        self.on_save(f"{action} заказ {tracking} ({descr})")
        self.destroy()


class IssueForm(tk.Toplevel):
    """Выдача заказа: клиент называет код получения, сотрудник принимает оплату."""

    def __init__(self, parent, order, recipient, employee_id, on_save):
        super().__init__(parent)
        self.order = order
        self.employee_id = employee_id
        self.on_save = on_save
        self.title("Выдача заказа")
        self.resizable(False, False)
        self.transient(parent)

        self.code_var = tk.StringVar()

        frame = ttk.Frame(self, padding=12)
        frame.pack()
        pay = (f"{order.amount:.2f} руб. (принять оплату)" if order.amount > 0
               else "0.00 руб. (заказ оплачен)")
        info = (("Трек-номер:", order.tracking_number), ("Товар:", order.description),
                ("Получатель:", recipient), ("Ячейка:", order.cell), ("К оплате:", pay))
        for i, (label, value) in enumerate(info):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Label(frame, text=value).grid(row=i, column=1, sticky="w", padx=(8, 0))
        ttk.Label(frame, text="Код получения:").grid(row=len(info), column=0, sticky="w", pady=3)
        entry = ttk.Entry(frame, textvariable=self.code_var, width=10, show="*")
        entry.grid(row=len(info), column=1, sticky="w", padx=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(info) + 1, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(buttons, text="Выдать", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left")
        self.bind("<Return>", lambda event: self.save())

        self.wait_visibility()
        self.grab_set()
        entry.focus_set()

    def save(self):
        error = validators.validate_issue(self.code_var.get().strip(), self.order.pickup_code)
        if error:
            messagebox.showerror("Ошибка ввода", error, parent=self)
            return
        try:
            IssueRepository().issue_order(self.order.id, self.employee_id, self.order.amount)
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка", f"Заказ не выдан: {e}", parent=self)
            return
        self.on_save(f"выдан заказ {self.order.tracking_number} ({self.order.description})")
        self.destroy()


class ReportWindow(tk.Toplevel):
    def __init__(self, parent, ref_repo):
        super().__init__(parent)
        self.title("Отчёты")
        self.geometry("920x500")
        self.report = None

        today = date.today()
        self.type_var = tk.StringVar(value=REPORT_TYPES[0])
        self.start_var = tk.StringVar(value=f"{today.year}-01-01")
        self.end_var = tk.StringVar(value=str(today))
        self.carrier_var = tk.StringVar(value=reports.ALL_CARRIERS)
        self.total_var = tk.StringVar()

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Отчёт:").grid(row=0, column=0, sticky="w", pady=3)
        type_box = ttk.Combobox(top, textvariable=self.type_var, values=REPORT_TYPES,
                                state="readonly", width=26)
        type_box.grid(row=0, column=1, columnspan=3, sticky="w", padx=4)
        type_box.bind("<<ComboboxSelected>>", lambda event: self.on_type_change())

        ttk.Label(top, text="Период с (ГГГГ-ММ-ДД):").grid(row=1, column=0, sticky="w", pady=3)
        self.start_entry = ttk.Entry(top, textvariable=self.start_var, width=12)
        self.start_entry.grid(row=1, column=1, padx=4)
        ttk.Label(top, text="по:").grid(row=1, column=2)
        self.end_entry = ttk.Entry(top, textvariable=self.end_var, width=12)
        self.end_entry.grid(row=1, column=3, padx=4)

        ttk.Label(top, text="Служба доставки:").grid(row=2, column=0, sticky="w", pady=3)
        names = [reports.ALL_CARRIERS] + [r["name"] for r in ref_repo.get_carriers()]
        self.carrier_box = ttk.Combobox(top, textvariable=self.carrier_var, values=names,
                                        state="readonly", width=30)
        self.carrier_box.grid(row=2, column=1, columnspan=3, sticky="w", padx=4)
        ttk.Button(top, text="Сформировать", command=self.build_report).grid(
            row=0, column=4, rowspan=3, padx=20)

        self.tree = ttk.Treeview(self, show="headings")
        self.tree.tag_configure("low", foreground="red")
        self.tree.pack(fill="both", expand=True, padx=8)
        ttk.Label(self, textvariable=self.total_var,
                  font=("Arial", 10, "bold")).pack(anchor="w", padx=8, pady=4)

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Сохранить в CSV",
                   command=lambda: self.save("csv")).pack(side="left")
        ttk.Button(bottom, text="Сохранить в HTML",
                   command=lambda: self.save("html")).pack(side="left", padx=6)
        self.on_type_change()

    def on_type_change(self):
        """Доступны только параметры выбранного отчёта."""
        kind = self.type_var.get()
        self.start_entry.configure(state="normal" if kind == REPORT_TYPES[0] else "disabled")
        self.end_entry.configure(state="normal" if kind == REPORT_TYPES[0] else "disabled")
        self.carrier_box.configure(state="readonly" if kind == REPORT_TYPES[1] else "disabled")

    def build_report(self):
        kind = self.type_var.get()
        try:
            if kind == REPORT_TYPES[0]:
                start, end = self.start_var.get().strip(), self.end_var.get().strip()
                error = validators.validate_dates(start, end)
                if error:
                    messagebox.showwarning("Параметры отчёта", error, parent=self)
                    return
                self.report = reports.report_issues(start, end)
            elif kind == REPORT_TYPES[1]:
                self.report = reports.report_top10(self.carrier_var.get())
            else:
                self.report = reports.report_stored()
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка", f"Не удалось сформировать отчёт: {e}", parent=self)
            return
        self.show_report()

    def show_report(self):
        rep = self.report
        self.tree.delete(*self.tree.get_children())
        columns = [f"c{i}" for i in range(len(rep.headers))]
        self.tree["columns"] = columns
        for col, header in zip(columns, rep.headers):
            self.tree.heading(col, text=header)
            self.tree.column(col, width=120)
        for i, row in enumerate(rep.rows):
            tags = ("low",) if i in rep.red_rows else ()
            self.tree.insert("", "end", values=[reports.fmt(v) for v in row], tags=tags)
        self.total_var.set(rep.total)

    def save(self, kind):
        if self.report is None:
            messagebox.showwarning("Внимание", "Сначала сформируйте отчёт", parent=self)
            return
        try:
            if kind == "csv":
                path = reports.save_csv(self.report)
            else:
                path = reports.save_html(self.report)
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {e}", parent=self)
            return
        messagebox.showinfo("Готово", f"Отчёт сохранён:\n{path}", parent=self)


class UsersWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Сотрудники")
        self.geometry("560x320")
        self.repo = EmployeeRepository()

        columns = (("id", "№", 40), ("full_name", "ФИО", 240),
                   ("login", "Логин", 120), ("role", "Роль", 100))
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings")
        for col, text, width in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(self, text="Добавить сотрудника",
                   command=lambda: UserForm(self, self.load)).pack(pady=(0, 8))
        self.load()

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.repo.get_employees():
            self.tree.insert("", "end", values=(r["id"], r["full_name"], r["login"], r["role"]))


class UserForm(tk.Toplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.on_save = on_save
        self.title("Новый сотрудник")
        self.resizable(False, False)
        self.transient(parent)

        self.name_var = tk.StringVar()
        self.login_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.role_var = tk.StringVar(value="manager")

        frame = ttk.Frame(self, padding=12)
        frame.pack()
        rows = [
            ("ФИО:", ttk.Entry(frame, textvariable=self.name_var, width=30)),
            ("Логин:", ttk.Entry(frame, textvariable=self.login_var, width=30)),
            ("Пароль:", ttk.Entry(frame, textvariable=self.password_var, show="*", width=30)),
            ("Роль:", ttk.Combobox(frame, textvariable=self.role_var, state="readonly", width=27,
                                   values=("admin", "manager", "report"))),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=3)
            widget.grid(row=i, column=1, padx=(8, 0))
        ttk.Button(frame, text="Сохранить", command=self.save).grid(
            row=len(rows), column=0, columnspan=2, pady=(10, 0))

        self.wait_visibility()
        self.grab_set()

    def save(self):
        name = self.name_var.get().strip()
        login_name = self.login_var.get().strip()
        errors = validators.validate_employee(name, login_name,
                                              self.password_var.get(), self.role_var.get())
        if errors:
            messagebox.showerror("Ошибка ввода", "\n".join(errors), parent=self)
            return
        try:
            EmployeeRepository().add_employee(name, login_name, self.password_var.get(),
                                              self.role_var.get())
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Сотрудник с таким логином уже существует", parent=self)
            return
        logging.info("Создан сотрудник %s (роль %s)", login_name, self.role_var.get())
        self.on_save()
        self.destroy()