from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QMenu, QLineEdit,
    QHBoxLayout, QCheckBox, QLabel, QComboBox, QFrame, QCompleter
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QSize, Qt, QTimer, QStringListModel
from gui.sidebar.tree_widget import OntologyTreeWidget


class ToolboxWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 1. Toolbar ────────────────────────────────────────────────────────
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet("QToolBar { border-bottom: 1px solid #333; padding: 5px; }")
        layout.addWidget(self.toolbar)

        create_menu = QMenu(self)
        create_menu.addAction("Новый класс",     self.main_window.open_class_dialog)
        create_menu.addAction("Новый индивид",   self.main_window.open_individual_dialog)
        create_menu.addAction("Новое отношение", self.main_window.open_object_property_dialog)
        create_menu.addAction("Новое свойство",  self.main_window.open_data_property_dialog)

        add_btn = QAction(QIcon("resources/icons/add.png"), "Создать", self)
        add_btn.setMenu(create_menu)
        self.toolbar.addAction(add_btn)
        self.toolbar.addSeparator()
        self.toolbar.addAction(QIcon("resources/icons/validate.png"), "Валидация", self.main_window.run_validation)
        self.toolbar.addAction(QIcon("resources/icons/export.png"),   "Экспорт",   self.main_window.run_export)

        # ── 2. Поиск ──────────────────────────────────────────────────────────
        search_frame = QFrame()
        search_frame.setStyleSheet("QFrame { border-bottom: 1px solid #333; }")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(6, 4, 6, 4)
        search_layout.setSpacing(4)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по имени или метке...")
        self.search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_edit)

        layout.addWidget(search_frame)

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_search)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())

        # ── 2.1. Автодополнение и переход к узлу ───────────────────────────────
        # display-строка ("Имя (Метка)") → (type_node, name)
        self._search_index: dict[str, tuple[str, str]] = {}

        self._completer_model = QStringListModel()
        self.completer = QCompleter(self._completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.search_edit.setCompleter(self.completer)

        self.completer.activated[str].connect(self._on_completer_activated)
        self.search_edit.returnPressed.connect(self._on_search_return)

        # ── 3. Фильтры ────────────────────────────────────────────────────────
        filter_frame = QFrame()
        filter_frame.setStyleSheet("QFrame { border-bottom: 1px solid #333; }")
        filter_outer = QVBoxLayout(filter_frame)
        filter_outer.setContentsMargins(6, 4, 6, 6)
        filter_outer.setSpacing(4)

        filter_outer.addWidget(QLabel("Показывать:"))

        checks_layout = QHBoxLayout()
        checks_layout.setSpacing(8)

        self.cb_classes     = QCheckBox("Классы")
        self.cb_individuals = QCheckBox("Индивиды")
        self.cb_properties  = QCheckBox("Свойства")

        self.cb_classes.setChecked(True)
        self.cb_individuals.setChecked(True)
        self.cb_properties.setChecked(True)

        checks_layout.addWidget(self.cb_classes)
        checks_layout.addWidget(self.cb_individuals)
        checks_layout.addWidget(self.cb_properties)
        checks_layout.addStretch()
        filter_outer.addLayout(checks_layout)

        level_layout = QHBoxLayout()
        level_layout.setSpacing(6)
        level_layout.addWidget(QLabel("Уровень:"))

        self.level_combo = QComboBox()
        self.level_combo.addItem("Все уровни", -1)
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        filter_outer.addLayout(level_layout)

        layout.addWidget(filter_frame)

        self.cb_classes.stateChanged.connect(self._apply_filters)
        self.cb_individuals.stateChanged.connect(self._apply_filters)
        self.cb_properties.stateChanged.connect(self._apply_filters)
        self.level_combo.currentIndexChanged.connect(self._apply_filters)

        # ── 4. Дерево ─────────────────────────────────────────────────────────
        self.tree = OntologyTreeWidget(main_window)
        layout.addWidget(self.tree, 1)

    # ── Публичные методы ──────────────────────────────────────────────────────

    def refresh(self):
        if hasattr(self, 'tree'):
            self.tree.refresh()
        self._update_level_combo()
        self._apply_filters()
        self._apply_search()
        self._rebuild_search_index()

    def get_filter_state(self) -> dict:
        return {
            "show_classes":     self.cb_classes.isChecked(),
            "show_individuals": self.cb_individuals.isChecked(),
            "show_properties":  self.cb_properties.isChecked(),
            "max_level":        self.level_combo.currentData(),
        }

    # ── Динамический комбобокс уровней ────────────────────────────────────────

    def _update_level_combo(self):
        """Пересчитывает максимальную глубину иерархии и обновляет комбобокс."""
        manager = getattr(self.main_window, 'manager', None)

        max_depth = self._compute_max_depth(manager)

        # Запоминаем текущий выбор
        current_data = self.level_combo.currentData()

        # Блокируем сигнал чтобы не триггерить apply_filters во время перестройки
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        self.level_combo.addItem("Все уровни", -1)

        for i in range(1, max_depth + 1):
            self.level_combo.addItem(f"До {i}-го уровня", i)

        # Восстанавливаем выбор если он ещё валиден
        idx = self.level_combo.findData(current_data)
        if idx >= 0:
            self.level_combo.setCurrentIndex(idx)
        else:
            self.level_combo.setCurrentIndex(0)  # "Все уровни"

        self.level_combo.blockSignals(False)

    def _compute_max_depth(self, manager) -> int:
        """Вычисляет максимальную глубину иерархии классов."""
        if not manager or not manager.classes:
            return 1

        def depth_of(elem, visited=None) -> int:
            if visited is None:
                visited = set()
            if elem.name in visited:
                return 1  # защита от циклов
            visited.add(elem.name)
            if not elem.children:
                return 1
            return 1 + max(depth_of(child, visited) for child in elem.children)

        max_d = 1
        for elem in manager.classes.values():
            if not elem.parent:  # только корневые классы
                max_d = max(max_d, depth_of(elem))

        return max_d

    # ── Внутренние методы ─────────────────────────────────────────────────────

    def _apply_filters(self):
        state = self.get_filter_state()

        scene = getattr(self.main_window, 'scene', None)
        if scene:
            scene.apply_filters(state)

        self.tree.apply_filters(state)

    def _apply_search(self):
        query = self.search_edit.text().strip()

        scene = getattr(self.main_window, 'scene', None)
        if scene:
            scene.apply_search(query)

        self.tree.apply_search(query)

    # ── Автодополнение и переход к узлу ─────────────────────────────────────────

    def _rebuild_search_index(self):
        """
        Перестраивает индекс автодополнения по текущей модели.
        display-строка вида "Имя (Метка)" → (type_node, name).
        """
        manager = getattr(self.main_window, 'manager', None)
        self._search_index.clear()
        entries: list[str] = []

        if manager:
            for name, elem in manager.classes.items():
                label = getattr(elem, 'label', None)
                display = f"{name} ({label})" if label and label != name else name
                self._search_index[display] = ("class", name)
                entries.append(display)

            for name, elem in manager.individuals.items():
                label = getattr(elem, 'label', None)
                display = f"{name} ({label})" if label and label != name else name
                self._search_index[display] = ("individual", name)
                entries.append(display)

        entries.sort(key=str.lower)
        self._completer_model.setStringList(entries)

    def _on_completer_activated(self, display: str):
        """Выбор элемента из выпадающего списка автодополнения."""
        entry = self._search_index.get(display)
        if not entry:
            return
        type_node, name = entry
        self._zoom_to(type_node, name)

    def _on_search_return(self):
        """
        Нажатие Enter в поле поиска: ищем точное совпадение по имени
        или метке (без учёта регистра) и переходим к узлу.
        """
        query = self.search_edit.text().strip()
        if not query:
            return

        manager = getattr(self.main_window, 'manager', None)
        if not manager:
            return

        q = query.lower()

        for name, elem in manager.classes.items():
            label = getattr(elem, 'label', None)
            if name.lower() == q or (label and label.lower() == q):
                self._zoom_to("class", name)
                return

        for name, elem in manager.individuals.items():
            label = getattr(elem, 'label', None)
            if name.lower() == q or (label and label.lower() == q):
                self._zoom_to("individual", name)
                return

    def _zoom_to(self, type_node: str, name: str):
        """Зум к узлу на canvas + синхронизация выбора в дереве."""
        scene = getattr(self.main_window, 'scene', None)
        if scene and hasattr(scene, 'zoom_to_node'):
            scene.zoom_to_node(type_node, name)

        if hasattr(self.main_window, '_on_node_clicked'):
            self.main_window._on_node_clicked(type_node, name)
