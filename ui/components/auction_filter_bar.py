# -*- coding: utf-8 -*-
"""
경매/시장 조회용 공통 필터 바.
날짜 → 품목 → 품종 → 시장 → 법인 → 조회
(실시간·정산 탭 전용. 시장분석 탭은 본 위젯 미사용.)
"""
from __future__ import annotations

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ui.styles import MainStyles

FILTER_CONTROL_HEIGHT = 28

# 공공 API 소분류(품종) 코드 — DB 품종명과 매핑 (서비스 미수정, UI 전용)
VARIETY_NAME_TO_API_ITEM_CD = {
    "신고": "06-02-01",
    "원황": "06-02-02",
    "화산": "06-02-03",
    "추황": "06-02-04",
}
DEFAULT_API_ITEM_CD = "06-02-01"

MARKET_OPTIONS = (
    ("가락", "110001"),
    ("부평", "230001"),
)


def _code_row_get(row, key: str, default: str = "") -> str:
    """공통코드 행: dict 또는 sqlite3.Row 모두 지원."""
    if row is None:
        return default
    if isinstance(row, dict):
        v = row.get(key, default)
        return default if v is None else str(v)
    try:
        v = row[key]
        return default if v is None else str(v)
    except (KeyError, TypeError, IndexError):
        return default


def _api_item_cd_for_variety_row(code_nm: str, code_cd: str) -> str:
    nm = str(code_nm or "").strip()
    if nm in VARIETY_NAME_TO_API_ITEM_CD:
        return VARIETY_NAME_TO_API_ITEM_CD[nm]
    cd = str(code_cd or "").strip()
    if len(cd) >= 7 and cd[:2].isdigit():
        return cd
    return DEFAULT_API_ITEM_CD


