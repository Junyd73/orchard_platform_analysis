# -*- coding: utf-8 -*-
"""
홈 대시보드: 브리핑 바, 2열 카드 그리드, DB 연동 레이아웃·드래그 재정렬·숨김.
"""
import datetime
import time

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
)
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
    QStackedWidget,
    QSizePolicy,
    QPushButton,
    QMessageBox,
    QDialog,
)
from ui.styles import MainStyles
from ui.widgets.dashboard_card_widget import DashboardCard
from ui.pages.market_price_page import MarketPricePage
from ui.pages.weather_detail_page import WeatherDetailPage
from ui.pages.cost_detail_page import CostDetailPage
from ui.pages.kpi_detail_page import KpiDetailPage
from core.market_price_manager import MarketPriceManager
from core.market_price_service import MarketPriceService
from core.services.market_analysis_service import MarketAnalysisService

DASHBOARD_CARD_SPECS = [
    ("work", "오늘 작업", "📅", "0건", "영농일지", ""),
    ("market", "시장/경매", "📈", "—", "시세 요약", ""),
    ("labor", "비용 현황", "💳", "0원", "통합/구분", ""),
    ("weather", "날씨", "🌤️", "—", "기상 요약", ""),
    ("orders", "주문/판매", "🛒", "0건", "오늘", ""),
    ("inventory", "재고", "📦", "—", "재고 현황", ""),
    ("receivables", "미수금", "💰", "0원", "총 미수", ""),
    ("kpi", "KPI", "📊", "—", "지표 요약", ""),
]

DEFAULT_CARD_ORDER = [spec[0] for spec in DASHBOARD_CARD_SPECS]
CARDS_META = {
    cid: (title, icon, val, sub, st)
    for cid, title, icon, val, sub, st in DASHBOARD_CARD_SPECS
}


def _norm_ymd_sql(col: str) -> str:
    """sales_dt 등 YYYY-MM-DD / YYYYMMDD 혼재 시 정규화."""
    c = col
    return (
        f"CASE "
        f"WHEN {c} IS NULL THEN NULL "
        f"WHEN length({c})=10 AND instr({c}, '-')=5 THEN {c} "
        f"WHEN length({c})=8 THEN substr({c},1,4)||'-'||substr({c},5,2)||'-'||substr({c},7,2) "
        f"ELSE {c} END"
    )


