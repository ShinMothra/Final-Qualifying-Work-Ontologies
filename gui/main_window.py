import traceback
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QMenuBar, QMessageBox,
    QFileDialog, QDialog, QFrame, QStackedWidget, QInputDialog
)
from PySide6.QtGui import QAction, QPalette, QColor, QFontDatabase, QFont, QIcon, QKeySequence
from PySide6.QtCore import Signal, QPropertyAnimation, QEasingCurve, QTimer, Qt

from gui.start_page import StartPage
from gui.canvas.graphics_scene import OntologyScene, OntologyView
from gui.toolbox.toolbox_widget import ToolboxWidget
from gui.dialogs.class_dialog import CreateClassDialog
from gui.dialogs.object_property_dialog import CreateObjectPropertyDialog
from gui.dialogs.data_property_dialog import CreateDataPropertyDialog
from gui.dialogs.individual_dialog import CreateIndividualDialog
from gui.canvas.layout_storage import save_layout
from gui.canvas.minimap import MiniMap

from modules.editor_module import EditorModule
from modules.validation_module import ValidationModule
from modules.export_module import ExportModule
from core.model.ontology import OntologyManager
from core.history import HistoryManager

from modules.formula_module.formula_editor import FormulaEditorDialog


class MainWindow(QMainWindow):
    update_scene = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Конструктор Онтологий")
        self.setGeometry(100, 100, 1400, 900)

        self.setWindowIcon(QIcon("resources/icons/app_icon.ico"))

        self.manager = None
        self.history: HistoryManager | None = None
        self.current_file_path: str | None = None

        try:
            self.setStyleSheet(open("resources/style.qss", "r", encoding="utf-8").read())
            font_db = QFontDatabase()
            font_id = font_db.addApplicationFont("resources/Roboto-Regular.ttf")
            if font_id != -1:
                font_family = font_db.applicationFontFamilies(font_id)[0]
                self.setFont(QFont(font_family, 12))
        except Exception as e:
            print(f"Не удалось загрузить стиль/шрифт: {e}")

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.start_page = StartPage()
        self.stacked_widget.addWidget(self.start_page)

        self.editor_widget = None
        self.scene = None
        self.toolbox = None

        self.start_page.project_selected.connect(self.open_project)
        self.start_page.create_new.connect(self.create_new_project)
        self.start_page.import_project.connect(self.import_owl_project)

        self.stacked_widget.setCurrentWidget(self.start_page)

    # ── Заголовок ────────────────────────────────────────────────────────────

    def _update_title(self):
        if self.current_file_path:
            filename = os.path.basename(self.current_file_path)
            self.setWindowTitle(f"{filename} — Конструктор Онтологий")
        else:
            self.setWindowTitle("Конструктор Онтологий")

    # ── Закрытие ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        try:
            if hasattr(self, 'scene') and self.scene:
                save_layout(self.scene, self.current_file_path)
        except Exception as e:
            print(f"Не удалось сохранить макет при закрытии: {e}")
        event.accept()

    # ── Сохранение ───────────────────────────────────────────────────────────

    def save_current(self):
        """Ctrl+S — сохраняет в текущий файл, если он известен."""
        if not self.current_file_path:
            self.run_export()
            return
        try:
            ext = os.path.splitext(self.current_file_path)[1].lower()
            format_ = "json" if ext == ".json" else "rdfxml"
            self.exporter.export(self.current_file_path, format_)
            if self.scene:
                save_layout(self.scene, self.current_file_path)
            filename = os.path.basename(self.current_file_path)
            self.setWindowTitle(f"{filename} — Конструктор Онтологий  ✓")
            QTimer.singleShot(2000, self._update_title)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

    # ── История: Undo / Redo ─────────────────────────────────────────────────

    def undo(self):
        if not self.history or not self.history.can_undo():
            return
        desc = self.history.undo()
        print(f"[Undo] {desc}")
        self._refresh_after_history()
        self._update_undo_redo_actions()

    def redo(self):
        if not self.history or not self.history.can_redo():
            return
        desc = self.history.redo()
        print(f"[Redo] {desc}")
        self._refresh_after_history()
        self._update_undo_redo_actions()

    def _refresh_after_history(self):
        """Обновляет сцену и дерево после undo/redo."""
        try:
            if self.scene:
                self.scene.update_from_manager()
            if hasattr(self, 'scene_view'):
                self.scene_view.update_view()
            if hasattr(self, 'toolbox'):
                self.toolbox.refresh()
        except Exception as e:
            print(f"Ошибка обновления после undo/redo: {e}")
            traceback.print_exc()

    def _update_undo_redo_actions(self):
        """Обновляет состояние пунктов меню Undo/Redo."""
        if hasattr(self, '_undo_action'):
            can = self.history.can_undo() if self.history else False
            desc = self.history.undo_description() if can else ""
            self._undo_action.setEnabled(can)
            self._undo_action.setText(f"Отменить «{desc}»" if desc else "Отменить")

        if hasattr(self, '_redo_action'):
            can = self.history.can_redo() if self.history else False
            desc = self.history.redo_description() if can else ""
            self._redo_action.setEnabled(can)
            self._redo_action.setText(f"Повторить «{desc}»" if desc else "Повторить")

    # ── Проекты ──────────────────────────────────────────────────────────────

    def create_new_project(self):
        self.manager = OntologyManager()
        self.history = HistoryManager()
        self.current_file_path = None
        self.setup_editor()
        self.init_editor_modules()
        self.stacked_widget.setCurrentWidget(self.editor_widget)
        self._update_title()
        QTimer.singleShot(50, self.on_update_scene)

    def open_project(self, path: str):
        if not path:
            return

        self.manager = OntologyManager()
        self.history = HistoryManager()

        try:
            ext = Path(path).suffix.lower()

            if ext == ".json":
                from core.storage.owl_handler import OWLHandler
                OWLHandler.load_json(path, self.manager)
            else:
                # OWL / Turtle / RDF/XML
                from core.storage.owl_handler import OWLHandler
                success = OWLHandler.load_ontology(path, self.manager)
                if not success:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл:\n{path}")
                    return

            self.current_file_path = path
            self.setup_editor()
            self.init_editor_modules()
            self.stacked_widget.setCurrentWidget(self.editor_widget)

            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()

            QTimer.singleShot(50, self.on_update_scene)

            self.start_page.add_recent_project(Path(path).stem, path)

            self._update_title()
            QMessageBox.information(self, "Успех", f"Онтология успешно загружена:\n{path}")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Критическая ошибка при открытии:\n{e}")

    def on_update_scene(self):
        try:
            if self.scene:
                self.scene.update_from_manager()
            if hasattr(self, 'scene_view'):
                self.scene_view.update_view()
            if hasattr(self, 'toolbox'):
                self.toolbox.refresh()
            self._update_undo_redo_actions()
        except Exception as e:
            print(f"Ошибка обновления: {e}")
            traceback.print_exc()

    def import_owl_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импортировать OWL", "", "OWL Files (*.owl *.ttl *.rdf);;Все файлы (*)"
        )
        if path:
            self.open_project(path)

    def import_json_project(self):
        """Загрузка онтологии из JSON-файла, созданного этим редактором."""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Открыть JSON", "", "JSON Files (*.json);;Все файлы (*)"
            )
            if not filename:
                return

            self.manager = OntologyManager()
            self.history = HistoryManager()

            from core.storage.owl_handler import OWLHandler
            OWLHandler.load_json(filename, self.manager)

            self.current_file_path = filename

            if self.editor_widget is None:
                self.setup_editor()
                self.init_editor_modules()
            else:
                self.scene.manager = self.manager
                self.editor = EditorModule(self.manager, self.history)
                self.validator = ValidationModule(self.manager)
                self.exporter = ExportModule(self.manager)

            self.stacked_widget.setCurrentWidget(self.editor_widget)
            QTimer.singleShot(50, self.on_update_scene)
            self._update_title()
            self.start_page.add_recent_project(Path(filename).stem, filename)
            QMessageBox.information(self, "Успех", f"Онтология загружена из JSON:\n{filename}")
        except Exception as e:
            print(f"Ошибка в import_json_project: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить JSON:\n{e}")

    def setup_editor(self):
        if self.editor_widget is not None:
            return

        self.editor_widget = QWidget()
        self.main_hbox = QHBoxLayout(self.editor_widget)
        self.main_hbox.setContentsMargins(2, 2, 2, 2)
        self.main_hbox.setSpacing(2)

        self.toolbox = ToolboxWidget(self)
        self.toolbox.tree.item_selected.connect(
            lambda t, n: self.scene.highlight_node(t, n)
        )
        self.toolbox.tree.item_path_target_selected.connect(
            lambda t, n: self.scene.select_path_target(t, n)
        )
        self.toolbox.tree.selection_cleared.connect(
            lambda: self.scene.clear_path_selection()
        )
        self.toolbox.setMinimumWidth(300)

        self.canvas_frame = QFrame()
        self.canvas_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        canvas_layout = QVBoxLayout(self.canvas_frame)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.scene = OntologyScene(self.manager)
        self.scene.node_clicked.connect(self._on_node_clicked)
        self.scene_view = OntologyView(self.scene)
        canvas_layout.addWidget(self.scene_view)

        self.minimap = MiniMap(self.scene_view, self.canvas_frame)
        self.minimap.attach()

        self.main_hbox.addWidget(self.toolbox, 1)
        self.main_hbox.addWidget(self.canvas_frame, 3)

        self.stacked_widget.addWidget(self.editor_widget)

    def init_editor_modules(self):
        self.editor = EditorModule(self.manager, self.history)
        self.validator = ValidationModule(self.manager)
        self.exporter = ExportModule(self.manager)

        self.scene.manager = self.manager
        self.update_scene.connect(self.on_update_scene)
        self.create_menu()

        if hasattr(self, 'toolbox'):
            self.toolbox.refresh()

        self._update_undo_redo_actions()

    # ── Меню ─────────────────────────────────────────────────────────────────

    def create_menu(self):
        if hasattr(self, "menu_created"):
            return
        self.menu_created = True

        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")
        edit_menu = menubar.addMenu("Редактирование")
        tools_menu = menubar.addMenu("Инструменты")

        # Файл
        save_act = QAction("Сохранить", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self.save_current)
        file_menu.addAction(save_act)

        export_act = QAction("Сохранить как...", self)
        export_act.triggered.connect(self.run_export)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        open_act = QAction("Открыть OWL...", self)
        open_act.triggered.connect(self.open_owl_file)
        file_menu.addAction(open_act)

        open_json_act = QAction("Открыть JSON...", self)
        open_json_act.triggered.connect(self.import_json_project)
        file_menu.addAction(open_json_act)

        # Undo / Redo
        self._undo_action = QAction("Отменить", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self.undo)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("Повторить", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.setEnabled(False)
        self._redo_action.triggered.connect(self.redo)
        edit_menu.addAction(self._redo_action)

        edit_menu.addSeparator()

        new_class_act = QAction(QIcon("resources/icons/add.png"), "Новый класс", self)
        new_class_act.triggered.connect(self.open_class_dialog)
        edit_menu.addAction(new_class_act)

        new_ind_act = QAction(QIcon("resources/icons/add.png"), "Новый индивид", self)
        new_ind_act.triggered.connect(self.open_individual_dialog)
        edit_menu.addAction(new_ind_act)

        new_obj_prop_act = QAction(QIcon("resources/icons/add.png"), "Новое отношение", self)
        new_obj_prop_act.triggered.connect(self.open_object_property_dialog)
        edit_menu.addAction(new_obj_prop_act)

        formula_action = QAction("Редактор формул", self)
        formula_action.triggered.connect(self.open_formula_editor)
        edit_menu.addAction(formula_action)

        validate_act = QAction(QIcon("resources/icons/edit.png"), "Валидация", self)
        validate_act.triggered.connect(self.run_validation)
        tools_menu.addAction(validate_act)

    # ── Диалоги ──────────────────────────────────────────────────────────────

    def open_class_dialog(self, class_name: str = None):
        try:
            dialog = CreateClassDialog(self.manager, self, class_name)
            dialog.setProperty("opacity", 0)
            dialog.show()
            anim = QPropertyAnimation(dialog, b"windowOpacity")
            anim.setDuration(300)
            anim.setStartValue(0)
            anim.setEndValue(1)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start()

            if dialog.exec() == QDialog.Accepted:
                elem = dialog.get_element()
                if not elem:
                    return
                if class_name:
                    self.editor.update_class(class_name, elem)
                else:
                    self.editor.create_class(elem)
                    created = self.manager.classes.get(elem.name)
                    if created:
                        dialog.save_pending_properties(created)
                QTimer.singleShot(0, self.update_scene.emit)

        except Exception as e:
            print(f"Ошибка в open_class_dialog: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось обработать класс: {e}")

    def open_object_property_dialog(self, prop_name: str = None):
        try:
            if not self.manager.classes:
                QMessageBox.warning(self, "Предупреждение", "Создайте хотя бы один класс!")
                return

            dialog = CreateObjectPropertyDialog(self.manager, self, prop_name)
            dialog.setProperty("opacity", 0)
            dialog.show()
            anim = QPropertyAnimation(dialog, b"windowOpacity")
            anim.setDuration(300)
            anim.setStartValue(0)
            anim.setEndValue(1)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start()

            if dialog.exec() == QDialog.Accepted:
                elem = dialog.get_element()
                if elem:
                    if prop_name:
                        self.editor.update_object_property(prop_name, elem)
                    else:
                        self.editor.create_object_property(elem)
                    self.update_scene.emit()
        except Exception as e:
            print(f"Ошибка в open_object_property_dialog: {e}")
            traceback.print_exc()

    def open_data_property_dialog(self, prop_name: str = None):
        try:
            if not self.manager.classes:
                QMessageBox.warning(self, "Предупреждение", "Создайте хотя бы один класс!")
                return

            dialog = CreateDataPropertyDialog(self.manager, self, prop_name)
            dialog.setProperty("opacity", 0)
            dialog.show()
            anim = QPropertyAnimation(dialog, b"windowOpacity")
            anim.setDuration(300)
            anim.setStartValue(0)
            anim.setEndValue(1)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start()

            if dialog.exec() == QDialog.Accepted:
                elem = dialog.get_element()
                if elem:
                    if prop_name:
                        self.editor.update_data_property(prop_name, elem)
                    else:
                        self.editor.create_data_property(elem)
                    self.update_scene.emit()
        except Exception as e:
            print(f"Ошибка в open_data_property_dialog: {e}")
            traceback.print_exc()

    def open_individual_dialog(self, ind_name: str = None):
        try:
            if not self.manager.classes:
                QMessageBox.warning(self, "Внимание", "Сначала создайте хотя бы один класс!")
                return

            dialog = CreateIndividualDialog(self.manager, self, ind_name)
            if dialog.exec() == QDialog.Accepted:
                elem = dialog.get_element()
                if not elem:
                    return
                if ind_name:
                    self.editor.update_individual(ind_name, elem)
                else:
                    self.editor.create_individual(elem)
                self.update_scene.emit()

        except Exception as e:
            print(f"Ошибка в open_individual_dialog: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось обработать индивида: {e}")

    def open_owl_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Открыть OWL", "", "OWL Files (*.owl *.ttl *.rdf)")
        if filename:
            self.open_project(filename)

    def run_validation(self):
        try:
            is_valid, report = self.validator.run()
            title = "Валидация: OK" if is_valid else "Валидация: Ошибки"
            QMessageBox.information(self, title, report)
        except Exception as e:
            print(f"Ошибка в run_validation: {e}")
            traceback.print_exc()

    def run_export(self):
        try:
            filename, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Сохранить онтологию",
                self.current_file_path or "ontology.owl",
                "OWL Files (*.owl);;RDF/XML (*.rdf);;JSON (*.json)"
            )
            if not filename:
                return

            _FILTER_MAP = {
                "OWL Files (*.owl)": (".owl", "rdfxml"),
                "RDF/XML (*.rdf)":   (".rdf", "rdfxml"),
                "JSON (*.json)":     (".json", "json"),
            }

            ext = os.path.splitext(filename)[1].lower()
            expected_ext, format_ = _FILTER_MAP.get(
                selected_filter, (ext or ".owl", "rdfxml")
            )

            if ext != expected_ext:
                base = os.path.splitext(filename)[0]
                filename = base + expected_ext

            self.exporter.export(filename, format_)
            self.current_file_path = filename
            if self.scene:
                save_layout(self.scene, self.current_file_path)
            self._update_title()
            QMessageBox.information(self, "Успех", "Онтология успешно сохранена.")
        except Exception as e:
            print(f"Ошибка в run_export: {e}")
            traceback.print_exc()

    def open_formula_editor(self):
        dialog = FormulaEditorDialog(self)
        dialog.exec()

    def _on_node_clicked(self, type_node: str, name: str):
        self.scene.highlight_node(type_node, name)

        tree = self.toolbox.tree
        tree.blockSignals(True)
        try:
            it = tree.findItems(name, Qt.MatchRecursive | Qt.MatchExactly, 0)
            for item in it:
                data = item.data(0, Qt.UserRole)
                if data and data[0] == type_node and data[1] == name:
                    tree.setCurrentItem(item)
                    tree.scrollToItem(item)
                    break
        finally:
            tree.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'minimap'):
            self.minimap.parentResizeEvent()
