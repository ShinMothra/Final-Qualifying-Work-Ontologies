from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QLabel, QScrollArea, QWidget, QHBoxLayout
)
from core.model.elements import DataPropertyElement, PropertyCharacteristic, DataType


class CreateDataPropertyDialog(QDialog):
    def __init__(self, manager, parent=None, prop_name: str = None,
                 extra_class_name: str = None):
        """
        extra_class_name — имя класса, который ещё не сохранён в manager,
        но должен присутствовать в domain_combo (создание атрибута «на лету»).
        """
        super().__init__(parent)
        self.manager = manager
        self.prop_name = prop_name
        self._extra_class_name = extra_class_name

        self.setWindowTitle("Редактировать свойство" if prop_name else "Создать свойство")
        self.resize(450, 450)

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("Имя свойства:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Метка (Label):"))
        self.label_edit = QLineEdit()
        layout.addWidget(self.label_edit)

        layout.addWidget(QLabel("Домен (класс):"))
        self.domain_combo = QComboBox()
        self._fill_domain_combo()
        layout.addWidget(self.domain_combo)

        layout.addWidget(QLabel("Тип данных:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([t.value for t in DataType])
        layout.addWidget(self.type_combo)

        self.func_cb = QCheckBox("Функциональное")
        layout.addWidget(self.func_cb)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        btn = QPushButton("Сохранить" if prop_name else "Создать")
        btn.clicked.connect(self.accept)
        main_layout.addWidget(btn)

        if prop_name and prop_name in manager.data_properties:
            elem = manager.data_properties[prop_name]
            self.name_edit.setText(elem.name)
            self.domain_combo.setCurrentText(elem.domain.name)
            self.type_combo.setCurrentText(elem.data_type.value)
            self.func_cb.setChecked(PropertyCharacteristic.FUNCTIONAL in elem.characteristics)

    def _fill_domain_combo(self):
        """Заполняет domain_combo классами из manager + возможный ещё не сохранённый класс."""
        self.domain_combo.clear()
        names = sorted(self.manager.classes.keys())
        # Если передан extra_class_name и его ещё нет в manager — добавляем первым
        if self._extra_class_name and self._extra_class_name not in self.manager.classes:
            self.domain_combo.addItem(self._extra_class_name)
        for name in names:
            self.domain_combo.addItem(name)

    def get_element(self) -> DataPropertyElement | None:
        name = self.name_edit.text().strip()
        if not name:
            return None

        domain_name = self.domain_combo.currentText()

        # Домен может быть уже сохранённым классом или extra_class_name (заглушка)
        domain = self.manager.classes.get(domain_name)
        if domain is None and domain_name == self._extra_class_name:
            # Создаём временный объект-заглушку; реальная привязка произойдёт
            # после сохранения класса через manager.create_class / update_class
            from core.model.elements import ClassElement
            domain = ClassElement(name=domain_name)

        if domain is None:
            return None

        data_type = DataType(self.type_combo.currentText())
        chars = [PropertyCharacteristic.FUNCTIONAL] if self.func_cb.isChecked() else []
        return DataPropertyElement(name, domain, data_type, chars)
