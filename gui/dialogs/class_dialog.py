from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QLabel, QMessageBox, QHBoxLayout, QWidget,
    QScrollArea, QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.model.elements import ClassElement, EdgeType, PropertyOverride
from modules.formula_module.formula_editor import FormulaEditorDialog
import logging

logger = logging.getLogger(__name__)


class CreateClassDialog(QDialog):
    def __init__(self, manager, parent=None, class_name: str = None):
        super().__init__(parent)
        self.manager = manager
        self.class_name = class_name
        self.elem = None

        self._pending_data_properties: list = []
        self._pending_object_properties: list = []
        self._overrides: dict = {}
        self._prop_values: dict = {}   # значения атрибутов: {prop_name: str}

        self.setWindowTitle("Редактировать класс" if class_name else "Создать новый класс")
        self.resize(620, 860)

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # ── Основные данные ───────────────────────────────────────────────────
        base_group = QGroupBox("Общая информация")
        base_form = QFormLayout(base_group)

        self.name_edit = QLineEdit()
        self.uri_edit = QLineEdit()
        self.label_edit = QLineEdit()
        self.parent_combo = QComboBox()
        self.edge_combo = QComboBox()
        self.edge_combo.addItems([e.value for e in EdgeType])

        base_form.addRow("Имя класса*:", self.name_edit)
        base_form.addRow("URI:", self.uri_edit)
        base_form.addRow("Метка:", self.label_edit)
        base_form.addRow("Родитель:", self.parent_combo)
        base_form.addRow("Тип связи:", self.edge_combo)
        layout.addWidget(base_group)

        # ── Расширение ────────────────────────────────────────────────────────
        ext_group = QGroupBox("Расширение")
        ext_form = QFormLayout(ext_group)

        self.extension_combo = QComboBox()
        self.extension_combo.setEditable(True)
        self.extension_combo.setInsertPolicy(QComboBox.InsertAtTop)
        self.extension_combo.addItem("")
        self.extension_combo.lineEdit().setPlaceholderText("Выберите или введите новое...")

        ext_form.addRow("Расширение:", self.extension_combo)
        ext_group.setToolTip(
            "Расширение — это именованная группа подклассов одного родителя.\n"
            "Оставьте пустым, если класс не входит в расширение."
        )
        layout.addWidget(ext_group)

        # ── Свойства ─────────────────────────────────────────────────────────
        self.prop_group = QGroupBox("Свойства (характеристики и связи)")
        self.prop_outer = QVBoxLayout(self.prop_group)
        self.prop_outer.setSpacing(8)

        add_btns = QHBoxLayout()
        add_data_btn = QPushButton("+ Атрибут")
        add_obj_btn  = QPushButton("+ Отношение")
        add_data_btn.clicked.connect(self.quick_add_data_property)
        add_obj_btn.clicked.connect(self.quick_add_object_property)
        add_btns.addWidget(add_data_btn)
        add_btns.addWidget(add_obj_btn)
        self.prop_outer.addLayout(add_btns)

        self.prop_outer.addWidget(QLabel("<b>Атрибуты данных:</b>"))

        dp_scroll = QScrollArea()
        dp_scroll.setWidgetResizable(True)
        dp_scroll.setFrameShape(QScrollArea.NoFrame)
        dp_scroll.setMaximumHeight(200)
        self._dp_panel = QWidget()
        self._dp_layout = QVBoxLayout(self._dp_panel)
        self._dp_layout.setSpacing(4)
        self._dp_layout.setContentsMargins(0, 0, 0, 0)
        dp_scroll.setWidget(self._dp_panel)
        self.prop_outer.addWidget(dp_scroll)

        self.prop_outer.addWidget(QLabel("<b>Отношения:</b>"))
        self.obj_props_list = QListWidget()
        self.obj_props_list.setMaximumHeight(100)
        self.obj_props_list.itemDoubleClicked.connect(self._edit_object_property)
        self.prop_outer.addWidget(self.obj_props_list)

        edit_op_btn = QPushButton("✎ Изменить отношение")
        edit_op_btn.clicked.connect(self._edit_selected_object_property)
        self.prop_outer.addWidget(edit_op_btn)

        layout.addWidget(self.prop_group)

        # ── Дополнительно ─────────────────────────────────────────────────────
        extra_group = QGroupBox("Дополнительно")
        extra_layout = QVBoxLayout(extra_group)

        extra_layout.addWidget(QLabel("Комментарий:"))
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(60)
        extra_layout.addWidget(self.comment_edit)

        extra_layout.addWidget(QLabel("Формула:"))
        self.formula_edit = QLineEdit()
        extra_layout.addWidget(self.formula_edit)

        btn_formula = QPushButton("Редактор формул")
        btn_formula.clicked.connect(self.open_formula_editor)
        extra_layout.addWidget(btn_formula)
        layout.addWidget(extra_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        self.update_parent_combo()
        self.update_extension_combo()
        self.parent_combo.currentTextChanged.connect(self._on_parent_changed)

        if class_name:
            self.load_existing_data()

    # ── Вспомогательные ──────────────────────────────────────────────────────

    def _current_class_name(self) -> str:
        name = self.name_edit.text().strip()
        return name if name else (self.class_name or "")

    def _get_ancestor_chain_from(self, start_name: str) -> list:
        chain = [start_name]
        visited = {start_name}
        current_name = start_name
        while True:
            elem = self.manager.classes.get(current_name)
            if not elem or not elem.parent:
                break
            parent_name = elem.parent.name
            if parent_name in visited:
                break
            visited.add(parent_name)
            chain.append(parent_name)
            current_name = parent_name
        return chain

    # ── Комбо ────────────────────────────────────────────────────────────────

    def update_parent_combo(self):
        self.parent_combo.clear()
        self.parent_combo.addItem("None")
        for name in sorted(self.manager.classes.keys()):
            if name != self.class_name:
                self.parent_combo.addItem(name)

    def update_extension_combo(self):
        current_text = self.extension_combo.currentText()
        self.extension_combo.blockSignals(True)
        self.extension_combo.clear()
        self.extension_combo.addItem("")
        parent_name = self.parent_combo.currentText()
        if parent_name and parent_name != "None":
            existing = self.manager.get_extensions_for_parent(parent_name)
            for ext_name in sorted(existing.keys()):
                if ext_name:
                    self.extension_combo.addItem(ext_name)
        if current_text:
            idx = self.extension_combo.findText(current_text)
            if idx >= 0:
                self.extension_combo.setCurrentIndex(idx)
            else:
                self.extension_combo.setCurrentText(current_text)
        self.extension_combo.blockSignals(False)

    def _on_parent_changed(self, parent_name: str):
        self.update_extension_combo()
        self.refresh_properties_lists()

    # ── Обновление панели свойств ─────────────────────────────────────────────

    def refresh_properties_lists(self, skip_snapshot: bool = False):
        if skip_snapshot:
            logger.debug(
                "[refresh_properties_lists] пропуск снэпшота (виджеты ещё не построены), "
                "_prop_values сохранён: %s", self._prop_values
            )
        else:
            self._snapshot_prop_values()
        self._rebuild_dp_panel()
        self.obj_props_list.clear()

        name = self._current_class_name()
        seen_op: set = set()

        for op in self.manager.object_properties.values():
            if op.domain and op.domain.name == name:
                seen_op.add(op.name)
                range_name = op.range_.name if op.range_ else "Any"
                item = QListWidgetItem(f"{op.name} → {range_name}")
                item.setData(Qt.UserRole, op.name)
                self.obj_props_list.addItem(item)

        for op in self._pending_object_properties:
            seen_op.add(op.name)
            range_name = op.range_.name if op.range_ else "Any"
            item = QListWidgetItem(f"{op.name} → {range_name}  [несохранённый]")
            item.setData(Qt.UserRole, f"__pending_op__{op.name}")
            item.setForeground(QColor("#cc7700"))
            self.obj_props_list.addItem(item)

        selected_parent = self.parent_combo.currentText()
        if selected_parent and selected_parent != "None":
            ancestors = self._get_ancestor_chain_from(selected_parent)
            for ancestor_name in ancestors:
                for op in self.manager.object_properties.values():
                    if op.domain and op.domain.name == ancestor_name and op.name not in seen_op:
                        seen_op.add(op.name)
                        range_name = op.range_.name if op.range_ else "Any"
                        item = QListWidgetItem(f"{op.name} → {range_name}")
                        item.setData(Qt.UserRole, op.name)
                        self.obj_props_list.addItem(item)

    def _snapshot_prop_values(self):
        """Сохраняет текущие значения полей ввода в _prop_values."""
        before = dict(self._prop_values)
        for i in range(self._dp_layout.count()):
            w = self._dp_layout.itemAt(i).widget()
            if w is None:
                continue
            prop_name = w.property("prop_name")
            if not prop_name:
                continue
            value_widget = w.findChild(QComboBox, "value_input")
            if value_widget is None:
                value_widget = w.findChild(QLineEdit, "value_input")
            if value_widget is not None:
                val = (value_widget.currentText() if isinstance(value_widget, QComboBox)
                       else value_widget.text()).strip()
                if val:
                    self._prop_values[prop_name] = val
                else:
                    self._prop_values.pop(prop_name, None)
        if self._prop_values != before:
            logger.debug(
                "[_snapshot_prop_values] _prop_values изменился:\n  было:  %s\n  стало: %s",
                before, self._prop_values
            )
        else:
            logger.debug("[_snapshot_prop_values] _prop_values не изменился: %s", self._prop_values)

    def _rebuild_dp_panel(self):
        """Перестраивает панель атрибутов с полями ввода значений."""
        while self._dp_layout.count():
            item = self._dp_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        name = self._current_class_name()
        seen_dp: set = set()
        all_dp: list = []  # (dp, is_pending)

        for dp in self.manager.data_properties.values():
            if dp.domain and dp.domain.name == name and dp.name not in seen_dp:
                seen_dp.add(dp.name)
                all_dp.append((dp, False))

        for dp in self._pending_data_properties:
            if dp.name not in seen_dp:
                seen_dp.add(dp.name)
                all_dp.append((dp, True))

        selected_parent = self.parent_combo.currentText()
        if selected_parent and selected_parent != "None":
            for ancestor_name in self._get_ancestor_chain_from(selected_parent):
                for dp in self.manager.data_properties.values():
                    if dp.domain and dp.domain.name == ancestor_name and dp.name not in seen_dp:
                        seen_dp.add(dp.name)
                        all_dp.append((dp, False))

        if not all_dp:
            lbl = QLabel("Нет атрибутов")
            lbl.setStyleSheet("color: gray; font-size: 11px;")
            self._dp_layout.addWidget(lbl)
            return

        for dp, is_pending in all_dp:
            self._add_dp_row(dp, is_pending)

    def _add_dp_row(self, dp, is_pending: bool):
        """Строка атрибута с полем ввода значения."""
        from core.model.elements import DataType

        row = QWidget()
        row.setProperty("prop_name", dp.name)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(2, 2, 2, 2)
        row_layout.setSpacing(6)

        color = "#cc7700" if is_pending else "#333333"
        suffix = "  [несохранённый]" if is_pending else ""
        lbl = QLabel(
            f"<span style='color:{color}'><b>{dp.name}</b> "
            f"<span style='color:gray;font-size:11px'>({dp.data_type.value}){suffix}</span></span>"
        )
        lbl.setFixedWidth(200)
        row_layout.addWidget(lbl)

        current_val = self._prop_values.get(dp.name, "")

        if dp.data_type == DataType.BOOLEAN:
            widget = QComboBox()
            widget.setObjectName("value_input")
            widget.addItems(["", "True", "False"])
            if current_val in ("True", "False"):
                widget.setCurrentText(current_val)
        elif dp.data_type == DataType.INTEGER:
            widget = QLineEdit()
            widget.setObjectName("value_input")
            widget.setPlaceholderText("целое число")
            widget.setText(current_val)
        elif dp.data_type == DataType.FLOAT:
            widget = QLineEdit()
            widget.setObjectName("value_input")
            widget.setPlaceholderText("дробное число")
            widget.setText(current_val)
        else:
            widget = QLineEdit()
            widget.setObjectName("value_input")
            widget.setPlaceholderText("строка")
            widget.setText(current_val)

        row_layout.addWidget(widget, 1)

        if not is_pending and dp.name in self.manager.data_properties:
            edit_btn = QPushButton("✎")
            edit_btn.setFixedWidth(28)
            edit_btn.setToolTip("Изменить определение атрибута")
            edit_btn.clicked.connect(lambda _, n=dp.name: self._open_edit_data_property_dialog(n))
            row_layout.addWidget(edit_btn)

        self._dp_layout.addWidget(row)



    # ── Добавление свойств ────────────────────────────────────────────────────

    def quick_add_data_property(self):
        from gui.dialogs.data_property_dialog import CreateDataPropertyDialog
        name = self._current_class_name()
        dialog = CreateDataPropertyDialog(self.manager, self, extra_class_name=name or None)
        if name:
            dialog.domain_combo.setCurrentText(name)
        if dialog.exec() == QDialog.Accepted:
            new_prop = dialog.get_element()
            if new_prop:
                if name in self.manager.classes:
                    self.manager.create_data_property(new_prop)
                else:
                    self._pending_data_properties.append(new_prop)
                self.refresh_properties_lists()

    def quick_add_object_property(self):
        from gui.dialogs.object_property_dialog import CreateObjectPropertyDialog
        name = self._current_class_name()
        dialog = CreateObjectPropertyDialog(self.manager, self, extra_class_name=name or None)
        if name:
            dialog.domain_combo.setCurrentText(name)
        if dialog.exec() == QDialog.Accepted:
            new_prop = dialog.get_element()
            if new_prop:
                if name in self.manager.classes:
                    self.manager.add_object_property(new_prop)
                else:
                    self._pending_object_properties.append(new_prop)
                self.refresh_properties_lists()

    # ── Редактирование свойств ────────────────────────────────────────────────

    def _open_edit_data_property_dialog(self, prop_name: str):
        from gui.dialogs.data_property_dialog import CreateDataPropertyDialog
        dialog = CreateDataPropertyDialog(self.manager, self, prop_name=prop_name)
        if dialog.exec() == QDialog.Accepted:
            new_prop = dialog.get_element()
            if new_prop:
                self.manager.update_data_property(prop_name, new_prop)
                self.refresh_properties_lists()

    def _edit_object_property(self, item: QListWidgetItem):
        prop_name = item.data(Qt.UserRole)
        if not prop_name or prop_name not in self.manager.object_properties:
            return
        self._open_edit_object_property_dialog(prop_name)

    def _edit_selected_object_property(self):
        selected = self.obj_props_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "Нет выбора", "Выберите отношение для редактирования")
            return
        prop_name = selected[0].data(Qt.UserRole)
        if prop_name:
            self._open_edit_object_property_dialog(prop_name)

    def _open_edit_object_property_dialog(self, prop_name: str):
        from gui.dialogs.object_property_dialog import CreateObjectPropertyDialog
        dialog = CreateObjectPropertyDialog(self.manager, self, prop_name=prop_name)
        if dialog.exec() == QDialog.Accepted:
            new_prop = dialog.get_element()
            if new_prop:
                self.manager.update_object_property(prop_name, new_prop)
                self.refresh_properties_lists()

    # ── Загрузка существующих данных ─────────────────────────────────────────

    def load_existing_data(self):
        self.elem = self.manager.classes[self.class_name]
        self.name_edit.setText(self.elem.name)
        self.uri_edit.setText(self.elem.uri or "")
        self.label_edit.setText(self.elem.label or "")
        self.comment_edit.setPlainText(self.elem.comment or "")
        self.formula_edit.setText(self.elem.formula or "")
        if self.elem.parent:
            self.parent_combo.setCurrentText(self.elem.parent.name)
        self.edge_combo.setCurrentText(self.elem.edge_type.value)

        # Загружаем переопределения и значения атрибутов
        self._overrides = dict(self.elem.overridden_properties)
        raw_pv = dict(getattr(self.elem, 'prop_values', {}))
        self._prop_values = raw_pv
        logger.debug(
            "[load_existing_data] класс='%s'  prop_values из модели: %s",
            self.class_name, raw_pv
        )

        self.update_extension_combo()
        if self.elem.extension:
            idx = self.extension_combo.findText(self.elem.extension)
            if idx >= 0:
                self.extension_combo.setCurrentIndex(idx)
            else:
                self.extension_combo.setCurrentText(self.elem.extension)

        self.refresh_properties_lists(skip_snapshot=True)

    # ── Формулы ───────────────────────────────────────────────────────────────

    def open_formula_editor(self):
        current_formula = self.formula_edit.text().strip()
        if not self.elem:
            self.elem = ClassElement(
                name=self.name_edit.text() or "temp",
                formula=current_formula
            )
        else:
            self.elem.formula = current_formula
        dialog = FormulaEditorDialog(self, target=self.elem)
        if dialog.exec() == QDialog.Accepted:
            self.formula_edit.setText(self.elem.formula or "")

    # ── Отложенные свойства ───────────────────────────────────────────────────

    def save_pending_properties(self, class_elem) -> None:
        for dp in self._pending_data_properties:
            dp.domain = class_elem
            try:
                self.manager.create_data_property(dp)
            except Exception as e:
                print(f"[save_pending_properties] data_property '{dp.name}': {e}")
        self._pending_data_properties.clear()

        for op in self._pending_object_properties:
            if op.domain and op.domain.name == class_elem.name:
                op.domain = class_elem
            if op.range_ and op.range_.name == class_elem.name:
                op.range_ = class_elem
            try:
                self.manager.add_object_property(op)
            except Exception as e:
                print(f"[save_pending_properties] object_property '{op.name}': {e}")
        self._pending_object_properties.clear()

    # ── Получение элемента ────────────────────────────────────────────────────

    def get_element(self) -> ClassElement | None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Имя класса обязательно")
            return None

        extension = self.extension_combo.currentText().strip() or None

        symbol_context = {}
        if self.elem and hasattr(self.elem, 'symbol_context'):
            symbol_context = self.elem.symbol_context or {}

        self._snapshot_prop_values()
        logger.debug(
            "[get_element] класс='%s'  _prop_values перед созданием элемента: %s",
            name, self._prop_values
        )

        new_elem = ClassElement(
            name=name,
            uri=self.uri_edit.text().strip() or None,
            label=self.label_edit.text().strip() or None,
            comment=self.comment_edit.toPlainText().strip() or None,
            formula=self.formula_edit.text().strip() or None,
            parent=self.manager.classes.get(
                self.parent_combo.currentText()
            ) if self.parent_combo.currentText() != "None" else None,
            edge_type=EdgeType(self.edge_combo.currentText()),
            extension=extension,
            symbol_context=symbol_context,
            overridden_properties=dict(self._overrides),
        )
        new_elem.prop_values = dict(self._prop_values)
        logger.debug(
            "[get_element] создан ClassElement '%s', prop_values: %s",
            name, new_elem.prop_values
        )
        return new_elem
