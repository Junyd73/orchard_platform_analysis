from datetime import datetime
from pathlib import Path
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QWidget


class WeatherSunArcWidget(QWidget):
    EMPTY_TEXT = "일출/일몰 데이터 없음"
    TEXT_COLOR = "#2D3748"
    SUB_TEXT_COLOR = "#718096"

    ARC_SIDE_MARGIN = 22
    ARC_TOP_MARGIN = 24
    ARC_WIDTH_RATIO = 0.84
    ARC_MAX_WIDTH_PER_HEIGHT = 1.68
    ARC_END_DASH_DEG = 18
    CENTER_TEXT_TOP_OFFSET = 16

    DAY_ARC_TRACK_COLOR = "#EAD7B4"
    DAY_ARC_COLOR = "#F6AD55"
    DAY_ICON_COLOR = "#F6AD55"
    DAY_ICON_GLOW = "#FBD38D"

    NIGHT_ARC_TRACK_COLOR = "#8A94C4"
    NIGHT_ARC_COLOR = "#5B67A5"
    NIGHT_ICON_COLOR = "#D8DEFF"
    NIGHT_ICON_GLOW = "#AAB6F7"

    MARKER_LEFT_COLOR = "#F59E0B"
    MARKER_RIGHT_COLOR = "#DD6B20"
    CENTER_ICON_RADIUS = 7
    CENTER_ICON_GLOW_RADIUS = 16

    BADGE_HEIGHT = 30
    BADGE_BOTTOM_MARGIN = 10
    LABELS_GAP = 10

    # 첨부 원본(좌:낮, 우:밤) 그대로 사용
    EARTH_SOURCE_IMAGE = Path(__file__).resolve().parents[2] / "resources" / "weather" / "earth_source.png"
    EARTH_SOURCE_SPLIT_RATIO = 0.5
    EARTH_WIDTH_RATIO = 0.58
    EARTH_HEIGHT_RATIO = 0.29
    EARTH_IMAGE_SCALE = 0.49
    EARTH_ARC_WIDTH_RATIO = 0.56
    EARTH_VISIBLE_HEIGHT_RATIO = 0.50
    EARTH_VERTICAL_OFFSET = 8
    EARTH_PILL_GAP = 12
    EARTH_BOTTOM_FADE_START_RATIO = 0.52
    BG_KEY_THRESHOLD = 18
    BBOX_SCAN_HEIGHT_RATIO = 0.82

    FALLBACK_DAY_TOP = "#BEE3FF"
    FALLBACK_DAY_BOTTOM = "#6FAFE6"
    FALLBACK_NIGHT_TOP = "#3F4F87"
    FALLBACK_NIGHT_BOTTOM = "#1F2648"
    FALLBACK_BORDER_DAY = "#9FB4CC"
    FALLBACK_BORDER_NIGHT = "#7D8DC4"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {}
        self.setMinimumHeight(280)
        self._earth_source_pm = QPixmap(str(self.EARTH_SOURCE_IMAGE))
        self._earth_day_pm, self._earth_night_pm = self._build_earth_pixmaps()

    def set_data(self, data: dict):
        self._data = dict(data or {})
        self.update()

    def _parse_hhmm(self, text: str):
        s = str(text or "").strip()
        if ":" not in s:
            return None
        try:
            hh, mm = s.split(":", 1)
            h = int(hh)
            m = int(mm)
        except (TypeError, ValueError):
            return None
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return (h * 60) + m

    def _parse_duration_minutes(self, text: str):
        s = str(text or "")
        if not s:
            return None
        digits = ""
        h = None
        m = None
        for ch in s:
            if ch.isdigit():
                digits += ch
            elif digits:
                if ch == "시":
                    h = int(digits)
                elif ch == "분":
                    m = int(digits)
                digits = ""
        if h is None and m is None:
            return None
        return ((h or 0) * 60) + (m or 0)

    def _is_day_mode(self, sunrise_min, sunset_min):
        if sunrise_min is None or sunset_min is None:
            return True
        now = datetime.now()
        now_min = (now.hour * 60) + now.minute
        if sunrise_min <= sunset_min:
            return sunrise_min <= now_min < sunset_min
        return now_min >= sunrise_min or now_min < sunset_min

    def _calc_day_minutes(self, sunrise_min, sunset_min, daylight_text: str):
        parsed = self._parse_duration_minutes(daylight_text)
        if parsed is not None:
            return max(0, min(1440, parsed))
        if sunrise_min is None or sunset_min is None:
            return 0
        if sunset_min >= sunrise_min:
            return sunset_min - sunrise_min
        return (1440 - sunrise_min) + sunset_min

    @staticmethod
    def _calc_night_minutes(day_minutes: int):
        return max(0, 1440 - int(day_minutes or 0))

    @staticmethod
    def _format_duration(minutes: int):
        total = max(0, int(minutes or 0))
        h, m = divmod(total, 60)
        return f"{h}시간 {m}분"

    def _build_mode_state(self):
        sunrise = str(self._data.get("sunrise") or "").strip()
        sunset = str(self._data.get("sunset") or "").strip()
        daylight_text = str(self._data.get("daylight") or "").strip()
        sunrise_min = self._parse_hhmm(sunrise)
        sunset_min = self._parse_hhmm(sunset)
        day_minutes = self._calc_day_minutes(sunrise_min, sunset_min, daylight_text)
        night_minutes = self._calc_night_minutes(day_minutes)
        is_day = self._is_day_mode(sunrise_min, sunset_min)

        if is_day:
            return {
                "is_day": True,
                "main_text": daylight_text or self._format_duration(day_minutes),
                "sub_text": "낮 길이",
                "arc_track_color": self.DAY_ARC_TRACK_COLOR,
                "arc_color": self.DAY_ARC_COLOR,
                "icon_text": "☀",
                "icon_color": self.DAY_ICON_COLOR,
                "icon_glow": self.DAY_ICON_GLOW,
            }
        return {
            "is_day": False,
            "main_text": self._format_duration(night_minutes),
            "sub_text": "밤 길이",
            "arc_track_color": self.NIGHT_ARC_TRACK_COLOR,
            "arc_color": self.NIGHT_ARC_COLOR,
            "icon_text": "☾",
            "icon_color": self.NIGHT_ICON_COLOR,
            "icon_glow": self.NIGHT_ICON_GLOW,
        }

    def _arc_rect(self, baseline_y: float):
        full_w = max(20, self.width() - (self.ARC_SIDE_MARGIN * 2))
        max_h_by_top = max(36.0, (baseline_y - self.ARC_TOP_MARGIN) * 2.0)
        target_w = full_w * self.ARC_WIDTH_RATIO
        max_curve_w = max_h_by_top * self.ARC_MAX_WIDTH_PER_HEIGHT
        w = max(20.0, min(target_w, max_curve_w))
        h = min(max_h_by_top, w / self.ARC_MAX_WIDTH_PER_HEIGHT)
        x = (self.width() - w) / 2.0
        y = baseline_y - (h / 2.0)
        if y < self.ARC_TOP_MARGIN:
            y = self.ARC_TOP_MARGIN
        return QRectF(x, y, w, h)

    def _draw_empty(self, painter: QPainter):
        painter.setPen(QColor(self.SUB_TEXT_COLOR))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)

    def _build_earth_pixmaps(self):
        pm = self._earth_source_pm
        if pm.isNull():
            return QPixmap(), QPixmap()
        img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        split_x = int(img.width() * self.EARTH_SOURCE_SPLIT_RATIO)
        day_img = img.copy(0, 0, split_x, img.height())
        night_img = img.copy(split_x, 0, img.width() - split_x, img.height())
        return self._extract_earth_half(day_img), self._extract_earth_half(night_img)

    def _extract_earth_half(self, half_img: QImage):
        transparent = self._remove_corner_black_background(half_img)
        bbox = self._largest_alpha_component_bbox(transparent)
        if bbox is None:
            bbox = self._alpha_bbox(transparent)
        if bbox is None:
            return QPixmap()
        cropped = transparent.copy(*bbox)
        return QPixmap.fromImage(cropped)

    def _remove_corner_black_background(self, image: QImage):
        img = image.convertToFormat(QImage.Format.Format_ARGB32)
        w = img.width()
        h = img.height()
        if w <= 0 or h <= 0:
            return img
        q = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])
        visited = set()
        threshold = self.BG_KEY_THRESHOLD

        while q:
            x, y = q.popleft()
            if (x, y) in visited:
                continue
            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            visited.add((x, y))
            c = img.pixelColor(x, y)
            if c.red() > threshold or c.green() > threshold or c.blue() > threshold:
                continue
            img.setPixelColor(x, y, QColor(c.red(), c.green(), c.blue(), 0))
            q.append((x + 1, y))
            q.append((x - 1, y))
            q.append((x, y + 1))
            q.append((x, y - 1))
        return img

    def _alpha_bbox(self, image: QImage):
        w = image.width()
        h = image.height()
        y_limit = max(1, int(h * self.BBOX_SCAN_HEIGHT_RATIO))
        min_x = w
        min_y = y_limit
        max_x = -1
        max_y = -1

        for y in range(y_limit):
            for x in range(w):
                if image.pixelColor(x, y).alpha() > 0:
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y
        if max_x < min_x or max_y < min_y:
            return None
        pad = 2
        min_x = max(0, min_x - pad)
        min_y = max(0, min_y - pad)
        max_x = min(w - 1, max_x + pad)
        max_y = min(h - 1, max_y + pad)
        return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

    def _largest_alpha_component_bbox(self, image: QImage):
        w = image.width()
        h = image.height()
        if w <= 0 or h <= 0:
            return None

        visited = set()
        best_area = 0
        best_bbox = None

        for y in range(h):
            for x in range(w):
                if (x, y) in visited:
                    continue
                if image.pixelColor(x, y).alpha() == 0:
                    continue

                q = deque([(x, y)])
                visited.add((x, y))
                area = 0
                min_x = x
                max_x = x
                min_y = y
                max_y = y

                while q:
                    cx, cy = q.popleft()
                    area += 1
                    if cx < min_x:
                        min_x = cx
                    if cx > max_x:
                        max_x = cx
                    if cy < min_y:
                        min_y = cy
                    if cy > max_y:
                        max_y = cy

                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if nx < 0 or ny < 0 or nx >= w or ny >= h:
                            continue
                        if (nx, ny) in visited:
                            continue
                        if image.pixelColor(nx, ny).alpha() == 0:
                            continue
                        visited.add((nx, ny))
                        q.append((nx, ny))

                if area > best_area:
                    best_area = area
                    best_bbox = (min_x, min_y, max_x, max_y)

        if best_bbox is None:
            return None

        min_x, min_y, max_x, max_y = best_bbox
        pad = 2
        min_x = max(0, min_x - pad)
        min_y = max(0, min_y - pad)
        max_x = min(w - 1, max_x + pad)
        max_y = min(h - 1, max_y + pad)
        return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

    def _calc_earth_rect(self, arc_rect: QRectF, baseline_y: float):
        earth_w = max(130.0, arc_rect.width() * self.EARTH_WIDTH_RATIO)
        earth_h = max(42.0, earth_w * self.EARTH_HEIGHT_RATIO)
        earth_x = (self.width() - earth_w) / 2.0
        earth_y = baseline_y - (earth_h * 0.10)
        return QRectF(earth_x, earth_y, earth_w, earth_h)

    def _draw_fallback_earth(self, painter: QPainter, earth_rect: QRectF, mode_state: dict):
        is_day = mode_state.get("is_day", True)
        top = self.FALLBACK_DAY_TOP if is_day else self.FALLBACK_NIGHT_TOP
        bottom = self.FALLBACK_DAY_BOTTOM if is_day else self.FALLBACK_NIGHT_BOTTOM
        border = self.FALLBACK_BORDER_DAY if is_day else self.FALLBACK_BORDER_NIGHT

        grad = QRadialGradient(
            QPointF(earth_rect.center().x(), earth_rect.top() + earth_rect.height() * 0.35),
            earth_rect.width() * 0.6,
        )
        grad.setColorAt(0.0, QColor(top))
        grad.setColorAt(1.0, QColor(bottom))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawChord(earth_rect, 0, 180 * 16)

        painter.setPen(QPen(QColor(border), 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(earth_rect, 0, 180 * 16)

    def _apply_bottom_alpha_fade(self, pixmap: QPixmap):
        if pixmap.isNull():
            return pixmap
        img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        h = img.height()
        if h <= 0:
            return pixmap

        fade_start = max(0.0, min(1.0, self.EARTH_BOTTOM_FADE_START_RATIO))
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(0, 0, 0, 255))
        grad.setColorAt(fade_start, QColor(0, 0, 0, 255))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        p = QPainter(img)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.fillRect(img.rect(), grad)
        p.end()
        return QPixmap.fromImage(img)

    def _draw_earth_image(self, painter: QPainter, mode_state: dict, arc_rect: QRectF, baseline_y: float, badge_top: float):
        pm = self._earth_day_pm if mode_state.get("is_day", True) else self._earth_night_pm
        if pm.isNull():
            earth_rect = self._calc_earth_rect(arc_rect, baseline_y)
            self._draw_fallback_earth(painter, earth_rect, mode_state)
            return

        # 지구 구도를 arc 기준으로 맞추기 위해 폭을 arc 비율로 계산하고 원본 비율은 유지한다.
        aspect = float(pm.height()) / max(1.0, float(pm.width()))
        earth_w = arc_rect.width() * self.EARTH_ARC_WIDTH_RATIO
        earth_h = earth_w * aspect
        visible_h = earth_h * self.EARTH_VISIBLE_HEIGHT_RATIO
        earth_x = (self.width() - earth_w) / 2.0
        earth_y = baseline_y - (visible_h * 0.10) - self.EARTH_VERTICAL_OFFSET
        max_earth_bottom = badge_top - self.EARTH_PILL_GAP
        if (earth_y + visible_h) > max_earth_bottom:
            earth_y = max_earth_bottom - visible_h
        earth_rect = QRectF(earth_x, earth_y, earth_w, visible_h)
        src_rect = QRectF(0, 0, pm.width(), pm.height() * self.EARTH_VISIBLE_HEIGHT_RATIO)
        source = pm.copy(src_rect.toRect())
        scaled = source.scaled(
            max(1, int(round(earth_rect.width()))),
            max(1, int(round(earth_rect.height()))),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        faded = self._apply_bottom_alpha_fade(scaled)
        painter.drawPixmap(earth_rect.topLeft(), faded)

    def _draw_arc(self, painter: QPainter, arc_rect: QRectF, mode_state: dict, baseline_y: float):
        track_pen = QPen(QColor(mode_state["arc_track_color"]), 2)
        track_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(arc_rect, 0, 180 * 16)

        arc_pen = QPen(QColor(mode_state["arc_color"]), 3)
        painter.setPen(arc_pen)
        dash_deg = self.ARC_END_DASH_DEG
        solid_start = dash_deg
        solid_span = 180 - (dash_deg * 2)
        if solid_span > 0:
            painter.drawArc(arc_rect, solid_start * 16, solid_span * 16)

        connector_pen = QPen(QColor(mode_state["arc_color"]), 2)
        connector_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(connector_pen)
        painter.drawArc(arc_rect, 0, dash_deg * 16)
        painter.drawArc(arc_rect, (180 - dash_deg) * 16, dash_deg * 16)

    def _draw_mode_icon(self, painter: QPainter, arc_rect: QRectF, mode_state: dict):
        progress = 0.5
        icon_x = arc_rect.left() + (arc_rect.width() * progress)
        icon_y = arc_rect.bottom() - (arc_rect.height() * (4 * progress * (1 - progress)))

        glow = QRadialGradient(QPointF(icon_x, icon_y), self.CENTER_ICON_GLOW_RADIUS)
        glow.setColorAt(0.0, QColor(mode_state["icon_glow"]))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(icon_x, icon_y), self.CENTER_ICON_GLOW_RADIUS, self.CENTER_ICON_GLOW_RADIUS)

        painter.setBrush(QColor(mode_state["icon_color"]))
        painter.drawEllipse(QPointF(icon_x, icon_y), self.CENTER_ICON_RADIUS, self.CENTER_ICON_RADIUS)

        icon_font = QFont()
        icon_font.setPointSize(18)
        painter.setFont(icon_font)
        painter.setPen(QColor(mode_state["icon_color"]))
        painter.drawText(
            QRectF(icon_x - 12, icon_y - 16, 24, 24),
            Qt.AlignmentFlag.AlignCenter,
            mode_state["icon_text"],
        )

    def _draw_center_text(self, painter: QPainter, arc_rect: QRectF, mode_state: dict):
        main_font = QFont()
        main_font.setPointSize(13)
        main_font.setBold(True)
        painter.setFont(main_font)
        painter.setPen(QColor(self.TEXT_COLOR))
        painter.drawText(
            QRectF(0, arc_rect.top() + self.CENTER_TEXT_TOP_OFFSET, self.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            mode_state["main_text"],
        )

        sub_font = QFont()
        sub_font.setPointSize(9)
        painter.setFont(sub_font)
        painter.setPen(QColor(self.SUB_TEXT_COLOR))
        painter.drawText(
            QRectF(0, arc_rect.top() + self.CENTER_TEXT_TOP_OFFSET + 20, self.width(), 18),
            Qt.AlignmentFlag.AlignCenter,
            mode_state["sub_text"],
        )

    def _draw_sunrise_sunset_labels(self, painter: QPainter, arc_rect: QRectF, baseline_y: float, labels_y: float, sunrise: str, sunset: str):
        painter.setPen(QPen(QColor(self.MARKER_LEFT_COLOR), 2))
        painter.drawLine(QPointF(arc_rect.left(), baseline_y - 8), QPointF(arc_rect.left(), baseline_y + 8))
        painter.setPen(QPen(QColor(self.MARKER_RIGHT_COLOR), 2))
        painter.drawLine(QPointF(arc_rect.right(), baseline_y - 8), QPointF(arc_rect.right(), baseline_y + 8))

        icon_font = QFont()
        icon_font.setPointSize(11)
        painter.setFont(icon_font)
        painter.setPen(QColor(self.MARKER_LEFT_COLOR))
        painter.drawText(QRectF(arc_rect.left() - 16, baseline_y + 8, 32, 16), Qt.AlignmentFlag.AlignCenter, "☀")
        painter.setPen(QColor(self.MARKER_RIGHT_COLOR))
        painter.drawText(QRectF(arc_rect.right() - 16, baseline_y + 8, 32, 16), Qt.AlignmentFlag.AlignCenter, "🌇")

        sub_font = QFont()
        sub_font.setPointSize(9)
        painter.setFont(sub_font)
        painter.setPen(QColor(self.SUB_TEXT_COLOR))
        # 아이콘 아래에 라벨이 오도록 y 기준을 아이콘 하단 기준으로 재배치한다.
        text_top = baseline_y + 24
        painter.drawText(
            QRectF(arc_rect.left() - 40, text_top, 80, 34),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            f"일출\n{sunrise}",
        )
        painter.drawText(
            QRectF(arc_rect.right() - 40, text_top, 80, 34),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            f"일몰\n{sunset}",
        )

    def _draw_golden_hour_pill(self, painter: QPainter, badge_top: float, golden_morning: str, golden_evening: str):
        if not (golden_morning and golden_evening):
            return
        badge_rect = QRectF(
            max(10.0, self.width() * 0.18),
            badge_top,
            max(200.0, self.width() * 0.64),
            self.BADGE_HEIGHT,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EDF2F7"))
        painter.drawRoundedRect(badge_rect, 14, 14)
        badge_font = QFont()
        badge_font.setPointSize(9)
        painter.setFont(badge_font)
        painter.setPen(QColor(self.SUB_TEXT_COLOR))
        painter.drawText(
            badge_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"✨ 골든아워(아침) {golden_morning}   |   ✨ 골든아워(저녁) {golden_evening}",
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        sunrise = str(self._data.get("sunrise") or "").strip()
        sunset = str(self._data.get("sunset") or "").strip()
        golden_morning = str(self._data.get("golden_morning") or "").strip()
        golden_evening = str(self._data.get("golden_evening") or "").strip()
        if not (sunrise and sunset):
            self._draw_empty(painter)
            return

        mode_state = self._build_mode_state()
        badge_top = self.height() - self.BADGE_HEIGHT - self.BADGE_BOTTOM_MARGIN
        labels_y = badge_top - 54
        baseline_y = labels_y - self.LABELS_GAP
        arc_rect = self._arc_rect(baseline_y)

        self._draw_arc(painter, arc_rect, mode_state, baseline_y)
        self._draw_earth_image(painter, mode_state, arc_rect, baseline_y, badge_top)
        self._draw_mode_icon(painter, arc_rect, mode_state)
        self._draw_center_text(painter, arc_rect, mode_state)
        self._draw_sunrise_sunset_labels(painter, arc_rect, baseline_y, labels_y, sunrise, sunset)
        self._draw_golden_hour_pill(painter, badge_top, golden_morning, golden_evening)
