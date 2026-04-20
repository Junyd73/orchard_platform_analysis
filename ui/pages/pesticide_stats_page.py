# -*- coding: utf-8 -*-
"""농약 연간 사용 통계: 일자별 사용량·현재고·월별 사용 건수."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from matplotlib import rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.pesticide_manager import PesticideManager
from ui.styles import DEFAULT_FONT_FAMILY, MainStyles

# matplotlib 기본(DejaVu Sans)은 한글 미지원 → UI와 동일 폰트 사용
rcParams["font.family"] = "sans-serif"
rcParams["font.sans-serif"] = [DEFAULT_FONT_FAMILY, "Gulim", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False


def _lbl_field(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setStyleSheet(MainStyles.LBL_GRID_HEADER)
    return lb


def _norm_search(s: str) -> str:
    return (s or "").replace(" ", "").replace("\u3000", "").lower()


# 일자별 표: MainStyles.TABLE과 문자열 병합하지 않음(동일 선택자가 두 번 정의되면 셀 padding·행 높이가 안 먹는 경우 있음)
# 색·선택·호버만 공통 테이블과 맞춤, 셀 padding은 세로 0으로 고정
_PEST_STATS_TABLE_STYLE = """
    QTableWidget {
        background-color: white;
        gridline-color: #DCD6CF;
        border: none;
        selection-background-color: #E8F0E7;
        selection-color: #2D5A27;
        outline: none;
    }
    QTableWidget::item {
        padding: 0px 4px;
    }
    QTableWidget::item:hover {
        background-color: #E3F2FD;
        color: black;
    }
    QHeaderView::section {
        background-color: #F8F9FA;
        min-height: 26px;
        max-height: 26px;
        padding: 0px 2px;
        border: none;
        border-bottom: 1px solid #EAE7E2;
        font-weight: bold;
        color: #444;
    }
