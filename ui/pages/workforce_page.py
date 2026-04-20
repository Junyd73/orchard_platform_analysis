# -*- coding: utf-8 -*-
"""인력관리: 마스터·투입 이력·지급/미지급 (m_partner.worker_type_cd 연동)."""

from pathlib import Path
import re
import sys

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.styles import MainStyles

WORKER_TYPE_LABELS = {
    "EMP": "고용인력",
    "OWNER": "농장주",
    "FAMILY": "가족",
    "TEMP": "일용/외부",
}
WORKER_TYPE_CODES = ("EMP", "OWNER", "FAMILY", "TEMP")


def _worker_type_label(code: str) -> str:
    c = (code or "EMP").strip().upper() or "EMP"
    return WORKER_TYPE_LABELS.get(c, c)


def _ymd_key(d: QDate) -> str:
    return d.toString("yyyyMMdd")


def _price_digits_int(s: str) -> int:
    """콤마·공백 제거 후 정수 금액."""
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


def _apply_workforce_list_combo_look(cb: QComboBox) -> None:
    """테이블 내 QLineEdit(10pt)과 동일하게: 스타일시트(pt) + 상위 전파 폰트 무력화."""
    cb.setStyleSheet(MainStyles.COMBO_WORKFORCE_LIST_CELL)


