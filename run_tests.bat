@echo off
chcp 65001 >nul
echo === Автотесты ПВЗ "Забирай" ===
python -m coverage run -m unittest discover -s tests -t . -v
python -m coverage report -m
