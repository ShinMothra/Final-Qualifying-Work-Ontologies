import json
from pathlib import Path

# Фоллбэк для случаев, когда путь к онтологии неизвестен
_FALLBACK_LAYOUT = Path("layout.json")


def get_layout_path(ontology_path: str | Path | None) -> Path:
    """
    Возвращает путь к layout-файлу для данной онтологии.
    Демонстрация.owl  →  Демонстрация.layout.json
    my_onto.json      →  my_onto.layout.json
    None              →  layout.json  (фоллбэк)
    """
    if not ontology_path:
        return _FALLBACK_LAYOUT
    p = Path(ontology_path)
    return p.parent / (p.stem + ".layout.json")


def _resolve_path(scene_or_path) -> Path:
    """
    Принимает либо сцену (берёт путь из main_window),
    либо строку/Path напрямую.
    """
    if isinstance(scene_or_path, (str, Path)):
        return get_layout_path(scene_or_path)

    # Это сцена — достаём путь из main_window
    try:
        views = scene_or_path.views() if hasattr(scene_or_path, 'views') else []
        if views:
            mw = views[0].window()
            if hasattr(mw, 'current_file_path'):
                return get_layout_path(mw.current_file_path)
    except Exception:
        pass

    return _FALLBACK_LAYOUT


def save_layout(scene, ontology_path: str | Path | None = None) -> None:
    """
    Сохраняет позиции узлов и состояния рёбер в layout-файл.

    ontology_path — путь к файлу онтологии; если не передан,
    путь берётся из main_window через сцену.
    """
    try:
        layout_file = get_layout_path(ontology_path) if ontology_path else _resolve_path(scene)
        positions = {}

        # Классы
        for name, item in getattr(scene, "class_items", {}).items():
            pos = item.scenePos()
            positions[name] = [pos.x(), pos.y()]

        # Индивиды
        for ind_name, items in getattr(scene, "individual_items", {}).items():
            for item in items:
                parent = item.parentItem()
                if parent and hasattr(parent, "name"):
                    key = f"ind:{ind_name}@@{parent.name}"
                    pos = item.pos()
                    positions[key] = [pos.x(), pos.y()]

        # Рёбра (waypoints / handle_offset)
        for edge in getattr(scene, "edges", []):
            src_name = edge.from_node.name if hasattr(edge, 'from_node') and hasattr(edge.from_node, "name") else None
            dst_name = edge.to_node.name   if hasattr(edge, 'to_node')   and hasattr(edge.to_node,   "name") else None
            if not src_name or not dst_name:
                continue

            label = ""
            if hasattr(edge, "label_text") and edge.label_text:
                label = edge.label_text.toPlainText()

            key = f"edge:{src_name}→{dst_name}→{label}"

            if hasattr(edge, "save_state"):
                positions[key] = edge.save_state()
            elif hasattr(edge, "waypoints") and edge.waypoints:
                positions[key] = [[p.x(), p.y()] for p in edge.waypoints]

        with open(layout_file, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[layout_storage] Ошибка при сохранении: {e}")


def load_layout(ontology_path: str | Path | None = None) -> dict:
    """
    Загружает layout для онтологии по её пути.
    Если путь не указан — пробует фоллбэк layout.json.
    """
    layout_file = get_layout_path(ontology_path)

    # Если файл не найден — пробуем фоллбэк (для обратной совместимости)
    if not layout_file.exists():
        if layout_file != _FALLBACK_LAYOUT and _FALLBACK_LAYOUT.exists():
            layout_file = _FALLBACK_LAYOUT
        else:
            return {"nodes": {}, "edges": {}}

    try:
        with open(layout_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = {}
        edges = {}

        for key, value in data.items():
            if key.startswith("edge:"):
                clean_key = key[len("edge:"):]
                edges[clean_key] = value
            elif key.startswith("ind:"):
                clean_key = key[len("ind:"):]
                nodes[clean_key] = (float(value[0]), float(value[1]))
            else:
                nodes[key] = (float(value[0]), float(value[1]))

        return {"nodes": nodes, "edges": edges}

    except Exception as e:
        print(f"[layout_storage] Ошибка при загрузке: {e}")
        return {"nodes": {}, "edges": {}}
