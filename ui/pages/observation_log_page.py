# -*- coding: utf-8 -*-
"""관찰일지: 등록·조회·수정·논리삭제 + Stage2(사진·열매·추적·대시보드)."""

from __future__ import annotations

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDoubleValidator, QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.code_manager import CodeManager
from core.db_manager import DBManager
from core.observation_media import load_thumb_pixmap
from ui.styles import MainStyles
from ui.widgets.observation.fruit_growth_chart import FruitGrowthChart
from ui.widgets.observation.photo_compare_dialog import PhotoCompareDialog
from ui.widgets.observation.photo_panel import PhotoPanel
from ui.widgets.observation.ai_analysis_panel import AiAnalysisPanel

OBS_LIST_LIMIT = 500
OBS_SUMMARY_LIST_LIMIT = 1000
OBS_COL_OBS_ID = Qt.ItemDataRole.UserRole
OBS_COL_SEVERITY = Qt.ItemDataRole.UserRole + 1
TRACK_ROLE_OBS_ID = Qt.ItemDataRole.UserRole
OBS_SESSION_MISSING_MSG = (
    "로그인 또는 농장 세션 정보를 확인할 수 없습니다.\n"
    "다시 로그인한 후 이용해 주세요."
)
# 목록 화면이 작업창 폭을 넘지 않도록 최소폭을 제한
OBS_FILTER_COMBO_MIN_W = 80
OBS_FILTER_DATE_MAX_W = 128
OBS_FILTER_KEYWORD_MIN_W = 120
OBS_SUMMARY_CARD_MIN_W = 72
OBS_TABLE_MIN_SECTION_W = 48

# 대상별 권장 위치 입력 (1단계는 강제하지 않음)
_TARGET_FIELD_HINT = {
    "OB010100": ("zone", "row", "tree"),
    "OB010200": ("zone", "row", "tree", "branch", "sample"),
    "OB010300": ("zone", "row", "tree"),
    "OB010400": ("zone", "row", "tree"),
    "OB010500": ("zone",),
    "OB010600": ("zone",),
}

_FRUIT_METRIC_KEYS = (
    ("width_mm", "가로(폭)", "mm"),
    ("height_mm", "세로(길이)", "mm"),
    ("circumference_mm", "둘레", "mm"),
    ("estimated_weight_g", "추정 무게", "g"),
)

_SUMMARY_KEYS = (
    ("in_progress", "관찰 중"),
    ("followup_today", "오늘 재관찰"),
    ("followup_overdue", "재관찰 지연"),
    ("caution_danger", "주의·위험"),
    ("month_done", "이번 달 완료"),
)


def _combo_fill(cb: QComboBox, rows, blank_label="전체"):
    cb.clear()
    cb.addItem(blank_label, None)
    for r in rows or []:
        if hasattr(r, "keys"):
            cd = r["code_cd"] if "code_cd" in r.keys() else r[0]
            nm = r["code_nm"] if "code_nm" in r.keys() else r[1]
        else:
            cd, nm = r[0], r[1]
        cb.addItem(str(nm), str(cd))


def _set_combo_data(cb: QComboBox, data):
    if data is None or data == "":
        cb.setCurrentIndex(0)
        return
    idx = cb.findData(data)
    if idx < 0:
        cb.setCurrentIndex(0)
    else:
        cb.setCurrentIndex(idx)


def _yn_checked(val) -> bool:
    return str(val or "").strip().upper() == "Y"


class _ObsSummaryCard(QFrame):
    """클릭 가능한 관찰 요약 카드."""

    clicked = pyqtSignal(str)

    def __init__(self, key: str, title: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("ObsSummaryCard")
        self.setStyleSheet(MainStyles.OBS_SUMMARY_CARD)
        self.setMinimumHeight(72)
        self.setMinimumWidth(OBS_SUMMARY_CARD_MIN_W)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("ObsSummaryTitle")
        self.lbl_value = QLabel("0")
        self.lbl_value.setObjectName("ObsSummaryValue")
        lay.addWidget(t)
        lay.addWidget(self.lbl_value)
        lay.addStretch(1)

    def set_value(self, n: int):
        self.lbl_value.setText(str(int(n or 0)))

    def set_selected(self, on: bool):
        self.setProperty("selected", bool(on))
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)


