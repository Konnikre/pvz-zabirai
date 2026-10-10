"""Автотесты приложения «ПВЗ «Забирай».

Запуск из корня проекта:
    python -m unittest discover -s tests -t . -v
С измерением покрытия (нужен пакет coverage):
    python -m coverage run --source=. --omit="tests/*,gui.py,main.py" -m unittest discover -s tests -t .
    python -m coverage report -m
"""
import logging
import os
import tempfile

# Журналы тестов не должны попадать в рабочие app.log и backup.log проекта.
# Настройка выполняется до импорта модулей проекта.
logging.basicConfig(filename=os.path.join(tempfile.gettempdir(), "pvz_tests.log"),
                    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    encoding="utf-8")
logging.getLogger("backup").addHandler(logging.NullHandler())
