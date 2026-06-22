from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem, QGraphicsTextItem
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtGui import QPainterPath, QFont, QColor, QBrush, QPen
from PySide6.QtCore import QRectF, Signal, Qt

from modules.formula_module.formula_renderer import render_formula_to_svg_item

# Пороги LOD (уровень детализации) по масштабу мирового преобразования
LOD_FULL_THRESHOLD = 0.5
LOD_MEDIUM_THRESHOLD = 0.15


class GraphicsIndividual(QGraphicsObject):
    scenePosChanged = Signal()

    def __init__(self, name: str, label: str, parent=None, formula: str = ""):
        super().__init__(parent)
        self.name = name
        self.label = label
        self.formula = formula.strip() if formula else ""
        self._highlighted = False
        self._current_lod = "full"

        print(f"[GraphicsIndividual {self.name}] init with formula: '{self.formula}'")

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(12)

        self.text = QGraphicsTextItem(self.label or self.name, self)
        self.text.setFont(QFont("Roboto", 10, QFont.Bold))
        self.text.setDefaultTextColor(QColor("white"))
        self.text.setPos(10, 6)

        # SVG-элемент для формулы
        self.formula_svg_item: QGraphicsSvgItem | None = None
        self._update_formula_display()
        self._update_tooltip()

    # ── формула ──────────────────────────────────────────────────────────────

    def _update_formula_display(self):
        print(f"[GraphicsIndividual {self.name}] Updating formula, current: '{self.formula}'")

        if self.formula_svg_item:
            self.formula_svg_item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(self.formula_svg_item)
            self.formula_svg_item = None

        if not self.formula:
            print(f"[GraphicsIndividual {self.name}] No formula")
            return

        svg_item = render_formula_to_svg_item(
            self.formula,
            font_size=11.0,
            color="#e8f0ff",
            max_width=240,
        )

        if svg_item is None:
            print(f"[GraphicsIndividual {self.name}] SVG render → None")
            return

        svg_item.setParentItem(self)
        svg_item.setAcceptedMouseButtons(Qt.NoButton)
        svg_item.setZValue(1.0)
        svg_item.setPos(10, 28)

        self.formula_svg_item = svg_item
        print(f"[GraphicsIndividual {self.name}] SVG item placed")

        self.formula_svg_item.setVisible(self._current_lod == "full")

        self.prepareGeometryChange()
        self.update()

    def _update_tooltip(self):
        if self.formula:
            escaped = self.formula.replace("<", "&lt;").replace(">", "&gt;")
            self.setToolTip(
                f'<b>Формула:</b><br>'
                f'<span style="font-family: monospace; white-space: pre;">{escaped}</span>'
            )
        else:
            self.setToolTip("")

    def update_formula(self, new_formula: str):
        self.formula = new_formula.strip() if new_formula else ""
        print(f"[GraphicsIndividual {self.name}] Updated formula to: '{self.formula}'")
        self._update_formula_display()
        self._update_tooltip()
        self.prepareGeometryChange()
        self.update()

    # ── подсветка ─────────────────────────────────────────────────────────────

    def set_highlight(self, state: bool):
        self._highlighted = state
        self.update()

    # ── геометрия ─────────────────────────────────────────────────────────────

    def _formula_height(self) -> float:
        if not self.formula_svg_item:
            return 0.0
        return self.formula_svg_item.boundingRect().height() * self.formula_svg_item.scale()

    def _formula_width(self) -> float:
        if not self.formula_svg_item:
            return 0.0
        return self.formula_svg_item.boundingRect().width() * self.formula_svg_item.scale()

    def boundingRect(self):
        text_w = self.text.boundingRect().width()
        formula_w = self._formula_width()
        w = max(text_w, formula_w) + 24
        fh = self._formula_height()
        h = 28 + fh + 10 if fh > 0 else 44
        return QRectF(0, 0, w, h)

    # ── LOD (уровень детализации) ───────────────────────────────────────────────

    def _lod_for_scale(self, scale: float) -> str:
        if scale >= LOD_FULL_THRESHOLD:
            return "full"
        if scale >= LOD_MEDIUM_THRESHOLD:
            return "medium"
        return "minimal"

    def _apply_lod_to_children(self):
        lod = self._current_lod

        # Заголовок: скрыт только на minimal
        self.text.setVisible(lod != "minimal")

        # Формула: видна только на full
        if self.formula_svg_item:
            self.formula_svg_item.setVisible(lod == "full")

    def _update_lod(self, painter):
        scale = painter.worldTransform().m11()
        new_lod = self._lod_for_scale(scale)
        if new_lod != self._current_lod:
            self._current_lod = new_lod
            self._apply_lod_to_children()

    # ── отрисовка ─────────────────────────────────────────────────────────────

    def paint(self, painter, option, widget):
        self._update_lod(painter)
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 12, 12)
        if self._highlighted:
            painter.setBrush(QBrush(QColor(255, 220, 80, 230)))
            painter.setPen(QPen(QColor(200, 130, 0), 3))
        else:
            painter.setBrush(QBrush(QColor(100, 180, 255, 220)))
            painter.setPen(QPen(QColor(0, 100, 200), 2))
        painter.drawPath(path)

    # ── события ───────────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change in (QGraphicsItem.ItemPositionHasChanged, QGraphicsItem.ItemParentHasChanged):
            self.scenePosChanged.emit()
        return super().itemChange(change, value)