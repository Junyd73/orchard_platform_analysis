# -*- coding: utf-8 -*-
"""농약 AI 추천 UI 블록 — 사전/사용 페이지에서 공통 사용 (의사결정 중심 레이아웃)."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QBrush, QColor, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ui.styles import MainStyles
from ui.widgets.ai_recommend_worker import AiRecommendWorker


def _plain(s: object) -> str:
    t = str(s) if s is not None else ""
    return t.strip()


def _fmt_num(v: object, digits: int = 0) -> str:
    try:
        if digits == 0:
            return str(int(round(float(v))))
        return str(round(float(v), digits))
    except (TypeError, ValueError):
        return "—"


def _truncate(s: str, max_len: int) -> str:
    t = (s or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _risk_label_from_score(score: object) -> str:
    """UI 표시용 등급(점수 구간만 반영 — 채점식과 pesticide_ai_recommend_manager.RISK_* 와 동일 구간)."""
    try:
        s = int(score)
    except (TypeError, ValueError):
        s = 0
    if s <= 3:
        return "낮음"
    if s <= 6:
        return "주의"
    return "위험"


# 결론 카드 톤: 방제 필요 / 예방·권장 관찰 / 경과 관찰(안정·녹계열)
_CONCLUSION_STYLES = {
    "need": (
        "#FEF6EE",
        "#E8D4C4",
        "#D97706",
        "#9A3412",
    ),  # bg, border, accent, title
    "watch": ("#F4F6F8", "#E2E8F0", "#718096", "#2D3748"),
    "hold": ("#EDF7F2", "#CDE9DC", "#276749", "#22543D"),
}


# 분석 단계 표시 순서(Worker·매니저 콜백과 동일한 문구)
AI_RECOMMEND_STEP_LABELS: tuple[str, ...] = (
    "기상 영향 분석",
    "작업 이력 확인",
    "병해충 위험 판단",
    "방제 필요 여부 판단",
    "최근 사용 농약 확인",
    "최종 방제 추천",
)

_WORKER_TO_UI_STEP: Dict[str, str] = {
    "날씨 데이터 수집": "기상 영향 분석",
    "기상 분석": "기상 영향 분석",
    "작업 이력 분석": "작업 이력 확인",
    "병해충 위험도 계산": "병해충 위험 판단",
    "농약 후보 추출": "최근 사용 농약 확인",
    "재고·사용이력 보정": "최근 사용 농약 확인",
    "최종 추천 생성": "최종 방제 추천",
}

_LOG_MAX_LINES = 1000

# 카드·본문 통일
_CARD_FRAME = """
    QFrame#aiCard {
        background-color: #FFFFFF;
        border: 1px solid #EAE7E2;
        border-radius: 10px;
    }
