from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from ui.widgets.weather.weather_base_widget import BaseWeatherWidget


class WeatherTempRangeChart(BaseWeatherWidget):
    MAX_ITEMS = 7
    COLOR_TEMP_RANGE = "#F6AD55"
    COLOR_RAIN = "#4A90E2"
    COLOR_TEXT_MAIN = "#2D3748"
    COLOR_TEXT_SUB = "#718096"
    CHART_TOP_PADDING = 36
    CHART_BOTTOM_PADDING = 72
    MAX_LABEL_GAP = 10
    LABEL_HEIGHT = 14
    MIN_TOP_GAP = 8
    ICON_TOP_GAP = 24
    DAY_TOP_GAP = 40
    ICON_TEXT_MAP = {
        "sun": "☀",
        "cloud": "☁",
        "rain": "☂",
        "partly_cloudy": "⛅",
        "snow": "❄",
    }
    ICON_COLOR_MAP = {
        "sun": "#F59E0B",
        "cloud": COLOR_TEXT_SUB,
        "rain": COLOR_RAIN,
        "partly_cloudy": "#D69E2E",
        "snow": "#63B3ED",
    }
    EMPTY_TEXT = "날씨 데이터 없음"

    def _normalize_range(self):
        values = []
        for row in self._data[: self.MAX_ITEMS]:
            if "min" not in row or "max" not in row:
                continue
            try:
                mn = float(row["min"])
                mx = float(row["max"])
            except (TypeError, ValueError):
                continue
            values.extend([mn, mx])
        if not values:
            return None
        low = min(values)
        high = max(values)
        span = high - low
        if span <= 0:
            # 동일 온도만 들어와도 막대 길이가 0이 되지 않도록 최소 범위 확보
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
        top = max(s.TOP_PADDING, self.CHART_TOP_PADDING)
        right = max(left + 1, self.width() - s.PADDING)
        bottom_pad = max(s.BOTTOM_PADDING, self.CHART_BOTTOM_PADDING)
        bottom = max(top + 1, self.height() - bottom_pad)
        return QRectF(left, top, right - left, bottom - top)

    def _calc_item_rects(self, chart_rect: QRectF):
        count = min(len(self._data), self.MAX_ITEMS)
        if count <= 0:
            return []
        item_w = chart_rect.width() / float(count)
        rects = []
        for idx in range(count):
            rects.append(
                QRectF(
                    chart_rect.left() + (item_w * idx),
                    chart_rect.top(),
                    item_w,
                    chart_rect.height(),
                )
            )
        return rects

    def _temp_to_y(self, value, min_temp, max_temp, rect: QRectF):
        span = max_temp - min_temp
        if span <= 0:
            return rect.center().y()
        ratio = (float(value) - min_temp) / span
        return rect.bottom() - (ratio * rect.height())

    def _iter_valid_rows(self, item_rects):
        for idx, rect in enumerate(item_rects):
            row = self._data[idx]
            if "min" not in row or "max" not in row:
                continue
            try:
                mn = float(row["min"])
                mx = float(row["max"])
            except (TypeError, ValueError):
                continue
            yield row, rect, mn, mx

    def _draw_bars(self, painter: QPainter, item_rects, min_temp, max_temp):
        s = self._style
        pen = QPen(QColor(s.BAR_COLOR))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setWidth(max(1, int(s.BAR_WIDTH)))
        painter.setPen(pen)
        for _, rect, mn, mx in self._iter_valid_rows(item_rects):
            cx = rect.center().x()
            y_top = self._temp_to_y(mx, min_temp, max_temp, rect)
            y_bottom = self._temp_to_y(mn, min_temp, max_temp, rect)
            painter.drawLine(QPointF(cx, y_top), QPointF(cx, y_bottom))

    def _draw_labels(self, painter: QPainter, item_rects, min_temp, max_temp):
        s = self._style
        font_main = QFont()
        font_main.setPointSize(s.FONT_SUB_SIZE)
        font_main.setBold(False)
        font_sub = QFont()
        font_sub.setPointSize(s.FONT_SUB_SIZE)
        font_day = QFont()
        font_day.setPointSize(s.DAY_FONT_SIZE)
        font_day.setBold(False)

        for row, rect, mn, mx in self._iter_valid_rows(item_rects):
            y_top = self._temp_to_y(mx, min_temp, max_temp, rect)
            y_bottom = self._temp_to_y(mn, min_temp, max_temp, rect)

            painter.setPen(QColor(s.TEXT_COLOR))
            painter.setFont(font_main)
            max_y = max(0.0, y_top - (self.LABEL_HEIGHT + self.MAX_LABEL_GAP))
            max_rect = QRectF(rect.left(), max_y, rect.width(), self.LABEL_HEIGHT)
            painter.drawText(
                max_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                f"{int(round(mx))}°",
            )

            painter.setFont(font_sub)
            painter.setPen(QColor(s.SUB_TEXT_COLOR))
            min_rect = QRectF(rect.left(), y_bottom + self.MIN_TOP_GAP, rect.width(), 14)
            painter.drawText(min_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{int(round(mn))}°")

            painter.setFont(font_day)
            painter.setPen(QColor(s.TEXT_COLOR))
            day_text = str(row.get("day") or "")
            date_text = str(row.get("date") or "").strip()
            if date_text:
                day_text = f"{date_text}({day_text})" if day_text else date_text
            day_rect = QRectF(rect.left(), rect.bottom() + self.DAY_TOP_GAP, rect.width(), 16)
            painter.drawText(
                day_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                day_text,
            )

    def _draw_icons(self, painter: QPainter, item_rects):
        s = self._style
        icon_font = QFont()
        icon_font.setPointSize(s.ICON_FONT_SIZE + 1)
        icon_font.setBold(False)
        painter.setFont(icon_font)
        for idx, rect in enumerate(item_rects):
            row = self._data[idx]
            raw_icon = str(row.get("icon") or "").strip().lower()
            icon_text = self.ICON_TEXT_MAP.get(raw_icon, "•")
            icon_color = self.ICON_COLOR_MAP.get(raw_icon, s.SUB_TEXT_COLOR)
            painter.setPen(QColor(icon_color))
            # 최저온도 아래, 요일 위에 배치해 하단 안정감을 확보
            icon_rect = QRectF(rect.left(), rect.bottom() + self.ICON_TOP_GAP, rect.width(), 16)
            painter.drawText(
                icon_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                icon_text,
            )

    def draw(self, painter: QPainter):
        if not self._data:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return

        chart_rect = self._calc_chart_rect()
        item_rects = self._calc_item_rects(chart_rect)
        if not item_rects:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return

        normalized = self._normalize_range()
        if normalized is None:
            painter.setPen(QColor(self._style.SUB_TEXT_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return
        min_temp, max_temp = normalized

        self._draw_bars(painter, item_rects, min_temp, max_temp)
        self._draw_labels(painter, item_rects, min_temp, max_temp)
        self._draw_icons(painter, item_rects)
