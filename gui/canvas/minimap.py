"""
gui/canvas/minimap.py

Мини-карта онтологии — overlay поверх OntologyView.

Использование в main_window.py (внутри setup_editor, после создания scene_view):

    from gui.canvas.minimap import MiniMap
    self.minimap = MiniMap(self.scene_view, self.canvas_frame)
    self.minimap.attach()
"""

import logging
from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QRectF, QPointF, QRect, QPoint
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath,
    QMouseEvent, QResizeEvent, QFont, QFontMetrics
)

logger = logging.getLogger(__name__)

# ── Настройки внешнего вида ───────────────────────────────────────────────────

_MM_WIDTH       = 200          # ширина мини-карты в пикселях
_MM_HEIGHT      = 140          # высота
_MM_MARGIN      = 12           # отступ от угла canvas
_MM_PADDING     = 8            # внутренние отступы до содержимого

_COLOR_BG        = QColor(24, 24, 32, 210)        # фон мини-карты
_COLOR_BORDER    = QColor(80, 80, 110, 200)        # рамка
_COLOR_NODE_CLS  = QColor(70, 130, 200, 200)       # классы
_COLOR_NODE_IND  = QColor(120, 70, 190, 200)       # индивиды
_COLOR_EDGE      = QColor(150, 150, 170, 100)      # рёбра
_COLOR_VP_FILL   = QColor(255, 255, 255, 25)       # заливка viewport-прямоугольника
_COLOR_VP_BORDER = QColor(255, 220, 80, 200)       # рамка viewport-прямоугольника
_COLOR_HANDLE    = QColor(255, 220, 80, 160)       # угловой маркер (drag)
_COLOR_LABEL_CLS = QColor(180, 210, 255, 220)      # подписи классов
_COLOR_LABEL_IND = QColor(200, 170, 255, 200)      # подписи индивидов

# Минимальное расстояние между соседними узлами в px на мини-карте,
# при котором начинают рисоваться подписи имён
_LABEL_MIN_SPREAD = 18


