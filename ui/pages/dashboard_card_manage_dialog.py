# -*- coding: utf-8 -*-
"""숨김 카드 복원 · 기본 배치 복원"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox,
)
from PyQt6.QtCore import Qt

from ui.styles import MainStyles


class DashboardCardManageDialog(QDialog):
    def __init__(self, parent, visible_titles: dict, hidden_ids: list, meta_titles: dict):
        super().__init__(parent)
        self.setWindowTitle("카드 관리")
        self.resize(420, 480)
        self.setStyleSheet(MainStyles.MAIN_BG)
        self._hidden_ids = list(hidden_ids)
        self._meta = meta_titles
        lay = QVBoxLayout(self)

        g1 = QGroupBox("표시 중인 카드")
        g1.setStyleSheet(MainStyles.GROUP_BOX)
        l1 = QVBoxLayout(g1)
        self.list_visible = QListWidget()
        for cid, title in visible_titles.items():
            self.list_visible.addItem(QListWidgetItem(title))
        l1.addWidget(self.list_visible)
        lay.addWidget(g1)

        g2 = QGroupBox("숨겨진 카드")
        g2.setStyleSheet(MainStyles.GROUP_BOX)
        l2 = QVBoxLayout(g2)
        self.list_hidden = QListWidget()
        for cid in hidden_ids:
            self.list_hidden.addItem(QListWidgetItem(meta_titles.get(cid, cid)))
            self.list_hidden.item(self.list_hidden.count() - 1).setData(Qt.ItemDataRole.UserRole, cid)
        l2.addWidget(self.list_hidden)
        btn_restore = QPushButton("다시 표시")
        btn_restore.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_restore.clicked.connect(self._on_restore)
        l2.addWidget(btn_restore)
        lay.addWidget(g2)

        row = QHBoxLayout()
        btn_default = QPushButton("기본 배치로 복원")
        btn_default.setStyleSheet(MainStyles.BTN_DANGER)
        btn_default.clicked.connect(self._accept_default)
        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_close.clicked.connect(self.reject)
        row.addWidget(btn_default)
        row.addStretch()
        row.addWidget(btn_close)
        lay.addLayout(row)

        self._restore_id = None
        self._want_default = False

    def _on_restore(self):
        it = self.list_hidden.currentItem()
        if not it:
            return
        cid = it.data(Qt.ItemDataRole.UserRole)
        self._restore_id = cid
        self.accept()

    def _accept_default(self):
        self._want_default = True
        self.accept()

    def restore_card_id(self):
        return self._restore_id

    def wants_default_layout(self):
        return self._want_default
