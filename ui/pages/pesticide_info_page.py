# -*- coding: utf-8 -*-
"""농약 정보 조회: 농약별·사전 관리(PSIS 동기화). AI 추천·진행 UI는 농약 사용관리 탭(`PesticideAIRecommendPanel`)에서 동작."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.pesticide_manager import PesticideManager
from ui.styles import MainStyles

# PSIS 농장 작물 동기화: 메인 스레드와 DB 분리(작업 스레드 전용 SQLite 연결).
class _PsisFarmSyncWorker(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, user_id: str, farm_cd: str):
        super().__init__()
        self._user_id = user_id
        self._farm_cd = farm_cd

    @pyqtSlot()
    def run(self) -> None:
        db = None
        try:
            from core.db_manager import DBManager
            from core.pesticide_manager import PesticideManager

            db = DBManager()
            mgr = PesticideManager(db)
            summary = mgr.bulk_upsert_pesticide_info_from_psis_for_farm(
                self._user_id,
                self._farm_cd,
                progress_callback=lambda d: self.progress.emit(dict(d)),
            )
            self.finished.emit(summary)
        except ValueError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


class _PsisBrandSyncWorker(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, user_id: str, farm_cd: str, brand_keyword: str):
        super().__init__()
        self._user_id = user_id
        self._farm_cd = farm_cd
        self._brand_keyword = brand_keyword

    @pyqtSlot()
    def run(self) -> None:
        db = None
        try:
            from core.db_manager import DBManager
            from core.pesticide_manager import PesticideManager

            db = DBManager()
            mgr = PesticideManager(db)
            summary = mgr.bulk_upsert_pesticide_info_from_psis_by_brand(
                self._user_id,
                self._farm_cd,
                self._brand_keyword,
                progress_callback=lambda d: self.progress.emit(dict(d)),
            )
            self.finished.emit(summary)
        except ValueError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


# 탭(농약 사전 관리) — 동기화 버튼 옆 ? 툴팁
_M3_TAB_HELP_TOOLTIP = (
    "저장된 농약사전을 조회합니다.\n\n"
    "「농장 작물 기준 동기화」는 이 농장에 등록된 활성 재배작물만 기준으로 "
    "PSIS 목록(SVC01)·상세(SVC02)를 반영합니다.\n"
    "(전국 전체 대상 아님 · UPSERT · info_id 유지)"
)


def _lbl_field(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setStyleSheet(MainStyles.LBL_GRID_HEADER)
    return lb


def _plain(s: object) -> str:
    t = str(s) if s is not None else ""
    return t.strip()


class PesticideInfoPage(QWidget):
    ROLE_INFO_ID = Qt.ItemDataRole.UserRole + 1

    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        self.farm_cd = str(session.get("farm_cd") or "")
        self.user_id = str(session.get("user_id") or "")
        self.mgr = PesticideManager(db_manager)
        self._year = date.today().year
        self._m3_psis_thread: QThread | None = None
        self._m3_psis_worker: QObject | None = None
        self._m3_psis_sync_busy = False
        self._m3_sync_mode = "farm"
        self._m3_sync_brand_keyword = ""
        self.tabs = QTabWidget()
        self._build_ui()
        self.setStyleSheet(MainStyles.MAIN_BG)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("📚 농약 사전")
        title.setStyleSheet(MainStyles.LBL_TITLE)
        root.addWidget(title)
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)
        self.tabs.addTab(self._build_tab_by_pesticide(), "농약별 조회")
        self.tabs.addTab(self._build_tab_info_manage(), "농약 사전 관리")
        self.tabs.currentChanged.connect(lambda _i: self.refresh_data())
        root.addWidget(self.tabs, stretch=1)
        self._reload_t1_category_combo()
        QTimer.singleShot(0, self.refresh_data)

    def refresh_data(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._run_tab1_query()
        elif idx == 1:
            self._reload_m3_catalog_table()

    def refresh_all(self):
        self._reload_t1_category_combo()
        self._run_tab1_query()
        self._reload_m3_catalog_table()

    def _reload_t1_category_combo(self) -> None:
        prev = self.t1_cat.currentData()
        self.t1_cat.blockSignals(True)
        try:
            self.t1_cat.clear()
            self.t1_cat.addItem("(전체)", "")
            for nm in self.mgr.list_distinct_pesticide_category_nms():
                self.t1_cat.addItem(nm, nm)
            idx = self.t1_cat.findData(prev)
            if idx >= 0:
                self.t1_cat.setCurrentIndex(idx)
            else:
                self.t1_cat.setCurrentIndex(0)
        finally:
            self.t1_cat.blockSignals(False)

    # --- 탭1 ---
    def _build_tab_by_pesticide(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        filt = QGroupBox("검색")
        filt.setStyleSheet(MainStyles.GROUP_BOX)
        fg = QGridLayout(filt)
        fg.setContentsMargins(16, 16, 16, 12)
        self.t1_nm = QLineEdit()
        self.t1_nm.setPlaceholderText("농약명(부분 일치)")
        self.t1_nm.setStyleSheet(MainStyles.INPUT_CENTER)
        self.t1_cat = QComboBox()
        self.t1_cat.setStyleSheet(MainStyles.COMBO)
        self.t1_cat.setMinimumWidth(140)
        self.t1_stock = QCheckBox("재고 있는 것만 보기")
        self.t1_stock.setStyleSheet("color: #333;")
        btn = QPushButton("조회")
        btn.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn.clicked.connect(self._run_tab1_query)
        fg.addWidget(_lbl_field("농약명"), 0, 0)
        fg.addWidget(self.t1_nm, 0, 1)
        fg.addWidget(_lbl_field("구분"), 0, 2)
        fg.addWidget(self.t1_cat, 0, 3)
        fg.addWidget(self.t1_stock, 0, 4)
        fg.addWidget(btn, 0, 5)
        lay.addWidget(filt)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.t1_list = QTableWidget()
        self.t1_list.setColumnCount(3)
        self.t1_list.setHorizontalHeaderLabels(["농약명", "구분", "현재재고(낱개)"])
        self.t1_list.setStyleSheet(MainStyles.TABLE)
        self.t1_list.setShowGrid(True)
        self.t1_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t1_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.t1_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t1_list.verticalHeader().setVisible(False)
        hh = self.t1_list.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.t1_list.itemSelectionChanged.connect(self._on_tab1_select)
        split.addWidget(self.t1_list)

        detail = QFrame()
        detail.setStyleSheet(MainStyles.CARD)
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 12, 12, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        self.t1_form = QGridLayout(inner)
        self.t1_form.setContentsMargins(4, 4, 4, 4)
        self.t1_form.setHorizontalSpacing(12)
        self.t1_form.setVerticalSpacing(8)
        r = 0
        self._t1_labels: dict[str, QLabel] = {}
        for key, cap in [
            ("pesticide_nm", "농약명"),
            ("maker_nm", "제조사"),
            ("ingredient_nm", "성분명"),
            ("category_nm", "구분"),
            ("brand_nm", "상표명"),
            ("spec_nm", "규격"),
            ("dilution_guide", "희석·사용기준"),
            ("usage_note", "사용설명"),
            ("caution_note", "주의사항"),
            ("stock_qty", "현재재고(낱개)"),
            ("last_use_dt", "최근 사용일(확정)"),
            ("annual_use_qty", f"연간 사용량({self._year}년, 확정)"),
            ("annual_use_cnt", f"연간 사용횟수({self._year}년, 확정)"),
        ]:
            self.t1_form.addWidget(_lbl_field(cap), r, 0)
            lb = QLabel("")
            lb.setWordWrap(True)
            lb.setStyleSheet("color: #333;")
            self.t1_form.addWidget(lb, r, 1)
            self._t1_labels[key] = lb
            r += 1
        scroll.setWidget(inner)
        dv.addWidget(scroll)
        split.addWidget(detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, stretch=1)
        return w

    def _run_tab1_query(self):
        self.mgr.try_auto_link_unlinked_items_to_info(
            self.farm_cd, self.user_id or "system"
        )
        cat = self.t1_cat.currentData()
        if cat is None:
            cat = ""
        rows = self.mgr.get_pesticide_info_summary_list(
            self.farm_cd,
            nm_sub=self.t1_nm.text(),
            category_nm=str(cat).strip(),
            stock_only=self.t1_stock.isChecked(),
        )
        self.t1_list.setRowCount(0)
        for rec in rows:
            r = self.t1_list.rowCount()
            self.t1_list.insertRow(r)
            iid = int(rec["info_id"])
            self.t1_list.setItem(r, 0, QTableWidgetItem(_plain(rec.get("pesticide_nm"))))
            self.t1_list.setItem(r, 1, QTableWidgetItem(_plain(rec.get("category_nm"))))
            it = QTableWidgetItem(str(int(rec.get("stock_qty") or 0)))
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.t1_list.setItem(r, 2, it)
            self.t1_list.item(r, 0).setData(self.ROLE_INFO_ID, iid)
        self._clear_tab1_detail()
        if self.t1_list.rowCount() > 0:
            self.t1_list.selectRow(0)

    def _clear_tab1_detail(self):
        for k, lb in self._t1_labels.items():
            lb.setText("—")

    def _on_tab1_select(self):
        r = self.t1_list.currentRow()
        if r < 0:
            self._clear_tab1_detail()
            return
        it = self.t1_list.item(r, 0)
        if not it:
            return
        iid = it.data(self.ROLE_INFO_ID)
        if iid is None:
            return
        d = self.mgr.get_pesticide_info_detail(int(iid), self.farm_cd, self._year)
        if not d:
            self._clear_tab1_detail()
            return
        self._t1_labels["pesticide_nm"].setText(_plain(d.get("pesticide_nm")) or "—")
        self._t1_labels["maker_nm"].setText(_plain(d.get("maker_nm")) or "—")
        self._t1_labels["ingredient_nm"].setText(_plain(d.get("ingredient_nm")) or "—")
        self._t1_labels["category_nm"].setText(_plain(d.get("category_nm")) or "—")
        b1 = _plain(d.get("brand_nm"))
        s1 = _plain(d.get("spec_nm"))
        if not b1 and s1:
            b1, s1 = s1, ""
        self._t1_labels["brand_nm"].setText(b1 or "—")
        self._t1_labels["spec_nm"].setText(s1 or "—")
        self._t1_labels["dilution_guide"].setText(_plain(d.get("dilution_guide")) or "—")
        self._t1_labels["usage_note"].setText(_plain(d.get("usage_note")) or "—")
        self._t1_labels["caution_note"].setText(_plain(d.get("caution_note")) or "—")
        self._t1_labels["stock_qty"].setText(str(int(d.get("stock_qty") or 0)))
        lu = _plain(d.get("last_use_dt"))
        self._t1_labels["last_use_dt"].setText(lu if lu else "—")
        self._t1_labels["annual_use_qty"].setText(str(int(d.get("annual_use_qty") or 0)))
        cnt = int(d.get("annual_use_cnt") or 0)
        self._t1_labels["annual_use_cnt"].setText(f"{cnt}회")

    # --- 농약 사전 관리 (PSIS 동기화 + 간단 조회 전용) ---
    def _build_tab_info_manage(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        row_top = QHBoxLayout()
        self.m3_b_psis_sync = QPushButton("농장 작물 기준 동기화")
        self.m3_b_psis_sync.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.m3_b_psis_sync.clicked.connect(self._on_m3_psis_bulk_sync)
        row_top.addWidget(self.m3_b_psis_sync)
        self.m3_b_psis_brand_add = QPushButton("상표명 해당농약사전 추가")
        self.m3_b_psis_brand_add.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.m3_b_psis_brand_add.clicked.connect(self._on_m3_psis_brand_sync)
        row_top.addWidget(self.m3_b_psis_brand_add)
        m3_help = QToolButton()
        m3_help.setText("?")
        m3_help.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        m3_help.setToolTip(_M3_TAB_HELP_TOOLTIP)
        m3_help.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        m3_help.setAutoRaise(True)
        m3_help.setCursor(Qt.CursorShape.WhatsThisCursor)
        m3_help.setFixedSize(30, 30)
        m3_help.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        row_top.addWidget(m3_help)
        row_top.addStretch()
        lay.addLayout(row_top)

        sync_fr = QFrame()
        sync_fr.setStyleSheet(MainStyles.CARD)
        sv = QVBoxLayout(sync_fr)
        sv.setContentsMargins(10, 8, 10, 8)
        sv.setSpacing(6)
        self.m3_sync_status_lbl = QLabel(
            "재동기화 대기 중입니다. 실행 시 목록 수집·상세 반영 진행률이 표시됩니다."
        )
        self.m3_sync_status_lbl.setWordWrap(True)
        self.m3_sync_status_lbl.setStyleSheet(MainStyles.LBL_SUB)
        sv.addWidget(self.m3_sync_status_lbl)
        self.m3_sync_progress = QProgressBar()
        self.m3_sync_progress.setRange(0, 100)
        self.m3_sync_progress.setValue(0)
        self.m3_sync_progress.setTextVisible(True)
        sv.addWidget(self.m3_sync_progress)
        self.m3_sync_summary_lbl = QLabel("신규 0건 · 갱신 0건 · 실패 0건")
        self.m3_sync_summary_lbl.setStyleSheet("color: #333;")
        sv.addWidget(self.m3_sync_summary_lbl)
        lay.addWidget(sync_fr)

        search = QGroupBox("조회 조건")
        search.setStyleSheet(MainStyles.GROUP_BOX)
        sg = QGridLayout(search)
        sg.setContentsMargins(12, 12, 12, 10)
        sg.setHorizontalSpacing(10)
        sg.setVerticalSpacing(6)
        self.m3_s_brand = QLineEdit()
        self.m3_s_brand.setPlaceholderText("상표명 (부분 일치)")
        self.m3_s_brand.setStyleSheet(MainStyles.INPUT_CENTER)
        self.m3_s_pest = QLineEdit()
        self.m3_s_pest.setPlaceholderText("대상병해충명 — PSIS 매핑 기준 (부분 일치)")
        self.m3_s_pest.setStyleSheet(MainStyles.INPUT_CENTER)
        self.m3_s_maker = QLineEdit()
        self.m3_s_maker.setPlaceholderText("상호명 (부분 일치)")
        self.m3_s_maker.setStyleSheet(MainStyles.INPUT_CENTER)
        sg.addWidget(_lbl_field("상표명"), 0, 0)
        sg.addWidget(self.m3_s_brand, 0, 1)
        sg.addWidget(_lbl_field("대상병해충"), 0, 2)
        sg.addWidget(self.m3_s_pest, 0, 3)
        sg.addWidget(_lbl_field("상호명"), 1, 0)
        sg.addWidget(self.m3_s_maker, 1, 1)
        btn_s = QPushButton("조회")
        btn_s.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_s.clicked.connect(self._reload_m3_catalog_table)
        btn_r = QPushButton("초기화")
        btn_r.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_r.clicked.connect(self._m3_reset_catalog_search)
        sh = QHBoxLayout()
        sh.addWidget(btn_s)
        sh.addWidget(btn_r)
        sh.addStretch()
        sg.addLayout(sh, 1, 2, 1, 2)
        lay.addWidget(search)

        self.m3_catalog_empty = QLabel("")
        self.m3_catalog_empty.setWordWrap(True)
        self.m3_catalog_empty.setStyleSheet(MainStyles.LBL_SUB)
        lay.addWidget(self.m3_catalog_empty)

        self.m3_catalog = QTableWidget()
        self.m3_catalog.setColumnCount(8)
        self.m3_catalog.setHorizontalHeaderLabels(
            [
                "상표명",
                "대상병해충명(PSIS)",
                "상호명",
                "작물명",
                "품목명(성분)",
                "희석배수",
                "사용시기",
                "사용가능횟수",
            ]
        )
        self.m3_catalog.setStyleSheet(MainStyles.TABLE)
        self.m3_catalog.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.m3_catalog.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.m3_catalog.verticalHeader().setVisible(False)
        self.m3_catalog.setWordWrap(False)
        mh = self.m3_catalog.horizontalHeader()
        for c in range(8):
            mh.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        mh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        mh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        mh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        mh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        mh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        mh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        mh.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        mh.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.m3_catalog, stretch=1)
        return w

    def _m3_reset_catalog_search(self) -> None:
        self.m3_s_brand.clear()
        self.m3_s_pest.clear()
        self.m3_s_maker.clear()
        self._reload_m3_catalog_table()

    def _m3_reset_psis_sync_progress_idle(self) -> None:
        self.m3_sync_status_lbl.setText(
            "재동기화 대기 중입니다. 실행 시 목록 수집·상세 반영 진행률이 표시됩니다."
        )
        self.m3_sync_progress.setRange(0, 100)
        self.m3_sync_progress.setValue(0)
        self.m3_sync_summary_lbl.setText("신규 0건 · 갱신 0건 · 실패 0건")

    def _m3_apply_psis_sync_progress(self, info: dict) -> None:
        phase = str(info.get("phase") or "")
        if phase == "listing":
            fc = int(info.get("farm_crop_count") or 0)
            if self._m3_sync_mode == "brand":
                kw = self._m3_sync_brand_keyword
                self.m3_sync_status_lbl.setText(
                    f"상표명 '{kw}' 기준 — PSIS 등록 목록 수집 중… (페이지 순회)"
                )
            else:
                self.m3_sync_status_lbl.setText(
                    f"활성 작물 {fc}종 기준 — PSIS 등록 목록 수집 중… (작물·페이지 순회)"
                )
            self.m3_sync_progress.setRange(0, 0)
            self.m3_sync_summary_lbl.setText("신규 0건 · 갱신 0건 · 실패 0건")
        elif phase == "detail":
            tk = int(info.get("total_keys") or 0)
            proc = int(info.get("processed_count") or 0)
            fc = int(info.get("farm_crop_count") or 0)
            self.m3_sync_progress.setRange(0, 0 if tk <= 0 else tk)
            if tk > 0:
                self.m3_sync_progress.setValue(min(proc, tk))
            else:
                self.m3_sync_progress.setRange(0, 1)
                self.m3_sync_progress.setValue(0)
            self.m3_sync_status_lbl.setText(
                f"활성 작물 {fc}종 기준 — 전체 {tk:,}건 중 {proc:,}건 처리 중 (상세 조회·저장)"
            )
            ic = int(info.get("inserted_count") or 0)
            uc = int(info.get("updated_count") or 0)
            fc = int(info.get("failed_count") or 0)
            self.m3_sync_summary_lbl.setText(
                f"신규 {ic:,}건 · 갱신 {uc:,}건 · 실패 {fc:,}건"
            )
        elif phase == "done":
            tk = int(info.get("total_keys") or 0)
            fc = int(info.get("farm_crop_count") or 0)
            self.m3_sync_progress.setRange(0, max(1, tk))
            self.m3_sync_progress.setValue(tk)
            self.m3_sync_status_lbl.setText(
                f"활성 작물 {fc}종 기준 처리 완료 (등록 키 총 {tk:,}건)"
            )
            ic = int(info.get("inserted_count") or 0)
            uc = int(info.get("updated_count") or 0)
            fc = int(info.get("failed_count") or 0)
            self.m3_sync_summary_lbl.setText(
                f"신규 {ic:,}건 · 갱신 {uc:,}건 · 실패 {fc:,}건"
            )

    def _reload_m3_catalog_table(self) -> None:
        rows = self.mgr.get_pesticide_info_catalog_display_rows(
            brand_sub=self.m3_s_brand.text(),
            pest_sub=self.m3_s_pest.text(),
            maker_sub=self.m3_s_maker.text(),
        )
        t = self.m3_catalog
        t.setRowCount(0)
        for rec in rows:
            r = t.rowCount()
            t.insertRow(r)
            pest_txt = _plain(rec.get("pest_psis_agg"))
            t.setItem(r, 0, QTableWidgetItem(_plain(rec.get("brand_nm"))))
            t.setItem(r, 1, QTableWidgetItem(pest_txt))
            t.setItem(r, 2, QTableWidgetItem(_plain(rec.get("maker_nm"))))
            t.setItem(r, 3, QTableWidgetItem(_plain(rec.get("crop_nm"))))
            t.setItem(r, 4, QTableWidgetItem(_plain(rec.get("ingredient_nm"))))
            t.setItem(r, 5, QTableWidgetItem(_plain(rec.get("dilution_guide"))))
            t.setItem(r, 6, QTableWidgetItem(_plain(rec.get("usage_timing_disp"))))
            t.setItem(r, 7, QTableWidgetItem(_plain(rec.get("usage_limit_disp"))))
        has_any = len(rows) > 0
        if has_any:
            self.m3_catalog_empty.clear()
        else:
            self.m3_catalog_empty.setText(
                "조건에 맞는 농약이 없습니다. 검색어를 바꾸거나 「초기화」로 전체 목록을 다시 불러오세요."
            )

    def _m3_clear_psis_thread(self) -> None:
        self._m3_psis_thread = None
        self._m3_psis_worker = None

    def _on_m3_psis_worker_failed(self, msg: str) -> None:
        self._m3_psis_sync_busy = False
        self.m3_b_psis_sync.setEnabled(True)
        self.m3_b_psis_brand_add.setEnabled(True)
        title = (
            "상표명 해당농약사전 추가"
            if self._m3_sync_mode == "brand"
            else "농장 작물 기준 동기화"
        )
        QMessageBox.warning(self, title, _plain(msg) or "동기화에 실패했습니다.")
        self._m3_reset_psis_sync_progress_idle()
        self._m3_sync_mode = "farm"
        self._m3_sync_brand_keyword = ""
        self._m3_clear_psis_thread()

    def _on_m3_psis_worker_finished(self, summary: dict) -> None:
        self._m3_psis_sync_busy = False
        self.m3_b_psis_sync.setEnabled(True)
        self.m3_b_psis_brand_add.setEnabled(True)
        self.refresh_all()
        tk = int(summary.get("total_keys") or 0)
        sc = int(summary.get("success_count") or summary.get("ok_rows") or 0)
        ic = int(summary.get("inserted_count") or 0)
        uc = int(summary.get("updated_count") or 0)
        fc = int(summary.get("failed_count") or 0)
        sd = int(summary.get("skipped_duplicate_count") or 0)
        lc = int(summary.get("list_api_calls") or 0)
        fcc = int(summary.get("farm_crop_count") or summary.get("crops_used") or 0)
        if self._m3_sync_mode == "brand":
            kw = self._m3_sync_brand_keyword
            msg = (
                f"상표명 '{kw}' 기준 — 등록 키 {tk:,}건 중 {sc:,}건 반영 "
                f"(신규 {ic:,}건 / 갱신 {uc:,}건), 실패 {fc:,}건\n"
                f"(목록 단계 중복 키 스킵 {sd:,}건 · SVC01 호출 {lc:,}회)"
            )
            title = "상표명 해당농약사전 추가"
        else:
            msg = (
                f"활성 작물 {fcc}종 기준 — 등록 키 {tk:,}건 중 {sc:,}건 반영 "
                f"(신규 {ic:,}건 / 갱신 {uc:,}건), 실패 {fc:,}건\n"
                f"(목록 단계 중복 키 스킵 {sd:,}건 · SVC01 호출 {lc:,}회)"
            )
            title = "농장 작물 기준 동기화"
        note = _plain(summary.get("sync_scope_note"))
        if note:
            msg = f"{msg}\n\n※ {note}"
        QMessageBox.information(self, title, msg)
        self._m3_reset_psis_sync_progress_idle()
        self._m3_sync_mode = "farm"
        self._m3_sync_brand_keyword = ""
        self._m3_clear_psis_thread()

    def _on_m3_psis_bulk_sync(self) -> None:
        if self._m3_psis_sync_busy:
            QMessageBox.information(
                self, "동기화", "이미 동기화가 진행 중입니다. 완료될 때까지 기다려 주세요."
            )
            return
        if not _plain(self.farm_cd):
            QMessageBox.warning(self, "동기화", "로그인 농장 정보가 없습니다.")
            return
        crops = self.mgr.farm_psis_sync_crop_names(self.farm_cd)
        if not crops:
            QMessageBox.warning(
                self,
                "동기화",
                "농장에 등록된 활성 작물이 없어 PSIS 동기화를 시작할 수 없습니다.",
            )
            return
        if (
            QMessageBox.question(
                self,
                "농장 작물 기준 동기화",
                "농장에 등록된 활성 재배작물만 기준으로 PSIS 농약사전을 동기화합니다.\n"
                "(전국 전체 농약이 아닙니다.)\n"
                "시간이 걸릴 수 있습니다. 진행할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        self._m3_psis_sync_busy = True
        self._m3_sync_mode = "farm"
        self._m3_sync_brand_keyword = ""
        self.m3_b_psis_sync.setEnabled(False)
        self.m3_b_psis_brand_add.setEnabled(False)
        th = QThread()
        worker = _PsisFarmSyncWorker(self.user_id, self.farm_cd)
        worker.moveToThread(th)
        self._m3_psis_thread = th
        self._m3_psis_worker = worker

        th.started.connect(worker.run)
        worker.progress.connect(self._m3_apply_psis_sync_progress)
        worker.finished.connect(self._on_m3_psis_worker_finished)
        worker.failed.connect(self._on_m3_psis_worker_failed)
        worker.finished.connect(th.quit)
        worker.failed.connect(th.quit)
        th.finished.connect(worker.deleteLater)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_m3_psis_brand_sync(self) -> None:
        if self._m3_psis_sync_busy:
            QMessageBox.information(
                self, "동기화", "이미 동기화가 진행 중입니다. 완료될 때까지 기다려 주세요."
            )
            return
        brand_kw, ok = QInputDialog.getText(
            self,
            "상표명 해당농약사전 추가",
            "조회할 상표명을 입력하세요.",
            text=self.m3_s_brand.text().strip(),
        )
        if not ok:
            return
        brand_kw = _plain(brand_kw)
        if not brand_kw:
            QMessageBox.warning(self, "상표명 해당농약사전 추가", "상표명을 입력해 주세요.")
            return
        if (
            QMessageBox.question(
                self,
                "상표명 해당농약사전 추가",
                f"상표명 '{brand_kw}' 기준으로 PSIS를 조회해 농약사전에 반영합니다.\n진행할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        self._m3_psis_sync_busy = True
        self._m3_sync_mode = "brand"
        self._m3_sync_brand_keyword = brand_kw
        self.m3_b_psis_sync.setEnabled(False)
        self.m3_b_psis_brand_add.setEnabled(False)
        th = QThread()
        worker = _PsisBrandSyncWorker(self.user_id, self.farm_cd, brand_kw)
        worker.moveToThread(th)
        self._m3_psis_thread = th
        self._m3_psis_worker = worker

        th.started.connect(worker.run)
        worker.progress.connect(self._m3_apply_psis_sync_progress)
        worker.finished.connect(self._on_m3_psis_worker_finished)
        worker.failed.connect(self._on_m3_psis_worker_failed)
        worker.finished.connect(th.quit)
        worker.failed.connect(th.quit)
        th.finished.connect(worker.deleteLater)
        th.finished.connect(th.deleteLater)
        th.start()
