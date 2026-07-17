# -*- coding: utf-8 -*-
"""관찰 추적 사진 좌·우 비교 다이얼로그."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.observation_media import load_thumb_pixmap, resolve_media_path
from ui.styles import MainStyles

ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 0.2
PREVIEW_BASE = 360


class _SidePane(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self._source = QPixmap()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        head = QLabel(title)
        head.setStyleSheet("font-weight: bold; font-size: 10px; border: none;")
        lay.addWidget(head)

        self.cb_obs = QComboBox()
        self.cb_obs.setStyleSheet(MainStyles.COMBO)
        lay.addWidget(self.cb_obs)

        self.cb_photo = QComboBox()
        self.cb_photo.setStyleSheet(MainStyles.COMBO)
        lay.addWidget(self.cb_photo)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setWordWrap(True)
        self.lbl_meta.setStyleSheet("color: #4A5568; font-size: 10px; border: none;")
        lay.addWidget(self.lbl_meta)

        self.lbl_img = QLabel("사진 없음")
        self.lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img.setMinimumSize(PREVIEW_BASE, PREVIEW_BASE)
        self.lbl_img.setStyleSheet(
            "background: #FFFFFF; border: 1px solid #EAE7E2; border-radius: 8px;"
        )
        lay.addWidget(self.lbl_img, 1)

        zrow = QHBoxLayout()
        self.btn_zin = QPushButton("확대")
        self.btn_zout = QPushButton("축소")
        for b in (self.btn_zin, self.btn_zout):
            b.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_zin.clicked.connect(self._zoom_in)
        self.btn_zout.clicked.connect(self._zoom_out)
        zrow.addWidget(self.btn_zin)
        zrow.addWidget(self.btn_zout)
        zrow.addStretch(1)
        lay.addLayout(zrow)

    def set_source_pixmap(self, pm: QPixmap | None):
        self._source = pm if pm is not None and not pm.isNull() else QPixmap()
        self._scale = 1.0
        self._refresh()

    def _zoom_in(self):
        self._scale = min(ZOOM_MAX, self._scale + ZOOM_STEP)
        self._refresh()

    def _zoom_out(self):
        self._scale = max(ZOOM_MIN, self._scale - ZOOM_STEP)
        self._refresh()

    def _refresh(self):
        if self._source.isNull():
            self.lbl_img.setPixmap(QPixmap())
            self.lbl_img.setText("사진 없음")
            return
        self.lbl_img.setText("")
        w = max(80, int(PREVIEW_BASE * self._scale))
        h = max(80, int(PREVIEW_BASE * self._scale))
        scaled = self._source.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.lbl_img.setPixmap(scaled)


class PhotoCompareDialog(QDialog):
    """track 항목 2건 이상일 때 좌·우 관찰/사진 비교."""

    def __init__(self, parent, db, farm_cd: str, track_rows: list[dict]):
        super().__init__(parent)
        self.db = db
        self.farm_cd = farm_cd
        self.track_rows = list(track_rows or [])
        self.setWindowTitle("사진 비교")
        self.setMinimumSize(900, 560)
        self._build_ui()
        self._fill_obs_combos()
        if len(self.track_rows) >= 2:
            self.left.cb_obs.setCurrentIndex(0)
            self.right.cb_obs.setCurrentIndex(1)
        self._reload_side(self.left)
        self._reload_side(self.right)

    def _build_ui(self):
        root = QVBoxLayout(self)
        row = QHBoxLayout()
        self.left = _SidePane("왼쪽")
        self.right = _SidePane("오른쪽")
        row.addWidget(self.left, 1)
        row.addWidget(self.right, 1)
        root.addLayout(row, 1)

        self.left.cb_obs.currentIndexChanged.connect(
            lambda: self._reload_side(self.left)
        )
        self.right.cb_obs.currentIndexChanged.connect(
            lambda: self._reload_side(self.right)
        )
        self.left.cb_photo.currentIndexChanged.connect(
            lambda: self._show_photo(self.left)
        )
        self.right.cb_photo.currentIndexChanged.connect(
            lambda: self._show_photo(self.right)
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("닫기")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def _fill_obs_combos(self):
        for pane in (self.left, self.right):
            pane.cb_obs.blockSignals(True)
            pane.cb_obs.clear()
            for r in self.track_rows:
                oid = str(r.get("obs_id") or "")
                dt = str(r.get("obs_dt") or "")
                sev = str(r.get("severity_nm") or r.get("severity_cd") or "")
                label = f"{dt} · {sev}".strip(" ·")
                pane.cb_obs.addItem(label or oid, oid)
            pane.cb_obs.blockSignals(False)

    def _track_by_id(self, obs_id: str) -> dict:
        for r in self.track_rows:
            if str(r.get("obs_id") or "") == obs_id:
                return r
        return {}

    def _reload_side(self, pane: _SidePane):
        obs_id = pane.cb_obs.currentData()
        rec = self._track_by_id(obs_id) if obs_id else {}
        sev = str(rec.get("severity_nm") or rec.get("severity_cd") or "-")
        memo = str(rec.get("obs_content") or "")[:120]
        pane.lbl_meta.setText(f"심각도: {sev}\n{memo}")

        pane.cb_photo.blockSignals(True)
        pane.cb_photo.clear()
        photos = []
        if self.db and self.farm_cd and obs_id:
            photos = self.db.list_observation_photos(self.farm_cd, obs_id) or []
        for p in photos:
            pid = str(p.get("photo_id") or "")
            nm = str(p.get("original_nm") or pid)
            pane.cb_photo.addItem(nm, pid)
            # stash paths on item via userData as tuple — keep map
        pane._photo_map = {str(p.get("photo_id") or ""): p for p in photos}
        pane.cb_photo.blockSignals(False)
        self._show_photo(pane)

    def _show_photo(self, pane: _SidePane):
        pid = pane.cb_photo.currentData()
        pmap = getattr(pane, "_photo_map", {}) or {}
        p = pmap.get(str(pid or ""), {})
        if not p:
            pane.set_source_pixmap(None)
            return
        abs_path = resolve_media_path(p.get("file_path") or "")
        pm = QPixmap()
        if abs_path is not None and abs_path.is_file():
            pm = QPixmap(str(abs_path))
        if pm.isNull():
            pm = load_thumb_pixmap(p.get("thumb_path") or "", 800) or QPixmap()
        pane.set_source_pixmap(pm if not pm.isNull() else None)
