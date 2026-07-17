from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.styles import MainStyles


class WeatherAirQualityCard(QFrame):
    EMPTY_TEXT = "데이터 없음"
    COLOR_TEXT_MAIN = "#2D3748"
    COLOR_TEXT_SUB = "#718096"
    CARD_STYLE = MainStyles.CARD
    CAPTION_STYLE = MainStyles.TXT_CAPTION
    STATUS_STYLE = MainStyles.TXT_LABEL_BOLD
    CHART_BG_STYLE = "QFrame { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; }"
    BAR_TRACK_STYLE = "QFrame { background:#EDF2F7; border:none; border-radius:4px; }"
    FORECAST_TRACK_STYLE = (
        "QFrame { background:#FAF5FF; border:1px dashed #B794F4; border-radius:4px; }"
    )
    BAR_MIN_HEIGHT = 2
    BAR_MAX_HEIGHT = 48
    TIME_LABEL_EVERY = 2
    SUB_BAR_MAX_HEIGHT = 28
    SUB_TIME_LABEL_EVERY = 4

    AQI_LEVELS = [
        (30, "매우좋음", "#2F80ED"),  # 기상청 톤(청색)
        (80, "좋음", "#27AE60"),      # 녹색
        (120, "보통", "#F2C94C"),     # 황색
        (200, "나쁨", "#F2994A"),     # 주황
        (10_000, "아주나쁨", "#EB5757"),  # 적색
    ]

    def __init__(self, title: str = "대기질", parent=None, embedded: bool = False):
        super().__init__(parent)
        self._title = title
        self._embedded = bool(embedded)
        self._bar_items = []
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(
            "QFrame { background:transparent; border:none; }"
            if self._embedded
            else self.CARD_STYLE
        )
        root = QVBoxLayout(self)
        if self._embedded:
            root.setContentsMargins(0, 0, 0, 0)
        else:
            root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        if not self._embedded:
            lbl_title = QLabel(self._title)
            lbl_title.setStyleSheet(MainStyles.TXT_CARD_TITLE)
            root.addWidget(lbl_title)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.lbl_now = QLabel("현재 AQI —")
        self.lbl_now.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH)
        self.lbl_status = QLabel(self.EMPTY_TEXT)
        self.lbl_status.setStyleSheet(self.STATUS_STYLE + f" color:{self.COLOR_TEXT_MAIN};")
        self.lbl_caption = QLabel("")
        self.lbl_caption.setWordWrap(True)
        self.lbl_caption.setStyleSheet(self.CAPTION_STYLE)
        header.addWidget(self.lbl_now)
        header.addWidget(self.lbl_status)
        header.addStretch()
        root.addLayout(header)
        root.addWidget(self.lbl_caption)

        pm_row = QHBoxLayout()
        pm_row.setContentsMargins(0, 0, 0, 0)
        pm_row.setSpacing(10)
        self.lbl_pm25 = QLabel("PM2.5 —")
        self.lbl_pm25.setStyleSheet(MainStyles.TXT_BODY + f" color:{self.COLOR_TEXT_MAIN};")
        self.lbl_pm10 = QLabel("PM10 —")
        self.lbl_pm10.setStyleSheet(MainStyles.TXT_BODY + f" color:{self.COLOR_TEXT_MAIN};")
        pm_row.addWidget(self.lbl_pm25)
        pm_row.addWidget(self.lbl_pm10)
        pm_row.addStretch()
        root.addLayout(pm_row)

        self.chart_wrap = QFrame()
        self.chart_wrap.setStyleSheet(self.CHART_BG_STYLE)
        chart_lay = QHBoxLayout(self.chart_wrap)
        chart_lay.setContentsMargins(10, 8, 10, 8)
        chart_lay.setSpacing(6)
        self._bars_layout = chart_lay
        root.addWidget(self.chart_wrap)

        self.forecast_wrap = QFrame()
        self.forecast_wrap.setStyleSheet(self.CHART_BG_STYLE)
        fc_root = QVBoxLayout(self.forecast_wrap)
        fc_root.setContentsMargins(8, 6, 8, 6)
        fc_root.setSpacing(6)
        self.lbl_fc_head = QLabel("24시간 예보 PM (Open-Meteo CAMS, µg/m³)")
        self.lbl_fc_head.setStyleSheet(MainStyles.TXT_LABEL_BOLD + f" color:{self.COLOR_TEXT_MAIN};")
        fc_root.addWidget(self.lbl_fc_head)
        self.fc_pm25_chart = QFrame()
        fc_pm25_lay = QHBoxLayout(self.fc_pm25_chart)
        fc_pm25_lay.setContentsMargins(2, 0, 2, 0)
        fc_pm25_lay.setSpacing(4)
        self._fc_pm25_layout = fc_pm25_lay
        fc_root.addWidget(self.fc_pm25_chart)
        self.fc_pm10_chart = QFrame()
        fc_pm10_lay = QHBoxLayout(self.fc_pm10_chart)
        fc_pm10_lay.setContentsMargins(2, 0, 2, 0)
        fc_pm10_lay.setSpacing(4)
        self._fc_pm10_layout = fc_pm10_lay
        fc_root.addWidget(self.fc_pm10_chart)
        self.forecast_wrap.setVisible(False)
        root.addWidget(self.forecast_wrap)

        self.pm25_wrap = QFrame()
        self.pm25_wrap.setStyleSheet(self.CHART_BG_STYLE)
        pm25_root = QVBoxLayout(self.pm25_wrap)
        pm25_root.setContentsMargins(8, 6, 8, 6)
        pm25_root.setSpacing(4)
        self.lbl_pm25_title = QLabel("PM2.5")
        self.lbl_pm25_title.setStyleSheet(MainStyles.TXT_LABEL_BOLD + f" color:{self.COLOR_TEXT_MAIN};")
        pm25_root.addWidget(self.lbl_pm25_title)
        self.pm25_chart = QFrame()
        pm25_lay = QHBoxLayout(self.pm25_chart)
        pm25_lay.setContentsMargins(2, 0, 2, 0)
        pm25_lay.setSpacing(4)
        self._pm25_layout = pm25_lay
        pm25_root.addWidget(self.pm25_chart)
        root.addWidget(self.pm25_wrap)

        self.pm10_wrap = QFrame()
        self.pm10_wrap.setStyleSheet(self.CHART_BG_STYLE)
        pm10_root = QVBoxLayout(self.pm10_wrap)
        pm10_root.setContentsMargins(8, 6, 8, 6)
        pm10_root.setSpacing(4)
        self.lbl_pm10_title = QLabel("PM10")
        self.lbl_pm10_title.setStyleSheet(MainStyles.TXT_LABEL_BOLD + f" color:{self.COLOR_TEXT_MAIN};")
        pm10_root.addWidget(self.lbl_pm10_title)
        self.pm10_chart = QFrame()
        pm10_lay = QHBoxLayout(self.pm10_chart)
        pm10_lay.setContentsMargins(2, 0, 2, 0)
        pm10_lay.setSpacing(4)
        self._pm10_layout = pm10_lay
        pm10_root.addWidget(self.pm10_chart)
        root.addWidget(self.pm10_wrap)

        legend = QLabel(
            "관측 AQI 막대: 매우좋음~아주나쁨 색상 · "
            "예보 막대: 보라(PM2.5)·주황(PM10), 모델값"
        )
        legend.setStyleSheet(self.CAPTION_STYLE)
        legend.setWordWrap(True)
        root.addWidget(legend)

    def _resolve_level(self, value: float):
        for threshold, label, color in self.AQI_LEVELS:
            if value <= threshold:
                return label, color
        return "아주나쁨", "#EB5757"

    def _clear_bars(self):
        while self._bars_layout.count():
            item = self._bars_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._bar_items.clear()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _build_bar_item(self, idx: int, time_text: str, value: float, max_value: float):
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        lbl_val = QLabel(f"{int(round(value))}")
        lbl_val.setStyleSheet(MainStyles.TXT_CAPTION + f" color:{self.COLOR_TEXT_MAIN};")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(lbl_val)

        track = QFrame()
        track.setFixedWidth(10)
        track.setFixedHeight(self.BAR_MAX_HEIGHT)
        track.setStyleSheet(self.BAR_TRACK_STYLE)
        track_lay = QVBoxLayout(track)
        track_lay.setContentsMargins(0, 0, 0, 0)
        track_lay.setSpacing(0)
        track_lay.addStretch()

        bar_h = self.BAR_MIN_HEIGHT
        if max_value > 0:
            bar_h = int((max(0.0, value) / max_value) * self.BAR_MAX_HEIGHT)
            bar_h = max(self.BAR_MIN_HEIGHT, min(self.BAR_MAX_HEIGHT, bar_h))
        _, color = self._resolve_level(value)
        fill = QFrame()
        fill.setFixedHeight(bar_h)
        fill.setStyleSheet(f"QFrame {{ background:{color}; border:none; border-radius:4px; }}")
        track_lay.addWidget(fill)
        lay.addWidget(track, 0, Qt.AlignmentFlag.AlignHCenter)

        show_time = (idx % self.TIME_LABEL_EVERY) == 0
        lbl_time = QLabel(time_text if show_time else "")
        lbl_time.setStyleSheet(MainStyles.TXT_CAPTION + f" color:{self.COLOR_TEXT_SUB};")
        lbl_time.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(lbl_time)
        return host

    def _build_forecast_sub_bar_item(
        self, idx: int, time_text: str, value: float, max_value: float, color: str
    ):
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        track = QFrame()
        track.setFixedWidth(8)
        track.setFixedHeight(self.SUB_BAR_MAX_HEIGHT)
        track.setStyleSheet(self.FORECAST_TRACK_STYLE)
        track_lay = QVBoxLayout(track)
        track_lay.setContentsMargins(0, 0, 0, 0)
        track_lay.setSpacing(0)
        track_lay.addStretch()

        bar_h = self.BAR_MIN_HEIGHT
        if max_value > 0:
            bar_h = int((max(0.0, value) / max_value) * self.SUB_BAR_MAX_HEIGHT)
            bar_h = max(self.BAR_MIN_HEIGHT, min(self.SUB_BAR_MAX_HEIGHT, bar_h))
        fill = QFrame()
        fill.setFixedHeight(bar_h)
        fill.setStyleSheet(f"QFrame {{ background:{color}; border:none; border-radius:3px; }}")
        track_lay.addWidget(fill)
        lay.addWidget(track, 0, Qt.AlignmentFlag.AlignHCenter)

        show_time = (idx % self.SUB_TIME_LABEL_EVERY) == 0
        lbl_time = QLabel(time_text if show_time else "")
        lbl_time.setStyleSheet(MainStyles.TXT_CAPTION + f" color:{self.COLOR_TEXT_SUB};")
        lbl_time.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(lbl_time)
        return host

    def _build_sub_bar_item(self, idx: int, time_text: str, value: float, max_value: float, color: str):
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        track = QFrame()
        track.setFixedWidth(8)
        track.setFixedHeight(self.SUB_BAR_MAX_HEIGHT)
        track.setStyleSheet(self.BAR_TRACK_STYLE)
        track_lay = QVBoxLayout(track)
        track_lay.setContentsMargins(0, 0, 0, 0)
        track_lay.setSpacing(0)
        track_lay.addStretch()

        bar_h = self.BAR_MIN_HEIGHT
        if max_value > 0:
            bar_h = int((max(0.0, value) / max_value) * self.SUB_BAR_MAX_HEIGHT)
            bar_h = max(self.BAR_MIN_HEIGHT, min(self.SUB_BAR_MAX_HEIGHT, bar_h))
        fill = QFrame()
        fill.setFixedHeight(bar_h)
        fill.setStyleSheet(f"QFrame {{ background:{color}; border:none; border-radius:3px; }}")
        track_lay.addWidget(fill)
        lay.addWidget(track, 0, Qt.AlignmentFlag.AlignHCenter)

        show_time = (idx % self.SUB_TIME_LABEL_EVERY) == 0
        lbl_time = QLabel(time_text if show_time else "")
        lbl_time.setStyleSheet(MainStyles.TXT_CAPTION + f" color:{self.COLOR_TEXT_SUB};")
        lbl_time.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(lbl_time)
        return host

    def _render_sub_chart(self, layout, rows, value_key: str, color: str):
        self._clear_layout(layout)
        max_value = max([float(r.get(value_key, 0) or 0) for r in rows], default=0.0)
        if max_value <= 0:
            max_value = 1.0
        for idx, row in enumerate(rows):
            v = float(row.get(value_key, 0) or 0)
            item = self._build_sub_bar_item(idx, str(row.get("time") or ""), v, max_value, color)
            layout.addWidget(item, 1)

    def _render_forecast_sub_chart(self, layout, rows, value_key: str, color: str):
        self._clear_layout(layout)
        max_value = max([float(r.get(value_key, 0) or 0) for r in rows], default=0.0)
        if max_value <= 0:
            max_value = 1.0
        for idx, row in enumerate(rows):
            v = float(row.get(value_key, 0) or 0)
            item = self._build_forecast_sub_bar_item(
                idx, str(row.get("time") or ""), v, max_value, color
            )
            layout.addWidget(item, 1)

    def set_data(self, data: dict):
        payload = data or {}
        aqi = payload.get("aqi")
        if aqi in (None, ""):
            aqi = 0
        try:
            current_aqi = float(aqi)
        except (TypeError, ValueError):
            current_aqi = 0.0

        status = str(payload.get("status") or self._resolve_level(current_aqi)[0])
        caption = str(payload.get("caption") or "")
        pm25 = payload.get("pm25")
        pm10 = payload.get("pm10")
        hourly = list(payload.get("hourly") or [])
        forecast = list(payload.get("forecast") or [])
        if not hourly:
            # 단일값만 들어오면 24시간 동일값으로 fallback
            hourly = [
                {"time": f"{h:02d}:00", "aqi": current_aqi, "pm25": 0.0, "pm10": 0.0}
                for h in range(24)
            ]

        self.lbl_now.setText(f"현재 AQI {int(round(current_aqi))}")
        self.lbl_status.setText(status)
        self.lbl_caption.setText(caption)
        self.lbl_pm25.setText(f"PM2.5 {pm25 if pm25 not in (None, '') else '—'}")
        self.lbl_pm10.setText(f"PM10 {pm10 if pm10 not in (None, '') else '—'}")
        self.lbl_pm25_title.setText(f"PM2.5 ({pm25 if pm25 not in (None, '') else '—'})")
        self.lbl_pm10_title.setText(f"PM10 ({pm10 if pm10 not in (None, '') else '—'})")

        _, color = self._resolve_level(current_aqi)
        self.lbl_status.setStyleSheet(self.STATUS_STYLE + f" color:{color};")

        rows = []
        for row in hourly:
            try:
                v = float(row.get("aqi", 0))
            except (TypeError, ValueError):
                v = 0.0
            try:
                pm25_v = float(row.get("pm25", 0))
            except (TypeError, ValueError):
                pm25_v = 0.0
            try:
                pm10_v = float(row.get("pm10", 0))
            except (TypeError, ValueError):
                pm10_v = 0.0
            rows.append(
                {
                    "time": str(row.get("time") or ""),
                    "aqi": max(0.0, v),
                    "pm25": max(0.0, pm25_v),
                    "pm10": max(0.0, pm10_v),
                }
            )
        max_value = max([r["aqi"] for r in rows], default=0.0)
        if max_value <= 0:
            max_value = 1.0

        self._clear_bars()
        for idx, row in enumerate(rows):
            item = self._build_bar_item(idx, row["time"], row["aqi"], max_value)
            self._bars_layout.addWidget(item, 1)
            self._bar_items.append(item)

        self._render_sub_chart(self._pm25_layout, rows, "pm25", "#4A90E2")
        self._render_sub_chart(self._pm10_layout, rows, "pm10", "#27AE60")

        fc_rows: list = []
        for row in forecast:
            try:
                p2 = float(row.get("pm25", 0) or 0)
            except (TypeError, ValueError):
                p2 = 0.0
            try:
                p1 = float(row.get("pm10", 0) or 0)
            except (TypeError, ValueError):
                p1 = 0.0
            fc_rows.append(
                {
                    "time": str(row.get("time") or ""),
                    "pm25": max(0.0, p2),
                    "pm10": max(0.0, p1),
                }
            )
        has_fc = len(fc_rows) > 0
        self.forecast_wrap.setVisible(has_fc)
        if has_fc:
            self._render_forecast_sub_chart(self._fc_pm25_layout, fc_rows, "pm25", "#805AD5")
            self._render_forecast_sub_chart(self._fc_pm10_layout, fc_rows, "pm10", "#DD6B20")
        else:
            self._clear_layout(self._fc_pm25_layout)
            self._clear_layout(self._fc_pm10_layout)