"""
_PEST_STATS_DATA_ROW_H = 20
_PEST_STATS_HDR_ROW_H = 24


class PesticideStatsPage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        self.farm_cd = str(session.get("farm_cd") or "")
        self.mgr = PesticideManager(db_manager)
        self._usage_day_iso: list[str] = []
        self._scroll_sync = False
        self._sel_sync = False
        self._matrix = {}
        self._fig = Figure(figsize=(7, 3.6), layout="tight")
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setMinimumHeight(320)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()
        self.setStyleSheet(MainStyles.MAIN_BG)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("📊 농약 사용통계")
        title.setStyleSheet(MainStyles.LBL_TITLE)
        root.addWidget(title)

        filt = QGroupBox("조회 조건")
        filt.setStyleSheet(MainStyles.GROUP_BOX)
        fg = QGridLayout(filt)
        fg.setContentsMargins(16, 16, 16, 12)
        fg.setHorizontalSpacing(12)
        fg.setVerticalSpacing(8)
        self.sp_year = QSpinBox()
        self.sp_year.setRange(2000, 2100)
        self.sp_year.setValue(date.today().year)
        self.sp_year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sp_year.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self.sp_year.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sp_year.setFixedWidth(96)
        self.q_search = QLineEdit()
        self.q_search.setPlaceholderText("품목명 검색(포함)")
        self.q_search.setStyleSheet(MainStyles.INPUT_CENTER)
        self.q_search.setFixedHeight(28)
        self.chk_used_only = QCheckBox("사용 있는 품목만 보기")
        self.chk_used_only.setStyleSheet("color: #333;")
        btn = QPushButton("조회")
        btn.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._load_data)
        row_al = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        fg.addWidget(_lbl_field("연도"), 0, 0, row_al)
        fg.addWidget(self.sp_year, 0, 1, row_al)
        fg.addWidget(_lbl_field("품목 검색"), 0, 2, row_al)
        fg.addWidget(self.q_search, 0, 3, row_al)
        fg.addWidget(self.chk_used_only, 0, 4, row_al)
        fg.addWidget(btn, 0, 5, row_al)
        fg.setColumnStretch(3, 1)
        root.addWidget(filt)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)

        tbl_wrap = QFrame()
        tbl_wrap.setStyleSheet(MainStyles.CARD)
        tbl_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tw = QHBoxLayout(tbl_wrap)
        tw.setContentsMargins(8, 8, 8, 8)
        tw.setSpacing(0)

        self.tbl_left = QTableWidget()
        self.tbl_left.setColumnCount(3)
        self.tbl_left.setHorizontalHeaderLabels(["품목명", "사용량", "현재고량"])
        self.tbl_left.setStyleSheet(_PEST_STATS_TABLE_STYLE)
        self.tbl_left.setShowGrid(True)
        self.tbl_left.verticalHeader().setVisible(False)
        self.tbl_left.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_left.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_left.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self.tbl_left.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setFixedHeight(_PEST_STATS_HDR_ROW_H)
        self.tbl_left.setFixedWidth(320)
        vh_l = self.tbl_left.verticalHeader()
        vh_l.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh_l.setMinimumSectionSize(1)
        vh_l.setDefaultSectionSize(_PEST_STATS_DATA_ROW_H)

        self.tbl_right = QTableWidget()
        self.tbl_right.setStyleSheet(_PEST_STATS_TABLE_STYLE)
        self.tbl_right.setShowGrid(True)
        self.tbl_right.verticalHeader().setVisible(False)
        self.tbl_right.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_right.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_right.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hr = self.tbl_right.horizontalHeader()
        hr.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        hr.setFixedHeight(_PEST_STATS_HDR_ROW_H)
        self.tbl_right.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        vh_r = self.tbl_right.verticalHeader()
        vh_r.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh_r.setMinimumSectionSize(1)
        vh_r.setDefaultSectionSize(_PEST_STATS_DATA_ROW_H)
        self.tbl_right.verticalScrollBar().valueChanged.connect(self._on_scroll_right)
        self.tbl_left.verticalScrollBar().valueChanged.connect(self._on_scroll_left)

        tw.addWidget(self.tbl_left)
        tw.addWidget(self.tbl_right, stretch=1)

        chart_fr = QFrame()
        chart_fr.setStyleSheet(MainStyles.CARD)
        chart_fr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cvl = QVBoxLayout(chart_fr)
        cvl.setContentsMargins(12, 12, 12, 12)
        cvl.addWidget(QLabel("월별 사용 건수(사용 헤더 기준)"))
        cvl.addWidget(self._canvas, stretch=1)

        self.tabs.addTab(tbl_wrap, "일자별 사용")
        self.tabs.addTab(chart_fr, "월별 그래프")
        root.addWidget(self.tabs, stretch=1)

        self.tbl_left.currentCellChanged.connect(self._on_cell_left)
        self.tbl_right.currentCellChanged.connect(self._on_cell_right)

    def refresh_data(self):
        self._load_data()

    def _on_scroll_left(self, v: int):
        if self._scroll_sync:
            return
        self._scroll_sync = True
        self.tbl_right.verticalScrollBar().setValue(v)
        self._scroll_sync = False

    def _on_scroll_right(self, v: int):
        if self._scroll_sync:
            return
        self._scroll_sync = True
        self.tbl_left.verticalScrollBar().setValue(v)
        self._scroll_sync = False

    def _on_cell_left(self, r: int, c: int, pr: int, pc: int):
        if self._sel_sync or r < 0:
            return
        self._sel_sync = True
        self.tbl_right.selectRow(r)
        if self.tbl_right.columnCount() > 0:
            self.tbl_right.setCurrentCell(r, 0)
        self._sel_sync = False

    def _on_cell_right(self, r: int, c: int, pr: int, pc: int):
        if self._sel_sync or r < 0:
            return
        self._sel_sync = True
        self.tbl_left.selectRow(r)
        self.tbl_left.setCurrentCell(r, 0)
        self._sel_sync = False

    def _load_data(self):
        y = int(self.sp_year.value())
        q = _norm_search(self.q_search.text())
        only_used = self.chk_used_only.isChecked()

        self._matrix = self.mgr.get_yearly_usage_matrix(y, self.farm_cd)
        pairs: list[tuple[int, dict]] = []
        for iid, rec in self._matrix.items():
            nm = _norm_search(str(rec.get("item_nm") or ""))
            if q and q not in nm:
                continue
            if only_used and int(rec.get("total_qty") or 0) <= 0:
                continue
            pairs.append((iid, rec))
        pairs.sort(key=lambda x: (x[1].get("item_nm") or ""))

        # 표시 행들에서 실제 사용이 있는 날짜만 열로 나열(연도 내 ISO일자 합집합·정렬)
        day_keys: set[str] = set()
        for _, rec in pairs:
            for dk in (rec.get("daily") or {}):
                day_keys.add(str(dk).strip())
        self._usage_day_iso = sorted(day_keys)

        n = len(pairs)
        ncol = len(self._usage_day_iso)

        self.tbl_left.clearContents()
        self.tbl_left.setRowCount(n)
        self.tbl_right.clearContents()
        self.tbl_right.setRowCount(n)
        self.tbl_right.setColumnCount(ncol)
        labels = []
        for iso in self._usage_day_iso:
            try:
                dd = date.fromisoformat(iso[:10])
                labels.append(f"{dd.month}/{dd.day}")
            except ValueError:
                labels.append(iso)
        self.tbl_right.setHorizontalHeaderLabels(labels)
        cw = 44
        for j in range(ncol):
            self.tbl_right.setColumnWidth(j, cw)

        for i, (iid, rec) in enumerate(pairs):
            nm = str(rec.get("item_nm") or "")
            tot = int(rec.get("total_qty") or 0)
            stk = int(rec.get("current_stock") or 0)
            daily = rec.get("daily") or {}
            it0 = QTableWidgetItem(nm)
            it1 = QTableWidgetItem(str(tot))
            it2 = QTableWidgetItem(str(stk))
            it1.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it2.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_left.setItem(i, 0, it0)
            self.tbl_left.setItem(i, 1, it1)
            self.tbl_left.setItem(i, 2, it2)
            for j, dk in enumerate(self._usage_day_iso):
                uq = int(daily.get(dk, 0) or 0)
                cell = QTableWidgetItem(str(uq) if uq else "")
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_right.setItem(i, j, cell)

        self._apply_data_row_heights(n)
        self._draw_chart(y)

    def _apply_data_row_heights(self, n: int) -> None:
        """스타일시트만으로는 행 높이가 안 줄어드는 경우가 있어 행 단위로 고정."""
        h = _PEST_STATS_DATA_ROW_H
        for i in range(n):
            self.tbl_left.setRowHeight(i, h)
            self.tbl_right.setRowHeight(i, h)

    def _draw_chart(self, year: int):
        self._ax.clear()
        monthly = self.mgr.get_monthly_usage_count(year, self.farm_cd)
        xs = list(range(1, 13))
        ys = [monthly.get(m, 0) for m in xs]
        self._ax.bar(xs, ys)
        self._ax.set_xticks(xs)
        self._ax.set_xlabel("월")
        self._ax.set_ylabel("건수")
        self._ax.grid(True, linestyle="--", alpha=0.3)
        self._fig.tight_layout()
        self._canvas.draw_idle()