class DashboardPage(QWidget):
    """홈 대시보드: briefing → cards_host(2열 그리드) → 알림."""

    PAGE_IDS = list(DEFAULT_CARD_ORDER)
    DETAIL_IDS = ["market", "market_analysis", "weather", "labor", "kpi"]

    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        self.farm_cd = str(session.get("farm_cd") or "").strip()
        self.farm_nm = session.get("farm_nm", "과수원")
        self.user_id = str(session.get("user_id") or "").strip()
        self._detail_pages = {}
        self.is_loaded = True

        self._cards = {}
        self._card_order = list(DEFAULT_CARD_ORDER)
        self._hidden_card_ids = set()
        self._layout_rows = {}
        self._visible_map = {cid: "Y" for cid in DEFAULT_CARD_ORDER}

        # 드래그 재정렬 UX(고스트는 카드 위젯에서, 여기서는 분리·슬롯 애니메이션)
        self._dnd_anim_group = None
        self._dnd_detached = False
        self._dnd_initial_visible_order = None
        self._dnd_source = None
        self._dnd_old_slot = 0
        self._dnd_last_hover = None
        self._dnd_cell_w = 120
        self._dnd_cell_h = 120  # detach 시 실제 카드 geometry로 갱신
        self._dnd_gap = 8
        self._editing_mode = False
        self.market_service = None
        self.market_analysis_service = None
        try:
            self.market_service = MarketPriceService(MarketPriceManager())
        except Exception as e:
            print(f"[Dashboard] market service init failed: {e}")
        try:
            self.market_analysis_service = MarketAnalysisService(self.db)
        except Exception as e:
            print(f"[Dashboard] market analysis service init failed: {e}")

        self._ensure_dashboard_layout_table()
        self._migrate_legacy_card_pref_table()
        self._load_layout_from_db()

        self.init_ui()
        self._reflow_card_grid()
        self.load_summary_data()

    def init_ui(self):
        self.setStyleSheet(MainStyles.MAIN_BG)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        self.dashboard_widget = QWidget()
        self.dashboard_widget.setStyleSheet("background: transparent;")
        dashboard_layout = QVBoxLayout(self.dashboard_widget)
        dashboard_layout.setContentsMargins(12, 12, 12, 12)
        dashboard_layout.setSpacing(8)

        self.briefing_bar = self._create_briefing_bar()
        dashboard_layout.addWidget(self.briefing_bar)

        self.cards_host = QWidget()
        self.cards_host.setStyleSheet("background: transparent;")
        self.cards_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._grid_layout = QGridLayout(self.cards_host)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(8)
        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)
        # _grid_layout은 cards_host에만 1회 연결됨(dashboard_layout에는 cards_host만 addWidget)

        for cid, title, icon, val, sub, st in DASHBOARD_CARD_SPECS:
            card = DashboardCard(
                cid,
                title,
                icon,
                val,
                sub,
                st,
                show_overflow_menu=True,
                show_hide_button=False,
            )
            card.setParent(self.cards_host)
            card.detail_requested.connect(self._open_detail_page)
            card.menu_detail.connect(self._on_menu_detail)
            card.hide_requested.connect(self._on_card_hide_requested)
            card.reorder_drop.connect(self._on_reorder_drop)
            card.drag_started.connect(self._on_dnd_drag_started)
            card.drag_finished.connect(self._on_dnd_drag_finished)
            card.drag_hover.connect(self._on_dnd_drag_hover)
            self._cards[cid] = card

        dashboard_layout.addWidget(self.cards_host, 1)

        self.alert_frame = QFrame()
        self.alert_frame.setStyleSheet(MainStyles.CARD)
        self.alert_frame.setMaximumHeight(44)
        al = QHBoxLayout(self.alert_frame)
        al.setContentsMargins(10, 4, 10, 4)
        alert_title = QLabel("알림", styleSheet=MainStyles.TXT_CARD_TITLE)
        al.addWidget(alert_title)
        self.alert_label = QLabel("오늘의 알림이 없습니다.")
        self.alert_label.setStyleSheet(MainStyles.TXT_CAPTION)
        al.addWidget(self.alert_label)
        al.addStretch()
        dashboard_layout.addWidget(self.alert_frame)

        self.stack.addWidget(self.dashboard_widget)
        root.addWidget(self.stack)

    def _create_briefing_bar(self):
        bar = QFrame()
        bar.setStyleSheet(MainStyles.SEARCH_BAR_STYLE)
        # BTN_SECONDARY 세로 padding(8+8) + 글자 높이를 수용하려면 내부 높이 30px 이상 필요.
        # 기존 40 - 상하마진 16 = 24px만 남아 버튼(28)이 세로로 잘림 → 바 높이 확대.
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        self.lbl_date = QLabel(datetime.datetime.now().strftime("%Y-%m-%d"))
        self.lbl_farm = QLabel(self.farm_nm)
        self.lbl_weather = QLabel("날씨 —")
        self.lbl_market = QLabel("시세 —")
        self.lbl_sales = QLabel("오늘 매출 0원")
        self.lbl_cost = QLabel("오늘 비용 0원")
        self.lbl_receivables = QLabel("미수 0원")
        self.lbl_alert_count = QLabel("알림 0건")
        st = (
            "font-weight: bold; color: #4A5568; "
            "border: none; background: transparent;"
        )
        for w in [
            self.lbl_date,
            self.lbl_farm,
            self.lbl_weather,
            self.lbl_market,
            self.lbl_sales,
            self.lbl_cost,
            self.lbl_receivables,
            self.lbl_alert_count,
        ]:
            w.setStyleSheet(st)
        for w in [
            self.lbl_date,
            self.lbl_farm,
            QLabel("|", styleSheet="color:#CBD5E0;"),
            self.lbl_weather,
            self.lbl_market,
            QLabel("|", styleSheet="color:#CBD5E0;"),
            self.lbl_sales,
            self.lbl_cost,
            self.lbl_receivables,
            QLabel("|", styleSheet="color:#CBD5E0;"),
            self.lbl_alert_count,
        ]:
            lay.addWidget(w)
        # 좌측: 정보 라벨 / 우측 끝: 편집·카드 관리(간격만 좁게)
        lay.addStretch()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.btn_edit_mode = QPushButton("대시보드 편집")
        self.btn_edit_mode.setCheckable(True)
        self.btn_edit_mode.setChecked(False)
        self.btn_edit_mode.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_edit_mode.setFixedHeight(34)
        self.btn_edit_mode.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        _fm_edit = QFontMetrics(self.btn_edit_mode.font())
        self.btn_edit_mode.setMinimumWidth(
            _fm_edit.boundingRect(self.btn_edit_mode.text()).width() + 40
        )
        self.btn_edit_mode.setToolTip(
            "켜면 카드를 바로 끌어 재정렬할 수 있고, 카드가 편집 상태로 표시됩니다."
        )
        self.btn_edit_mode.toggled.connect(self._on_edit_mode_toggled)
        btn_row.addWidget(self.btn_edit_mode)
        self.btn_card_manage = QPushButton("카드 관리")
        self.btn_card_manage.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_card_manage.setFixedHeight(34)
        self.btn_card_manage.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        _fm_card = QFontMetrics(self.btn_card_manage.font())
        self.btn_card_manage.setMinimumWidth(
            _fm_card.boundingRect(self.btn_card_manage.text()).width() + 40
        )
        self.btn_card_manage.clicked.connect(self._open_card_manage_dialog)
        btn_row.addWidget(self.btn_card_manage)
        lay.addLayout(btn_row)
        return bar

    def _on_edit_mode_toggled(self, checked: bool):
        self._editing_mode = bool(checked)
        if checked:
            self.btn_edit_mode.setStyleSheet(MainStyles.BTN_DASHBOARD_EDIT_ON)
        else:
            self.btn_edit_mode.setStyleSheet(MainStyles.BTN_SECONDARY)
        self._apply_editing_mode_to_cards()

    def _apply_editing_mode_to_cards(self):
        """숨긴 카드는 편집 표시 제외."""
        for cid, card in self._cards.items():
            if cid in self._hidden_card_ids:
                card.set_editing_mode(False)
            else:
                card.set_editing_mode(self._editing_mode)

    def _on_menu_detail(self, card_id: str):
        if card_id in self.DETAIL_IDS:
            target_id = "market_analysis" if card_id == "market" else card_id
            self._show_detail_page(target_id)

    def _play_drop_settle_animation(self):
        """드롭 후 카드 정착(불투명도)."""
        for cid in self._visible_card_order():
            if cid in self._cards:
                self._cards[cid].play_settle_animation(150)

    def _ensure_dashboard_layout_table(self):
        """카드별 레이아웃(정렬·표시). 행 없음 => visible_yn 은 앱에서 'Y'로 간주."""
        self.db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS t_dashboard_card_layout (
                user_id TEXT NOT NULL,
                farm_cd TEXT NOT NULL,
                card_id TEXT NOT NULL,
                sort_ord INTEGER NOT NULL DEFAULT 0,
                visible_yn TEXT NOT NULL DEFAULT 'Y',
                PRIMARY KEY (user_id, farm_cd, card_id)
            )
            """
        )

    def _migrate_legacy_card_pref_table(self):
        """구 t_dashboard_card_pref 데이터를 layout 테이블로 이전(한 번만 유효)."""
        chk = self.db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='t_dashboard_card_pref'"
        )
        if not chk:
            return
        self.db.execute_query(
            """
            INSERT OR IGNORE INTO t_dashboard_card_layout (user_id, farm_cd, card_id, sort_ord, visible_yn)
            SELECT user_id, farm_cd, card_id, 0, visible_yn FROM t_dashboard_card_pref
            """
        )

    def _default_sort_ord(self, card_id: str) -> int:
        """DB 행 없을 때 기본 순서(1..8)."""
        try:
            return DEFAULT_CARD_ORDER.index(card_id) + 1
        except ValueError:
            return 999

    def _sort_ord_for_card(self, card_id: str) -> int:
        return self._default_sort_ord(card_id)

    def _load_layout_from_db(self):
        """DEFAULT_CARD_ORDER + DB 오버라이드. 행 없으면 visible_yn = 'Y'."""
        rows = self.db.execute_query(
            "SELECT card_id, sort_ord, visible_yn FROM t_dashboard_card_layout "
            "WHERE user_id = ? AND farm_cd = ?",
            (self.user_id, self.farm_cd),
        )
        self._layout_rows = {}
        if rows:
            for r in rows:
                cid = str(r[0])
                self._layout_rows[cid] = {
                    "sort_ord": int(r[1]),
                    "visible_yn": str(r[2]).strip().upper() or "Y",
                }
        self._visible_map = {}
        for cid in DEFAULT_CARD_ORDER:
            if cid in self._layout_rows:
                self._visible_map[cid] = self._layout_rows[cid]["visible_yn"]
            else:
                self._visible_map[cid] = "Y"
        self._hidden_card_ids = {
            cid for cid, yn in self._visible_map.items() if yn == "N"
        }

    def _visible_card_order(self):
        """표시 카드만, sort_ord(없으면 기본 인덱스) 순으로 정렬."""
        visible = [cid for cid in DEFAULT_CARD_ORDER if self._visible_map.get(cid, "Y") != "N"]

        def sort_key(cid):
            if cid in self._layout_rows:
                s = int(self._layout_rows[cid]["sort_ord"])
            else:
                s = self._default_sort_ord(cid)
            tie = DEFAULT_CARD_ORDER.index(cid)
            return (s, tie)

        visible.sort(key=sort_key)
        return visible

    def _persist_visible_sort_order(self, ordered_ids):
        """보이는 카드 순서만 DB에 반영 (sort_ord 1..n, visible_yn='Y')."""
        for i, cid in enumerate(ordered_ids):
            sort_ord = i + 1
            self.db.execute_query(
                """
                INSERT INTO t_dashboard_card_layout (user_id, farm_cd, card_id, sort_ord, visible_yn)
                VALUES (?, ?, ?, ?, 'Y')
                ON CONFLICT(user_id, farm_cd, card_id) DO UPDATE SET
                    sort_ord = excluded.sort_ord,
                    visible_yn = 'Y'
                """,
                (self.user_id, self.farm_cd, cid, sort_ord),
            )

    def _on_dnd_drag_started(self, card_id: str):
        """드래그 시작 직전: 그리드에서 분리해 절대 좌표로 두고, 이후 호버마다 밀어내기 애니메이션."""
        self._dnd_initial_visible_order = list(self._visible_card_order())
        if card_id not in self._dnd_initial_visible_order:
            return
        self._dnd_source = card_id
        self._dnd_old_slot = self._dnd_initial_visible_order.index(card_id)
        self._dnd_last_hover = None
        self._detach_cards_for_dnd()
        self._dnd_detached = True

    def _detach_cards_for_dnd(self):
        """현재 그리드 기하를 스냅샷한 뒤 레이아웃에서 제거(원본 카드는 움직이지 않음)."""
        vis = self._visible_card_order()
        geoms = {}
        for cid in vis:
            geoms[cid] = QRect(self._cards[cid].geometry())
        if vis:
            self._dnd_cell_w = max(1, geoms[vis[0]].width())
            self._dnd_cell_h = max(1, geoms[vis[0]].height())
        self._clear_grid_layout()
        for cid in vis:
            w = self._cards[cid]
            w.setParent(self.cards_host)
            w.setGeometry(geoms[cid])
            w.show()
            w.raise_()

    def _cell_rect_for_slot(self, slot: int, n_slots: int) -> QRect:
        """2열 그리드에서 slot(0..n-1)의 목표 사각형."""
        row, col = slot // 2, slot % 2
        cw, ch, g = self._dnd_cell_w, self._dnd_cell_h, self._dnd_gap
        x = col * (cw + g)
        y = row * (ch + g)
        return QRect(x, y, cw, ch)

    def _preview_order_for_dnd(self, source_id: str, target_id: str):
        vis = list(self._dnd_initial_visible_order or [])
        if source_id not in vis or target_id not in vis:
            return vis
        vis.remove(source_id)
        idx = vis.index(target_id)
        vis.insert(idx, source_id)
        return vis

    def _animate_dnd_shift(self, preview_order, source_id: str, old_slot: int):
        """드래그 소스는 고정, 나머지 카드만 목표 슬롯으로 부드럽게 이동."""
        if self._dnd_anim_group is not None:
            self._dnd_anim_group.stop()
            self._dnd_anim_group.deleteLater()
            self._dnd_anim_group = None

        n = len(preview_order)
        slots = [i for i in range(n) if i != old_slot]
        others = [c for c in preview_order if c != source_id]
        if len(others) != len(slots):
            return

        grp = QParallelAnimationGroup(self)
        dur = 180
        ec = QEasingCurve(QEasingCurve.Type.OutCubic)
        for j, cid in enumerate(others):
            target_rect = self._cell_rect_for_slot(slots[j], n)
            w = self._cards[cid]
            anim = QPropertyAnimation(w, b"geometry", self)
            anim.setDuration(dur)
            anim.setStartValue(w.geometry())
            anim.setEndValue(target_rect)
            anim.setEasingCurve(ec)
            grp.addAnimation(anim)
        grp.start()
        self._dnd_anim_group = grp

    def _on_dnd_drag_hover(self, source_id: str, target_id: str):
        if not self._dnd_detached or self._dnd_source is None:
            return
        if source_id != self._dnd_source:
            return
        if target_id == source_id:
            return
        if target_id == self._dnd_last_hover:
            return
        self._dnd_last_hover = target_id
        preview = self._preview_order_for_dnd(source_id, target_id)
        self._animate_dnd_shift(preview, source_id, self._dnd_old_slot)

    def _on_dnd_drag_finished(self, _card_id: str):
        """드롭 없이 취소된 경우에만 그리드 복구. 성공 시 _on_reorder_drop에서 이미 reflow."""
        if self._dnd_anim_group is not None:
            self._dnd_anim_group.stop()
            self._dnd_anim_group.deleteLater()
            self._dnd_anim_group = None
        if self._dnd_detached:
            self._reflow_grid_full()
        self._dnd_detached = False
        self._dnd_source = None
        self._dnd_last_hover = None
        self._dnd_initial_visible_order = None

    def _on_reorder_drop(self, source_id: str, target_id: str):
        """드롭으로 보이는 카드 순서 변경 후 DB 저장."""
        self._dnd_detached = False
        if self._dnd_anim_group is not None:
            self._dnd_anim_group.stop()
            self._dnd_anim_group.deleteLater()
            self._dnd_anim_group = None

        if source_id == target_id:
            return
        vis = self._visible_card_order()
        if source_id not in vis or target_id not in vis:
            return
        vis = list(vis)
        vis.remove(source_id)
        idx = vis.index(target_id)
        vis.insert(idx, source_id)
        self._persist_visible_sort_order(vis)
        self._load_layout_from_db()
        self._reflow_grid_full()
        self._play_drop_settle_animation()

    def _open_card_manage_dialog(self):
        hidden = [cid for cid in DEFAULT_CARD_ORDER if self._visible_map.get(cid, "Y") == "N"]
        if not hidden:
            QMessageBox.information(self, "카드 관리", "숨긴 카드가 없습니다.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("카드 관리")
        dlg.setMinimumWidth(400)
        root = QVBoxLayout(dlg)
        root.setSpacing(10)
        hidden_desc = QLabel("숨긴 카드를 다시 표시할 수 있습니다.", styleSheet=MainStyles.TXT_CAPTION)
        root.addWidget(hidden_desc)
        for cid in hidden:
            title = CARDS_META[cid][0]
            icon = CARDS_META[cid][1]
            row = QHBoxLayout()
            title_lbl = QLabel(f"{icon}  {title}", styleSheet=MainStyles.TXT_CARD_TITLE + " color:#2D3748;")
            row.addWidget(title_lbl)
            row.addStretch()
            btn = QPushButton("다시 표시")
            btn.setStyleSheet(MainStyles.BTN_SECONDARY)
            btn.setFixedHeight(28)

            def _make_restore(c):
                def _go():
                    self._restore_card(c)
                    dlg.accept()

                return _go

            btn.clicked.connect(_make_restore(cid))
            row.addWidget(btn)
            root.addLayout(row)

        btn_all = QPushButton("모두 표시")
        btn_all.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_all.setFixedHeight(28)
        btn_all.clicked.connect(lambda: (self._restore_all_hidden_cards(), dlg.accept()))
        root.addWidget(btn_all)

        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_close.clicked.connect(dlg.accept)
        root.addWidget(btn_close)
        dlg.exec()

    def _restore_card(self, card_id: str):
        self.db.execute_query(
            "DELETE FROM t_dashboard_card_layout "
            "WHERE user_id = ? AND farm_cd = ? AND card_id = ?",
            (self.user_id, self.farm_cd, card_id),
        )
        self._load_layout_from_db()
        self._reflow_grid_full()

    def _restore_all_hidden_cards(self):
        self.db.execute_query(
            "DELETE FROM t_dashboard_card_layout "
            "WHERE user_id = ? AND farm_cd = ? AND visible_yn = 'N'",
            (self.user_id, self.farm_cd),
        )
        self._load_layout_from_db()
        self._reflow_grid_full()

    def _on_card_hide_requested(self, card_id):
        if card_id not in DEFAULT_CARD_ORDER:
            return
        sort_ord = self._sort_ord_for_card(card_id)
        self.db.execute_query(
            """
            INSERT INTO t_dashboard_card_layout (user_id, farm_cd, card_id, sort_ord, visible_yn)
            VALUES (?, ?, ?, ?, 'N')
            ON CONFLICT(user_id, farm_cd, card_id) DO UPDATE SET visible_yn = 'N'
            """,
            (self.user_id, self.farm_cd, card_id, sort_ord),
        )
        self._load_layout_from_db()
        self._reflow_grid_full()

    def _clear_grid_layout(self):
        """그리드에서 위젯만 제거(부모/컨테이너 크기는 건드리지 않음)."""
        if self._dnd_anim_group is not None:
            self._dnd_anim_group.stop()
            self._dnd_anim_group.deleteLater()
            self._dnd_anim_group = None
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._grid_layout.removeWidget(widget)

    def _reflow_card_grid(self):
        """보이는 카드만 그리드에 다시 넣기. cards_host/dashboard 등 컨테이너 높이는 reflow에서 조정하지 않음."""
        self._card_order = self._visible_card_order()
        self._clear_grid_layout()

        for cid, card in self._cards.items():
            if cid not in self._card_order:
                card.setParent(self.cards_host)
                card.hide()

        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)

        for idx, cid in enumerate(self._card_order):
            card = self._cards[cid]
            card.show()
            self._grid_layout.addWidget(card, idx // 2, idx % 2)

        self._grid_layout.invalidate()
        self.cards_host.updateGeometry()

        self._apply_editing_mode_to_cards()

    def _reflow_grid_full(self):
        self._reflow_card_grid()

    def _open_detail_page(self, card_id: str):
        """상세 버튼·내부 네비: 대시보드 stack으로 상세 위젯 표시(MainApp.switch_page와 별개)."""
        if card_id in self.DETAIL_IDS:
            target_id = "market_analysis" if card_id == "market" else card_id
            self._show_detail_page(target_id)

    def _show_detail_page(self, page_id):
        normalized_page_id = "market" if page_id == "market_analysis" else page_id
        if normalized_page_id not in self._detail_pages:
            if normalized_page_id == "market":
                self._detail_pages[page_id] = MarketPricePage(self.db, self.session, self)
            elif normalized_page_id == "weather":
                self._detail_pages[normalized_page_id] = WeatherDetailPage(self.db, self.session, self)
            elif normalized_page_id == "labor":
                self._detail_pages[normalized_page_id] = CostDetailPage(self.db, self.session, self)
            elif normalized_page_id == "kpi":
                self._detail_pages[normalized_page_id] = KpiDetailPage(self.db, self.session, self)
            else:
                return
            if normalized_page_id == "market":
                self._detail_pages["market"] = self._detail_pages[page_id]
                self._detail_pages["market_analysis"] = self._detail_pages[page_id]
            pg = self._detail_pages[normalized_page_id]
            pg.back_to_dashboard.connect(self._back_to_dashboard)
            pg.navigate_to.connect(self._show_detail_page)
            self.stack.addWidget(pg)
        page = self._detail_pages[normalized_page_id]
        self.stack.setCurrentWidget(page)
        if page_id == "market_analysis" and hasattr(page, "open_market_analysis_tab"):
            page.open_market_analysis_tab()

    def _back_to_dashboard(self):
        self.stack.setCurrentWidget(self.dashboard_widget)

    def load_summary_data(self):
        self.lbl_date.setText(datetime.datetime.now().strftime("%Y-%m-%d"))
        self.lbl_farm.setText(self.farm_nm)
        work_today = orders_today = receivables = sales_today = 0
        cost_summary = self._empty_cost_summary()
        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            sales_dt_norm = _norm_ymd_sql("sales_dt")
            r1 = self.db.execute_query(
                f"SELECT COALESCE(SUM(tot_sales_amt + tot_ship_fee), 0) "
                f"FROM t_sales_master WHERE farm_cd = ? AND {sales_dt_norm} = ?",
                (self.farm_cd, today),
            )
            r2 = self.db.execute_query(
                "SELECT COALESCE(SUM(tot_unpaid_amt), 0) FROM t_sales_master WHERE farm_cd = ?",
                (self.farm_cd,),
            )
            r3 = self.db.execute_query(
                "SELECT COUNT(*) FROM t_work_log WHERE farm_cd = ? AND work_dt = ?",
                (self.farm_cd, today),
            )
            r4 = self.db.execute_query(
                "SELECT COUNT(*) FROM t_order_master WHERE farm_cd = ? AND order_dt = ?",
                (self.farm_cd, today),
            )
            sales_today = int(r1[0][0]) if r1 and r1[0] else 0
            receivables = int(r2[0][0]) if r2 and r2[0] else 0
            work_today = int(r3[0][0]) if r3 and r3[0] else 0
            orders_today = int(r4[0][0]) if r4 and r4[0] else 0
            if hasattr(self.db, "get_dashboard_cost_summary"):
                cost_summary = self.db.get_dashboard_cost_summary(self.farm_cd, today) or self._empty_cost_summary()
        except Exception as e:
            print(f"[Dashboard] load_summary_data failed: {e}")
        self.lbl_sales.setText(f"오늘 매출 {sales_today:,}원")
        self.lbl_cost.setText(f"오늘 비용 {int(cost_summary.get('today_total') or 0):,}원")
        self.lbl_receivables.setText(f"미수 {receivables:,}원")
        self.lbl_alert_count.setText("알림 0건")
        if "work" in self._cards:
            self._cards["work"].set_main_value(f"{work_today}건")
        if "orders" in self._cards:
            self._cards["orders"].set_main_value(f"{orders_today}건")
        if "receivables" in self._cards:
            self._cards["receivables"].set_main_value(f"{receivables:,}원")
        if "labor" in self._cards and hasattr(self._cards["labor"], "set_cost_summary_data"):
            self._cards["labor"].set_cost_summary_data(cost_summary)
        if "market" in self._cards:
            self._cards["market"].set_market_summary_data(
                self._build_market_analysis_card_payload()
            )

    @staticmethod
    def _empty_cost_summary():
        return {
            "today_total": 0,
            "month_total": 0,
            "unpaid_total_count": 0,
            "unpaid_total_amount": 0,
            "labor_today": 0,
            "labor_month": 0,
            "labor_unpaid_count": 0,
            "labor_unpaid_amount": 0,
            "expense_today": 0,
            "expense_month": 0,
            "expense_unpaid_count": 0,
            "expense_unpaid_amount": 0,
        }

    def refresh_data(self):
        """홈 재진입 시 대시보드로 복귀 후 요약·그리드 갱신."""
        if getattr(self, "stack", None) and getattr(self, "dashboard_widget", None):
            self.stack.setCurrentWidget(self.dashboard_widget)
        self._load_layout_from_db()
        self.load_summary_data()
        if self._cards:
            self._reflow_grid_full()

    def _build_market_card_payload(self):
        started = time.perf_counter()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        fallback = {
            "decision": "관망",
            "special_ratio": 0.0,
            "large_ratio": 0.0,
            "top_corp_prices": [],
            "source": "fallback",
            "status": "error",
            "api_call_count": 0,
            "requested_date": today,
            "base_date": "",
            "fallback_used": False,
            "fallback_attempts": 0,
        }
        if self.market_service is None:
            return fallback
        try:
            payload = self.market_service.get_market_card_summary_fast(
                date=today,
                variety="신고",
                market="가락",
                corp="전체",
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            print(
                "[Dashboard] market card load "
                f"requested_date={payload.get('requested_date')} "
                f"base_date={payload.get('base_date')} "
                f"fallback_used={payload.get('fallback_used')} "
                f"attempts={payload.get('fallback_attempts')} "
                f"source={payload.get('source')} "
                f"api_calls={payload.get('api_call_count')} "
                f"elapsed_ms={elapsed_ms}"
            )
            return payload
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            print(f"[Dashboard] market card payload failed: {e} (elapsed_ms={elapsed_ms})")
            return fallback

    def _build_market_analysis_card_payload(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        fallback = {
            "signal": "관망",
            "decision": "관망",
            "base_avg_price": None,
            "d1_pct": None,
            "d7_pct": None,
            "d30_pct": None,
            "base_special_ratio": 0.0,
            "base_within20_ratio": 0.0,
            "requested_date": today,
            "base_date": today,
            "status": "empty",
            "variety": "신고",
            "market": "가락",
            "reason_lines": ["분석 대기"],
        }
        if self.market_analysis_service is None:
            return fallback
        try:
            # 시장 상세와 동일한 summary 행을 쓰도록: '오늘' 이전 최신 거래일을 기준일로 고정
            # (미래·휴일만 넣으면 최신 행이 바뀌어 신호·가격이 상세(선택일)와 어긋남)
            ref_date = self.market_analysis_service.get_latest_summary_date(
                variety="신고",
                market="가락",
                on_or_before=today,
            )
            base_date = ref_date or today
            summary = self.market_analysis_service.get_dashboard_summary(
                base_date=base_date,
                variety="신고",
                market="가락",
            )
            payload = dict(fallback)
            payload.update(summary or {})
            sig = str(payload.get("signal") or "관망").strip()
            payload["signal"] = sig
            payload["decision"] = sig
            return payload
        except Exception as e:
            print(f"[Dashboard] market analysis card payload failed: {e}")
            return fallback
