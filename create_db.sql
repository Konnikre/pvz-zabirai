-- =============================================
-- DDL-скрипт базы данных пункта выдачи заказов (ПВЗ)
-- СУБД: SQLite 3 (файл pvz.db создаётся при первом подключении)
-- =============================================

PRAGMA foreign_keys = ON;

-- ---------- Таблицы-справочники ----------

-- Службы доставки / маркетплейсы, чьи заказы приходят в пункт выдачи
CREATE TABLE carriers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    phone TEXT
);

-- Получатели заказов (клиенты пункта выдачи)
CREATE TABLE recipients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name         TEXT NOT NULL,
    phone             TEXT NOT NULL,
    email             TEXT,
    registration_date TEXT NOT NULL DEFAULT (date('now', 'localtime'))
);

-- Сотрудники: логин, роль и хеш пароля (формат "соль$хеш")
CREATE TABLE employees (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'report')),
    login         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

-- ---------- Основные таблицы ----------

-- Заказы. status: stored - на хранении, issued - выдан, returned - возвращён отправителю
CREATE TABLE orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_number TEXT NOT NULL UNIQUE CHECK (length(tracking_number) = 13),
    description     TEXT NOT NULL,
    amount          REAL NOT NULL DEFAULT 0 CHECK (amount >= 0),   -- к оплате при получении (0 - предоплачен)
    pickup_code     TEXT NOT NULL CHECK (length(pickup_code) = 4), -- код получения
    cell            TEXT NOT NULL,                                 -- ячейка хранения, например A-12
    status          TEXT NOT NULL DEFAULT 'stored'
                    CHECK (status IN ('stored', 'issued', 'returned')),
    received_date   TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    storage_until   TEXT NOT NULL,
    recipient_id    INTEGER NOT NULL,
    carrier_id      INTEGER NOT NULL,
    CONSTRAINT fk_orders_recipients
        FOREIGN KEY (recipient_id) REFERENCES recipients(id)
        ON UPDATE CASCADE,
    CONSTRAINT fk_orders_carriers
        FOREIGN KEY (carrier_id) REFERENCES carriers(id)
        ON UPDATE CASCADE
);

-- Выдачи заказов (один заказ выдаётся только один раз)
CREATE TABLE issues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    issue_date  TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    paid_amount REAL NOT NULL CHECK (paid_amount >= 0)
);

-- ---------- Служебные таблицы ----------

-- Журнал резервного копирования
CREATE TABLE backup_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name  TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Журнал аудита: I - вставка, U - изменение, D - удаление
CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation  TEXT NOT NULL CHECK (operation IN ('I', 'U', 'D')),
    record_id  INTEGER,
    changed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    old_values TEXT,
    new_values TEXT
);

-- ---------- Индексы ----------

CREATE INDEX idx_orders_status    ON orders(status, storage_until);
CREATE INDEX idx_orders_recipient ON orders(recipient_id);
CREATE INDEX idx_orders_carrier   ON orders(carrier_id);
CREATE INDEX idx_issues_date      ON issues(issue_date);

-- ---------- Представления ----------

-- Заказы вместе с получателем и службой доставки
CREATE VIEW v_orders_full AS
SELECT o.id, o.tracking_number, o.description, r.full_name AS recipient,
       r.phone, c.name AS carrier, o.cell, o.amount, o.pickup_code,
       o.status,
       CASE o.status WHEN 'stored'   THEN 'На хранении'
                     WHEN 'issued'   THEN 'Выдан'
                     ELSE 'Возвращён' END AS status_text,
       o.received_date, o.storage_until, o.recipient_id, o.carrier_id
FROM orders o
JOIN recipients r ON r.id = o.recipient_id
JOIN carriers c   ON c.id = o.carrier_id;

-- Агрегация выдач по месяцам
CREATE VIEW v_issues_report AS
SELECT strftime('%Y-%m', issue_date) AS month,
       COUNT(*)         AS issues_count,
       SUM(paid_amount) AS revenue
FROM issues
GROUP BY month;

-- Заказы на хранении и сколько дней осталось до конца срока
CREATE VIEW v_stored_orders AS
SELECT o.tracking_number, o.description, r.full_name AS recipient,
       c.name AS carrier, o.cell, o.amount, o.storage_until,
       CAST(julianday(o.storage_until) - julianday(date('now', 'localtime')) AS INTEGER) AS days_left
FROM orders o
JOIN recipients r ON r.id = o.recipient_id
JOIN carriers c   ON c.id = o.carrier_id
WHERE o.status = 'stored';

-- ---------- Триггеры целостности ----------

-- Выдать можно только заказ, который лежит на хранении
CREATE TRIGGER trg_issues_before_insert
BEFORE INSERT ON issues
WHEN (SELECT status FROM orders WHERE id = NEW.order_id) <> 'stored'
BEGIN
    SELECT RAISE(ABORT, 'Заказ нельзя выдать: он не находится на хранении');
END;

-- После выдачи заказ получает статус "выдан"
CREATE TRIGGER trg_issues_after_insert
AFTER INSERT ON issues
BEGIN
    UPDATE orders SET status = 'issued' WHERE id = NEW.order_id;
END;

-- Запрет удаления заказа, по которому оформлена выдача
CREATE TRIGGER trg_orders_before_delete
BEFORE DELETE ON orders
WHEN EXISTS (SELECT 1 FROM issues WHERE order_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'Нельзя удалить заказ: он уже выдан получателю');
END;

-- ---------- Триггеры аудита таблицы orders ----------

CREATE TRIGGER trg_orders_audit_insert
AFTER INSERT ON orders
BEGIN
    INSERT INTO audit_log (table_name, operation, record_id, new_values)
    VALUES ('orders', 'I', NEW.id,
            NEW.description || '; ' || NEW.amount || '; ' || NEW.status);
END;

CREATE TRIGGER trg_orders_audit_update
AFTER UPDATE ON orders
BEGIN
    INSERT INTO audit_log (table_name, operation, record_id, old_values, new_values)
    VALUES ('orders', 'U', NEW.id,
            OLD.description || '; ' || OLD.amount || '; ' || OLD.status,
            NEW.description || '; ' || NEW.amount || '; ' || NEW.status);
END;

CREATE TRIGGER trg_orders_audit_delete
AFTER DELETE ON orders
BEGIN
    INSERT INTO audit_log (table_name, operation, record_id, old_values)
    VALUES ('orders', 'D', OLD.id,
            OLD.description || '; ' || OLD.amount || '; ' || OLD.status);
END;
