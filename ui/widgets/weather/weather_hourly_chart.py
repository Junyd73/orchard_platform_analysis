from math import ceil

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from ui.widgets.weather.weather_base_widget import BaseWeatherWidget


class WeatherHourlyChart(BaseWeatherWidget):
    EMPTY_TEXT = "시간별 데이터 없음"
    COLOR_TEXT_MAIN = "#2D3748"
    COLOR_TEXT_SUB = "#718096"
    COLOR_TEMP_LINE = "#F6AD55"
    COLOR_RAIN = "#4A90E2"
    COLOR_POINT_FILL = "#FFFFFF"
    LINE_COLOR = COLOR_TEMP_LINE
    POINT_FILL_COLOR = COLOR_POINT_FILL
    POINT_STROKE_COLOR = COLOR_TEMP_LINE
    ICON_TEXT_MAP = {
        "sun": "☀",
        "moon": "☾",
        "cloud": "☁",
        "rain": "☂",
        "partly_cloudy": "⛅",
        "snow": "❄",
    }
    ICON_COLOR_MAP = {
        "sun": "#F59E0B",
        "moon": "#6366F1",
        "cloud": COLOR_TEXT_SUB,
        "rain": COLOR_RAIN,
        "partly_cloudy": "#D69E2E",
        "snow": "#63B3ED",
    }
    TOP_LABEL_HEIGHT = 18
    ICON_HEIGHT = 16
    TIME_HEIGHT = 14
    BOTTOM_SECTION_GAP = 8
    LINE_WIDTH = 2
    POINT_RADIUS = 3
    MIN_CHART_HEIGHT = 20

    def _normalize_range(self):
        values = []
        for row in self._data:
            if "temp" not in row:
                continue
            try:
                values.append(float(row["temp"]))
            except (TypeError, ValueError):
                continue
        if not values:
            return None
        low = min(values)
        high = max(values)
        span = high - low
        if span <= 0:
            span = 6.0
            low -= span / 2.0
            high += span / 2.0
        else:
            buffer = max(1.0, span * 0.15)
            low -= buffer
            high += buffer
        return low, high

    def _calc_chart_rect(self):
        s = self._style
        left = s.PADDING
        right = max(left + 1, self.width() - s.PADDING)
        top = s.TOP_PADDING + self.TOP_LABEL_HEIGHT
        bottom_reserved = (
            self.ICON_HEIGHT
            + self.TIME_HEIGHT
            + (self.BOTTOM_SECTION_GAP * 2)
            + max(s.BOTTOM_PADDING, 0)
        )
        bottom = max(top + self.MIN_CHART_HEIGHT, self.height() - bottom_reserved)
        return QRectF(left, top, right - left, bottom - top)

    def _slot_x_positions(self, chart_rect: QRectF, n: int):
        """강수 막대 차트와 동일: N개 슬롯을 폭으로 균등 분할한 각 칸의 중심 X."""
        if n <= 0:
            return []
        left = chart_rect.left()
        w = chart_rect.width()
        if n == 1:
            return [left + w / 2.0]
        slot_w = w / float(n)
        return [left + (i + 0.5) * slot_w for i in range(n)]

    def _calc_points(self, chart_rect: QRectF, min_temp, max_temp):
        points = []
        n = len(self._data)
        if n <= 0:
            return points
        xs = self._slot_x_positions(chart_rect, n)
        for idx, row in enumerate(self._data):
            try:
                temp = float(row.get("temp"))
            except (TypeError, ValueError):
                continue
            x = xs[idx]
            y = self._temp_to_y(temp, min_temp, max_temp, chart_rect)
            points.append((idx, row, temp, QPointF(x, y)))
        return points

    def _temp_to_y(self, temp, min_temp, max_temp, rect: QRectF):
        span = max_temp - min_temp
        if span <= 0:
            return rect.center().y()
        ratio = (float(temp) - min_temp) / span
        return rect.bottom() - (ratio * rect.height())

    def _label_step(self, item_count, chart_rect: QRectF):
        if item_count <= 0:
            return 1
        min_slot_px = 34
        max_labels = max(1, int(chart_rect.width() // min_slot_px))
        return max(1, ceil(item_count / max_labels))

    def _draw_line(self, painter: QPainter, points):
        if len(points) < 2:
            return
        path = QPainterPath(points[0][3])
        for _, _, _, pt in points[1:]:
            path.lineTo(pt)
        pen = QPen(QColor(self.LINE_COLOR), self.LINE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _draw_points(self, painter: QPainter, points):
        painter.setPen(QPen(QColor(self.POINT_STROKE_COLOR), 1))
        painter.setBrush(QColor(self.POINT_FILL_COLOR))
        for _, _, _, pt in points:
            painter.drawEllipse(pt, self.POINT_RADIUS, self.POINT_RADIUS)

    def _draw_labels(self, painter: QPainter, points):
        s = self._style
        f = QFont()
        f.setPointSize(s.FONT_SUB_SIZE)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(QColor(s.TEXT_COLOR))
        for _, _, temp, pt in points:
            rect = QRectF(pt.x() - 16, pt.y() - 22, 32, 14)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{int(round(temp))}°")

    def _draw_icons(self, painter: QPainter, chart_rect: QRectF, xs, step: int):
        s = self._style
        f = QFont()
        f.setPointSize(s.ICON_FONT_SIZE)
        f.setBold(False)
        painter.setFont(f)
        icon_y = chart_rect.bottom() + self.BOTTOM_SECTION_GAP
        for idx, row in enumerate(self._data):
            if idx % step != 0:
                continue
            x = xs[idx]
            raw = str(row.get("icon") or "").strip().lower()
            text = self.ICON_TEXT_MAP.get(raw, "•")
            color = self.ICON_COLOR_MAP.get(raw, self.COLOR_TEXT_SUB)
            painter.setPen(QColor(color))
            rect = QRectF(x - 12, icon_y, 24, self.ICON_HEIGHT)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_times(self, painter: QPainter, chart_rect: QRectF, xs, step: int):
        s = self._style
        f = QFont()
        f.setPointSize(s.FONT_SUB_SIZE)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(QColor(self.COLOR_TEXT_MAIN))
        time_y = (
            chart_rect.bottom()
            + self.BOTTOM_SECTION_GAP
            + self.ICON_HEIGHT
            + self.BOTTOM_SECTION_GAP
        )
        for idx, row in enumerate(self._data):
            if idx % step != 0:
                continue
            x = xs[idx]
            t = str(row.get("time") or "")
            rect = QRectF(x - 22, time_y, 44, self.TIME_HEIGHT)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, t)

    def draw(self, painter: QPainter):
        if not self._data:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return

        normalized = self._normalize_range()
        if normalized is None:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return
        min_temp, max_temp = normalized

        chart_rect = self._calc_chart_rect()
        points = self._calc_points(chart_rect, min_temp, max_temp)
        if not points:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return

        xs = self._slot_x_positions(chart_rect, len(self._data))
        step = self._label_step(len(self._data), chart_rect)
        self._draw_line(painter, points)
        self._draw_points(painter, points)
        self._draw_labels(painter, points)
        self._draw_icons(painter, chart_rect, xs, step)
        self._draw_times(painter, chart_rect, xs, step)
