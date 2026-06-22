from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QComboBox, QPushButton, QLabel,
    QCheckBox, QTextEdit, QGroupBox, QHBoxLayout, QWidget, QScrollArea
)
from core.model.elements import ObjectPropertyElement, PropertyCharacteristic


class CreateObjectPropertyDialog(QDialog):
    def __init__(self, manager, parent=None, prop_name: str = None,
                 extra_class_name: str = None):
        """
        extra_class_name — имя класса, который ещё не сохранён в manager,
        но должен присутствовать в domain/range combo (создание отношения «на лету»).
        """
        super().__init__(parent)
        self.manager = manager
        self.prop_name = prop_name
        self._extra_class_name = extra_class_name

        self.setWindowTitle("Редактировать отношение" if prop_name else "Создать отношение")
        self.resize(500, 650)

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Имя (обязательно):"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Метка (rdfs:label):"))
        self.label_edit = QLineEdit()
        layout.addWidget(self.label_edit)

        layout.addWidget(QLabel("Комментарий (rdfs:comment):"))
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(60)
        layout.addWidget(self.comment_edit)

        # Домен и диапазон
        dr_group = QGroupBox("Домен и диапазон")
        dr_layout = QVBoxLayout()

        for label, attr_type in [("Домен:", "domain"), ("Диапазон:", "range")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            type_combo = QComboBox()
            type_combo.addItems(["Классы", "Индивиды"])
            val_combo = QComboBox()
            val_combo.setEditable(True)
            self._fill_class_combo(val_combo)

            type_combo.currentTextChanged.connect(
                lambda t, c=val_combo: self._update_combo(t, c)
            )

            setattr(self, f"{attr_type}_type_combo", type_combo)
            setattr(self, f"{attr_type}_combo", val_combo)

            row.addWidget(type_combo, 1)
            row.addWidget(val_combo, 4)
            dr_layout.addLayout(row)

        dr_group.setLayout(dr_layout)
        layout.addWidget(dr_group)

        # Характеристики
        layout.addWidget(QLabel("Характеристики:"))
        self.chars = {
            "transitive":     QCheckBox("Транзитивное"),
            "symmetric":      QCheckBox("Симметричное"),
            "functional":     QCheckBox("Функциональное"),
            "inv_functional": QCheckBox("Инверсно-функциональное"),
            "reflexive":      QCheckBox("Рефлексивное"),
            "irreflexive":    QCheckBox("Иррефлексивное"),
            "asymmetric":     QCheckBox("Асимметричное"),
        }
        for cb in self.chars.values():
            layout.addWidget(cb)

        layout.addWidget(QLabel("Описание:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        layout.addWidget(self.desc_edit)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        btn = QPushButton("Сохранить" if prop_name else "Создать")
        btn.setMinimumHeight(40)
        btn.clicked.connect(self.accept)
        main_layout.addWidget(btn)

        if prop_name and prop_name in manager.object_properties:
            self.load_data()

    # ── заполнение комбо ─────────────────────────────────────────────────────

    def _fill_class_combo(self, combo: QComboBox):
        """Классы из manager + возможный ещё не сохранённый класс."""
        combo.clear()
        if self._extra_class_name and self._extra_class_name not in self.manager.classes:
            combo.addItem(self._extra_class_name)
        for name in sorted(self.manager.classes.keys()):
            combo.addItem(name)

    def _update_combo(self, text: str, combo: QComboBox):
        """Переключение между классами и индивидами."""
        combo.clear()
        if text == "Классы":
            self._fill_class_combo(combo)
        else:
            for name in sorted(self.manager.individuals.keys()):
                combo.addItem(name)

    # ── загрузка существующих данных ─────────────────────────────────────────

    def load_data(self):
        elem = self.manager.object_properties[self.prop_name]
        self.name_edit.setText(elem.name)
        self.label_edit.setText(getattr(elem, 'label', "") or "")
        self.comment_edit.setPlainText(getattr(elem, 'comment', "") or "")
        self.desc_edit.setPlainText(getattr(elem, 'description', "") or "")
        if elem.domain:
            self.domain_combo.setCurrentText(elem.domain.name)
        if elem.range_:
            self.range_combo.setCurrentText(elem.range_.name)

        mapping = {
            PropertyCharacteristic.TRANSITIVE:          self.chars["transitive"],
            PropertyCharacteristic.SYMMETRIC:           self.chars["symmetric"],
            PropertyCharacteristic.FUNCTIONAL:          self.chars["functional"],
            PropertyCharacteristic.INVERSE_FUNCTIONAL:  self.chars["inv_functional"],
            PropertyCharacteristic.REFLEXIVE:           self.chars["reflexive"],
            PropertyCharacteristic.IRREFLEXIVE:         self.chars["irreflexive"],
            PropertyCharacteristic.ASYMMETRIC:          self.chars["asymmetric"],
        }
        for char, cb in mapping.items():
            cb.setChecked(char in elem.characteristics)

    # ── получение элемента ───────────────────────────────────────────────────

    def _resolve_domain_or_range(self, combo: QComboBox, type_combo: QComboBox):
        """Возвращает ClassElement/IndividualElement или временную заглушку."""
        selected = combo.currentText().strip()
        if not selected:
            return None

        if type_combo.currentText() == "Классы":
            obj = self.manager.classes.get(selected)
            if obj is None and selected == self._extra_class_name:
                from core.model.elements import ClassElement
                obj = ClassElement(name=selected)
            return obj
        else:
            return self.manager.individuals.get(selected)

    def get_element(self) -> ObjectPropertyElement | None:
        name = self.name_edit.text().strip()
        if not name:
            return None

        domain = self._resolve_domain_or_range(self.domain_combo, self.domain_type_combo)
        range_ = self._resolve_domain_or_range(self.range_combo, self.range_type_combo)

        characteristics = []
        mapping = {
            PropertyCharacteristic.TRANSITIVE:          self.chars["transitive"],
            PropertyCharacteristic.SYMMETRIC:           self.chars["symmetric"],
            PropertyCharacteristic.FUNCTIONAL:          self.chars["functional"],
            PropertyCharacteristic.INVERSE_FUNCTIONAL:  self.chars["inv_functional"],
            PropertyCharacteristic.REFLEXIVE:           self.chars["reflexive"],
            PropertyCharacteristic.IRREFLEXIVE:         self.chars["irreflexive"],
            PropertyCharacteristic.ASYMMETRIC:          self.chars["asymmetric"],
        }
        for char, cb in mapping.items():
            if cb.isChecked():
                characteristics.append(char)

        return ObjectPropertyElement(
            name=name,
            domain=domain,
            range_=range_,
            characteristics=characteristics,
            description=self.desc_edit.toPlainText(),
            label=self.label_edit.text().strip(),
            comment=self.comment_edit.toPlainText(),
        )
    