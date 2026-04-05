# -*- coding: utf-8 -*-
"""
대시보드 카드: normal / drag_ready / dragging — 그림자·테두리·불투명·커서만 변경.
드래그 생명주기에서 min/max/fixed height·resize·updateGeometry로 크기를 바꾸지 않음.
"""
import math

from PyQt6.QtWidgets import (
    QFrame,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QApplication,
    QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,
    QToolButton,
    QMenu,
)
from PyQt6.QtCore import (
    Qt,
    QMimeData,
    QPoint,
    QTimer,
    pyqtSignal,
    QRect,
    QEasingCurve,
    QPropertyAnimation,
    QSize,
)
from PyQt6.QtGui import QColor, QCursor, QDrag, QMouseEvent, QPainter, QPen, QPixmap
from ui.styles import MainStyles, make_app_font

LONG_PRESS_MS = 800
MIME_DASHBOARD_CARD = "application/x-orchard-dashboard-card-id"

CARD_MIN_WIDTH = 120
MARKET_DONUT_SIZE = 62
MARKET_DONUT_RING_WIDTH = 8
MARKET_MAIN_DONUT_SCALE = 1.12
MARKET_MAIN_DONUT_SIZE = int(MARKET_DONUT_SIZE * MARKET_MAIN_DONUT_SCALE)
MARKET_MAIN_DONUT_RING_WIDTH = 8
MARKET_INFO_FONT_PT = 10
MARKET_INFO_TITLE_COLOR = "#5A6573"
MARKET_INFO_TEXT_COLOR = "#718096"
MARKET_INFO_DIVIDER_COLOR = "#A0AEC0"
MARKET_INFO_GROUP_GAP = 18
MARKET_LINE_SEPARATOR = "   ·   "
MARKET_INFO_LABEL_DEEMPH_COLOR = "#939DAC"
MARKET_TOP_CORP_NAME_PRICE_SPACING = "  "
MARKET_SPECIAL_DONUT_COLOR = "#2F855A"
MARKET_LARGE_DONUT_COLOR = "#3182CE"
MARKET_UP_COLOR = MARKET_LARGE_DONUT_COLOR
MARKET_DOWN_COLOR = "#C53030"
MARKET_FLAT_COLOR = "#718096"
MARKET_HELP_BUTTON_SIZE = 14
MARKET_HELP_FONT_PT = 8
CARD_HEADER_HEIGHT = 32
CARD_HEADER_MARGINS = (0, 4, 0, 4)
CARD_HEADER_ITEM_SPACING = 6
CARD_HEADER_ICON_SIZE = 16
CARD_HEADER_ICON_FONT_PT = 13
CARD_HEADER_TITLE_FONT_PT = 12
MARKET_BASE_DATE_FONT_PT = 8
MARKET_BASE_DATE_COLOR = "#8A94A6"

# 테두리 두께는 모든 상태에서 2px로 통일 → 스타일 전환 시 레이아웃/ sizeHint가 누적 증가하지 않음
STYLE_CARD = """
    QFrame#DashboardCardRoot {
        background-color: white;
        border: 2px solid #EAE7E2;
        border-radius: 12px;
    }
    QFrame#DashboardCardRoot:hover {
        border: 2px solid #D4CDC4;
        background-color: #FDFCFA;
    }
"""
STYLE_EDIT_MODE = """
    QFrame#DashboardCardRoot {
        background-color: #FFF9F4;
        border: 2px dashed #8B95A6;
        border-radius: 12px;
    }
    QFrame#DashboardCardRoot:hover {
        border: 2px dashed #718096;
        background-color: #FFFCF8;
    }
"""
STYLE_DRAG_READY = """
    QFrame#DashboardCardRoot {
        background-color: #FAFDFF;
        border: 2px solid #3182CE;
        border-radius: 12px;
    }
    QFrame#DashboardCardRoot:hover {
        background-color: #F7FBFF;
        border: 2px solid #2B6CB0;
    }
"""
# 카드 ⋮ 오버플로 메뉴: 플랫·선명한 텍스트(QGraphicsEffect 없음)
STYLE_CARD_OVERFLOW_MENU = """
    QMenu {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 2px 0;
    }
    QMenu::item {
        padding: 5px 14px;
        color: #2D3748;
        background-color: transparent;
    }
    QMenu::item:selected {
        background-color: #EDF2F7;
        color: #1A202C;
    }
    QMenu::item:disabled {
        color: #A0AEC0;
    }
"""


