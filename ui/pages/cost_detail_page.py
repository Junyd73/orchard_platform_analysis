# -*- coding: utf-8 -*-
"""
작업(work_dt) 기준 비용 상세 분석 — 인건비·경비가 어떤 작업에서 발생했는지 표로 제공.
"""
import calendar

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.code_manager import CodeManager
from ui.pages.dashboard_detail_base import DashboardDetailBase
from ui.styles import MainStyles


def _row_dict(row):
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {}


def _labor_worker_display(worker_type_cd: str) -> str:
    """OWNER/FAMILY → 자가노동, 그 외 코드는 짧은 한글 표기."""
    c = str(worker_type_cd or "EMP").strip().upper() or "EMP"
    if c in ("OWNER", "FAMILY"):
        return "자가노동"
    mapping = {"EMP": "고용", "TEMP": "일용"}
    return mapping.get(c, c)


def _pay_status_label(raw) -> str:
    """pay_status Y/N → 화면용 문구."""
    s = str(raw or "").strip().upper()
    if s == "Y":
        return "지급"
    if s == "N":
        return "미지급"
    return str(raw or "").strip() or "미지급"


def _style_detail_pay_cell(cell: QTableWidgetItem, display_text: str):
    """지급 열: 가운데 정렬, 미지급만 색 구분."""
    cell.setTextAlignment(
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
    )
    if display_text == "미지급":
        cell.setForeground(QBrush(QColor(MainStyles.DASH_UNPAID_AMOUNT_COLOR)))
    elif display_text == "지급":
        cell.setForeground(QBrush(QColor("#2D5A27")))


