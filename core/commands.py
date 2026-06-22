# core/commands.py

import copy
from .history import Command
from .model.ontology import OntologyManager
from .model.elements import (
    ClassElement, ObjectPropertyElement,
    DataPropertyElement, IndividualElement
)


# ══════════════════════════════════════════════════════════════════════════════
# Классы
# ══════════════════════════════════════════════════════════════════════════════

class CreateClassCommand(Command):
    def __init__(self, manager: OntologyManager, elem: ClassElement):
        self._manager = manager
        self._elem = elem

    @property
    def description(self) -> str:
        return f"Создать класс «{self._elem.name}»"

    def execute(self) -> None:
        self._manager.create_class(self._elem)
        if self._elem.formula:
            self._manager.set_formula(self._elem.name, self._elem.formula)

    def undo(self) -> None:
        self._manager.delete_class(self._elem.name)


class UpdateClassCommand(Command):
    def __init__(self, manager: OntologyManager, old_name: str, new_elem: ClassElement):
        self._manager = manager
        self._old_name = old_name
        self._new_elem = new_elem
        # Сохраняем снимок старого состояния для отмены
        old = manager.classes.get(old_name)
        self._old_elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Изменить класс «{self._old_name}»"

    def execute(self) -> None:
        self._manager.update_class(self._old_name, self._new_elem)
        if self._new_elem.formula is not None:
            self._manager.set_formula(self._new_elem.name, self._new_elem.formula)

    def undo(self) -> None:
        if self._old_elem is None:
            return
        # Откатываем к старому состоянию
        self._manager.update_class(self._new_elem.name, self._old_elem)
        if self._old_elem.formula is not None:
            self._manager.set_formula(self._old_elem.name, self._old_elem.formula)


class DeleteClassCommand(Command):
    def __init__(self, manager: OntologyManager, name: str):
        self._manager = manager
        self._name = name
        old = manager.classes.get(name)
        self._elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Удалить класс «{self._name}»"

    def execute(self) -> None:
        self._manager.delete_class(self._name)

    def undo(self) -> None:
        if self._elem is None:
            return
        self._manager.create_class(self._elem)
        if self._elem.formula:
            self._manager.set_formula(self._elem.name, self._elem.formula)


# ══════════════════════════════════════════════════════════════════════════════
# Объектные свойства
# ══════════════════════════════════════════════════════════════════════════════

class CreateObjectPropertyCommand(Command):
    def __init__(self, manager: OntologyManager, elem: ObjectPropertyElement):
        self._manager = manager
        self._elem = elem

    @property
    def description(self) -> str:
        return f"Создать отношение «{self._elem.name}»"

    def execute(self) -> None:
        self._manager.create_object_property(self._elem)

    def undo(self) -> None:
        self._manager.delete_object_property(self._elem.name)


class UpdateObjectPropertyCommand(Command):
    def __init__(self, manager: OntologyManager, old_name: str, new_elem: ObjectPropertyElement):
        self._manager = manager
        self._old_name = old_name
        self._new_elem = new_elem
        old = manager.object_properties.get(old_name)
        self._old_elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Изменить отношение «{self._old_name}»"

    def execute(self) -> None:
        self._manager.update_object_property(self._old_name, self._new_elem)

    def undo(self) -> None:
        if self._old_elem is None:
            return
        self._manager.update_object_property(self._new_elem.name, self._old_elem)


class DeleteObjectPropertyCommand(Command):
    def __init__(self, manager: OntologyManager, name: str):
        self._manager = manager
        self._name = name
        old = manager.object_properties.get(name)
        self._elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Удалить отношение «{self._name}»"

    def execute(self) -> None:
        self._manager.delete_object_property(self._name)

    def undo(self) -> None:
        if self._elem:
            self._manager.create_object_property(self._elem)


# ══════════════════════════════════════════════════════════════════════════════
# Свойства данных
# ══════════════════════════════════════════════════════════════════════════════

class CreateDataPropertyCommand(Command):
    def __init__(self, manager: OntologyManager, elem: DataPropertyElement):
        self._manager = manager
        self._elem = elem

    @property
    def description(self) -> str:
        return f"Создать свойство «{self._elem.name}»"

    def execute(self) -> None:
        self._manager.create_data_property(self._elem)

    def undo(self) -> None:
        self._manager.delete_data_property(self._elem.name)


class UpdateDataPropertyCommand(Command):
    def __init__(self, manager: OntologyManager, old_name: str, new_elem: DataPropertyElement):
        self._manager = manager
        self._old_name = old_name
        self._new_elem = new_elem
        old = manager.data_properties.get(old_name)
        self._old_elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Изменить свойство «{self._old_name}»"

    def execute(self) -> None:
        self._manager.update_data_property(self._old_name, self._new_elem)

    def undo(self) -> None:
        if self._old_elem is None:
            return
        self._manager.update_data_property(self._new_elem.name, self._old_elem)


class DeleteDataPropertyCommand(Command):
    def __init__(self, manager: OntologyManager, name: str):
        self._manager = manager
        self._name = name
        old = manager.data_properties.get(name)
        self._elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Удалить свойство «{self._name}»"

    def execute(self) -> None:
        self._manager.delete_data_property(self._name)

    def undo(self) -> None:
        if self._elem:
            self._manager.create_data_property(self._elem)


# ══════════════════════════════════════════════════════════════════════════════
# Индивиды
# ══════════════════════════════════════════════════════════════════════════════

class CreateIndividualCommand(Command):
    def __init__(self, manager: OntologyManager, elem: IndividualElement):
        self._manager = manager
        self._elem = elem

    @property
    def description(self) -> str:
        return f"Создать индивида «{self._elem.name}»"

    def execute(self) -> None:
        self._manager.create_individual(self._elem)
        if self._elem.formula:
            self._manager.set_formula(self._elem.name, self._elem.formula)

    def undo(self) -> None:
        self._manager.delete_individual(self._elem.name)


class UpdateIndividualCommand(Command):
    def __init__(self, manager: OntologyManager, old_name: str, new_elem: IndividualElement):
        self._manager = manager
        self._old_name = old_name
        self._new_elem = new_elem
        old = manager.individuals.get(old_name)
        self._old_elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Изменить индивида «{self._old_name}»"

    def execute(self) -> None:
        self._manager.update_individual(self._old_name, self._new_elem)
        if self._new_elem.formula is not None:
            self._manager.set_formula(self._new_elem.name, self._new_elem.formula)

    def undo(self) -> None:
        if self._old_elem is None:
            return
        self._manager.update_individual(self._new_elem.name, self._old_elem)
        if self._old_elem.formula is not None:
            self._manager.set_formula(self._old_elem.name, self._old_elem.formula)


class DeleteIndividualCommand(Command):
    def __init__(self, manager: OntologyManager, name: str):
        self._manager = manager
        self._name = name
        old = manager.individuals.get(name)
        self._elem = copy.copy(old) if old else None

    @property
    def description(self) -> str:
        return f"Удалить индивида «{self._name}»"

    def execute(self) -> None:
        self._manager.delete_individual(self._name)

    def undo(self) -> None:
        if self._elem:
            self._manager.create_individual(self._elem)
            if self._elem.formula:
                self._manager.set_formula(self._elem.name, self._elem.formula)
