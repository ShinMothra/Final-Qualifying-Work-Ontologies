from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QPainterPath, QColor, QPainter, QPolygonF, QFont
import math


class GraphicsEdge(QGraphicsPathItem):
    def __init__(self, from_node, to_node=None, label: str = "", edge_type: str = "related",
                 style: str = "solid", color: str = "#333333", arrow: bool = False):
        super().__init__()
        self.from_node = from_node
        self.to_node = to_node
        self.edge_type = edge_type
        self.arrow_at_end = arrow

        # Индекс для разведения параллельных рёбер (0 - прямо, 1, -1, 2, -2...)
        self.arc_index = 0

        self.label_text = QGraphicsTextItem(label, self)
        self.label_text.setDefaultTextColor(QColor("#333333"))
        self.label_text.setFont(QFont("Roboto", 9))

        self.pen_color = QColor(color)
        pen_style = Qt.SolidLine if style == "solid" else Qt.DashLine if style == "dashed" else Qt.DotLine
        self.default_pen = QPen(self.pen_color, 2, pen_style)
        self._highlighted = False

        if edge_type == "inheritance":
            self.default_pen.setColor(QColor("#0066ff"))
            self.default_pen.setWidth(3)
        elif edge_type == "instance_of":
            self.default_pen.setColor(QColor("#9933ff"))
            self.default_pen.setWidth(2)

        self.setPen(self.default_pen)
        self.setZValue(-10)
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)

        if from_node:
            from_node.scenePosChanged.connect(self.update_path)
        if to_node:
            to_node.scenePosChanged.connect(self.update_path)

        self.update_path()

    def update_path(self):
        if not self.from_node or not self.to_node:
            return

        start = self.from_node.mapToScene(self.from_node.boundingRect().center())
        end = self.to_node.mapToScene(self.to_node.boundingRect().center())

        path = QPainterPath()
        path.moveTo(start)

        # Логика разведения рёбер
        if self.arc_index == 0:
            # Стандартная S-образная кривая для одиночного ребра
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            ctrl1 = QPointF(start.x() + dx * 0.5, start.y())
            ctrl2 = QPointF(start.x() + dx * 0.5, end.y())
            path.cubicTo(ctrl1, ctrl2, end)
        else:
            # Вычисление дуги (квадратичная кривая Безье)
            mid = (start + end) / 2
            # Дистанция выноса (40 пикселей на каждый индекс)
            dist = 50 * self.arc_index

            line_vec = end - start
            length = math.sqrt(line_vec.x() ** 2 + line_vec.y() ** 2)

            if length > 0:
                # Вектор перпендикуляра
                perp = QPointF(-line_vec.y() / length, line_vec.x() / length)
                ctrl = mid + perp * dist
                path.quadTo(ctrl, end)
            else:
                path.lineTo(end)

        self.setPath(path)

        # Обновление позиции подписи
        mid_point = path.pointAtPercent(0.5)
        rect = self.label_text.boundingRect()
        self.label_text.setPos(mid_point.x() - rect.width() / 2, mid_point.y() - rect.height() - 8)

    def set_highlight(self, state: bool):
        self._highlighted = state
        self.update()

    def paint(self, painter: QPainter, option, widget):
        # Отрисовка основной линии
        if self._highlighted:
            painter.setPen(QPen(QColor("#ffcc00"), self.default_pen.width() + 2, Qt.SolidLine))
        elif self.isSelected():
            painter.setPen(QPen(self.pen_color.darker(150), self.default_pen.width() + 1, self.default_pen.style()))
        else:
            painter.setPen(self.default_pen)

        painter.drawPath(self.path())
        current_color = painter.pen().color()
        path = self.path()

        if path.length() < 5:
            return

        # Стрелка посередине
        mid_point = path.pointAtPercent(0.5)
        angle_rad = math.radians(-path.angleAtPercent(0.5))
        mid_arrow_size = 12
        wing_angle = math.pi / 6

        p1_mid = QPointF(mid_point.x() - mid_arrow_size * math.cos(angle_rad - wing_angle),
                         mid_point.y() - mid_arrow_size * math.sin(angle_rad - wing_angle))
        p2_mid = QPointF(mid_point.x() - mid_arrow_size * math.cos(angle_rad + wing_angle),
                         mid_point.y() - mid_arrow_size * math.sin(angle_rad + wing_angle))

        painter.setBrush(current_color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([mid_point, p1_mid, p2_mid]))

        # Стрелка на конце
        if self.arrow_at_end:
            end = path.pointAtPercent(1.0)
            angle_end_rad = math.radians(-path.angleAtPercent(1.0))
            end_arrow_size = 15
            p1_end = QPointF(end.x() - end_arrow_size * math.cos(angle_end_rad - 0.5),
                             end.y() - end_arrow_size * math.sin(angle_end_rad - 0.5))
            p2_end = QPointF(end.x() - end_arrow_size * math.cos(angle_end_rad + 0.5),
                             end.y() - end_arrow_size * math.sin(angle_end_rad + 0.5))
            painter.drawPolygon(QPolygonF([end, p1_end, p2_end]))