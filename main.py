"""Точка входа: окно входа, затем главное окно по роли пользователя."""
import os

from db import get_db_path, set_read_only
from gui import LoginWindow, MainWindow


def main():
    """Запускает приложение (при первом запуске создаёт БД)."""
    if not os.path.exists(get_db_path()):
        import seed
        seed.seed()
        print("База данных создана. Пользователи: admin/admin123, "
              "manager/manager123, report/report123")

    login_window = LoginWindow()
    login_window.mainloop()
    user = login_window.user
    if user is None:
        return
    if user["role"] == "report":
        set_read_only(True)
    MainWindow(user).mainloop()


if __name__ == "__main__":
    main()
