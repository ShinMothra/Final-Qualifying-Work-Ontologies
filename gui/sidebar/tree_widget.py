from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QTreeWidgetItemIterator
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QColor, QBrush, QFont


class OntologyTreeWidget(QTreeWidget):
    item_selected = Signal(str, str)  # (type_node, name) — обычный клик, узел A
    item_path_target_selected = Signal(str, str)  # (type_node, name) — Ctrl+клик, узел B
    selection_cleared = Signal()  # клик по пустому месту / Esc — полная отмена выбора

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._ctrl_click_pending = False

        self.setHeaderLabel("Структура онтологии")
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.header().setStretchLastSection(True)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.currentItemChanged.connect(self._on_item_changed)

    def mousePressEvent(self, event):
        # Запоминаем, был ли зажат Ctrl на момент клика — currentItemChanged
        # сработает уже после super().mousePressEvent() и не передаёт модификаторы
        self._ctrl_click_pending = bool(event.modifiers() & Qt.ControlModifier)

        if self.itemAt(event.pos()) is None:
            self.selection_cleared.emit()
            super().mousePressEvent(event)
            self.clearSelection()
            self.setCurrentItem(None)
            return

        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selection_cleared.emit()
            self.clearSelection()
            self.setCurrentItem(None)
        super().keyPressEvent(event)

    def _on_item_changed(self, current, previous):
        if not current:
            return
        data = current.data(0, Qt.UserRole)
        if not data:
            return
        type_node, name_node = data

        if self._ctrl_click_pending:
            self._ctrl_click_pending = False
            self.item_path_target_selected.emit(type_node, name_node)
        else:
            self.item_selected.emit(type_node, name_node)

    def refresh(self):
        self.clear()

        manager = getattr(self.main_window, 'manager', None)
        if not manager:
            return

        # 1. Классы и Индивиды
        classes_root = QTreeWidgetItem(self)
        classes_root.setText(0, "Классы и Индивиды")
        classes_root.setIcon(0, QIcon("resources/icons/class_root.png"))

        for cls_name, cls_elem in manager.classes.items():
            if not cls_elem.parent:
                self.add_class_item(classes_root, cls_elem)

        # 2. Объектные свойства
        obj_prop_root = QTreeWidgetItem(self)
        obj_prop_root.setText(0, "Объектные свойства")
        obj_prop_root.setIcon(0, QIcon("resources/icons/object_property_root.png"))

        for prop_name in manager.object_properties.keys():
            item = QTreeWidgetItem(obj_prop_root)
            item.setText(0, prop_name)
            item.setData(0, Qt.UserRole, ("object_property", prop_name))
            item.setIcon(0, QIcon("resources/icons/object_property.png"))

        # 3. Свойства данных
        if hasattr(manager, 'data_properties'):
            data_prop_root = QTreeWidgetItem(self)
            data_prop_root.setText(0, "Свойства данных")
            for prop_name in manager.data_properties.keys():
                item = QTreeWidgetItem(data_prop_root)
                item.setText(0, prop_name)
                item.setData(0, Qt.UserRole, ("data_property", prop_name))
                item.setIcon(0, QIcon("resources/icons/data_property.png"))

        self.expandItem(classes_root)
        self.viewport().update()

    def add_class_item(self, parent_item: QTreeWidgetItem, cls_elem):
        class_item = QTreeWidgetItem(parent_item)
        class_item.setText(0, cls_elem.name)
        class_item.setData(0, Qt.UserRole, ("class", cls_elem.name))
        class_item.setIcon(0, QIcon("resources/icons/class.png"))

        manager = self.main_window.manager

        # Индивиды
        for ind_name, ind_elem in manager.individuals.items():
            if any(c.name == cls_elem.name for c in ind_elem.classes):
                ind_item = QTreeWidgetItem(class_item)
                ind_item.setText(0, ind_name)
                ind_item.setData(0, Qt.UserRole, ("individual", ind_name))
                ind_item.setIcon(0, QIcon("resources/icons/individual.png"))

        # Группируем подклассы по расширениям
        groups: dict[str | None, list] = {}
        for child in cls_elem.children:
            groups.setdefault(child.extension, []).append(child)

        # Сначала — без расширения
        for child in groups.get(None, []):
            self.add_class_item(class_item, child)

        # Затем — по расширениям
        for ext_name, children in sorted(groups.items(), key=lambda x: x[0] or ""):
            if ext_name is None:
                continue

            ext_item = QTreeWidgetItem(class_item)
            ext_item.setText(0, f"[{ext_name}]")
            ext_item.setData(0, Qt.UserRole, ("extension", ext_name))
            ext_item.setIcon(0, QIcon("resources/icons/class_root.png"))

            font = ext_item.font(0)
            font.setItalic(True)
            ext_item.setFont(0, font)
            ext_item.setForeground(0, QBrush(QColor(100, 140, 200)))

            for child in children:
                self.add_class_item(ext_item, child)

            ext_item.setExpanded(True)

        return class_item

    # ── Фильтрация ────────────────────────────────────────────────────────────

    def apply_filters(self, state: dict):
        """Скрывает/показывает элементы дерева согласно фильтрам."""
        show_classes     = state.get("show_classes", True)
        show_individuals = state.get("show_individuals", True)
        show_properties  = state.get("show_properties", True)
        max_level        = state.get("max_level", -1)  # -1 = все

        it = QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.UserRole)

            if not data:
                # Корневые секции — всегда видны
                item.setHidden(False)
                it += 1
                continue

            type_node = data[0]
            depth = self._item_depth(item)

            hide = False

            if type_node == "class":
                if not show_classes:
                    hide = True
                elif max_level != -1 and depth > max_level:
                    hide = True

            elif type_node == "individual":
                if not show_individuals:
                    hide = True
                elif max_level != -1 and depth > max_level:
                    hide = True

            elif type_node in ("object_property", "data_property"):
                if not show_properties:
                    hide = True

            elif type_node == "extension":
                # Узел расширения скрывается если классы скрыты
                if not show_classes:
                    hide = True
                elif max_level != -1 and depth > max_level:
                    hide = True

            item.setHidden(hide)
            it += 1

    def apply_search(self, query: str):
        """Подсвечивает совпадения в дереве, скрывает несовпадающие."""
        manager = getattr(self.main_window, 'manager', None)

        # Сброс подсветки и видимости
        it = QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            item.setBackground(0, QBrush())  # сброс фона
            it += 1

        if not query or not manager:
            return

        q = query.lower()
        matched_items = []

        it = QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.UserRole)
            if not data:
                it += 1
                continue

            type_node, name = data
            match = False

            if type_node == "class" and name in manager.classes:
                elem = manager.classes[name]
                match = (q in name.lower() or
                         (elem.label and q in elem.label.lower()))

            elif type_node == "individual" and name in manager.individuals:
                elem = manager.individuals[name]
                match = (q in name.lower() or
                         (elem.label and q in elem.label.lower()))

            elif type_node in ("object_property", "data_property"):
                match = q in name.lower()

            if match:
                item.setBackground(0, QBrush(QColor(255, 220, 80, 160)))
                matched_items.append(item)

            it += 1

        # Прокручиваем к первому совпадению
        if matched_items:
            self.scrollToItem(matched_items[0])
            self.setCurrentItem(matched_items[0])

    # ── Вспомогательные ──────────────────────────────────────────────────────

    def _item_depth(self, item: QTreeWidgetItem) -> int:
        """Возвращает глубину элемента (корень = 0)."""
        depth = 0
        parent = item.parent()
        while parent:
            depth += 1
            parent = parent.parent()
        return depth

    # ── Контекстное меню ─────────────────────────────────────────────────────

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.UserRole)
        if not data:
            return

        menu = QMenu(self)
        type_node, name_node = data

        if type_node == "class":
            menu.addAction("Редактировать", lambda: self.main_window.open_class_dialog(name_node))
            menu.addAction("Удалить класс", lambda: self.delete_class(name_node))

        elif type_node == "extension":
            menu.addAction(f"Расширение: {name_node}").setEnabled(False)

        elif type_node == "individual":
            menu.addAction("Редактировать", lambda: self.main_window.open_individual_dialog(name_node))
            menu.addAction("Удалить индивида", lambda: self.delete_individual(name_node))

        elif type_node == "object_property":
            menu.addAction("Редактировать отношение", lambda: self.main_window.open_object_property_dialog(name_node))
            menu.addAction("Удалить отношение", lambda: self.delete_object_property(name_node))

        elif type_node == "data_property":
            menu.addAction("Редактировать свойство", lambda: self.main_window.open_data_property_dialog(name_node))
            menu.addAction("Удалить свойство", lambda: self.delete_data_property(name_node))

        menu.exec(self.mapToGlobal(pos))

    # ── Удаление ─────────────────────────────────────────────────────────────

    def _editor(self):
        return getattr(self.main_window, 'editor', None)

    def delete_class(self, name):
        if QMessageBox.question(self, "Удаление", f"Удалить класс '{name}'?") != QMessageBox.Yes:
            return
        editor = self._editor()
        if editor:
            try:
                editor.delete_class(name)
                self.main_window.update_scene.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))
        else:
            if self.main_window.manager.delete_class(name):
                self.main_window.update_scene.emit()

    def delete_individual(self, name):
        if QMessageBox.question(self, "Удаление", f"Удалить индивида '{name}'?") != QMessageBox.Yes:
            return
        editor = self._editor()
        if editor:
            try:
                editor.delete_individual(name)
                self.main_window.update_scene.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))
        else:
            if self.main_window.manager.delete_individual(name):
                self.main_window.update_scene.emit()

    def delete_object_property(self, name):
        if QMessageBox.question(self, "Удаление", f"Удалить отношение '{name}'?") != QMessageBox.Yes:
            return
        editor = self._editor()
        if editor:
            try:
                editor.delete_object_property(name)
                self.main_window.update_scene.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))
        else:
            if hasattr(self.main_window.manager, 'delete_object_property'):
                if self.main_window.manager.delete_object_property(name):
                    self.main_window.update_scene.emit()

    def delete_data_property(self, name):
        if QMessageBox.question(self, "Удаление", f"Удалить свойство '{name}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        editor = self._editor()
        if editor:
            try:
                editor.delete_data_property(name)
                self.main_window.update_scene.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))
        else:
            if hasattr(self.main_window.manager, 'delete_data_property'):
                if self.main_window.manager.delete_data_property(name):
                    self.main_window.update_scene.emit()

    # ── Видимость расширений ─────────────────────────────────────────────────

    def hide_extension(self, ext_name: str):
        it = QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "extension" and data[1] == ext_name:
                item.setHidden(True)
            it += 1

    def show_extension(self, ext_name: str):
        it = QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "extension" and data[1] == ext_name:
                item.setHidden(False)
            it += 1
