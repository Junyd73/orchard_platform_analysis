# -*- coding: utf-8 -*-
"""관찰 AI 분석·공식 농약정보 탭."""

from __future__ import annotations

from functools import partial
from urllib.parse import urlparse

from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.ai.image_sanitize import MAX_PHOTOS_PER_ANALYSIS
from core.ai.observation_ai_service import is_observation_ai_available
from core.db_manager import DBManager
from core.observation_media import load_thumb_pixmap, resolve_media_path
from core.observation_stage3 import ANALYSIS_STATUS_FAILED, ANALYSIS_STATUS_OK
from core.pesticide.pesticide_service import is_psis_available
from ui.styles import MainStyles
from ui.widgets.observation.ai_analysis_worker import ObservationAiWorker
from ui.widgets.observation.psis_search_worker import PsisSearchWorker

AI_DISCLAIMER = (
    "AI 분석은 사진에 기반한 참고 후보이며 병해충 확진 결과가 아닙니다."
)
PESTI_DISCLAIMER = (
    "농약은 현재 작물과 병해충에 등록된 제품인지 공식 정보를 다시 확인하고, "
    "제품 라벨과 안전사용기준을 준수하십시오."
)
CONSENT_MSG = (
    "선택한 사진이 OpenAI 서버로 전송됩니다.\n"
    "EXIF/GPS는 제거·축소 후 전송되며, 농장·사용자 정보는 보내지 않습니다.\n\n"
    "동의하고 분석을 진행하시겠습니까?"
)
PSIS_ALLOWED_HOSTS = frozenset({"psis.rda.go.kr"})
HIST_ROLE_ID = Qt.ItemDataRole.UserRole
PESTI_ROLE_DATA = Qt.ItemDataRole.UserRole

# AI 탭 레이아웃 높이 (요약 가독성 우선)
PHOTO_LIST_MAX_H = 88
SUMMARY_MIN_H = 170
SUMMARY_STRETCH = 3
CAND_LIST_MIN_H = 96
CAND_LIST_MAX_H = 150
PESTI_LIST_MIN_H = 150
PESTI_LIST_STRETCH = 2
HIST_LIST_MIN_H = 72
HIST_LIST_MAX_H = 100


def _is_allowed_psis_url(url: str) -> bool:
    try:
        p = urlparse(str(url or "").strip())
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    return host in PSIS_ALLOWED_HOSTS


