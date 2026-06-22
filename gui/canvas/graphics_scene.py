from PySide6.QtGui import QWheelEvent, QPainter, QPen, QColor, QPainterPath
from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QInputDialog, QMessageBox,
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsTextItem
)
from core.model.ontology import OntologyManager
from .graphics_class import GraphicsClass
from .graphics_edge import GraphicsEdge
from .graphics_individual import GraphicsIndividual
from .graphics_extension import GraphicsExtension
from .layout_storage import load_layout, save_layout


class CurvedEdge(GraphicsEdge):
    def __init__(self, from_node, to_node, label="", edge_type="related",
                 style="solid", color="#ff8800", arrow=True):
        self.handle_offset = QPointF(0, 0)
        self.is_dragging_path = False
        self.arc_index = 0

        super().__init__(from_node, to_node, label, edge_type, style, color, arrow)

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging_path = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging_path:
            start = self.from_node.mapToScene(self.from_node.boundingRect().center())
            end = self.to_node.mapToScene(self.to_node.boundingRect().center())
            mid = (start + end) / 2

            auto_offset = QPointF(0, 0)
            if self.arc_index != 0:
                line_vec = end - start
                length = (line_vec.x() ** 2 + line_vec.y() ** 2) ** 0.5
                if length > 0:
                    perp = QPointF(-line_vec.y() / length, line_vec.x() / length)
                    auto_offset = perp * (50 * self.arc_index)

            self.handle_offset = event.scenePos() - (mid + auto_offset)
            self.update_path()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_dragging_path = False
        if self.scene():
            save_layout(self.scene(), self.scene()._ontology_path() if self.scene() else None)
        super().mouseReleaseEvent(event)

    def update_path(self):
        if not self.from_node or not self.to_node:
            self.setPath(QPainterPath())
            return

        start = self.from_node.mapToScene(self.from_node.boundingRect().center())
        end = self.to_node.mapToScene(self.to_node.boundingRect().center())
        mid = (start + end) / 2

        auto_offset = QPointF(0, 0)
        if self.arc_index != 0:
            line_vec = end - start
            length = (line_vec.x() ** 2 + line_vec.y() ** 2) ** 0.5
            if length > 0:
                perp = QPointF(-line_vec.y() / length, line_vec.x() / length)
                auto_offset = perp * (50 * self.arc_index)

        ctrl = mid + auto_offset + self.handle_offset
        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(ctrl, end)
        self.setPath(path)

        if self.label_text:
            mid_on_path = path.pointAtPercent(0.5)
            rect = self.label_text.boundingRect()
            self.label_text.setPos(
                mid_on_path.x() - rect.width() / 2,
                mid_on_path.y() - rect.height() - 8
            )

    def save_state(self):
        return {"ox": self.handle_offset.x(), "oy": self.handle_offset.y(), "arc": self.arc_index}

    def load_state(self, data):
        if data:
            self.handle_offset = QPointF(data.get("ox", 0), data.get("oy", 0))
            self.arc_index = data.get("arc", 0)
            self.update_path()


