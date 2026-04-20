# -*- coding: utf-8 -*-
"""
dashboard_detail_base.py - 대시보드 상세 페이지 베이스 클래스
Header / 요약 카드 / 메인 콘텐츠(3) : 우측 사이드바(1) 비율
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.styles import MainStyles
from ui.widgets.dashboard_card_widget import DashboardCard


class DashboardDetailBase(QWidget):
    """
    대시보드 상세 페이지 베이스
    - 헤더(제목 좌측 · 대시보드 버튼 우측)
    - 요약 카드 영역
    - 메인 분석 콘텐츠 (좌 3) : 우측 네비게이션 카드 (1)
    - navigate_to(page_id) 시그널
    """
    navigate_to = pyqtSignal(str)  # 다른 상세 페이지로 이동
    back_to_dashboard = pyqtSignal()

    def __init__(
        self,
        page_id,
        title,
        icon,
        db_manager,
        session,
        parent=None,
        *,
        sidebar_nav_title="📌 관련 보기",
        content_split=(3, 1),
    ):
        super().__init__(parent)
        self.page_id = page_id
        self.db = db_manager
        self.session = session
        self.farm_cd = session.get('farm_cd', '')
        self._title = title
        self._icon = icon
        self._sidebar_nav_title = sidebar_nav_title  # None이면 상단 네비 제목·자리만 비움(전용 패널용)
        self._content_split = content_split  # (메인 스크롤, 우측 사이드바) stretch 비율
        self._sidebar_cards = []  # 우측 네비게이션용 카드 목록
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(MainStyles.MAIN_BG)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # 1. 헤더 (제목 좌측 · 대시보드 버튼 우측)
        header = QHBoxLayout()
        self.btn_back = QPushButton("← 대시보드")
        self.btn_back.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_back.setFixedHeight(36)
        self.btn_back.clicked.connect(self.back_to_dashboard.emit)

        title_lbl = QLabel(f"{self._icon} {self._title}")
        title_lbl.setStyleSheet(MainStyles.LBL_TITLE)
        header.addWidget(title_lbl)
        header.addStretch(1)
        header.addWidget(self.btn_back)
        main_layout.addLayout(header)

        # 2. 요약 카드 영역 (서브클래스에서 채움)
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("background: transparent; border: none;")
        self.summary_layout = QHBoxLayout(self.summary_frame)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.summary_frame)

        # 3. 메인 콘텐츠 + 사이드바 (기본 3:1, 화면별 content_split으로 조정)
        content_wrapper = QHBoxLayout()
        content_wrapper.setSpacing(20)

        # 좌측: 메인 분석 영역 (스크롤)
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_scroll.setStyleSheet("background: transparent; border: none;")
        self.main_content = QWidget()
        self.main_content.setStyleSheet("background: transparent;")
        self.main_layout = QVBoxLayout(self.main_content)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_scroll.setWidget(self.main_content)
        self.main_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # 우측: 관련 네비게이션 카드
        self.sidebar = QFrame()
        self.sidebar.setStyleSheet(MainStyles.CARD)
        # stretch 비율(content_split)이 적용되도록 고정 폭 사용 안 함
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(12, 12, 12, 12)
        if self._sidebar_nav_title:
            self.sidebar_layout.addWidget(
                QLabel(self._sidebar_nav_title, styleSheet=MainStyles.CARD_LBL_STYLE)
            )

        ms, ss = self._content_split if len(self._content_split) == 2 else (3, 1)
        content_wrapper.addWidget(self.main_scroll, int(ms))
        content_wrapper.addWidget(self.sidebar, int(ss))
        main_layout.addLayout(content_wrapper)

    def add_sidebar_card(self, card_id, title, icon="•"):
        """우측 사이드바에 네비게이션 카드 추가"""
        card = DashboardCard(
            card_id,
            title,
            icon=icon,
            main_value="",
            sub_desc="클릭하여 이동",
            show_overflow_menu=False,
            show_hide_button=False,
            enable_drag_reorder=False,
        )
        card.setMinimumHeight(80)
        card.detail_requested.connect(self.navigate_to.emit)
        self.sidebar_layout.addWidget(card)
        self._sidebar_cards.append(card)
        return card

    def set_summary_cards(self, cards_data):
        """요약 카드 영역 설정. cards_data: [(title, value, sub), ...]"""
        for i in reversed(range(self.summary_layout.count())):
            w = self.summary_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        for title, value, sub in cards_data:
            c = QFrame()
            c.setStyleSheet(MainStyles.CARD)
            c.setFixedHeight(70)
            lay = QVBoxLayout(c)
            lay.setContentsMargins(12, 8, 12, 8)
            lay.addWidget(QLabel(title, styleSheet="color: #718096;"))
            lay.addWidget(QLabel(str(value), styleSheet="font-weight: bold; color: #2D3748;"))
            if sub:
                lay.addWidget(QLabel(sub, styleSheet="color: #A0AEC0;"))
            self.summary_layout.addWidget(c)
