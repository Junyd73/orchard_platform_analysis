# -*- coding: utf-8 -*-
"""농약 사용관리: 사용 등록·이력 조회·AI 추천."""

from __future__ import annotations

import sys
from pathlib import Path

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.code_manager import CodeManager
from core.pesticide_manager import PesticideManager
from ui.styles import MainStyles
from ui.widgets.pesticide_ai_recommend_panel import PesticideAIRecommendPanel


def _lbl_field(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setStyleSheet(MainStyles.LBL_GRID_HEADER)
    return lb


def _same_site_id(a, b) -> bool:
    """필지 PK가 숫자·문자 혼용될 때 비교."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return str(a) == str(b)


# 세션에 farm_cd가 없을 때 과수원 마스터(farm_site_page)·영농일지와 동일하게 사용하는 기본 코드
_PESTICIDE_USE_DEFAULT_FARM_CD = "OR001"


class PesticideUsePage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        self.farm_cd = (
            str(session.get("farm_cd") or "").strip() or _PESTICIDE_USE_DEFAULT_FARM_CD
        )
        self.user_id = session.get("user_id", "")
        self.mgr = PesticideManager(db_manager)
        self.code_mgr = CodeManager(db_manager, self.farm_cd)
        self._items: list = []
        self._current_use_id = None

        self.tabs = QTabWidget()
        self._build_ui()
        self.setStyleSheet(MainStyles.MAIN_BG)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)
        title = QLabel("📝 농약 사용관리")
        title.setStyleSheet(MainStyles.LBL_TITLE)
        root.addWidget(title)
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)
        self.tabs.addTab(self._build_register_tab(), "사용등록")
        self.tabs.addTab(self._build_query_tab(), "사용이력조회")
        self._ai_panel = PesticideAIRecommendPanel(self.farm_cd)
        self.tabs.addTab(self._ai_panel, "농약 AI 추천")
        root.addWidget(self.tabs, stretch=1)
        QTimer.singleShot(0, self.refresh_data)

    def refresh_data(self):
        self._ai_panel.set_farm_cd(self.farm_cd)
        self._reload_items_cache()
        if self.tabs.currentIndex() == 1:
            self._run_query()

    def _reload_items_cache(self):
        self._items = self.mgr.list_items(self.farm_cd)

    def _apply_date_edit_style(self, date_edit: QDateEdit) -> None:
        """농약 사용관리 날짜 위젯 공통 스타일(캘린더 년/월 헤더 가시성 보장)."""
        date_edit.setStyleSheet(MainStyles.COMBO)
        date_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cal = date_edit.calendarWidget()
        cal.setStyleSheet(
            """
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #F8F9FA;
                border-bottom: 1px solid #E2E8F0;
            }
            QCalendarWidget QToolButton {
                color: #2D3748;
                font-weight: bold;
                background: transparent;
                border: none;
                min-width: 64px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #E2E8F0;
                border-radius: 4px;
            }
            QCalendarWidget QSpinBox {
                color: #1A202C;
                background: #FFFFFF;
            }
            """
        )

    def _item_by_id(self, item_id: int):
        for it in self._items:
            if int(it["item_id"]) == int(item_id):
                return it
        return None

    def _build_register_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(12)

        head = QGroupBox("사용 정보")
        head.setStyleSheet(MainStyles.GROUP_BOX)
        gl = QGridLayout(head)
        gl.setContentsMargins(16, 20, 16, 12)
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(10)

        self.use_dt = QDateEdit()
        self.use_dt.setCalendarPopup(True)
        self.use_dt.setDate(QDate.currentDate())
        self.use_dt.setDisplayFormat("yyyy-MM-dd")
        self._apply_date_edit_style(self.use_dt)

        self.use_site = QComboBox()
        self.use_site.setStyleSheet(MainStyles.COMBO)
        self._fill_site_combo()

        self.use_worker = QLineEdit()
        self.use_worker.setStyleSheet(MainStyles.INPUT_CENTER)
        self.use_worker.setText(str(self.session.get("user_nm", "") or ""))

        self.use_work_type = QLineEdit()
        self.use_work_type.setPlaceholderText("예: 방제, 예방살포")
        self.use_work_type.setStyleSheet(MainStyles.INPUT_CENTER)

        self.use_rmk = QLineEdit()
        self.use_rmk.setStyleSheet(MainStyles.INPUT_CENTER)

        gl.addWidget(_lbl_field("사용일자"), 0, 0)
        gl.addWidget(self.use_dt, 0, 1)
        gl.addWidget(_lbl_field("필지"), 0, 2)
        gl.addWidget(self.use_site, 0, 3)
        gl.addWidget(_lbl_field("작업자명"), 1, 0)
        gl.addWidget(self.use_worker, 1, 1)
        gl.addWidget(_lbl_field("작업유형"), 1, 2)
        gl.addWidget(self.use_work_type, 1, 3)
        gl.addWidget(_lbl_field("비고"), 2, 0)
        gl.addWidget(self.use_rmk, 2, 1, 1, 3)

        self.use_status_lbl = QLabel("")
        self.use_status_lbl.setStyleSheet("font-weight: bold; color: #2D5A27;")
        gl.addWidget(self.use_status_lbl, 3, 0, 1, 4)

        lay.addWidget(head)

        sec = QLabel("사용 품목")
        sec.setStyleSheet(MainStyles.LBL_TABLE_SUB)
        lay.addWidget(sec)

        card = QFrame()
        card.setStyleSheet(MainStyles.CARD)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(12, 12, 12, 12)
        self.use_lines = QTableWidget()
        self.use_lines.setColumnCount(6)
        self.use_lines.setHorizontalHeaderLabels(
            ["품목", "규격", "현재고(낱개)", "사용수량", "사용목적", "비고"]
        )
        self.use_lines.setStyleSheet(MainStyles.TABLE)
        self.use_lines.setShowGrid(False)
        self.use_lines.setFrameShape(QFrame.Shape.NoFrame)
        hh = self.use_lines.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.use_lines.setMinimumHeight(120)
        self.use_lines.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.use_lines.setAlternatingRowColors(True)
        self.use_lines.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        scr_lines = QScrollArea()
        scr_lines.setWidgetResizable(True)
        scr_lines.setFrameShape(QFrame.Shape.NoFrame)
        scr_lines.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scr_lines.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hold_lines = QWidget()
        hl_lines = QVBoxLayout(hold_lines)
        hl_lines.setContentsMargins(0, 0, 0, 0)
        hl_lines.addWidget(self.use_lines)
        scr_lines.setWidget(hold_lines)
        cv.addWidget(scr_lines)
        lay.addWidget(card, stretch=1)

        btns = QHBoxLayout()
        self.btn_new = QPushButton("새 문서")
        self.btn_new.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_new.clicked.connect(self._on_new_doc)
        self.btn_add_row = QPushButton("행 추가")
        self.btn_add_row.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_add_row.clicked.connect(self._on_add_line)
        self.btn_del_row = QPushButton("선택 행 삭제")
        self.btn_del_row.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_del_row.clicked.connect(self._on_del_line)
        self.btn_save = QPushButton("저장")
        self.btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_save.clicked.connect(self._on_save_use)
        self.btn_apply = QPushButton("사용 확정")
        self.btn_apply.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_apply.clicked.connect(self._on_apply_use)
        self.btn_cancel_ap = QPushButton("사용 취소")
        self.btn_cancel_ap.setStyleSheet(MainStyles.BTN_DANGER)
        self.btn_cancel_ap.clicked.connect(self._on_cancel_use)
        for b in (
            self.btn_new,
            self.btn_add_row,
            self.btn_del_row,
            self.btn_save,
            self.btn_apply,
            self.btn_cancel_ap,
        ):
            btns.addWidget(b)
        btns.addStretch()
        lay.addLayout(btns)

        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return w

    def _fill_site_combo(self):
        self.use_site.blockSignals(True)
        self.use_site.clear()
        self.use_site.addItem("(필지 미선택)", None)
        try:
            sites = self.code_mgr.get_farm_sites()
        except Exception:
            sites = []
        for loc in sites or []:
            try:
                sid = loc["site_id"]
                snm = loc["site_nm"] or ""
            except (TypeError, KeyError):
                continue
            # m_farm_site.site_id는 INTEGER 또는 문자열(레거시) 모두 가능
            self.use_site.addItem(snm, sid)
        self.use_site.blockSignals(False)

    def _make_item_combo(self, selected_id=None):
        cb = QComboBox()
        cb.setStyleSheet(MainStyles.COMBO_TABLE_CELL)
        cb.addItem("(품목 선택)", None)
        for it in self._items:
            cb.addItem(it.get("item_nm") or "", int(it["item_id"]))
        if selected_id is not None:
            for i in range(cb.count()):
                if cb.itemData(i) == int(selected_id):
                    cb.setCurrentIndex(i)
                    break
        cb.currentIndexChanged.connect(lambda *_: self._on_line_item_changed(cb))
        return cb

    def _row_for_combo(self, cb: QComboBox) -> int:
        for r in range(self.use_lines.rowCount()):
            if self.use_lines.cellWidget(r, 0) is cb:
                return r
        return -1

    def _on_line_item_changed(self, cb: QComboBox):
        r = self._row_for_combo(cb)
        if r < 0:
            return
        iid = cb.currentData()
        sp_it = self.use_lines.item(r, 1)
        st_it = self.use_lines.item(r, 2)
        if iid is None:
            if sp_it:
                sp_it.setText("")
            if st_it:
                st_it.setText("")
            return
        it = self._item_by_id(int(iid))
        if not it:
            return
        spec = str(it.get("spec_nm") or "")
        stock = int(it.get("qty_piece") or 0)
        if sp_it:
            sp_it.setText(spec)
        if st_it:
            st_it.setText(str(stock))

    def _set_line_row_readonly(self, r: int, ro: bool):
        cb = self.use_lines.cellWidget(r, 0)
        if isinstance(cb, QComboBox):
            cb.setEnabled(not ro)
        sp = self.use_lines.cellWidget(r, 3)
        if isinstance(sp, QSpinBox):
            sp.setEnabled(not ro)
        for c in (4, 5):
            it = self.use_lines.item(r, c)
            if it:
                f = it.flags()
                if ro:
                    it.setFlags(f & ~Qt.ItemFlag.ItemIsEditable)
                else:
                    it.setFlags(f | Qt.ItemFlag.ItemIsEditable)

    def _append_line_row(self, ln: dict | None = None) -> None:
        ln = ln or {}
        r = self.use_lines.rowCount()
        self.use_lines.insertRow(r)
        iid = ln.get("item_id")
        cb = self._make_item_combo(int(iid) if iid else None)
        self.use_lines.setCellWidget(r, 0, cb)
        sp = QTableWidgetItem(str(ln.get("spec_nm_snapshot", "")))
        sp.setFlags(sp.flags() & ~Qt.ItemFlag.ItemIsEditable)
        st = QTableWidgetItem("")
        st.setFlags(st.flags() & ~Qt.ItemFlag.ItemIsEditable)
        st.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.use_lines.setItem(r, 1, sp)
        self.use_lines.setItem(r, 2, st)
        sb = QSpinBox()
        sb.setRange(0, 999999)
        sb.setStyleSheet(MainStyles.SPINBOX_TABLE_CELL)
        sb.setAlignment(Qt.AlignmentFlag.AlignRight)
        sb.setValue(max(0, int(ln.get("use_qty") or 0)))
        self.use_lines.setCellWidget(r, 3, sb)
        self.use_lines.setItem(r, 4, QTableWidgetItem(str(ln.get("purpose_nm", ""))))
        self.use_lines.setItem(r, 5, QTableWidgetItem(str(ln.get("line_rmk", ""))))
        if iid:
            self._on_line_item_changed(cb)

    def _sync_register_editable(self, confirmed: bool):
        ro = confirmed
        self.use_dt.setEnabled(not ro)
        self.use_site.setEnabled(not ro)
        self.use_worker.setEnabled(not ro)
        self.use_work_type.setEnabled(not ro)
        self.use_rmk.setEnabled(not ro)
        self.btn_add_row.setEnabled(not ro)
        self.btn_del_row.setEnabled(not ro)
        self.btn_save.setEnabled(not ro)
        self.btn_apply.setEnabled(not ro)
        self.btn_cancel_ap.setEnabled(confirmed)
        for r in range(self.use_lines.rowCount()):
            self._set_line_row_readonly(r, ro)

    def _sync_register_status_label(self, rec: dict | None):
        if not self._current_use_id:
            self.use_status_lbl.setText("미저장 문서 — 저장 후 「사용 확정」으로 재고에서 차감합니다.")
            self.btn_apply.setEnabled(False)
            self.btn_cancel_ap.setEnabled(False)
            return
        yn = str((rec or {}).get("stock_applied_yn") or "N").strip().upper()
        if yn == "Y":
            self.use_status_lbl.setText(
                "재고 차감 완료 — 수정·저장·재확정은 불가합니다. 「사용 취소」 후 편집하세요."
            )
            self.btn_apply.setEnabled(False)
            self.btn_save.setEnabled(False)
        else:
            self.use_status_lbl.setText("미확정 — 저장 후 「사용 확정」하면 낱개 재고가 차감됩니다.")
            self.btn_save.setEnabled(True)
            self.btn_cancel_ap.setEnabled(False)
            self.btn_apply.setEnabled(True)

    def _clear_register(self):
        self._current_use_id = None
        self.use_dt.setDate(QDate.currentDate())
        self.use_site.setCurrentIndex(0)
        self.use_worker.setText(str(self.session.get("user_nm", "") or ""))
        self.use_work_type.clear()
        self.use_rmk.clear()
        self.use_lines.setRowCount(0)
        self._sync_register_editable(False)
        self._sync_register_status_label({})

    def _load_use_into_register(self, use_id: int):
        rec = self.mgr.get_use_header(self.farm_cd, use_id)
        if not rec:
            QMessageBox.warning(self, "안내", "문서를 찾을 수 없습니다.")
            return
        self._current_use_id = use_id
        ymd = str(rec.get("use_dt") or "")
        if len(ymd) >= 10:
            self.use_dt.setDate(QDate.fromString(ymd[:10], Qt.DateFormat.ISODate))
        sid = rec.get("site_id")
        self.use_site.blockSignals(True)
        self.use_site.setCurrentIndex(0)
        if sid is not None:
            for i in range(self.use_site.count()):
                if _same_site_id(self.use_site.itemData(i), sid):
                    self.use_site.setCurrentIndex(i)
                    break
        self.use_site.blockSignals(False)
        self.use_worker.setText(str(rec.get("worker_nm") or ""))
        self.use_work_type.setText(str(rec.get("work_type_nm") or ""))
        self.use_rmk.setText(str(rec.get("rmk") or ""))
        self.use_lines.setRowCount(0)
        self._reload_items_cache()
        for ln in self.mgr.list_use_lines(use_id):
            self._append_line_row(ln)
        confirmed = str(rec.get("stock_applied_yn") or "N").strip().upper() == "Y"
        self._sync_register_editable(confirmed)
        self._sync_register_status_label(rec)

    def _collect_lines(self) -> list:
        out = []
        for r in range(self.use_lines.rowCount()):
            cb = self.use_lines.cellWidget(r, 0)
            if not isinstance(cb, QComboBox):
                continue
            iid = cb.currentData()
            if iid is None:
                continue
            it = self._item_by_id(int(iid))
            nm = (it or {}).get("item_nm") or ""
            spec = (it or {}).get("spec_nm") or ""
            sb = self.use_lines.cellWidget(r, 3)
            uq = sb.value() if isinstance(sb, QSpinBox) else 0
            p4 = self.use_lines.item(r, 4)
            p5 = self.use_lines.item(r, 5)
            out.append(
                {
                    "item_id": int(iid),
                    "item_nm_snapshot": nm,
                    "spec_nm_snapshot": spec,
                    "use_qty": int(uq),
                    "purpose_nm": p4.text().strip() if p4 else "",
                    "line_rmk": p5.text().strip() if p5 else "",
                }
            )
        return out

    def _on_new_doc(self):
        self._clear_register()

    def _on_add_line(self):
        self._reload_items_cache()
        self._append_line_row({})

    def _on_del_line(self):
        r = self.use_lines.currentRow()
        if r < 0:
            QMessageBox.information(self, "안내", "삭제할 행을 선택하세요.")
            return
        self.use_lines.removeRow(r)

    def _on_save_use(self):
        dt = self.use_dt.date().toString(Qt.DateFormat.ISODate)
        if not dt.strip():
            QMessageBox.warning(self, "입력", "사용일자를 지정하세요.")
            return
        si = self.use_site.currentIndex()
        site_id = self.use_site.itemData(si)
        site_sql = site_id if site_id is not None else None
        lines = self._collect_lines()
        try:
            uid = self.mgr.save_use_full(
                self.farm_cd,
                self.user_id,
                self._current_use_id,
                dt,
                site_sql,
                self.use_worker.text(),
                "",
                self.use_work_type.text(),
                self.use_rmk.text(),
                lines,
            )
        except ValueError as e:
            QMessageBox.warning(self, "저장", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return
        if not uid:
            QMessageBox.warning(self, "저장 실패", "저장에 실패했습니다.")
            return
        self._current_use_id = uid
        self._load_use_into_register(uid)
        QMessageBox.information(self, "저장", "저장했습니다.")

    def _on_apply_use(self):
        if not self._current_use_id:
            QMessageBox.information(self, "안내", "먼저 저장하세요.")
            return
        ok, errs = self.mgr.apply_use_to_stock(self.farm_cd, self.user_id, self._current_use_id)
        if not ok:
            QMessageBox.warning(self, "사용 확정", "\n".join(errs[:20]))
            return
        QMessageBox.information(self, "사용 확정", "재고에서 낱개를 차감했습니다.")
        self._load_use_into_register(self._current_use_id)
        self._reload_items_cache()

    def _on_cancel_use(self):
        if not self._current_use_id:
            return
        if (
            QMessageBox.question(
                self,
                "사용 취소",
                "확정을 취소하고 낱개 재고를 복원할까요?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        ok, errs = self.mgr.cancel_use_restore_stock(self.farm_cd, self.user_id, self._current_use_id)
        if not ok:
            QMessageBox.warning(self, "취소 실패", "\n".join(errs))
            return
        QMessageBox.information(self, "사용 취소", "재고를 복원하고 미확정 상태로 되돌렸습니다.")
        self._load_use_into_register(self._current_use_id)
        self._reload_items_cache()

    def _build_query_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 16)
        filt = QGroupBox("조회 조건")
        filt.setStyleSheet(MainStyles.GROUP_BOX)
        filt_lay = QHBoxLayout()
        filt_lay.setContentsMargins(16, 16, 16, 12)
        filt_lay.setSpacing(12)
        self.q_date_from = QDateEdit()
        self.q_date_from.setCalendarPopup(True)
        self.q_date_from.setDate(QDate.currentDate().addMonths(-1))
        self.q_date_from.setDisplayFormat("yyyy-MM-dd")
        self._apply_date_edit_style(self.q_date_from)
        self.q_date_to = QDateEdit()
        self.q_date_to.setCalendarPopup(True)
        self.q_date_to.setDate(QDate.currentDate())
        self.q_date_to.setDisplayFormat("yyyy-MM-dd")
        self._apply_date_edit_style(self.q_date_to)
        self.q_item = QLineEdit()
        self.q_item.setPlaceholderText("농약종류(품목명) 포함 검색")
        self.q_item.setStyleSheet(MainStyles.INPUT_CENTER)
        self.q_site = QComboBox()
        self.q_site.setStyleSheet(MainStyles.COMBO)
        self.q_site.addItem("전체 필지", None)
        try:
            for loc in self.code_mgr.get_farm_sites() or []:
                self.q_site.addItem(loc["site_nm"], loc["site_id"])
        except Exception:
            pass
        self.q_worker = QLineEdit()
        self.q_worker.setPlaceholderText("작업자명")
        self.q_worker.setStyleSheet(MainStyles.INPUT_CENTER)
        self.q_conf = QComboBox()
        self.q_conf.setStyleSheet(MainStyles.COMBO)
        self.q_conf.addItem("전체", None)
        self.q_conf.addItem("미확정", False)
        self.q_conf.addItem("확정", True)
        btn_q = QPushButton("조회")
        btn_q.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_q.clicked.connect(self._run_query)
        # 조회조건 3열 동일 폭(1:1:1): 열별 2행 구성
        _date_w = 150
        self.q_date_from.setMinimumWidth(_date_w)
        self.q_date_to.setMinimumWidth(_date_w)
        self.q_date_from.setMaximumWidth(_date_w)
        self.q_date_to.setMaximumWidth(_date_w)

        def _pair_row_stretch(lbl: QLabel, w: QWidget) -> QHBoxLayout:
            h = QHBoxLayout()
            h.setSpacing(8)
            h.addWidget(lbl)
            h.addWidget(w, 1)
            return h

        def _pair_row_date(lbl: QLabel, de: QDateEdit) -> QHBoxLayout:
            h = QHBoxLayout()
            h.setSpacing(8)
            h.addWidget(lbl)
            h.addWidget(de)
            h.addStretch(1)
            return h

        col1 = QVBoxLayout()
        col1.setSpacing(10)
        col1.addLayout(_pair_row_date(_lbl_field("시작일"), self.q_date_from))
        col1.addLayout(_pair_row_stretch(_lbl_field("농약종류"), self.q_item))

        col2 = QVBoxLayout()
        col2.setSpacing(10)
        col2.addLayout(_pair_row_date(_lbl_field("종료일"), self.q_date_to))
        col2.addLayout(_pair_row_stretch(_lbl_field("작업필지"), self.q_site))

        col3 = QVBoxLayout()
        col3.setSpacing(10)
        col3.addLayout(_pair_row_stretch(_lbl_field("작업자"), self.q_worker))
        h_conf = QHBoxLayout()
        h_conf.setSpacing(8)
        h_conf.addWidget(_lbl_field("확정상태"))
        h_conf.addWidget(self.q_conf, 1)
        h_conf.addWidget(btn_q)
        col3.addLayout(h_conf)

        filt_lay.addLayout(col1, 1)
        filt_lay.addLayout(col2, 1)
        filt_lay.addLayout(col3, 1)
        filt.setLayout(filt_lay)
        lay.addWidget(filt)

        split = QSplitter(Qt.Orientation.Vertical)
        self.q_list = QTableWidget()
        self.q_list.setColumnCount(7)
        self.q_list.setHorizontalHeaderLabels(
            ["번호", "사용일자", "필지", "작업자", "작업유형", "비고", "확정"]
        )
        self.q_list.setStyleSheet(MainStyles.TABLE)
        self.q_list.setShowGrid(False)
        self.q_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.q_list.setAlternatingRowColors(True)
        self.q_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.q_list.setMinimumHeight(100)
        self.q_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.q_list.itemSelectionChanged.connect(self._on_query_select)
        scr_qlist = QScrollArea()
        scr_qlist.setWidgetResizable(True)
        scr_qlist.setFrameShape(QFrame.Shape.NoFrame)
        scr_qlist.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scr_qlist.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hold_qlist = QWidget()
        hql = QVBoxLayout(hold_qlist)
        hql.setContentsMargins(0, 0, 0, 0)
        hql.addWidget(self.q_list)
        scr_qlist.setWidget(hold_qlist)
        split.addWidget(scr_qlist)

        det_fr = QFrame()
        det_fr.setStyleSheet(MainStyles.CARD)
        dvl = QVBoxLayout(det_fr)
        dvl.setContentsMargins(12, 12, 12, 12)
        dvl.addWidget(QLabel("선택 문서 상세"))
        self.q_detail = QTableWidget()
        self.q_detail.setColumnCount(5)
        self.q_detail.setHorizontalHeaderLabels(
            ["품목명", "규격", "사용수량", "사용목적", "비고"]
        )
        self.q_detail.setStyleSheet(MainStyles.TABLE)
        self.q_detail.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.q_detail.setMinimumHeight(80)
        self.q_detail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        scr_qdet = QScrollArea()
        scr_qdet.setWidgetResizable(True)
        scr_qdet.setFrameShape(QFrame.Shape.NoFrame)
        scr_qdet.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scr_qdet.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hold_qdet = QWidget()
        hqdl = QVBoxLayout(hold_qdet)
        hqdl.setContentsMargins(0, 0, 0, 0)
        hqdl.addWidget(self.q_detail)
        scr_qdet.setWidget(hold_qdet)
        dvl.addWidget(scr_qdet, stretch=1)
        btn_open = QPushButton("등록 탭에서 열기")
        btn_open.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_open.clicked.connect(self._open_selected_in_register)
        dvl.addWidget(btn_open)
        split.addWidget(det_fr)
        split.setChildrenCollapsible(False)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, stretch=1)
        return w

    def _run_query(self):
        df = self.q_date_from.date().toString(Qt.DateFormat.ISODate)
        dt = self.q_date_to.date().toString(Qt.DateFormat.ISODate)
        item_q = self.q_item.text().strip()
        wk = self.q_worker.text().strip()
        sidx = self.q_site.currentIndex()
        site_f = self.q_site.itemData(sidx)
        cidx = self.q_conf.currentIndex()
        conf = self.q_conf.itemData(cidx)
        rows = self.mgr.list_use_headers_filtered(
            self.farm_cd,
            date_from=df,
            date_to=dt,
            item_nm_sub=item_q,
            site_id_eq=site_f if site_f is not None else None,
            worker_nm_sub=wk,
            confirmed=conf,
            limit=500,
        )
        self.q_list.setRowCount(0)
        self.q_detail.setRowCount(0)
        for rec in rows:
            r = self.q_list.rowCount()
            self.q_list.insertRow(r)
            uid = int(rec["use_id"])
            self.q_list.setItem(r, 0, QTableWidgetItem(str(uid)))
            self.q_list.setItem(r, 1, QTableWidgetItem(str(rec.get("use_dt") or "")))
            self.q_list.setItem(r, 2, QTableWidgetItem(str(rec.get("site_nm_joined") or "")))
            self.q_list.setItem(r, 3, QTableWidgetItem(str(rec.get("worker_nm") or "")))
            self.q_list.setItem(r, 4, QTableWidgetItem(str(rec.get("work_type_nm") or "")))
            self.q_list.setItem(r, 5, QTableWidgetItem(str(rec.get("rmk") or "")))
            yn = str(rec.get("stock_applied_yn") or "N").strip().upper()
            self.q_list.setItem(r, 6, QTableWidgetItem("확정" if yn == "Y" else "미확정"))
            self.q_list.item(r, 0).setData(Qt.ItemDataRole.UserRole, uid)

    def _selected_query_use_id(self):
        r = self.q_list.currentRow()
        if r < 0:
            return None
        it = self.q_list.item(r, 0)
        if not it:
            return None
        return int(it.data(Qt.ItemDataRole.UserRole))

    def _on_query_select(self):
        uid = self._selected_query_use_id()
        self.q_detail.setRowCount(0)
        if uid is None:
            return
        for ln in self.mgr.list_use_lines(uid):
            r = self.q_detail.rowCount()
            self.q_detail.insertRow(r)
            self.q_detail.setItem(r, 0, QTableWidgetItem(str(ln.get("item_nm_snapshot", ""))))
            self.q_detail.setItem(r, 1, QTableWidgetItem(str(ln.get("spec_nm_snapshot", ""))))
            self.q_detail.setItem(r, 2, QTableWidgetItem(str(int(ln.get("use_qty") or 0))))
            self.q_detail.setItem(r, 3, QTableWidgetItem(str(ln.get("purpose_nm", ""))))
            self.q_detail.setItem(r, 4, QTableWidgetItem(str(ln.get("line_rmk", ""))))

    def _open_selected_in_register(self):
        uid = self._selected_query_use_id()
        if uid is None:
            QMessageBox.information(self, "안내", "목록에서 문서를 선택하세요.")
            return
        self.tabs.setCurrentIndex(0)
        self._reload_items_cache()
        self._fill_site_combo()
        self._load_use_into_register(uid)
