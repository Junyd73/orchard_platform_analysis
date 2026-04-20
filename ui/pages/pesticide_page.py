# -*- coding: utf-8 -*-
"""농약 재고관리: 재고(낱개), 입고 거래명세, 공급자 마스터."""

import sys
from pathlib import Path

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from PyQt6.QtCore import Qt, QDate, QTimer
from typing import Optional

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.pesticide_manager import PEST_CATEGORY_CHOICES, PesticideManager
from ui.pages.pesticide_item_link_dialog import PesticideItemLinkDialog
from ui.styles import MainStyles

# 현재고 테이블: 규격은 짧은 문자열·구분 콤보는 라벨 전체가 보이도록 폭 정책
_STOCK_COL_WIDTH_CATEGORY = 132
_STOCK_COL_WIDTH_SPEC_MAX = 100
_STOCK_TAB_HELP_TOOLTIP = (
    "등록된 농약 품목의 현재고를 낱개(병·포 등) 수량으로만 조회·관리합니다.\n\n"
    "입고 명세만 있고 품목이 없으면 목록이 비어 있습니다. "
    "「품목 추가」로 마스터를 만든 뒤 수량을 맞추세요.\n\n"
    "「사전(PSIS)」열: PSIS 동기화로 쌓인 농약 사전(m_pesticide_info)과의 연결 여부·품목명입니다. "
    "「사전 연결…」에서 품목별로 연결·해제할 수 있습니다.\n\n"
    "구분 필터·「재고 부족만」으로 목록을 좁힐 수 있습니다.\n"
    "구분: 전착제·살충제·영양제·살균제 등. 재고↓경고(낱개): 해당 수 미만이면 행이 강조됩니다."
)
_STOCK_TABLE_MIN_HEIGHT = 420
# 명세 공급가: True = 사용자 수동 입력(수량·단가 변경 시 공급가 자동 덮어쓰기 안 함)
_PEST_RCPT_SUPPLY_MANUAL_ROLE = Qt.ItemDataRole.UserRole + 40
# 재고 행 id 열: DB info_id 캐시(이미 연결된 경우 저장 시 재매칭 생략)
_STOCK_INFO_ID_ROLE = Qt.ItemDataRole.UserRole + 41
# 명세 품목: 수량 열 — 헤더「수량」+ 숫자 약 3자리 분량
_PEST_RCPT_COL_WIDTH_QTY = 68

_RCPT_ALIGN_R = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _parse_amount_text(t: str):
    """표시용 콤마·공백 제거 후 숫자 파싱. 실패 시 None."""
    s = (t or "").strip().replace(",", "").replace(" ", "").replace("\u3000", "")
    if not s:
        return None
    try:
        return float(s) if "." in s else float(int(s))
    except ValueError:
        return None


def _fmt_amount_display(val) -> str:
    """단가·금액: 천단위 콤마(0,000). 정수면 소수 생략."""
    if val is None or val == "":
        return ""
    try:
        x = float(val)
    except (TypeError, ValueError):
        return str(val)
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    s = f"{x:,.2f}"
    if s.endswith(".00"):
        return s[:-3]
    return s.rstrip("0").rstrip(".")


def _form_field_label(text: str) -> QLabel:
    """폼 그리드 좌측 필드명 — MainStyles.LBL_GRID_HEADER."""
    lb = QLabel(text)
    lb.setStyleSheet(MainStyles.LBL_GRID_HEADER)
    return lb


def _build_pest_category_combo(selected: str = "") -> QComboBox:
    cb = QComboBox()
    cb.setMinimumWidth(_STOCK_COL_WIDTH_CATEGORY - 16)
    cb.setStyleSheet(MainStyles.COMBO_TABLE_CELL)
    for val in PEST_CATEGORY_CHOICES:
        lab = "미지정" if val == "" else val
        cb.addItem(lab, val)
    sel = (selected or "").strip()
    for i in range(cb.count()):
        if cb.itemData(i) == sel:
            cb.setCurrentIndex(i)
            break
    return cb


class _PesticideInfoPickDialog(QDialog):
    """재고 품목명에 매칭되는 사전이 여러 건일 때 info_id 선택."""

    def __init__(self, parent: QWidget, candidates: list) -> None:
        super().__init__(parent)
        self.setWindowTitle("농약 사전 연결")
        self.setModal(True)
        self.setStyleSheet(MainStyles.MAIN_BG)
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "PSIS 사전은 작물·병해충(사용) 단위로 행이 나뉘어, 같은 상표명이 여러 건일 수 있습니다.\n"
                "재고 한 품목에는 그중 하나만 연결하면 됩니다. 작물·병해충을 보고 대표로 쓸 행을 고르세요."
            )
        )
        self._list = QListWidget()
        self._list.setStyleSheet(MainStyles.TABLE)
        for c in candidates:
            iid = int(c["info_id"])
            nm = str(c.get("pesticide_nm") or "").strip()
            mk = str(c.get("maker_nm") or "").strip()
            crop = str(c.get("crop_nm") or "").strip()
            pest = str(c.get("pest_psis_agg") or "").strip()
            head = nm if not mk else f"{nm}  ({mk})"
            bits = [head]
            if crop:
                bits.append(f"작물: {crop}")
            if pest:
                bits.append(f"병해충: {pest}")
            label = "  ·  ".join(bits)
            tip_lines = [f"info_id={iid}"]
            if crop:
                tip_lines.append(f"작물: {crop}")
            if pest:
                tip_lines.append(f"병해충: {pest}")
            it = QListWidgetItem(label)
            it.setToolTip("\n".join(tip_lines))
            it.setData(Qt.ItemDataRole.UserRole, iid)
            self._list.addItem(it)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        lay.addWidget(self._list, stretch=1)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(680, 400)

    def selected_info_id(self) -> Optional[int]:
        it = self._list.currentItem()
        if not it:
            return None
        v = it.data(Qt.ItemDataRole.UserRole)
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None


class _NewItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("품목 추가")
        self.setStyleSheet(MainStyles.MAIN_BG)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.ed_name = QLineEdit()
        self.ed_name.setStyleSheet(MainStyles.INPUT_CENTER)
        self.ed_spec = QLineEdit()
        self.ed_spec.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sp_piece = QSpinBox()
        self.sp_piece.setRange(0, 999999)
        self.cb_cat = _build_pest_category_combo("")
        self.cb_cat.setStyleSheet(MainStyles.COMBO)
        form.addRow(_form_field_label("품목명"), self.ed_name)
        form.addRow(_form_field_label("규격"), self.ed_spec)
        form.addRow(_form_field_label("구분"), self.cb_cat)
        form.addRow(_form_field_label("낱개(수량)"), self.sp_piece)
        lay.addLayout(form)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        return (
            self.ed_name.text().strip(),
            self.ed_spec.text().strip(),
            str(self.cb_cat.currentData() or ""),
            self.sp_piece.value(),
        )


