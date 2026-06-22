from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsTextItem, QMenu
from PySide6.QtGui import QPainterPath, QPen, QColor, QPolygonF, QPainter, QFont
from PySide6.QtCore import Qt, QPointF, QRectF

class PolyLineEdge(QGraphicsPathItem):
    WAYPOINT_SIZE = 16

    def __init__(self, from_node, to_node, label="", edge_type="related",
                 style="solid", color="#ff8800", arrow=True):
        super().__init__()
        self.from_node = from_node
        self.to_node = to_node
        self.edge_type = edge_type
        self.arrow = arrow

        # Метка
        self.label_text = QGraphicsTextItem(label, self)
        self.label_text.setDefaultTextColor(QColor("#333333"))
        self.label_text.setFont(QFont("Roboto", 9))

        # Стиль линии
        pen_color = QColor(color)
        pen_style = Qt.SolidLine if style == "solid" else Qt.DashLine
        pen = QPen(pen_color, 2, pen_style)
        if edge_type == "inheritance":
            pen.setColor(QColor("#0066ff"))
            pen.setWidth(3)
        elif edge_type == "instance_of":
            pen.setColor(QColor("#9933ff"))
            pen.setWidth(2)
        self.setPen(pen)
        self.setZValue(-100)

        # Waypoints (минимум 2: начало и конец)
        self.waypoints = [QPointF(0, 0), QPointF(100, 0)]  # относительные
        self.waypoint_items = []

        # Подписки на перемещение узлов
        from_node.scenePosChanged.connect(self.update_path)
        to_node.scenePosChanged.connect(self.update_path)

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)

        self.update_path()

    def mouseDoubleClickEvent(self, event):
        # Двойной клик — добавляем waypoint в месте клика
        pos = event.scenePos()
        path = self.shape()
        if path.contains(pos):
            # Находим ближайший сегмент
            start = self.from_node.mapToScene(self.from_node.boundingRect().center())
            end = self.to_node.mapToScene(self.to_node.boundingRect().center())
            points = [start] + [start + wp for wp in self.waypoints] + [end]
            # Находим ближайшую точку на линии
            closest = None
            min_dist = float('inf')
            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i + 1]
                proj = self.project_point_on_line(pos, p1, p2)
                dist = (proj - pos).manhattanLength()
                if dist < min_dist:
                    min_dist = dist
                    closest = proj
            if closest:
                # Добавляем относительную точку
                rel = closest - start
                self.waypoints.append(rel)
                self.update_path()
        super().mouseDoubleClickEvent(event)

    def project_point_on_line(self, point, a, b):
        ab = b - a
        ap = point - a
        proj = a + ab * (ap.x() * ab.x() + ap.y() * ab.y()) / (ab.x()**2 + ab.y()**2)
        return proj

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction("Удалить точку")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            # Удаляем ближайшую waypoint
            pos = event.scenePos()
            start = self.from_node.mapToScene(self.from_node.boundingRect().center())
            min_dist = float('inf')
            idx = -1
            for i, wp in enumerate(self.waypoints):
                wp_pos = start + wp
                dist = (wp_pos - pos).manhattanLength()
                if dist < min_dist:
                    min_dist = dist
                    idx = i
            if idx >= 0 and len(self.waypoints) > 2:  # оставляем минимум 2
                self.waypoints.pop(idx)
                self.update_path()

    def update_path(self):
        if not self.from_node or not self.to_node:
            return

        start = self.from_node.mapToScene(self.from_node.boundingRect().center())
        end = self.to_node.mapToScene(self.to_node.boundingRect().center())

        path = QPainterPath()
        path.moveTo(start)

        # Удаляем старые ручки
        for item in self.waypoint_items:
            self.scene().removeItem(item)
        self.waypoint_items.clear()

        # Строим путь по waypoints
        points = [start]
        for wp in self.waypoints:
            pt = start + wp
            points.append(pt)
            # Добавляем ручку
            handle = QGraphicsEllipseItem(-self.WAYPOINT_SIZE/2, -self.WAYPOINT_SIZE/2, self.WAYPOINT_SIZE, self.WAYPOINT_SIZE, self)
            handle.setPos(pt)
            handle.setBrush(QColor(255, 80, 80, 220))
            handle.setPen(QPen(QColor(200, 0, 0), 2))
            handle.setFlag(QGraphicsEllipseItem.ItemIsMovable, True)
            handle.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges, True)
            handle.setCursor(Qt.CursorShape.SizeAllCursor)
            handle.setZValue(200)

            def make_handler(index):
                def handler():
                    new_pos = handle.scenePos()
                    self.waypoints[index] = new_pos - start
                    self.update_path()
                return handler
            handle.itemChange = lambda change, value, idx=index: (handler() if change == QGraphicsEllipseItem.ItemPositionHasChanged else value)

            self.waypoint_items.append(handle)

        points.append(end)
        for i in range(1, len(points)):
            path.lineTo(points[i])

        self.setPath(path)

        # Метка посередине
        if self.label_text:
            mid = path.pointAtPercent(0.5)
            rect = self.label_text.boundingRect()
            self.label_text.setPos(mid.x() - rect.width() / 2, mid.y() - rect.height() - 8)

        # Стрелка на конце
        if self.arrow:
            self.paint_arrow()

    def paint(self, painter: QPainter, option, widget):
        super().paint(painter, option, widget)

        if self.arrow:
            path = self.path()
            if path.length() == 0:
                return
            end = path.pointAtPercent(1.0)
            angle = path.angleAtPercent(1.0)

            size = 15
            p1 = QPointF(end.x() - size * QPainterPath().cos(math.radians(angle - 30)), end.y() - size * QPainterPath().sin(math.radians(angle - 30)))
            p2 = QPointF(end.x() - size * QPainterPath().cos(math.radians(angle + 30)), end.y() - size * QPainterPath().sin(math.radians(angle + 30)))

            painter.setBrush(QColor(self.pen().color()))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([end, p1, p2]))

    def save_state(self):
        return {"waypoints": [(wp.x(), wp.y()) for wp in self.waypoints]}

    def load_state(self, data):
        if "waypoints" in data:
            self.waypoints = [QPointF(x, y) for x, y in data["waypoints"]]
        self.update_path()
