from math import ceil

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from ui.widgets.weather.weather_base_widget import BaseWeatherWidget


class WeatherRainChart(BaseWeatherWidget):
    EMPTY_TEXT = "강수 데이터 없음"
    COLOR_TEXT_MAIN = "#2D3748"
    COLOR_TEXT_SUB = "#718096"
    BAR_COLOR = "#4A90E2"
    BAR_BASE_COLOR = "#BEE3F8"
    BAR_WIDTH = 10
    TOP_LABEL_HEIGHT = 16
    TIME_HEIGHT = 14
    BOTTOM_SECTION_GAP = 4
    MIN_CHART_HEIGHT = 24

    def _normalize_range(self):
        values = []
        for row in self._data:
            try:
                values.append(float(row.get("rain", 0)))
            except (TypeError, ValueError):
                continue
        if not values:
            return None
        high = max(values)
        if high <= 0:
            high = 1.0
        else:
            high += max(0.5, high * 0.1)
        return 0.0, high

    def _calc_chart_rect(self):
        s = self._style
        left = s.PADDING
        right = max(left + 1, self.width() - s.PADDING)
        top = s.TOP_PADDING + self.TOP_LABEL_HEIGHT
        bottom_reserved = self.TIME_HEIGHT + self.BOTTOM_SECTION_GAP + max(s.BOTTOM_PADDING, 0)
        bottom = max(top + self.MIN_CHART_HEIGHT, self.height() - bottom_reserved)
        return QRectF(left, top, right - left, bottom - top)

    def _calc_item_rects(self, chart_rect: QRectF):
        rows = []
        for row in self._data:
            try:
                rain = float(row.get("rain", 0))
            except (TypeError, ValueError):
                continue
            rows.append((row, max(0.0, rain)))
        if not rows:
            return []
        item_w = chart_rect.width() / float(len(rows))
        rects = []
        for idx, (row, rain) in enumerate(rows):
            item_rect = QRectF(
                chart_rect.left() + (item_w * idx),
                chart_rect.top(),
                item_w,
                chart_rect.height(),
            )
            rects.append((row, rain, item_rect))
        return rects

    def _rain_to_height(self, value, max_rain, rect: QRectF):
        if max_rain <= 0:
            return 0.0
        h = (float(value) / max_rain) * rect.height()
        return max(0.0, min(rect.height(), h))

    def _label_step(self, item_count, chart_rect: QRectF):
        if item_count <= 0:
            return 1
        # 시간별 예보 차트와 동일 간격 → 같은 인덱스에 시간 라벨 표시
        min_slot_px = 34
        max_labels = max(1, int(chart_rect.width() // min_slot_px))
        return max(1, ceil(item_count / max_labels))

    def _draw_bars(self, painter: QPainter, item_rects, max_rain):
        painter.setPen(Qt.PenStyle.NoPen)
        for _, rain, rect in item_rects:
            h = self._rain_to_height(rain, max_rain, rect)
            cx = rect.center().x()
            width = min(self.BAR_WIDTH, max(3, int(rect.width() * 0.5)))
            x = cx - (width / 2.0)
            y = rect.bottom() - h
            if h <= 0.0:
                painter.setBrush(QColor(self.BAR_BASE_COLOR))
                painter.drawRect(QRectF(x, rect.bottom() - 1, width, 1))
                continue
            painter.setBrush(QColor(self.BAR_COLOR))
            painter.drawRoundedRect(QRectF(x, y, width, h), 2, 2)

    def _draw_labels(self, painter: QPainter, item_rects, max_rain, step: int):
        s = self._style
        f = QFont()
        f.setPointSize(s.FONT_SUB_SIZE)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(QColor(self.COLOR_TEXT_MAIN))
        for idx, (_, rain, rect) in enumerate(item_rects):
            if idx % step != 0:
                continue
            h = self._rain_to_height(rain, max_rain, rect)
            if rain <= 0:
                continue
            label = f"{rain:g}mm"
            label_rect = QRectF(rect.center().x() - 18, rect.bottom() - h - 16, 36, 14)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_times(self, painter: QPainter, item_rects, chart_rect: QRectF, step: int):
        s = self._style
        f = QFont()
        f.setPointSize(s.FONT_SUB_SIZE)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(QColor(self.COLOR_TEXT_MAIN))
        y = chart_rect.bottom() + self.BOTTOM_SECTION_GAP
        for idx, (row, _, rect) in enumerate(item_rects):
            if idx % step != 0:
                continue
            t = str(row.get("time") or "")
            label_rect = QRectF(rect.center().x() - 22, y, 44, self.TIME_HEIGHT)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, t)

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
        _, max_rain = normalized

        chart_rect = self._calc_chart_rect()
        item_rects = self._calc_item_rects(chart_rect)
        if not item_rects:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return

        step = self._label_step(len(item_rects), chart_rect)
        self._draw_bars(painter, item_rects, max_rain)
        self._draw_labels(painter, item_rects, max_rain, step)
        self._draw_times(painter, item_rects, chart_rect, step)
