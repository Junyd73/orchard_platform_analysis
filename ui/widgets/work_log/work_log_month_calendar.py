"""
영농일지 월간 캘린더 — paintCell에서는 메모리 캐시만 그린다(DB 조회 금지).
"""
from __future__ import annotations

from PyQt6.QtCore import QDate, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QCalendarWidget

from ui.styles import MainStyles

# 날씨 코드 → 아이콘 (WT01). 미매핑은 흐림 계열로 안전 처리.
_WEATHER_ICON_BY_CD = {
    "WT010100": "☀",
    "WT010200": "⛅",
    "WT010300": "☁",
    "WT010400": "☂",
    "WT010500": "🌧",
    "WT010600": "❄",
    "WT010700": "⛈",
    "WT019900": "•",
}

_MSG_FUTURE_DATE = "미래 날짜의 영농일지는 작성할 수 없습니다."

# 셀 레이아웃 상수 (전 셀 동일)
_PAD_X = 6
_PAD_TOP = 4
_PAD_BOTTOM = 5
_DAY_LINE_H = 16
_BODY_LINE_H = 13


def weather_icon_for_cd(weather_cd: str, weather_nm: str = "") -> str:
    cd = str(weather_cd or "").strip()
    if cd in _WEATHER_ICON_BY_CD:
        return _WEATHER_ICON_BY_CD[cd]
    nm = str(weather_nm or "")
    if "비" in nm and "눈" in nm:
        return "🌧"
    if "비" in nm:
        return "☂"
    if "눈" in nm:
        return "❄"
    if "구름" in nm or "흐림" in nm:
        return "☁"
    if "맑" in nm:
        return "☀"
    if "뇌" in nm:
        return "⛈"
    return ""


def _fmt_won(amount) -> str:
    try:
        n = int(round(float(amount or 0)))
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return ""
    if n >= 10000:
        return f"{n // 10000}만"
    return f"{n:,}"