class PesticidePage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        self.farm_cd = session.get("farm_cd", "")
        self.user_id = session.get("user_id", "")
        self.farm_nm = session.get("farm_nm", "")
        self.mgr = PesticideManager(db_manager)
        self._item_combo_options = [(None, "")]
        self._rcpt_suppress_line_change = False

        self._receipt_id = None
        self.tabs = QTabWidget()
        self._build_ui()
        self.setStyleSheet(MainStyles.MAIN_BG)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("🧪 농약 재고관리")
        title.setStyleSheet(MainStyles.LBL_TITLE)
        root.addWidget(title)

        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)
        self.tabs.addTab(self._build_stock_tab(), "현재고")
        self.tabs.addTab(self._build_receipt_tab(), "입고·거래명세")
        self.tabs.addTab(self._build_supplier_tab(), "공급자")
        self.tabs.currentChanged.connect(self._on_pesticide_tab_changed)
        root.addWidget(self.tabs, stretch=1)
        # 첫 표시 전에도 목록이 비지 않도록(메인 전환 직후 타이밍 보완)
        QTimer.singleShot(0, lambda: self._on_pesticide_tab_changed(self.tabs.currentIndex()))

    def refresh_data(self):
        self._on_pesticide_tab_changed(self.tabs.currentIndex())

    def _on_pesticide_tab_changed(self, idx: int):
        if idx == 0:
            self._reload_stock_table()
        elif idx == 1:
            self._reload_receipt_list()
            self._reload_supplier_combo()
            self._reload_item_combo_for_lines()
            if self._receipt_id:
                if self.mgr.get_receipt(self.farm_cd, self._receipt_id):
                    self._select_receipt_row_by_id(self._receipt_id)
                else:
                    self._clear_receipt_form()
            self._sync_stock_apply_ui(
                self.mgr.get_receipt(self.farm_cd, self._receipt_id)
                if self._receipt_id
                else None
            )
        else:
            self._reload_supplier_table()

    def _resolve_info_id_for_stock_item_nm(self, item_nm: str) -> Optional[int]:
        """m_pesticide_info 매칭. 1건 자동, 다건 팝업, 없음/취소 시 None."""
        raw = (item_nm or "").strip()
        if not raw:
            return None
        cands = self.mgr.find_pesticide_info_match_candidates(raw)
        if not cands:
            return None
        if len(cands) == 1:
            return int(cands[0]["info_id"])
        dlg = _PesticideInfoPickDialog(self, cands)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.selected_info_id()

    # --- 재고 ---
    def _build_stock_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(12)

        sec_row = QHBoxLayout()
        sec_row.setSpacing(6)
        sec = QLabel("현재고 현황")
        sec.setStyleSheet(MainStyles.LBL_TABLE_SUB)
        sec_row.addWidget(sec)
        stock_help = QToolButton()
        stock_help.setText("?")
        stock_help.setToolTip(_STOCK_TAB_HELP_TOOLTIP)
        stock_help.setStyleSheet(MainStyles.BTN_HELP_TOOLTIP)
        stock_help.setCursor(Qt.CursorShape.PointingHandCursor)
        stock_help.setAutoRaise(True)
        stock_help.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        sec_row.addWidget(stock_help)
        sec_row.addStretch()
        lay.addLayout(sec_row)

        self.stock_summary_lbl = QLabel("등록 품목 0건")
        self.stock_summary_lbl.setStyleSheet(
            "font-weight: bold; color: #2D5A27; background: transparent; border: none;"
        )
        lay.addWidget(self.stock_summary_lbl)

        bar = QHBoxLayout()
        self.stock_search = QLineEdit()
        self.stock_search.setPlaceholderText("품목명 검색…")
        self.stock_search.setStyleSheet(MainStyles.INPUT_CENTER)
        self.stock_search.textChanged.connect(self._refresh_stock_row_visibility)
        bar.addWidget(self.stock_search, stretch=1)

        flb = QLabel("구분")
        flb.setStyleSheet(MainStyles.LBL_GRID_HEADER)
        bar.addWidget(flb)
        self.stock_filter_cat = QComboBox()
        self.stock_filter_cat.setStyleSheet(MainStyles.COMBO)
        self.stock_filter_cat.setMinimumWidth(120)
        self.stock_filter_cat.addItem("전체", None)
        for val in PEST_CATEGORY_CHOICES:
            lab = "미지정" if val == "" else val
            self.stock_filter_cat.addItem(lab, val)
        self.stock_filter_cat.currentIndexChanged.connect(
            lambda *_: self._refresh_stock_row_visibility()
        )
        bar.addWidget(self.stock_filter_cat)

        self.stock_chk_low_only = QCheckBox("재고 부족만")
        self.stock_chk_low_only.setStyleSheet(MainStyles.LBL_GRID_HEADER)
        self.stock_chk_low_only.stateChanged.connect(
            lambda *_: self._refresh_stock_row_visibility()
        )
        bar.addWidget(self.stock_chk_low_only)

        btn_rf = QPushButton("목록 새로고침")
        btn_rf.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_rf.clicked.connect(self._reload_stock_table)
        bar.addWidget(btn_rf)

        btn_psis = QPushButton("사전 연결…")
        btn_psis.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_psis.setToolTip(
            "먼저 품목명·제조사 기준 자동 연결을 시도한 뒤, "
            "남은 미연결만 연결 창에서 수동 지정합니다."
        )
        btn_psis.clicked.connect(self._on_open_pesticide_info_link_dialog)
        bar.addWidget(btn_psis)

        btn_add = QPushButton("품목 추가")
        btn_add.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_add.clicked.connect(self._on_add_stock_item)
        btn_save = QPushButton("저장")
        btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_save.clicked.connect(self._on_save_stock_table)
        btn_del = QPushButton("선택 삭제")
        btn_del.setStyleSheet(MainStyles.BTN_DANGER)
        btn_del.clicked.connect(self._on_delete_stock_row)
        bar.addWidget(btn_add)
        bar.addWidget(btn_save)
        bar.addWidget(btn_del)
        lay.addLayout(bar)

        stock_card = QFrame()
        stock_card.setStyleSheet(MainStyles.CARD)
        stock_card_lay = QVBoxLayout(stock_card)
        stock_card_lay.setContentsMargins(12, 12, 12, 12)
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(7)
        self.stock_table.setHorizontalHeaderLabels(
            ["id", "품목", "규격", "구분", "사전(PSIS)", "낱개 수량", "재고↓경고(낱개)"]
        )
        self.stock_table.setColumnHidden(0, True)
        self.stock_table.setStyleSheet(MainStyles.TABLE)
        self.stock_table.setShowGrid(False)
        self.stock_table.setFrameShape(QFrame.Shape.NoFrame)
        hh = self.stock_table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # 규격: 내용 길이만큼만 (남는 폭을 품목·구분에 넘김)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        # 구분: 콤보는 헤더가 내용 폭을 과소 계산하는 경우가 있어 고정 폭 확보
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.stock_table.setColumnWidth(3, _STOCK_COL_WIDTH_CATEGORY)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for c in (5, 6):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.setMinimumHeight(_STOCK_TABLE_MIN_HEIGHT)
        self.stock_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        stock_card_lay.addWidget(self.stock_table, stretch=1)
        lay.addWidget(stock_card, stretch=1)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return w

    def _reload_stock_table(self):
        self.stock_table.setRowCount(0)
        items = self.mgr.list_items(self.farm_cd)
        for row in items:
            self._append_stock_row(row)
        self._update_stock_summary()
        self.stock_table.resizeColumnToContents(2)
        w2 = self.stock_table.columnWidth(2)
        if w2 > _STOCK_COL_WIDTH_SPEC_MAX:
            self.stock_table.setColumnWidth(2, _STOCK_COL_WIDTH_SPEC_MAX)
        self._refresh_stock_row_visibility()

    @staticmethod
    def _parse_row_info_id(row: dict):
        raw = row.get("info_id")
        if raw is None:
            return None
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            return None
        return pk if pk > 0 else None

    def _stock_psis_display_from_row(self, row: dict) -> tuple[str, str]:
        """사전(PSIS) 열 (표시문자, 툴팁)."""
        pid = self._parse_row_info_id(row)
        if not pid:
            return (
                "미연결",
                "농약 사전(PSIS 동기화 데이터)에 연결되지 않았습니다. 「사전 연결…」에서 지정하세요.",
            )
        inf_nm = str(row.get("info_pesticide_nm") or "").strip()
        if not inf_nm:
            inf_nm = self.mgr.get_pesticide_info_pesticide_nm(pid)
        disp = inf_nm if inf_nm else f"연결 #{pid}"
        tip = f"사전 품목명: {inf_nm}" if inf_nm else f"info_id={pid}"
        return (disp, tip)

    def _on_open_pesticide_info_link_dialog(self) -> None:
        uid = str(self.user_id or "").strip() or "system"
        n_auto = self.mgr.try_auto_link_unlinked_items_to_info(self.farm_cd, uid)
        self._reload_stock_table()
        remaining = self.mgr.get_unlinked_pesticide_items(self.farm_cd)
        if not remaining:
            msg = (
                f"자동 연결 {n_auto}건을 반영했습니다.\n남은 미연결 품목이 없습니다."
                if n_auto > 0
                else "미연결 품목이 없습니다."
            )
            QMessageBox.information(self, "사전 연결", msg)
            return
        if n_auto > 0:
            QMessageBox.information(
                self,
                "사전 연결",
                f"자동 연결 {n_auto}건 반영. "
                f"남은 품목 {len(remaining)}건은 연결 창에서 선택하세요.",
            )
        dlg = PesticideItemLinkDialog(self.db, self.session, self)
        dlg.exec()
        self._reload_stock_table()

    def _append_stock_row(self, row: dict):
        r = self.stock_table.rowCount()
        self.stock_table.insertRow(r)
        id_it = QTableWidgetItem(str(row["item_id"]))
        id_it.setData(Qt.ItemDataRole.UserRole, int(row["item_id"]))
        id_it.setFlags(id_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
        raw_info = row.get("info_id")
        if raw_info is not None:
            try:
                ri = int(raw_info)
                if ri > 0:
                    id_it.setData(_STOCK_INFO_ID_ROLE, ri)
            except (TypeError, ValueError):
                pass
        self.stock_table.setItem(r, 0, id_it)

        nm = QTableWidgetItem(row.get("item_nm") or "")
        self.stock_table.setItem(r, 1, nm)
        sp = QTableWidgetItem(row.get("spec_nm") or "")
        self.stock_table.setItem(r, 2, sp)

        cat_cb = _build_pest_category_combo(str(row.get("pest_category_nm") or ""))

        def _on_cat(rr):
            return lambda *_: (
                self._apply_stock_row_style(rr),
                self._refresh_stock_row_visibility(),
            )

        cat_cb.currentIndexChanged.connect(_on_cat(r))
        self.stock_table.setCellWidget(r, 3, cat_cb)

        psis_txt, psis_tip = self._stock_psis_display_from_row(row)
        link_it = QTableWidgetItem(psis_txt)
        link_it.setFlags(link_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
        link_it.setToolTip(psis_tip)
        self.stock_table.setItem(r, 4, link_it)

        def _on_qty_spin(rr):
            return lambda *_: (
                self._apply_stock_row_style(rr),
                self._refresh_stock_row_visibility(),
            )

        for col, key, mx in (
            (5, "qty_piece", 999999),
            (6, "warn_piece_below", 999999),
        ):
            sb = QSpinBox()
            sb.setStyleSheet(MainStyles.SPINBOX_TABLE_CELL)
            sb.setRange(0, mx)
            v = row.get(key)
            sb.setValue(int(v or 0))
            sb.valueChanged.connect(_on_qty_spin(r))
            self.stock_table.setCellWidget(r, col, sb)

        self._apply_stock_row_style(r)

    def _stock_spin_stylesheet(self, low: bool) -> str:
        bg = "#FFF9C4" if low else "transparent"
        return MainStyles.SPINBOX_TABLE_CELL + f"\nQSpinBox {{ background-color: {bg}; }}\n"

    def _stock_combo_stylesheet(self, low: bool) -> str:
        bg = "#FFF9C4" if low else "transparent"
        return MainStyles.COMBO_TABLE_CELL + f"\nQComboBox {{ background-color: {bg}; }}\n"

    def _apply_stock_row_style(self, r: int):
        id_it = self.stock_table.item(r, 0)
        if not id_it:
            return
        sb_p = self.stock_table.cellWidget(r, 5)
        wp = self.stock_table.cellWidget(r, 6)
        cat_cb = self.stock_table.cellWidget(r, 3)
        if not isinstance(sb_p, QSpinBox) or not isinstance(wp, QSpinBox):
            return
        warn_p = wp.value()
        low = warn_p > 0 and sb_p.value() < warn_p
        for c in (1, 2, 4):
            it = self.stock_table.item(r, c)
            if it:
                if low:
                    it.setBackground(Qt.GlobalColor.yellow)
                else:
                    it.setBackground(Qt.GlobalColor.transparent)
        sb_p.setStyleSheet(self._stock_spin_stylesheet(low))
        wp.setStyleSheet(self._stock_spin_stylesheet(low))
        if isinstance(cat_cb, QComboBox):
            cat_cb.setStyleSheet(self._stock_combo_stylesheet(low))

    def _update_stock_summary(self):
        n = self.stock_table.rowCount()
        total = 0
        for r in range(n):
            sb = self.stock_table.cellWidget(r, 5)
            if isinstance(sb, QSpinBox):
                total += sb.value()
        self.stock_summary_lbl.setText(
            f"등록 품목 {n}건 · 낱개 합계 {total:,}개 "
            f"(수량·경고는 모두 낱개 기준입니다)"
        )

    def _refresh_stock_row_visibility(self):
        q = (self.stock_search.text() or "").strip().lower()
        cat_data = self.stock_filter_cat.currentData()
        low_only = self.stock_chk_low_only.isChecked()
        for r in range(self.stock_table.rowCount()):
            it = self.stock_table.item(r, 1)
            nm = (it.text() if it else "").lower()
            hide_search = bool(q) and q not in nm

            cat_cb = self.stock_table.cellWidget(r, 3)
            cat_val = ""
            if isinstance(cat_cb, QComboBox):
                cat_val = str(cat_cb.currentData() or "")
            hide_cat = cat_data is not None and cat_val != str(cat_data)

            sb_p = self.stock_table.cellWidget(r, 5)
            wp = self.stock_table.cellWidget(r, 6)
            hide_low = False
            if low_only:
                if isinstance(sb_p, QSpinBox) and isinstance(wp, QSpinBox):
                    wv = wp.value()
                    hide_low = not (wv > 0 and sb_p.value() < wv)
                else:
                    hide_low = True

            self.stock_table.setRowHidden(r, hide_search or hide_cat or hide_low)

    def _on_add_stock_item(self):
        dlg = _NewItemDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, spec, cat, qp = dlg.values()
        if not name:
            QMessageBox.warning(self, "입력", "품목명을 입력하세요.")
            return
        link_id = self._resolve_info_id_for_stock_item_nm(name)
        new_id = self.mgr.insert_item(
            self.farm_cd, self.user_id, name, spec, cat, 0, qp, "", link_id
        )
        if not new_id:
            QMessageBox.warning(self, "저장 실패", "품목을 추가하지 못했습니다.")
            return
        self._append_stock_row(
            {
                "item_id": new_id,
                "item_nm": name,
                "spec_nm": spec,
                "pest_category_nm": cat,
                "qty_piece": qp,
                "warn_piece_below": 0,
                "info_id": link_id,
            }
        )
        self._update_stock_summary()
        self._refresh_stock_row_visibility()

    def _on_save_stock_table(self):
        bad_rows = []
        for r in range(self.stock_table.rowCount()):
            nm_it = self.stock_table.item(r, 1)
            name = nm_it.text().strip() if nm_it else ""
            if not name:
                bad_rows.append(r + 1)
        if bad_rows:
            QMessageBox.warning(
                self,
                "입력",
                "품목명이 비어 있는 행이 있습니다. 이름을 입력하거나 해당 행을 삭제하세요.\n"
                f"행 번호: {', '.join(str(x) for x in bad_rows[:20])}"
                + (" …" if len(bad_rows) > 20 else ""),
            )
            return
        for r in range(self.stock_table.rowCount()):
            id_it = self.stock_table.item(r, 0)
            if not id_it:
                continue
            iid = int(id_it.data(Qt.ItemDataRole.UserRole))
            nm_it = self.stock_table.item(r, 1)
            sp_it = self.stock_table.item(r, 2)
            cat_cb = self.stock_table.cellWidget(r, 3)
            sb_p = self.stock_table.cellWidget(r, 5)
            wp = self.stock_table.cellWidget(r, 6)
            if not nm_it or not isinstance(sb_p, QSpinBox):
                continue
            name = nm_it.text().strip()
            cat = ""
            if isinstance(cat_cb, QComboBox):
                cat = str(cat_cb.currentData() or "")
            wpv = wp.value() if isinstance(wp, QSpinBox) else 0
            warn_p = wpv if wpv > 0 else None
            cached_info = id_it.data(_STOCK_INFO_ID_ROLE)
            link_id = None
            if cached_info is not None:
                try:
                    ci = int(cached_info)
                    if ci > 0:
                        link_id = ci
                except (TypeError, ValueError):
                    pass
            if link_id is None:
                link_id = self._resolve_info_id_for_stock_item_nm(name)
            self.mgr.update_item_full(
                self.farm_cd,
                self.user_id,
                iid,
                name,
                sp_it.text().strip() if sp_it else "",
                cat,
                0,
                sb_p.value(),
                None,
                warn_p,
                "",
                link_id,
            )
            if link_id is not None and link_id > 0:
                id_it.setData(_STOCK_INFO_ID_ROLE, int(link_id))
            else:
                id_it.setData(_STOCK_INFO_ID_ROLE, None)
            psis_txt, psis_tip = self._stock_psis_display_from_row(
                {
                    "info_id": link_id,
                    "info_pesticide_nm": self.mgr.get_pesticide_info_pesticide_nm(
                        link_id
                    ),
                }
            )
            psis_it = self.stock_table.item(r, 4)
            if psis_it is None:
                psis_it = QTableWidgetItem()
                psis_it.setFlags(psis_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.stock_table.setItem(r, 4, psis_it)
            psis_it.setText(psis_txt)
            psis_it.setToolTip(psis_tip)
        for r in range(self.stock_table.rowCount()):
            self._apply_stock_row_style(r)
        self._update_stock_summary()
        self._refresh_stock_row_visibility()
        QMessageBox.information(self, "저장", "재고 정보를 저장했습니다.")

    def _on_delete_stock_row(self):
        rows = self.stock_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "안내", "삭제할 행을 선택하세요.")
            return
        r = rows[0].row()
        id_it = self.stock_table.item(r, 0)
        if not id_it:
            return
        iid = int(id_it.data(Qt.ItemDataRole.UserRole))
        nm_it = self.stock_table.item(r, 1)
        nm = nm_it.text().strip() if nm_it else ""
        disp = nm if nm else f"ID {iid}"
        if (
            QMessageBox.question(
                self,
                "삭제",
                f"[{disp}] 품목을 목록에서 숨깁니다. 계속할까요?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.mgr.soft_delete_item(self.farm_cd, self.user_id, iid):
            self.stock_table.removeRow(r)

    # --- 입고 ---
    def _build_receipt_tab(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 12, 16, 16)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setStyleSheet(
            "QSplitter::handle { background-color: #EAE7E2; width: 4px; margin: 2px 0; }"
        )
        list_wrap = QFrame()
        list_wrap.setStyleSheet(MainStyles.CARD)
        # 좌측 목록이 과도하게 좁아지지 않도록(가독성)
        list_wrap.setMinimumWidth(360)
        list_lay = QVBoxLayout(list_wrap)
        list_lay.setContentsMargins(12, 12, 12, 12)
        list_lay.setSpacing(8)
        list_title = QLabel("거래명세 목록")
        list_title.setStyleSheet(MainStyles.LBL_TABLE_SUB)
        list_lay.addWidget(list_title)
        self.rcpt_list = QTableWidget()
        self.rcpt_list.setColumnCount(4)
        self.rcpt_list.setHorizontalHeaderLabels(["번호", "일자", "공급자", "반영"])
        self.rcpt_list.setStyleSheet(MainStyles.TABLE)
        self.rcpt_list.setShowGrid(False)
        self.rcpt_list.setFrameShape(QFrame.Shape.NoFrame)
        rlist_hh = self.rcpt_list.horizontalHeader()
        rlist_hh.setMinimumSectionSize(56)
        rlist_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        rlist_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        rlist_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        rlist_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.rcpt_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rcpt_list.setAlternatingRowColors(True)
        self.rcpt_list.itemSelectionChanged.connect(self._on_receipt_selected)
        list_lay.addWidget(self.rcpt_list)
        split.addWidget(list_wrap)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setSpacing(12)
        head = QGroupBox("명세 헤더")
        head.setStyleSheet(MainStyles.GROUP_BOX)
        fl = QGridLayout(head)
        fl.setContentsMargins(16, 20, 16, 12)
        fl.setHorizontalSpacing(12)
        fl.setVerticalSpacing(10)
        self.rcpt_date = QDateEdit()
        self.rcpt_date.setCalendarPopup(True)
        self.rcpt_date.setDate(QDate.currentDate())
        self.rcpt_date.setDisplayFormat("yyyy-MM-dd")
        self.rcpt_supplier_combo = QComboBox()
        self.rcpt_supplier_combo.setStyleSheet(MainStyles.COMBO)
        self.rcpt_supplier_combo.currentIndexChanged.connect(self._on_supplier_combo_changed)
        self.rcpt_supplier_nm = QLineEdit()
        self.rcpt_supplier_nm.setPlaceholderText("명세에 표시할 공급자명")
        self.rcpt_supplier_nm.setStyleSheet(MainStyles.INPUT_CENTER)
        self.rcpt_recipient = QLineEdit()
        self.rcpt_recipient.setStyleSheet(MainStyles.INPUT_CENTER)
        self.rcpt_recipient.setText(self.farm_nm or "")
        self.rcpt_rmk = QLineEdit()
        self.rcpt_rmk.setStyleSheet(MainStyles.INPUT_CENTER)
        # 명세 헤더 2줄: 1) 거래일·등록 공급자·공급자명 / 2) 인수처·비고
        rcpt_head_row0 = QWidget()
        rcpt_head_row0_lay = QHBoxLayout(rcpt_head_row0)
        rcpt_head_row0_lay.setContentsMargins(0, 0, 0, 0)
        rcpt_head_row0_lay.setSpacing(10)
        rcpt_head_row0_lay.addWidget(_form_field_label("거래일"))
        rcpt_head_row0_lay.addWidget(self.rcpt_date)
        rcpt_head_row0_lay.addWidget(_form_field_label("등록 공급자"))
        rcpt_head_row0_lay.addWidget(self.rcpt_supplier_combo, stretch=1)
        rcpt_head_row0_lay.addWidget(_form_field_label("공급자명"))
        rcpt_head_row0_lay.addWidget(self.rcpt_supplier_nm, stretch=2)
        fl.addWidget(rcpt_head_row0, 0, 0)

        rcpt_head_row1 = QWidget()
        rcpt_head_row1_lay = QHBoxLayout(rcpt_head_row1)
        rcpt_head_row1_lay.setContentsMargins(0, 0, 0, 0)
        rcpt_head_row1_lay.setSpacing(10)
        rcpt_head_row1_lay.addWidget(_form_field_label("인수처"))
        rcpt_head_row1_lay.addWidget(self.rcpt_recipient, stretch=1)
        rcpt_head_row1_lay.addWidget(_form_field_label("비고"))
        rcpt_head_row1_lay.addWidget(self.rcpt_rmk, stretch=2)
        fl.addWidget(rcpt_head_row1, 1, 0)
        rv.addWidget(head)

        lines_sec = QLabel("명세 품목")
        lines_sec.setStyleSheet(MainStyles.LBL_TABLE_SUB)
        b_new = QPushButton("새 명세")
        b_new.setStyleSheet(MainStyles.BTN_SECONDARY)
        b_new.clicked.connect(self._on_new_receipt)
        b_row = QPushButton("행 추가")
        b_row.setStyleSheet(MainStyles.BTN_SECONDARY)
        b_row.clicked.connect(self._on_add_receipt_line)
        b_row_del = QPushButton("선택 행 삭제")
        b_row_del.setStyleSheet(MainStyles.BTN_SECONDARY)
        b_row_del.clicked.connect(self._on_delete_receipt_line)
        b_save = QPushButton("명세 저장")
        b_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        b_save.clicked.connect(self._on_save_receipt)
        self.rcpt_btn_apply = QPushButton("재고 반영")
        self.rcpt_btn_apply.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.rcpt_btn_apply.clicked.connect(self._on_apply_receipt_stock)
        b_del = QPushButton("명세 삭제")
        b_del.setStyleSheet(MainStyles.BTN_DANGER)
        b_del.clicked.connect(self._on_delete_receipt)
        lines_top = QHBoxLayout()
        lines_top.setSpacing(8)
        lines_top.addWidget(lines_sec, 0, Qt.AlignmentFlag.AlignVCenter)
        lines_top.addStretch(1)
        lines_top.addWidget(b_new)
        lines_top.addWidget(b_row)
        lines_top.addWidget(b_row_del)
        lines_top.addSpacing(16)
        lines_top.addWidget(b_save)
        lines_top.addWidget(self.rcpt_btn_apply)
        lines_top.addWidget(b_del)
        rv.addLayout(lines_top)

        lines_card = QFrame()
        lines_card.setStyleSheet(MainStyles.CARD)
        lines_card_lay = QVBoxLayout(lines_card)
        lines_card_lay.setContentsMargins(12, 12, 12, 12)
        self.rcpt_lines = QTableWidget()
        self.rcpt_lines.setColumnCount(8)
        self.rcpt_lines.setHorizontalHeaderLabels(
            ["품목", "규격", "수량", "단가", "공급가", "세액", "비고", "재고연결"]
        )
        self.rcpt_lines.setStyleSheet(MainStyles.TABLE)
        self.rcpt_lines.setShowGrid(False)
        self.rcpt_lines.setFrameShape(QFrame.Shape.NoFrame)
        hl = self.rcpt_lines.horizontalHeader()
        for c in range(1, 7):
            if c == 2:
                continue
            hl.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hl.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.rcpt_lines.setColumnWidth(2, _PEST_RCPT_COL_WIDTH_QTY)
        hl.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hl.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.rcpt_lines.setMinimumHeight(220)
        self.rcpt_lines.setAlternatingRowColors(True)
        self.rcpt_lines.itemChanged.connect(self._on_receipt_line_item_changed)
        lines_card_lay.addWidget(self.rcpt_lines)
        rv.addWidget(lines_card)

        self.rcpt_lbl_stock_done = QLabel("")
        self.rcpt_lbl_stock_done.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
        self.rcpt_lbl_stock_done.setWordWrap(True)
        self.rcpt_lbl_stock_done.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        rv.addWidget(self.rcpt_lbl_stock_done)

        split.addWidget(right)
        # 기존 1:2(좌≈33%) 대비 좌측 약 50% 넓힘 → 1:1(각 50%)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        outer.addWidget(split)
        return w

    def _reload_supplier_combo(self):
        self.rcpt_supplier_combo.blockSignals(True)
        self.rcpt_supplier_combo.clear()
        self.rcpt_supplier_combo.addItem("(선택 안 함)", None)
        for s in self.mgr.list_suppliers(self.farm_cd):
            self.rcpt_supplier_combo.addItem(
                s.get("supplier_nm") or "",
                int(s["supplier_id"]),
            )
        self.rcpt_supplier_combo.blockSignals(False)

    def _reload_item_combo_for_lines(self):
        self._item_combo_options = [(None, "")]
        for it in self.mgr.list_items(self.farm_cd):
            nm = (it.get("item_nm") or "").strip()
            sp = (it.get("spec_nm") or "").strip()
            if sp:
                label = f"{nm}  ·  {sp}"
            else:
                label = nm or "(이름 없음)"
            self._item_combo_options.append((int(it["item_id"]), label))

    def _make_line_item_combo(self, selected_id):
        cb = QComboBox()
        cb.setStyleSheet(MainStyles.COMBO_TABLE_CELL)
        cb.setMinimumWidth(200)
        for i, (iid, label) in enumerate(self._item_combo_options):
            disp = label if label else "(연결 안 함)"
            cb.addItem(disp, iid)
            cb.setItemData(i, disp, Qt.ItemDataRole.ToolTipRole)
            if iid == selected_id:
                cb.setCurrentIndex(i)
        return cb

    def _reload_receipt_list(self):
        self.rcpt_list.setRowCount(0)
        for rec in self.mgr.list_receipts(self.farm_cd):
            r = self.rcpt_list.rowCount()
            self.rcpt_list.insertRow(r)
            rid = rec["receipt_id"]
            dt = rec.get("receipt_dt") or ""
            sn = rec.get("supplier_nm_text") or rec.get("supplier_nm_joined") or ""
            self.rcpt_list.setItem(r, 0, QTableWidgetItem(str(rid)))
            self.rcpt_list.setItem(r, 1, QTableWidgetItem(str(dt)))
            self.rcpt_list.setItem(r, 2, QTableWidgetItem(sn))
            yn = str(rec.get("stock_applied_yn") or "N").strip().upper()
            self.rcpt_list.setItem(r, 3, QTableWidgetItem("완료" if yn == "Y" else "-"))
            self.rcpt_list.item(r, 0).setData(Qt.ItemDataRole.UserRole, int(rid))

    def _sync_stock_apply_ui(self, rec=None):
        """재고 반영 완료 시 버튼 비활성화(동일 명세 중복 반영 방지)."""
        if not self._receipt_id:
            self.rcpt_btn_apply.setEnabled(True)
            self.rcpt_lbl_stock_done.setText("")
            return
        if rec is None:
            rec = self.mgr.get_receipt(self.farm_cd, self._receipt_id) or {}
        yn = str(rec.get("stock_applied_yn") or "N").strip().upper()
        if yn == "Y":
            self.rcpt_btn_apply.setEnabled(False)
            dt = str(rec.get("stock_applied_dt") or "")
            self.rcpt_lbl_stock_done.setText(
                "재고 반영 완료 — 아래 「재고 반영」 버튼은 비활성화되었습니다. "
                "명세는 수정·저장할 수 있으나 동일 명세로 재고를 다시 늘리지는 않습니다."
                + (f"\n반영일시: {dt}" if dt else "")
            )
        else:
            self.rcpt_btn_apply.setEnabled(True)
            self.rcpt_lbl_stock_done.setText(
                "미반영 — 저장 후 「재고 반영」으로 낱개 현재고에 입고 수량을 더할 수 있습니다."
            )

    def _clear_receipt_form(self):
        self._receipt_id = None
        self.rcpt_date.setDate(QDate.currentDate())
        self.rcpt_supplier_combo.setCurrentIndex(0)
        self.rcpt_supplier_nm.clear()
        self.rcpt_recipient.setText(self.farm_nm or "")
        self.rcpt_rmk.clear()
        self.rcpt_lines.setRowCount(0)
        self._sync_stock_apply_ui({})

    def _select_receipt_row_by_id(self, receipt_id: int) -> None:
        self.rcpt_list.blockSignals(True)
        try:
            for r in range(self.rcpt_list.rowCount()):
                it = self.rcpt_list.item(r, 0)
                if it and int(it.data(Qt.ItemDataRole.UserRole)) == int(receipt_id):
                    self.rcpt_list.selectRow(r)
                    if self.rcpt_list.item(r, 0):
                        self.rcpt_list.scrollToItem(self.rcpt_list.item(r, 0))
                    break
        finally:
            self.rcpt_list.blockSignals(False)

    def _on_new_receipt(self):
        self.rcpt_list.clearSelection()
        self._clear_receipt_form()

    def _on_receipt_selected(self):
        sel = self.rcpt_list.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        it = self.rcpt_list.item(row, 0)
        if not it:
            return
        rid = int(it.data(Qt.ItemDataRole.UserRole))
        self._load_receipt_into_form(rid)

    def _load_receipt_into_form(self, receipt_id: int):
        rec = self.mgr.get_receipt(self.farm_cd, receipt_id)
        if not rec:
            return
        self._receipt_id = receipt_id
        ymd = str(rec.get("receipt_dt") or "")
        if len(ymd) >= 10:
            self.rcpt_date.setDate(QDate.fromString(ymd[:10], Qt.DateFormat.ISODate))
        sid = rec.get("supplier_id")
        self.rcpt_supplier_combo.blockSignals(True)
        if sid:
            for i in range(self.rcpt_supplier_combo.count()):
                if self.rcpt_supplier_combo.itemData(i) == sid:
                    self.rcpt_supplier_combo.setCurrentIndex(i)
                    break
        else:
            self.rcpt_supplier_combo.setCurrentIndex(0)
        self.rcpt_supplier_combo.blockSignals(False)
        self.rcpt_supplier_nm.setText(str(rec.get("supplier_nm_text") or ""))
        self.rcpt_recipient.setText(str(rec.get("recipient_nm") or self.farm_nm or ""))
        self.rcpt_rmk.setText(str(rec.get("rmk") or ""))

        self._rcpt_suppress_line_change = True
        self.rcpt_lines.blockSignals(True)
        try:
            self.rcpt_lines.setRowCount(0)
            self._reload_item_combo_for_lines()
            for ln in self.mgr.list_receipt_lines(receipt_id):
                self._append_receipt_line_row(ln)
        finally:
            self.rcpt_lines.blockSignals(False)
            self._rcpt_suppress_line_change = False
        self._sync_stock_apply_ui(rec)

    def _row_index_for_qty_spinbox(self, sb: QSpinBox) -> int:
        for rr in range(self.rcpt_lines.rowCount()):
            if self.rcpt_lines.cellWidget(rr, 2) is sb:
                return rr
        return -1

    def _on_receipt_qty_spin_changed(self):
        sb = self.sender()
        if isinstance(sb, QSpinBox):
            r = self._row_index_for_qty_spinbox(sb)
            if r >= 0:
                self._maybe_autofill_supply_row(r)

    def _on_receipt_line_item_changed(self, item: QTableWidgetItem):
        if self._rcpt_suppress_line_change:
            return
        c = item.column()
        r = item.row()
        if c == 4:
            if not item.text().strip():
                item.setData(_PEST_RCPT_SUPPLY_MANUAL_ROLE, False)
                return
            item.setData(_PEST_RCPT_SUPPLY_MANUAL_ROLE, True)
            self._reformat_rcpt_money_cell(item)
            return
        if c == 1:
            item.setTextAlignment(_RCPT_ALIGN_R)
            return
        if c == 3:
            self._reformat_rcpt_money_cell(item)
            self._maybe_autofill_supply_row(r)
        elif c == 5:
            self._reformat_rcpt_money_cell(item)

    def _reformat_rcpt_money_cell(self, item: QTableWidgetItem):
        raw = item.text().strip()
        if not raw:
            return
        p = _parse_amount_text(raw)
        if p is None:
            return
        fmt = _fmt_amount_display(p)
        if fmt != item.text():
            self._rcpt_suppress_line_change = True
            try:
                item.setText(fmt)
            finally:
                self._rcpt_suppress_line_change = False

    def _maybe_autofill_supply_row(self, r: int):
        if self._rcpt_suppress_line_change:
            return
        it_sup = self.rcpt_lines.item(r, 4)
        if it_sup and it_sup.data(_PEST_RCPT_SUPPLY_MANUAL_ROLE):
            return
        sb = self.rcpt_lines.cellWidget(r, 2)
        qty = sb.value() if isinstance(sb, QSpinBox) else 0
        it_up = self.rcpt_lines.item(r, 3)
        t = (it_up.text().strip().replace(",", "") if it_up else "")
        if not t:
            return
        try:
            unit = float(t)
        except ValueError:
            return
        amt = int(round(qty * unit))
        amt_txt = _fmt_amount_display(amt)
        self._rcpt_suppress_line_change = True
        try:
            if it_sup is None:
                it_sup = QTableWidgetItem(amt_txt)
                it_sup.setTextAlignment(_RCPT_ALIGN_R)
                it_sup.setData(_PEST_RCPT_SUPPLY_MANUAL_ROLE, False)
                self.rcpt_lines.setItem(r, 4, it_sup)
            else:
                it_sup.setText(amt_txt)
        finally:
            self._rcpt_suppress_line_change = False

    def _append_receipt_line_row(self, ln: dict = None):
        ln = ln or {}
        r = self.rcpt_lines.rowCount()
        self.rcpt_lines.insertRow(r)
        self.rcpt_lines.setItem(r, 0, QTableWidgetItem(str(ln.get("item_nm", ""))))
        sp_it = QTableWidgetItem(str(ln.get("spec_nm", "")))
        sp_it.setTextAlignment(_RCPT_ALIGN_R)
        self.rcpt_lines.setItem(r, 1, sp_it)
        sb_q = QSpinBox()
        sb_q.setRange(0, 999999)
        sb_q.setStyleSheet(MainStyles.SPINBOX_TABLE_CELL)
        sb_q.setMaximumWidth(_PEST_RCPT_COL_WIDTH_QTY - 6)
        sb_q.setAlignment(_RCPT_ALIGN_R)
        sb_q.setValue(max(0, int(ln.get("qty") or 0)))
        sb_q.valueChanged.connect(self._on_receipt_qty_spin_changed)
        self.rcpt_lines.setCellWidget(r, 2, sb_q)
        up = ln.get("unit_price")
        up_it = QTableWidgetItem(_fmt_amount_display(up) if up is not None else "")
        up_it.setTextAlignment(_RCPT_ALIGN_R)
        self.rcpt_lines.setItem(r, 3, up_it)
        sa = ln.get("supply_amt")
        sa_it = QTableWidgetItem(_fmt_amount_display(sa) if sa is not None else "")
        sa_it.setTextAlignment(_RCPT_ALIGN_R)
        # DB에 공급가가 있으면 수동과 동일 취급(수량·단가만 바꿔 공급가 덮어쓰기 안 함)
        sa_it.setData(
            _PEST_RCPT_SUPPLY_MANUAL_ROLE,
            bool(sa_it.text().strip()),
        )
        self.rcpt_lines.setItem(r, 4, sa_it)
        ta = ln.get("tax_amt")
        ta_it = QTableWidgetItem(_fmt_amount_display(ta) if ta is not None else "")
        ta_it.setTextAlignment(_RCPT_ALIGN_R)
        self.rcpt_lines.setItem(r, 5, ta_it)
        self.rcpt_lines.setItem(r, 6, QTableWidgetItem(str(ln.get("line_rmk", ""))))
        link_id = ln.get("link_item_id")
        self.rcpt_lines.setCellWidget(
            r, 7, self._make_line_item_combo(int(link_id) if link_id else None)
        )

    def _on_delete_receipt_line(self):
        r = self.rcpt_lines.currentRow()
        if r < 0:
            QMessageBox.information(self, "안내", "삭제할 행을 표에서 선택하세요.")
            return
        self.rcpt_lines.removeRow(r)

    def _on_add_receipt_line(self):
        self._reload_item_combo_for_lines()
        self._append_receipt_line_row({})

    def _on_supplier_combo_changed(self):
        i = self.rcpt_supplier_combo.currentIndex()
        sid = self.rcpt_supplier_combo.itemData(i)
        if sid is None:
            return
        name = self.rcpt_supplier_combo.currentText()
        if not self.rcpt_supplier_nm.text().strip():
            self.rcpt_supplier_nm.setText(name)

    def _collect_receipt_lines(self):
        lines = []
        for r in range(self.rcpt_lines.rowCount()):
            def cell_text(c):
                it = self.rcpt_lines.item(r, c)
                return it.text().strip() if it else ""

            sbq = self.rcpt_lines.cellWidget(r, 2)
            qty = sbq.value() if isinstance(sbq, QSpinBox) else 0

            def num_or_none(c):
                return _parse_amount_text(cell_text(c))

            cb = self.rcpt_lines.cellWidget(r, 7)
            link_id = cb.currentData() if isinstance(cb, QComboBox) else None

            lines.append(
                {
                    "item_nm": cell_text(0),
                    "spec_nm": cell_text(1),
                    "qty": qty,
                    "unit_price": num_or_none(3),
                    "supply_amt": num_or_none(4),
                    "tax_amt": num_or_none(5),
                    "line_rmk": cell_text(6),
                    # DB checked_yn 유지·화면 미노출(재고 반영 등 로직 미사용)
                    "checked_yn": False,
                    "link_item_id": link_id,
                }
            )
        return lines

    def _on_save_receipt(self):
        self._reload_item_combo_for_lines()
        raw_lines = self._collect_receipt_lines()
        lines = [ln for ln in raw_lines if (ln.get("item_nm") or "").strip()]
        for ln in lines:
            if int(ln.get("qty") or 0) < 0:
                QMessageBox.warning(self, "입력", "수량은 0 이상만 저장할 수 있습니다.")
                return
        i = self.rcpt_supplier_combo.currentIndex()
        sid = self.rcpt_supplier_combo.itemData(i)
        supplier_id = int(sid) if sid is not None else None
        dt = self.rcpt_date.date().toString(Qt.DateFormat.ISODate)
        if not dt.strip():
            QMessageBox.warning(self, "입력", "거래일을 지정하세요.")
            return
        try:
            rid = self.mgr.save_receipt_full(
                self.farm_cd,
                self.user_id,
                self._receipt_id,
                dt,
                supplier_id,
                self.rcpt_supplier_nm.text(),
                self.rcpt_recipient.text(),
                self.rcpt_rmk.text(),
                lines,
            )
        except Exception as ex:
            QMessageBox.critical(self, "저장 실패", f"거래명세를 저장하지 못했습니다.\n{ex}")
            return
        if not rid:
            QMessageBox.warning(self, "저장 실패", "저장 결과가 없습니다.")
            return
        self._receipt_id = rid
        self._reload_receipt_list()
        self._select_receipt_row_by_id(rid)
        self._sync_stock_apply_ui(self.mgr.get_receipt(self.farm_cd, rid))
        QMessageBox.information(self, "저장", "거래명세를 저장했습니다.")

    def _on_apply_receipt_stock(self):
        if not self._receipt_id:
            QMessageBox.information(self, "안내", "먼저 명세를 저장하세요.")
            return
        n, skipped, notes = self.mgr.apply_receipt_to_stock(
            self.farm_cd, self.user_id, self._receipt_id
        )
        msg = f"재고에 반영된 품목(라인): {n}건"
        if notes:
            msg += "\n\n" + "\n".join(notes)
        if skipped:
            msg += "\n\n제외/실패:\n" + "\n".join(skipped[:15])
            if len(skipped) > 15:
                msg += "\n…"
        QMessageBox.information(self, "재고 반영", msg)
        self._reload_stock_table()
        self._reload_receipt_list()
        if self._receipt_id:
            self._select_receipt_row_by_id(self._receipt_id)
            self._sync_stock_apply_ui(
                self.mgr.get_receipt(self.farm_cd, self._receipt_id)
            )

    def _on_delete_receipt(self):
        if not self._receipt_id:
            return
        if (
            QMessageBox.question(self, "삭제", "이 명세와 품목 행을 삭제합니다. 계속할까요?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.mgr.delete_receipt(self.farm_cd, self._receipt_id):
            self._clear_receipt_form()
            self._reload_receipt_list()

    # --- 공급자 ---
    def _build_supplier_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(12)

        sup_sec = QLabel("공급자 마스터")
        sup_sec.setStyleSheet(MainStyles.LBL_TABLE_SUB)
        lay.addWidget(sup_sec)

        form = QGroupBox("공급자 입력")
        form.setStyleSheet(MainStyles.GROUP_BOX)
        gl = QGridLayout(form)
        gl.setContentsMargins(16, 20, 16, 12)
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(10)
        self.sup_biz = QLineEdit()
        self.sup_biz.setPlaceholderText("사업자등록번호")
        self.sup_biz.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sup_nm = QLineEdit()
        self.sup_nm.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sup_ceo = QLineEdit()
        self.sup_ceo.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sup_addr = QLineEdit()
        self.sup_addr.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sup_type = QLineEdit()
        self.sup_type.setPlaceholderText("업태")
        self.sup_type.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sup_item = QLineEdit()
        self.sup_item.setPlaceholderText("종목")
        self.sup_item.setStyleSheet(MainStyles.INPUT_CENTER)
        gl.addWidget(_form_field_label("사업자번호"), 0, 0)
        gl.addWidget(self.sup_biz, 0, 1)
        gl.addWidget(_form_field_label("상호"), 1, 0)
        gl.addWidget(self.sup_nm, 1, 1)
        gl.addWidget(_form_field_label("대표자"), 2, 0)
        gl.addWidget(self.sup_ceo, 2, 1)
        gl.addWidget(_form_field_label("주소"), 3, 0)
        gl.addWidget(self.sup_addr, 3, 1)
        gl.addWidget(_form_field_label("업태 / 종목"), 4, 0)
        hb = QHBoxLayout()
        hb.addWidget(self.sup_type)
        hb.addWidget(self.sup_item)
        gl.addLayout(hb, 4, 1)
        self.sup_lbl_mode = QLabel("신규 등록 모드 — 표에서 행을 선택하면 수정 모드로 전환됩니다.")
        self.sup_lbl_mode.setStyleSheet("color: #555; background: transparent;")
        self.sup_lbl_mode.setWordWrap(True)
        gl.addWidget(self.sup_lbl_mode, 5, 0, 1, 2)
        bl = QHBoxLayout()
        self.sup_btn_save = QPushButton("등록")
        self.sup_btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.sup_btn_save.clicked.connect(self._on_add_supplier)
        b_clear = QPushButton("입력 비우기")
        b_clear.setStyleSheet(MainStyles.BTN_SECONDARY)
        b_clear.clicked.connect(self._on_clear_supplier_form)
        b_del_sup = QPushButton("선택 삭제")
        b_del_sup.setStyleSheet(MainStyles.BTN_DANGER)
        b_del_sup.clicked.connect(self._on_delete_supplier)
        bl.addWidget(self.sup_btn_save)
        bl.addWidget(b_clear)
        bl.addWidget(b_del_sup)
        gl.addLayout(bl, 6, 0, 1, 2)
        lay.addWidget(form)

        search_row = QHBoxLayout()
        sl = QLabel("검색")
        sl.setStyleSheet(MainStyles.LBL_GRID_HEADER)
        search_row.addWidget(sl)
        self.sup_search = QLineEdit()
        self.sup_search.setPlaceholderText("상호 또는 사업자번호…")
        self.sup_search.setStyleSheet(MainStyles.INPUT_CENTER)
        self.sup_search.textChanged.connect(self._filter_supplier_table_rows)
        search_row.addWidget(self.sup_search, stretch=1)
        lay.addLayout(search_row)

        tbl_sec = QLabel("등록된 공급자")
        tbl_sec.setStyleSheet(MainStyles.LBL_TABLE_SUB)
        lay.addWidget(tbl_sec)

        sup_tbl_card = QFrame()
        sup_tbl_card.setStyleSheet(MainStyles.CARD)
        sup_tbl_lay = QVBoxLayout(sup_tbl_card)
        sup_tbl_lay.setContentsMargins(12, 12, 12, 12)
        self.sup_table = QTableWidget()
        self.sup_table.setColumnCount(5)
        self.sup_table.setHorizontalHeaderLabels(["ID", "사업자번호", "상호", "대표", "주소"])
        self.sup_table.setStyleSheet(MainStyles.TABLE)
        self.sup_table.setShowGrid(False)
        self.sup_table.setFrameShape(QFrame.Shape.NoFrame)
        self.sup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sup_table.setAlternatingRowColors(True)
        self.sup_table.itemSelectionChanged.connect(self._on_supplier_table_selected)
        sup_tbl_lay.addWidget(self.sup_table)
        lay.addWidget(sup_tbl_card)
        self._selected_supplier_id = None
        self._sync_supplier_form_mode_label()
        return w

    def _reload_supplier_table(self):
        self.sup_table.setRowCount(0)
        for s in self.mgr.list_suppliers(self.farm_cd):
            r = self.sup_table.rowCount()
            self.sup_table.insertRow(r)
            sid = int(s["supplier_id"])
            self.sup_table.setItem(r, 0, QTableWidgetItem(str(sid)))
            self.sup_table.setItem(r, 1, QTableWidgetItem(str(s.get("biz_reg_no") or "")))
            self.sup_table.setItem(r, 2, QTableWidgetItem(str(s.get("supplier_nm") or "")))
            self.sup_table.setItem(r, 3, QTableWidgetItem(str(s.get("ceo_nm") or "")))
            self.sup_table.setItem(r, 4, QTableWidgetItem(str(s.get("addr") or "")))
            self.sup_table.item(r, 0).setData(Qt.ItemDataRole.UserRole, sid)
        self._filter_supplier_table_rows(self.sup_search.text())

    def _filter_supplier_table_rows(self, text: str):
        q = (text or "").strip().lower()
        for r in range(self.sup_table.rowCount()):
            biz = (self.sup_table.item(r, 1).text() if self.sup_table.item(r, 1) else "").lower()
            nm = (self.sup_table.item(r, 2).text() if self.sup_table.item(r, 2) else "").lower()
            ok = not q or q in biz or q in nm
            self.sup_table.setRowHidden(r, not ok)

    def _sync_supplier_form_mode_label(self):
        if self._selected_supplier_id:
            self.sup_lbl_mode.setText(
                f"수정 모드 (공급자 ID {self._selected_supplier_id}) — 저장 시 변경 내용이 반영됩니다."
            )
            self.sup_btn_save.setText("수정 반영")
        else:
            self.sup_lbl_mode.setText(
                "신규 등록 모드 — 표에서 행을 선택하면 수정 모드로 전환됩니다."
            )
            self.sup_btn_save.setText("등록")

    def _on_clear_supplier_form(self):
        self._selected_supplier_id = None
        self.sup_biz.clear()
        self.sup_nm.clear()
        self.sup_ceo.clear()
        self.sup_addr.clear()
        self.sup_type.clear()
        self.sup_item.clear()
        self.sup_table.clearSelection()
        self._sync_supplier_form_mode_label()

    def _on_delete_supplier(self):
        if not self._selected_supplier_id:
            QMessageBox.information(self, "안내", "삭제할 공급자를 표에서 선택하세요.")
            return
        nm = self.sup_nm.text().strip() or f"ID {self._selected_supplier_id}"
        if (
            QMessageBox.question(
                self,
                "삭제",
                f"[{nm}] 공급자를 삭제(비활성) 처리할까요?\n입고 명세 등 기존 기록과의 연결은 유지됩니다.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.mgr.soft_delete_supplier(self.farm_cd, self.user_id, self._selected_supplier_id):
            QMessageBox.information(self, "공급자", "삭제(비활성) 처리했습니다.")
            self._on_clear_supplier_form()
            self._reload_supplier_table()
            self._reload_supplier_combo()
        else:
            QMessageBox.warning(self, "공급자", "삭제 처리에 실패했습니다.")

    def _on_supplier_table_selected(self):
        sel = self.sup_table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        it = self.sup_table.item(row, 0)
        if not it:
            return
        sid = int(it.data(Qt.ItemDataRole.UserRole))
        self._selected_supplier_id = sid
        for s in self.mgr.list_suppliers(self.farm_cd):
            if int(s["supplier_id"]) == sid:
                self.sup_biz.setText(str(s.get("biz_reg_no") or ""))
                self.sup_nm.setText(str(s.get("supplier_nm") or ""))
                self.sup_ceo.setText(str(s.get("ceo_nm") or ""))
                self.sup_addr.setText(str(s.get("addr") or ""))
                self.sup_type.setText(str(s.get("biz_type") or ""))
                self.sup_item.setText(str(s.get("biz_item") or ""))
                break
        self._sync_supplier_form_mode_label()

    def _on_add_supplier(self):
        nm = self.sup_nm.text().strip()
        if not nm:
            QMessageBox.warning(self, "입력", "상호(공급자명)는 필수입니다.")
            return
        if self._selected_supplier_id:
            ok = self.mgr.update_supplier(
                self.farm_cd,
                self.user_id,
                self._selected_supplier_id,
                nm,
                self.sup_biz.text(),
                self.sup_ceo.text(),
                self.sup_addr.text(),
                self.sup_type.text(),
                self.sup_item.text(),
            )
            msg = "수정했습니다." if ok else "수정에 실패했습니다."
        else:
            new_id = self.mgr.insert_supplier(
                self.farm_cd,
                self.user_id,
                nm,
                self.sup_biz.text(),
                self.sup_ceo.text(),
                self.sup_addr.text(),
                self.sup_type.text(),
                self.sup_item.text(),
            )
            ok = bool(new_id)
            msg = "등록했습니다." if ok else "등록에 실패했습니다."
        QMessageBox.information(self, "공급자", msg)
        self._reload_supplier_table()
        self._reload_supplier_combo()
        if ok:
            self._on_clear_supplier_form()
