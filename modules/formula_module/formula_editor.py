# modules/formula_module/formula_editor.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QSplitter, QWidget, QFileDialog, QListWidget, QListWidgetItem,
    QGroupBox, QScrollArea, QFrame, QCheckBox, QTabWidget,
    QComboBox, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon
from .formula_core import FormulaEvaluator
from .formula_preview import FormulaPreviewWidget
import json


class FormulaEditorDialog(QDialog):
    recent_formulas = []

    def __init__(self, parent=None, target=None):
        super().__init__(parent)
        self.target = target
        self.setWindowTitle("Редактор формул")
        self.resize(1100, 700)

        self.evaluator = FormulaEvaluator()
        self._symbol_context: dict = {}

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # История формул
        history_layout = QHBoxLayout()
        history_layout.addWidget(QLabel("История:"))

        self.history_combo = QComboBox()
        self.history_combo.setPlaceholderText("Выберите формулу из истории...")
        self.history_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.history_combo.activated.connect(self._load_from_history)
        history_layout.addWidget(self.history_combo)

        clear_history_btn = QPushButton("Очистить историю")
        clear_history_btn.setFixedWidth(140)
        clear_history_btn.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_history_btn)

        main_layout.addLayout(history_layout)

        # Вкладки
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_formula_tab(),   "Формула")
        self.tabs.addTab(self._build_calculate_tab(), "Вычисление")
        self.tabs.addTab(self._build_context_tab(),   "Контекст символов")

        # Кнопки
        save_layout = QHBoxLayout()

        save_to_elem_btn = QPushButton("Сохранить в элемент")
        save_to_elem_btn.clicked.connect(self.save_to_target)
        save_layout.addWidget(save_to_elem_btn)

        save_file_btn = QPushButton("Сохранить в файл")
        save_file_btn.clicked.connect(self.save_formula)
        save_layout.addWidget(save_file_btn)

        load_file_btn = QPushButton("Загрузить из файла")
        load_file_btn.clicked.connect(self.load_formula)
        save_layout.addWidget(load_file_btn)

        main_layout.addLayout(save_layout)

        self._update_history_combo()

        # Загружаем данные из target — silent=True чтобы не показывать
        # QMessageBox пока диалог ещё не отображён на экране
        if target:
            if hasattr(target, 'formula') and target.formula:
                self.input_edit.setPlainText(target.formula)
            if hasattr(target, 'symbol_context') and target.symbol_context:
                self._symbol_context = dict(target.symbol_context)
            self.parse_formula(silent=True)

    # ── Вкладки ──────────────────────────────────────────────────────────────

    def _build_formula_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)

        left_layout.addWidget(QLabel("Формула:"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(
            "Введите формулу, например:\n"
            "E = m c^2\n"
            "F = m a\n"
            "\\sum_{i=1}^{m} p_i = 1"
        )
        self.input_edit.setMaximumHeight(100)
        left_layout.addWidget(self.input_edit)

        btn_layout = QHBoxLayout()
        parse_btn = QPushButton("Разобрать")
        parse_btn.clicked.connect(self.parse_formula)
        btn_layout.addWidget(parse_btn)
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self.clear)
        btn_layout.addWidget(clear_btn)
        left_layout.addLayout(btn_layout)

        left_layout.addWidget(QLabel("Структура формулы:"))
        self.struct_tree = QTreeWidget()
        self.struct_tree.setHeaderLabels(["Элемент", "Тип"])
        left_layout.addWidget(self.struct_tree, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Предпросмотр (LaTeX):"))
        self.preview = FormulaPreviewWidget()
        right_layout.addWidget(self.preview, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([480, 480])
        layout.addWidget(splitter)

        return widget

    def _build_calculate_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        info = QLabel("Введите значения переменных. Константы подставляются автоматически.")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._var_container = QWidget()
        self.var_layout = QVBoxLayout(self._var_container)
        self.var_layout.setSpacing(6)
        self.var_layout.addStretch()

        scroll.setWidget(self._var_container)
        layout.addWidget(scroll, 1)

        calc_btn = QPushButton("Вычислить правую часть")
        calc_btn.clicked.connect(self.calculate)
        layout.addWidget(calc_btn)

        self.result_label = QLabel("Результат: —")
        self.result_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px;")
        layout.addWidget(self.result_label)

        return widget

    def _build_context_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)

        info = QLabel(
            "Задайте смысл каждого символа формулы.\n"
            "Регистр учитывается: E и e — разные символы.\n"
            "Константы подставляются автоматически при вычислении."
        )
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._ctx_container = QWidget()
        self._ctx_layout = QVBoxLayout(self._ctx_container)
        self._ctx_layout.setSpacing(8)
        self._ctx_layout.setContentsMargins(4, 4, 4, 4)
        self._ctx_layout.addStretch()

        lbl = QLabel("Символов нет — сначала разберите формулу на вкладке «Формула».")
        lbl.setStyleSheet("color: gray;")
        lbl.setObjectName("_placeholder")
        self._ctx_layout.insertWidget(0, lbl)

        scroll.setWidget(self._ctx_container)
        layout.addWidget(scroll, 1)

        return widget

    # ── История ───────────────────────────────────────────────────────────────

    def _update_history_combo(self):
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        for formula in reversed(self.recent_formulas[-20:]):
            display = formula[:80] + "..." if len(formula) > 80 else formula
            self.history_combo.addItem(display, userData=formula)
        self.history_combo.blockSignals(False)

    def _load_from_history(self, index: int):
        formula = self.history_combo.itemData(index)
        if formula:
            self.input_edit.setPlainText(formula)
            self.tabs.setCurrentIndex(0)
            self.parse_formula()

    def _clear_history(self):
        self.recent_formulas.clear()
        self._update_history_combo()

    # ── Контекст символов ─────────────────────────────────────────────────────

    def _rebuild_context_panel(self, symbols: list):
        self._collect_context_from_ui_fields()

        while self._ctx_layout.count() > 1:
            item = self._ctx_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not symbols:
            lbl = QLabel("Символов нет — сначала разберите формулу на вкладке «Формула».")
            lbl.setStyleSheet("color: gray;")
            lbl.setObjectName("_placeholder")
            self._ctx_layout.insertWidget(0, lbl)
            return

        for sym in symbols:
            ctx = self._symbol_context.get(sym, {})
            is_const = ctx.get("is_constant", False)

            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            frame.setObjectName(f"frame_{sym}")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(10, 8, 10, 8)
            frame_layout.setSpacing(6)

            header = QHBoxLayout()
            sym_label = QLabel(f"<b style='font-size:16px'>{sym}</b>")
            header.addWidget(sym_label)
            cb_const = QCheckBox("Константа")
            cb_const.setObjectName(f"const_{sym}")
            cb_const.setChecked(is_const)
            header.addWidget(cb_const)
            header.addStretch()
            frame_layout.addLayout(header)

            desc_edit = QLineEdit(ctx.get("description", ""))
            desc_edit.setPlaceholderText("Описание (например: масса тела, скорость света...)")
            desc_edit.setObjectName(f"desc_{sym}")
            frame_layout.addWidget(desc_edit)

            row2 = QHBoxLayout()
            domain_edit = QLineEdit(ctx.get("domain", ""))
            domain_edit.setPlaceholderText("Область знаний (физика, геометрия...)")
            domain_edit.setObjectName(f"domain_{sym}")
            row2.addWidget(domain_edit)

            unit_edit = QLineEdit(ctx.get("unit", ""))
            unit_edit.setPlaceholderText("Единица [кг, м/с...]")
            unit_edit.setFixedWidth(110)
            unit_edit.setObjectName(f"unit_{sym}")
            row2.addWidget(unit_edit)
            frame_layout.addLayout(row2)

            val_row = QHBoxLayout()
            val_label = QLabel("Значение константы:")
            val_label.setObjectName(f"vallabel_{sym}")
            val_edit = QLineEdit(str(ctx.get("value", "")) if ctx.get("value") is not None else "")
            val_edit.setPlaceholderText("Числовое значение")
            val_edit.setObjectName(f"val_{sym}")
            val_row.addWidget(val_label)
            val_row.addWidget(val_edit)
            frame_layout.addLayout(val_row)

            val_label.setVisible(is_const)
            val_edit.setVisible(is_const)

            cb_const.stateChanged.connect(
                lambda state, vl=val_label, ve=val_edit:
                    (vl.setVisible(bool(state)), ve.setVisible(bool(state)))
            )

            self._ctx_layout.insertWidget(self._ctx_layout.count() - 1, frame)

    def _collect_context_from_ui_fields(self):
        if self.evaluator.expr is None:
            return
        for sym in self.evaluator.get_symbols():
            desc_edit   = self._ctx_container.findChild(QLineEdit, f"desc_{sym}")
            domain_edit = self._ctx_container.findChild(QLineEdit, f"domain_{sym}")
            unit_edit   = self._ctx_container.findChild(QLineEdit, f"unit_{sym}")
            cb_const    = self._ctx_container.findChild(QCheckBox, f"const_{sym}")
            val_edit    = self._ctx_container.findChild(QLineEdit, f"val_{sym}")

            if any(w is not None for w in [desc_edit, domain_edit, unit_edit, cb_const]):
                entry = self._symbol_context.get(sym, {})
                if desc_edit   is not None: entry["description"]  = desc_edit.text().strip()
                if domain_edit is not None: entry["domain"]        = domain_edit.text().strip()
                if unit_edit   is not None: entry["unit"]          = unit_edit.text().strip()
                if cb_const    is not None: entry["is_constant"]   = cb_const.isChecked()
                if val_edit    is not None:
                    raw = val_edit.text().strip().replace(" ", "").replace("\u00a0", "")
                    try:
                        entry["value"] = float(raw) if raw else None
                    except ValueError:
                        entry["value"] = raw or None
                self._symbol_context[sym] = entry

    def _collect_context_from_ui(self):
        self._collect_context_from_ui_fields()

    def _get_constants_dict(self) -> dict:
        result = {}
        for sym, ctx in self._symbol_context.items():
            if ctx.get("is_constant") and ctx.get("value") is not None:
                try:
                    result[sym] = float(ctx["value"])
                except (ValueError, TypeError):
                    pass
        return result

    # ── Разбор формулы ────────────────────────────────────────────────────────

    def parse_formula(self, silent: bool = False):
        """
        Разбирает формулу из поля ввода.
        silent=True — при ошибке не показывать QMessageBox.
        Используется при автоматическом вызове из __init__, когда диалог
        ещё не показан на экране (во избежание неожиданных всплывашек).
        """
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        success, msg = self.evaluator.parse(text)

        if success:
            self.preview.show_latex(self.evaluator.get_latex())
            self._show_structure()
            self._rebuild_context_panel(self.evaluator.get_symbols())
            self._collect_context_from_ui_fields()
            self._update_variables()
            self._rebuild_context_panel(self.evaluator.get_symbols())

            if text not in self.recent_formulas:
                self.recent_formulas.append(text)
                self._update_history_combo()
        else:
            # Показываем формулу как plain text даже если SymPy не смог разобрать
            self.preview.show_latex(text)
            if not silent:
                QMessageBox.warning(self, "Ошибка разбора", msg)
            else:
                print(f"[FormulaEditor] Ошибка парсинга (silent): {msg}")

    def _show_structure(self):
        self.struct_tree.clear()
        if self.evaluator.expr is None:
            return

        def add_node(parent, expr):
            item = QTreeWidgetItem(parent)
            item.setText(0, str(expr))
            item.setText(1, getattr(expr, 'func', type(expr)).__name__)
            for arg in expr.args:
                add_node(item, arg)

        root = QTreeWidgetItem(self.struct_tree)
        root.setText(0, str(self.evaluator.expr))
        root.setText(1, "Root")
        for arg in self.evaluator.expr.args:
            add_node(root, arg)
        self.struct_tree.expandAll()

    def _update_variables(self):
        while self.var_layout.count() > 1:
            item = self.var_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rhs_symbols = self.evaluator.get_rhs_symbols()

        if not rhs_symbols:
            lbl = QLabel("Символов нет — сначала разберите формулу.")
            lbl.setStyleSheet("color: gray;")
            self.var_layout.insertWidget(0, lbl)
            return

        for sym in rhs_symbols:
            ctx = self._symbol_context.get(sym, {})
            is_const = ctx.get("is_constant", False)

            row = QHBoxLayout()

            lbl = QLabel(f"<b>{sym}</b> =")
            lbl.setFixedWidth(50)
            row.addWidget(lbl)

            edit = QLineEdit()
            edit.setObjectName(sym)

            if is_const:
                raw = str(ctx.get("value", "")).strip().replace(" ", "").replace("\u00a0", "")
                edit.setText(raw)
                edit.setReadOnly(True)
                edit.setStyleSheet("color: gray; background: transparent;")
            else:
                edit.setText("0")

            row.addWidget(edit)

            desc = ctx.get("description", "")
            unit = ctx.get("unit", "")
            hint_parts = []
            if desc: hint_parts.append(desc)
            if unit: hint_parts.append(f"[{unit}]")
            if is_const: hint_parts.append("(константа)")
            if hint_parts:
                hint = QLabel("  " + "  ".join(hint_parts))
                hint.setStyleSheet("color: gray;")
                row.addWidget(hint)

            row.addStretch()
            container = QWidget()
            container.setLayout(row)
            self.var_layout.insertWidget(self.var_layout.count() - 1, container)

    # ── Вычисление ────────────────────────────────────────────────────────────

    def calculate(self):
        self._collect_context_from_ui_fields()

        values = {}
        for i in range(self.var_layout.count() - 1):
            item = self.var_layout.itemAt(i)
            if not item or not item.widget():
                continue
            edit = item.widget().findChild(QLineEdit)
            if edit and edit.objectName():
                sym = edit.objectName()
                try:
                    values[sym] = float(edit.text())
                except ValueError:
                    values[sym] = edit.text()

        constants = {}
        for sym, ctx in self._symbol_context.items():
            if ctx.get("is_constant") and ctx.get("value") is not None:
                try:
                    raw = str(ctx["value"]).strip().replace(" ", "").replace("\u00a0", "")
                    constants[sym] = float(raw)
                except (ValueError, TypeError):
                    pass

        result, err = self.evaluator.substitute(values, constants=constants)

        if err:
            self.result_label.setText(f"Ошибка: {err}")
        else:
            self.result_label.setText(f"Результат: {result}")

    # ── Очистка ───────────────────────────────────────────────────────────────

    def clear(self):
        self.input_edit.clear()
        self.preview.show_latex("")
        self.struct_tree.clear()
        self.result_label.setText("Результат: —")
        self._symbol_context.clear()
        self._rebuild_context_panel([])
        while self.var_layout.count() > 1:
            item = self.var_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Сохранение / загрузка ─────────────────────────────────────────────────

    def save_to_target(self):
        if self.evaluator.expr is None:
            QMessageBox.warning(self, "Ошибка", "Сначала разберите формулу")
            return
        if self.target is None:
            QMessageBox.warning(self, "Ошибка", "Редактор открыт не из элемента онтологии")
            return

        formula_str = self.input_edit.toPlainText().strip()
        if not formula_str:
            QMessageBox.warning(self, "Ошибка", "Формула пустая")
            return

        self._collect_context_from_ui()

        self.target.formula = formula_str
        self.target.symbol_context = dict(self._symbol_context)

        if hasattr(self.parent(), 'manager'):
            self.parent().manager.set_formula(self.target.name, formula_str)

        QMessageBox.information(self, "Успех", f"Формула и контекст сохранены в «{self.target.name}»")
        self.accept()

    def save_formula(self):
        if self.evaluator.expr is None:
            QMessageBox.warning(self, "Ошибка", "Нет формулы для сохранения")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Сохранить формулу", "", "JSON (*.json)")
        if not path:
            return

        self._collect_context_from_ui()
        data = self.evaluator.to_dict()
        data["symbol_context"] = self._symbol_context

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Успех", "Формула сохранена в файл")

    def load_formula(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить формулу", "", "JSON (*.json)")
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.evaluator = FormulaEvaluator.from_dict(data)
            self._symbol_context = data.get("symbol_context", {})
            self.input_edit.setPlainText(data.get("string", ""))
            self.tabs.setCurrentIndex(0)
            self.parse_formula()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить формулу:\n{str(e)}")
