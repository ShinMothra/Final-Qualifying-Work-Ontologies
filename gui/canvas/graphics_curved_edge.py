from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem
from PySide6.QtGui import QPen, QColor, QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF
from .graphics_edge import GraphicsEdge


class CurvedEdge(GraphicsEdge):
    """Ребро с возможностью ручного искривления через контрольную точку"""

    def __init__(self, from_node, to_node, label="", edge_type="related",
                 style="solid", color="#ff8800", arrow=True):
        super().__init__(from_node, to_node, label, edge_type, style, color, arrow)

        self.handle = QGraphicsEllipseItem(-10, -10, 20, 20, self)
        self.handle.setBrush(QColor(255, 100, 100, 200))
        self.handle.setPen(QPen(QColor(200, 0, 0), 2))
        self.handle.setFlag(QGraphicsEllipseItem.ItemIsMovable, True)
        self.handle.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges, True)
        self.handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self.handle.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        self.handle.setZValue(100)

        self.handle_offset = QPointF(0, -100)

        # Переопределяем itemChange для ручки
        self.handle.itemChange = self.handle_moved
        self.update_handle_pos()

    def update_handle_pos(self):
        """Обновляет позицию ручки на основе центров узлов и сохраненного смещения"""
        if not self.from_node or not self.to_node:
            return
        # Сохранено: использование центров узлов
        start = self.from_node.mapToScene(self.from_node.boundingRect().center())
        end = self.to_node.mapToScene(self.to_node.boundingRect().center())
        mid = (start + end) / 2

        # Блокируем сигналы, чтобы избежать рекурсии при программной установке позиции
        self.handle.blockSignals(True)
        self.handle.setPos(mid + self.handle_offset)
        self.handle.blockSignals(False)

    def handle_moved(self, change, value):
        """Реагирует на перетаскивание ручки пользователем"""
        if change == QGraphicsEllipseItem.ItemPositionHasChanged:
            # Ручка двигается в координатах Parent (этого ребра).
            # pos() ручки - это и есть абсолютная позиция на сцене, так как ребро в (0,0)

            if self.from_node and self.to_node:
                start = self.from_node.mapToScene(self.from_node.boundingRect().center())
                end = self.to_node.mapToScene(self.to_node.boundingRect().center())
                mid = (start + end) / 2

                # Вычисляем новое смещение относительно текущей середины
                # value - это новая позиция (QPointF)
                self.handle_offset = value - mid
                self.update_path()  # Перерисовываем кривую
        return super(QGraphicsEllipseItem, self.handle).itemChange(change, value)

    def update_path(self):
        """Переопределяет создание пути: использует quadTo через контрольную точку"""
        if not self.from_node or not self.to_node:
            return

        start = self.from_node.mapToScene(self.from_node.boundingRect().center())
        end = self.to_node.mapToScene(self.to_node.boundingRect().center())

        ctrl = self.handle.pos()

        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(ctrl, end)

        self.setPath(path)
        self.update_handle_pos()

        mid_on_path = path.pointAtPercent(0.5)
        rect = self.label_text.boundingRect()
        self.label_text.setPos(mid_on_path.x() - rect.width() / 2, mid_on_path.y() - rect.height() - 8)

    def save_state(self):
        """Возвращает данные для сохранения в layout.json"""
        return {
            "offset_x": self.handle_offset.x(),
            "offset_y": self.handle_offset.y()
        }

    def load_state(self, data):
        """Восстанавливает изгиб из layout.json"""
        if not data: return
        self.handle_offset = QPointF(data.get("offset_x", 0), data.get("offset_y", -100))
        self.update_handle_pos()
        self.update_path()