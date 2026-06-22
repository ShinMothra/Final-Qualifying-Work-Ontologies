# core/history.py

from typing import Optional


class Command:
    """Базовый класс команды. Все команды наследуются от него."""

    def execute(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return "Действие"


class HistoryManager:
    """
    Менеджер истории изменений.
    Хранит стек выполненных команд и стек отменённых команд.
    """

    def __init__(self, max_size: int = 100):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_size = max_size

    def push(self, command: Command) -> None:
        """Выполняет команду и помещает её в стек отмены."""
        command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)
        # Любое новое действие сбрасывает стек повтора
        self._redo_stack.clear()

    def undo(self) -> Optional[str]:
        """Отменяет последнее действие. Возвращает описание или None."""
        if not self._undo_stack:
            return None
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return command.description

    def redo(self) -> Optional[str]:
        """Повторяет последнее отменённое действие. Возвращает описание или None."""
        if not self._redo_stack:
            return None
        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        return command.description

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo_description(self) -> Optional[str]:
        return self._undo_stack[-1].description if self._undo_stack else None

    def redo_description(self) -> Optional[str]:
        return self._redo_stack[-1].description if self._redo_stack else None

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
