import os
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QSpacerItem, QSizePolicy,
    QFileDialog, QMessageBox, QGridLayout
)
from PySide6.QtCore import Qt, QSize, QDateTime, Signal
from PySide6.QtGui import QIcon, QFont


RECENT_FILE = Path("recent_projects.json")


class ProjectCard(QFrame):
    clicked = Signal(str)

    def __init__(self, name: str, path: str, last_opened: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(290, 160)
        self.setCursor(Qt.PointingHandCursor)

        # Современный градиент + тень
        self.setStyleSheet("""
            ProjectCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4f46e5, stop:1 #7c3aed);
                border-radius: 16px;
                border: none;
            }
            ProjectCard:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6366f1, stop:1 #8b5cf6);
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Название проекта
        title = QLabel(name)
        title.setStyleSheet("color: white; font-size: 19px; font-weight: 600;")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Путь (сокращённый)
        path_label = QLabel(str(Path(path)).replace(str(Path.home()), "~"))
        path_label.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 12px;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        layout.addStretch()

        # Дата открытия
        date = QLabel(f"Открыт: {last_opened}")
        date.setStyleSheet("color: rgba(255,255,255,0.75); font-size: 11px;")
        layout.addWidget(date)

    def mousePressEvent(self, event):
        self.clicked.emit(self.path)


class StartPage(QWidget):
    project_selected = Signal(str)
    create_new = Signal()
    import_project = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("start_page")   # важно для QSS

        layout = QVBoxLayout(self)
        layout.setSpacing(32)
        layout.setContentsMargins(60, 60, 60, 60)

        # Заголовок
        title = QLabel("Конструктор онтологий")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 48px; font-weight: 700; color: #1e2937;")
        layout.addWidget(title)

        subtitle = QLabel("Визуальное создание и редактирование OWL-онтологий")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 19px; color: #64748b; margin-bottom: 20px;")
        layout.addWidget(subtitle)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)
        btn_layout.addStretch()

        btn_new = QPushButton("Новый проект")
        btn_new.setIcon(QIcon.fromTheme("document-new"))
        btn_new.setStyleSheet("""
            QPushButton {
                background: #10b981; color: white; border-radius: 12px;
                padding: 16px 32px; font-size: 16px; font-weight: 600;
            }
            QPushButton:hover { background: #34d399; }
        """)
        btn_new.clicked.connect(self.create_new.emit)
        btn_layout.addWidget(btn_new)

        btn_open = QPushButton("Открыть существующий")
        btn_open.setStyleSheet("""
            QPushButton {
                background: #3b82f6; color: white; border-radius: 12px;
                padding: 16px 32px; font-size: 16px; font-weight: 600;
            }
            QPushButton:hover { background: #60a5fa; }
        """)
        btn_open.clicked.connect(self.open_project)
        btn_layout.addWidget(btn_open)

        btn_import = QPushButton("Импорт OWL файла")
        btn_import.setStyleSheet("""
            QPushButton {
                background: #8b5cf6; color: white; border-radius: 12px;
                padding: 16px 32px; font-size: 16px; font-weight: 600;
            }
            QPushButton:hover { background: #a78bfa; }
        """)
        btn_import.clicked.connect(self.import_project.emit)
        btn_layout.addWidget(btn_import)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addSpacing(20)

        # Недавние проекты
        recent_title = QLabel("Недавние проекты")
        recent_title.setStyleSheet("font-size: 24px; font-weight: 600; color: #1e2937;")
        layout.addWidget(recent_title)

        self.grid = QGridLayout()
        self.grid.setSpacing(24)
        layout.addLayout(self.grid)

        self.load_recent_projects()

    def load_recent_projects(self):
        # Очищаем предыдущие карточки
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)

        if not RECENT_FILE.exists():
            empty = QLabel("Пока нет недавних проектов")
            empty.setStyleSheet("color: #94a3b8; font-size: 17px;")
            empty.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(empty, 0, 0)
            return

        try:
            with open(RECENT_FILE, "r", encoding="utf-8") as f:
                projects = json.load(f)
        except:
            projects = []

        if not projects:
            empty = QLabel("Пока нет недавних проектов")
            empty.setStyleSheet("color: #94a3b8; font-size: 17px;")
            empty.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(empty, 0, 0)
            return

        row = col = 0
        for proj in projects[-6:]:   # последние 6 (2 ряда по 3)
            card = ProjectCard(
                name=proj.get("name", "Без названия"),
                path=proj["path"],
                last_opened=QDateTime.fromSecsSinceEpoch(proj.get("last_opened", 0)).toString("dd.MM.yyyy HH:mm")
            )
            card.clicked.connect(self.project_selected.emit)
            self.grid.addWidget(card, row, col)

            col += 1
            if col > 2:
                col = 0
                row += 1

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть файл онтологии", "",
            "Все поддерживаемые форматы (*.owl *.ttl *.rdf *.json);;"
            "OWL Files (*.owl *.ttl *.rdf);;"
            "JSON Files (*.json);;"
            "All Files (*)"
        )
        if path:
            self.project_selected.emit(path)

    def add_recent_project(self, name: str, path: str):
        """Вызывается из MainWindow"""
        if not RECENT_FILE.exists():
            projects = []
        else:
            try:
                with open(RECENT_FILE, "r", encoding="utf-8") as f:
                    projects = json.load(f)
            except:
                projects = []

        projects = [p for p in projects if p.get("path") != path]
        projects.append({
            "name": name,
            "path": path,
            "last_opened": QDateTime.currentDateTime().toSecsSinceEpoch()
        })
        projects = projects[-15:]

        try:
            with open(RECENT_FILE, "w", encoding="utf-8") as f:
                json.dump(projects, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения recent_projects: {e}")