class AiAnalysisPanel(QWidget):
    """AI 분석 + 사용자 확정 + 공식 농약정보 조회."""

    aiBusyChanged = pyqtSignal(bool)
    analysisUpdated = pyqtSignal()

    def __init__(
        self,
        parent=None,
        *,
        db=None,
        farm_cd: str = "",
        user_id: str = "",
        obs_id: str = "",
        read_only: bool = False,
    ):
        super().__init__(parent)
        self.db = db
        self.farm_cd = farm_cd or ""
        self.user_id = user_id or ""
        self.obs_id = obs_id or ""
        self.read_only = read_only
        self._busy = False
        self._req_id = 0
        self._thread: QThread | None = None
        self._worker = None
        self._thread_req_id = 0
        self._ai_pending: dict | None = None
        self._psis_busy = False
        self._psis_req_id = 0
        self._psis_thread: QThread | None = None
        self._psis_worker = None
        self._psis_thread_req_id = 0
        self._psis_pending: dict | None = None
        self._pending_similar = None
        self._analysis: dict | None = None
        self._active_analysis_id: str | None = None
        self._viewing_history = False
        self._photos: list[dict] = []
        self._build_ui()
        self._apply_gate()
        if self.obs_id:
            self.reload()

    def is_busy(self) -> bool:
        return bool(self._busy or self._psis_busy)

    def set_context(self, farm_cd, user_id, obs_id, *, db=None):
        if self.is_busy():
            # 진행 중 작업을 stale 처리. 강제 종료 없이 완료 시 quit·finished로 정리.
            self._req_id += 1
            self._psis_req_id += 1
            self._ai_pending = None
            self._psis_pending = None
            self._pending_similar = None
        if db is not None:
            self.db = db
        self.farm_cd = farm_cd or ""
        self.user_id = user_id or ""
        self.obs_id = obs_id or ""
        self._apply_gate()
        if not self.is_busy():
            self.reload()

    def set_obs_id(self, obs_id: str):
        self.set_context(self.farm_cd, self.user_id, obs_id, db=self.db)

    def _db_path(self) -> str:
        if self.db and getattr(self.db, "db_name", None):
            return str(self.db.db_name)
        return ""

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #2D3748; border: none; padding-top: 4px;"
        )
        return lbl

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self.lbl_gate = QLabel("기본 정보 저장 후 AI 분석을 사용할 수 있습니다.")
        self.lbl_gate.setStyleSheet("color: #718096; font-size: 10px; border: none;")
        self.lbl_gate.setWordWrap(True)
        lay.addWidget(self.lbl_gate)

        self.lbl_ai_disc = QLabel(AI_DISCLAIMER)
        self.lbl_ai_disc.setWordWrap(True)
        self.lbl_ai_disc.setStyleSheet("color: #C05621; font-size: 10px; border: none;")
        lay.addWidget(self.lbl_ai_disc)

        self.lbl_cfg = QLabel("")
        self.lbl_cfg.setWordWrap(True)
        self.lbl_cfg.setStyleSheet("color: #4A5568; font-size: 10px; border: none;")
        lay.addWidget(self.lbl_cfg)

        self.lbl_progress = QLabel("")
        self.lbl_progress.setVisible(False)
        self.lbl_progress.setStyleSheet("color: #2B6CB0; font-size: 10px; border: none;")
        lay.addWidget(self.lbl_progress)

        self.lbl_view_mode = QLabel("")
        self.lbl_view_mode.setStyleSheet("color: #553C9A; font-size: 10px; border: none;")
        self.lbl_view_mode.setVisible(False)
        lay.addWidget(self.lbl_view_mode)

        lay.addWidget(self._section_label("분석 대상 사진"))
        self.photo_list = QListWidget()
        self.photo_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.photo_list.setMaximumHeight(PHOTO_LIST_MAX_H)
        lay.addWidget(self.photo_list)

        btns = QHBoxLayout()
        self.btn_analyze = QPushButton("AI 분석")
        self.btn_reanalyze = QPushButton("재분석")
        self.btn_back_current = QPushButton("현재 결과로 돌아가기")
        self.btn_analyze.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_reanalyze.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_back_current.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_reanalyze.clicked.connect(self._on_analyze)
        self.btn_back_current.clicked.connect(self._on_back_current)
        self.btn_back_current.setVisible(False)
        btns.addWidget(self.btn_analyze)
        btns.addWidget(self.btn_reanalyze)
        btns.addWidget(self.btn_back_current)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.lbl_status = QLabel("분석 상태: -")
        self.lbl_status.setStyleSheet("font-size: 10px; border: none;")
        lay.addWidget(self.lbl_status)

        self.lbl_last_fail = QLabel("")
        self.lbl_last_fail.setWordWrap(True)
        self.lbl_last_fail.setStyleSheet("color: #C53030; font-size: 10px; border: none;")
        self.lbl_last_fail.setVisible(False)
        lay.addWidget(self.lbl_last_fail)

        lay.addWidget(self._section_label("전체 요약"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setMinimumHeight(SUMMARY_MIN_H)
        self.txt_summary.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.txt_summary.setStyleSheet(MainStyles.INPUT_CENTER)
        self.txt_summary.setPlaceholderText("AI 분석 요약이 여기에 표시됩니다.")
        lay.addWidget(self.txt_summary, SUMMARY_STRETCH)

        lay.addWidget(self._section_label("후보 · 신뢰도"))
        self.cand_list = QListWidget()
        self.cand_list.setMinimumHeight(CAND_LIST_MIN_H)
        self.cand_list.setMaximumHeight(CAND_LIST_MAX_H)
        self.cand_list.currentRowChanged.connect(self._on_cand_sel)
        lay.addWidget(self.cand_list)

        conf = QHBoxLayout()
        conf.addWidget(QLabel("확정 병해충명"))
        self.ed_confirm = QLineEdit()
        self.ed_confirm.setStyleSheet(MainStyles.INPUT_CENTER)
        conf.addWidget(self.ed_confirm, 1)
        self.btn_confirm = QPushButton("사용자 확정")
        self.btn_confirm.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_confirm.clicked.connect(self._on_confirm)
        conf.addWidget(self.btn_confirm)
        lay.addLayout(conf)

        self.lbl_confirm = QLabel("사용자 확정: (없음)")
        self.lbl_confirm.setStyleSheet("font-size: 10px; border: none; color: #2F855A;")
        lay.addWidget(self.lbl_confirm)

        lay.addWidget(self._section_label("공식 등록정보 조회"))
        self.lbl_pesti_disc = QLabel(PESTI_DISCLAIMER)
        self.lbl_pesti_disc.setWordWrap(True)
        self.lbl_pesti_disc.setStyleSheet("color: #C05621; font-size: 10px; border: none;")
        lay.addWidget(self.lbl_pesti_disc)

        crow = QHBoxLayout()
        crow.addWidget(QLabel("작물명"))
        self.cb_crop = QComboBox()
        self.cb_crop.setStyleSheet(MainStyles.COMBO)
        self.cb_crop.setEditable(True)
        crow.addWidget(self.cb_crop, 1)
        lay.addLayout(crow)

        pbtn = QHBoxLayout()
        self.btn_pesti = QPushButton("공식 등록정보 조회")
        self.btn_refresh = QPushButton("최신 정보 다시 조회")
        self.btn_source = QPushButton("공식 출처 열기")
        self.btn_pesti.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_refresh.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_source.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_pesti.clicked.connect(lambda: self._on_pesti_search(False))
        self.btn_refresh.clicked.connect(lambda: self._on_pesti_search(True))
        self.btn_source.clicked.connect(self._on_open_source)
        pbtn.addWidget(self.btn_pesti)
        pbtn.addWidget(self.btn_refresh)
        pbtn.addWidget(self.btn_source)
        pbtn.addStretch(1)
        lay.addLayout(pbtn)

        self.lbl_pesti_meta = QLabel("")
        self.lbl_pesti_meta.setWordWrap(True)
        self.lbl_pesti_meta.setStyleSheet("font-size: 10px; border: none;")
        lay.addWidget(self.lbl_pesti_meta)

        self.pesti_list = QListWidget()
        self.pesti_list.setMinimumHeight(PESTI_LIST_MIN_H)
        self.pesti_list.itemDoubleClicked.connect(self._on_open_source)
        lay.addWidget(self.pesti_list, PESTI_LIST_STRETCH)

        lay.addWidget(self._section_label("분석 이력"))
        self.hist = QListWidget()
        self.hist.setMinimumHeight(HIST_LIST_MIN_H)
        self.hist.setMaximumHeight(HIST_LIST_MAX_H)
        self.hist.itemClicked.connect(self._on_hist_clicked)
        self.hist.itemDoubleClicked.connect(self._on_hist_clicked)
        lay.addWidget(self.hist)

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _apply_gate(self):
        has = bool(self.obs_id)
        self.lbl_gate.setVisible(not has)
        ai_ok = is_observation_ai_available()
        ps_ok = is_psis_available()
        hints = []
        if not ai_ok:
            hints.append("OPENAI_API_KEY 미설정 — AI 분석 비활성")
        if not ps_ok:
            hints.append("ORCHARD_PSIS_API_KEY 미설정 — 공식 조회·캐시만 가능")
        self.lbl_cfg.setText(" / ".join(hints))
        viewing_hist = self._viewing_history
        can = has and not self.read_only and not self.is_busy() and not viewing_hist
        self.btn_analyze.setEnabled(can and ai_ok)
        self.btn_reanalyze.setEnabled(can and ai_ok)
        conf_ok = can and bool(self._analysis)
        self.btn_confirm.setEnabled(conf_ok)
        self.ed_confirm.setEnabled(conf_ok)
        confirmed = self._confirmed_name()
        pesti_ok = (
            has
            and not self.read_only
            and not self.is_busy()
            and bool(confirmed)
            and not viewing_hist
        )
        self.btn_pesti.setEnabled(pesti_ok)
        self.btn_refresh.setEnabled(pesti_ok)
        self.cb_crop.setEnabled(pesti_ok)
        self.btn_source.setEnabled(bool(self.pesti_list.currentItem()))
        self.btn_back_current.setVisible(viewing_hist)

    def _set_ai_busy(self, busy: bool, text: str = ""):
        prev = self.is_busy()
        self._busy = bool(busy)
        self._sync_busy_ui(text)
        if prev != self.is_busy():
            self.aiBusyChanged.emit(self.is_busy())

    def _set_psis_busy(self, busy: bool, text: str = ""):
        prev = self.is_busy()
        self._psis_busy = bool(busy)
        self._sync_busy_ui(text)
        if prev != self.is_busy():
            self.aiBusyChanged.emit(self.is_busy())

    def _sync_busy_ui(self, text: str = ""):
        self.lbl_progress.setVisible(self.is_busy())
        if text:
            self.lbl_progress.setText(text)
        elif not self.is_busy():
            self.lbl_progress.setText("")
        self._apply_gate()

    def reload(self):
        self._viewing_history = False
        self.lbl_view_mode.setVisible(False)
        self.btn_back_current.setVisible(False)
        self.photo_list.clear()
        self.cand_list.clear()
        self.hist.clear()
        self.pesti_list.clear()
        self._analysis = None
        self._photos = []
        self.txt_summary.clear()
        self.ed_confirm.clear()
        self.lbl_confirm.setText("사용자 확정: (없음)")
        self.lbl_status.setText("분석 상태: -")
        self.lbl_pesti_meta.setText("")
        self.lbl_last_fail.setVisible(False)
        self._load_crops()
        if not self.db or not self.farm_cd or not self.obs_id:
            self._apply_gate()
            return
        self._photos = self.db.list_observation_photos(self.farm_cd, self.obs_id) or []
        for p in self._photos:
            it = QListWidgetItem(str(p.get("original_nm") or p.get("photo_id") or ""))
            it.setData(Qt.ItemDataRole.UserRole, p.get("photo_id"))
            pm = load_thumb_pixmap(p.get("thumb_path") or "", 64)
            if pm is not None and not pm.isNull():
                it.setIcon(QIcon(pm))
            self.photo_list.addItem(it)
        if self.photo_list.count():
            self.photo_list.item(0).setSelected(True)

        obs = self.db.get_observation(self.farm_cd, self.obs_id) or {}
        self.lbl_status.setText(f"분석 상태: {obs.get('ai_status') or 'NONE'}")

        self._analysis = self.db.get_latest_ai_analysis(self.farm_cd, self.obs_id)
        self._active_analysis_id = (
            str(self._analysis.get("analysis_id")) if self._analysis else None
        )
        attempt = self.db.get_latest_ai_attempt(self.farm_cd, self.obs_id)
        if (
            attempt
            and str(attempt.get("status") or "") == ANALYSIS_STATUS_FAILED
            and (
                not self._analysis
                or attempt.get("analysis_id") != self._analysis.get("analysis_id")
            )
        ):
            self.lbl_last_fail.setText(
                f"최근 재분석 실패: [{attempt.get('error_code') or '-'}] "
                f"{attempt.get('error_message') or ''} "
                f"({attempt.get('analyzed_at') or ''})"
            )
            self.lbl_last_fail.setVisible(True)
            if self._analysis and self._confirmed_name():
                self.lbl_last_fail.setText(
                    self.lbl_last_fail.text()
                    + "\n기존 사용자 확정 결과는 유지됩니다."
                )

        self._render_analysis(self._analysis, history_view=False)
        for h in self.db.list_ai_analysis_history(self.farm_cd, self.obs_id) or []:
            aid = str(h.get("analysis_id") or "")
            mark = "실패" if str(h.get("status")) == ANALYSIS_STATUS_FAILED else "성공"
            it = QListWidgetItem(
                f"{h.get('analyzed_at') or ''} · {mark} · "
                f"{(h.get('overall_summary') or h.get('error_message') or '')[:40]}"
            )
            it.setData(HIST_ROLE_ID, aid)
            self.hist.addItem(it)
        self._apply_gate()
        name = self._confirmed_name()
        if name:
            self._load_cached_pesti(name)

    def _load_crops(self):
        self.cb_crop.clear()
        self.cb_crop.addItem("선택", "")
        try:
            from core.pesticide_manager import PesticideManager

            if self.db and self.farm_cd:
                mgr = PesticideManager(self.db)
                for nm in mgr.farm_psis_sync_crop_names(self.farm_cd) or []:
                    self.cb_crop.addItem(str(nm), str(nm))
        except Exception:
            pass

    def _render_analysis(self, a: dict | None, *, history_view: bool):
        self.cand_list.clear()
        self._analysis = a
        self._viewing_history = history_view
        if history_view:
            self.lbl_view_mode.setText("과거 분석 조회 중 (읽기 전용)")
            self.lbl_view_mode.setVisible(True)
        else:
            self.lbl_view_mode.setVisible(False)
        if not a:
            self.txt_summary.setPlainText("")
            self._apply_gate()
            return
        lines = [
            f"분석ID: {a.get('analysis_id') or '-'}",
            f"상태: {a.get('status') or '-'} | 품질: {a.get('image_quality') or '-'}",
            f"분석가능: {'Y' if a.get('analysis_possible') else 'N'} | "
            f"사진수: {a.get('input_photo_count') or len(a.get('photo_ids') or [])}",
            f"모델: {a.get('model_nm') or '-'} / {a.get('analyzed_at') or ''}",
            "",
            str(a.get("overall_summary") or ""),
            "",
            "추가 촬영: " + ", ".join(a.get("additional_photos") or []),
            "즉시 대응: " + ", ".join(a.get("immediate_actions") or []),
            str(a.get("warning") or AI_DISCLAIMER),
        ]
        if a.get("error_code") or a.get("error_message"):
            lines.append(
                f"오류: [{a.get('error_code') or '-'}] {a.get('error_message') or ''}"
            )
        self.txt_summary.setPlainText("\n".join(lines))
        for c in a.get("candidates") or []:
            conf = c.get("confidence")
            try:
                conf_s = f"{float(conf)*100:.0f}%"
            except (TypeError, ValueError):
                conf_s = "-"
            text = (
                f"[{c.get('category')}] {c.get('name_ko')} ({conf_s}) "
                f"urgency={c.get('urgency')}"
            )
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, c)
            it.setToolTip(
                "근거: "
                + ", ".join(c.get("visual_evidence") or [])
                + "\n"
                + str(c.get("differential_reason") or "")
            )
            self.cand_list.addItem(it)
        conf_c = None
        for c in a.get("candidates") or []:
            if str(c.get("selected_yn") or "") == "Y":
                conf_c = c
                break
        if conf_c:
            nm = conf_c.get("confirmed_name") or conf_c.get("name_ko")
            self.lbl_confirm.setText(
                f"사용자 확정: {nm} ({conf_c.get('confirmed_at') or ''})"
            )
            self.ed_confirm.setText(str(nm or ""))
        else:
            self.lbl_confirm.setText("사용자 확정: (없음)")
            if history_view:
                self.ed_confirm.clear()
        self._apply_gate()

    def _confirmed_name(self) -> str:
        # 현재 활성 확정명은 history view가 아니거나, 활성 분석 기준
        a = self._analysis if not self._viewing_history else None
        if a is None and self.db and self.obs_id:
            a = self.db.get_latest_ai_analysis(self.farm_cd, self.obs_id)
        for c in (a or {}).get("candidates") or []:
            if str(c.get("selected_yn") or "") == "Y":
                return str(c.get("confirmed_name") or c.get("name_ko") or "").strip()
        return ""

    def _selected_photo_paths(self) -> tuple[list[str], list[str], int]:
        """반환: (ids, paths, selected_count_before_cap)."""
        ids, paths = [], []
        items = list(self.photo_list.selectedItems())
        selected_count = len(items)
        for it in items:
            pid = it.data(Qt.ItemDataRole.UserRole)
            p = next((x for x in self._photos if x.get("photo_id") == pid), None)
            if not p:
                continue
            abs_p = resolve_media_path(p.get("file_path") or "")
            if abs_p is None or not abs_p.is_file():
                continue
            ids.append(str(pid))
            paths.append(str(abs_p))
        return ids, paths, selected_count

    def _on_cand_sel(self, row: int):
        if row < 0 or self._viewing_history:
            return
        it = self.cand_list.item(row)
        c = it.data(Qt.ItemDataRole.UserRole) or {}
        if not self.ed_confirm.text().strip():
            self.ed_confirm.setText(str(c.get("name_ko") or ""))

    def _on_analyze(self):
        if not self.obs_id or self.is_busy() or self.read_only or self._viewing_history:
            return
        if not is_observation_ai_available():
            QMessageBox.information(self, "설정", "OPENAI_API_KEY를 설정해 주세요.")
            return
        ids, paths, sel_n = self._selected_photo_paths()
        if sel_n > MAX_PHOTOS_PER_ANALYSIS:
            QMessageBox.information(
                self, "안내", "사진은 최대 3장까지 선택할 수 있습니다."
            )
            return
        if not paths:
            QMessageBox.information(self, "안내", "분석할 사진을 1~3장 선택해 주세요.")
            return
        ans = QMessageBox.question(
            self,
            "외부 전송 동의",
            CONSENT_MSG,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self._req_id += 1
        req = self._req_id
        crop = self.cb_crop.currentText().strip()
        self._ai_pending = None
        self._set_ai_busy(True, "AI 분석 중…")

        thread = QThread()
        worker = ObservationAiWorker(
            self._db_path(),
            self.farm_cd,
            self.obs_id,
            self.user_id,
            ids,
            paths,
            crop,
            req,
        )
        worker.moveToThread(thread)
        self._thread = thread
        self._worker = worker
        self._thread_req_id = req
        thread.started.connect(worker.run)
        worker.progress.connect(partial(self._on_ai_progress, req))
        worker.completed.connect(partial(self._on_ai_completed, req, thread))
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(partial(self._on_ai_thread_finished, req, thread))
        thread.start()

    def _on_ai_progress(self, req_id, text):
        if req_id != self._req_id:
            return
        self.lbl_progress.setText(str(text))

    def _on_ai_completed(self, req_id: int, thread: QThread, payload: dict):
        try:
            if (
                req_id == self._req_id
                and self._thread is thread
                and self._thread_req_id == req_id
            ):
                self._ai_pending = dict(payload or {})
        finally:
            # stale·current 무관하게 해당 QThread는 반드시 종료
            if thread is not None:
                thread.quit()

    def _on_ai_thread_finished(self, req_id: int, thread: QThread):
        # 전역 최신 req_id와 달라도, 현재 보관 thread이면 참조·busy를 정리한다.
        if self._thread is not thread or self._thread_req_id != req_id:
            return
        self._thread = None
        self._worker = None
        self._thread_req_id = 0
        pending = self._ai_pending
        self._ai_pending = None
        is_current = req_id == self._req_id
        self._set_ai_busy(False, "")
        self.reload()
        self.analysisUpdated.emit()
        if not is_current or not pending:
            return
        if pending.get("ok"):
            QMessageBox.information(
                self, "AI 분석", "분석이 완료되었습니다. 후보를 확인하고 확정해 주세요."
            )
        else:
            QMessageBox.warning(
                self,
                "AI 분석",
                f"[{pending.get('error_code') or '-'}] "
                f"{pending.get('error_message') or '분석에 실패했습니다.'}",
            )

    def _on_confirm(self):
        if (
            not self._analysis
            or self.read_only
            or self.is_busy()
            or self._viewing_history
        ):
            return
        row = self.cand_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "안내", "확정할 후보를 선택해 주세요.")
            return
        c = self.cand_list.item(row).data(Qt.ItemDataRole.UserRole) or {}
        name = self.ed_confirm.text().strip() or str(c.get("name_ko") or "")
        if not name:
            QMessageBox.warning(self, "검증", "확정 병해충명을 입력해 주세요.")
            return
        ok, msg = self.db.confirm_ai_candidate(
            self.farm_cd,
            self._analysis.get("analysis_id"),
            int(c.get("candidate_seq") or row + 1),
            name,
            self.user_id,
            obs_id=self.obs_id,
        )
        if not ok:
            QMessageBox.warning(self, "확정 실패", msg)
            return
        QMessageBox.information(self, "확정", msg)
        self.reload()
        self.analysisUpdated.emit()

    def _on_hist_clicked(self, item: QListWidgetItem):
        if not item or not self.db:
            return
        aid = str(item.data(HIST_ROLE_ID) or "").strip()
        if not aid:
            return
        detail = self.db.get_ai_analysis(self.farm_cd, aid)
        if not detail:
            QMessageBox.information(self, "이력", "분석 상세를 찾을 수 없습니다.")
            return
        self._render_analysis(detail, history_view=True)

    def _on_back_current(self):
        self.reload()

    def _on_pesti_search(self, force: bool):
        if self.is_busy() or self.read_only or self._viewing_history:
            return
        disease = self._confirmed_name()
        if not disease:
            QMessageBox.information(self, "안내", "병해충 후보를 먼저 확정해 주세요.")
            return
        crop = self.cb_crop.currentText().strip()
        if not crop or crop == "선택":
            QMessageBox.information(self, "안내", "작물명을 선택하거나 입력해 주세요.")
            return

        self._psis_req_id += 1
        req = self._psis_req_id
        aid = self._active_analysis_id
        self._psis_pending = None
        self._pending_similar = None
        self._set_psis_busy(True, "공식 등록정보 조회 중…")
        self._start_psis(req, crop, disease, force, allow_similar=False, analysis_id=aid)

    def _start_psis(self, req, crop, disease, force, allow_similar, analysis_id):
        thread = QThread()
        worker = PsisSearchWorker(
            self._db_path(),
            self.farm_cd,
            self.obs_id,
            self.user_id,
            crop,
            disease,
            analysis_id,
            force,
            allow_similar,
            req,
        )
        worker.moveToThread(thread)
        self._psis_thread = thread
        self._psis_worker = worker
        self._psis_thread_req_id = req
        thread.started.connect(worker.run)
        worker.progress.connect(partial(self._on_psis_progress, req))
        worker.completed.connect(
            partial(self._on_psis_completed, req, thread, crop, disease, force)
        )
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(partial(self._on_psis_thread_finished, req, thread))
        thread.start()

    def _on_psis_progress(self, req_id, text):
        if req_id != self._psis_req_id:
            return
        self.lbl_progress.setText(str(text))

    def _on_psis_completed(self, req_id, thread, crop, disease, force, payload: dict):
        try:
            is_current = (
                req_id == self._psis_req_id
                and self._psis_thread is thread
                and self._psis_thread_req_id == req_id
            )
            if not is_current:
                return
            items = (payload or {}).get("items") or []
            want_similar = (
                bool((payload or {}).get("ok"))
                and not items
                and not (payload or {}).get("from_cache")
                and not force
                and is_psis_available()
            )
            if want_similar:
                ans = QMessageBox.question(
                    self,
                    "유사명 검색",
                    "정확한 등록 결과가 없습니다.\n유사명 검색을 진행할까요?\n"
                    "(결과는 ‘유사명 검색 결과 — 정확 등록정보가 아님’으로 표시됩니다)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if ans == QMessageBox.StandardButton.Yes:
                    self._pending_similar = (crop, disease)
                    self._psis_pending = None
                    return
            self._psis_pending = dict(payload or {})
        finally:
            if thread is not None:
                thread.quit()

    def _on_psis_thread_finished(self, req_id: int, thread: QThread):
        # 전역 최신 psis_req_id와 달라도, 현재 보관 thread이면 참조·busy를 정리한다.
        if self._psis_thread is not thread or self._psis_thread_req_id != req_id:
            return
        self._psis_thread = None
        self._psis_worker = None
        self._psis_thread_req_id = 0

        is_current = req_id == self._psis_req_id
        pending_similar = self._pending_similar
        self._pending_similar = None
        if is_current and pending_similar:
            crop, disease = pending_similar
            self._psis_req_id += 1
            req = self._psis_req_id
            # busy 유지 (False로 풀지 않음)
            self._set_psis_busy(True, "유사명 검색 중…")
            self._start_psis(
                req, crop, disease, True, True, self._active_analysis_id
            )
            return

        payload = self._psis_pending if is_current else None
        self._psis_pending = None
        self._set_psis_busy(False, "")
        if not is_current:
            self.reload()
            return
        if not payload:
            return
        if not payload.get("ok") and not payload.get("items"):
            QMessageBox.warning(
                self,
                "공식 조회",
                f"[{payload.get('error_code')}] {payload.get('error_message')}",
            )
            return
        self._render_pesti(payload)

    def _load_cached_pesti(self, disease: str):
        crop = self.cb_crop.currentText().strip()
        if not crop or crop == "선택":
            return
        rows = self.db.list_pesticide_snapshots(
            self.farm_cd, self.obs_id, crop_name=crop, disease_name=disease
        )
        if rows:
            self._render_pesti(
                {
                    "ok": True,
                    "items": rows,
                    "from_cache": True,
                    "fetched_at": rows[0].get("fetched_at"),
                    "match_type": rows[0].get("match_type"),
                    "label": "과거 조회자료",
                }
            )

    def _render_pesti(self, payload: dict):
        self.pesti_list.clear()
        mt = str(payload.get("match_type") or "")
        if mt == "SIMILAR":
            label = "유사명 검색 결과 — 정확 등록정보가 아님"
        else:
            label = payload.get("label") or "공식 등록정보 조회 결과"
        meta = f"{label} · 조회시각: {payload.get('fetched_at') or '-'}"
        if payload.get("from_cache"):
            meta += " · 과거 조회자료"
        self.lbl_pesti_meta.setText(meta)
        for it in payload.get("items") or []:
            src = it.get("source_nm") or "농촌진흥청 농약안전정보시스템"
            src_url = it.get("source_url") or "https://psis.rda.go.kr/"
            text = (
                f"[공식 등록정보] {it.get('brand_name') or '-'} / "
                f"{it.get('pesticide_name') or '-'} ({it.get('company_name') or '-'})\n"
                f"작물:{it.get('crop_name') or '-'} | 적용병해충:{it.get('disease_name') or '-'} | "
                f"용도:{it.get('purpose_name') or '-'}\n"
                f"주성분·함량:{it.get('active_ingredient') or '-'}\n"
                f"작용기작:{it.get('action_mechanism') or '-'} | "
                f"사용방법:{it.get('usage_method') or '-'}\n"
                f"희석/사용량:{it.get('dilution') or '-'} | "
                f"수확전:{it.get('preharvest_interval') or '-'} | "
                f"최대횟수:{it.get('max_use_count') or '-'}\n"
                f"독성:{it.get('toxicity') or '-'} / 어독성:{it.get('fish_toxicity') or '-'}\n"
                f"출처:{src} | {src_url}"
            )
            item = QListWidgetItem(text)
            item.setData(PESTI_ROLE_DATA, dict(it))
            self.pesti_list.addItem(item)
        if self.pesti_list.count():
            self.pesti_list.setCurrentRow(0)
        self._apply_gate()

    def _on_open_source(self, *_args):
        it = self.pesti_list.currentItem()
        if not it:
            QMessageBox.information(self, "안내", "약제 항목을 선택해 주세요.")
            return
        data = it.data(PESTI_ROLE_DATA) or {}
        url = str(data.get("source_url") or "https://psis.rda.go.kr/").strip()
        if not _is_allowed_psis_url(url):
            QMessageBox.warning(
                self,
                "출처 열기",
                "허용되지 않은 출처 주소입니다. psis.rda.go.kr 만 열 수 있습니다.",
            )
            return
        QDesktopServices.openUrl(QUrl(url))
