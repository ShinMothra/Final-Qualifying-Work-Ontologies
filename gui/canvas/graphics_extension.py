from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QGraphicsTextItem
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPainterPath


PADDING = 30
HEADER_HEIGHT = 28
COLLAPSE_SIZE = 18


class GraphicsExtension(QGraphicsObject):
    """
    Визуальная рамка-группировка для подклассов одного расширения.
    При сворачивании полностью скрывается вместе с узлами.
    Сигнал collapse_requested эмитируется при нажатии кнопки «−».
    """
    collapse_requested = Signal(str)   # (extension_name,) — запрос на сворачивание

    COLORS = [
        QColor(100, 180, 100, 40),
        QColor(180, 100, 180, 40),
        QColor(180, 160, 60,  40),
        QColor(60,  160, 180, 40),
        QColor(180, 80,  80,  40),
        QColor(80,  120, 180, 40),
    ]
    BORDER_COLORS = [
        QColor(60,  140, 60,  180),
        QColor(140, 60,  140, 180),
        QColor(160, 130, 30,  180),
        QColor(30,  130, 160, 180),
        QColor(160, 50,  50,  180),
        QColor(50,  90,  160, 180),
    ]

    def __init__(self, extension_name: str, color_index: int = 0):
        super().__init__()
        self.extension_name = extension_name
        self.color_index = color_index % len(self.COLORS)
        self._rect = QRectF(0, 0, 200, 100)

        self.setZValue(1)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)

        self._label = QGraphicsTextItem(extension_name, self)
        self._label.setFont(QFont("Roboto", 9, QFont.Bold))
        self._label.setDefaultTextColor(
            self.BORDER_COLORS[self.color_index].darker(130)
        )
        self._label.setPos(PADDING, 4)
        self._label.setZValue(2)

    def update_from_nodes(self, node_items: list):
        """Пересчитывает рамку по текущим позициям узлов."""
        if not node_items:
            return

        min_x = min(item.scenePos().x() + item.boundingRect().left()  for item in node_items)
        min_y = min(item.scenePos().y() + item.boundingRect().top()   for item in node_items)
        max_x = max(item.scenePos().x() + item.boundingRect().right() for item in node_items)
        max_y = max(item.scenePos().y() + item.boundingRect().bottom() for item in node_items)

        self.prepareGeometryChange()
        self._rect = QRectF(
            0, 0,
            (max_x - min_x) + PADDING * 2,
            (max_y - min_y) + PADDING * 2 + HEADER_HEIGHT
        )
        self.setPos(min_x - PADDING, min_y - PADDING - HEADER_HEIGHT)
        self._label.setPos(PADDING, 4)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._rect.width(), self._rect.height())

    def paint(self, painter: QPainter, option, widget):
        fill   = self.COLORS[self.color_index]
        border = self.BORDER_COLORS[self.color_index]

        # Основная рамка
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 1.5, Qt.DashLine))
        painter.drawRoundedRect(self.boundingRect(), 12, 12)

        # Полоска заголовка
        header_color = QColor(border)
        header_color.setAlpha(50)
        painter.setBrush(QBrush(header_color))
        painter.setPen(Qt.NoPen)

        w = self._rect.width()
        h = HEADER_HEIGHT + 8
        path = QPainterPath()
        path.moveTo(12, 0)
        path.lineTo(w - 12, 0)
        path.quadTo(w, 0, w, 12)
        path.lineTo(w, h)
        path.lineTo(0, h)
        path.lineTo(0, 12)
        path.quadTo(0, 0, 12, 0)
        painter.drawPath(path)

        # Кнопка «−»
        btn_x   = w - COLLAPSE_SIZE - 8
        btn_y   = (HEADER_HEIGHT - COLLAPSE_SIZE) / 2 + 2
        btn_rect = QRectF(btn_x, btn_y, COLLAPSE_SIZE, COLLAPSE_SIZE)

        painter.setBrush(QBrush(QColor(255, 255, 255, 120)))
        painter.setPen(QPen(border, 1.5))
        painter.drawRoundedRect(btn_rect, 4, 4)

        painter.setPen(QPen(border.darker(150), 2))
        cy = btn_y + COLLAPSE_SIZE / 2
        painter.drawLine(
            int(btn_x + 4), int(cy),
            int(btn_x + COLLAPSE_SIZE - 4), int(cy)
        )

    def mousePressEvent(self, event):
        btn_x    = self._rect.width() - COLLAPSE_SIZE - 8
        btn_y    = (HEADER_HEIGHT - COLLAPSE_SIZE) / 2 + 2
        btn_rect = QRectF(btn_x, btn_y, COLLAPSE_SIZE, COLLAPSE_SIZE)

        if btn_rect.contains(event.pos()):
            event.accept()
            self.collapse_requested.emit(self.extension_name)
        else:
            super().mousePressEvent(event)
