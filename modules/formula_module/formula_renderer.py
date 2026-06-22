import re
import matplotlib
matplotlib.use("Agg")
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtSvg import QSvgRenderer
import matplotlib.pyplot as plt
from io import BytesIO


# ── Таблица замен LaTeX → matplotlib mathtext ─────────────────────────────────

_MATHTEXT_REPLACEMENTS = [
    # Сокращённые операторы сравнения → полные формы
    (r'\ge',       r'\geq'),
    (r'\le',       r'\leq'),

    # Логические связки
    (r'\land',     r'\wedge'),
    (r'\lor',      r'\vee'),

    # Стрелки / отношения
    (r'\implies',  r'\Rightarrow'),
    (r'\iff',      r'\Leftrightarrow'),
    (r'\to',       r'\rightarrow'),
    (r'\gets',     r'\leftarrow'),

    # Множества
    (r'\Z',        r'\mathbb{Z}'),
    (r'\N',        r'\mathbb{N}'),
    (r'\Q',        r'\mathbb{Q}'),

]

_LEFT_RIGHT_RE = re.compile(r'\\(left|right)\s*([(\)\[\]|{}.\\])')


def _normalize_for_mathtext(latex_str: str) -> str:
    """
    Приводит LaTeX-строку к подмножеству, понятному matplotlib mathtext.
    Применяет таблицу замен и удаляет неподдерживаемые конструкции.
    """
    s = latex_str

    # Убираем \left( и \right) — оставляем только скобки
    s = _LEFT_RIGHT_RE.sub(r'\2', s)

    # Применяем таблицу замен (только целые команды — через word boundary)
    for old, new in _MATHTEXT_REPLACEMENTS:
        # Экранируем \ для re и добавляем границу — не захватывать \geq при замене \ge
        escaped = re.escape(old)
        # Граница: после команды не должно быть буквы (иначе \ge захватит \geq)
        s = re.sub(escaped + r'(?![a-zA-Z])', new.replace('\\', r'\\'), s)

    return s


def render_formula_to_svg_bytes(
    formula: str,
    font_size: float = 14,
    color: str = "#000000",
) -> bytes | None:
    """
    Рендерит формулу в SVG-байты через matplotlib mathtext.
    Возвращает bytes или None при ошибке.
    """
    if not formula or not formula.strip():
        return None

    # Получаем LaTeX-строку через FormulaEvaluator
    try:
        from .formula_core import FormulaEvaluator
        ev = FormulaEvaluator()
        ok, _ = ev.parse(formula)
        latex_str = ev.get_latex() if ok else formula.strip()
    except Exception:
        latex_str = formula.strip()

    # Нормализуем для matplotlib mathtext
    latex_str = _normalize_for_mathtext(latex_str)

    try:
        fig = plt.figure(figsize=(5.0, 1.0))
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        ax.set_axis_off()

        ax.text(
            0.5, 0.5,
            f"${latex_str}$",
            fontsize=font_size,
            color=color,
            ha='center', va='center',
            usetex=False,
            fontfamily='DejaVu Sans'
        )

        buf = BytesIO()
        fig.savefig(
            buf,
            format='svg',
            bbox_inches='tight',
            transparent=True,
            pad_inches=0.08,
        )
        buf.seek(0)
        plt.close(fig)

        return buf.read()

    except Exception as e:
        print(f"[formula_renderer] Ошибка рендера: {e}")
        # Второй шанс — рендерим формулу как plain text без $...$
        try:
            fig = plt.figure(figsize=(5.0, 1.0))
            fig.patch.set_alpha(0.0)
            ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
            ax.set_axis_off()
            ax.text(0.5, 0.5, formula.strip(),
                    fontsize=font_size, color=color,
                    ha='center', va='center')
            buf = BytesIO()
            fig.savefig(buf, format='svg', bbox_inches='tight',
                        transparent=True, pad_inches=0.08)
            buf.seek(0)
            plt.close(fig)
            return buf.read()
        except Exception as e2:
            print(f"[formula_renderer] Fallback тоже упал: {e2}")
            plt.close('all')
            return None


def render_formula_to_svg_item(
    formula: str,
    font_size: float = 14,
    color: str = "#000000",
    max_width: float = 320,
    parent=None,
) -> QGraphicsSvgItem | None:
    """
    Рендерит формулу и возвращает QGraphicsSvgItem для размещения на сцене.
    """
    svg_bytes = render_formula_to_svg_bytes(formula, font_size, color)
    if not svg_bytes:
        return None

    try:
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        if not renderer.isValid():
            print("[formula_renderer] SVG renderer невалиден")
            return None

        item = QGraphicsSvgItem()
        item.setSharedRenderer(renderer)
        item._svg_renderer = renderer  # держим ссылку чтобы не собрал GC

        w = item.boundingRect().width()
        if w > max_width and w > 0:
            item.setScale(max_width / w)

        return item

    except Exception as e:
        print(f"[formula_renderer] Ошибка создания QGraphicsSvgItem: {e}")
        return None


# ── Pixmap fallback ───────────────────────────────────────────────────────────

from PySide6.QtGui import QPixmap, QImage

def render_formula_to_pixmap(
    latex: str,
    font_size: float = 14,
    color: str = "#000000",
    dpi: int = 200,
    max_width: int = 380,
) -> QPixmap | None:
    """Fallback: рендер в QPixmap."""
    svg_bytes = render_formula_to_svg_bytes(latex, font_size, color)
    if not svg_bytes:
        return None

    try:
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        if not renderer.isValid():
            return None

        from PySide6.QtCore import QSize
        size = renderer.defaultSize() * 2
        if size.width() > max_width:
            size.setHeight(int(size.height() * max_width / size.width()))
            size.setWidth(max_width)

        from PySide6.QtGui import QPainter
        img = QImage(size, QImage.Format.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()

        return QPixmap.fromImage(img)

    except Exception as e:
        print(f"[formula_renderer] Ошибка pixmap fallback: {e}")
        return None