class RatioDonutWidget(QWidget):
    """간단한 도넛형 비중 시각화 위젯(0~100%)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ratio = 0.0
        self._active_color = QColor(MARKET_SPECIAL_DONUT_COLOR)
        self._line_top = ""
        self.setFixedSize(MARKET_MAIN_DONUT_SIZE, MARKET_MAIN_DONUT_SIZE)

    def set_ratio(self, value: float):
        try:
            v = float(value or 0.0)
        except Exception:
            v = 0.0
        self._ratio = max(0.0, min(100.0, v))
        self.update()

    def set_active_color(self, color_hex: str):
        self._active_color = QColor(color_hex or MARKET_SPECIAL_DONUT_COLOR)
        self.update()

    def set_center_label(self, text: str):
        self._line_top = str(text or "")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        side = min(self.width(), self.height())
        margin = 5
        rect_size = max(1, side - (margin * 2))
        x = (self.width() - rect_size) / 2
        y = (self.height() - rect_size) / 2

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track_pen = QPen(QColor("#E2E8F0"), MARKET_DONUT_RING_WIDTH)
        p.setPen(track_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(x), int(y), rect_size, rect_size)

        span = int(360 * 16 * (self._ratio / 100.0))
        value_pen = QPen(self._active_color, MARKET_DONUT_RING_WIDTH)
        p.setPen(value_pen)
        p.drawArc(int(x), int(y), rect_size, rect_size, 90 * 16, -span)

        center_text = f"{self._ratio:.0f}%"
        if self._line_top:
            center_text = f"{self._line_top}\n{center_text}"
        p.setPen(QColor("#2D3748"))
        p.setFont(make_app_font(8, bold=True))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, center_text)


class DecisionDonutWidget(QWidget):
    """메인 판단 표시용 대형 도넛 KPI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#B7791F")
        self._text = "관망"
        self._progress = 65.0
        self.setFixedSize(MARKET_MAIN_DONUT_SIZE, MARKET_MAIN_DONUT_SIZE)

    def set_decision(self, text: str, color_hex: str, progress: float):
        self._text = str(text or "관망")
        self._color = QColor(color_hex or "#B7791F")
        self._progress = max(0.0, min(100.0, float(progress or 0.0)))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        side = min(self.width(), self.height())
        margin = 6
        rect_size = max(1, side - (margin * 2))
        x = (self.width() - rect_size) / 2
        y = (self.height() - rect_size) / 2

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor("#E7E2D8"), MARKET_MAIN_DONUT_RING_WIDTH))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(int(x), int(y), rect_size, rect_size)

        span = int(360 * 16 * (self._progress / 100.0))
        p.setPen(QPen(self._color, MARKET_MAIN_DONUT_RING_WIDTH))
        p.drawArc(int(x), int(y), rect_size, rect_size, 90 * 16, -span)

        p.setPen(self._color)
        p.setFont(make_app_font(10, bold=True))
        p.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            self._text.replace(" ", "\n"),
        )


