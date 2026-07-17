from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget


@dataclass
class WeatherChartStyle:
    PADDING: int = 14
    TOP_PADDING: int = 12
    BOTTOM_PADDING: int = 34
    BAR_WIDTH: int = 8
    BAR_RADIUS: int = 4
    BAR_COLOR: str = "#F6AD55"
    TEXT_COLOR: str = "#2D3748"
    SUB_TEXT_COLOR: str = "#718096"
    FONT_MAIN_SIZE: int = 10
    FONT_SUB_SIZE: int = 9
    DAY_FONT_SIZE: int = 9
    ICON_FONT_SIZE: int = 10


class BaseWeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._style = WeatherChartStyle()

    def set_data(self, data):
        self._data = list(data or [])
        self.update()

    def set_style(self, style):
        self._style = style if style is not None else WeatherChartStyle()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.draw(painter)

    def draw(self, painter: QPainter):
        pass