"""
_SECTION_TITLE_STYLE = (
    "font-weight: bold; color: #374151; border: none; background: transparent;"
)
_BODY_STYLE = "color: #4A5568; border: none; background: transparent;"
_CAPTION_STYLE = "color: #718096; border: none; background: transparent;"
_KV_LABEL_STYLE = "color: #718096; border: none; background: transparent;"
_KV_VALUE_STYLE = "font-weight: bold; color: #2D3748; border: none; background: transparent;"
_CARD_BODY_SPACING = 4
_CARD_CONTENT_TOP_MARGIN = 2
_TABLE_HEADING_STYLE = (
    "font-weight: bold; color: #2D5A27; border: none; background: transparent;"
)
_TABLE_HINT_STYLE = "color: #718096; border: none; background: transparent;"
_RECOMMEND_TABLE_STYLE = (
    MainStyles.TABLE
    + """
    QHeaderView::section { min-height: 28px; }
    """
)
_ROW_TOP_BG = QColor(245, 250, 243)

_SCORE_DETAIL_POPUP_STYLE = (
    """
    QMessageBox {
        background-color: #FFFFFF;
        border: 1px solid #EAE7E2;
        border-radius: 10px;
        color: #2D3748;
    }
    /* QMessageBox는 아이콘 영역을 기본 확보해서 텍스트가 오른쪽으로 밀림 */
    QLabel#qt_msgboxex_icon_label {
        min-width: 0px;
        max-width: 0px;
        min-height: 0px;
        max-height: 0px;
        margin: 0px;
        padding: 0px;
    }
    QLabel#qt_msgboxex_icon_label * { border: none; }
    QLabel#qt_msgbox_label {
        padding-left: 0px;
        margin-left: 0px;
    }
    QMessageBox QLabel {
        color: #2D3748;
    }
    QMessageBox QPushButton {
        """
    + MainStyles.BTN_PRIMARY.replace("QPushButton", "QPushButton")
    + """
    }
    """
)


class PesticideAIRecommendPanel(QWidget):
    def __init__(self, farm_cd: str):
        super().__init__()
        self.farm_cd = str(farm_cd or "")
        self._thread: QThread | None = None
        self._worker: AiRecommendWorker | None = None
        self._step_labels: list[QLabel] = []
        self._last_result: dict | None = None
        self._step_started_at: Dict[str, float] = {}
        self._step_elapsed_sec: Dict[str, float] = {}
        self._substep_elapsed_sec: Dict[str, float] = {}
        self._active_step: str = ""
        self._ui_step_order: List[str] = list(AI_RECOMMEND_STEP_LABELS)
        self._progress_payloads: Dict[str, Dict[str, object]] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(6)

        btn_row = QHBoxLayout()
        self.ai_btn = QPushButton("AI 추천 실행")
        self.ai_btn.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.ai_btn.clicked.connect(self._run_recommend)
        btn_row.addWidget(self.ai_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setSpacing(4)
        lay.setContentsMargins(0, 0, 2, 0)

        # —— [1] 결론 카드 ——
        self._conclusion_frame = QFrame()
        self._conclusion_frame.setObjectName("conclusionCard")
        self._conclusion_title = QLabel("방제 요약")
        self._conclusion_line1 = QLabel("")
        self._conclusion_line1.setWordWrap(True)
        self._conclusion_line2 = QLabel("")
        self._conclusion_line2.setWordWrap(True)
        self._conclusion_line3 = QLabel("")
        self._conclusion_line3.setWordWrap(True)
        for lb in (
            self._conclusion_line1,
            self._conclusion_line2,
            self._conclusion_line3,
        ):
            lb.setStyleSheet(_BODY_STYLE)
        cl = QVBoxLayout(self._conclusion_frame)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(4)
        cl.addWidget(self._conclusion_title)
        cl.addWidget(self._conclusion_line1)
        cl.addWidget(self._conclusion_line2)
        cl.addWidget(self._conclusion_line3)
        lay.addWidget(self._conclusion_frame)

        # —— [2] 상태 카드 (기준일·생육·진행) ——
        self._status_frame = QFrame()
        self._status_frame.setObjectName("aiCard")
        self._status_frame.setStyleSheet(_CARD_FRAME)
        st = QVBoxLayout(self._status_frame)
        st.setContentsMargins(8, 6, 8, 6)
        st.setSpacing(_CARD_BODY_SPACING)
        meta_row = QHBoxLayout()
        self._lbl_base_dt = QLabel("기준일 —")
        self._lbl_base_dt.setStyleSheet(_KV_VALUE_STYLE)
        self._lbl_growth = QLabel("생육 —")
        self._lbl_growth.setStyleSheet(_KV_VALUE_STYLE)
        self._lbl_run_state = QLabel("")
        self._lbl_run_state.setStyleSheet(_CAPTION_STYLE)
        meta_row.addWidget(self._lbl_base_dt)
        meta_row.addSpacing(16)
        meta_row.addWidget(self._lbl_growth)
        meta_row.addStretch()
        meta_row.addWidget(self._lbl_run_state)
        st.addLayout(meta_row)
        self._prog = QProgressBar()
        self._prog.setRange(0, 100)
        self._prog.setValue(0)
        self._prog.setFixedHeight(6)
        self._prog.setTextVisible(False)
        self._prog.setStyleSheet(
            """
            QProgressBar { background: #EDF2F7; border: none; border-radius: 3px; }
            QProgressBar::chunk { background: #5B7C5B; border-radius: 3px; }
            """
        )
        st.addWidget(self._prog)
        lay.addWidget(self._status_frame)

        # —— 병해충 위험 요약 카드 ——
        self._pest_frame = QFrame()
        self._pest_frame.setObjectName("aiCard")
        self._pest_frame.setStyleSheet(_CARD_FRAME)
        self._pest_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        pf = QVBoxLayout(self._pest_frame)
        pf.setContentsMargins(8, 6, 8, 6)
        pf.setSpacing(_CARD_BODY_SPACING)
        lbl_pest_t = QLabel("병해충 위험 판단")
        lbl_pest_t.setStyleSheet(_SECTION_TITLE_STYLE)
        pf.addWidget(lbl_pest_t)
        self._pest_rows_host = QWidget()
        self._pest_vlay = QVBoxLayout(self._pest_rows_host)
        self._pest_vlay.setContentsMargins(0, _CARD_CONTENT_TOP_MARGIN, 0, 0)
        self._pest_vlay.setSpacing(3)
        pf.addWidget(self._pest_rows_host)

        # —— 분석 단계 카드 (입력 요약·병해충과 동일: QFrame + 내부 제목) ——
        self._step_frame = QFrame()
        self._step_frame.setObjectName("aiCard")
        self._step_frame.setStyleSheet(_CARD_FRAME)
        self._step_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._step_frame.setMinimumWidth(170)
        s_lay = QVBoxLayout(self._step_frame)
        s_lay.setContentsMargins(8, 6, 8, 6)
        s_lay.setSpacing(_CARD_BODY_SPACING)
        lbl_step_t = QLabel("분석 단계")
        lbl_step_t.setStyleSheet(_SECTION_TITLE_STYLE)
        s_lay.addWidget(lbl_step_t)
        self._step_content = QWidget()
        s_inner = QVBoxLayout(self._step_content)
        s_inner.setContentsMargins(0, _CARD_CONTENT_TOP_MARGIN, 0, 0)
        s_inner.setSpacing(3)
        for title in AI_RECOMMEND_STEP_LABELS:
            lab = QLabel(f"○  {title}")
            lab.setStyleSheet(_BODY_STYLE)
            self._step_labels.append(lab)
            s_inner.addWidget(lab)
        s_lay.addWidget(self._step_content)

        # —— 분석 단계별 데이터 카드(1차) ——
        self._hist_frame = QFrame()
        self._hist_frame.setObjectName("aiCard")
        self._hist_frame.setStyleSheet(_CARD_FRAME)
        hist_v = QVBoxLayout(self._hist_frame)
        hist_v.setContentsMargins(8, 6, 8, 6)
        hist_v.setSpacing(_CARD_BODY_SPACING)
        hist_t = QLabel("작업 이력 확인")
        hist_t.setStyleSheet(_SECTION_TITLE_STYLE)
        hist_v.addWidget(hist_t)
        self._hist_grid_host = QWidget()
        self._hist_grid = QGridLayout(self._hist_grid_host)
        self._hist_grid.setContentsMargins(0, _CARD_CONTENT_TOP_MARGIN, 0, 0)
        self._hist_grid.setHorizontalSpacing(10)
        self._hist_grid.setVerticalSpacing(2)
        self._hist_grid.setColumnStretch(1, 1)
        hist_v.addWidget(self._hist_grid_host)

        self._weather_frame = QFrame()
        self._weather_frame.setObjectName("aiCard")
        self._weather_frame.setStyleSheet(_CARD_FRAME)
        weather_v = QVBoxLayout(self._weather_frame)
        weather_v.setContentsMargins(8, 6, 8, 6)
        weather_v.setSpacing(_CARD_BODY_SPACING)
        weather_t = QLabel("기상 영향 분석")
        weather_t.setStyleSheet(_SECTION_TITLE_STYLE)
        weather_v.addWidget(weather_t)
        self._weather_grid_host = QWidget()
        self._weather_grid = QGridLayout(self._weather_grid_host)
        self._weather_grid.setContentsMargins(0, _CARD_CONTENT_TOP_MARGIN, 0, 0)
        self._weather_grid.setHorizontalSpacing(10)
        self._weather_grid.setVerticalSpacing(2)
        self._weather_grid.setColumnStretch(1, 1)
        weather_v.addWidget(self._weather_grid_host)

        self._last_use_frame = QFrame()
        self._last_use_frame.setObjectName("aiCard")
        self._last_use_frame.setStyleSheet(_CARD_FRAME)
        last_v = QVBoxLayout(self._last_use_frame)
        last_v.setContentsMargins(8, 6, 8, 6)
        last_v.setSpacing(_CARD_BODY_SPACING)
        last_t = QLabel("최근 사용 농약 확인")
        last_t.setStyleSheet(_SECTION_TITLE_STYLE)
        last_v.addWidget(last_t)
        self._last_use_grid_host = QWidget()
        self._last_use_grid = QGridLayout(self._last_use_grid_host)
        self._last_use_grid.setContentsMargins(0, _CARD_CONTENT_TOP_MARGIN, 0, 0)
        self._last_use_grid.setHorizontalSpacing(10)
        self._last_use_grid.setVerticalSpacing(2)
        self._last_use_grid.setColumnStretch(1, 1)
        last_v.addWidget(self._last_use_grid_host)

        # —— 추천·판단 근거 카드 ——
        self._reason_frame = QFrame()
        self._reason_frame.setObjectName("aiCard")
        self._reason_frame.setStyleSheet(_CARD_FRAME)
        self._reason_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        rf = QVBoxLayout(self._reason_frame)
        rf.setContentsMargins(8, 6, 8, 6)
        rf.setSpacing(_CARD_BODY_SPACING)
        lbl_r = QLabel("방제 필요 여부 판단")
        lbl_r.setStyleSheet(_SECTION_TITLE_STYLE)
        rf.addWidget(lbl_r)
        self._reason_host = QWidget()
        self._reason_vlay = QVBoxLayout(self._reason_host)
        self._reason_vlay.setContentsMargins(0, _CARD_CONTENT_TOP_MARGIN, 0, 0)
        self._reason_vlay.setSpacing(3)
        rf.addWidget(self._reason_host, 1)

        # —— 추천 농약(표) 카드 ——
        self._table_card = QFrame()
        self._table_card.setObjectName("aiCard")
        self._table_card.setStyleSheet(_CARD_FRAME)
        self._table_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        tb_lay = QVBoxLayout(self._table_card)
        tb_lay.setContentsMargins(8, 6, 8, 6)
        tb_lay.setSpacing(_CARD_BODY_SPACING)
        self._table_heading = QLabel("최종 방제 추천 (우선순위)")
        self._table_heading.setStyleSheet(_TABLE_HEADING_STYLE)
        self._table_hint = QLabel("")
        self._table_hint.setStyleSheet(_TABLE_HINT_STYLE)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(
            ["농약명", "점수", "구분", "보유량", "주요 추천 이유"]
        )
        self.result_table.setStyleSheet(_RECOMMEND_TABLE_STYLE)
        self.result_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.verticalHeader().setDefaultSectionSize(28)
        self.result_table.setMinimumHeight(120)
        self.result_table.cellClicked.connect(self._on_recommend_row_clicked)
        self.result_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        h5 = self.result_table.horizontalHeader()
        h5.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h5.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h5.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h5.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h5.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        tb_lay.addWidget(self._table_heading)
        tb_lay.addWidget(self._table_hint)
        tb_lay.addWidget(self.result_table, 1)

        # —— 카드 배치(상단 5개 우선 노출, 하단은 판단/추천) ——
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        for card in (
            self._step_frame,
            self._weather_frame,
            self._hist_frame,
            self._pest_frame,
            self._last_use_frame,
        ):
            card.setMinimumWidth(220)
            top_row.addWidget(card, 1, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top_row, 1)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)
        self._reason_frame.setMinimumWidth(360)
        self._table_card.setMinimumWidth(480)
        bottom_row.addWidget(self._reason_frame, 1, Qt.AlignmentFlag.AlignTop)
        bottom_row.addWidget(self._table_card, 1, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(bottom_row, 1)

        # —— 분석 로그 (접기) ——
        log_bar = QHBoxLayout()
        self._log_toggle = QPushButton("분석 로그 펼치기")
        self._log_toggle.setCheckable(True)
        self._log_toggle.setChecked(False)
        self._log_toggle.setStyleSheet(
            """
            QPushButton {
                color: #718096;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 4px 10px;
                background: #FAFAFA;
            }
            QPushButton:checked { background: #F0F4F8; color: #4A5568; }
            """
        )
        self._log_toggle.toggled.connect(self._on_log_toggle)
        log_bar.addWidget(self._log_toggle)
        log_bar.addStretch()
        lay.addLayout(log_bar)

        self._log_wrap = QWidget()
        log_v = QVBoxLayout(self._log_wrap)
        log_v.setContentsMargins(0, 0, 0, 0)
        log_v.setSpacing(4)
        self._log_te = QTextEdit()
        self._log_te.setReadOnly(True)
        self._log_te.setMaximumHeight(72)
        self._log_te.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._log_te.setStyleSheet(
            MainStyles.INPUT_CENTER
            + """
            QTextEdit {
                border: 1px solid #E2E8F0;
                padding: 6px;
                border-radius: 6px;
                background-color: #FAFAFA;
                color: #718096;
            }
            """
        )
        log_v.addWidget(self._log_te)
        self._log_wrap.setVisible(False)
        lay.addWidget(self._log_wrap)

        outer.addWidget(scroll, 1)
        self._apply_empty_placeholders()

    # —— UI 헬퍼 ——
    def _apply_empty_placeholders(self) -> None:
        self._style_conclusion("watch", "방제 요약", "실행 전", "AI 추천 실행 후 한눈에 판단 요약이 표시됩니다.", "")
        self._lbl_base_dt.setText("기준일 —")
        self._lbl_growth.setText("생육단계 —")
        self._lbl_run_state.setText("")
        self._prog.setValue(0)
        self._clear_pest_rows()
        pe = QLabel("—")
        pe.setStyleSheet(_BODY_STYLE)
        self._pest_vlay.addWidget(pe)
        self._clear_grid(self._hist_grid)
        self._add_kv_row(self._hist_grid, 0, "최근 방제", "미확인")
        self._clear_grid(self._weather_grid)
        self._add_kv_row(self._weather_grid, 0, "기상", "미확인")
        self._clear_grid(self._last_use_grid)
        self._add_kv_row(self._last_use_grid, 0, "최근 사용", "기록 없음")
        self._clear_reason_rows()
        rq = QLabel("실행 후 짧은 근거 목록이 표시됩니다.")
        rq.setStyleSheet(_CAPTION_STYLE)
        self._reason_vlay.addWidget(rq)
        self.result_table.setRowCount(0)
        self._table_hint.setText("표시할 추천이 없습니다.")
        self._last_result = None
        # 단계 완료 시 순차 노출
        self._weather_frame.setVisible(False)
        self._hist_frame.setVisible(False)
        self._last_use_frame.setVisible(False)
        self._pest_frame.setVisible(False)
        self._reason_frame.setVisible(False)
        self._table_card.setVisible(False)

    def _style_conclusion(
        self,
        kind: str,
        title: str,
        line1: str,
        line2: str,
        line3: str,
    ) -> None:
        bg, border, accent, title_c = _CONCLUSION_STYLES.get(
            kind, _CONCLUSION_STYLES["watch"]
        )
        self._conclusion_frame.setStyleSheet(
            f"""
            QFrame#conclusionCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
                border-left: 5px solid {accent};
            }}
            """
        )
        self._conclusion_title.setText(title)
        self._conclusion_title.setStyleSheet(
            f"font-weight: bold; color: {title_c}; border: none; background: transparent;"
        )
        self._conclusion_line1.setText(line1)
        self._conclusion_line2.setText(line2)
        self._conclusion_line3.setText(line3)

    def _clear_grid(self, g: QGridLayout) -> None:
        while g.count():
            it = g.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _add_kv_row(
        self,
        g: QGridLayout,
        row: int,
        k: str,
        v: str,
        value_style: str = _KV_VALUE_STYLE,
        value_word_wrap: bool = True,
    ) -> None:
        lk = QLabel(k)
        lk.setStyleSheet(_KV_LABEL_STYLE)
        lv = QLabel(v)
        lv.setStyleSheet(value_style)
        lv.setWordWrap(value_word_wrap)
        lv.setToolTip(v)
        g.addWidget(lk, row, 0, Qt.AlignmentFlag.AlignLeft)
        g.addWidget(lv, row, 1, Qt.AlignmentFlag.AlignLeft)

    def _clear_pest_rows(self) -> None:
        while self._pest_vlay.count():
            it = self._pest_vlay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _clear_reason_rows(self) -> None:
        while self._reason_vlay.count():
            it = self._reason_vlay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _risk_badge_style(self, risk: str) -> str:
        r = (risk or "").strip()
        if r == "위험":
            return "color:#9A3412; font-weight:bold; border:none; background:transparent;"
        if r == "주의":
            return "color:#B7791F; font-weight:bold; border:none; background:transparent;"
        if r == "낮음":
            return "color:#5A6B5C; border:none; background:transparent;"
        return _BODY_STYLE

    def _pest_row_widget(self, name: str, score: int) -> QWidget:
        risk = _risk_label_from_score(score)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        nm = QLabel(name)
        nm.setStyleSheet(
            "font-weight: bold; color: #2D3748; border: none; background: transparent;"
        )
        sc = QLabel(f"점수 {score}")
        sc.setStyleSheet(_BODY_STYLE)
        rk = QLabel(risk)
        rk.setStyleSheet(self._risk_badge_style(risk))
        h.addWidget(nm, 1)
        h.addWidget(sc, 0)
        h.addWidget(rk, 0, Qt.AlignmentFlag.AlignRight)
        return row

    def _bullet_label(self, text: str, sub: bool = False) -> QLabel:
        lb = QLabel(f"•  {_truncate(text, 120)}")
        lb.setWordWrap(True)
        lb.setStyleSheet(_CAPTION_STYLE if sub else _BODY_STYLE)
        return lb

    def _section_reason_title(self, text: str) -> QLabel:
        lb = QLabel(text)
        lb.setStyleSheet(
            "font-weight: bold; color: #4A5568; border: none; background: transparent; margin-top: 4px;"
        )
        return lb

    def _reveal_cards_by_step(self, step_title: str) -> None:
        """단계 완료 시 연계 카드 즉시 노출."""
        step = str(step_title or "")
        if step == "기상 영향 분석":
            self._weather_frame.setVisible(True)
        elif step == "작업 이력 확인":
            self._hist_frame.setVisible(True)
        elif step == "병해충 위험 판단":
            self._pest_frame.setVisible(True)
        elif step == "방제 필요 여부 판단":
            self._reason_frame.setVisible(True)
        elif step == "최근 사용 농약 확인":
            self._last_use_frame.setVisible(True)
        elif step == "최종 방제 추천":
            self._table_card.setVisible(True)

    def _to_korean_date(self, raw: object) -> str:
        """YYYY-MM-DD / M/D / M월 D일을 M월 D일로 변환."""
        s = _plain(raw)
        if not s:
            return ""
        try:
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                d = datetime.strptime(s[:10], "%Y-%m-%d")
                return f"{d.month}월 {d.day}일"
            if "/" in s:
                mm, dd = s.split("/", 1)
                return f"{int(mm)}월 {int(dd)}일"
            if "월" in s and "일" in s:
                mm = s.split("월", 1)[0].strip()
                dd = s.split("월", 1)[1].split("일", 1)[0].strip()
                return f"{int(mm)}월 {int(dd)}일"
        except Exception:
            return s
        return s

    def _recheck_date_text(self, rec_raw: object) -> str:
        """추천일 - 4일을 M월 D일로 반환. 계산 실패 시 빈 문자열."""
        s = _plain(rec_raw)
        if not s:
            return ""
        try:
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                d = datetime.strptime(s[:10], "%Y-%m-%d")
            elif "/" in s:
                mm, dd = s.split("/", 1)
                d = datetime(datetime.now().year, int(mm), int(dd))
            elif "월" in s and "일" in s:
                mm = s.split("월", 1)[0].strip()
                dd = s.split("월", 1)[1].split("일", 1)[0].strip()
                d = datetime(datetime.now().year, int(mm), int(dd))
            else:
                return ""
            r = d.date().fromordinal(d.date().toordinal() - 4)
            return f"{r.month}월 {r.day}일"
        except Exception:
            return ""

    def _load_recent_pesticide_history(self) -> list[dict]:
        """worker payload 기반 최근 방제 이력(최근 2일, 약제 1건당 1행)."""
        payload = self._progress_payloads.get("재고·사용이력 보정") or {}
        hist_rows = payload.get("recent_use_history")
        if not isinstance(hist_rows, list):
            return []
        recent_days: List[str] = []
        out: List[dict] = []
        seen_rows: set[tuple[str, str, str, str]] = set()
        day_limit = 2
        for row in hist_rows:
            if not isinstance(row, dict):
                continue
            use_dt = str(row.get("use_dt") or "").strip()
            item_nm = str(row.get("item_nm") or "").strip()
            if not use_dt or not item_nm:
                continue
            if use_dt not in recent_days:
                if len(recent_days) >= day_limit:
                    continue
                recent_days.append(use_dt)
            spec_nm = str(row.get("spec_nm") or "").strip()
            qty = _fmt_num(row.get("use_qty"), 0)
            item_txt = f"{item_nm}({spec_nm}) * {qty}" if spec_nm else f"{item_nm} * {qty}"
            key = (use_dt, item_nm, spec_nm, qty)
            if key in seen_rows:
                continue
            seen_rows.add(key)
            out.append({"use_dt": use_dt, "items_text": item_txt})
        return out

    def _render_weather_preview(self) -> None:
        w: Dict[str, object] = {}
        fc: Dict[str, object] = {}
        p0 = self._progress_payloads.get("날씨 데이터 수집") or {}
        p1 = self._progress_payloads.get("기상 분석") or {}
        if isinstance(p1.get("weather_summary"), dict):
            w = dict(p1.get("weather_summary") or {})
        elif isinstance(p0.get("weather_summary"), dict):
            w = dict(p0.get("weather_summary") or {})
        if isinstance(p1.get("forecast_summary"), dict):
            fc = dict(p1.get("forecast_summary") or {})
        self._clear_grid(self._weather_grid)
        wsrc = str(w.get("weather_source") or "").strip().lower()
        row = 0
        if "default" in wsrc:
            self._add_kv_row(self._weather_grid, row, "최근3일 평균기온", "-")
            row += 1
            self._add_kv_row(self._weather_grid, row, "최근7일 강수량", "-")
            row += 1
            self._add_kv_row(self._weather_grid, row, "최근7일 강우일수", "-")
            row += 1
            self._add_kv_row(self._weather_grid, row, "평균 습도", "-")
            row += 1
        else:
            self._add_kv_row(
                self._weather_grid, row, "최근3일 평균기온", f"{_fmt_num(w.get('avg_temp_3d'), 1)}℃"
            )
            row += 1
            self._add_kv_row(
                self._weather_grid, row, "최근7일 강수량", f"{_fmt_num(w.get('rain_sum_7d'), 1)}mm"
            )
            row += 1
            self._add_kv_row(
                self._weather_grid, row, "최근7일 강우일수", f"{_fmt_num(w.get('rain_days_7d'))}일"
            )
            row += 1
            self._add_kv_row(
                self._weather_grid, row, "평균 습도", f"{_fmt_num(w.get('avg_humidity_7d'))}%"
            )
            row += 1
        self._add_kv_row(self._weather_grid, row, "향후3일 강수합", f"{_fmt_num(fc.get('rain_sum_3d'), 1)}mm")
        row += 1
        self._add_kv_row(self._weather_grid, row, "향후3일 강우일수", f"{_fmt_num(fc.get('rain_days_3d'))}일")
        row += 1
        self._add_kv_row(self._weather_grid, row, "중기 첫 비 예정일", _plain(fc.get("mid_first_rain_date")) or "없음")

    def _render_history_preview(self) -> None:
        payload = self._progress_payloads.get("작업 이력 분석") or {}
        ws = payload.get("work_status") if isinstance(payload.get("work_status"), dict) else {}
        spd = ws.get("spray_interval_days")
        lsd = ws.get("last_spray_date")
        self._clear_grid(self._hist_grid)
        self._add_kv_row(self._hist_grid, 0, "최근 방제", "있음" if ws.get("recent_spray_yn") else "없음")
        self._add_kv_row(self._hist_grid, 1, "마지막 방제일", _plain(lsd) or "없음")
        self._add_kv_row(self._hist_grid, 2, "기준 주기", f"{_fmt_num(spd)}일" if spd else "미확인")
        self._add_kv_row(self._hist_grid, 3, "봉지 여부", "봉지 후" if ws.get("after_bag_yn") else "봉지 전")

    @staticmethod
    def _weather_error_reason(code: str) -> str:
        c = str(code or "").strip()
        if c == "429":
            return "일간 트래픽을 초과하였습니다."
        if c == "101":
            return "인증키 실패입니다."
        if c in ("201", "202", "203", "204"):
            return "파라미터 오류입니다."
        if c == "301":
            return "데이터가 없습니다."
        if c == "500":
            return "서버 오류입니다."
        if c == "999":
            return "기타 오류입니다."
        return "원본 확인이 필요합니다."

    def _weather_notice_lines(self, weather_card: Dict[str, Any]) -> tuple[str, str]:
        wsrc = str(weather_card.get("weather_source") or "").strip().lower()
        if "default" not in wsrc:
            return "", ""
        err_code = str(weather_card.get("weather_error_code") or "").strip()
        reason = self._weather_error_reason(err_code)
        return (
            "농업 기상 기본 관측 데이터를 가져올 수 없습니다.",
            f"원인 : {reason}",
        )

    def _render_pest_preview(self) -> None:
        p0 = self._progress_payloads.get("날씨 데이터 수집") or {}
        p1 = self._progress_payloads.get("기상 분석") or {}
        w: Dict[str, object] = {}
        if isinstance(p1.get("weather_summary"), dict):
            w = dict(p1.get("weather_summary") or {})
        elif isinstance(p0.get("weather_summary"), dict):
            w = dict(p0.get("weather_summary") or {})
        if str(w.get("weather_source") or "").strip().lower() != "api":
            self._clear_pest_rows()
            self._pest_vlay.addWidget(self._bullet_label("기상 데이터 부족", sub=True))
            return
        payload = self._progress_payloads.get("병해충 위험도 계산") or {}
        ps = payload.get("pest_scores") if isinstance(payload.get("pest_scores"), list) else []
        top = sorted(
            [x for x in ps if isinstance(x, dict)],
            key=lambda x: int(x.get("score") or 0),
            reverse=True,
        )
        self._clear_pest_rows()
        if not top:
            self._pest_vlay.addWidget(self._bullet_label("병해충 데이터가 없습니다.", sub=True))
            return
        for p in top:
            nm = str(p.get("pest_nm") or "").strip()
            sc = int(p.get("score") or 0)
            if nm:
                self._pest_vlay.addWidget(self._pest_row_widget(nm, sc))

    def _render_reason_preview(self) -> None:
        self._clear_reason_rows()
        self._reason_vlay.addWidget(self._bullet_label("병해충 위험과 작업 이력을 바탕으로 방제 필요 여부를 정리했습니다."))

    def _render_recent_use_preview(self) -> None:
        self._clear_grid(self._last_use_grid)
        rows = self._load_recent_pesticide_history()
        if not rows:
            self._add_kv_row(
                self._last_use_grid, 0, "최근 사용", "기록 없음", value_style=_BODY_STYLE, value_word_wrap=False
            )
            return
        for i, h in enumerate(rows):
            dt = _plain(h.get("use_dt"))
            items_text = _plain(h.get("items_text"))
            dt_short = ""
            if len(dt) >= 10 and dt[4] == "-" and dt[7] == "-":
                try:
                    d = datetime.strptime(dt[:10], "%Y-%m-%d")
                    dt_short = f"{d.month}/{d.day}"
                except Exception:
                    dt_short = dt
            else:
                dt_short = dt or "날짜 미상"
            self._add_kv_row(
                self._last_use_grid,
                i,
                dt_short,
                items_text or "기록 없음",
                value_style=_BODY_STYLE,
                value_word_wrap=False,
            )

    def _on_log_toggle(self, checked: bool) -> None:
        self._log_wrap.setVisible(checked)
        self._log_toggle.setText("분석 로그 접기" if checked else "분석 로그 펼치기")
        if checked:
            self._log_te.setMaximumHeight(160)
        else:
            self._log_te.setMaximumHeight(72)

    def _render_step_labels(self) -> None:
        for i, lab in enumerate(self._step_labels):
            title = self._ui_step_order[i]
            title_disp = title
            if title == "기상 영향 분석":
                ew = float(self._substep_elapsed_sec.get("날씨 데이터 수집", 0.0) or 0.0)
                ef = float(self._substep_elapsed_sec.get("기상 분석", 0.0) or 0.0)
                if ew > 0 or ef > 0:
                    title_disp = f"{title} (수집 {ew:.1f}초 / 분석 {ef:.1f}초)"
            if title in self._step_elapsed_sec:
                elapsed = self._step_elapsed_sec.get(title, 0.0)
                lab.setText(f"✔  {title_disp} ({elapsed:.1f}초)")
                lab.setStyleSheet(
                    "color: #5A6B5C; border: none; background: transparent;"
                )
            elif title == self._active_step:
                lab.setText(f"▶  {title_disp}")
                lab.setStyleSheet(
                    "color: #2D5A27; font-weight: bold; border: none; background: transparent;"
                )
            else:
                lab.setText(f"○  {title_disp}")
                lab.setStyleSheet(
                    "color: #A0AEC0; border: none; background: transparent;"
                )

    # —— 기존 슬롯 호환 ——
    def set_farm_cd(self, farm_cd: str) -> None:
        self.farm_cd = str(farm_cd or "")

    def _reset_step_labels(self) -> None:
        self._step_started_at = {}
        self._step_elapsed_sec = {}
        self._substep_elapsed_sec = {}
        self._active_step = ""
        self._render_step_labels()

    def _set_all_steps_done(self) -> None:
        now_ts = time.perf_counter()
        for title in self._ui_step_order:
            if title not in self._step_elapsed_sec:
                st = self._step_started_at.get(title, now_ts)
                self._step_elapsed_sec[title] = max(0.0, now_ts - st)
        self._active_step = ""
        self._render_step_labels()

    def _on_progress_step(self, title: str) -> None:
        mapped = _WORKER_TO_UI_STEP.get(str(title), "")
        if not mapped or mapped not in self._ui_step_order:
            return
        now_ts = time.perf_counter()
        if mapped == self._active_step:
            # 동일 UI 단계(예: 날씨 데이터 수집→기상 분석) 재진입 시 시작시각은 유지하고 미리보기만 갱신
            if mapped == "기상 영향 분석":
                self._render_weather_preview()
            return
        if self._active_step and self._active_step not in self._step_elapsed_sec:
            started = self._step_started_at.get(self._active_step, now_ts)
            self._step_elapsed_sec[self._active_step] = max(0.0, now_ts - started)
            self._reveal_cards_by_step(self._active_step)

        # "병해충 위험 판단" 다음 단계("방제 필요 여부 판단")는 백엔드 단일 step으로 넘어가므로 UI에서 즉시 완료 처리
        if mapped == "최근 사용 농약 확인" and "방제 필요 여부 판단" not in self._step_elapsed_sec:
            if "병해충 위험 판단" in self._step_elapsed_sec:
                self._step_elapsed_sec["방제 필요 여부 판단"] = 0.1
            else:
                self._step_elapsed_sec["방제 필요 여부 판단"] = 0.0
            self._reveal_cards_by_step("방제 필요 여부 판단")

        self._active_step = mapped
        self._step_started_at[mapped] = now_ts
        self._render_step_labels()
        self._reveal_cards_by_step(mapped)
        if mapped == "기상 영향 분석":
            self._render_weather_preview()
        elif mapped == "작업 이력 확인":
            self._render_history_preview()
        elif mapped == "병해충 위험 판단":
            self._render_pest_preview()
        elif mapped == "방제 필요 여부 판단":
            self._render_reason_preview()
        elif mapped == "최근 사용 농약 확인":
            self._render_recent_use_preview()

    def _on_progress_percent(self, v: object) -> None:
        try:
            self._prog.setValue(max(0, min(100, int(v))))
        except (TypeError, ValueError):
            pass

    def _on_progress_payload(self, step_name: str, payload: dict) -> None:
        step = str(step_name or "").strip()
        if not step:
            return
        payload_map = dict(payload or {})
        self._progress_payloads[step] = payload_map
        # 기상 통합 단계(수집/분석) 실측 시간 분리 표시용
        try:
            if step == "날씨 데이터 수집" and payload_map.get("elapsed_weather_summary") is not None:
                self._substep_elapsed_sec["날씨 데이터 수집"] = float(
                    payload_map.get("elapsed_weather_summary") or 0.0
                )
            elif step == "기상 분석" and payload_map.get("elapsed_forecast_summary") is not None:
                self._substep_elapsed_sec["기상 분석"] = float(
                    payload_map.get("elapsed_forecast_summary") or 0.0
                )
        except (TypeError, ValueError):
            pass
        self._render_step_labels()
        mapped = _WORKER_TO_UI_STEP.get(step, "")
        if mapped == "기상 영향 분석":
            self._render_weather_preview()
        elif mapped == "작업 이력 확인":
            self._render_history_preview()
        elif mapped == "병해충 위험 판단":
            self._render_pest_preview()
        elif mapped == "최근 사용 농약 확인":
            self._render_recent_use_preview()

    def _append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_te.append(f"[{ts}] {message}")
        cur = self._log_te.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self._log_te.setTextCursor(cur)
        lines = self._log_te.toPlainText().splitlines()
        if len(lines) > _LOG_MAX_LINES:
            self._log_te.setPlainText("\n".join(lines[-_LOG_MAX_LINES:]))
            cur = self._log_te.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._log_te.setTextCursor(cur)

    def _prepare_run_ui(self) -> None:
        self.ai_btn.setEnabled(False)
        self._progress_payloads = {}
        self._apply_empty_placeholders()
        self._reset_step_labels()
        self._log_te.clear()
        self._prog.setValue(0)
        self._lbl_run_state.setText("진행 중")
        self._log_toggle.setChecked(True)
        self._on_log_toggle(True)

    def _finish_success_ui(self) -> None:
        self.ai_btn.setEnabled(True)
        self._set_all_steps_done()
        for st in self._ui_step_order:
            self._reveal_cards_by_step(st)
        self._append_log("분석 완료")
        self._prog.setValue(100)
        self._lbl_run_state.setText("완료")
        self._log_toggle.setChecked(False)
        self._on_log_toggle(False)

    def _finish_failed_ui(self, user_message: str) -> None:
        self.ai_btn.setEnabled(True)
        self._prog.setValue(0)
        self._lbl_run_state.setText("")
        self._log_toggle.setChecked(False)
        self._on_log_toggle(False)
        QMessageBox.warning(self, "분석 실패", user_message)

    def _run_recommend(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self._prepare_run_ui()
        self._thread = QThread()
        self._worker = AiRecommendWorker(self.farm_cd)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress_step.connect(self._on_progress_step)
        self._worker.progress_log.connect(self._append_log)
        self._worker.progress_percent.connect(self._on_progress_percent)
        self._worker.progress_payload.connect(self._on_progress_payload)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)

        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._thread_finished_cleanup)

        self._thread.start()

    def _thread_finished_cleanup(self) -> None:
        self._thread = None
        self._worker = None

    def _on_worker_finished(self, res: dict) -> None:
        # 최종 단계 완료 시점에서 결과 카드 데이터를 확정 렌더
        self._reveal_cards_by_step("최종 방제 추천")
        self._apply_recommend_result(res)
        self._finish_success_ui()

    def _on_worker_failed(self, msg: str) -> None:
        self._finish_failed_ui(msg)

    def _conclusion_bucket(self, res: dict) -> tuple[str, str]:
        """현장형 결론 톤 — 점수 구간·방제 이력만 사용(채점 로직 변경 없음)."""
        summ = res.get("input_summary") or {}
        pests_detail = res.get("pests") or []
        scores = [
            int(p.get("score") or 0)
            for p in pests_detail
            if isinstance(p, dict)
        ]
        mx = max(scores) if scores else 0
        recent_spray = bool(summ.get("recent_spray_yn"))

        if not scores:
            if recent_spray:
                return "hold", "경과 관찰"
            return "watch", "예방 권장"

        if any(s >= 7 for s in scores):
            return "need", "방제 필요"
        if recent_spray and mx <= 3:
            return "hold", "경과 관찰"
        if any(4 <= s <= 6 for s in scores):
            return "watch", "예방 관찰"
        if 1 <= mx <= 3:
            return "watch", "예방 관찰"
        if mx == 0 and not recent_spray:
            return "watch", "예방 권장"
        if mx == 0 and recent_spray:
            return "hold", "경과 관찰"
        return "watch", "예방 관찰"

    def _no_pesticide_reason_lines(self, res: dict) -> list[str]:
        """추천 약제가 없을 때 납득용 설명(입력 요약·히트 only, 새 추론 없음)."""
        lines: list[str] = []
        summ = res.get("input_summary") or {}
        if not summ:
            lines.append("현장 잎·가지·과실을 확인하며 필요 시 다시 분석해 보세요.")
            return lines

        if res.get("empty_hint") == "no_top_pest":
            lines.append(
                "모니터링 기준을 넘은 병해충이 없어 이번에는 약제 목록을 두지 않았습니다."
            )

        if summ.get("recent_spray_yn"):
            lines.append("최근 방제 이력이 있어 추가 투입은 현장 소모·잔류를 보며 판단하면 됩니다.")

        try:
            rain = float(summ.get("rain_sum_7d") or 0)
        except (TypeError, ValueError):
            rain = 0.0
        if rain < 15:
            lines.append("최근 강수가 많지 않아 병해충 압력이 상대적으로 낮은 편으로 볼 수 있습니다.")

        try:
            temp = float(summ.get("avg_temp_3d") or 0)
        except (TypeError, ValueError):
            temp = 0.0
        if 0 < temp < 12:
            lines.append("기온이 낮은 편이라 확산이 다르게 느껴질 수 있습니다. 현장 관찰을 병행해 주세요.")

        if not summ.get("weather_trace_ok"):
            lines.append(
                "기상 API를 쓰지 못해 기본 환경값을 참고했으니, 밭 상태를 함께 보시는 것이 좋습니다."
            )

        if len(lines) < 2:
            lines.append("당분간 관찰과 물리 적제·포장 후 생리를 우선 살펴보셔도 됩니다.")

        return lines[:6]

    def _apply_recommend_result(self, res: dict) -> None:
        self._last_result = dict(res)
        cards = res.get("analysis_cards") or {}
        weather_card = cards.get("weather_analysis") or {}
        weather_notice_1, weather_notice_2 = self._weather_notice_lines(weather_card)
        weather_source = str(weather_card.get("weather_source") or "").strip().lower()
        weather_error = weather_source != "api"
        summ = res.get("input_summary") or {}
        pests_detail: list = res.get("pests") or []
        pests = res.get("pests_simple")
        if pests is None:
            raw = pests_detail
            if raw and isinstance(raw[0], dict):
                pests = [
                    (str(p.get("pest_nm", "")), int(p.get("score") or 0))
                    for p in raw
                ]
            else:
                pests = raw
        pests = pests or []
        rows = res.get("pesticides") or []

        # 기준일·생육 (데이터 구조 변경 없음: 표시만 오늘 기준 + summary 내 생육)
        base_dt = datetime.now().strftime("%Y-%m-%d")
        self._lbl_base_dt.setText(f"기준일 {base_dt}")
        gs = str(summ.get("growth_stage") or "—") if summ else "—"
        self._lbl_growth.setText(f"생육 {gs}")

        kind, headline = self._conclusion_bucket(res)

        # 병해충 한 줄 요약: 이름(등급) 형태
        sorted_p: list = []
        if pests_detail and all(isinstance(p, dict) for p in pests_detail):
            sorted_p = sorted(
                pests_detail,
                key=lambda x: int(x.get("score") or 0),
                reverse=True,
            )
        elif pests:
            sorted_p = [
                {"pest_nm": str(n), "score": int(s or 0)}
                for n, s in pests
                if str(n or "").strip()
            ]
            sorted_p.sort(key=lambda x: int(x.get("score") or 0), reverse=True)

        pest_bits: list[str] = []
        for p in sorted_p[:3]:
            if isinstance(p, dict):
                nm = str(p.get("pest_nm", "") or "").strip()
                sc = int(p.get("score") or 0)
            else:
                continue
            if nm:
                pest_bits.append(f"{nm}({_risk_label_from_score(sc)})")

        if pest_bits:
            l1 = "주요 병해충: " + ", ".join(pest_bits)
        else:
            l1 = "주요 병해충: 확인 중(목록 없음)"

        top_pnm = [str(r.get("name") or "") for r in rows if r.get("name")]
        top_pnm = [_plain(x) for x in top_pnm if _plain(x)][:3]
        if top_pnm:
            l2 = "추천 농약: " + ", ".join(top_pnm)
        elif rows:
            l2 = "추천 농약: (표 참고)"
        else:
            l2 = "추천 농약: 없음"

        l3 = ""
        danger_pest = next(
            (
                p
                for p in pests_detail
                if isinstance(p, dict) and int(p.get("score") or 0) >= 7
            ),
            None,
        )
        if danger_pest:
            rs = danger_pest.get("reasons") or []
            if rs:
                l3 = _truncate(str(rs[0]), 52)
            else:
                l3 = f"{danger_pest.get('pest_nm', '')} — 위험 구간, 우선 점검 권장"
        elif not rows:
            npl = self._no_pesticide_reason_lines(res)
            if npl:
                l3 = _truncate(npl[0], 52)
        elif summ.get("summary_line"):
            l3 = _truncate(str(summ.get("summary_line")), 52)
        elif top_pnm and rows:
            l3 = _truncate(_plain(rows[0].get("main_reason")), 52)

        # 방제 시점 레이어(spray_timing) — 결론 카드는 타이밍 중심 3줄
        st = res.get("spray_timing")
        if isinstance(st, dict) and str(st.get("trigger", "")) != "":
            trigger = str(st.get("trigger") or "none")
            need_sp = bool(st.get("need_spray"))

            recommended_date = st.get("recommended_date")
            recommended_period = _plain(st.get("recommended_period") or "")
            decision_type = _plain(st.get("decision_type") or "")
            due_date = st.get("due_date")
            due_k = self._to_korean_date(due_date)

            rec_k = self._to_korean_date(recommended_date)
            recheck_k = self._recheck_date_text(recommended_date)
            fb_sel = bool(st.get("fallback_selected"))

            line1 = ""
            line2 = ""
            line3 = ""

            # 타이틀: decision_type 우선(방제 직후·rain_lock은 trigger/need_sp와 무관하게 명시)
            if decision_type == "hold_after_spray":
                title_sp = "방제 직후 대기"
                kind_sp = "hold"
            elif decision_type == "rain_lock":
                title_sp = "비 전 선행 방제 권장"
                kind_sp = "need"
            elif trigger == "pest":
                title_sp = "즉시 방제 필요"
                kind_sp = "need"
            elif need_sp:
                title_sp = "이번 주 방제 권장"
                kind_sp = "watch"
            else:
                title_sp = "경과 관찰"
                kind_sp = "hold"

            if decision_type in ("mid_term_prediction", "wait_due", "observe"):
                title_sp = "재확인 안내"
                kind_sp = "watch"
            elif (
                recommended_date
                and recommended_period
                and decision_type
                not in (
                    "hold_after_spray",
                    "rain_lock",
                    "mid_term_prediction",
                    "wait_due",
                    "observe",
                    "urgent",
                )
            ):
                title_sp = "지금 실행 권장"
                kind_sp = "need"

            # rain_lock: 즉시 실행 분기보다 먼저 3줄 고정(연속 강우·마지막 안전 창)
            if decision_type == "rain_lock" and recommended_date and recommended_period:
                line1 = f"{rec_k} {recommended_period} 방제하세요."
                if fb_sel:
                    line2 = "조건이 다소 불리하지만 현장에서는 덜 나쁜 시점을 잡는 편이 유리합니다."
                else:
                    line2 = "기준일 전후 강우가 이어져 비 오기 전 선행 방제가 유리합니다."
                line3 = _truncate(str(st.get("reason") or ""), 80)
            elif recommended_date and recommended_period:
                line1 = f"{rec_k} {recommended_period} 방제하세요."
                if fb_sel:
                    line2 = "조건이 다소 불리하지만 현재 예보 기준으로는 가장 나은 선택입니다."
                else:
                    line2 = "비 영향이 없고 작업하기 좋은 조건입니다."
                line3 = _truncate(str(st.get("reason") or ""), 80)
            elif decision_type == "mid_term_prediction":
                line1 = "지금은 방제할 시점이 아닙니다."
                line2 = f"{rec_k} 전후로 준비하세요." if rec_k else "권장 시점 전후로 준비하세요."
                line3 = (
                    f"{recheck_k} 이후 다시 확인하면 정확한 시간까지 안내됩니다."
                    if recheck_k
                    else "다시 확인하면 정확한 시간까지 안내됩니다."
                )
            elif decision_type == "hold_after_spray":
                line1 = "최근 방제가 완료되어 추가 방제는 필요 없습니다."
                line2 = f"다음 방제는 {due_k} 전후로 예상됩니다." if due_k else (f"다음 방제는 {rec_k} 전후로 예상됩니다." if rec_k else "다음 방제 예정일 전후로 예상됩니다.")
                recheck_base = due_date if due_date else recommended_date
                line3 = f"{self._recheck_date_text(recheck_base)} 이후 다시 확인하세요." if self._recheck_date_text(recheck_base) else "며칠 후 다시 확인하세요."
            elif decision_type in ("wait_due", "observe"):
                line1 = "지금은 방제 시점이 아닙니다."
                line2 = f"{due_k} 전후로 준비하세요." if due_k else (f"{rec_k} 전후로 준비하세요." if rec_k else "다음 도래일 전후로 준비하세요.")
                recheck_base = due_date if due_date else recommended_date
                line3 = f"{self._recheck_date_text(recheck_base)} 이후 다시 확인하세요." if self._recheck_date_text(recheck_base) else "며칠 후 다시 확인하세요."
            else:
                if rec_k:
                    line1 = f"{rec_k} {recommended_period}".strip() + " 방제를 권장합니다."
                    line2 = _truncate(str(st.get("reason") or ""), 80)
                    line3 = f"{recheck_k} 이후 다시 확인하세요." if recheck_k else _truncate(f"{l1} · {l2}", 80)
                else:
                    line1 = "현재 방제 시점을 판단하기 위한 정보가 부족합니다."
                    line2 = "날씨를 확인한 후 다시 시도하세요."
                    line3 = _truncate(f"{l1} · {l2}", 80)
            if weather_notice_1:
                line2 = weather_notice_1
                line3 = weather_notice_2
            self._style_conclusion(kind_sp, title_sp, line1, line2, line3)
        else:
            if weather_notice_1:
                l2 = weather_notice_1
                l3 = weather_notice_2
            self._style_conclusion(kind, headline, l1, l2, l3)
        if weather_error:
            self._style_conclusion(
                "watch",
                "기상 데이터 확인 필요",
                "농업 기상 기본 관측 데이터를 가져올 수 없습니다.",
                weather_notice_2 or "원인 : 원본 확인이 필요합니다.",
                "내일 다시 확인해 주세요.",
            )

        # 분석 카드(기상/작업이력/최근 사용 1건)
        hist_card = cards.get("work_history_analysis") or {}
        last_use = cards.get("last_pesticide_use") or {}

        self._clear_grid(self._hist_grid)
        self._add_kv_row(
            self._hist_grid,
            0,
            "최근 방제",
            "있음" if hist_card.get("recent_spray_yn") else "없음",
        )
        self._add_kv_row(
            self._hist_grid,
            1,
            "마지막 방제일",
            _plain(hist_card.get("last_spray_date")) or "없음",
        )
        de = hist_card.get("days_elapsed")
        self._add_kv_row(
            self._hist_grid,
            2,
            "경과일수",
            f"{_fmt_num(de)}일" if de is not None else "미확인",
        )
        self._add_kv_row(
            self._hist_grid,
            3,
            "기준 주기",
            f"{_fmt_num(hist_card.get('spray_interval_days'))}일",
        )
        self._add_kv_row(
            self._hist_grid,
            4,
            "봉지 여부",
            "봉지 후" if hist_card.get("after_bag_yn") else "봉지 전",
        )
        self._add_kv_row(
            self._hist_grid,
            5,
            "주기 도래 예정일",
            _plain(hist_card.get("due_date")) or "미확인",
        )

        self._clear_grid(self._weather_grid)
        wsrc_card = str(weather_card.get("weather_source") or "").strip().lower()
        row = 0
        if "default" in wsrc_card:
            self._add_kv_row(self._weather_grid, row, "최근3일 평균기온", "-")
            row += 1
            self._add_kv_row(self._weather_grid, row, "최근7일 강수량", "-")
            row += 1
            self._add_kv_row(self._weather_grid, row, "최근7일 강우일수", "-")
            row += 1
            self._add_kv_row(self._weather_grid, row, "평균 습도", "-")
            row += 1
        else:
            self._add_kv_row(
                self._weather_grid, row, "최근3일 평균기온", f"{_fmt_num(weather_card.get('avg_temp_3d'), 1)}℃"
            )
            row += 1
            self._add_kv_row(
                self._weather_grid, row, "최근7일 강수량", f"{_fmt_num(weather_card.get('rain_sum_7d'), 1)}mm"
            )
            row += 1
            self._add_kv_row(
                self._weather_grid, row, "최근7일 강우일수", f"{_fmt_num(weather_card.get('rain_days_7d'))}일"
            )
            row += 1
            self._add_kv_row(
                self._weather_grid, row, "평균 습도", f"{_fmt_num(weather_card.get('avg_humidity_7d'))}%"
            )
            row += 1
        self._add_kv_row(
            self._weather_grid, row, "향후3일 강수합", f"{_fmt_num(weather_card.get('rain_sum_3d_forecast'), 1)}mm"
        )
        row += 1
        self._add_kv_row(
            self._weather_grid, row, "향후3일 강우일수", f"{_fmt_num(weather_card.get('rain_days_3d_forecast'))}일"
        )
        row += 1
        self._add_kv_row(
            self._weather_grid, row, "중기 첫 비 예정일", _plain(weather_card.get("mid_first_rain_date")) or "없음"
        )
        row += 1
        self._add_kv_row(
            self._weather_grid, row, "추천구간 평균풍속", f"{_fmt_num(weather_card.get('selected_avg_wind'), 1)}m/s"
        )
        row += 1
        self._add_kv_row(
            self._weather_grid, row, "추천구간 최대풍속", f"{_fmt_num(weather_card.get('selected_max_wind'), 1)}m/s"
        )
        row += 1
        self._add_kv_row(
            self._weather_grid, row, "24h 최대 강수확률", f"{_fmt_num(weather_card.get('selected_next24h_max_pop'))}%"
        )
        row += 1
        self._add_kv_row(
            self._weather_grid, row, "24h 누적강수량", f"{_fmt_num(weather_card.get('selected_next24h_sum_pcp'), 1)}mm"
        )

        self._clear_grid(self._last_use_grid)
        # 최근 방제 이력: 최근 2일 내 약제 1건당 1행 표시
        hist_rows = self._load_recent_pesticide_history()
        ridx = 0
        if hist_rows:
            for h in hist_rows:
                dt = _plain(h.get("use_dt"))
                items_text = _plain(h.get("items_text")) or "기록 없음"
                dt_short = dt
                if len(dt) >= 10 and dt[4] == "-" and dt[7] == "-":
                    try:
                        d = datetime.strptime(dt[:10], "%Y-%m-%d")
                        dt_short = f"{d.month}/{d.day}"
                    except Exception:
                        dt_short = dt
                self._add_kv_row(
                    self._last_use_grid,
                    ridx,
                    dt_short or "날짜 미상",
                    items_text,
                    value_style=_BODY_STYLE,
                    value_word_wrap=False,
                )
                ridx += 1
        elif last_use:
            self._add_kv_row(
                self._last_use_grid,
                ridx,
                _plain(last_use.get("use_dt")) or "날짜 미상",
                f"{_plain(last_use.get('item_nm')) or '약제 미상'} × {_fmt_num(last_use.get('use_qty'), 0)}",
                value_style=_BODY_STYLE,
                value_word_wrap=False,
            )
            ridx += 1
        else:
            self._add_kv_row(
                self._last_use_grid, ridx, "최근 사용", "기록 없음", value_style=_BODY_STYLE, value_word_wrap=False
            )

        # 병해충 행 (점수 상위 표시, 등급은 점수 구간으로만 표시)
        self._clear_pest_rows()
        if weather_error:
            self._pest_vlay.addWidget(self._bullet_label("기상 데이터 부족", sub=True))
        elif pests_detail and all(isinstance(p, dict) for p in pests_detail):
            shown = 0
            for p in sorted(
                pests_detail,
                key=lambda x: int(x.get("score") or 0),
                reverse=True,
            ):
                nm = str(p.get("pest_nm", "") or "").strip()
                if not nm:
                    continue
                sc = int(p.get("score") or 0)
                self._pest_vlay.addWidget(self._pest_row_widget(nm, sc))
                shown += 1
        elif pests:
            for n, s in pests:
                self._pest_vlay.addWidget(
                    self._pest_row_widget(str(n), int(s or 0))
                )
        else:
            pe = QLabel("병해충 목록을 불러오지 못했습니다. 다시 실행해 주세요.")
            pe.setStyleSheet(_BODY_STYLE)
            pe.setWordWrap(True)
            self._pest_vlay.addWidget(pe)

        # 추천 이유 — 항상 한 줄 이상
        self._clear_reason_rows()
        pest_bullets: list[str] = []
        for p in pests_detail:
            if not isinstance(p, dict):
                continue
            pest_nm = str(p.get("pest_nm", "") or "").strip()
            if not pest_nm:
                continue
            for r in (p.get("reasons") or [])[:2]:
                t = str(r).strip()
                if t:
                    pest_bullets.append(f"{pest_nm}: {t}")
        tag_lines: list[str] = []
        for pr in rows:
            if not isinstance(pr, dict):
                continue
            nm = _plain(pr.get("name"))
            if not nm:
                continue
            mr = _plain(pr.get("main_reason") or "")
            tags = pr.get("reason_tags") or []
            if mr:
                tag_lines.append(f"{nm}: {mr}")
            elif tags:
                tag_lines.append(f"{nm}: {', '.join(str(t) for t in tags)}")

        if pest_bullets:
            self._reason_vlay.addWidget(self._section_reason_title("병해충 판단 근거"))
            for b in pest_bullets[:6]:
                self._reason_vlay.addWidget(self._bullet_label(b))
        if tag_lines:
            self._reason_vlay.addWidget(
                self._section_reason_title("추천 농약 선정 이유")
            )
            for b in tag_lines[:6]:
                self._reason_vlay.addWidget(self._bullet_label(b))
        if not rows:
            self._reason_vlay.addWidget(
                self._section_reason_title("추천 농약이 없는 이유")
            )
            for line in self._no_pesticide_reason_lines(res):
                self._reason_vlay.addWidget(self._bullet_label(line))
        elif not pest_bullets and not tag_lines:
            mr0 = _plain(rows[0].get("main_reason")) if rows else ""
            if mr0:
                self._reason_vlay.addWidget(self._bullet_label(mr0))
            else:
                sl = summ.get("summary_line") if summ else ""
                self._reason_vlay.addWidget(
                    self._bullet_label(
                        _truncate(str(sl), 120)
                        if sl
                        else "현장 잎·가지 상태를 확인하며 단계적으로 대응하면 됩니다."
                    )
                )

        # 표
        self.result_table.setRowCount(0)
        for i, prow in enumerate(rows):
            self.result_table.insertRow(i)
            self.result_table.setItem(
                i, 0, QTableWidgetItem(_plain(prow.get("name")))
            )
            self.result_table.setItem(
                i, 1, QTableWidgetItem(str(prow.get("score", 0)))
            )
            src = str(prow.get("source") or "candidate")
            if src == "stock":
                src_lbl = "보유"
            elif src == "db":
                src_lbl = "등록"
            else:
                src_lbl = "추천"
            self.result_table.setItem(i, 2, QTableWidgetItem(src_lbl))
            qty_lbl = _plain(prow.get("stock_qty_label") or "")
            if not qty_lbl:
                qty_lbl = "—"
            self.result_table.setItem(i, 3, QTableWidgetItem(qty_lbl))
            mr = _plain(prow.get("main_reason") or "")
            if not mr:
                tags = prow.get("reason_tags") or []
                mr = ", ".join(str(t) for t in tags) if tags else ""
            self.result_table.setItem(i, 4, QTableWidgetItem(mr))

        if rows:
            self._table_hint.setText(f"총 {len(rows)}건 · 1순위 강조")
            for col in range(5):
                it = self.result_table.item(0, col)
                if it is not None:
                    it.setBackground(QBrush(_ROW_TOP_BG))
        else:
            if res.get("empty_hint") == "no_top_pest":
                self._table_hint.setText(
                    "이번에는 약제 목록을 두지 않았습니다. 병해충·근거를 함께 확인하세요."
                )
            else:
                self._table_hint.setText(
                    "표시할 추천 약제가 없습니다. 상단 요약·근거를 참고하세요."
                )

    def _on_recommend_row_clicked(self, row: int, col: int) -> None:
        """추천 표 행 클릭 시 점수 상세 팝업(읽기 전용)."""
        try:
            res = self._last_result or {}
            rows = res.get("pesticides") or []
            if not isinstance(rows, list) or row < 0 or row >= len(rows):
                return
            self._show_score_detail(rows[row])
        except Exception:
            return

    def _show_score_detail(self, item: dict) -> None:
        detail = item.get("score_detail") or {}
        main_reason = str(detail.get("main_reason") or "-").strip() or "-"
        sr = detail.get("support_reasons") or []
        if not isinstance(sr, list):
            sr = []
        sr_lines = [str(x).strip() for x in sr if str(x).strip()]
        if not sr_lines:
            sr_lines = ["-"]
        name = _plain(item.get("name") or "")
        total = str(item.get("score", 0))

        # 실제 반영된 항목만 판단형 문장으로 구성(0점 항목 제외)
        d_base = 5
        src = str(item.get("source") or "")
        d_stock = 2 if src == "stock" else (1 if src == "db" else 0)
        d_pest = 3 if src in ("stock", "db") else 2
        d_context = 0
        d_multi = 0
        d_recent = 0
        d_limit = 0

        situation_reason = str(detail.get("situation_reason") or "")
        if "연속 강우" in situation_reason:
            d_context = 4
        elif "강우 전" in situation_reason or "선행 방제" in situation_reason:
            d_context = 3
        elif "긴급" in situation_reason:
            d_context = 4
        if any("내우성 부족" in x for x in sr_lines):
            d_context = -3

        cc = int(item.get("cover_count") or 0)
        if cc >= 3:
            d_multi = 3
        elif cc >= 2:
            d_multi = 2

        recent_reason = str(detail.get("recent_reason") or "")
        if "(-5)" in recent_reason:
            d_recent = -5
        elif "(-3)" in recent_reason:
            d_recent = -3

        if any("사용 제한 임계" in x for x in sr_lines):
            d_limit = -3

        pest_name = ""
        covered = item.get("covered_pests") or []
        if isinstance(covered, list) and covered:
            pest_name = str(covered[0]).strip()
        if not pest_name:
            pest_name = "병해충"

        comp_lines: list[str] = [f"- 기본 점수: {d_base:+d}"]
        if d_stock != 0:
            comp_lines.append(f"- 현재 보유 농약: {d_stock:+d}" if d_stock > 0 else f"- 현재 보유 농약: {d_stock:+d}")
        if d_pest != 0:
            comp_lines.append(f"- {pest_name} 직접 대응: {d_pest:+d}")
        if d_context > 0:
            if "강우 전" in situation_reason or "선행 방제" in situation_reason:
                comp_lines.append(f"- 강우 전 예방 방제에 적합: {d_context:+d}")
            elif "긴급" in situation_reason:
                comp_lines.append(f"- 지금 바로 방제 필요: {d_context:+d}")
            else:
                comp_lines.append(f"- 비 오기 전 방제에 적합: {d_context:+d}")
        elif d_context < 0:
            comp_lines.append(f"- 비에 약해 효과 유지가 불리함: {d_context:+d}")
        if d_multi > 0:
            comp_lines.append(f"- 여러 병해충 동시 대응: {d_multi:+d}")
        if d_recent < 0:
            comp_lines.append(f"- 최근 사용 이력 있음: {d_recent:+d}")
        if d_limit < 0:
            comp_lines.append(f"- 사용 횟수 제한 근접: {d_limit:+d}")

        # 표기 합계와 실제 총점이 다르면 숨은 보정만 한 줄로 보여 사용자가 혼동하지 않게 함
        try:
            total_int = int(item.get("score", 0))
        except (TypeError, ValueError):
            total_int = 0
        shown_sum = d_base + d_stock + d_pest + d_context + d_multi + d_recent + d_limit
        drift = total_int - shown_sum
        if drift != 0:
            comp_lines.append(f"- 현장 조건 종합 반영: {drift:+d}")

        text = (
            f"[점수 상세]\n\n"
            f"농약: {name}\n"
            f"총점: {total}\n\n"
            f"■ 주요 이유\n"
            f"- {main_reason}\n\n"
            f"■ 보조 이유\n"
            f"- " + "\n- ".join(sr_lines) + "\n\n"
            f"■ 점수 구성\n"
            + "\n".join(comp_lines)
            + "\n"
        )
        mb = QMessageBox(self)
        mb.setWindowTitle("점수 상세")
        mb.setIcon(QMessageBox.Icon.NoIcon)
        mb.setText(text)
        mb.setStandardButtons(QMessageBox.StandardButton.Ok)
        mb.setStyleSheet(_SCORE_DETAIL_POPUP_STYLE)
        mb.exec()