class SignalCircleWidget(QWidget):
    """실시간 신호 원형 배지."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "보합"
        self._fill = QColor("#EDF2F7")
        self._stroke = QColor("#CBD5E0")
        self._text_color = QColor("#718096")
        self.setMinimumSize(44, 44)
        self.setMaximumSize(52, 52)

    def set_signal(self, signal_text: str):
        t = str(signal_text or "보합")
        self._text = t
        if "강세" in t:
            self._fill = QColor("#E6FFFA")
            self._stroke = QColor("#81E6D9")
            self._text_color = QColor("#2F855A")
        elif "약세" in t:
            self._fill = QColor("#FFF5F5")
            self._stroke = QColor("#FEB2B2")
            self._text_color = QColor("#C53030")
        else:
            self._fill = QColor("#EDF2F7")
            self._stroke = QColor("#CBD5E0")
            self._text_color = QColor("#718096")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        side = min(self.width(), self.height())
        margin = 4
        rect_size = max(1, side - (margin * 2))
        x = (self.width() - rect_size) / 2
        y = (self.height() - rect_size) / 2

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(self._stroke, 2))
        p.setBrush(self._fill)
        p.drawEllipse(int(x), int(y), rect_size, rect_size)

        p.setPen(self._text_color)
        p.setFont(make_app_font(8, bold=True))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)


class DashboardCard(QFrame):
    """대시보드 카드: 편집 모드·드래그·메뉴. detail_requested는 상세 화면 이동용(card_id)."""

    detail_requested = pyqtSignal(str)
    hide_requested = pyqtSignal(str)
    menu_detail = pyqtSignal(str)
    reorder_drop = pyqtSignal(str, str)
    drag_started = pyqtSignal(str)
    drag_finished = pyqtSignal(str)
    drag_hover = pyqtSignal(str, str)

    def __init__(
        self,
        card_id,
        title,
        icon="📋",
        main_value="—",
        sub_desc="",
        status="",
        parent=None,
        *,
        show_detail_button=True,
        show_hide_button=False,
        show_overflow_menu=True,
        enable_drag_reorder=True,
    ):
        super().__init__(parent)
        self.setObjectName("DashboardCardRoot")
        self.card_id = card_id
        self._enable_drag = enable_drag_reorder
        self._show_overflow_menu = show_overflow_menu
        self._show_hide_inline = show_hide_button and not show_overflow_menu
        self._is_market_card = str(card_id or "").strip() == "market"
        self._market_card_mode = "market"
        self._opacity_effect = None
        self._editing_mode = False
        self._interaction_state = "normal"  # normal | drag_ready | dragging
        self._market_value_labels = {}
        self._market_decision_label = None
        self._market_basis_label = None
        self._market_top_corp_label = None
        self._market_top_corp_value_label = None
        self._market_special_donut = None
        self._market_within20_donut = None
        self._market_decision_donut = None
        self._market_base_date_label = None

        self._press_pos = None
        self._pressing = False
        self._drag_ready = False
        self._drag_started = False
        self._long_timer = QTimer(self)
        self._long_timer.setSingleShot(True)
        self._long_timer.timeout.connect(self._on_long_press)

        self._shake_timer = QTimer(self)
        self._shake_timer.setInterval(40)
        self._shake_timer.timeout.connect(self._tick_shake)
        self._shake_phase = 0.0
        # 편집 모드 흔들림: 레이아웃 마진은 건드리지 않고 _inner x 오프셋만 변경(폭·sizeHint 누적 방지)
        self._shake_dx = 0
        self._inner = None
        self._body_layout = None
        # 상단 마진 최소화로 타이틀을 상단에 가깝게(좌·우·하 균형 유지)
        self._body_margins_default = (10, 2, 10, 8)

        self._menu_fade_timer = QTimer(self)
        self._menu_fade_timer.setSingleShot(True)
        self._menu_fade_timer.timeout.connect(self._hide_menu_button)
        self._btn_menu_opacity = None

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.setMinimumWidth(CARD_MIN_WIDTH)
        self.setMaximumWidth(16777215)
        self.setFont(make_app_font(11))
        self.apply_normal_style()

        if self._enable_drag:
            self.setAcceptDrops(True)

        self._build_ui(title, icon, main_value, sub_desc, status, show_detail_button)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def minimumSizeHint(self):
        """내부 레이아웃 기반(상수 고정 높이 없음)."""
        if self._inner is not None:
            m = self._inner.minimumSizeHint()
            return QSize(max(CARD_MIN_WIDTH, m.width()), max(1, m.height()))
        return QSize(CARD_MIN_WIDTH, 80)

    def sizeHint(self):
        if self._inner is not None:
            m = self._inner.sizeHint()
            return QSize(max(CARD_MIN_WIDTH, m.width()), max(1, m.height()))
        return QSize(CARD_MIN_WIDTH, 100)

    def apply_normal_style(self):
        """정상 시각 상태(스타일 문자열 전체 치환, 누적 없음)."""
        if self._editing_mode:
            self.setStyleSheet(STYLE_EDIT_MODE)
        else:
            self.setStyleSheet(STYLE_CARD)

    def apply_drag_ready_style(self):
        """드래그 준비 시각만: 테두리·은은한 그림자·커서(geometry/min/max 변경 없음)."""
        self.setStyleSheet(STYLE_DRAG_READY)
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(12)
        sh.setOffset(0, 3)
        sh.setColor(QColor(0, 0, 0, 58))
        self.setGraphicsEffect(sh)
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        self.update()

    def apply_dragging_style(self):
        """드래그 중 시각만: 그림자 제거 → 일반 테두리 + 소스 반투명."""
        self.setGraphicsEffect(None)
        self.apply_normal_style()
        self._apply_drag_source_opacity(True)
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def enter_drag_ready_state(self):
        """롱프레스 직후 또는 편집 모드 즉시(이동 전 피드백)."""
        self._stop_shake_animation()
        self._interaction_state = "drag_ready"
        self._drag_ready = True
        self.apply_drag_ready_style()

    def restore_normal_state(self):
        """드롭/취소 후: 그래픽 효과·스타일·커서만 복구(geometry는 건드리지 않음)."""
        self._long_timer.stop()
        self._pressing = False
        self._press_pos = None
        self._drag_ready = False
        self._drag_started = False
        self._interaction_state = "normal"
        self.setGraphicsEffect(None)
        self._opacity_effect = None
        self.apply_normal_style()
        self.unsetCursor()
        if self._editing_mode and self._enable_drag:
            self._start_shake_animation()

    def set_editing_mode(self, on: bool):
        self._editing_mode = bool(on)
        if self._interaction_state == "normal":
            self.apply_normal_style()
        if self._editing_mode and self._enable_drag:
            self._start_shake_animation()
        else:
            self._stop_shake_animation()
        if not self._editing_mode:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    @staticmethod
    def _label_font(point_size: int):
        return make_app_font(point_size)

    def _build_unified_header(
        self,
        title: str,
        icon: str,
        *,
        help_tooltip: str = "",
        trailing_widget=None,
    ):
        header_host = QWidget()
        header_host.setStyleSheet("background: transparent; border: none;")
        header_host.setFixedHeight(CARD_HEADER_HEIGHT)
        header_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        header = QHBoxLayout(header_host)
        header.setContentsMargins(*CARD_HEADER_MARGINS)
        header.setSpacing(CARD_HEADER_ITEM_SPACING)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_icon = QLabel(str(icon or "📋"))
        lbl_icon.setStyleSheet("border:none;background:transparent;")
        lbl_icon.setFont(self._label_font(CARD_HEADER_ICON_FONT_PT))
        lbl_icon.setFixedSize(CARD_HEADER_ICON_SIZE, CARD_HEADER_ICON_SIZE)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(lbl_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        lbl_title = QLabel(str(title or ""))
        lbl_title.setStyleSheet(
            "background: transparent; color: #4A5568; font-weight: bold; border: none;"
        )
        lbl_title.setFont(self._label_font(CARD_HEADER_TITLE_FONT_PT))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        header.addWidget(lbl_title, 0, Qt.AlignmentFlag.AlignVCenter)

        help_btn = None
        if help_tooltip:
            help_btn = self._build_help_button(help_tooltip)
            header.addWidget(help_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addStretch()
        if trailing_widget is not None:
            header.addWidget(trailing_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        if self._show_overflow_menu:
            header.addSpacing(30)

        return header_host, help_btn

    def _sync_inner_geometry(self):
        """_inner 위치/크기(흔들림은 x 오프셋만). 레이아웃 마진은 __init__에서 1회만 설정."""
        if self._inner is None or self.width() <= 0 or self.height() <= 0:
            return
        dx = self._shake_dx if self._shake_timer.isActive() else 0
        self._inner.setGeometry(dx, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_inner_geometry()
        self._position_overflow_menu_button()
        self._position_detail_button()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_inner_geometry()
        self._position_overflow_menu_button()
        self._position_detail_button()

    def _build_ui(self, title, icon, main_value, sub_desc, status, show_detail_button):
        self._inner = QFrame(self)
        self._inner.setObjectName("DashboardCardInner")
        self._inner.setStyleSheet("QFrame#DashboardCardInner { background: transparent; border: none; }")
        self._inner.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not self._is_market_card,
        )

        self._body_layout = QVBoxLayout(self._inner)
        self._body_layout.setContentsMargins(*self._body_margins_default)
        self._body_layout.setSpacing(5)

        # ⋮ 버튼은 카드 루트(self)에 둠: _inner의 WA_TransparentForMouseEvents가 자식 클릭까지 막아 메뉴가 열리지 않던 문제 방지
        self.btn_menu = None
        if self._show_overflow_menu:
            self.btn_menu = QToolButton(self)
            self.btn_menu.setText("⋮")
            self.btn_menu.setFixedSize(28, 24)
            self.btn_menu.setStyleSheet(
                "QToolButton{border:none;color:#718096;background:transparent;border-radius:4px;}"
                "QToolButton:hover{background:#E2E8F0;color:#4A5568;}"
                "QToolButton:pressed{background:#CBD5E0;}"
            )
            self.btn_menu.setFont(self._label_font(16))
            self.btn_menu.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._btn_menu_opacity = QGraphicsOpacityEffect(self.btn_menu)
            self._btn_menu_opacity.setOpacity(0.0)
            self.btn_menu.setGraphicsEffect(self._btn_menu_opacity)
            self.btn_menu.setVisible(True)
            self.btn_menu.clicked.connect(self._open_overflow_menu)
            self.btn_menu.raise_()

        if self._is_market_card:
            self._build_market_ui(title, icon, show_detail_button)
            return

        if self._show_hide_inline:
            self.btn_hide = QPushButton("숨기기")
            self.btn_hide.setStyleSheet(
                "QPushButton{color:#718096;padding:2px 6px;border:1px solid #E2E8F0;"
                "border-radius:4px;background:#F7FAFC;}"
            )
            self.btn_hide.setFont(self._label_font(10))
            self.btn_hide.setFixedHeight(22)
            self.btn_hide.clicked.connect(lambda: self.hide_requested.emit(self.card_id))
        else:
            self.btn_hide = None

        header_widget, _ = self._build_unified_header(
            title,
            icon,
            trailing_widget=self.btn_hide,
        )
        self._body_layout.addWidget(header_widget)

        self.lbl_value = QLabel(str(main_value))
        self.lbl_value.setStyleSheet(
            "font-weight:bold;color:#2D3748;background:transparent;border:none;"
        )
        self.lbl_value.setFont(self._label_font(16))
        self._body_layout.addWidget(self.lbl_value)

        self.lbl_sub = QLabel(sub_desc)
        self.lbl_sub.setStyleSheet("color:#718096;background:transparent;")
        self.lbl_sub.setFont(self._label_font(10))
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setMaximumHeight(20)
        self._body_layout.addWidget(self.lbl_sub)

        bot = QHBoxLayout()
        # 우측은 루트에 띄운 «상세» 버튼 영역(겹침 방지, 레이아웃 행 높이는 동일)
        bot.setContentsMargins(0, 0, 76, 0)
        self.lbl_status = QLabel(status)
        self.lbl_status.setStyleSheet("color:#A0AEC0;background:transparent;")
        self.lbl_status.setFont(self._label_font(10))
        bot.addWidget(self.lbl_status)
        bot.addStretch()

        # 상세 버튼은 ⋮과 동일하게 카드 루트(self)에 둠(_inner 투명 전달 시 자식 클릭이 먹히지 않는 문제 방지)
        self.btn_detail = None
        if show_detail_button:
            self.btn_detail = QPushButton("상세 →", self)
            self.btn_detail.setStyleSheet(MainStyles.BTN_DASHBOARD_CARD_DETAIL)
            self.btn_detail.setFont(self._label_font(11))
            self.btn_detail.setFixedHeight(24)
            self.btn_detail.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.btn_detail.clicked.connect(self._on_detail_clicked)
            self.btn_detail.setVisible(True)
            self.btn_detail.raise_()

        self._body_layout.addLayout(bot)

    def _position_overflow_menu_button(self):
        """우상단 오버레이(Hit-test는 루트에서 처리, _inner 투명 전달과 무관)."""
        if not self._show_overflow_menu or self.btn_menu is None:
            return
        if self.width() <= 0:
            return
        m = 6
        self.btn_menu.move(self.width() - self.btn_menu.width() - m, m)
        self.btn_menu.raise_()

    def _position_detail_button(self):
        """우하단 오버레이(루트에 두어 클릭 확실히 수신)."""
        if self.btn_detail is None:
            return
        if self.width() <= 0 or self.height() <= 0:
            return
        self.btn_detail.adjustSize()
        mr, mb = self._body_margins_default[2], self._body_margins_default[3]
        w, h = self.btn_detail.width(), self.btn_detail.height()
        self.btn_detail.move(self.width() - w - mr, self.height() - h - mb)
        self.btn_detail.raise_()

    def _open_overflow_menu(self):
        if self.btn_menu is None:
            return
        m = QMenu(self)
        m.setStyleSheet(STYLE_CARD_OVERFLOW_MENU)
        m.setGraphicsEffect(None)
        m.setMinimumWidth(max(112, self.btn_menu.width() + 8))
        # OS가 붙이는 메뉴 창 그림자 완화(플랫폼에 따라 무시될 수 있음)
        m.setWindowFlags(m.windowFlags() | Qt.WindowType.NoDropShadowWindowHint)
        m.addAction("상세보기", lambda: self.menu_detail.emit(self.card_id))
        m.addAction("숨기기", lambda: self.hide_requested.emit(self.card_id))
        self._menu_fade_timer.stop()
        if self._btn_menu_opacity:
            self._btn_menu_opacity.setOpacity(1.0)
        m.aboutToHide.connect(lambda: self._menu_fade_timer.start(200))
        # ⋮ 버튼 바로 아래, 카드와 시각적으로 붙어 보이도록
        anchor = self.btn_menu.mapToGlobal(self.btn_menu.rect().bottomLeft())
        m.exec(anchor)

    def enterEvent(self, event):
        if self._show_overflow_menu and self.btn_menu and self._btn_menu_opacity:
            self._menu_fade_timer.stop()
            self._fade_menu_opacity(0.0, 1.0, 120)
        if self._editing_mode and self._enable_drag and not self._pressing:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().enterEvent(event)

    def leaveEvent(self, event):
        pop = QApplication.activePopupWidget()
        if pop is not None:
            super().leaveEvent(event)
            return
        if self._show_overflow_menu and self.btn_menu and self._btn_menu_opacity:
            self._menu_fade_timer.start(220)
        if not self._drag_ready and not self._drag_started:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().leaveEvent(event)

    def _hide_menu_button(self):
        if self._btn_menu_opacity:
            self._fade_menu_opacity(self._btn_menu_opacity.opacity(), 0.0, 100)

    def _fade_menu_opacity(self, start: float, end: float, ms: int):
        if not self._btn_menu_opacity:
            return
        self._btn_menu_opacity.setOpacity(start)
        anim = QPropertyAnimation(self._btn_menu_opacity, b"opacity", self)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

    # --- 흔들림: _inner x 오프셋만(레이아웃 margins/spacing 불변 → sizeHint 누적 방지) ---

    def _tick_shake(self):
        # 편집 모드: 미세 진동(과한 움직임·장난스러운 느낌 방지)
        self._shake_phase += 0.22
        self._shake_dx = int(round(1.0 * math.sin(self._shake_phase)))
        self._sync_inner_geometry()

    def _start_shake_animation(self):
        self._stop_shake_animation()
        self._shake_phase = 0.0
        self._shake_dx = 0
        self._shake_timer.start()

    def _stop_shake_animation(self):
        self._shake_timer.stop()
        self._shake_dx = 0
        self._sync_inner_geometry()

    # --- 고스트: 원본과 동일 픽셀 크기(스케일 없음), 테두리만 내부에 그림 ---

    def _build_drag_ghost_pixmap(self) -> QPixmap:
        """원본 카드와 동일 픽셀 크기, 약한 그림자 느낌 + 테두리만 강화(스케일 업 없음)."""
        w, h = self.width(), self.height()
        raw = self.grab(QRect(0, 0, w, h))
        if raw.isNull() or raw.width() != w or raw.height() != h:
            raw = self.grab()
            if raw.width() != w or raw.height() != h:
                raw = raw.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        # 동일 크기 안에서만 은은한 하이라이트(레이아웃 불안정 유발 확대 없음)
        p.setOpacity(1.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 16))
        p.drawRoundedRect(2, 3, w - 4, h - 5, 10, 10)
        p.setOpacity(0.98)
        p.drawPixmap(0, 0, raw)
        p.setOpacity(1.0)
        p.setPen(QPen(QColor(49, 130, 206, 210), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)
        p.end()
        return out

    def _apply_drag_source_opacity(self, on: bool):
        if not on:
            self.setGraphicsEffect(None)
            self._opacity_effect = None
            return
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.5)
        self.setGraphicsEffect(self._opacity_effect)

    def play_settle_animation(self, duration_ms: int = 150):
        """내부 콘텐츠만 짧게 정착(루트 높이 불변)."""
        if self._inner is None:
            return
        eff = QGraphicsOpacityEffect(self._inner)
        self._inner.setGraphicsEffect(eff)
        eff.setOpacity(0.94)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(duration_ms)
        anim.setStartValue(0.94)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _cleanup():
            if self._inner and self._inner.graphicsEffect() == eff:
                self._inner.setGraphicsEffect(None)

        anim.finished.connect(_cleanup)
        anim.start()

    def _is_press_on_button(self, pos: QPoint) -> bool:
        w = self.childAt(pos)
        while w and w != self:
            if isinstance(w, (QPushButton, QToolButton)):
                return True
            w = w.parentWidget()
        return False

    def mousePressEvent(self, event: QMouseEvent):
        if not self._enable_drag:
            return super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        if self._is_press_on_button(event.pos()):
            return super().mousePressEvent(event)
        self._pressing = True
        self._press_pos = QPoint(event.pos())
        self._drag_ready = False
        self._drag_started = False
        self._long_timer.stop()

        if self._editing_mode:
            self.enter_drag_ready_state()
        else:
            self._long_timer.start(LONG_PRESS_MS)
        super().mousePressEvent(event)

    def _on_long_press(self):
        if not self._pressing or not self._press_pos or self._editing_mode:
            return
        self.enter_drag_ready_state()

    def mouseMoveEvent(self, event: QMouseEvent):
        if (
            self._enable_drag
            and self._drag_ready
            and not self._drag_started
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._press_pos is not None
        ):
            delta = event.pos() - self._press_pos
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self._start_drag()
                return
        if self._editing_mode and self._enable_drag and not self._pressing and not self._drag_started:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().mouseMoveEvent(event)

    def _start_drag(self):
        self._stop_shake_animation()
        self._long_timer.stop()
        self._interaction_state = "dragging"
        self._drag_started = True
        self.apply_dragging_style()

        ghost = self._build_drag_ghost_pixmap()
        mime = QMimeData()
        mime.setData(MIME_DASHBOARD_CARD, self.card_id.encode("utf-8"))

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(ghost)
        drag.setHotSpot(QPoint(ghost.width() // 2, ghost.height() // 2))

        if self._enable_drag:
            self.drag_started.emit(self.card_id)

        try:
            drag.exec(Qt.DropAction.MoveAction)
        except Exception as e:
            print(f"[DashboardCard] drag.exec failed: {e}")
            raise
        finally:
            if self._enable_drag:
                self.drag_finished.emit(self.card_id)
            self._apply_drag_source_opacity(False)
            self.restore_normal_state()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._enable_drag and event.button() == Qt.MouseButton.LeftButton:
            self._pressing = False
            self._long_timer.stop()
            if not self._drag_started:
                self.restore_normal_state()
                if (
                    self._is_market_card
                    and not self._editing_mode
                    and not self._is_press_on_button(event.pos())
                ):
                    self.detail_requested.emit(self.card_id)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if not self._enable_drag:
            return super().dragEnterEvent(event)
        if event.mimeData().hasFormat(MIME_DASHBOARD_CARD):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self._enable_drag:
            return super().dragMoveEvent(event)
        if event.mimeData().hasFormat(MIME_DASHBOARD_CARD):
            raw = event.mimeData().data(MIME_DASHBOARD_CARD)
            source_id = bytes(raw).decode("utf-8", errors="replace").strip()
            if source_id and source_id != self.card_id:
                self.drag_hover.emit(source_id, self.card_id)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self._enable_drag:
            return super().dropEvent(event)
        if not event.mimeData().hasFormat(MIME_DASHBOARD_CARD):
            return super().dropEvent(event)
        raw = event.mimeData().data(MIME_DASHBOARD_CARD)
        source_id = bytes(raw).decode("utf-8", errors="replace").strip()
        if source_id and source_id != self.card_id:
            self.reorder_drop.emit(source_id, self.card_id)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _on_detail_clicked(self):
        self.detail_requested.emit(self.card_id)

    def clear_move_ui(self):
        self._apply_drag_source_opacity(False)
        self.restore_normal_state()

    def set_main_value(self, v):
        if self._is_market_card and self._market_decision_label is not None:
            self._set_market_decision(str(v))
            return
        self.lbl_value.setText(str(v))

    def set_sub_desc(self, t):
        if self._is_market_card:
            return
        self.lbl_sub.setText(t)

    def set_status(self, t):
        if self._is_market_card:
            return
        self.lbl_status.setText(t)

    def _build_market_ui(self, title: str, icon: str, show_detail_button: bool):
        self._body_layout.setSpacing(2)

        # 1) 헤더: 모든 카드와 동일한 구조/높이/정렬 기준 사용
        self._market_base_date_label = QLabel("기준일자: 확인중...")
        self._market_base_date_label.setFont(self._label_font(MARKET_BASE_DATE_FONT_PT))
        self._market_base_date_label.setStyleSheet(
            f"color:{MARKET_BASE_DATE_COLOR};background:transparent;border:none;"
            f"font-size:{MARKET_BASE_DATE_FONT_PT}pt;"
        )
        header_widget, help_btn = self._build_unified_header(
            title,
            icon or "📈",
            help_tooltip="신고배의 특품·대과(20과이내) 비중과 주요 법인 최고가를 기준으로 현재 출하 상태를 요약합니다.",
            trailing_widget=self._market_base_date_label,
        )
        self._market_basis_label = help_btn
        self._body_layout.addWidget(header_widget)

        # 2) KPI 그룹: 도넛 3개를 하나의 수평 그룹으로 정렬
        kpi_row = QHBoxLayout()
        kpi_row.setContentsMargins(24, 0, 24, 0)
        kpi_row.setSpacing(48)
        kpi_row.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._market_decision_donut = DecisionDonutWidget()
        kpi_row.addWidget(
            self._market_decision_donut,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        self._market_decision_label = QLabel("관망")
        self._market_decision_label.setFont(self._label_font(12))
        self._market_decision_label.setStyleSheet("font-weight:800;color:#B7791F;background:transparent;border:none;")
        self._market_decision_label.hide()
        kpi_row.addWidget(
            self._build_ratio_item("special_ratio", "특품", MARKET_SPECIAL_DONUT_COLOR),
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        kpi_row.addWidget(
            self._build_ratio_item("within20_ratio", "대과", MARKET_LARGE_DONUT_COLOR),
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        self._body_layout.addLayout(kpi_row)
        self._body_layout.addSpacing(14)

        # 3) 하단 정보 영역: 실시간 최고가 (초경량 요약 카드)
        info_block = QVBoxLayout()
        info_block.setContentsMargins(0, 0, 0, 0)
        info_block.setSpacing(0)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)
        bottom_title = "• 실시간 최고가"
        self._market_top_corp_label = self._make_market_info_label(
            bottom_title,
            color=MARKET_INFO_LABEL_DEEMPH_COLOR,
        )
        self._market_top_corp_label.setWordWrap(False)
        bottom.addWidget(self._market_top_corp_label)
        bottom.addSpacing(MARKET_INFO_GROUP_GAP)
        self._market_top_corp_value_label = self._make_market_info_label(
            "-",
            color=MARKET_INFO_TITLE_COLOR,
        )
        self._market_top_corp_value_label.setWordWrap(False)
        bottom.addWidget(self._market_top_corp_value_label)
        bottom.addStretch()
        info_block.addLayout(bottom)
        self._body_layout.addLayout(info_block)

        self.btn_detail = None

    def _build_ratio_item(self, key: str, label_text: str, donut_color: str):
        box = QFrame()
        box.setStyleSheet("QFrame { background: transparent; border: none; }")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        donut = RatioDonutWidget()
        donut.set_active_color(donut_color)
        donut.set_center_label(label_text)
        lay.addWidget(donut, alignment=Qt.AlignmentFlag.AlignHCenter)
        if key == "special_ratio":
            self._market_special_donut = donut
        elif key == "within20_ratio":
            self._market_within20_donut = donut
        return box

    def _build_compact_metric_item(self, key: str, label_text: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        lbl = self._make_market_info_label(f"{label_text} ")
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)
        val = self._make_market_info_label("-")
        val.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        val.setWordWrap(False)
        row.addWidget(val)
        self._market_value_labels[key] = val
        return row

    def _build_compact_divider(self):
        div = QLabel(MARKET_LINE_SEPARATOR)
        div.setStyleSheet(
            f"color:{MARKET_INFO_DIVIDER_COLOR};background:transparent;border:none;"
            f"font-size:{MARKET_INFO_FONT_PT}pt;"
        )
        div.setFont(self._label_font(MARKET_INFO_FONT_PT))
        div.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        return div

    def _make_market_info_label(self, text: str, *, color: str = MARKET_INFO_TEXT_COLOR):
        lbl = QLabel(str(text or ""))
        lbl.setStyleSheet(
            f"color:{color};background:transparent;border:none;font-weight:400;"
            f"font-size:{MARKET_INFO_FONT_PT}pt;"
        )
        lbl.setFont(self._label_font(MARKET_INFO_FONT_PT))
        return lbl

    def set_market_summary_data(self, data: dict):
        if not self._is_market_card:
            return
        payload = data or {}
        # 분석 페이로드는 signal만 오는 경우가 많고, fallback decision(관망)이 남으면 잘못 표시됨
        if self._is_analysis_payload(payload):
            decision_text = str(payload.get("signal") or payload.get("decision") or "관망")
        else:
            decision_text = str(payload.get("decision") or payload.get("signal") or "관망")
        self._set_market_decision(decision_text)
        is_analysis_payload = self._is_analysis_payload(payload)
        if self._market_top_corp_label is not None:
            self._market_top_corp_label.setText(
                "• 출하 판단 요약" if is_analysis_payload else "• 실시간 최고가"
            )
        if is_analysis_payload:
            self._set_market_ratio("special_ratio", payload.get("base_special_ratio"))
            self._set_market_ratio("within20_ratio", payload.get("base_within20_ratio"))
            if str(payload.get("status") or "").lower() != "ok":
                top_corp_text = "데이터 부족 (분석 대기)"
            else:
                avg_text = "-"
                avg_price = payload.get("base_avg_price")
                if avg_price not in ("", None):
                    avg_text = f"{int(float(avg_price)):,}"
                top_corp_text = (
                    f"평균 {avg_text}원"
                    f"{MARKET_LINE_SEPARATOR}D1 {self._fmt_signed_pct(payload.get('d1_pct'))}"
                    f"{MARKET_LINE_SEPARATOR}D7 {self._fmt_signed_pct(payload.get('d7_pct'))}"
                    f"{MARKET_LINE_SEPARATOR}D30 {self._fmt_signed_pct(payload.get('d30_pct'))}"
                )
        else:
            self._set_market_ratio("special_ratio", payload.get("special_ratio"))
            self._set_market_ratio("within20_ratio", payload.get("within20_ratio"))
            top_corp_text = self._format_top_corp_line(payload.get("top_corp_prices") or [])
        if self._market_top_corp_value_label is not None:
            self._market_top_corp_value_label.setText(top_corp_text)
        else:
            self._market_top_corp_label.setText(top_corp_text)
        if self._market_base_date_label is not None:
            self._market_base_date_label.setText(self._format_base_date_text(payload))

    def _is_analysis_payload(self, payload: dict):
        if not isinstance(payload, dict):
            return False
        keys = ("signal", "base_avg_price", "d1_pct", "d7_pct", "d30_pct")
        return any(k in payload for k in keys)

    def _format_base_date_text(self, payload: dict):
        requested = str(payload.get("requested_date") or "").strip()
        base = str(payload.get("base_date") or "").strip()
        status = str(payload.get("status") or "").strip()
        variety = str(payload.get("variety") or "").strip()
        market = str(payload.get("market") or "").strip()
        is_analysis_payload = self._is_analysis_payload(payload)
        if status in ("error", "empty"):
            if is_analysis_payload:
                vm = ""
                if variety or market:
                    vm = f" | {variety or '-'} / {market or '-'}"
                return f"기준일자: 없음{vm}"
            return "기준일자: 없음"
        if not base:
            return "기준일자: 확인중..."
        if is_analysis_payload:
            vm = ""
            if variety or market:
                vm = f" | {variety or '-'} / {market or '-'}"
            if requested and requested != base:
                return f"기준일자: {base} (최근 정산일자){vm}"
            return f"기준일자: {base}{vm}"
        if requested and requested != base:
            return f"기준일자: {base} (최근 정산일자)"
        return f"기준일자: {base}"

    def _set_market_ratio(self, key: str, value):
        if key == "special_ratio" and self._market_special_donut is not None:
            self._market_special_donut.set_ratio(value or 0.0)
        elif key == "within20_ratio" and self._market_within20_donut is not None:
            self._market_within20_donut.set_ratio(value or 0.0)

    def _set_market_metric(self, key: str, value_text: str, color: str = "#4A5568"):
        lbl = self._market_value_labels.get(key)
        if lbl is None:
            return
        lbl.setText(value_text)
        lbl.setStyleSheet(
            f"color:{color};font-weight:400;background:transparent;border:none;"
            f"font-size:{MARKET_INFO_FONT_PT}pt;"
        )

    def _set_market_decision(self, decision: str):
        if self._market_decision_label is None:
            return
        color_map = {
            "적극 출하": "#1F7A3D",
            "강한 출하 권장": "#2F855A",
            "출하 권장": "#68A357",
            "강세": "#2F855A",
            "관망": "#B7791F",
            "출하 유보": "#C05621",
            "강한 유보": "#C53030",
            "약세": "#C53030",
        }
        progress_map = {
            "적극 출하": 95.0,
            "강한 출하 권장": 82.0,
            "출하 권장": 70.0,
            "강세": 75.0,
            "관망": 55.0,
            "출하 유보": 35.0,
            "강한 유보": 20.0,
            "약세": 30.0,
        }
        color = color_map.get(decision, "#4A5568")
        self._market_decision_label.setText(decision)
        self._market_decision_label.setStyleSheet(
            f"font-weight:800;color:{color};background:transparent;border:none;"
        )
        if self._market_decision_donut is not None:
            self._market_decision_donut.set_decision(
                decision,
                color,
                progress_map.get(decision, 55.0),
            )

    def _fmt_ratio(self, value, change):
        base = f"{float(value or 0):.1f}%"
        ch = float(change or 0)
        sign = "+" if ch > 0 else ""
        if ch == 0:
            return f"{base} (0.0%)"
        return f"{base} ({sign}{ch:.1f}%)"

    def _fmt_signed_pct(self, value):
        if value in ("", None):
            return "-"
        try:
            v = float(value)
        except Exception:
            return "-"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f}%"

    def _color_for_change(self, value):
        v = float(value or 0)
        if v > 0:
            return MARKET_UP_COLOR
        if v < 0:
            return MARKET_DOWN_COLOR
        return MARKET_FLAT_COLOR

    def _color_for_signal(self, text: str):
        t = str(text or "")
        if "강세" in t:
            return MARKET_UP_COLOR
        if "약세" in t:
            return MARKET_DOWN_COLOR
        return MARKET_FLAT_COLOR

    def _infer_realtime_change(self, signal_text: str):
        t = str(signal_text or "")
        if "강세" in t:
            return 1.4
        if "약세" in t:
            return -1.4
        return 0.0

    def _build_help_button(self, tooltip_text: str):
        btn = QToolButton()
        btn.setText("?")
        btn.setToolTip(str(tooltip_text or ""))
        btn.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        btn.setFixedSize(MARKET_HELP_BUTTON_SIZE, MARKET_HELP_BUTTON_SIZE)
        btn.setStyleSheet(
            f"QToolButton{{color:#8A94A6;background:#F1F5F9;border:1px solid #D5DCE6;"
            f"border-radius:{MARKET_HELP_BUTTON_SIZE // 2}px;padding:0;font-size:{MARKET_HELP_FONT_PT}pt;}}"
            "QToolButton:hover{background:#E8EEF5;color:#5A6573;}"
            f"QToolTip{{color:#1A202C;background-color:#F8FAFC;border:1px solid #CBD5E0;padding:4px;font-size:{MARKET_INFO_FONT_PT}pt;}}"
        )
        btn.setFont(self._label_font(MARKET_HELP_FONT_PT))
        return btn

    def _format_top_corp_line(self, top_corp_prices):
        if not top_corp_prices:
            return "-"
        items = []
        plain_len = 0
        for row in list(top_corp_prices)[:3]:
            name = str(row.get("name") or "").strip()
            price = int(row.get("price") or 0)
            if not name:
                continue
            text_piece = f"{name}{MARKET_TOP_CORP_NAME_PRICE_SPACING}{price:,}"
            next_len = plain_len + (3 if items else 0) + len(text_piece)
            if next_len > 46:
                break
            items.append(text_piece)
            plain_len = next_len
        if not items:
            return "-"
        text = MARKET_LINE_SEPARATOR.join(items)
        if len(items) < len(list(top_corp_prices)[:3]):
            text += " …"
        return text
