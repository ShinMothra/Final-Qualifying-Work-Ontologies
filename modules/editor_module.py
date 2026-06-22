from core.model.ontology import OntologyManager
from core.model.elements import (
    ClassElement, ObjectPropertyElement,
    DataPropertyElement, IndividualElement
)
from core.history import HistoryManager
from core.commands import (
    CreateClassCommand, UpdateClassCommand, DeleteClassCommand,
    CreateObjectPropertyCommand, UpdateObjectPropertyCommand, DeleteObjectPropertyCommand,
    CreateDataPropertyCommand, UpdateDataPropertyCommand, DeleteDataPropertyCommand,
    CreateIndividualCommand, UpdateIndividualCommand, DeleteIndividualCommand,
)


class EditorModule:
    def __init__(self, manager: OntologyManager, history: HistoryManager = None):
        self.manager = manager
        self.history = history or HistoryManager()

    # ── Классы ───────────────────────────────────────────────────────────────

    def create_class(self, elem: ClassElement) -> None:
        try:
            self.history.push(CreateClassCommand(self.manager, elem))
            print(f"[EditorModule] Создан класс '{elem.name}'")
        except Exception as e:
            raise Exception(f"Ошибка создания класса: {e}")

    def update_class(self, old_name: str, new_elem: ClassElement) -> None:
        try:
            self.history.push(UpdateClassCommand(self.manager, old_name, new_elem))
            print(f"[EditorModule] Обновлён класс '{old_name}' → '{new_elem.name}'")
        except Exception as e:
            raise Exception(f"Ошибка обновления класса: {e}")

    def delete_class(self, name: str) -> None:
        try:
            self.history.push(DeleteClassCommand(self.manager, name))
            print(f"[EditorModule] Удалён класс '{name}'")
        except Exception as e:
            raise Exception(f"Ошибка удаления класса: {e}")

    # ── Объектные свойства ───────────────────────────────────────────────────

    def create_object_property(self, elem: ObjectPropertyElement) -> None:
        try:
            self.history.push(CreateObjectPropertyCommand(self.manager, elem))
            print(f"[EditorModule] Создано отношение '{elem.name}'")
        except Exception as e:
            raise Exception(f"Ошибка создания отношения: {e}")

    def update_object_property(self, old_name: str, new_elem: ObjectPropertyElement) -> None:
        try:
            self.history.push(UpdateObjectPropertyCommand(self.manager, old_name, new_elem))
            print(f"[EditorModule] Обновлено отношение '{old_name}'")
        except Exception as e:
            raise Exception(f"Ошибка обновления отношения: {e}")

    def delete_object_property(self, name: str) -> None:
        try:
            self.history.push(DeleteObjectPropertyCommand(self.manager, name))
            print(f"[EditorModule] Удалено отношение '{name}'")
        except Exception as e:
            raise Exception(f"Ошибка удаления отношения: {e}")

    # ── Свойства данных ──────────────────────────────────────────────────────

    def create_data_property(self, elem: DataPropertyElement) -> None:
        try:
            self.history.push(CreateDataPropertyCommand(self.manager, elem))
            print(f"[EditorModule] Создано свойство '{elem.name}'")
        except Exception as e:
            raise Exception(f"Ошибка создания свойства: {e}")

    def update_data_property(self, old_name: str, new_elem: DataPropertyElement) -> None:
        try:
            self.history.push(UpdateDataPropertyCommand(self.manager, old_name, new_elem))
            print(f"[EditorModule] Обновлено свойство '{old_name}'")
        except Exception as e:
            raise Exception(f"Ошибка обновления свойства: {e}")

    def delete_data_property(self, name: str) -> None:
        try:
            self.history.push(DeleteDataPropertyCommand(self.manager, name))
            print(f"[EditorModule] Удалено свойство '{name}'")
        except Exception as e:
            raise Exception(f"Ошибка удаления свойства: {e}")

    # ── Индивиды ─────────────────────────────────────────────────────────────

    def create_individual(self, elem: IndividualElement) -> None:
        try:
            self.history.push(CreateIndividualCommand(self.manager, elem))
            print(f"[EditorModule] Создан индивид '{elem.name}'")
        except Exception as e:
            raise Exception(f"Ошибка создания индивида: {e}")

    def update_individual(self, old_name: str, new_elem: IndividualElement) -> None:
        try:
            self.history.push(UpdateIndividualCommand(self.manager, old_name, new_elem))
            print(f"[EditorModule] Обновлён индивид '{old_name}'")
        except Exception as e:
            raise Exception(f"Ошибка обновления индивида: {e}")

    def delete_individual(self, name: str) -> None:
        try:
            self.history.push(DeleteIndividualCommand(self.manager, name))
            print(f"[EditorModule] Удалён индивид '{name}'")
        except Exception as e:
            raise Exception(f"Ошибка удаления индивида: {e}")