class ObservationEditDialog(QDialog):
    """관찰 등록/수정 다이얼로그 (기본·사진·열매·추적 탭)."""

    def __init__(
        self,
        parent,
        db,
        code_mgr,
        farm_cd,
        user_id,
        record=None,
        *,
        follow_up_of=None,
        read_only: bool = False,
        initial_obs_dt: str | None = None,
        initial_site_id: str | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.code_mgr = code_mgr
        self.farm_cd = farm_cd
        self.user_id = user_id
        self.record = dict(record) if record else None
        self.follow_up_of = dict(follow_up_of) if follow_up_of else None
        self.read_only = bool(read_only)
        self.saved_obs_id = None
        self._initial_obs_id = (self.record or {}).get("obs_id")
        self._saved_snapshot: dict | None = None
        self._pending_root = None
        self._pending_parent = None
        self._initial_obs_dt = initial_obs_dt
        self._initial_site_id = initial_site_id

        if self.follow_up_of:
            self.setWindowTitle("후속 관찰")
            parent_rec = self.follow_up_of
            self._pending_parent = parent_rec.get("obs_id")
            self._pending_root = (
                parent_rec.get("root_obs_id") or parent_rec.get("obs_id")
            )
        elif self.record:
            self.setWindowTitle("관찰 상세" if self.read_only else "관찰 수정")
        else:
            self.setWindowTitle("신규 관찰")

        self.setMinimumWidth(640)
        self.setMinimumHeight(520)
        self._build_ui()

        if self.follow_up_of:
            self._prefill_follow_up(self.follow_up_of)
        elif self.record:
            self._load_record(self.record)
        else:
            if self._initial_obs_dt:
                qd = QDate.fromString(str(self._initial_obs_dt), "yyyy-MM-dd")
                if qd.isValid():
                    self.dt_obs.setDate(qd)
            if self._initial_site_id:
                _set_combo_data(self.cb_site, self._initial_site_id)

        self._on_target_changed()
        self._sync_photo_panel()
        self._sync_ai_panel()
        self._load_fruit()
        self._load_track()
        self._update_saved_snapshot()
        if self.read_only:
            self._apply_read_only()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #EAE7E2; }")

        # --- 기본 관찰 ---
        # QFormLayout에 parent를 붙이지 않는다.
        # (parent 지정 후 다른 layout에 addLayout 하면 원본 위젯이 GC되어 크래시)
        form = QFormLayout()
        form.setSpacing(8)

        self.dt_obs = QDateEdit(QDate.currentDate())
        self.dt_obs.setCalendarPopup(True)
        self.dt_obs.setDisplayFormat("yyyy-MM-dd")
        self.dt_obs.setMaximumDate(QDate.currentDate())
        self.dt_obs.setStyleSheet(MainStyles.COMBO)

        self.cb_target = QComboBox()
        self.cb_type = QComboBox()
        self.cb_severity = QComboBox()
        self.cb_progress = QComboBox()
        self.cb_site = QComboBox()
        for cb in (
            self.cb_target,
            self.cb_type,
            self.cb_severity,
            self.cb_progress,
            self.cb_site,
        ):
            cb.setStyleSheet(MainStyles.COMBO)

        _combo_fill(
            self.cb_target,
            self.code_mgr.get_common_codes(DBManager.OBS_TARGET_PARENT_CD),
            "선택",
        )
        _combo_fill(
            self.cb_type,
            self.code_mgr.get_common_codes(DBManager.OBS_TYPE_PARENT_CD),
            "선택",
        )
        _combo_fill(
            self.cb_severity,
            self.code_mgr.get_common_codes(DBManager.OBS_SEVERITY_PARENT_CD),
            "선택",
        )
        _combo_fill(
            self.cb_progress,
            self.code_mgr.get_common_codes(DBManager.OBS_PROGRESS_PARENT_CD),
            "선택",
        )
        self.cb_site.clear()
        self.cb_site.addItem("선택", None)
        for loc in self.code_mgr.get_farm_sites() or []:
            if hasattr(loc, "keys"):
                sid = loc["site_id"]
                snm = loc["site_nm"]
            else:
                sid, snm = loc[0], loc[1]
            self.cb_site.addItem(str(snm), str(sid))

        self.ed_zone = QLineEdit()
        self.ed_row = QLineEdit()
        self.ed_tree = QLineEdit()
        self.ed_branch = QLineEdit()
        self.ed_sample = QLineEdit()
        for ed in (
            self.ed_zone,
            self.ed_row,
            self.ed_tree,
            self.ed_branch,
            self.ed_sample,
        ):
            ed.setStyleSheet(MainStyles.INPUT_CENTER)

        self.ed_title = QLineEdit()
        self.ed_title.setStyleSheet(MainStyles.INPUT_CENTER)
        self.txt_content = QTextEdit()
        self.txt_content.setMinimumHeight(90)
        self.txt_action = QTextEdit()
        self.txt_action.setMinimumHeight(70)
        self.dt_followup = QDateEdit()
        self.dt_followup.setCalendarPopup(True)
        self.dt_followup.setDisplayFormat("yyyy-MM-dd")
        self.dt_followup.setSpecialValueText("없음")
        self.dt_followup.setDate(QDate.currentDate())
        self.dt_followup.setMinimumDate(QDate(2000, 1, 1))
        self.cb_follow_use = QComboBox()
        self.cb_follow_use.addItem("없음", False)
        self.cb_follow_use.addItem("지정", True)
        self.cb_follow_use.setStyleSheet(MainStyles.COMBO)
        self.cb_follow_use.currentIndexChanged.connect(self._on_follow_toggle)
        self.dt_followup.setEnabled(False)

        follow_row = QHBoxLayout()
        follow_row.addWidget(self.cb_follow_use)
        follow_row.addWidget(self.dt_followup, 1)
        follow_w = QWidget()
        follow_w.setLayout(follow_row)

        self.lbl_hint = QLabel("")
        self.lbl_hint.setStyleSheet("color: #718096; font-size: 10px; border: none;")

        form.addRow("관찰일자 *", self.dt_obs)
        form.addRow("관찰 대상 *", self.cb_target)
        form.addRow("관찰 유형 *", self.cb_type)
        form.addRow("작업장소 *", self.cb_site)
        form.addRow("구역", self.ed_zone)
        form.addRow("열 번호", self.ed_row)
        form.addRow("나무번호", self.ed_tree)
        form.addRow("가지번호", self.ed_branch)
        form.addRow("표본번호", self.ed_sample)
        form.addRow("상태/심각도 *", self.cb_severity)
        form.addRow("처리상태 *", self.cb_progress)
        form.addRow("제목 *", self.ed_title)
        form.addRow("관찰내용 *", self.txt_content)
        form.addRow("조치내용", self.txt_action)
        form.addRow("재관찰 예정일", follow_w)
        form.addRow("", self.lbl_hint)

        basic_wrap = QWidget()
        basic_lay = QVBoxLayout(basic_wrap)
        basic_lay.setContentsMargins(4, 8, 4, 4)
        basic_lay.addLayout(form)
        self.btn_followup = QPushButton("후속 관찰 등록")
        self.btn_followup.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_followup.clicked.connect(self._on_follow_up)
        # 수정 모드에서만 표시
        show_fu = bool(self.record) and not self.follow_up_of and not self.read_only
        self.btn_followup.setVisible(show_fu)
        basic_lay.addWidget(self.btn_followup, 0, Qt.AlignmentFlag.AlignLeft)
        basic_lay.addStretch(1)
        self.tabs.addTab(basic_wrap, "기본 관찰")

        self.cb_target.currentIndexChanged.connect(self._on_target_changed)
        self.dt_obs.dateChanged.connect(self._on_obs_dt_changed)

        # --- 사진 ---
        oid = (self.record or {}).get("obs_id") or ""
        odt = ""
        if self.record:
            odt = str(self.record.get("obs_dt") or "")
        elif self.follow_up_of:
            odt = QDate.currentDate().toString("yyyy-MM-dd")
        self.photo_panel = PhotoPanel(
            self,
            db=self.db,
            code_mgr=self.code_mgr,
            farm_cd=self.farm_cd,
            user_id=self.user_id,
            obs_id=oid,
            obs_dt=odt or self.dt_obs.date().toString("yyyy-MM-dd"),
            read_only=self.read_only,
        )
        self.photo_panel.importStateChanged.connect(
            self._on_async_busy_changed
        )
        self.tabs.addTab(self.photo_panel, "사진")

        # --- AI 분석 ---
        self.ai_panel = AiAnalysisPanel(
            self,
            db=self.db,
            farm_cd=self.farm_cd,
            user_id=self.user_id,
            obs_id=oid,
            read_only=self.read_only,
        )
        self.ai_panel.aiBusyChanged.connect(self._on_async_busy_changed)
        self.tabs.addTab(self.ai_panel, "AI 분석")

        # --- 열매 측정 ---
        fl = QFormLayout()
        fl.setSpacing(8)
        self.lbl_fruit_gate = QLabel("열매 관찰에서만 측정값을 입력할 수 있습니다.")
        self.lbl_fruit_gate.setStyleSheet(
            "color: #718096; font-size: 10px; border: none;"
        )
        fl.addRow(self.lbl_fruit_gate)

        num_val = QDoubleValidator(0.0, 99999.0, 2, self)
        num_val.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.ed_width = QLineEdit()
        self.ed_height = QLineEdit()
        self.ed_circ = QLineEdit()
        self.ed_weight = QLineEdit()
        for ed in (self.ed_width, self.ed_height, self.ed_circ, self.ed_weight):
            ed.setStyleSheet(MainStyles.INPUT_CENTER)
            ed.setValidator(num_val)
            ed.setPlaceholderText("0 이상")

        self.cb_shape = QComboBox()
        self.cb_skin = QComboBox()
        self.cb_stalk = QComboBox()
        self.cb_calyx = QComboBox()
        for cb, parent_cd in (
            (self.cb_shape, DBManager.OBS_FRUIT_SHAPE_PARENT_CD),
            (self.cb_skin, DBManager.OBS_FRUIT_COLOR_PARENT_CD),
            (self.cb_stalk, DBManager.OBS_STALK_PARENT_CD),
            (self.cb_calyx, DBManager.OBS_CALYX_PARENT_CD),
        ):
            cb.setStyleSheet(MainStyles.COMBO)
            _combo_fill(cb, self.code_mgr.get_common_codes(parent_cd), "선택")

        self.sp_asym = QSpinBox()
        self.sp_asym.setRange(-1, 5)
        self.sp_asym.setSpecialValueText("미지정")
        self.sp_asym.setValue(-1)
        self.sp_asym.setStyleSheet(MainStyles.COMBO)

        self.chk_spot = QCheckBox("반점")
        self.chk_wound = QCheckBox("상처")
        self.chk_crack = QCheckBox("열과")
        self.chk_russet = QCheckBox("러셋")
        self.chk_sunburn = QCheckBox("일소")
        self.chk_deform = QCheckBox("기형")
        flag_row = QHBoxLayout()
        for chk in (
            self.chk_spot,
            self.chk_wound,
            self.chk_crack,
            self.chk_russet,
            self.chk_sunburn,
            self.chk_deform,
        ):
            flag_row.addWidget(chk)
        flag_row.addStretch(1)
        flag_w = QWidget()
        flag_w.setLayout(flag_row)

        self.ed_fruit_rmk = QLineEdit()
        self.ed_fruit_rmk.setStyleSheet(MainStyles.INPUT_CENTER)

        fl.addRow("가로(폭) mm", self.ed_width)
        fl.addRow("세로(길이) mm", self.ed_height)
        fl.addRow("둘레 mm", self.ed_circ)
        fl.addRow("추정 무게 g", self.ed_weight)
        fl.addRow("열매 형태", self.cb_shape)
        fl.addRow("과피색", self.cb_skin)
        fl.addRow("비대칭 등급", self.sp_asym)
        fl.addRow("이상 여부", flag_w)
        fl.addRow("과경 상태", self.cb_stalk)
        fl.addRow("꽃받침 상태", self.cb_calyx)
        fl.addRow("비고", self.ed_fruit_rmk)
        self._fruit_widgets = [
            self.ed_width,
            self.ed_height,
            self.ed_circ,
            self.ed_weight,
            self.cb_shape,
            self.cb_skin,
            self.sp_asym,
            self.chk_spot,
            self.chk_wound,
            self.chk_crack,
            self.chk_russet,
            self.chk_sunburn,
            self.chk_deform,
            self.cb_stalk,
            self.cb_calyx,
            self.ed_fruit_rmk,
        ]
        fruit_wrap = QWidget()
        fruit_lay = QVBoxLayout(fruit_wrap)
        fruit_lay.setContentsMargins(4, 8, 4, 4)
        fruit_lay.addLayout(fl)
        fruit_lay.addStretch(1)
        self.tabs.addTab(fruit_wrap, "열매 측정")

        # --- 추적 이력 ---
        track = QWidget()
        tl = QVBoxLayout(track)
        tl.setContentsMargins(4, 8, 4, 4)
        tl.setSpacing(8)
        self.lst_track = QListWidget()
        self.lst_track.setMinimumHeight(140)
        self.lst_track.setStyleSheet("font-size: 10px;")
        self.lst_track.itemDoubleClicked.connect(self._on_track_open)
        tl.addWidget(self.lst_track, 1)

        tbtn = QHBoxLayout()
        self.btn_compare = QPushButton("사진 비교")
        self.btn_compare.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_compare.clicked.connect(self._on_photo_compare)
        tbtn.addWidget(self.btn_compare)
        tbtn.addStretch(1)
        tbtn.addWidget(QLabel("성장 지표"))
        self.cb_metric = QComboBox()
        self.cb_metric.setStyleSheet(MainStyles.COMBO)
        for key, label, unit in _FRUIT_METRIC_KEYS:
            self.cb_metric.addItem(f"{label} ({unit})", key)
        self.cb_metric.currentIndexChanged.connect(self._refresh_growth_chart)
        tbtn.addWidget(self.cb_metric)
        tl.addLayout(tbtn)

        self.growth_chart = FruitGrowthChart("mm")
        tl.addWidget(self.growth_chart)
        self.tabs.addTab(track, "추적 이력")

        lay.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_save_continue = QPushButton("저장 후 계속")
        self.btn_save_close = QPushButton("저장 후 닫기")
        self.btn_cancel = QPushButton("취소")
        self.btn_save_continue.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_save_close.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_cancel.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_save_continue.setDefault(True)
        self.btn_save_continue.clicked.connect(self._on_save_continue)
        self.btn_save_close.clicked.connect(self._on_save_close)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_save_continue)
        btn_row.addWidget(self.btn_save_close)
        btn_row.addWidget(self.btn_cancel)
        lay.addLayout(btn_row)
        self._photo_busy_msg_open = False
        if self.read_only:
            self.btn_save_continue.setVisible(False)
            self.btn_save_close.setVisible(False)

    def _apply_read_only(self):
        for w in (
            self.dt_obs,
            self.cb_target,
            self.cb_type,
            self.cb_severity,
            self.cb_progress,
            self.cb_site,
            self.ed_zone,
            self.ed_row,
            self.ed_tree,
            self.ed_branch,
            self.ed_sample,
            self.ed_title,
            self.txt_content,
            self.txt_action,
            self.cb_follow_use,
            self.dt_followup,
            *self._fruit_widgets,
        ):
            w.setEnabled(False)
        self.btn_followup.setVisible(False)
        self.btn_save_continue.setVisible(False)
        self.btn_save_close.setVisible(False)
        self.btn_cancel.setText("닫기")

    def _on_follow_toggle(self):
        use = bool(self.cb_follow_use.currentData())
        self.dt_followup.setEnabled(use and not self.read_only)

    def _on_obs_dt_changed(self, _qd=None):
        self.photo_panel.set_obs_dt(self.dt_obs.date().toString("yyyy-MM-dd"))

    def _on_target_changed(self):
        target = self.cb_target.currentData()
        hints = _TARGET_FIELD_HINT.get(target or "", ())
        mapping = {
            "zone": (self.ed_zone, "구역"),
            "row": (self.ed_row, "열"),
            "tree": (self.ed_tree, "나무번호"),
            "branch": (self.ed_branch, "가지번호"),
            "sample": (self.ed_sample, "표본번호"),
        }
        names = [mapping[k][1] for k in hints if k in mapping]
        if names:
            self.lbl_hint.setText("권장 입력: " + " · ".join(names) + " (필수는 아님)")
        else:
            self.lbl_hint.setText("")
        if not hasattr(self, "_fruit_widgets"):
            return
        is_fruit = str(target or "") == DBManager.OBS_TARGET_FRUIT_CD
        self.lbl_fruit_gate.setVisible(not is_fruit)
        for w in self._fruit_widgets:
            w.setEnabled(is_fruit and not self.read_only)
        # 열매 측정 탭 인덱스: 2
        if hasattr(self, "tabs") and self.tabs.count() > 2:
            self.tabs.setTabEnabled(2, is_fruit or bool(self.record))

    def _prefill_follow_up(self, parent: dict):
        """위치·대상 유지, 내용 필드는 비움."""
        _set_combo_data(self.cb_target, parent.get("target_type_cd"))
        _set_combo_data(self.cb_type, parent.get("obs_type_cd"))
        _set_combo_data(self.cb_site, parent.get("site_id"))
        self.ed_zone.setText(str(parent.get("zone_nm") or ""))
        self.ed_row.setText(str(parent.get("row_no") or ""))
        self.ed_tree.setText(str(parent.get("tree_no") or ""))
        self.ed_branch.setText(str(parent.get("branch_no") or ""))
        self.ed_sample.setText(str(parent.get("sample_no") or ""))
        self.dt_obs.setDate(QDate.currentDate())
        self.cb_severity.setCurrentIndex(0)
        self.cb_progress.setCurrentIndex(0)
        self.ed_title.clear()
        self.txt_content.clear()
        self.txt_action.clear()
        self.cb_follow_use.setCurrentIndex(0)
        self.dt_followup.setEnabled(False)

    def _load_record(self, rec: dict):
        qd = QDate.fromString(str(rec.get("obs_dt") or ""), "yyyy-MM-dd")
        if qd.isValid():
            self.dt_obs.setDate(qd)
        _set_combo_data(self.cb_target, rec.get("target_type_cd"))
        _set_combo_data(self.cb_type, rec.get("obs_type_cd"))
        _set_combo_data(self.cb_severity, rec.get("severity_cd"))
        _set_combo_data(self.cb_progress, rec.get("progress_status_cd"))
        _set_combo_data(self.cb_site, rec.get("site_id"))
        self.ed_zone.setText(str(rec.get("zone_nm") or ""))
        self.ed_row.setText(str(rec.get("row_no") or ""))
        self.ed_tree.setText(str(rec.get("tree_no") or ""))
        self.ed_branch.setText(str(rec.get("branch_no") or ""))
        self.ed_sample.setText(str(rec.get("sample_no") or ""))
        self.ed_title.setText(str(rec.get("obs_title") or ""))
        self.txt_content.setPlainText(str(rec.get("obs_content") or ""))
        self.txt_action.setPlainText(str(rec.get("action_content") or ""))
        fu = str(rec.get("followup_dt") or "").strip()
        if fu:
            self.cb_follow_use.setCurrentIndex(1)
            fqd = QDate.fromString(fu, "yyyy-MM-dd")
            if fqd.isValid():
                self.dt_followup.setDate(fqd)
            self.dt_followup.setEnabled(not self.read_only)
        else:
            self.cb_follow_use.setCurrentIndex(0)
            self.dt_followup.setEnabled(False)

    def _sync_photo_panel(self):
        oid = ""
        if self.record:
            oid = str(self.record.get("obs_id") or "")
        odt = self.dt_obs.date().toString("yyyy-MM-dd")
        self.photo_panel.set_context(
            self.farm_cd,
            self.user_id,
            oid,
            odt,
            db=self.db,
            code_mgr=self.code_mgr,
        )
        self.photo_panel.set_unsaved_guard(self._is_form_dirty)

    def _sync_ai_panel(self):
        oid = ""
        if self.record:
            oid = str(self.record.get("obs_id") or "")
        elif self.saved_obs_id:
            oid = str(self.saved_obs_id)
        self.ai_panel.set_context(
            self.farm_cd, self.user_id, oid, db=self.db
        )

    def _form_state(self) -> dict:
        followup = None
        if self.cb_follow_use.currentData():
            followup = self.dt_followup.date().toString("yyyy-MM-dd")
        return {
            "obs_id": (self.record or {}).get("obs_id") or self.saved_obs_id,
            "obs_dt": self.dt_obs.date().toString("yyyy-MM-dd"),
            "target_type_cd": self.cb_target.currentData(),
            "obs_type_cd": self.cb_type.currentData(),
            "site_id": self.cb_site.currentData(),
            "zone_nm": self.ed_zone.text().strip(),
            "row_no": self.ed_row.text().strip(),
            "tree_no": self.ed_tree.text().strip(),
            "branch_no": self.ed_branch.text().strip(),
            "sample_no": self.ed_sample.text().strip(),
            "severity_cd": self.cb_severity.currentData(),
            "progress_status_cd": self.cb_progress.currentData(),
            "obs_title": self.ed_title.text().strip(),
            "obs_content": self.txt_content.toPlainText().strip(),
            "action_content": self.txt_action.toPlainText().strip(),
            "followup_dt": followup,
            "fruit": self._fruit_payload(),
        }

    def _update_saved_snapshot(self):
        self._saved_snapshot = self._form_state()

    def _is_form_dirty(self) -> bool:
        if self.read_only:
            return False
        return self._form_state() != (self._saved_snapshot or {})

    def _load_fruit(self):
        oid = (self.record or {}).get("obs_id")
        if not oid:
            return
        fm = self.db.get_fruit_measurement(self.farm_cd, oid)
        if not fm:
            return
        self.ed_width.setText("" if fm.get("width_mm") is None else str(fm["width_mm"]))
        self.ed_height.setText(
            "" if fm.get("height_mm") is None else str(fm["height_mm"])
        )
        self.ed_circ.setText(
            "" if fm.get("circumference_mm") is None else str(fm["circumference_mm"])
        )
        self.ed_weight.setText(
            ""
            if fm.get("estimated_weight_g") is None
            else str(fm["estimated_weight_g"])
        )
        _set_combo_data(self.cb_shape, fm.get("shape_cd"))
        _set_combo_data(self.cb_skin, fm.get("skin_color_cd"))
        _set_combo_data(self.cb_stalk, fm.get("stalk_status_cd"))
        _set_combo_data(self.cb_calyx, fm.get("calyx_status_cd"))
        asym = fm.get("asymmetry_level")
        if asym is None or str(asym).strip() == "":
            self.sp_asym.setValue(-1)
        else:
            try:
                self.sp_asym.setValue(max(0, min(5, int(asym))))
            except (TypeError, ValueError):
                self.sp_asym.setValue(-1)
        self.chk_spot.setChecked(_yn_checked(fm.get("spot_yn")))
        self.chk_wound.setChecked(_yn_checked(fm.get("wound_yn")))
        self.chk_crack.setChecked(_yn_checked(fm.get("crack_yn")))
        self.chk_russet.setChecked(_yn_checked(fm.get("russet_yn")))
        self.chk_sunburn.setChecked(_yn_checked(fm.get("sunburn_yn")))
        self.chk_deform.setChecked(_yn_checked(fm.get("deformity_yn")))
        self.ed_fruit_rmk.setText(str(fm.get("fruit_rmk") or ""))

    def _fruit_payload(self) -> dict:
        return {
            "width_mm": self.ed_width.text().strip(),
            "height_mm": self.ed_height.text().strip(),
            "circumference_mm": self.ed_circ.text().strip(),
            "estimated_weight_g": self.ed_weight.text().strip(),
            "shape_cd": self.cb_shape.currentData(),
            "skin_color_cd": self.cb_skin.currentData(),
            "asymmetry_level": (
                None if self.sp_asym.value() < 0 else self.sp_asym.value()
            ),
            "spot_yn": "Y" if self.chk_spot.isChecked() else "N",
            "wound_yn": "Y" if self.chk_wound.isChecked() else "N",
            "crack_yn": "Y" if self.chk_crack.isChecked() else "N",
            "russet_yn": "Y" if self.chk_russet.isChecked() else "N",
            "sunburn_yn": "Y" if self.chk_sunburn.isChecked() else "N",
            "deformity_yn": "Y" if self.chk_deform.isChecked() else "N",
            "stalk_status_cd": self.cb_stalk.currentData(),
            "calyx_status_cd": self.cb_calyx.currentData(),
            "fruit_rmk": self.ed_fruit_rmk.text().strip(),
        }

    def _current_obs_id(self) -> str:
        if self.record and self.record.get("obs_id"):
            return str(self.record["obs_id"])
        return str(self.saved_obs_id or "")

    def _root_for_track(self) -> str:
        if self.record:
            return str(
                self.record.get("root_obs_id")
                or self.record.get("obs_id")
                or ""
            )
        if self.follow_up_of:
            return str(
                self.follow_up_of.get("root_obs_id")
                or self.follow_up_of.get("obs_id")
                or ""
            )
        return self._current_obs_id()

    def _load_track(self):
        self.lst_track.clear()
        self._track_rows = []
        root = self._root_for_track()
        if not root:
            self.btn_compare.setEnabled(False)
            self.growth_chart.set_series("성장", "mm", [])
            return
        rows = self.db.list_observation_track(self.farm_cd, root) or []
        self._track_rows = rows
        cur_id = self._current_obs_id()
        highlight = -1
        for i, r in enumerate(rows):
            oid = str(r.get("obs_id") or "")
            dt = str(r.get("obs_dt") or "")
            sev = str(r.get("severity_nm") or "")
            prog = str(r.get("progress_status_nm") or "")
            title = str(r.get("obs_title") or "")
            content = str(r.get("obs_content") or "").replace("\n", " ")
            snippet = content[:40] + ("…" if len(content) > 40 else "")
            text = f"{dt}  [{sev}] {prog}\n{title}\n{snippet}"
            item = QListWidgetItem(text)
            item.setData(TRACK_ROLE_OBS_ID, oid)
            thumb = load_thumb_pixmap(r.get("thumb_path") or "", 48)
            if thumb is not None and not thumb.isNull():
                item.setIcon(QIcon(thumb))
            self.lst_track.addItem(item)
            if oid == cur_id:
                highlight = i
        if highlight >= 0:
            self.lst_track.setCurrentRow(highlight)
            font = self.lst_track.item(highlight).font()
            font.setBold(True)
            self.lst_track.item(highlight).setFont(font)
        self.btn_compare.setEnabled(len(rows) >= 2)
        self._refresh_growth_chart()

    def _refresh_growth_chart(self):
        key = self.cb_metric.currentData() or "width_mm"
        label, unit = "지표", "mm"
        for k, lb, u in _FRUIT_METRIC_KEYS:
            if k == key:
                label, unit = lb, u
                break
        points = []
        for r in getattr(self, "_track_rows", []) or []:
            val = r.get(key)
            try:
                num = float(val) if val is not None and str(val).strip() != "" else None
            except (TypeError, ValueError):
                num = None
            points.append({"dt": str(r.get("obs_dt") or ""), "value": num})
        self.growth_chart.set_series(label, unit, points)

    def _on_photo_compare(self):
        rows = getattr(self, "_track_rows", []) or []
        if len(rows) < 2:
            QMessageBox.information(
                self, "안내", "비교하려면 추적 이력이 2건 이상 필요합니다."
            )
            return
        dlg = PhotoCompareDialog(self, self.db, self.farm_cd, rows)
        dlg.exec()

    def _on_track_open(self, item: QListWidgetItem):
        oid = item.data(TRACK_ROLE_OBS_ID)
        if not oid:
            return
        if oid == self._current_obs_id() and not self.follow_up_of:
            return
        rec = self.db.get_observation(self.farm_cd, oid)
        if not rec:
            return
        dlg = ObservationEditDialog(
            self,
            self.db,
            self.code_mgr,
            self.farm_cd,
            self.user_id,
            record=rec,
            read_only=True,
        )
        dlg.exec()

    def _on_follow_up(self):
        if not self.record:
            return
        prog = str(self.record.get("progress_status_cd") or "")
        if prog in DBManager.OBS_PROGRESS_DONE_CDS:
            ans = QMessageBox.question(
                self,
                "후속 관찰",
                "이미 정상 회복/종료된 관찰입니다.\n후속 관찰을 등록하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        # 현재 미저장 편집이 있어도, 후속은 저장된 원본 기준
        parent = self.db.get_observation(
            self.farm_cd, self.record.get("obs_id")
        ) or self.record
        dlg = ObservationEditDialog(
            self,
            self.db,
            self.code_mgr,
            self.farm_cd,
            self.user_id,
            follow_up_of=parent,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.saved_obs_id = dlg.saved_obs_id
            self.accept()

    def _build_observation_data(self) -> dict:
        obs_dt = self.dt_obs.date().toString("yyyy-MM-dd")
        followup = None
        if self.cb_follow_use.currentData():
            followup = self.dt_followup.date().toString("yyyy-MM-dd")

        data = {
            "obs_id": (self.record or {}).get("obs_id") or self.saved_obs_id,
            "farm_cd": self.farm_cd,
            "obs_dt": obs_dt,
            "target_type_cd": self.cb_target.currentData(),
            "obs_type_cd": self.cb_type.currentData(),
            "site_id": self.cb_site.currentData(),
            "zone_nm": self.ed_zone.text().strip(),
            "row_no": self.ed_row.text().strip(),
            "tree_no": self.ed_tree.text().strip(),
            "branch_no": self.ed_branch.text().strip(),
            "sample_no": self.ed_sample.text().strip(),
            "severity_cd": self.cb_severity.currentData(),
            "progress_status_cd": self.cb_progress.currentData(),
            "obs_title": self.ed_title.text().strip(),
            "obs_content": self.txt_content.toPlainText().strip(),
            "action_content": self.txt_action.toPlainText().strip(),
            "followup_dt": followup,
        }
        if self.record:
            data["root_obs_id"] = self.record.get("root_obs_id")
            data["parent_obs_id"] = self.record.get("parent_obs_id")
            data["ai_status"] = (
                self.record.get("ai_status") or DBManager.OBS_AI_STATUS_NONE
            )
        elif self.follow_up_of:
            data["root_obs_id"] = self._pending_root
            data["parent_obs_id"] = self._pending_parent
            data["ai_status"] = DBManager.OBS_AI_STATUS_NONE
        else:
            data["ai_status"] = DBManager.OBS_AI_STATUS_NONE
        return data

    def _persist_observation(self, close_after: bool) -> bool:
        if self.read_only:
            return False
        if self.photo_panel.is_importing() or self.ai_panel.is_busy():
            self._show_busy_message()
            return False

        obs_dt = self.dt_obs.date().toString("yyyy-MM-dd")
        today = QDate.currentDate().toString("yyyy-MM-dd")
        if obs_dt > today:
            QMessageBox.warning(self, "검증", "관찰일자는 오늘까지만 허용됩니다.")
            return False
        if self.cb_follow_use.currentData():
            followup = self.dt_followup.date().toString("yyyy-MM-dd")
            if followup < obs_dt:
                QMessageBox.warning(
                    self, "검증", "재관찰 예정일은 관찰일자보다 이전일 수 없습니다."
                )
                return False

        data = self._build_observation_data()
        fruit_data = None
        if str(self.cb_target.currentData() or "") == DBManager.OBS_TARGET_FRUIT_CD:
            fruit_data = self._fruit_payload()

        ok, msg, obs_id = self.db.save_observation_bundle(
            data, self.user_id, fruit_data=fruit_data
        )
        if not ok:
            QMessageBox.warning(self, "저장 실패", msg)
            return False

        self.saved_obs_id = obs_id
        self.record = self.db.get_observation(self.farm_cd, obs_id) or {
            **data,
            "obs_id": obs_id,
        }
        self.photo_panel.set_obs_id(obs_id, obs_dt)
        self.photo_panel.set_unsaved_guard(self._is_form_dirty)
        self.ai_panel.set_obs_id(obs_id)
        self.btn_followup.setVisible(not self.read_only and bool(self.record))
        self._load_fruit()
        self._load_track()
        self._on_target_changed()
        self._update_saved_snapshot()
        self.setWindowTitle("관찰 수정")

        if close_after:
            QMessageBox.information(self, "저장", msg)
            self.accept()
        else:
            QMessageBox.information(self, "저장", msg)
            if self.tabs.count() > 1:
                self.tabs.setCurrentIndex(1)
        return True

    def _on_save_continue(self):
        self._persist_observation(close_after=False)

    def _on_save_close(self):
        self._persist_observation(close_after=True)

    def _on_async_busy_changed(self, _busy: bool = False):
        """사진 가져오기 또는 AI/PSIS 작업 중 저장·취소 버튼 비활성."""
        busy = self.photo_panel.is_importing() or self.ai_panel.is_busy()
        if self.read_only:
            self.btn_cancel.setEnabled(not busy)
            return
        enabled = not busy
        self.btn_save_continue.setEnabled(enabled)
        self.btn_save_close.setEnabled(enabled)
        self.btn_cancel.setEnabled(enabled)

    def _show_busy_message(self):
        if self._photo_busy_msg_open:
            return
        self._photo_busy_msg_open = True
        try:
            if self.photo_panel.is_importing():
                progress = ""
                try:
                    progress = self.photo_panel.import_progress_text()
                except RuntimeError:
                    progress = ""
                msg = (
                    "사진 처리가 진행 중입니다.\n"
                    "처리가 완료된 후 창을 닫아 주세요."
                )
                if progress:
                    msg = f"{msg}\n\n({progress})"
            else:
                msg = (
                    "AI 분석 또는 공식 등록정보 조회가 진행 중입니다.\n"
                    "처리가 완료된 후 창을 닫아 주세요."
                )
            QMessageBox.information(self, "안내", msg)
        finally:
            self._photo_busy_msg_open = False

    def _on_cancel(self):
        if self.photo_panel.is_importing() or self.ai_panel.is_busy():
            self._show_busy_message()
            return
        if self.saved_obs_id and not self._initial_obs_id:
            QMessageBox.information(
                self,
                "취소",
                "저장된 관찰과 사진은 유지됩니다.",
            )
        self.reject()

    def reject(self):
        if self.photo_panel.is_importing() or self.ai_panel.is_busy():
            self._show_busy_message()
            return
        super().reject()

    def closeEvent(self, event):
        if self.photo_panel.is_importing() or self.ai_panel.is_busy():
            self._show_busy_message()
            event.ignore()
            return
        super().closeEvent(event)


class ObservationLogPage(QWidget):
    """관찰일지 목록·필터·CRUD·요약."""

    def __init__(self, db_manager, session, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.session = session if isinstance(session, dict) else {}
        self.farm_cd = str(self.session.get("farm_cd") or "").strip()
        self.user_id = str(self.session.get("user_id") or "").strip()
        self._session_valid = bool(self.farm_cd and self.user_id)
        self.code_mgr = CodeManager(self.db, self.farm_cd)
        self._selected_obs_id = None
        self._summary_filter = None
        self._summary_cards: dict[str, _ObsSummaryCard] = {}
        self._build_ui()
        self._apply_session_gate()
        if self._session_valid:
            self.refresh_data()
            self._refresh_summary()

    def _session_ok(self, *, alert: bool = False) -> bool:
        if self._session_valid:
            return True
        if alert:
            QMessageBox.warning(self, "세션 확인", OBS_SESSION_MISSING_MSG)
        return False

    def _apply_session_gate(self) -> None:
        """세션 누락 시 CRUD 차단. OR001/ADMIN은 세션에 있을 때만 정상 사용."""
        enabled = self._session_valid
        self.lbl_session_warn.setVisible(not enabled)
        widgets = [
            self.btn_new,
            self.btn_search,
            self.btn_reset,
            self.btn_detail,
            self.btn_delete,
            self.dt_from,
            self.dt_to,
            self.f_target,
            self.f_type,
            self.f_severity,
            self.f_progress,
            self.f_site,
            self.ed_keyword,
            self.table,
            self.summary_frame,
        ]
        for w in widgets:
            w.setEnabled(enabled)
        if not enabled:
            self.table.setRowCount(0)
            self.lbl_count.setText("0건")
            for card in self._summary_cards.values():
                card.set_value(0)

    def _build_ui(self):
        self.setStyleSheet(MainStyles.MAIN_BG)
        # Preferred를 넘어도 작업창 폭 안으로 수축 가능하게 함
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 12, 15, 15)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("관찰일지")
        title.setStyleSheet(MainStyles.WORK_LOG_PAGE_TITLE)
        head.addWidget(title)
        head.addStretch()
        self.btn_new = QPushButton("신규 관찰")
        self.btn_new.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_new.clicked.connect(self._on_new)
        self.btn_search = QPushButton("조회")
        self.btn_search.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_search.clicked.connect(self._on_search)
        self.btn_reset = QPushButton("초기화")
        self.btn_reset.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_reset.clicked.connect(self._on_reset_filters)
        head.addWidget(self.btn_new)
        head.addWidget(self.btn_search)
        head.addWidget(self.btn_reset)
        root.addLayout(head)

        self.lbl_session_warn = QLabel(OBS_SESSION_MISSING_MSG)
        self.lbl_session_warn.setWordWrap(True)
        self.lbl_session_warn.setStyleSheet(
            "color: #9B2C2C; background: #FFEBEE; border: 1px solid #FECACA; "
            "border-radius: 8px; padding: 10px; font-size: 11px;"
        )
        self.lbl_session_warn.setVisible(False)
        root.addWidget(self.lbl_session_warn)

        # 요약 카드
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("border: none; background: transparent;")
        self.summary_frame.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        srow = QHBoxLayout(self.summary_frame)
        srow.setContentsMargins(0, 0, 0, 0)
        srow.setSpacing(8)
        for key, title_txt in _SUMMARY_KEYS:
            card = _ObsSummaryCard(key, title_txt)
            card.clicked.connect(self._on_summary_clicked)
            srow.addWidget(card, 1)
            self._summary_cards[key] = card
        root.addWidget(self.summary_frame)

        filt = QFrame()
        filt.setStyleSheet(MainStyles.CARD)
        filt.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        fl = QGridLayout(filt)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setHorizontalSpacing(6)
        fl.setVerticalSpacing(8)

        self.dt_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.dt_to = QDateEdit(QDate.currentDate())
        for d in (self.dt_from, self.dt_to):
            d.setCalendarPopup(True)
            d.setDisplayFormat("yyyy-MM-dd")
            d.setStyleSheet(MainStyles.COMBO)
            d.setMaximumWidth(OBS_FILTER_DATE_MAX_W)

        self.f_target = QComboBox()
        self.f_type = QComboBox()
        self.f_severity = QComboBox()
        self.f_progress = QComboBox()
        self.f_site = QComboBox()
        for cb in (
            self.f_target,
            self.f_type,
            self.f_severity,
            self.f_progress,
            self.f_site,
        ):
            cb.setStyleSheet(MainStyles.COMBO)
            cb.setMinimumWidth(OBS_FILTER_COMBO_MIN_W)
            cb.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )

        _combo_fill(
            self.f_target,
            self.code_mgr.get_common_codes(DBManager.OBS_TARGET_PARENT_CD),
        )
        _combo_fill(
            self.f_type,
            self.code_mgr.get_common_codes(DBManager.OBS_TYPE_PARENT_CD),
        )
        _combo_fill(
            self.f_severity,
            self.code_mgr.get_common_codes(DBManager.OBS_SEVERITY_PARENT_CD),
        )
        _combo_fill(
            self.f_progress,
            self.code_mgr.get_common_codes(DBManager.OBS_PROGRESS_PARENT_CD),
        )
        self.f_site.clear()
        self.f_site.addItem("전체", None)
        for loc in self.code_mgr.get_farm_sites() or []:
            if hasattr(loc, "keys"):
                self.f_site.addItem(str(loc["site_nm"]), str(loc["site_id"]))
            else:
                self.f_site.addItem(str(loc[1]), str(loc[0]))

        self.ed_keyword = QLineEdit()
        self.ed_keyword.setPlaceholderText("제목·내용·나무번호·표본번호")
        self.ed_keyword.setStyleSheet(MainStyles.INPUT_CENTER)
        self.ed_keyword.setMinimumWidth(OBS_FILTER_KEYWORD_MIN_W)
        self.ed_keyword.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        # 1행: 기간 + 대상/유형/심각도
        fl.addWidget(QLabel("관찰기간"), 0, 0)
        fl.addWidget(self.dt_from, 0, 1)
        fl.addWidget(QLabel("~"), 0, 2)
        fl.addWidget(self.dt_to, 0, 3)
        fl.addWidget(QLabel("대상"), 0, 4)
        fl.addWidget(self.f_target, 0, 5)
        fl.addWidget(QLabel("유형"), 0, 6)
        fl.addWidget(self.f_type, 0, 7)
        fl.addWidget(QLabel("심각도"), 0, 8)
        fl.addWidget(self.f_severity, 0, 9)
        # 2행: 처리/장소 + 검색어(남은 폭)
        fl.addWidget(QLabel("처리"), 1, 0)
        fl.addWidget(self.f_progress, 1, 1)
        fl.addWidget(QLabel("장소"), 1, 2)
        fl.addWidget(self.f_site, 1, 3, 1, 2)
        fl.addWidget(self.ed_keyword, 1, 5, 1, 5)
        for c in range(10):
            fl.setColumnStretch(c, 1 if c in (5, 7, 9) else 0)
        fl.setColumnStretch(5, 2)
        fl.setColumnStretch(9, 1)
        root.addWidget(filt)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "관찰일자",
                "관찰 대상",
                "관찰 유형",
                "위치",
                "제목",
                "심각도",
                "처리상태",
                "재관찰일",
                "등록자",
            ]
        )
        self.table.setStyleSheet(MainStyles.TABLE + MainStyles.TABLE_CONTENT_10)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        hh = self.table.horizontalHeader()
        hh.setMinimumSectionSize(OBS_TABLE_MIN_SECTION_W)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        foot = QHBoxLayout()
        self.lbl_count = QLabel("0건")
        self.lbl_count.setStyleSheet("color: #4A5568; border: none;")
        foot.addWidget(self.lbl_count)
        foot.addStretch()
        self.btn_detail = QPushButton("상세/수정")
        self.btn_detail.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_detail.clicked.connect(self._on_edit_selected)
        self.btn_delete = QPushButton("삭제")
        self.btn_delete.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_delete.clicked.connect(self._on_delete_selected)
        foot.addWidget(self.btn_detail)
        foot.addWidget(self.btn_delete)
        root.addLayout(foot)

    def _refresh_summary(self):
        if not self._session_valid:
            return
        today = QDate.currentDate().toString("yyyy-MM-dd")
        summary = self.db.get_observation_dashboard_summary(self.farm_cd, today) or {}
        for key, _title in _SUMMARY_KEYS:
            card = self._summary_cards.get(key)
            if card:
                card.set_value(int(summary.get(key) or 0))
                card.set_selected(self._summary_filter == key)

    def _on_summary_clicked(self, key: str):
        if not self._session_ok(alert=True):
            return
        if self._summary_filter == key:
            self._summary_filter = None
        else:
            self._summary_filter = key
            # 요약 클릭 시 넓은 기간으로 조회
            self.dt_from.setDate(QDate.currentDate().addYears(-1))
            self.dt_to.setDate(QDate.currentDate())
            for cb in (
                self.f_target,
                self.f_type,
                self.f_severity,
                self.f_progress,
                self.f_site,
            ):
                cb.setCurrentIndex(0)
            self.ed_keyword.clear()
        self._refresh_summary()
        self.refresh_data()

    def _apply_summary_filter(self, rows: list[dict]) -> list[dict]:
        key = self._summary_filter
        if not key:
            return rows
        today = QDate.currentDate().toString("yyyy-MM-dd")
        month_prefix = today[:7]
        done = DBManager.OBS_PROGRESS_DONE_CDS
        caution = {"OS010300", "OS010400"}
        out = []
        for r in rows:
            prog = str(r.get("progress_status_cd") or "").strip()
            sev = str(r.get("severity_cd") or "").strip()
            fu = str(r.get("followup_dt") or "").strip()
            obs_dt = str(r.get("obs_dt") or "").strip()
            if key == "in_progress":
                if prog not in done:
                    out.append(r)
            elif key == "followup_today":
                if prog not in done and fu == today:
                    out.append(r)
            elif key == "followup_overdue":
                if prog not in done and fu and fu < today:
                    out.append(r)
            elif key == "caution_danger":
                if sev in caution and prog not in done:
                    out.append(r)
            elif key == "month_done":
                if prog in done and obs_dt.startswith(month_prefix):
                    out.append(r)
        return out

    def _on_search(self):
        self._summary_filter = None
        self._refresh_summary()
        self.refresh_data()

    def _on_reset_filters(self):
        if not self._session_ok(alert=True):
            return
        self._summary_filter = None
        self.dt_from.setDate(QDate.currentDate().addMonths(-1))
        self.dt_to.setDate(QDate.currentDate())
        for cb in (
            self.f_target,
            self.f_type,
            self.f_severity,
            self.f_progress,
            self.f_site,
        ):
            cb.setCurrentIndex(0)
        self.ed_keyword.clear()
        self._refresh_summary()
        self.refresh_data()

    def apply_external_filters(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        select_obs_id: str | None = None,
    ):
        """영농일지 등 외부 화면에서 기간·선택 관찰 이동."""
        if not self._session_ok(alert=False):
            return
        self._summary_filter = None
        if date_from:
            qd = QDate.fromString(str(date_from)[:10], "yyyy-MM-dd")
            if qd.isValid():
                self.dt_from.setDate(qd)
        if date_to:
            qd = QDate.fromString(str(date_to)[:10], "yyyy-MM-dd")
            if qd.isValid():
                self.dt_to.setDate(qd)
        self._refresh_summary()
        self.refresh_data(select_obs_id)

    def open_new_observation(
        self, obs_dt: str | None = None, site_id: str | None = None
    ):
        """영농일지 등에서 신규 관찰 다이얼로그 오픈."""
        if not self._session_ok(alert=True):
            return
        dlg = ObservationEditDialog(
            self,
            self.db,
            self.code_mgr,
            self.farm_cd,
            self.user_id,
            initial_obs_dt=obs_dt,
            initial_site_id=site_id,
        )
        code = dlg.exec()
        if dlg.saved_obs_id:
            self._selected_obs_id = dlg.saved_obs_id
            self.refresh_data(dlg.saved_obs_id)
            self._refresh_summary()

    def _loc_text(self, row: dict) -> str:
        parts = []
        site = (row.get("site_nm") or "").strip()
        if site:
            parts.append(site)
        zone = (row.get("zone_nm") or "").strip()
        if zone:
            parts.append(zone)
        tree = (row.get("tree_no") or "").strip()
        if tree:
            parts.append(f"나무 {tree}")
        sample = (row.get("sample_no") or "").strip()
        if sample:
            parts.append(f"표본 {sample}")
        return " / ".join(parts) if parts else "-"

    def refresh_data(self, select_obs_id: str | None = None):
        if not self._session_ok(alert=False):
            self.table.setRowCount(0)
            self.lbl_count.setText("0건")
            return
        if select_obs_id is None:
            select_obs_id = self._selected_obs_id

        limit = OBS_SUMMARY_LIST_LIMIT if self._summary_filter else OBS_LIST_LIMIT
        date_from = self.dt_from.date().toString("yyyy-MM-dd")
        date_to = self.dt_to.date().toString("yyyy-MM-dd")
        if self._summary_filter:
            date_from = QDate.currentDate().addYears(-1).toString("yyyy-MM-dd")
            date_to = QDate.currentDate().toString("yyyy-MM-dd")

        rows = self.db.list_observations(
            self.farm_cd,
            date_from=date_from,
            date_to=date_to,
            target_type_cd=None if self._summary_filter else self.f_target.currentData(),
            obs_type_cd=None if self._summary_filter else self.f_type.currentData(),
            severity_cd=None if self._summary_filter else self.f_severity.currentData(),
            progress_status_cd=(
                None if self._summary_filter else self.f_progress.currentData()
            ),
            site_id=None if self._summary_filter else self.f_site.currentData(),
            keyword=(
                None
                if self._summary_filter
                else (self.ed_keyword.text().strip() or None)
            ),
            limit=limit,
        )
        rows = self._apply_summary_filter(list(rows or []))

        self.table.setRowCount(0)
        select_row = -1
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            vals = [
                str(r.get("obs_dt") or ""),
                str(r.get("target_type_nm") or ""),
                str(r.get("obs_type_nm") or ""),
                self._loc_text(r),
                str(r.get("obs_title") or ""),
                str(r.get("severity_nm") or ""),
                str(r.get("progress_status_nm") or ""),
                str(r.get("followup_dt") or ""),
                str(r.get("reg_id") or ""),
            ]
            severity_cd = str(r.get("severity_cd") or "")
            bg = MainStyles.OBS_SEVERITY_BG.get(severity_cd)
            fg = MainStyles.OBS_SEVERITY_FG.get(severity_cd)
            for c, text in enumerate(vals):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 0:
                    item.setData(OBS_COL_OBS_ID, r.get("obs_id"))
                    item.setData(OBS_COL_SEVERITY, severity_cd)
                if bg:
                    item.setBackground(QBrush(QColor(bg)))
                if fg and c == 5:
                    item.setForeground(QBrush(QColor(fg)))
                self.table.setItem(i, c, item)
            if select_obs_id and r.get("obs_id") == select_obs_id:
                select_row = i

        self.lbl_count.setText(
            f"{len(rows)}건"
            + (f" (최대 {limit}건)" if len(rows) >= limit else "")
        )
        if select_row >= 0:
            self.table.selectRow(select_row)
            self._selected_obs_id = select_obs_id
        elif rows:
            self._selected_obs_id = None

    def _current_obs_id(self) -> str | None:
        items = self.table.selectedItems()
        if not items:
            row = self.table.currentRow()
            if row < 0:
                return None
            it = self.table.item(row, 0)
        else:
            it = self.table.item(items[0].row(), 0)
        if not it:
            return None
        return it.data(OBS_COL_OBS_ID)

    def _on_new(self):
        self.open_new_observation()

    def _on_edit_selected(self):
        if not self._session_ok(alert=True):
            return
        oid = self._current_obs_id()
        if not oid:
            QMessageBox.information(self, "안내", "수정할 관찰을 선택해 주세요.")
            return
        rec = self.db.get_observation(self.farm_cd, oid)
        if not rec or (rec.get("use_yn") or "Y") != "Y":
            QMessageBox.warning(self, "안내", "관찰 정보를 찾을 수 없습니다.")
            self.refresh_data()
            return
        dlg = ObservationEditDialog(
            self, self.db, self.code_mgr, self.farm_cd, self.user_id, record=rec
        )
        dlg.exec()
        if dlg.saved_obs_id:
            self._selected_obs_id = dlg.saved_obs_id or oid
            self.refresh_data(self._selected_obs_id)
            self._refresh_summary()

    def _on_double_click(self, row, _col):
        self.table.selectRow(row)
        self._on_edit_selected()

    def _on_delete_selected(self):
        if not self._session_ok(alert=True):
            return
        oid = self._current_obs_id()
        if not oid:
            QMessageBox.information(self, "안내", "삭제할 관찰을 선택해 주세요.")
            return
        ans = QMessageBox.question(
            self,
            "삭제 확인",
            "선택한 관찰을 삭제하시겠습니까?\n(목록에서만 숨기고 기록은 보관됩니다.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        ok, msg = self.db.soft_delete_observation(self.farm_cd, oid, self.user_id)
        if ok:
            QMessageBox.information(self, "삭제", msg)
            self._selected_obs_id = None
            self.refresh_data()
            self._refresh_summary()
        else:
            QMessageBox.warning(self, "삭제 실패", msg)
