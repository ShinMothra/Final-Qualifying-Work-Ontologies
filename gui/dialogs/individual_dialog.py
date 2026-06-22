from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QMessageBox,
    QGroupBox, QFormLayout, QComboBox, QScrollArea, QWidget,
    QFrame
)
from PySide6.QtCore import Qt
from core.model.elements import IndividualElement, PropertyOverride, DataType
from modules.formula_module.formula_editor import FormulaEditorDialog


class CreateIndividualDialog(QDialog):
    def __init__(self, manager, parent=None, ind_name: str = None):
        super().__init__(parent)
        self.manager = manager
        self.ind_name = ind_name
        self.elem = None
        self._overrides: dict = {}

        self.setWindowTitle("Редактировать индивид" if ind_name else "Создать новый индивид")
        self.resize(580, 700)

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setSpacing(12)

        # ── Основная информация ───────────────────────────────────────────────
        self.content_layout.addWidget(QLabel("Имя индивида:"))
        self.name_edit = QLineEdit()
        self.content_layout.addWidget(self.name_edit)

        self.content_layout.addWidget(QLabel("Принадлежит классам:"))
        self.class_list = QListWidget()
        self.class_list.setMaximumHeight(120)
        for cls_name in sorted(manager.classes.keys()):
            item = QListWidgetItem(cls_name)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Unchecked)
            self.class_list.addItem(item)

        self.class_list.itemChanged.connect(self.refresh_properties_fields)
        self.content_layout.addWidget(self.class_list)

        # ── Свойства ─────────────────────────────────────────────────────────
        self.props_group = QGroupBox("Свойства и атрибуты")
        self.props_layout = QVBoxLayout(self.props_group)
        self.props_layout.setSpacing(6)
        self.content_layout.addWidget(self.props_group)

        self.data_edits: dict = {}
        self.obj_combos: dict = {}

        # ── Комментарий ───────────────────────────────────────────────────────
        self.content_layout.addWidget(QLabel("Комментарий:"))
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(60)
        self.content_layout.addWidget(self.comment_edit)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        main_layout.addLayout(buttons)

        if ind_name:
            self.load_existing_data()

    # ── Вспомогательные ──────────────────────────────────────────────────────

    def _selected_class_elems(self) -> list:
        return [
            self.manager.classes[self.class_list.item(i).text()]
            for i in range(self.class_list.count())
            if self.class_list.item(i).checkState() == Qt.Checked
            and self.class_list.item(i).text() in self.manager.classes
        ]

    # ── Построение панели свойств ─────────────────────────────────────────────

    def refresh_properties_fields(self):
        """
        Собирает все data/object properties выбранных классов
        включая унаследованные по цепочке предков — и показывает
        единым списком без разделения на собственные/унаследованные.
        """
        while self.props_layout.count():
            item = self.props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.data_edits.clear()
        self.obj_combos.clear()

        selected_classes = self._selected_class_elems()
        if not selected_classes:
            lbl = QLabel("Выберите хотя бы один класс")
            lbl.setStyleSheet("color: gray;")
            self.props_layout.addWidget(lbl)
            return

        # Собираем все data properties: собственные + унаследованные
        seen_dp: set = set()
        all_dp: list = []
        for cls in selected_classes:
            for dp in cls.get_all_data_properties(self.manager.data_properties):
                if dp.name not in seen_dp:
                    seen_dp.add(dp.name)
                    all_dp.append(dp)

        # Собираем все object properties
        seen_op: set = set()
        all_op: list = []
        for cls in selected_classes:
            for op in cls.get_all_object_properties(self.manager.object_properties):
                if op.name not in seen_op:
                    seen_op.add(op.name)
                    all_op.append(op)

        if not all_dp and not all_op:
            lbl = QLabel("Нет свойств у выбранных классов")
            lbl.setStyleSheet("color: gray;")
            self.props_layout.addWidget(lbl)
            return

        if all_dp:
            self.props_layout.addWidget(QLabel("<b>Атрибуты данных:</b>"))
            for dp in all_dp:
                self._add_data_row(dp)

        if all_op:
            self.props_layout.addWidget(QLabel("<b>Отношения:</b>"))
            for op in all_op:
                self._add_object_row(op)

    def _add_data_row(self, dp):
        override = self._overrides.get(dp.name, PropertyOverride())
        excluded = override.excluded

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        row = QVBoxLayout(frame)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{dp.name}</b>  <span style='color:gray;font-size:11px'>{dp.data_type.value}</span>"))
        header.addStretch()

        excl_btn = QPushButton("✗ Исключить" if not excluded else "↩ Восстановить")
        excl_btn.setFixedWidth(120)
        excl_btn.setStyleSheet(
            "color: #cc3300; font-size: 11px;" if not excluded
            else "color: #007700; font-size: 11px;"
        )
        excl_btn.clicked.connect(lambda _, n=dp.name: self._toggle_exclude(n))
        header.addWidget(excl_btn)
        row.addLayout(header)

        if excluded:
            lbl = QLabel("⊘ Свойство исключено")
            lbl.setStyleSheet("color: #cc3300; font-style: italic; font-size: 11px;")
            row.addWidget(lbl)
            frame.setStyleSheet("QFrame { background: #fff5f5; border-radius: 6px; }")
        else:
            edit = QLineEdit()
            edit.setPlaceholderText(f"Тип: {dp.data_type.value}")
            if override.value is not None:
                edit.setText(str(override.value))
            row.addWidget(edit)
            self.data_edits[dp.name] = edit

        self.props_layout.addWidget(frame)

    def _add_object_row(self, op):
        override = self._overrides.get(op.name, PropertyOverride())
        excluded = override.excluded

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        row = QVBoxLayout(frame)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(4)

        header = QHBoxLayout()
        range_name = op.range_.name if op.range_ else "Any"
        header.addWidget(QLabel(f"<b>{op.name}</b>  <span style='color:gray;font-size:11px'>→ {range_name}</span>"))
        header.addStretch()

        excl_btn = QPushButton("✗ Исключить" if not excluded else "↩ Восстановить")
        excl_btn.setFixedWidth(120)
        excl_btn.setStyleSheet(
            "color: #cc3300; font-size: 11px;" if not excluded
            else "color: #007700; font-size: 11px;"
        )
        excl_btn.clicked.connect(lambda _, n=op.name: self._toggle_exclude(n))
        header.addWidget(excl_btn)
        row.addLayout(header)

        if excluded:
            lbl = QLabel("⊘ Свойство исключено")
            lbl.setStyleSheet("color: #cc3300; font-style: italic; font-size: 11px;")
            row.addWidget(lbl)
            frame.setStyleSheet("QFrame { background: #fff5f5; border-radius: 6px; }")
        else:
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems([""] + sorted(self.manager.individuals.keys()))
            if override.value:
                combo.setCurrentText(str(override.value))
            row.addWidget(combo)
            self.obj_combos[op.name] = combo

        self.props_layout.addWidget(frame)

    def _toggle_exclude(self, prop_name: str):
        ov = self._overrides.get(prop_name, PropertyOverride())
        ov.excluded = not ov.excluded
        if ov.excluded or ov.value or ov.comment:
            self._overrides[prop_name] = ov
        else:
            self._overrides.pop(prop_name, None)
        # Сохраняем текущие значения полей перед перерисовкой
        self._snapshot_values()
        self.refresh_properties_fields()
        self._restore_values()

    def _snapshot_values(self):
        """Запоминает текущие значения полей в _overrides перед перерисовкой."""
        for prop_name, edit in self.data_edits.items():
            val = edit.text().strip()
            ov = self._overrides.get(prop_name, PropertyOverride())
            ov.value = val or None
            if ov.value or ov.excluded:
                self._overrides[prop_name] = ov
            else:
                self._overrides.pop(prop_name, None)
        for prop_name, combo in self.obj_combos.items():
            val = combo.currentText().strip()
            ov = self._overrides.get(prop_name, PropertyOverride())
            ov.value = val or None
            if ov.value or ov.excluded:
                self._overrides[prop_name] = ov
            else:
                self._overrides.pop(prop_name, None)

    def _restore_values(self):
        """Восстанавливает значения полей после перерисовки."""
        for prop_name, edit in self.data_edits.items():
            ov = self._overrides.get(prop_name)
            if ov and ov.value is not None:
                edit.setText(str(ov.value))
        for prop_name, combo in self.obj_combos.items():
            ov = self._overrides.get(prop_name)
            if ov and ov.value:
                combo.setCurrentText(str(ov.value))

    # ── Загрузка существующих данных ─────────────────────────────────────────

    def load_existing_data(self):
        self.elem = self.manager.individuals[self.ind_name]
        self.name_edit.setText(self.elem.name)
        self.comment_edit.setPlainText(self.elem.comment)
        self._overrides = dict(self.elem.overridden_properties)

        self.class_list.blockSignals(True)
        for i in range(self.class_list.count()):
            item = self.class_list.item(i)
            if any(c.name == item.text() for c in self.elem.classes):
                item.setCheckState(Qt.Checked)
        self.class_list.blockSignals(False)
        self.refresh_properties_fields()

        for prop_name, value in self.elem.data_assertions.items():
            if prop_name in self.data_edits:
                self.data_edits[prop_name].setText(str(value))
        for prop_name, targets in self.elem.object_assertions.items():
            if prop_name in self.obj_combos and targets:
                self.obj_combos[prop_name].setCurrentText(targets[0])

    # ── Получение элемента ────────────────────────────────────────────────────

    def get_element(self) -> IndividualElement | None:
        name = self.name_edit.text().strip()
        if not name:
            return None

        selected_classes = self._selected_class_elems()
        if not selected_classes:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один класс")
            return None

        self._snapshot_values()

        elem = IndividualElement(
            name=name,
            classes=selected_classes,
            comment=self.comment_edit.toPlainText(),
            overridden_properties=dict(self._overrides),
        )

        for p_name, edit in self.data_edits.items():
            if edit.text().strip():
                elem.data_assertions[p_name] = edit.text().strip()

        for p_name, combo in self.obj_combos.items():
            if combo.currentText().strip():
                elem.object_assertions[p_name] = [combo.currentText().strip()]

        return elem