class OntologyScene(QGraphicsScene):
    itemMoved = Signal(str, QPointF)
    node_clicked = Signal(str, str)

    def __init__(self, manager: OntologyManager):
        super().__init__()
        self.manager = manager
        self.class_items: dict[str, GraphicsClass] = {}
        self.individual_items: dict[str, list] = {}
        self.edges = []

        self.extension_items: dict[str, GraphicsExtension] = {}
        self.extension_nodes: dict[str, list] = {}
        self.extension_edges: dict[str, list] = {}
        self.extension_parents: dict[str, GraphicsClass] = {}

        self._filter_state: dict = {}
        self._collapsed_by_extension: set = set()

        self.temp_edge = None
        self.temp_source_node = None
        self.is_creating_edge = False

        # Подсветка пути между двумя узлами (обычный клик → Ctrl+клик)
        self._path_node_a = None
        self._highlighted_path_edges: list = []
        self._highlighted_path_nodes: list = []

    def _ontology_path(self):
        """Возвращает путь к текущему файлу онтологии из главного окна."""
        try:
            views = self.views()
            if views:
                mw = views[0].window()
                if hasattr(mw, 'current_file_path'):
                    return mw.current_file_path
        except Exception:
            pass
        return None

    # ── Подсветка ─────────────────────────────────────────────────────────────

    def highlight_node(self, type_node: str, name: str):
        for item in self.items():
            if hasattr(item, 'set_highlight'):
                item.set_highlight(False)
        self._highlighted_path_nodes = []
        self._highlighted_path_edges = []
        self._path_node_a = None

        if type_node == "class" and name in self.class_items:
            node_item = self.class_items[name]
            node_item.set_highlight(True)
            self._path_node_a = node_item
        elif type_node == "individual" and name in self.individual_items:
            items_list = self.individual_items[name]
            for ind_item in items_list:
                ind_item.set_highlight(True)
            if items_list:
                # Для поиска пути берём первое графическое представление —
                # один individual может быть отображён в нескольких местах
                self._path_node_a = items_list[0]

        self.update()

    # ── Подсветка пути между двумя узлами ───────────────────────────────────────

    def _clear_path_highlight(self):
        """Снимает подсветку с узлов и рёбер ранее найденного пути."""
        for node in self._highlighted_path_nodes:
            if hasattr(node, 'set_highlight'):
                node.set_highlight(False)
        for edge in self._highlighted_path_edges:
            if hasattr(edge, 'set_highlight'):
                edge.set_highlight(False)
        self._highlighted_path_nodes = []
        self._highlighted_path_edges = []

    def clear_path_selection(self):
        """
        Полностью отменяет выбор узла A и подсвеченный путь — снимает подсветку
        со всех узлов/рёбер графа. Вызывается по Esc или клику по пустому месту
        (canvas или дерево объектов).
        """
        for item in self.items():
            if hasattr(item, 'set_highlight'):
                item.set_highlight(False)
        self._highlighted_path_nodes = []
        self._highlighted_path_edges = []
        self._path_node_a = None
        self.update()

    def _find_path_edges(self, node_a, node_b):
        """
        Ищет кратчайший путь между node_a и node_b по неориентированному графу,
        построенному из всех рёбер сцены (наследование, object property, instance_of).
        Возвращает (nodes_on_path, edges_on_path) либо ([], []) если путь не найден.
        """
        if node_a is None or node_b is None or node_a is node_b:
            return [], []

        # Граф смежности: node -> list[(neighbor_node, edge)]
        adjacency: dict = {}
        for edge in self.edges:
            a = getattr(edge, 'from_node', None)
            b = getattr(edge, 'to_node', None)
            if a is None or b is None:
                continue
            adjacency.setdefault(a, []).append((b, edge))
            adjacency.setdefault(b, []).append((a, edge))

        if node_a not in adjacency or node_b not in adjacency:
            return [], []

        # BFS — кратчайший путь по числу рёбер
        from collections import deque
        visited = {node_a}
        # came_from: node -> (previous_node, edge_used)
        came_from = {}
        queue = deque([node_a])
        found = False

        while queue:
            current = queue.popleft()
            if current is node_b:
                found = True
                break
            for neighbor, edge in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    came_from[neighbor] = (current, edge)
                    queue.append(neighbor)

        if not found:
            return [], []

        # Восстановление пути от node_b к node_a
        path_nodes = [node_b]
        path_edges = []
        current = node_b
        while current is not node_a:
            prev, edge = came_from[current]
            path_edges.append(edge)
            path_nodes.append(prev)
            current = prev

        path_nodes.reverse()
        path_edges.reverse()
        return path_nodes, path_edges

    def highlight_path_between(self, node_a, node_b):
        """Находит и подсвечивает путь между двумя графическими узлами (классы/индивиды)."""
        self._clear_path_highlight()

        nodes, edges = self._find_path_edges(node_a, node_b)
        if not nodes:
            self.update()
            return

        for node in nodes:
            if hasattr(node, 'set_highlight'):
                node.set_highlight(True)
        for edge in edges:
            if hasattr(edge, 'set_highlight'):
                edge.set_highlight(True)

        self._highlighted_path_nodes = nodes
        self._highlighted_path_edges = edges
        self.update()

    def select_path_target(self, type_node: str, name: str):
        """
        Аналог Ctrl+клика по узлу на canvas, но по (type_node, name) —
        используется деревом объектов для выбора узла B. Узел A берётся
        из self._path_node_a (устанавливается highlight_node / обычным кликом).
        """
        node_item = None
        if type_node == "class":
            node_item = self.class_items.get(name)
        elif type_node == "individual":
            items_list = self.individual_items.get(name)
            if items_list:
                node_item = items_list[0]

        if node_item is None:
            return
        if self._path_node_a is None or self._path_node_a is node_item:
            return

        self.highlight_path_between(self._path_node_a, node_item)

    # ── Фильтрация ────────────────────────────────────────────────────────────

    def apply_filters(self, state: dict):
        self._filter_state = state
        show_classes     = state.get("show_classes", True)
        show_individuals = state.get("show_individuals", True)
        show_properties  = state.get("show_properties", True)
        max_level        = state.get("max_level", -1)

        for name, item in self.class_items.items():
            if name in self._collapsed_by_extension:
                continue
            if not show_classes:
                item.setVisible(False)
                continue
            if max_level != -1:
                level = self._class_level(name)
                item.setVisible(level <= max_level)
            else:
                item.setVisible(True)

        for name, items_list in self.individual_items.items():
            for ind_item in items_list:
                if not show_individuals:
                    ind_item.setVisible(False)
                elif max_level != -1:
                    parent = ind_item.parentItem()
                    if parent and hasattr(parent, 'name'):
                        level = self._class_level(parent.name) + 1
                        ind_item.setVisible(level <= max_level)
                    else:
                        ind_item.setVisible(True)
                else:
                    ind_item.setVisible(True)

        for edge in self.edges:
            if not hasattr(edge, 'from_node') or not hasattr(edge, 'to_node'):
                continue
            if not show_properties:
                edge.setVisible(False)
                continue
            from_ok = edge.from_node and edge.from_node.isVisible()
            to_ok   = edge.to_node   and edge.to_node.isVisible()
            edge.setVisible(from_ok and to_ok)

        for ext_name, ext_item in self.extension_items.items():
            if not ext_item.isVisible():
                continue
            nodes = self.extension_nodes.get(ext_name, [])
            visible = [n for n in nodes if n.isVisible()]
            if visible:
                ext_item.update_from_nodes(visible)

    def _class_level(self, class_name: str) -> int:
        if not self.manager or class_name not in self.manager.classes:
            return 1
        level = 1
        elem = self.manager.classes[class_name]
        while elem.parent:
            level += 1
            elem = elem.parent
        return level

    # ── Поиск ────────────────────────────────────────────────────────────────

    def apply_search(self, query: str):
        for item in self.items():
            if hasattr(item, 'set_highlight'):
                item.set_highlight(False)
        self._path_node_a = None
        self._highlighted_path_nodes = []
        self._highlighted_path_edges = []

        if not query or not self.manager:
            self.update()
            return

        q = query.lower()
        first_match = None

        for name, item in self.class_items.items():
            if not item.isVisible():
                continue
            elem = self.manager.classes.get(name)
            if not elem:
                continue
            if (q in name.lower() or
                    (elem.label and q in elem.label.lower())):
                item.set_highlight(True)
                if first_match is None:
                    first_match = item

        for name, items_list in self.individual_items.items():
            elem = self.manager.individuals.get(name)
            for ind_item in items_list:
                if not ind_item.isVisible():
                    continue
                if (q in name.lower() or
                        (elem and elem.label and q in elem.label.lower())):
                    ind_item.set_highlight(True)
                    if first_match is None:
                        first_match = ind_item

        self.update()

        if first_match and self.views():
            self.views()[0].ensureVisible(first_match)

    def zoom_to_node(self, type_node: str, name: str, target_scale: float = 1.5):
        """
        Центрирует view на узле и устанавливает комфортный масштаб.
        Используется автодополнением поиска (выбор из списка / Enter).
        """
        item = None
        if type_node == "class":
            item = self.class_items.get(name)
        elif type_node == "individual":
            items_list = self.individual_items.get(name)
            if items_list:
                item = items_list[0]

        if item is None or not self.views():
            return

        view = self.views()[0]

        self.highlight_node(type_node, name)

        view.resetTransform()
        view.scale(target_scale, target_scale)
        view.centerOn(item)

    # ── Расширения ────────────────────────────────────────────────────────────

    def _get_child_extensions(self, ext_name: str) -> list[str]:
        parent_nodes = set(self.extension_nodes.get(ext_name, []))
        return [
            other_ext for other_ext, other_parent
            in self.extension_parents.items()
            if other_ext != ext_name and other_parent in parent_nodes
        ]

    def _collapse_extension(self, ext_name: str):
        ext_item = self.extension_items.get(ext_name)
        if not ext_item or not ext_item.isVisible():
            return

        for child_ext in self._get_child_extensions(ext_name):
            self._collapse_extension(child_ext)

        nodes  = self.extension_nodes.get(ext_name, [])
        edges  = self.extension_edges.get(ext_name, [])
        parent = self.extension_parents.get(ext_name)

        for node in nodes:
            node.setVisible(False)
            self._collapsed_by_extension.add(node)
        for edge in edges:
            edge.setVisible(False)
        ext_item.setVisible(False)

        if parent:
            parent.set_extension_collapsed(ext_name, True)

        tree = self._get_tree()
        if tree:
            tree.hide_extension(ext_name)

    def _expand_extension(self, ext_name: str):
        ext_item = self.extension_items.get(ext_name)
        nodes  = self.extension_nodes.get(ext_name, [])
        edges  = self.extension_edges.get(ext_name, [])
        parent = self.extension_parents.get(ext_name)

        if not ext_item:
            return

        for node in nodes:
            node.setVisible(True)
            self._collapsed_by_extension.discard(node)

        for edge in edges:
            from_ok = not hasattr(edge, 'from_node') or edge.from_node is None or edge.from_node.isVisible()
            to_ok   = not hasattr(edge, 'to_node')   or edge.to_node   is None or edge.to_node.isVisible()
            if from_ok and to_ok:
                edge.setVisible(True)

        ext_item.setVisible(True)
        ext_item.update_from_nodes(nodes)

        if parent:
            parent.set_extension_collapsed(ext_name, False)

        tree = self._get_tree()
        if tree:
            tree.show_extension(ext_name)

        if self._filter_state:
            self.apply_filters(self._filter_state)

    def update_extension_frames(self):
        for ext_name, ext_item in self.extension_items.items():
            if not ext_item.isVisible():
                continue
            nodes = self.extension_nodes.get(ext_name, [])
            visible = [n for n in nodes if n.isVisible()]
            if visible:
                ext_item.update_from_nodes(visible)

    def _get_tree(self):
        try:
            view = self.views()[0] if self.views() else None
            if view:
                main_window = view.window()
                if hasattr(main_window, 'toolbox') and main_window.toolbox:
                    return main_window.toolbox.tree
        except Exception:
            pass
        return None

    def _build_extensions(self):
        self.extension_items.clear()
        self.extension_nodes.clear()
        self.extension_edges.clear()
        self.extension_parents.clear()
        self._collapsed_by_extension.clear()

        if not self.manager:
            return

        color_map: dict[str, int] = {}
        color_counter = 0

        for class_name, class_elem in self.manager.classes.items():
            ext_name = class_elem.extension
            if not ext_name or class_name not in self.class_items:
                continue

            if ext_name not in color_map:
                color_map[ext_name] = color_counter % len(GraphicsExtension.COLORS)
                color_counter += 1

            self.extension_nodes.setdefault(ext_name, []).append(
                self.class_items[class_name]
            )

            if class_elem.parent and class_elem.parent.name in self.class_items:
                self.extension_parents[ext_name] = self.class_items[class_elem.parent.name]

        for ext_name, nodes in self.extension_nodes.items():
            node_set = set(nodes)
            self.extension_edges[ext_name] = [
                edge for edge in self.edges
                if (hasattr(edge, 'from_node') and hasattr(edge, 'to_node') and
                    (edge.from_node in node_set or edge.to_node in node_set))
            ]

        for ext_name, nodes in self.extension_nodes.items():
            ext_item = GraphicsExtension(ext_name, color_map[ext_name])
            ext_item.update_from_nodes(nodes)
            self.addItem(ext_item)
            self.extension_items[ext_name] = ext_item
            ext_item.collapse_requested.connect(self._on_collapse_requested)

        for ext_name, parent_item in self.extension_parents.items():
            parent_item.extension_toggle_requested.connect(self._on_extension_toggle)

    def _on_collapse_requested(self, ext_name: str):
        self._collapse_extension(ext_name)

    def _on_extension_toggle(self, class_name: str, ext_name: str):
        self._expand_extension(ext_name)

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        while item and isinstance(item, GraphicsEdge):
            item = item.parentItem()

        is_node = item and hasattr(item, "name") and (
            isinstance(item, GraphicsClass) or isinstance(item, GraphicsIndividual)
        )

        # Клик по пустому месту — полностью отменяет выбор узла A и путь
        if event.button() == Qt.LeftButton and item is None:
            self.clear_path_selection()

        # Ctrl+клик по узлу B — подсветить путь от ранее выбранного узла A
        if (event.button() == Qt.LeftButton and is_node and
                event.modifiers() & Qt.ControlModifier):
            event.accept()
            if self._path_node_a is not None and self._path_node_a is not item:
                self.highlight_path_between(self._path_node_a, item)
            return

        if (event.button() == Qt.LeftButton and is_node):
            # Обычный клик — запоминаем узел A для последующей подсветки пути
            self._clear_path_highlight()
            self._path_node_a = item

            if isinstance(item, GraphicsClass):
                self.node_clicked.emit("class", item.name)
            elif isinstance(item, GraphicsIndividual):
                self.node_clicked.emit("individual", item.name)

            if self.manager and self.manager.object_properties:
                self.temp_source_node = item
                self.temp_edge = GraphicsEdge(item, None, "temp", edge_type="related", color="#888888")
                self.addItem(self.temp_edge)
                self.temp_edge.setZValue(-100)
                self.is_creating_edge = True
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_creating_edge and self.temp_edge:
            pos = event.scenePos()
            dummy = type("obj", (), {
                "mapToScene": lambda *_: QPointF(pos.x() + 1, pos.y() + 1),
                "boundingRect": lambda: QRectF(0, 0, 1, 1)
            })()
            self.temp_edge.to_node = dummy
            self.temp_edge.update_path()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.is_creating_edge or not self.temp_edge or not self.temp_source_node:
            super().mouseReleaseEvent(event)
            return

        target_item = self.itemAt(event.scenePos(), self.views()[0].transform())
        while target_item and isinstance(target_item, GraphicsEdge):
            target_item = target_item.parentItem()

        if (target_item and hasattr(target_item, "name") and
                target_item is not self.temp_source_node and
                (isinstance(target_item, GraphicsClass) or isinstance(target_item, GraphicsIndividual))):

            source_name = self.temp_source_node.name
            target_name = target_item.name

            props = list(self.manager.object_properties.keys())
            if props:
                prop_name, ok = QInputDialog.getItem(
                    None, "Выберите отношение", "Свойство:", props, 0, False
                )
                if ok:
                    edge = CurvedEdge(
                        self.temp_source_node, target_item,
                        label=prop_name, edge_type="related",
                        style="dashed", color="#e74c3c", arrow=True
                    )
                    edge.setZValue(-100)
                    self.addItem(edge)
                    self.edges.append(edge)

                    if (isinstance(self.temp_source_node, GraphicsIndividual) and
                            isinstance(target_item, GraphicsIndividual)):
                        self.manager.add_individual_relation(source_name, target_name, prop_name)

        if self.temp_edge:
            self.removeItem(self.temp_edge)
            self.temp_edge = None
        self.temp_source_node = None
        self.is_creating_edge = False
        super().mouseReleaseEvent(event)

    # ── Edge offsets ──────────────────────────────────────────────────────────

    def update_all_edge_offsets(self):
        from collections import defaultdict
        edge_groups = defaultdict(list)

        for item in self.items():
            if isinstance(item, GraphicsEdge) and item.from_node and item.to_node:
                pair = frozenset([item.from_node, item.to_node])
                edge_groups[pair].append(item)

        for pair, edges in edge_groups.items():
            if len(edges) == 1:
                if hasattr(edges[0], 'arc_index'):
                    edges[0].arc_index = 0
                    edges[0].update_path()
            else:
                edges.sort(key=lambda x: x.label_text.toPlainText())
                reference_node = list(pair)[0]
                for i, edge in enumerate(edges):
                    if not hasattr(edge, 'arc_index'):
                        continue
                    direction = 1 if edge.from_node == reference_node else -1
                    if i == 0:
                        edge.arc_index = 0
                    else:
                        raw_index = (i // 2 + 1) * (1 if i % 2 == 1 else -1)
                        edge.arc_index = raw_index * direction
                    edge.update_path()

    # ── update_from_manager ───────────────────────────────────────────────────

    def update_from_manager(self):
        try:
            self.blockSignals(True)
            self.clear()
            self.class_items.clear()
            self.individual_items.clear()
            self.edges.clear()
            self.extension_items.clear()
            self.extension_nodes.clear()
            self.extension_edges.clear()
            self.extension_parents.clear()
            self._collapsed_by_extension.clear()

            # self.clear() уничтожает все QGraphicsItem — ссылки на узлы/рёбра
            # пути и временное состояние выбора больше не валидны
            self._path_node_a = None
            self._highlighted_path_nodes = []
            self._highlighted_path_edges = []

            graph_data = self.manager.get_graph_data()
            if not graph_data["nodes"]:
                return

            saved_layout = load_layout(self._ontology_path())
            saved_positions = saved_layout.get("nodes", {})
            edge_states     = saved_layout.get("edges", {})

            current_class_ids = {
                nid for nid, a in graph_data["nodes"].items()
                if a.get("type") != "individual"
            }
            new_class_ids = current_class_ids - set(saved_positions.keys())

            if new_class_ids:
                for nid in sorted(new_class_ids):
                    parent_id = next(
                        (e["from"] for e in graph_data["edges"]
                         if e["to"] == nid and e.get("type") in ("inheritance", "extends")),
                        None
                    )
                    if parent_id and parent_id in saved_positions:
                        bx, by = saved_positions[parent_id]
                        saved_positions[nid] = (bx + 400 + (hash(nid) % 200), by + (hash(nid) % 300) - 150)
                    else:
                        saved_positions[nid] = (1400 + (hash(nid) % 800), (hash(nid) % 1000) - 500)

            # Классы
            for nid, attrs in graph_data["nodes"].items():
                if attrs.get("type") == "individual":
                    continue
                pos     = saved_positions.get(nid, (0, 0))
                label   = attrs.get("label", nid)
                formula = attrs.get("formula", "")

                print(f"[update_from_manager] Создаётся класс {nid}, формула: '{formula}'")

                # Собираем свойства и значения из модели
                cls_elem = self.manager.classes.get(nid)
                own_props, inh_props, prop_values = [], [], {}
                if cls_elem is not None:
                    for dp in self.manager.data_properties.values():
                        if dp.domain and dp.domain.name == nid:
                            own_props.append(dp.name)
                    for dp in cls_elem.get_inherited_data_properties(self.manager.data_properties):
                        ancestor = dp.domain.name if dp.domain else ""
                        inh_props.append((dp.name, ancestor))
                    prop_values = dict(getattr(cls_elem, "prop_values", {}))

                item = GraphicsClass(
                    nid, label, pos,
                    formula=formula,
                    own_properties=own_props,
                    inherited_properties=inh_props,
                    prop_values=prop_values,
                )
                item.setZValue(10)
                self.addItem(item)
                self.class_items[nid] = item

                def handler_factory(name):
                    def handler():
                        save_layout(self, self._ontology_path())
                        self.update_extension_frames()
                    return handler
                item.scenePosChanged.connect(handler_factory(nid))

            # Индивиды
            for ind_name, ind_elem in self.manager.individuals.items():
                label = ind_elem.label or ind_name
                for cls_elem in ind_elem.classes:
                    cls_name = cls_elem.name
                    if cls_name not in self.class_items:
                        continue
                    parent_item = self.class_items[cls_name]
                    unique_key  = f"{ind_name}@@{cls_name}"
                    formula     = ind_elem.formula if hasattr(ind_elem, "formula") else ""

                    ind_item = GraphicsIndividual(ind_name, label, parent=parent_item, formula=formula)
                    ind_item.setZValue(15)
                    ind_item.setFlag(QGraphicsItem.ItemIsMovable, True)
                    ind_item.setFlag(QGraphicsItem.ItemIsSelectable, True)

                    if unique_key in saved_positions:
                        ind_item.setPos(*saved_positions[unique_key])
                    else:
                        children = [c for c in parent_item.childItems() if isinstance(c, GraphicsIndividual)]
                        row = len(children) % 4
                        col = len(children) // 4
                        ind_item.setPos(30 + row * 200, 80 + col * 90)

                    def make_handler(key):
                        def handler():
                            save_layout(self, self._ontology_path())
                        return handler
                    ind_item.scenePosChanged.connect(make_handler(unique_key))

                    self.addItem(ind_item)
                    self.individual_items.setdefault(ind_name, []).append(ind_item)

            # Рёбра
            for edge_data in graph_data["edges"]:
                if edge_data.get("type") == "instance_of":
                    continue

                from_name = edge_data["from"]
                to_name   = edge_data["to"]
                label     = edge_data.get("label", "")

                from_items = self.class_items.get(from_name) or self.individual_items.get(from_name, [])
                to_items   = self.class_items.get(to_name)   or self.individual_items.get(to_name, [])

                from_list = from_items if isinstance(from_items, list) else [from_items]
                to_list   = to_items   if isinstance(to_items,   list) else [to_items]

                for src in from_list:
                    for dst in to_list:
                        if not (src and dst):
                            continue
                        key  = f"{from_name}→{to_name}→{label}"
                        edge = CurvedEdge(
                            src, dst,
                            label=label,
                            edge_type=edge_data.get("type", "related"),
                            style=edge_data.get("style", "solid"),
                            color=edge_data.get("color", "#ff8800"),
                            arrow=edge_data.get("arrow", True)
                        )
                        edge.setZValue(-100)
                        self.addItem(edge)
                        self.edges.append(edge)
                        if key in edge_states:
                            edge.load_state(edge_states[key])

            # Стрелки "is a"
            for ind_name, items_list in self.individual_items.items():
                for ind_item in items_list:
                    parent = ind_item.parentItem()
                    if parent and isinstance(parent, GraphicsClass):
                        key  = f"{ind_name}→{parent.name}→is a"
                        edge = CurvedEdge(ind_item, parent, "is a", "instance_of", "solid", "#9933ff", True)
                        edge.setZValue(-100)
                        self.addItem(edge)
                        self.edges.append(edge)
                        if key in edge_states:
                            edge.load_state(edge_states[key])

            self.update_all_edge_offsets()
            self._build_extensions()

            if self._filter_state:
                self.apply_filters(self._filter_state)

            save_layout(self, self._ontology_path())

            if self.items():
                self.setSceneRect(self.itemsBoundingRect().adjusted(-600, -600, 600, 600))

        except Exception as e:
            print(f"Ошибка в update_from_manager: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.blockSignals(False)


class OntologyView(QGraphicsView):
    def __init__(self, scene: OntologyScene):
        super().__init__(scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scale(0.85, 0.85)
        # Нужно для keyPressEvent/keyReleaseEvent (перехват Ctrl) — по умолчанию
        # QGraphicsView не принимает фокус клавиатуры
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event):
        # ScrollHandDrag перехватывает любой левый клик под панорамирование,
        # из-за чего Ctrl+клик по узлу (подсветка пути) не доходит до сцены.
        # На время удержания Ctrl временно отключаем DragMode.
        if event.key() == Qt.Key_Control and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        elif event.key() == Qt.Key_Escape:
            self.scene().clear_path_selection()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyReleaseEvent(event)

    def update_view(self):
        try:
            if self.scene().items():
                r = self.scene().itemsBoundingRect().adjusted(-200, -200, 200, 200)
                self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as e:
            print(f"Ошибка в update_view: {e}")

    def wheelEvent(self, event: QWheelEvent):
        try:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            if 0.15 <= self.transform().m11() * factor <= 6.0:
                self.scale(factor, factor)
        except Exception as e:
            print(f"Ошибка в wheelEvent: {e}")