class MiniMap(QWidget):
    """
    Полупрозрачный overlay, отображающий граф в уменьшенном виде.

    Viewport главного QGraphicsView показан жёлтым прямоугольником;
    его можно перетаскивать мышью для навигации по графу.
    """

    def __init__(self, view, parent: QWidget):
        """
        Parameters
        ----------
        view   : OntologyView  — основной QGraphicsView
        parent : QWidget       — виджет-контейнер canvas (canvas_frame),
                                 к нему прикреплён overlay
        """
        super().__init__(parent)
        self._view   = view
        self._scene  = view.scene()

        # Состояние перетаскивания viewport-прямоугольника
        self._dragging      = False
        self._drag_start_mm = QPointF()   # точка нажатия в координатах мини-карты
        self._drag_start_sc = QPointF()   # соответствующая точка в координатах сцены

        # Кэш узлов для tooltip: список (mm_pt, name, node_type)
        # заполняется в paintEvent, читается в mouseMoveEvent
        self._node_cache: list[tuple[QPointF, str, str]] = []

        self.setFixedSize(_MM_WIDTH, _MM_HEIGHT)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Перерисовка при любом изменении сцены
        self._scene.changed.connect(self._on_scene_changed)

    # ── Публичный интерфейс ───────────────────────────────────────────────────

    def attach(self):
        """Показывает мини-карту и позиционирует её в правом нижнем углу."""
        self._reposition()
        self.show()
        self.raise_()

    def detach(self):
        """Скрывает мини-карту."""
        self.hide()

    def update_scene(self, scene):
        """Переключиться на новую сцену (например, после открытия другого файла)."""
        if self._scene:
            try:
                self._scene.changed.disconnect(self._on_scene_changed)
            except RuntimeError:
                pass
        self._scene = scene
        self._view  = scene.views()[0] if scene.views() else self._view
        self._scene.changed.connect(self._on_scene_changed)
        self.update()

    # ── Позиционирование ─────────────────────────────────────────────────────

    def _reposition(self):
        """Прижимает мини-карту к правому нижнему углу родительского виджета."""
        p = self.parent()
        if p is None:
            return
        x = p.width()  - _MM_WIDTH  - _MM_MARGIN
        y = p.height() - _MM_HEIGHT - _MM_MARGIN
        self.move(x, y)

    # ── Вычисление трансформации сцена → мини-карта ──────────────────────────

    def _scene_rect(self) -> QRectF:
        """Bounding rect всех элементов сцены (или sceneRect если пусто)."""
        r = self._scene.itemsBoundingRect()
        if r.isNull() or r.isEmpty():
            r = self._scene.sceneRect()
        return r.adjusted(-50, -50, 50, 50)

    def _mm_content_rect(self) -> QRect:
        """Область внутри мини-карты, доступная для рисования (с отступами)."""
        return QRect(
            _MM_PADDING,
            _MM_PADDING,
            _MM_WIDTH  - 2 * _MM_PADDING,
            _MM_HEIGHT - 2 * _MM_PADDING,
        )

    def _scene_to_mm(self, scene_pt: QPointF) -> QPointF:
        """Перевод точки из координат сцены в координаты мини-карты."""
        sr  = self._scene_rect()
        cr  = self._mm_content_rect()
        if sr.width() == 0 or sr.height() == 0:
            return QPointF(cr.x(), cr.y())
        sx = (scene_pt.x() - sr.x()) / sr.width()
        sy = (scene_pt.y() - sr.y()) / sr.height()
        return QPointF(
            cr.x() + sx * cr.width(),
            cr.y() + sy * cr.height(),
        )

    def _mm_to_scene(self, mm_pt: QPointF) -> QPointF:
        """Перевод точки из координат мини-карты в координаты сцены."""
        sr = self._scene_rect()
        cr = self._mm_content_rect()
        if cr.width() == 0 or cr.height() == 0:
            return QPointF(sr.x(), sr.y())
        sx = (mm_pt.x() - cr.x()) / cr.width()
        sy = (mm_pt.y() - cr.y()) / cr.height()
        return QPointF(
            sr.x() + sx * sr.width(),
            sr.y() + sy * sr.height(),
        )

    def _viewport_scene_rect(self) -> QRectF:
        """Прямоугольник видимой области главного view в координатах сцены."""
        vp   = self._view.viewport().rect()
        tl   = self._view.mapToScene(vp.topLeft())
        br   = self._view.mapToScene(vp.bottomRight())
        return QRectF(tl, br)

    # ── Отрисовка ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Фон и рамка
        painter.setPen(QPen(_COLOR_BORDER, 1))
        painter.setBrush(QBrush(_COLOR_BG))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

        scene = self._scene
        if not scene:
            return

        painter.save()
        painter.setClipRect(self._mm_content_rect())

        # Рёбра
        pen_edge = QPen(_COLOR_EDGE, 0.8)
        painter.setPen(pen_edge)
        painter.setBrush(Qt.NoBrush)
        for item in scene.items():
            if hasattr(item, 'path') and hasattr(item, 'from_node') and hasattr(item, 'to_node'):
                if not item.isVisible():
                    continue
                if item.from_node and item.to_node:
                    p1 = self._scene_to_mm(
                        item.from_node.mapToScene(item.from_node.boundingRect().center())
                    )
                    p2 = self._scene_to_mm(
                        item.to_node.mapToScene(item.to_node.boundingRect().center())
                    )
                    painter.drawLine(p1, p2)

        # Собираем узлы и заполняем кэш для tooltip
        cls_nodes: list = []   # (mm_pt, name)
        ind_nodes: list = []
        new_cache: list = []   # (mm_pt, name, node_type)

        for item in scene.items():
            if not item.isVisible():
                continue
            cls_name = item.__class__.__name__
            if hasattr(item, 'name') and cls_name == 'GraphicsClass':
                center = item.mapToScene(item.boundingRect().center())
                mm_pt  = self._scene_to_mm(center)
                cls_nodes.append((mm_pt, item.name))
                new_cache.append((mm_pt, item.name, 'class'))
            elif hasattr(item, 'name') and cls_name == 'GraphicsIndividual':
                center = item.mapToScene(item.boundingRect().center())
                mm_pt  = self._scene_to_mm(center)
                ind_nodes.append((mm_pt, item.name))
                new_cache.append((mm_pt, item.name, 'individual'))

        self._node_cache = new_cache

        # Решаем, показывать ли подписи (достаточно ли места)
        show_labels = self._should_show_labels(cls_nodes)

        label_font = QFont()
        label_font.setPointSize(5)
        label_font.setWeight(QFont.Weight.Medium)
        painter.setFont(label_font)
        fm = QFontMetrics(label_font)

        # Рисуем классы
        for mm_pt, name in cls_nodes:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(_COLOR_NODE_CLS))
            painter.drawEllipse(mm_pt, 4, 4)
            if show_labels:
                self._draw_node_label(painter, fm, mm_pt, name, _COLOR_LABEL_CLS, radius=4)

        # Рисуем индивиды
        for mm_pt, name in ind_nodes:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(_COLOR_NODE_IND))
            painter.drawEllipse(mm_pt, 3, 3)
            if show_labels:
                self._draw_node_label(painter, fm, mm_pt, name, _COLOR_LABEL_IND, radius=3)

        painter.restore()

        # Viewport-прямоугольник
        vp_scene = self._viewport_scene_rect()
        tl = self._scene_to_mm(vp_scene.topLeft())
        br = self._scene_to_mm(vp_scene.bottomRight())
        vp_mm = QRectF(tl, br)

        painter.setPen(QPen(_COLOR_VP_BORDER, 1.5))
        painter.setBrush(QBrush(_COLOR_VP_FILL))
        painter.drawRect(vp_mm)

        # Маленький маркер в правом нижнем углу прямоугольника (подсказка drag)
        handle_size = 6
        hx = min(br.x() - handle_size / 2, _MM_WIDTH  - handle_size)
        hy = min(br.y() - handle_size / 2, _MM_HEIGHT - handle_size)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(_COLOR_HANDLE))
        painter.drawEllipse(QPointF(hx, hy), handle_size / 2, handle_size / 2)

        painter.end()

    # ── Вспомогательные методы отрисовки ────────────────────────────────────

    def _should_show_labels(self, cls_nodes: list) -> bool:
        """
        Возвращает True если узлы достаточно разрежены для отображения подписей.
        Критерий: минимальное расстояние между любыми двумя классами >= _LABEL_MIN_SPREAD.
        При числе узлов <= 1 подписи показываются всегда.
        """
        if len(cls_nodes) <= 1:
            return True
        pts = [pt for pt, _ in cls_nodes]
        min_dist_sq = float('inf')
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dx = pts[i].x() - pts[j].x()
                dy = pts[i].y() - pts[j].y()
                d2 = dx * dx + dy * dy
                if d2 < min_dist_sq:
                    min_dist_sq = d2
        return min_dist_sq >= _LABEL_MIN_SPREAD ** 2

    def _draw_node_label(
        self,
        painter: QPainter,
        fm: QFontMetrics,
        mm_pt: QPointF,
        name: str,
        color: QColor,
        radius: int,
    ):
        """Рисует подпись имени узла под точкой mm_pt, усекая длинные имена."""
        max_chars = 12
        label = name if len(name) <= max_chars else name[:max_chars - 1] + "…"

        text_w = fm.horizontalAdvance(label)
        text_h = fm.height()

        x = mm_pt.x() - text_w / 2
        y = mm_pt.y() + radius + 1          # сразу под точкой узла

        # Ограничиваем выход за границы мини-карты
        cr = self._mm_content_rect()
        x = max(cr.left(), min(x, cr.right()  - text_w))
        y = max(cr.top(),  min(y, cr.bottom() - text_h))

        painter.setPen(color)
        painter.drawText(QPointF(x, y + text_h - fm.descent()), label)

    # ── Навигация мышью ──────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging      = True
            mm_pt               = QPointF(event.position())
            self._drag_start_mm = mm_pt
            self._drag_start_sc = self._viewport_scene_rect().center()
            self._navigate_to(mm_pt)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        mm_pt = QPointF(event.position())

        # Tooltip: ищем ближайший узел в кэше
        hit_name = self._hit_test(mm_pt)
        if hit_name:
            QToolTip.showText(event.globalPosition().toPoint(), hit_name, self)
        else:
            QToolTip.hideText()

        if self._dragging:
            self._navigate_to(mm_pt)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()

    def _hit_test(self, mm_pt: QPointF, radius: float = 7.0) -> str | None:
        """
        Возвращает имя узла из _node_cache, ближайшего к mm_pt в пределах radius px.
        Если таких нет — None.
        """
        best_name = None
        best_d2   = radius * radius
        for pt, name, _ in self._node_cache:
            dx = mm_pt.x() - pt.x()
            dy = mm_pt.y() - pt.y()
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2   = d2
                best_name = name
        return best_name

    def _navigate_to(self, mm_pt: QPointF):
        """Центрирует главный view на точке сцены, соответствующей mm_pt."""
        scene_center = self._mm_to_scene(mm_pt)
        self._view.centerOn(scene_center)
        self.update()

    # ── Слоты ────────────────────────────────────────────────────────────────

    def _on_scene_changed(self, _region=None):
        self.update()

    # ── Системные события ─────────────────────────────────────────────────────

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._reposition()

    def parentResizeEvent(self):
        """Вызвать из canvas_frame.resizeEvent если нужна реакция на изменение размера."""
        self._reposition()
        