"""Метрики качества кода по слоям проекта (этап 4): python inspect_metrics.py [папка]."""
import ast
import os
import sys

MAX_LINE = 100        # допустимая длина строки (как в setup.cfg)
MAX_FUNC_LINES = 40   # допустимая длина функции
MAX_COMPLEXITY = 10   # допустимая цикломатическая сложность

LAYERS = {
    "DataAccess": ["db.py", "repository.py", "queries.py", "models.py",
                   "seed.py", "backup.py", "restore.py"],
    "BusinessLogic": ["validators.py", "auth.py", "reports.py"],
    "Presentation": ["gui.py", "main.py"],
}


def complexity(func):
    """Цикломатическая сложность: 1 + число ветвлений и логических операторов."""
    result = 1
    for node in ast.walk(func):
        if isinstance(node, ast.BoolOp):
            result += len(node.values) - 1
        elif isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                               ast.IfExp, ast.comprehension)):
            result += 1
    return result


def has_no_docstring(node):
    """Публичный объект (имя без «_») без docstring."""
    return not node.name.startswith("_") and not ast.get_docstring(node)


def inspect_layer(folder, files):
    """Собирает показатели по файлам одного слоя."""
    stats = {"lines": 0, "funcs": 0, "long_lines": 0, "no_docstring": 0,
             "max_cc": (0, ""), "max_len": (0, ""), "too_long": [], "too_complex": []}
    for name in files:
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        lines = source.split("\n")
        stats["lines"] += len(lines)
        stats["long_lines"] += sum(len(line) > MAX_LINE for line in lines)
        if not ast.get_docstring(tree):
            stats["no_docstring"] += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and has_no_docstring(node):
                stats["no_docstring"] += 1
            if not isinstance(node, ast.FunctionDef):
                continue
            stats["funcs"] += 1
            if has_no_docstring(node):
                stats["no_docstring"] += 1
            length = node.end_lineno - node.lineno + 1
            cc = complexity(node)
            label = f"{name}:{node.name}"
            stats["max_len"] = max(stats["max_len"], (length, label))
            stats["max_cc"] = max(stats["max_cc"], (cc, label))
            if length > MAX_FUNC_LINES:
                stats["too_long"].append(f"{label}={length}")
            if cc > MAX_COMPLEXITY:
                stats["too_complex"].append(f"{label}={cc}")
    return stats


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    for layer, files in LAYERS.items():
        s = inspect_layer(folder, files)
        print(f"{layer}: строк {s['lines']}, функций {s['funcs']}, "
              f"строк > {MAX_LINE}: {s['long_lines']}, без docstring: {s['no_docstring']}")
        print(f"  макс. сложность {s['max_cc'][0]} ({s['max_cc'][1]}), "
              f"макс. длина {s['max_len'][0]} ({s['max_len'][1]})")
        print(f"  длиннее {MAX_FUNC_LINES} строк: {s['too_long'] or 'нет'}; "
              f"сложность > {MAX_COMPLEXITY}: {s['too_complex'] or 'нет'}")


if __name__ == "__main__":
    main()
