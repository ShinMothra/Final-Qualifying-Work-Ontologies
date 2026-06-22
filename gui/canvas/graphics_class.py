from PySide6.QtWidgets import (
    QGraphicsObject, QGraphicsTextItem, QGraphicsItem,
    QMenu, QGraphicsSceneMouseEvent
)
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QFont, QPen

from modules.formula_module.formula_renderer import render_formula_to_svg_item

BADGE_R = 12

# Пороги LOD (уровень детализации) по масштабу мирового преобразования
LOD_FULL_THRESHOLD = 0.5
LOD_MEDIUM_THRESHOLD = 0.15


class GraphicsClass(QGraphicsObject):
    scenePosChanged = Signal()
    extension_toggle_requested = Signal(str, str)  # (class_name, extension_name)

    def __init__(self, name: str, label: str, pos: tuple, formula: str = "",
                 own_properties: list = None, inherited_properties: list = None,
                 prop_values: dict = None):
        """
        own_properties: список строк — собственные свойства класса
        inherited_properties: список кортежей (str_label, ancestor_name) — унаследованные
        prop_values: dict[str, str] — значения атрибутов {prop_name: value}
        """
        super().__init__()
        self.setPos(pos[0], pos[1])
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        self.name = name
        self.label = label
        self.formula = formula.strip() if formula else ""
        self._own_properties: list[str] = own_properties or []
        self._inherited_properties: list[tuple[str, str]] = inherited_properties or []
        self._prop_values: dict[str, str] = prop_values or {}
        self._highlighted = False
        self._collapsed_extensions: dict[str, bool] = {}
        self._current_lod: str = "full"

        print(f"[GraphicsClass {self.name}] init with formula: '{self.formula}'")

        self.label_text = QGraphicsTextItem(self.label or self.name, self)
        self.label_text.setDefaultTextColor(QColor("black"))
        self.label_text.setFont(QFont("Roboto", 11, QFont.Bold))
        self.label_text.setPos(-self.label_text.boundingRect().width() / 2, -24)

        # SVG-элемент для формулы (инициализируется до _update_property_items,
        # т.к. она вызывает _apply_lod_to_children, читающую formula_svg_item)
        self.formula_svg_item: QGraphicsSvgItem | None = None

        # Текстовые элементы для свойств
        self._prop_text_items: list[QGraphicsTextItem] = []
        self._update_property_items()

        self._update_formula_display()
        self._update_tooltip()

    # ── свойства ─────────────────────────────────────────────────────────────

    def update_properties(self, own_properties: list[str], inherited_properties: list[tuple[str, str]]):
        """Обновляет отображаемые свойства (вызывается извне после изменения онтологии)."""
        self._own_properties = own_properties or []
        self._inherited_properties = inherited_properties or []
        self._update_property_items()
        self.prepareGeometryChange()
        self.update()

    def update_prop_values(self, prop_values: dict[str, str]):
        """Обновляет значения атрибутов и перерисовывает узел."""
        self._prop_values = prop_values or {}
        self._update_property_items()
        self.prepareGeometryChange()
        self.update()

    def _update_property_items(self):
        """Пересоздаёт дочерние QGraphicsTextItem для свойств."""
        for item in self._prop_text_items:
            item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(item)
        self._prop_text_items.clear()

        y = 14  # отступ под заголовком

        # Собственные свойства — обычный шрифт
        for prop_label in self._own_properties:
            value = self._prop_values.get(prop_label)
            full_text = f"• {prop_label}" if not value else f"• {prop_label}:  {value}"
            short_text = f"• {prop_label}"

            ti = QGraphicsTextItem(full_text, self)
            ti.setDefaultTextColor(
                QColor("#1a3a6e") if value else QColor("#1a1a2e")
            )
            font = QFont("Roboto", 8)
            font.setBold(bool(value))
            ti.setFont(font)
            ti.setAcceptedMouseButtons(Qt.NoButton)
            if value:
                ti.setToolTip(f"{prop_label} = {value}")
            ti._lod_full_text = full_text
            ti._lod_short_text = short_text
            self._prop_text_items.append(ti)
            y += 14

        # Унаследованные свойства — курсив, серый; значение если есть
        for prop_label, ancestor_name in self._inherited_properties:
            value = self._prop_values.get(prop_label)
            full_text = f"◦ {prop_label}" if not value else f"◦ {prop_label}:  {value}"
            short_text = f"◦ {prop_label}"

            ti = QGraphicsTextItem(full_text, self)
            ti.setDefaultTextColor(
                QColor("#5566aa") if value else QColor("#888899")
            )
            font = QFont("Roboto", 8)
            font.setItalic(True)
            font.setBold(bool(value))
            ti.setFont(font)
            tooltip = f"Унаследовано от: {ancestor_name}"
            if value:
                tooltip += f"\nЗначение: {value}"
            ti.setToolTip(tooltip)
            ti.setAcceptedMouseButtons(Qt.NoButton)
            ti._lod_full_text = full_text
            ti._lod_short_text = short_text
            self._prop_text_items.append(ti)
            y += 14

        self._reposition_property_items()
        self._apply_lod_to_children()

    def _reposition_property_items(self):
        """Расставляет текстовые элементы свойств по вертикали."""
        max_w = self._props_max_width()
        y = 14
        for ti in self._prop_text_items:
            ti.setPos(-max_w / 2, y)
            y += 16

    def _props_max_width(self) -> float:
        """Ширина самого широкого элемента свойств через QFontMetrics (не через boundingRect QGraphicsTextItem).

        Считается всегда по полному тексту (с значениями), чтобы геометрия узла
        не "плавала" при переключении LOD — меняется только то, что показывается,
        а не место, под него отведённое.
        """
        from PySide6.QtGui import QFontMetrics
        if not self._prop_text_items:
            return 0.0
        max_w = 0.0
        for ti in self._prop_text_items:
            fm = QFontMetrics(ti.font())
            text = getattr(ti, "_lod_full_text", ti.toPlainText())
            # +4 — небольшой запас на субпиксельный рендеринг
            w = fm.horizontalAdvance(text) + 4
            if w > max_w:
                max_w = w
        return max_w

    # ── LOD (уровень детализации) ───────────────────────────────────────────────

    def _lod_for_scale(self, scale: float) -> str:
        if scale >= LOD_FULL_THRESHOLD:
            return "full"
        if scale >= LOD_MEDIUM_THRESHOLD:
            return "medium"
        return "minimal"

    def _apply_lod_to_children(self):
        """Переключает видимость/текст дочерних элементов согласно self._current_lod.

        Геометрия (_base_rect) не пересчитывается здесь намеренно — она всегда
        зарезервирована под полный текст, чтобы не дёргать форму узла при зуме.
        """
        lod = self._current_lod

        # Заголовок: скрыт только на minimal
        self.label_text.setVisible(lod != "minimal")

        # Свойства
        for ti in self._prop_text_items:
            if lod == "minimal":
                ti.setVisible(False)
            elif lod == "medium":
                ti.setVisible(True)
                short_text = getattr(ti, "_lod_short_text", None)
                if short_text is not None and ti.toPlainText() != short_text:
                    ti.setPlainText(short_text)
            else:  # full
                ti.setVisible(True)
                full_text = getattr(ti, "_lod_full_text", None)
                if full_text is not None and ti.toPlainText() != full_text:
                    ti.setPlainText(full_text)

        # Формула: видна только на full
        if self.formula_svg_item:
            self.formula_svg_item.setVisible(lod == "full")

    def _update_lod(self, painter: QPainter):
        """Определяет текущий LOD по масштабу world transform и применяет при изменении."""
        scale = painter.worldTransform().m11()
        new_lod = self._lod_for_scale(scale)
        if new_lod != self._current_lod:
            self._current_lod = new_lod
            self._apply_lod_to_children()

    def _props_total_height(self) -> float:
        if not self._prop_text_items:
            return 0.0
        # n строк по 16px шага + высота последней строки (~14px) вместо ещё одного шага
        return len(self._prop_text_items) * 16 + 2

    # ── формула ──────────────────────────────────────────────────────────────

    def _update_formula_display(self):
        print(f"[GraphicsClass {self.name}] Updating formula display, current: '{self.formula}'")

        if self.formula_svg_item:
            self.formula_svg_item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(self.formula_svg_item)
            self.formula_svg_item = None

        if not self.formula:
            return

        svg_item = render_formula_to_svg_item(
            self.formula,
            font_size=13.0,
            color="#333333",
            max_width=300,
        )

        if svg_item is None:
            print(f"[GraphicsClass {self.name}] SVG render → None")
            return

        svg_item.setParentItem(self)
        svg_item.setAcceptedMouseButtons(Qt.NoButton)
        svg_item.setZValue(0.8)

        # Центрируем под свойствами
        w = svg_item.boundingRect().width() * svg_item.scale()
        formula_y = 14 + self._props_total_height() + 4
        svg_item.setPos(-w / 2, formula_y)

        self.formula_svg_item = svg_item
        print(f"[GraphicsClass {self.name}] SVG item placed, w={w:.1f}")

        self.formula_svg_item.setVisible(self._current_lod == "full")

        self.prepareGeometryChange()
        self.update()

    def _update_tooltip(self):
        parts = []
        if self._own_properties:
            rows = []
            for p in self._own_properties:
                v = self._prop_values.get(p)
                rows.append(f"{p} = {v}" if v else p)
            parts.append("<b>Свойства:</b> " + ", ".join(rows))
        if self._inherited_properties:
            rows = []
            for p, a in self._inherited_properties:
                v = self._prop_values.get(p)
                entry = f"{p} ({a})" + (f" = {v}" if v else "")
                rows.append(entry)
            parts.append("<b>Унаследованные:</b> " + ", ".join(rows))
        if self.formula:
            escaped = self.formula.replace("<", "&lt;").replace(">", "&gt;")
            parts.append(
                f'<b>Формула:</b><br>'
                f'<span style="font-family: monospace; white-space: pre;">{escaped}</span>'
            )
        self.setToolTip("<br>".join(parts) if parts else "")

    def update_formula(self, new_formula: str):
        self.formula = new_formula.strip() if new_formula else ""
        print(f"[GraphicsClass {self.name}] Updated formula to: '{self.formula}'")
        self._update_formula_display()
        self._update_tooltip()
        self.prepareGeometryChange()
        self.update()

    # ── подсветка ─────────────────────────────────────────────────────────────

    def set_highlight(self, state: bool):
        self._highlighted = state
        self.update()

    # ── значок свёрнутых расширений ───────────────────────────────────────────

    def set_extension_collapsed(self, ext_name: str, collapsed: bool):
        if collapsed:
            self._collapsed_extensions[ext_name] = True
        else:
            self._collapsed_extensions.pop(ext_name, None)
        self.prepareGeometryChange()
        self.update()

    def _has_collapsed_extensions(self) -> bool:
        return bool(self._collapsed_extensions)

    def _badge_center(self) -> QPointF:
        r = self._base_rect()
        return QPointF(r.right() - BADGE_R, r.bottom() - BADGE_R)

    def _badge_rect(self) -> QRectF:
        c = self._badge_center()
        return QRectF(c.x() - BADGE_R, c.y() - BADGE_R, BADGE_R * 2, BADGE_R * 2)

    # ── геометрия ─────────────────────────────────────────────────────────────

    def _formula_height(self) -> float:
        if not self.formula_svg_item:
            return 0.0
        return self.formula_svg_item.boundingRect().height() * self.formula_svg_item.scale()

    def _base_rect(self) -> QRectF:
        label_w = self.label_text.boundingRect().width()
        formula_w = 0.0
        if self.formula_svg_item:
            formula_w = self.formula_svg_item.boundingRect().width() * self.formula_svg_item.scale()

        props_w = self._props_max_width()

        w = max(label_w, formula_w, props_w) + 56
        props_h = self._props_total_height()
        fh = self._formula_height()

        # Высота: заголовок (40) + начальный отступ блока свойств (14) + свойства + формула + отступы
        h = 40
        if props_h > 0:
            h += 14 + props_h + 8
        if fh > 0:
            h += fh + 8
        if h < 70:
            h = 70

        return QRectF(-w / 2, -40, w, h)

    def boundingRect(self) -> QRectF:
        r = self._base_rect()
        if self._has_collapsed_extensions():
            return r.adjusted(0, 0, BADGE_R, BADGE_R)
        return r

    # ── отрисовка ─────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget):
        self._update_lod(painter)
        r = self._base_rect()

        if self._highlighted:
            painter.setBrush(QBrush(QColor(255, 230, 100)))
            painter.setPen(QPen(QColor(220, 150, 0), 3))
        else:
            painter.setBrush(QBrush(QColor(200, 230, 255)))
            painter.setPen(QPen(QColor(0, 100, 200), 2))
        painter.drawRoundedRect(r, 20, 20)

        # Разделитель под заголовком, если есть видимые свойства (с учётом LOD)
        if self._prop_text_items and self._current_lod != "minimal":
            sep_y = r.top() + 40
            painter.setPen(QPen(QColor(0, 100, 200, 80), 1, Qt.DashLine))
            painter.drawLine(
                int(r.left() + 12), int(sep_y),
                int(r.right() - 12), int(sep_y)
            )

        if self._has_collapsed_extensions():
            c = self._badge_center()
            br = self._badge_rect()

            painter.setBrush(QBrush(QColor(50, 150, 50)))
            painter.setPen(QPen(QColor(255, 255, 255), 1.5))
            painter.drawEllipse(br)

            painter.setPen(QPen(QColor(255, 255, 255), 2.5))
            painter.drawLine(
                int(c.x() - BADGE_R + 4), int(c.y()),
                int(c.x() + BADGE_R - 4), int(c.y())
            )
            painter.drawLine(
                int(c.x()), int(c.y() - BADGE_R + 4),
                int(c.x()), int(c.y() + BADGE_R - 4)
            )

    # ── события ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if (event.button() == Qt.LeftButton
                and self._has_collapsed_extensions()
                and self._badge_rect().contains(event.pos())):
            event.accept()
            self._show_extensions_menu(event)
            return
        super().mousePressEvent(event)

    def _show_extensions_menu(self, event: QGraphicsSceneMouseEvent):
        menu = QMenu()
        menu.setTitle("Расширения")

        for ext_name in sorted(self._collapsed_extensions.keys()):
            action = menu.addAction(ext_name)
            action.setCheckable(True)
            action.setChecked(False)
            action.triggered.connect(
                lambda checked, n=ext_name: self.extension_toggle_requested.emit(self.name, n)
            )

        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view:
            scene_pos = self.mapToScene(self._badge_center())
            screen_pos = view.mapToGlobal(view.mapFromScene(scene_pos))
            menu.exec(screen_pos)
        else:
            menu.exec(event.screenPos())

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.scenePosChanged.emit()
        return super().itemChange(change, value)