class WorkLogMonthCalendar(QCalendarWidget):
    """월간 영농일지 셀 확장 캘린더."""

    dayActivated = pyqtSignal(QDate)
    futureDateBlocked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._day_data = {}
        self._selected_date = QDate.currentDate()
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setNavigationBarVisible(False)
        self.setStyleSheet(MainStyles.WORK_LOG_MONTH_CALENDAR)
        self.setMinimumHeight(360)
        self.setMaximumDate(QDate.currentDate())
        self.clicked.connect(self._on_clicked)
        self.activated.connect(self._on_clicked)

    def set_day_data(self, days: dict | None):
        """yyyy-MM-dd → day cell dict."""
        self._day_data = days or {}
        self.updateCells()

    def set_selected_work_date(self, qdate: QDate):
        if not qdate or not qdate.isValid():
            return
        today = QDate.currentDate()
        target = QDate(qdate)
        if target > today:
            target = today
        self._selected_date = target
        self.setSelectedDate(self._selected_date)
        self.updateCells()

    def selected_work_date(self) -> QDate:
        return QDate(self._selected_date)

    def refresh_max_date(self) -> None:
        """자정 경과 등 오늘 기준 재동기화."""
        self.setMaximumDate(QDate.currentDate())
        self.updateCells()

    def _on_clicked(self, qdate: QDate):
        if not qdate.isValid():
            return
        today = QDate.currentDate()
        if qdate > today:
            self.futureDateBlocked.emit(_MSG_FUTURE_DATE)
            # 미래일로 선택 상태가 바뀌지 않도록 복원
            if self._selected_date.isValid() and self._selected_date <= today:
                self.setSelectedDate(self._selected_date)
            self.updateCells()
            return
        self._selected_date = QDate(qdate)
        self.setSelectedDate(self._selected_date)
        self.updateCells()
        self.dayActivated.emit(QDate(qdate))

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        painter.save()
        try:
            self._paint_day_cell(painter, rect, date)
        finally:
            painter.restore()

    def _paint_day_cell(self, painter: QPainter, rect: QRect, date: QDate):
        today = QDate.currentDate()
        in_month = date.month() == self.monthShown() and date.year() == self.yearShown()
        is_future = date > today
        is_selected = in_month and (not is_future) and date == self._selected_date
        is_today = date == today

        key = date.toString("yyyy-MM-dd")
        # 타월·미래일은 상세 정보 미표시
        info = self._day_data.get(key) if (in_month and not is_future) else None

        # 배경
        bg = QColor("#FFFFFF")
        if info:
            if info.get("has_in_progress"):
                bg = QColor(MainStyles.WORK_LOG_CAL_IN_PROGRESS_BG)
            elif info.get("has_work"):
                bg = QColor(MainStyles.WORK_LOG_CAL_HAS_WORK_BG)
        elif is_future or not in_month:
            bg = QColor("#FAFAFA")
        painter.fillRect(rect.adjusted(1, 1, -1, -1), bg)

        # 테두리: 선택 우선, 오늘 겸용이면 내부 파란선으로 구분
        if is_selected:
            pen = QPen(QColor(MainStyles.WORK_LOG_CAL_SELECTED_BORDER), 2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(2, 2, -2, -2))
            if is_today:
                pen2 = QPen(QColor(MainStyles.WORK_LOG_CAL_TODAY_BORDER), 1)
                painter.setPen(pen2)
                painter.drawRect(rect.adjusted(5, 5, -5, -5))
        elif is_today and in_month and not is_future:
            pen = QPen(QColor(MainStyles.WORK_LOG_CAL_TODAY_BORDER), 2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

        # 날짜 글자색 (평일/토/일/타월·미래)
        if (not in_month) or is_future:
            text_color = QColor(MainStyles.WORK_LOG_CAL_MUTED_TEXT)
        else:
            dow = date.dayOfWeek()  # 1=월 … 7=일
            if dow == 6:
                text_color = QColor(MainStyles.WORK_LOG_CAL_SAT_TEXT)
            elif dow == 7:
                text_color = QColor(MainStyles.WORK_LOG_CAL_SUN_TEXT)
            else:
                text_color = QColor(MainStyles.WORK_LOG_CAL_CELL_TEXT)
        muted = QColor(MainStyles.WORK_LOG_CAL_MUTED_TEXT)

        content = rect.adjusted(_PAD_X, _PAD_TOP, -_PAD_X, -_PAD_BOTTOM)
        if content.width() < 20 or content.height() < 18:
            return

        # 1) 날짜 + 날씨
        day_font = QFont(painter.font())
        day_font.setBold(True)
        day_font.setPointSize(10)
        painter.setFont(day_font)
        painter.setPen(text_color)

        weather_icon = ""
        if info:
            weather_icon = weather_icon_for_cd(
                info.get("weather_cd"), info.get("weather_nm")
            )
        top_label = f"{date.day()}"
        if weather_icon:
            top_label = f"{date.day()} {weather_icon}"

        top_rect = QRect(content.left(), content.top(), content.width() - 10, _DAY_LINE_H)
        painter.drawText(
            top_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            top_label,
        )

        if info and info.get("has_issue"):
            painter.setBrush(QColor(MainStyles.WORK_LOG_CAL_ISSUE_DOT))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(content.right() - 2, content.top() + 6), 3, 3)

        # 관찰 경고 점 (우상단 아래쪽) — 색상+숫자
        if info and info.get("has_observation"):
            sev = str(info.get("observation_max_severity") or "")
            if sev == "OS010400":
                oc = QColor(MainStyles.OBS_CAL_DOT_DANGER)
            elif sev == "OS010300":
                oc = QColor(MainStyles.OBS_CAL_DOT_CAUTION)
            elif sev == "OS010200":
                oc = QColor(MainStyles.OBS_CAL_DOT_WATCH)
            else:
                oc = QColor(MainStyles.OBS_CAL_DOT_NORMAL)
            painter.setBrush(oc)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(content.right() - 2, content.top() + 14), 3, 3)

        if not info:
            return

        # 본문: 우선순위 날짜·날씨 → 작업 → 관찰 경고 → 외 n건 → 인력 → 비용
        body_font = QFont(painter.font())
        body_font.setBold(False)
        body_font.setPointSize(9)
        painter.setFont(body_font)
        fm = QFontMetrics(body_font)

        y = content.top() + _DAY_LINE_H + 1
        max_y = content.bottom()
        line_h = _BODY_LINE_H
        text_w = content.width()

        def _draw_line(text: str, color: QColor) -> bool:
            nonlocal y
            if y + line_h > max_y:
                return False
            elided = fm.elidedText(
                text, Qt.TextElideMode.ElideRight, max(8, text_w)
            )
            painter.setPen(color)
            painter.drawText(
                QRect(content.left(), y, text_w, line_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided,
            )
            y += line_h
            return True

        names = list(info.get("work_names") or [])[:2]
        for nm in names:
            if not _draw_line(str(nm) if str(nm).strip() else "-", QColor(MainStyles.WORK_LOG_CAL_CELL_TEXT)):
                return

        # 관찰·재관찰 배지 (작업명 다음 우선)
        obs_n = int(info.get("observation_count") or 0)
        due_n = int(info.get("followup_due_count") or 0)
        overdue_n = int(info.get("followup_overdue_count") or 0)
        if overdue_n > 0:
            if not _draw_line(
                f"재관찰지연 {overdue_n}",
                QColor(MainStyles.OBS_CAL_FOLLOWUP_OVERDUE),
            ):
                return
        elif due_n > 0:
            if not _draw_line(
                f"재관찰 {due_n}",
                QColor(MainStyles.OBS_CAL_FOLLOWUP_DUE),
            ):
                return
        elif obs_n > 0:
            if info.get("has_observation_warning"):
                msg = f"관찰주의 {obs_n}"
                col = QColor(MainStyles.OBS_CAL_DOT_CAUTION)
            else:
                msg = f"관찰 {obs_n}"
                col = QColor(MainStyles.OBS_CAL_DOT_NORMAL)
            if not _draw_line(msg, col):
                return

        extra = int(info.get("extra_work_count") or 0)
        if extra > 0:
            if not _draw_line(f"외 {extra}건", muted):
                return

        res_cnt = int(info.get("resource_count") or 0)
        if res_cnt > 0:
            if not _draw_line(f"인원 {res_cnt}", muted):
                return

        cost_txt = _fmt_won(info.get("total_cost"))
        if cost_txt:
            _draw_line(cost_txt, QColor(MainStyles.WORK_LOG_CAL_CELL_TEXT))