class WorkforcePage(QWidget):
    """과수원관리(MN02G) 하위 MN08 — 인력 목록 / 투입 이력 / 지급내역."""

    def __init__(self, db_manager, session, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.session = session or {}
        self.farm_cd = (self.session.get("farm_cd") or "").strip() or "OR001"
        self.user_id = (self.session.get("user_id") or "").strip() or ""
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        lay.setSpacing(8)
        title = QLabel("인력관리")
        title.setStyleSheet(MainStyles.TXT_CARD_TITLE + " color:#2D3748;")
        lay.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)
        self.tabs.addTab(self._tab_list(), "인력 목록")
        self.tabs.addTab(self._tab_history(), "투입 이력")
        self.tabs.addTab(self._tab_pay(), "지급내역")
        lay.addWidget(self.tabs, 1)

    def _tab_list(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        hl = QHBoxLayout()
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("이름 검색")
        self.ed_search.setStyleSheet(MainStyles.INPUT_CENTER)
        self.ed_search.setMinimumWidth(200)
        btn_search = QPushButton("검색")
        btn_search.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        btn_search.clicked.connect(self._reload_list)
        self.chk_list_linked_user = QCheckBox("실사용자만 보기")
        self.chk_list_linked_user.setStyleSheet(MainStyles.CHK_CAPTION)
        self.chk_list_linked_user.toggled.connect(self._reload_list)
        btn_add = QPushButton("등록")
        btn_add.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        btn_add.clicked.connect(self._add_inline_row)
        btn_save = QPushButton("저장")
        btn_save.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        btn_save.clicked.connect(self._save_inline_rows)
        btn_stop = QPushButton("사용중지")
        btn_stop.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        btn_stop.clicked.connect(self._deactivate_partner)
        hl.addWidget(self.ed_search)
        hl.addWidget(btn_search)
        hl.addWidget(self.chk_list_linked_user)
        hl.addStretch()
        hl.addWidget(btn_add)
        hl.addWidget(btn_save)
        hl.addWidget(btn_stop)
        vl.addLayout(hl)
        self.tbl_list = QTableWidget(0, 7)
        self.tbl_list.setHorizontalHeaderLabels(
            ["이름", "구분", "연락처", "기본단가", "은행명", "계좌번호", "사용여부"]
        )
        self.tbl_list.setStyleSheet(MainStyles.TABLE + MainStyles.TABLE_WORKFORCE_LIST)
        self.tbl_list.verticalHeader().setVisible(False)
        hh = self.tbl_list.horizontalHeader()
        for c in range(7):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        self.tbl_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        vl.addWidget(self.tbl_list, 1)
        self._list_row_pt_ids = []
        self._reload_list()
        return w

    def _reload_list(self):
        if not hasattr(self, "tbl_list"):
            return
        q = self.ed_search.text().strip() if hasattr(self, "ed_search") else ""
        use_y_only = (
            self.chk_list_linked_user.isChecked() if hasattr(self, "chk_list_linked_user") else False
        )
        rows = self.db.list_workforce_partners(
            self.farm_cd, q if q else None, use_yn_y_only=use_y_only
        ) or []
        self.tbl_list.setRowCount(0)
        self._list_row_pt_ids = []
        for r in rows:
            i = self.tbl_list.rowCount()
            self.tbl_list.insertRow(i)
            self._list_row_pt_ids.append(r.get("pt_id"))
            self._fill_list_row_widgets(i, r)

    def _make_worker_type_combo(self) -> QComboBox:
        cb = QComboBox()
        _apply_workforce_list_combo_look(cb)
        for cd in WORKER_TYPE_CODES:
            cb.addItem(_worker_type_label(cd), cd)
        return cb

    def _make_use_yn_combo(self) -> QComboBox:
        cb = QComboBox()
        _apply_workforce_list_combo_look(cb)
        cb.addItem("Y", "Y")
        cb.addItem("N", "N")
        return cb

    def _fill_list_row_widgets(self, row: int, r: dict) -> None:
        ed_nm = QLineEdit()
        ed_nm.setStyleSheet(MainStyles.INPUT_WORKFORCE_LIST_CELL)
        ed_nm.setText(str(r.get("pt_nm") or ""))
        self.tbl_list.setCellWidget(row, 0, ed_nm)

        cb_type = self._make_worker_type_combo()
        wtc = str(r.get("worker_type_cd") or "EMP").upper()
        cb_type.setCurrentIndex(max(0, cb_type.findData(wtc)))
        self.tbl_list.setCellWidget(row, 1, cb_type)

        ed_tel = QLineEdit()
        ed_tel.setStyleSheet(MainStyles.INPUT_WORKFORCE_LIST_CELL)
        ed_tel.setText(str(r.get("pt_tel") or ""))
        self.tbl_list.setCellWidget(row, 2, ed_tel)

        ed_price = QLineEdit()
        ed_price.setStyleSheet(MainStyles.INPUT_WORKFORCE_LIST_PRICE)
        try:
            pv = int(float(r.get("base_price") or 0))
        except (TypeError, ValueError):
            pv = 0
        ed_price.setText(f"{pv:,}" if pv else "")
        ed_price.editingFinished.connect(lambda le=ed_price: self._format_price_lineedit(le))
        self.tbl_list.setCellWidget(row, 3, ed_price)

        ed_bank = QLineEdit()
        ed_bank.setStyleSheet(MainStyles.INPUT_WORKFORCE_LIST_CELL)
        ed_bank.setText(str(r.get("bank_cd") or ""))
        self.tbl_list.setCellWidget(row, 4, ed_bank)

        ed_acc = QLineEdit()
        ed_acc.setStyleSheet(MainStyles.INPUT_WORKFORCE_LIST_CELL)
        ed_acc.setText(str(r.get("account_no") or ""))
        self.tbl_list.setCellWidget(row, 5, ed_acc)

        cb_use = self._make_use_yn_combo()
        uy = str(r.get("use_yn") or "Y").upper()
        cb_use.setCurrentIndex(0 if uy == "Y" else 1)
        self.tbl_list.setCellWidget(row, 6, cb_use)

    def _format_price_lineedit(self, ed: QLineEdit) -> None:
        v = _price_digits_int(ed.text())
        ed.blockSignals(True)
        ed.setText(f"{v:,}" if v else "")
        ed.blockSignals(False)

    def _read_list_row_widgets(self, row: int) -> dict:
        ed_nm = self.tbl_list.cellWidget(row, 0)
        cb_type = self.tbl_list.cellWidget(row, 1)
        ed_tel = self.tbl_list.cellWidget(row, 2)
        ed_price = self.tbl_list.cellWidget(row, 3)
        ed_bank = self.tbl_list.cellWidget(row, 4)
        ed_acc = self.tbl_list.cellWidget(row, 5)
        cb_use = self.tbl_list.cellWidget(row, 6)
        wtc = str(cb_type.currentData() or "EMP") if cb_type else "EMP"
        uy = str(cb_use.currentData() or "Y") if cb_use else "Y"
        price = float(_price_digits_int(ed_price.text())) if ed_price else 0.0
        bank_nm = ed_bank.text().strip() if ed_bank else ""
        acc = ed_acc.text().strip() if ed_acc else ""
        return {
            "pt_nm": ed_nm.text().strip() if ed_nm else "",
            "worker_type_cd": wtc,
            "pt_tel": ed_tel.text().strip() if ed_tel else "",
            "base_price": price,
            "bank_cd": bank_nm or None,
            "account_no": acc,
            "use_yn": uy,
        }

    def _add_inline_row(self) -> None:
        self.tbl_list.insertRow(0)
        self._list_row_pt_ids.insert(0, None)
        empty = {
            "pt_nm": "",
            "worker_type_cd": "EMP",
            "pt_tel": "",
            "base_price": 0,
            "bank_cd": "",
            "account_no": "",
            "use_yn": "Y",
        }
        self._fill_list_row_widgets(0, empty)
        self.tbl_list.selectRow(0)
        ed0 = self.tbl_list.cellWidget(0, 0)
        if ed0:
            ed0.setFocus()

    def _save_inline_rows(self) -> None:
        if not hasattr(self, "tbl_list") or self.tbl_list.rowCount() == 0:
            QMessageBox.information(self, "안내", "저장할 행이 없습니다.")
            return
        if len(self._list_row_pt_ids) != self.tbl_list.rowCount():
            self._reload_list()
            QMessageBox.warning(self, "안내", "행 정보가 맞지 않아 새로고침했습니다. 다시 저장해 주세요.")
            return
        ok_any = False
        err_msgs = []
        for row in range(self.tbl_list.rowCount()):
            data = self._read_list_row_widgets(row)
            nm = data["pt_nm"]
            pid = self._list_row_pt_ids[row]
            if not nm:
                if pid is None:
                    continue
                err_msgs.append(f"{row + 1}행: 이름이 비어 있습니다.")
                continue
            if pid is None:
                ins = {
                    "pt_nm": nm,
                    "pt_tel": data["pt_tel"],
                    "base_price": data["base_price"],
                    "bank_cd": data.get("bank_cd"),
                    "account_no": data.get("account_no") or "",
                    "worker_type_cd": data["worker_type_cd"],
                    "use_yn": data["use_yn"],
                }
                new_id = self.db.add_new_partner_extended(self.farm_cd, ins, self.user_id)
                if new_id:
                    self._list_row_pt_ids[row] = new_id
                    ok_any = True
                else:
                    err_msgs.append(f"{row + 1}행: 등록 실패.")
            else:
                ok = self.db.update_workforce_partner(
                    self.farm_cd,
                    pid,
                    nm,
                    data["worker_type_cd"],
                    data["pt_tel"],
                    data["base_price"],
                    data["use_yn"],
                    bank_cd=data.get("bank_cd"),
                    account_no=data.get("account_no") or "",
                )
                if ok:
                    ok_any = True
                else:
                    err_msgs.append(f"{row + 1}행: 저장 실패.")
        if not ok_any and not err_msgs:
            QMessageBox.information(
                self,
                "안내",
                "저장할 데이터가 없습니다. 이름이 비어 있는 신규 행은 저장되지 않습니다.",
            )
            return
        if err_msgs:
            QMessageBox.warning(self, "저장", "\n".join(err_msgs[:5]))
        elif ok_any:
            QMessageBox.information(self, "완료", "저장했습니다.")
        self._reload_list()
        if hasattr(self, "cmb_hist_emp"):
            self._fill_emp_combo(self.cmb_hist_emp, with_all=True)

    def _selected_pt_ids(self):
        ids = []
        for mi in self.tbl_list.selectionModel().selectedRows():
            r = mi.row()
            if 0 <= r < len(self._list_row_pt_ids):
                pid = self._list_row_pt_ids[r]
                if pid is not None:
                    ids.append(pid)
        return ids

    def _row_dict_by_pt_id(self, pt_id):
        for r in self.db.list_workforce_partners(self.farm_cd, None) or []:
            if int(r.get("pt_id") or 0) == int(pt_id or 0):
                return r
        return None

    def _deactivate_partner(self):
        ids = self._selected_pt_ids()
        if not ids:
            QMessageBox.information(self, "안내", "사용중지할 행을 선택하세요.")
            return
        rows = []
        for pid in ids:
            row = self._row_dict_by_pt_id(pid)
            if row:
                rows.append((pid, row))
        if not rows:
            return
        if len(rows) == 1:
            msg = f"'{rows[0][1].get('pt_nm')}' 사용을 중지할까요?"
        else:
            msg = f"선택 {len(rows)}명의 사용을 중지할까요?"
        if QMessageBox.question(self, "확인", msg) != QMessageBox.StandardButton.Yes:
            return
        ok_all = True
        for pid, row in rows:
            ok = self.db.update_workforce_partner(
                self.farm_cd,
                pid,
                row.get("pt_nm"),
                row.get("worker_type_cd") or "EMP",
                row.get("pt_tel") or "",
                row.get("base_price") or 0,
                "N",
                bank_cd=(str(row.get("bank_cd") or "").strip() or None),
                account_no=str(row.get("account_no") or ""),
            )
            ok_all = ok_all and ok
        if ok_all:
            self._reload_list()
            if hasattr(self, "cmb_hist_emp"):
                self._fill_emp_combo(self.cmb_hist_emp, with_all=True)
        else:
            QMessageBox.warning(self, "오류", "일부 행 처리에 실패했습니다. 목록을 확인해 주세요.")
            self._reload_list()

    def _tab_history(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        fl = QHBoxLayout()
        self.dt_hist_from = QDateEdit()
        self.dt_hist_to = QDateEdit()
        for dx in (self.dt_hist_from, self.dt_hist_to):
            dx.setCalendarPopup(True)
            dx.setStyleSheet(MainStyles.COMBO)
            dx.setDisplayFormat("yyyy-MM-dd")
        self.dt_hist_from.setDate(QDate.currentDate().addMonths(-1))
        self.dt_hist_to.setDate(QDate.currentDate())
        self.cmb_hist_emp = QComboBox()
        self.cmb_hist_emp.setStyleSheet(MainStyles.COMBO)
        self._fill_emp_combo(self.cmb_hist_emp, with_all=True)
        self.cmb_hist_work = QComboBox()
        self.cmb_hist_work.setStyleSheet(MainStyles.COMBO)
        self.cmb_hist_work.setMinimumWidth(160)
        btn = QPushButton("조회")
        btn.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        btn.clicked.connect(self._reload_history)
        fl.addWidget(QLabel("기간", styleSheet=MainStyles.LBL_SUB))
        fl.addWidget(self.dt_hist_from)
        fl.addWidget(QLabel("~", styleSheet=MainStyles.LBL_SUB))
        fl.addWidget(self.dt_hist_to)
        fl.addWidget(QLabel("작업명", styleSheet=MainStyles.LBL_SUB))
        fl.addWidget(self.cmb_hist_work, 1)
        fl.addWidget(QLabel("작업자", styleSheet=MainStyles.LBL_SUB))
        fl.addWidget(self.cmb_hist_emp, 1)
        fl.addWidget(btn)
        vl.addLayout(fl)
        self.tbl_hist = QTableWidget(0, 7)
        self.tbl_hist.setHorizontalHeaderLabels(
            ["작업명", "작업일", "작업자", "투입MH", "작업장소", "인건비", "지급"]
        )
        self.tbl_hist.setStyleSheet(MainStyles.TABLE + MainStyles.TABLE_CONTENT_10)
        self.tbl_hist.verticalHeader().setVisible(False)
        hh = self.tbl_hist.horizontalHeader()
        for c in range(7):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        vl.addWidget(self.tbl_hist, 1)
        self._reload_history()
        return w

    def _fill_emp_combo(self, cb: QComboBox, with_all: bool):
        cb.blockSignals(True)
        cb.clear()
        if with_all:
            cb.addItem("전체", "")
        for r in self.db.list_workforce_partners(self.farm_cd, None) or []:
            cb.addItem(str(r.get("pt_nm") or ""), str(r.get("pt_id") or ""))
        cb.blockSignals(False)

    def _reload_history(self):
        sk = _ymd_key(self.dt_hist_from.date())
        ek = _ymd_key(self.dt_hist_to.date())
        prev_work = ""
        if hasattr(self, "cmb_hist_work"):
            prev_work = str(self.cmb_hist_work.currentData() or self.cmb_hist_work.currentText() or "")
        names = self.db.list_workforce_work_names_in_period(self.farm_cd, sk, ek) or []
        self.cmb_hist_work.blockSignals(True)
        self.cmb_hist_work.clear()
        self.cmb_hist_work.addItem("전체", "")
        for nm in names:
            self.cmb_hist_work.addItem(nm, nm)
        restore_idx = 0
        if prev_work:
            ix = self.cmb_hist_work.findData(prev_work)
            if ix >= 0:
                restore_idx = ix
        self.cmb_hist_work.setCurrentIndex(restore_idx)
        self.cmb_hist_work.blockSignals(False)

        emp = self.cmb_hist_emp.currentData()
        emp_arg = str(emp).strip() if emp else None
        work_arg = str(self.cmb_hist_work.currentData() or "").strip() or None
        rows = self.db.list_workforce_assignments(self.farm_cd, sk, ek, emp_arg, work_mid_nm=work_arg) or []
        self.tbl_hist.setRowCount(0)
        for r in rows:
            i = self.tbl_hist.rowCount()
            self.tbl_hist.insertRow(i)
            ps = "지급" if str(r.get("pay_status") or "").upper() == "Y" else "미지급"
            try:
                mh = float(r.get("man_hour") or 0)
            except (TypeError, ValueError):
                mh = 0.0
            mh_txt = str(int(mh)) if mh == int(mh) else f"{mh:.2f}".rstrip("0").rstrip(".")
            vals = [
                str(r.get("work_mid_nm") or ""),
                str(r.get("work_dt") or ""),
                str(r.get("pt_nm") or ""),
                mh_txt,
                str(r.get("site_nm") or ""),
                f"{int(float(r.get('daily_wage') or 0)):,}",
                ps,
            ]
            for c, t in enumerate(vals):
                it = QTableWidgetItem(t)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c in (3, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_hist.setItem(i, c, it)

    def _tab_pay(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        fl = QHBoxLayout()
        self.dt_pay_from = QDateEdit()
        self.dt_pay_to = QDateEdit()
        for dx in (self.dt_pay_from, self.dt_pay_to):
            dx.setCalendarPopup(True)
            dx.setStyleSheet(MainStyles.COMBO)
            dx.setDisplayFormat("yyyy-MM-dd")
        self.dt_pay_from.setDate(QDate.currentDate().addMonths(-1))
        self.dt_pay_to.setDate(QDate.currentDate())
        self.chk_unpaid_only = QCheckBox("미지급만 보기")
        self.chk_unpaid_only.setStyleSheet(MainStyles.CHK_CAPTION)
        self.chk_unpaid_only.toggled.connect(self._reload_pay)
        btn = QPushButton("조회")
        btn.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        btn.clicked.connect(self._reload_pay)
        fl.addWidget(QLabel("기간", styleSheet=MainStyles.LBL_SUB))
        fl.addWidget(self.dt_pay_from)
        fl.addWidget(QLabel("~", styleSheet=MainStyles.LBL_SUB))
        fl.addWidget(self.dt_pay_to)
        fl.addWidget(self.chk_unpaid_only)
        fl.addStretch()
        fl.addWidget(btn)
        vl.addLayout(fl)
        self.tbl_pay = QTableWidget(0, 4)
        self.tbl_pay.setHorizontalHeaderLabels(
            ["작업자", "총 인건비", "미지급 건수", "미지급 금액"]
        )
        self.tbl_pay.setStyleSheet(MainStyles.TABLE + MainStyles.TABLE_CONTENT_10)
        self.tbl_pay.verticalHeader().setVisible(False)
        hh = self.tbl_pay.horizontalHeader()
        for c in range(4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        vl.addWidget(self.tbl_pay, 1)
        self._reload_pay()
        return w

    def _reload_pay(self):
        sk = _ymd_key(self.dt_pay_from.date())
        ek = _ymd_key(self.dt_pay_to.date())
        unpaid_only = self.chk_unpaid_only.isChecked()
        rows = self.db.list_workforce_pay_summary(self.farm_cd, sk, ek, unpaid_only) or []
        self.tbl_pay.setRowCount(0)
        for r in rows:
            i = self.tbl_pay.rowCount()
            self.tbl_pay.insertRow(i)
            tot = int(float(r.get("total_labor") or 0))
            uc = int(float(r.get("unpaid_cnt") or 0))
            ua = int(float(r.get("unpaid_amt") or 0))
            vals = [str(r.get("pt_nm") or ""), f"{tot:,}", f"{uc:,}", f"{ua:,}"]
            for c, t in enumerate(vals):
                it = QTableWidgetItem(t)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c >= 1:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_pay.setItem(i, c, it)
