# -*- coding: utf-8 -*-
"""재고 품목 ↔ 농약정보(info_id) 연결 다이얼로그."""

from __future__ import annotations

import sys
from pathlib import Path

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.pesticide_manager import PesticideManager
from ui.styles import MainStyles


class PesticideItemLinkDialog(QDialog):
    ROLE_ITEM_ID = Qt.ItemDataRole.UserRole + 1

    def __init__(self, db_manager, session, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.farm_cd = str(session.get("farm_cd") or "")
        self.user_id = str(session.get("user_id") or "")
        self.mgr = PesticideManager(db_manager)
        self._rows: list = []
        self.setWindowTitle("재고 품목 ↔ 농약정보 연결")
        self.setMinimumSize(720, 480)
        self._build_ui()
        self._reload_table()
        self._reload_info_combo()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        t = QLabel("재고 품목에 농약정보를 연결하면 조회 화면에서 재고·사용이력이 집계됩니다.")
        t.setStyleSheet("color: #444;")
        lay.addWidget(t)

        filt = QGroupBox("품목 검색")
        filt.setStyleSheet(MainStyles.GROUP_BOX)
        fg = QHBoxLayout(filt)
        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("품목명 포함 필터")
        self.ed_filter.setStyleSheet(MainStyles.INPUT_CENTER)
        self.ed_filter.textChanged.connect(self._apply_filter)
        fg.addWidget(self.ed_filter)
        lay.addWidget(filt)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["품목명", "규격", "현재고(낱개)", "연결 농약정보"])
        self.tbl.setStyleSheet(MainStyles.TABLE)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.verticalHeader().setVisible(False)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tbl)

        linkb = QGroupBox("연결할 농약정보")
        linkb.setStyleSheet(MainStyles.GROUP_BOX)
        lg = QGridLayout(linkb)
        self.cb_info = QComboBox()
        self.cb_info.setStyleSheet(MainStyles.COMBO)
        self.cb_info.setMinimumWidth(320)
        lg.addWidget(QLabel("농약정보"), 0, 0)
        lg.addWidget(self.cb_info, 0, 1)
        hbtn = QHBoxLayout()
        b_link = QPushButton("선택 품목에 연결")
        b_link.setStyleSheet(MainStyles.BTN_PRIMARY)
        b_link.clicked.connect(self._on_link)
        b_un = QPushButton("선택 품목 연결 해제")
        b_un.setStyleSheet(MainStyles.BTN_SECONDARY)
        b_un.clicked.connect(self._on_unlink)
        hbtn.addWidget(b_link)
        hbtn.addWidget(b_un)
        hbtn.addStretch()
        lg.addLayout(hbtn, 1, 0, 1, 2)
        lay.addWidget(linkb)

        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close)

    def _reload_info_combo(self):
        self.cb_info.clear()
        self.cb_info.addItem("(선택)", None)
        for rec in self.mgr.get_pesticide_info_list():
            iid = int(rec["info_id"])
            nm = str(rec.get("pesticide_nm") or "").strip() or f"#{iid}"
            self.cb_info.addItem(nm, iid)

    def _reload_table(self):
        self._rows = self.mgr.get_all_pesticide_items(self.farm_cd)
        self._fill_table_rows(self._rows)

    def _fill_table_rows(self, rows: list):
        self.tbl.setRowCount(0)
        for rec in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            iid = int(rec["item_id"])
            nm = str(rec.get("item_nm") or "")
            sp = str(rec.get("spec_nm") or "")
            qv = int(rec.get("qty_piece") or 0)
            inf_id = rec.get("info_id")
            inf_nm = str(rec.get("info_pesticide_nm") or "").strip()
            if inf_id and not inf_nm:
                inf_nm = f"id:{inf_id}"
            link_txt = inf_nm if inf_id else "—"
            self.tbl.setItem(r, 0, QTableWidgetItem(nm))
            self.tbl.setItem(r, 1, QTableWidgetItem(sp))
            itq = QTableWidgetItem(str(qv))
            itq.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl.setItem(r, 2, itq)
            self.tbl.setItem(r, 3, QTableWidgetItem(link_txt))
            self.tbl.item(r, 0).setData(self.ROLE_ITEM_ID, iid)
        self._apply_filter()

    def _apply_filter(self):
        q = self.ed_filter.text().strip().lower()
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if not it:
                continue
            match = not q or q in (it.text() or "").lower()
            self.tbl.setRowHidden(r, not match)

    def _selected_item_ids(self) -> list[int]:
        out: list[int] = []
        for idx in self.tbl.selectionModel().selectedRows():
            r = idx.row()
            if self.tbl.isRowHidden(r):
                continue
            it = self.tbl.item(r, 0)
            if it:
                v = it.data(self.ROLE_ITEM_ID)
                if v is not None:
                    out.append(int(v))
        return out

    def _on_link(self):
        ids = self._selected_item_ids()
        if not ids:
            QMessageBox.information(self, "안내", "품목을 선택하세요.")
            return
        info_id = self.cb_info.currentData()
        if info_id is None:
            QMessageBox.warning(self, "입력", "연결할 농약정보를 선택하세요.")
            return
        if not self.mgr.update_item_info_link(self.farm_cd, ids, int(info_id), self.user_id):
            QMessageBox.warning(self, "실패", "연결 저장에 실패했습니다.")
            return
        self._reload_table()
        QMessageBox.information(self, "완료", f"{len(ids)}건 연결했습니다.")

    def _on_unlink(self):
        ids = self._selected_item_ids()
        if not ids:
            QMessageBox.information(self, "안내", "품목을 선택하세요.")
            return
        if (
            QMessageBox.question(
                self,
                "연결 해제",
                f"선택 {len(ids)}건의 농약정보 연결을 해제할까요?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if not self.mgr.update_item_info_link(self.farm_cd, ids, None, self.user_id):
            QMessageBox.warning(self, "실패", "저장에 실패했습니다.")
            return
        self._reload_table()
        QMessageBox.information(self, "완료", "연결을 해제했습니다.")