class CostDetailPage(DashboardDetailBase):
    """대시보드 비용 카드와 연결되는 작업 단위 비용 분석."""

    COL_WORK_ID = Qt.ItemDataRole.UserRole + 1
    @staticmethod
    def _unpaid_amt_positive_only(rows):
        """미지급 라인 중 금액 0원은 목록·집계에서 제외."""
        out = []
        for r in rows or []:
            if int(float(r.get("amt") or 0)) > 0:
                out.append(r)
        return out

    @staticmethod
    def _fmt_unpaid_rich(cnt: int, amt: int) -> str:
        c = MainStyles.DASH_UNPAID_AMOUNT_COLOR
        return (
            f'<span style="color:#64748B;font-weight:600;">{cnt}건</span>'
            f' <span style="color:#CBD5E0;">/</span> '
            f'<span style="color:{c};font-weight:bold;">{amt:,}원</span>'
        )

    @staticmethod
    def _work_dt_to_yyyy_mm(work_dt) -> str:
        """작업일 표시를 YYYY-MM으로."""
        s = str(work_dt or "").strip()
        if not s:
            return ""
        if len(s) >= 7 and s[4] == "-":
            return s[:7]
        digits = "".join(ch for ch in s if ch.isdigit())
        if len(digits) >= 6:
            return f"{digits[:4]}-{digits[4:6]}"
        return s

    @staticmethod
    def _work_dt_to_yyyy_mm_dd(work_dt) -> str:
        """미지급 설명용 작업일 YYYY-MM-DD."""
        s = str(work_dt or "").strip()
        if not s:
            return ""
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        digits = "".join(ch for ch in s if ch.isdigit())
        if len(digits) >= 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
        if len(digits) >= 6:
            return f"{digits[:4]}-{digits[4:6]}"
        return s

    def __init__(self, db_manager, session, parent=None):
        super().__init__(
            "labor",
            "작업 기준 비용 상세",
            "💳",
            db_manager,
            session,
            parent,
            sidebar_nav_title=None,
            content_split=(6, 4),
        )
        self.code_mgr = CodeManager(self.db, self.farm_cd)
        self._period_month = QDate.currentDate()
        self._main_rows = []
        self.sidebar.setMinimumWidth(260)
        self._create_filter_widgets()
        self._build_summary_area()
        self._build_main_body()
        self._build_sidebar()
        self._reload_all()

    @staticmethod
    def _iter_year_month_choices():
        """필터용 연속 월 목록 (YYYY-MM 콤보). 약 6년치."""
        today = QDate.currentDate()
        cur = QDate(today.year() - 4, 1, 1)
        end = QDate(today.year() + 1, 12, 1)
        while cur <= end:
            yield cur.year(), cur.month()
            cur = cur.addMonths(1)

    def _selected_period_qdate(self) -> QDate:
        """기간(월) 콤보 선택 → 해당 월 1일."""
        data = self.cmb_period.currentData()
        if data is None:
            d = QDate.currentDate()
            return QDate(d.year(), d.month(), 1)
        y, mo = data
        return QDate(int(y), int(mo), 1)

    def _month_range(self, d: QDate):
        """선택 월의 조회 구간 (현재 월이면 오늘까지, MTD)."""
        y, m = d.year(), d.month()
        start = QDate(y, m, 1)
        last = QDate(y, m, calendar.monthrange(y, m)[1])
        today = QDate.currentDate()
        if y == today.year() and m == today.month():
            end = min(last, today)
        else:
            end = last
        return start, end

    def _ymd_keys(self, start: QDate, end: QDate):
        return start.toString("yyyyMMdd"), end.toString("yyyyMMdd")

    @staticmethod
    def _style_filter_input(w):
        """필터 입력: 앱 공통 COMBO, 높이 통일."""
        w.setStyleSheet(MainStyles.COMBO)
        w.setMinimumHeight(32)

    @staticmethod
    def _table_style_10():
        return MainStyles.TABLE + MainStyles.TABLE_CONTENT_10

    @staticmethod
    def _table_style_main_work():
        """작업 리스트: 10pt + 행 hover 톤."""
        return (
            MainStyles.TABLE
            + MainStyles.TABLE_CONTENT_10
            + MainStyles.TABLE_COST_MAIN_HOVER
        )

    @staticmethod
    def _filter_field_inline(caption: str, editor, min_editor_width: int):
        """필터 한 줄: 라벨 + 입력 가로 배치."""
        box = QFrame()
        box.setStyleSheet("background: transparent; border: none;")
        hl = QHBoxLayout(box)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        lab = QLabel(caption)
        lab.setStyleSheet(MainStyles.DASH_FILTER_LABEL)
        lab.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        editor.setMinimumWidth(min_editor_width)
        hl.addWidget(lab, 0, Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(editor, 0, Qt.AlignmentFlag.AlignVCenter)
        return box

    def _fill_period_combo(self):
        """캘린더 없이 YYYY-MM 목록만 선택."""
        self.cmb_period.blockSignals(True)
        self.cmb_period.clear()
        for y, mo in self._iter_year_month_choices():
            self.cmb_period.addItem(f"{y:04d}-{mo:02d}", (y, mo))
        want = (self._period_month.year(), self._period_month.month())
        sel = -1
        for i in range(self.cmb_period.count()):
            if self.cmb_period.itemData(i) == want:
                sel = i
                break
        if sel < 0:
            self.cmb_period.insertItem(0, f"{want[0]:04d}-{want[1]:02d}", want)
            sel = 0
        self.cmb_period.setCurrentIndex(sel)
        self.cmb_period.blockSignals(False)

    def _create_filter_widgets(self):
        self.cmb_period = QComboBox()
        self._style_filter_input(self.cmb_period)
        self.cmb_period.setMinimumWidth(118)
        self.cmb_period.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._fill_period_combo()
        self.cmb_period.currentIndexChanged.connect(self._on_period_combo_changed)

        self.cmb_site = QComboBox()
        self._style_filter_input(self.cmb_site)
        self.cmb_site.setMinimumWidth(148)
        self.cmb_site.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._fill_site_combo()

        self.cmb_mid = QComboBox()
        self._style_filter_input(self.cmb_mid)
        self.cmb_mid.setMinimumWidth(148)
        self.cmb_mid.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._fill_mid_combo()

        self.cmb_site.currentIndexChanged.connect(self._reload_all)
        self.cmb_mid.currentIndexChanged.connect(self._reload_all)

    def _build_summary_area(self):
        """요약 카드 위: 필터 한 줄(스크롤 밖 summary 영역)."""
        for i in reversed(range(self.summary_layout.count())):
            w = self.summary_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        filter_fr = QFrame()
        filter_fr.setStyleSheet(MainStyles.CARD)
        fl = QHBoxLayout(filter_fr)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(14)
        filter_fr.setMinimumHeight(50)
        fl.addWidget(self._filter_field_inline("기간(월)", self.cmb_period, 118), 0)
        fl.addWidget(self._filter_field_inline("작업장소", self.cmb_site, 148), 0)
        fl.addWidget(self._filter_field_inline("작업종류", self.cmb_mid, 148), 0)
        fl.addStretch(1)
        self.summary_layout.addWidget(filter_fr)

    def _build_kpi_card(self):
        """필터 아래 요약 KPI(스크롤 영역 상단)."""
        outer = QFrame()
        outer.setStyleSheet(MainStyles.CARD)
        lay = QVBoxLayout(outer)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        self.lbl_period_title = QLabel("")
        self.lbl_period_title.setStyleSheet(MainStyles.DASH_CARD_TITLE)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        def _mk_card(title_key: str, value_style: str):
            fr = QFrame()
            fr.setStyleSheet("background: transparent; border: none;")
            fl = QVBoxLayout(fr)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(2)
            t = QLabel(title_key)
            t.setStyleSheet(MainStyles.DASH_LABEL)
            v = QLabel("—")
            v.setStyleSheet(value_style)
            s = QLabel("")
            s.setStyleSheet(MainStyles.DASH_BODY_TEXT)
            s.setVisible(False)
            fl.addWidget(t)
            fl.addWidget(v)
            fl.addWidget(s)
            return fr, v, s

        c0, self.val_total, self.sub_total = _mk_card("총비용", MainStyles.DASH_KPI_VALUE_PRIMARY)
        c1, self.val_labor, self.sub_labor = _mk_card("인건비", MainStyles.DASH_SUMMARY_VALUE)
        c2, self.val_expense, self.sub_expense = _mk_card("경비", MainStyles.DASH_SUMMARY_VALUE)
        c3, self.val_unpaid, self.sub_unpaid = _mk_card("미지급", MainStyles.DASH_KPI_VALUE)
        self.val_unpaid.setTextFormat(Qt.TextFormat.RichText)

        grid.addWidget(c0, 0, 0)
        grid.addWidget(c1, 0, 1)
        grid.addWidget(c2, 0, 2)
        grid.addWidget(c3, 0, 3)

        lay.addWidget(self.lbl_period_title)
        lay.addLayout(grid)
        return outer

    def _build_main_body(self):
        self.main_layout.addWidget(self._build_kpi_card())

        list_panel = QFrame()
        list_panel.setStyleSheet(MainStyles.CARD)
        list_lay = QVBoxLayout(list_panel)
        list_lay.setContentsMargins(12, 10, 12, 10)
        list_lay.setSpacing(8)

        cap = QLabel("작업 기준 비용 리스트")
        cap.setStyleSheet(MainStyles.DASH_SUBCARD_TITLE)
        list_lay.addWidget(cap)

        self.tbl_work = QTableWidget(0, 6)
        self.tbl_work.setHorizontalHeaderLabels(
            ["작업일", "작업명", "작업장소", "인건비", "경비", "합계"]
        )
        self.tbl_work.setStyleSheet(self._table_style_main_work())
        self.tbl_work.setMinimumHeight(200)
        self.tbl_work.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_work.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tbl_work.verticalHeader().setVisible(False)
        hh = self.tbl_work.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_work.itemSelectionChanged.connect(self._on_work_selected)
        list_lay.addWidget(self.tbl_work)
        self.main_layout.addWidget(list_panel)

        detail_fr = QFrame()
        detail_fr.setStyleSheet(MainStyles.CARD)
        dl = QVBoxLayout(detail_fr)
        dl.setContentsMargins(8, 6, 8, 6)
        dl.setSpacing(4)

        self.lbl_detail_title = QLabel("행을 선택하면 인건비·경비 상세가 표시됩니다.")
        self.lbl_detail_title.setStyleSheet(MainStyles.DASH_BODY_TEXT)
        dl.addWidget(self.lbl_detail_title)

        split = QHBoxLayout()
        split.setSpacing(12)

        lab_l = QLabel("인건비 상세")
        lab_l.setStyleSheet(MainStyles.DASH_SUBCARD_TITLE)
        self.tbl_labor = QTableWidget(0, 4)
        self.tbl_labor.setHorizontalHeaderLabels(["작업자", "구분", "인건비", "지급"])
        self.tbl_labor.setStyleSheet(self._table_style_10())
        self.tbl_labor.verticalHeader().setVisible(False)
        self.tbl_labor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        lab_e = QLabel("경비 상세")
        lab_e.setStyleSheet(MainStyles.DASH_SUBCARD_TITLE)
        self.tbl_expense = QTableWidget(0, 3)
        self.tbl_expense.setHorizontalHeaderLabels(["품목", "금액", "지급"])
        self.tbl_expense.setStyleSheet(self._table_style_10())
        self.tbl_expense.verticalHeader().setVisible(False)
        self.tbl_expense.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        vl = QVBoxLayout()
        vl.setSpacing(4)
        vl.addWidget(lab_l)
        vl.addWidget(self.tbl_labor)
        ve = QVBoxLayout()
        ve.setSpacing(4)
        ve.addWidget(lab_e)
        ve.addWidget(self.tbl_expense)
        split.addLayout(vl, 1)
        split.addLayout(ve, 1)
        dl.addLayout(split)

        self.tbl_labor.setMinimumHeight(140)
        self.tbl_expense.setMinimumHeight(140)
        self.main_layout.addWidget(detail_fr)
        self.main_layout.addStretch()

    def _fill_site_combo(self):
        self.cmb_site.blockSignals(True)
        self.cmb_site.clear()
        self.cmb_site.addItem("전체", "")
        for r in self.code_mgr.get_farm_sites() or []:
            d = _row_dict(r)
            sid = d.get("site_id")
            snm = d.get("site_nm") or str(sid or "")
            self.cmb_site.addItem(snm, "" if sid is None else str(sid).strip())
        self.cmb_site.blockSignals(False)

    def _fill_mid_combo(self):
        self.cmb_mid.blockSignals(True)
        self.cmb_mid.clear()
        self.cmb_mid.addItem("전체", "")
        try:
            mains = self.code_mgr.get_main_work_codes() or []
            for main in mains:
                md = _row_dict(main)
                pcd = md.get("code_cd")
                if not pcd:
                    continue
                for sub in self.code_mgr.get_sub_work_codes(pcd) or []:
                    sd = _row_dict(sub)
                    ccd = sd.get("code_cd")
                    cnm = sd.get("code_nm") or ccd
                    if ccd:
                        self.cmb_mid.addItem(cnm, ccd)
        except Exception:
            pass
        self.cmb_mid.blockSignals(False)

    def _filter_loc(self):
        d = self.cmb_site.currentData()
        s = "" if d is None else str(d).strip()
        return s or None

    def _filter_mid(self):
        d = self.cmb_mid.currentData()
        s = "" if d is None else str(d).strip()
        return s or None

    def _on_period_combo_changed(self):
        self._period_month = self._selected_period_qdate()
        self._reload_all()

    def _reload_all(self):
        qd = self._selected_period_qdate()
        start, end = self._month_range(qd)
        sk, ek = self._ymd_keys(start, end)
        loc = self._filter_loc()
        mid = self._filter_mid()

        y = qd.year()
        mo = qd.month()
        self.lbl_period_title.setText(f"{y:04d}-{mo:02d} 비용 상세")

        rows = []
        if hasattr(self.db, "get_cost_detail_by_work"):
            rows = self.db.get_cost_detail_by_work(
                self.farm_cd, sk, ek, work_loc_id=loc, work_mid_cd=mid
            ) or []
        self._main_rows = rows
        self._fill_work_table(rows)

        unpaid = []
        unpaid_year = []
        if hasattr(self.db, "get_cost_unpaid_list"):
            unpaid = self.db.get_cost_unpaid_list(
                self.farm_cd, sk, ek, limit=400, work_loc_id=loc, work_mid_cd=mid
            ) or []
            ysk = f"{y:04d}0101"
            today = QDate.currentDate()
            year_end = QDate(y, 12, 31)
            if year_end > today:
                year_end = today
            yek = year_end.toString("yyyyMMdd")
            unpaid_year = self.db.get_cost_unpaid_list(
                self.farm_cd, ysk, yek, limit=600, work_loc_id=loc, work_mid_cd=mid
            ) or []
        unpaid = self._unpaid_amt_positive_only(unpaid)
        unpaid_year = self._unpaid_amt_positive_only(unpaid_year)
        self._fill_unpaid_sidebar(unpaid, unpaid_year, y, mo)

        labor_sum = sum(int(float(r.get("labor_sum") or 0)) for r in rows)
        exp_sum = sum(int(float(r.get("expense_sum") or 0)) for r in rows)
        tot_sum = labor_sum + exp_sum
        u_cnt = len(unpaid)
        u_amt = sum(int(float(x.get("amt") or 0)) for x in unpaid)

        self.val_total.setText(f"{tot_sum:,}원")
        self.val_labor.setText(f"{labor_sum:,}원")
        self.val_expense.setText(f"{exp_sum:,}원")
        self.val_unpaid.setText(self._fmt_unpaid_rich(u_cnt, u_amt))

        self.tbl_labor.setRowCount(0)
        self.tbl_expense.setRowCount(0)
        self.lbl_detail_title.setText("행을 선택하면 인건비·경비 상세가 표시됩니다.")

    def _fill_work_table(self, rows):
        self.tbl_work.setRowCount(0)
        for r in rows:
            row = self.tbl_work.rowCount()
            self.tbl_work.insertRow(row)
            wd = str(r.get("work_dt") or "")
            wnm = str(r.get("work_mid_nm") or r.get("work_mid_cd") or "")
            site = str(r.get("site_nm") or "")
            lb = int(float(r.get("labor_sum") or 0))
            ex = int(float(r.get("expense_sum") or 0))
            tot = lb + ex
            wid = r.get("work_id")

            it0 = QTableWidgetItem(wd)
            it0.setData(self.COL_WORK_ID, wid)
            it1 = QTableWidgetItem(wnm)
            it2 = QTableWidgetItem(site)
            it3 = QTableWidgetItem(f"{lb:,}")
            it4 = QTableWidgetItem(f"{ex:,}")
            it5 = QTableWidgetItem(f"{tot:,}")
            items = [it0, it1, it2, it3, it4, it5]
            for c, it in enumerate(items):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c >= 3:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_work.setItem(row, c, it)

    def _on_work_selected(self):
        sel = self.tbl_work.selectedItems()
        if not sel:
            return
        ridx = self.tbl_work.currentRow()
        if ridx < 0:
            return
        it = self.tbl_work.item(ridx, 0)
        if not it:
            return
        work_id = it.data(self.COL_WORK_ID)
        if work_id is None:
            return
        self._load_work_details(work_id)

    def _load_work_details(self, work_id):
        self.lbl_detail_title.setText(f"작업 ID: {work_id}")
        self.tbl_labor.setRowCount(0)
        self.tbl_expense.setRowCount(0)

        res_rows = []
        if hasattr(self.db, "get_work_resource_detail"):
            res_rows = self.db.get_work_resource_detail(work_id) or []
        else:
            res_rows = self.db.get_work_resources(work_id) or []

        for rec in res_rows:
            d = _row_dict(rec)
            rr = self.tbl_labor.rowCount()
            self.tbl_labor.insertRow(rr)
            emp = str(d.get("emp_nm") or "").strip() or str(d.get("emp_cd") or "")
            type_lbl = _labor_worker_display(str(d.get("worker_type_cd") or "EMP"))
            wage = int(float(d.get("daily_wage") or 0))
            ps = _pay_status_label(d.get("pay_status"))
            for c, txt in enumerate([emp, type_lbl, f"{wage:,}", ps]):
                cell = QTableWidgetItem(txt)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                elif c == 3:
                    _style_detail_pay_cell(cell, ps)
                self.tbl_labor.setItem(rr, c, cell)

        exp_rows = []
        if hasattr(self.db, "get_work_expense_detail"):
            exp_rows = self.db.get_work_expense_detail(work_id) or []
        else:
            exp_rows = self.db.get_work_expenses(work_id) or []

        for rec in exp_rows:
            d = _row_dict(rec)
            rr = self.tbl_expense.rowCount()
            self.tbl_expense.insertRow(rr)
            nm = str(d.get("item_nm") or "")
            amt = int(float(d.get("total_amt") or 0))
            ps = _pay_status_label(d.get("pay_status"))
            for c, txt in enumerate([nm, f"{amt:,}", ps]):
                cell = QTableWidgetItem(txt)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                elif c == 2:
                    _style_detail_pay_cell(cell, ps)
                self.tbl_expense.setItem(rr, c, cell)

    def _configure_unpaid_table(self, tbl: QTableWidget):
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["구분", "금액", "설명"])
        tbl.setStyleSheet(self._table_style_10())
        tbl.setWordWrap(True)
        tbl.verticalHeader().setDefaultSectionSize(28)
        tbl.verticalHeader().setVisible(False)
        uh = tbl.horizontalHeader()
        uh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        uh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        uh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _fill_unpaid_rows_into(self, tbl: QTableWidget, rows):
        tbl.setRowCount(0)
        for r in rows or []:
            rr = tbl.rowCount()
            tbl.insertRow(rr)
            kind = str(r.get("kind") or "")
            amt = int(float(r.get("amt") or 0))
            desc = str(r.get("descr") or "")
            wd = str(r.get("work_dt") or "")
            wd_ymd = self._work_dt_to_yyyy_mm_dd(wd)
            note = f"{wd_ymd} · {desc}".strip(" ·")
            for c, txt in enumerate([kind, f"{amt:,}", note]):
                cell = QTableWidgetItem(txt)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                tbl.setItem(rr, c, cell)
        tbl.resizeRowsToContents()

    @staticmethod
    def _fmt_unpaid_section_one_line(title_plain: str, cnt: int, amt: int) -> str:
        """구역 제목 + 건수/금액 한 줄(RichText)."""
        return (
            f'<span style="font-weight:bold;color:#444;">{title_plain}</span>&nbsp;&nbsp;'
            + CostDetailPage._fmt_unpaid_rich(cnt, amt)
        )

    def _fill_unpaid_sidebar(self, rows_period, rows_year, y: int, mo: int):
        self._fill_unpaid_rows_into(self.tbl_unpaid, rows_period)
        self._fill_unpaid_rows_into(self.tbl_unpaid_year, rows_year)

        cp = len(rows_period or [])
        ap = sum(int(float(x.get("amt") or 0)) for x in (rows_period or []))
        self.lbl_unpaid_headline.setText(
            self._fmt_unpaid_section_one_line(f"{y}년 {mo:02d}월 미지급", cp, ap)
        )

        cy = len(rows_year or [])
        ay = sum(int(float(x.get("amt") or 0)) for x in (rows_year or []))
        self.lbl_unpaid_year_headline.setText(
            self._fmt_unpaid_section_one_line(f"{y}년 미지급", cy, ay)
        )

    def _build_sidebar(self):
        self.sidebar_layout.setSpacing(6)
        self.sidebar_layout.setContentsMargins(10, 8, 10, 10)

        title = QLabel("미지급 현황")
        title.setStyleSheet(MainStyles.DASH_CARD_TITLE)
        self.sidebar_layout.addWidget(title)

        td = QDate.currentDate()
        self.lbl_unpaid_headline = QLabel()
        self.lbl_unpaid_headline.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_unpaid_headline.setStyleSheet(MainStyles.DASH_KPI_VALUE)
        self.lbl_unpaid_headline.setWordWrap(True)
        self.lbl_unpaid_headline.setText(
            self._fmt_unpaid_section_one_line(
                f"{td.year()}년 {td.month():02d}월 미지급", 0, 0
            )
        )
        self.sidebar_layout.addWidget(self.lbl_unpaid_headline)

        self.tbl_unpaid = QTableWidget(0, 3)
        self._configure_unpaid_table(self.tbl_unpaid)
        self.tbl_unpaid.setMinimumHeight(200)
        self.sidebar_layout.addWidget(self.tbl_unpaid, 1)

        self.lbl_unpaid_year_headline = QLabel()
        self.lbl_unpaid_year_headline.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_unpaid_year_headline.setStyleSheet(MainStyles.DASH_KPI_VALUE)
        self.lbl_unpaid_year_headline.setWordWrap(True)
        self.lbl_unpaid_year_headline.setText(
            self._fmt_unpaid_section_one_line(f"{td.year()}년 미지급", 0, 0)
        )
        self.sidebar_layout.addWidget(self.lbl_unpaid_year_headline)

        self.tbl_unpaid_year = QTableWidget(0, 3)
        self._configure_unpaid_table(self.tbl_unpaid_year)
        self.tbl_unpaid_year.setMinimumHeight(180)
        self.sidebar_layout.addWidget(self.tbl_unpaid_year, 1)