class AuctionFilterBar(QWidget):
    """실시간·정산 탭 필터. code_mgr: CodeManager(db, farm_cd)."""

    def __init__(self, db, code_mgr, style_owner=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._code_mgr = code_mgr
        self._style_owner = style_owner
        self._loading = False

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self._apply_ctrl_style(self.date_edit)

        self.btn_today = QPushButton("오늘")
        self.btn_yesterday = QPushButton("어제")
        self._apply_btn_style(self.btn_today)
        self._apply_btn_style(self.btn_yesterday)
        self.btn_today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.btn_yesterday.clicked.connect(
            lambda: self.date_edit.setDate(QDate.currentDate().addDays(-1))
        )

        date_wrap = QWidget()
        dl = QHBoxLayout(date_wrap)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        dl.addWidget(self.date_edit, 2)
        dl.addWidget(self.btn_today)
        dl.addWidget(self.btn_yesterday)
        root.addWidget(date_wrap, 1)

        self.cmb_item = QComboBox()
        self._apply_ctrl_style(self.cmb_item)
        root.addWidget(self._wrap_labeled("품목", self.cmb_item), 1)

        self.cmb_variety = QComboBox()
        self._apply_ctrl_style(self.cmb_variety)
        root.addWidget(self._wrap_labeled("품종", self.cmb_variety), 1)

        self.cmb_market = QComboBox()
        self._apply_ctrl_style(self.cmb_market)
        for nm, cd in MARKET_OPTIONS:
            self.cmb_market.addItem(nm, cd)
        self.cmb_market.setCurrentIndex(0)
        root.addWidget(self._wrap_labeled("시장", self.cmb_market), 1)

        self.cmb_corp = QComboBox()
        self._apply_ctrl_style(self.cmb_corp)
        self.cmb_corp.addItem("전체", "")
        root.addWidget(self._wrap_labeled("법인", self.cmb_corp), 1)

        self.btn_search = QPushButton("조회")
        self.btn_search.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_search.setFixedHeight(FILTER_CONTROL_HEIGHT)
        self.btn_search.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        root.addWidget(self.btn_search)

        self._load_items_from_db()
        self.cmb_item.currentIndexChanged.connect(self._on_item_changed)
        self.cmb_market.currentIndexChanged.connect(self._on_market_changed)

    def _wrap_labeled(self, title: str, w: QWidget) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lb = QLabel(title)
        lb.setStyleSheet("color:#4A5568;border:none;background:transparent;")
        lay.addWidget(lb)
        lay.addWidget(w, 1)
        return box

    def _apply_ctrl_style(self, w: QWidget):
        if self._style_owner and hasattr(self._style_owner, "_apply_filter_control_style"):
            self._style_owner._apply_filter_control_style(w)
        else:
            w.setStyleSheet(MainStyles.COMBO)
            if hasattr(w, "setFixedHeight"):
                w.setFixedHeight(FILTER_CONTROL_HEIGHT)
            if isinstance(w, QComboBox):
                v = w.view()
                if v is not None:
                    v.setAutoFillBackground(True)

    def _apply_btn_style(self, btn: QPushButton):
        if self._style_owner and hasattr(self._style_owner, "_apply_quick_date_button_style"):
            self._style_owner._apply_quick_date_button_style(btn)
        else:
            btn.setStyleSheet(MainStyles.BTN_SECONDARY)
            btn.setFixedHeight(FILTER_CONTROL_HEIGHT)

    def _load_items_from_db(self):
        self._loading = True
        self.cmb_item.clear()
        rows = []
        if self._code_mgr:
            try:
                rows = self._code_mgr.get_common_codes("FR01") or []
            except Exception:
                rows = []
        if not rows:
            self.cmb_item.addItem("배", "FR010100")
        else:
            for r in rows:
                self.cmb_item.addItem(
                    _code_row_get(r, "code_nm"), _code_row_get(r, "code_cd")
                )
        # 기본 품목: 배
        idx = -1
        for i in range(self.cmb_item.count()):
            if "배" in self.cmb_item.itemText(i):
                idx = i
                break
        self.cmb_item.setCurrentIndex(max(0, idx))
        self._loading = False
        self._reload_varieties()

    def _reload_varieties(self):
        self._loading = True
        self.cmb_variety.clear()
        item_cd = self.cmb_item.currentData()
        rows = []
        if self._code_mgr and item_cd:
            try:
                rows = self._code_mgr.get_common_codes(str(item_cd)) or []
            except Exception:
                rows = []
        if not rows:
            for nm, api_cd in VARIETY_NAME_TO_API_ITEM_CD.items():
                self.cmb_variety.addItem(nm, api_cd)
        else:
            for r in rows:
                nm = _code_row_get(r, "code_nm").strip()
                cd = _code_row_get(r, "code_cd").strip()
                api_cd = _api_item_cd_for_variety_row(nm, cd)
                self.cmb_variety.addItem(nm or cd, api_cd)
        if self.cmb_variety.count() == 0:
            self.cmb_variety.addItem("신고", DEFAULT_API_ITEM_CD)
        self.cmb_variety.setCurrentIndex(0)
        self._loading = False

    def _on_item_changed(self, _idx: int = -1):
        if self._loading:
            return
        self._reload_varieties()
        self._reset_corp_combo()

    def _on_market_changed(self, _idx: int = -1):
        if self._loading:
            return
        self._reset_corp_combo()

    def _reset_corp_combo(self):
        self._loading = True
        self.cmb_corp.blockSignals(True)
        self.cmb_corp.clear()
        self.cmb_corp.addItem("전체", "")
        self.cmb_corp.setCurrentIndex(0)
        self.cmb_corp.blockSignals(False)
        self._loading = False

    def set_corp_options(self, names: list, preferred: str = "전체"):
        """조회 결과 등으로 법인 목록 갱신."""
        self._loading = True
        self.cmb_corp.blockSignals(True)
        self.cmb_corp.clear()
        self.cmb_corp.addItem("전체", "")
        seen = set()
        for n in names or []:
            t = str(n or "").strip()
            if t and t not in seen:
                seen.add(t)
                self.cmb_corp.addItem(t, t)
        pref = str(preferred or "전체").strip()
        ix = self.cmb_corp.findText(pref)
        if ix >= 0:
            self.cmb_corp.setCurrentIndex(ix)
        else:
            self.cmb_corp.setCurrentIndex(0)
        self.cmb_corp.blockSignals(False)
        self._loading = False

    def reset_to_defaults(self):
        self._loading = True
        self.date_edit.setDate(QDate.currentDate())
        self._load_items_from_db()
        self.cmb_market.setCurrentIndex(0)
        self._reset_corp_combo()
        self._loading = False

    def get_filters(self) -> dict:
        """표준 API 키 + 동일 콤보에서 읽는 표시명(별도 재가공 없음).

        필수: target_date, item_cd, variety_cd, market_cd, corp_cd
        표시명: item_name, variety_name, market_name, corp_name (로컬 재필터 등)
        """
        corp_raw = self.cmb_corp.currentData()
        corp_name = str(self.cmb_corp.currentText() or "").strip() or "전체"
        return {
            "target_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "item_cd": self.cmb_item.currentData(),
            "variety_cd": self.cmb_variety.currentData(),
            "market_cd": self.cmb_market.currentData(),
            "corp_cd": (None if corp_raw in ("", None) else corp_raw),
            "item_name": self.cmb_item.currentText().strip(),
            "variety_name": self.cmb_variety.currentText().strip(),
            "market_name": self.cmb_market.currentText().strip(),
            "corp_name": corp_name if corp_name else "전체",
        }
