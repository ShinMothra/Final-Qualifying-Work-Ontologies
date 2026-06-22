from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from io import BytesIO

class FormulaPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumHeight(120)
        self.layout().addWidget(self.label)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def show_latex(self, latex_str: str):
        """Рендерим LaTeX в изображение через matplotlib"""
        if not latex_str.strip():
            self.label.setText("Формула не задана")
            self.label.setPixmap(QPixmap())
            return

        try:
            fig = plt.figure(figsize=(6, 1.2), dpi=150)
            fig.text(0.5, 0.5, f"${latex_str}$", fontsize=18, ha='center', va='center')
            fig.patch.set_alpha(0.0)

            buf = BytesIO()
            canvas = FigureCanvasAgg(fig)
            canvas.print_png(buf)
            buf.seek(0)

            img = QImage.fromData(buf.read())
            pixmap = QPixmap.fromImage(img)
            self.label.setPixmap(pixmap.scaled(600, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            plt.close(fig)
        except Exception as e:
            self.label.setText(f"Ошибка рендеринга: {str(e)}")
            self.label.setPixmap(QPixmap())