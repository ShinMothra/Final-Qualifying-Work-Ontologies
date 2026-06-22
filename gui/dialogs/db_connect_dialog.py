from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt
from core.database.engine import init_db, get_db
from core.database.models import User

class DBConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Подключение к базе данных")
        self.setFixedSize(400, 300)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.host = QLineEdit("localhost")
        self.port = QLineEdit("5432")
        self.dbname = QLineEdit("ontologies_db")
        self.user = QLineEdit("ontology_user")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Хост:", self.host)
        form.addRow("Порт:", self.port)
        form.addRow("База:", self.dbname)
        form.addRow("Пользователь:", self.user)
        form.addRow("Пароль:", self.password)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.try_connect)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def try_connect(self):
        from core.database.engine import engine, DATABASE_URL
        import os
        os.environ["ONTOLOGY_DB_URL"] = (
            f"postgresql://{self.user.text()}:{self.password.text()}"
            f"@{self.host.text()}:{self.port.text()}/{self.dbname.text()}"
        )
        try:
            # Проверка подключения
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            init_db()  # создаём таблицы, если их нет
            QMessageBox.information(self, "Успех", "Подключено к базе данных!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось подключиться:\n{e}")
