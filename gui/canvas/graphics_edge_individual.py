from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem
from PySide6.QtGui import QPainterPath, QPen, QColor, QFont, QPolygonF
from PySide6.QtCore import Qt, QPointF
import math


class GraphicsEdgeIndividual(QGraphicsPathItem):
    def __init__(self, source_item, target_item, property_name, label=""):
        super().__init__()
        self.source = source_item
        self.target = target_item
        self.property_name = property_name
        self.label_text = label or property_name

        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        self.setZValue(-1)

        # Основной цвет линии (красноватый для объектных свойств индивидов)
        self.default_color = QColor("#e74c3c")
        self.selected_color = QColor("#c0392b")

        self.pen = QPen(self.default_color, 2, Qt.SolidLine)
        self.pen_selected = QPen(self.selected_color, 3, Qt.SolidLine)
        self.setPen(self.pen)

        self.label_item = QGraphicsTextItem(self.label_text, self)
        self.label_item.setDefaultTextColor(QColor("#2c3e50"))
        # Сохранено использование шрифта Roboto, как указано в требованиях к эстетике
        self.label_item.setFont(QFont("Roboto", 10, QFont.Bold))

        # Подписываемся на изменения позиций узлов для перерисовки
        if source_item:
            source_item.scenePosChanged.connect(self.update_position)
        if target_item:
            target_item.scenePosChanged.connect(self.update_position)

        self.update_position()

    def update_position(self):
        if not self.source or not self.target:
            return

        # Получаем центры узлов в координатах сцены
        source_pos = self.source.sceneBoundingRect().center()
        target_pos = self.target.sceneBoundingRect().center()

        # Создаем прямой путь
        path = QPainterPath()
        path.moveTo(source_pos)
        path.lineTo(target_pos)
        self.setPath(path)

        # Подпись посередине. Используем pointAtPercent для надежности, даже на прямой
        mid = path.pointAtPercent(0.5)
        rect = self.label_item.boundingRect()
        # Смещение подписи чуть выше линии, сохраняя логику оригинала (-10)
        self.label_item.setPos(mid - QPointF(rect.width() / 2, rect.height() + 5))

    def paint(self, painter, option, widget=None):
        # Сохраняем базовую логику отрисовки пути
        # self.update_position() # Вызов здесь обычно не нужен, если есть scenePosChanged, но оставляем для надежности

        current_pen = self.pen_selected if self.isSelected() else self.pen
        painter.setPen(current_pen)
        painter.drawPath(self.path())

        # --- ДОБАВЛЕНО: Отрисовка стрелки посередине ---
        path = self.path()
        if path.length() < 5:  # Не рисуем на слишком коротких линиях
            return

        # Берем точку и угол посередине пути
        mid_point = path.pointAtPercent(0.5)
        # Угол в градусах, Qt возвращает угол касательной
        angle_degrees = path.angleAtPercent(0.5)
        # Конвертируем в радианы и инвертируем y для математических расчетов
        angle_rad = math.radians(-angle_degrees)

        # Параметры стрелки
        arrow_size = 10
        # Угол "крыльев" стрелки относительно древки
        wing_angle = math.pi / 6  # 30 градусов

        # Вычисляем точки крыльев стрелки
        p1 = QPointF(mid_point.x() - arrow_size * math.cos(angle_rad - wing_angle),
                     mid_point.y() - arrow_size * math.sin(angle_rad - wing_angle))
        p2 = QPointF(mid_point.x() - arrow_size * math.cos(angle_rad + wing_angle),
                     mid_point.y() - arrow_size * math.sin(angle_rad + wing_angle))

        # Рисуем закрашенную стрелку цветом линии
        painter.setBrush(current_pen.color())
        painter.setPen(Qt.NoPen)  # Без контура
        painter.drawPolygon(QPolygonF([mid_point, p1, p2]))
        # -----------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.ItemSelectedHasChanged:
            self.setPen(self.pen_selected if value else self.pen)
        return super().itemChange(change, value)