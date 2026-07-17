# -*- coding: utf-8 -*-
"""관찰 사진 패널 — 썸네일 목록·추가·삭제·정렬·원본 열기."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.db_manager import DBManager
from core.observation_media import (
    OBS_ALLOWED_EXTS,
    compensate_photo_files,
    load_thumb_pixmap,
    photo_meta_rel_paths,
    resolve_media_path,
)
from ui.styles import MainStyles
from ui.widgets.observation.photo_import_worker import PhotoImportWorker

THUMB_LIST_PX = 96
PHOTO_ROLE_ID = Qt.ItemDataRole.UserRole
PHOTO_ROLE_PATH = Qt.ItemDataRole.UserRole + 1


def _combo_fill(cb: QComboBox, rows, blank_label="선택"):
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
    cb.setCurrentIndex(0 if idx < 0 else idx)


def _image_filter() -> str:
    exts = " ".join(f"*{e}" for e in sorted(OBS_ALLOWED_EXTS))
    return f"이미지 ({exts})"


class PhotoPanel(QWidget):
    """관찰 사진 탭. obs_id 없으면 추가 비활성."""

    photosChanged = pyqtSignal()
    dirtyChanged = pyqtSignal(bool)
    importStateChanged = pyqtSignal(bool)

    def __init__(
        self,
        parent=None,
        *,
        db=None,
        code_mgr=None,
        farm_cd: str = "",
        user_id: str = "",
        obs_id: str = "",
        obs_dt: str = "",
        read_only: bool = False,
    ):
        super().__init__(parent)
        self.db = db
        self.code_mgr = code_mgr
        self.farm_cd = farm_cd or ""
        self.user_id = user_id or ""
        self.obs_id = obs_id or ""
        self.obs_dt = obs_dt or ""
        self.read_only = read_only
        self._loading = False
        self._photos: list[dict] = []
        self._importing = False
        self._import_req_id = 0
        self._import_thread_req_id = 0
        self._import_thread: QThread | None = None
        self._import_worker: PhotoImportWorker | None = None
        self._import_ctx: tuple[str, str, int] = ("", "", 0)
        self._unsaved_guard = None
        self._import_progress_text = ""
        self._build_ui()
        self._apply_gate()
        if self.obs_id:
            self.reload()

    def is_importing(self) -> bool:
        return bool(self._importing)

    def import_progress_text(self) -> str:
        return str(self._import_progress_text or "").strip()

    def set_context(
        self,
        farm_cd: str,
        user_id: str,
        obs_id: str,
        obs_dt: str = "",
        *,
        db=None,
        code_mgr=None,
    ):
        if self._importing:
            self._import_req_id += 1
        if db is not None:
            self.db = db
        if code_mgr is not None:
            self.code_mgr = code_mgr
        self.farm_cd = farm_cd or ""
        self.user_id = user_id or ""
        self.obs_id = obs_id or ""
        if obs_dt:
            self.obs_dt = obs_dt
        self._apply_gate()
        if not self._importing:
            self.reload()

    def set_obs_id(self, obs_id: str, obs_dt: str = ""):
        if self._importing:
            self._import_req_id += 1
        self.obs_id = obs_id or ""
        if obs_dt:
            self.obs_dt = obs_dt
        self._apply_gate()
        if not self._importing:
            self.reload()

    def set_unsaved_guard(self, guard):
        """기본정보 미저장 시 사진 추가 차단용 콜백."""
        self._unsaved_guard = guard

    def set_obs_dt(self, obs_dt: str):
        self.obs_dt = obs_dt or ""

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.lbl_gate = QLabel("기본 정보 저장 후 사진을 추가할 수 있습니다")
        self.lbl_gate.setStyleSheet("color: #718096; font-size: 10px; border: none;")
        self.lbl_gate.setWordWrap(True)
        lay.addWidget(self.lbl_gate)

        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #4A5568; font-size: 10px; border: none;")
        self.lbl_progress.setVisible(False)
        lay.addWidget(self.lbl_progress)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(THUMB_LIST_PX, THUMB_LIST_PX))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setSpacing(8)
        self.list.setMinimumHeight(180)
        self.list.setStyleSheet(MainStyles.TABLE + " font-size: 10px;")
        self.list.currentItemChanged.connect(self._on_selection_changed)
        self.list.itemDoubleClicked.connect(self._on_open_original)
        lay.addWidget(self.list, 1)

        meta = QHBoxLayout()
        meta.setSpacing(6)
        meta.addWidget(QLabel("촬영유형"))
        self.cb_shot = QComboBox()
        self.cb_shot.setStyleSheet(MainStyles.COMBO)
        if self.code_mgr:
            _combo_fill(
                self.cb_shot,
                self.code_mgr.get_common_codes(DBManager.OBS_SHOT_PARENT_CD),
                "선택",
            )
        else:
            self.cb_shot.addItem("선택", None)
        self.cb_shot.currentIndexChanged.connect(self._on_meta_edited)
        meta.addWidget(self.cb_shot)
        meta.addWidget(QLabel("메모"))
        self.ed_memo = QLineEdit()
        self.ed_memo.setStyleSheet(MainStyles.INPUT_CENTER)
        self.ed_memo.setPlaceholderText("사진 메모")
        self.ed_memo.editingFinished.connect(self._on_meta_edited)
        meta.addWidget(self.ed_memo, 1)
        lay.addLayout(meta)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.btn_add = QPushButton("사진 추가")
        self.btn_del = QPushButton("삭제")
        self.btn_up = QPushButton("위로")
        self.btn_down = QPushButton("아래로")
        self.btn_open = QPushButton("원본 열기")
        for b in (
            self.btn_add,
            self.btn_del,
            self.btn_up,
            self.btn_down,
            self.btn_open,
        ):
            b.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_add.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_delete)
        self.btn_up.clicked.connect(lambda: self._on_move(-1))
        self.btn_down.clicked.connect(lambda: self._on_move(1))
        self.btn_open.clicked.connect(self._on_open_original)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_up)
        btns.addWidget(self.btn_down)
        btns.addWidget(self.btn_open)
        btns.addStretch(1)
        self.lbl_count = QLabel("0장")
        self.lbl_count.setStyleSheet("color: #4A5568; font-size: 10px; border: none;")
        btns.addWidget(self.lbl_count)
        lay.addLayout(btns)

    def _apply_gate(self):
        has_obs = bool(self.obs_id)
        self.lbl_gate.setVisible(not has_obs and not self._importing)
        can_edit = has_obs and not self.read_only and not self._importing
        self.btn_add.setEnabled(can_edit)
        self.btn_del.setEnabled(can_edit)
        self.btn_up.setEnabled(can_edit)
        self.btn_down.setEnabled(can_edit)
        self.cb_shot.setEnabled(can_edit)
        self.ed_memo.setEnabled(can_edit)
        self.btn_open.setEnabled(has_obs)

    def _set_import_busy(self, busy: bool, text: str = ""):
        prev = self._importing
        busy = bool(busy)
        self._importing = busy
        if busy:
            self._import_progress_text = text or self._import_progress_text
            self.lbl_progress.setVisible(True)
            self.lbl_progress.setText(self._import_progress_text)
        else:
            self._import_progress_text = ""
            self.lbl_progress.setVisible(False)
            self.lbl_progress.setText("")
        self._apply_gate()
        if prev != self._importing:
            self.importStateChanged.emit(self._importing)
            self.dirtyChanged.emit(self._importing)

    def reload(self):
        self._loading = True
        self.list.clear()
        self._photos = []
        if not self.db or not self.farm_cd or not self.obs_id:
            self.lbl_count.setText("0장")
            self._loading = False
            return
        self._photos = self.db.list_observation_photos(self.farm_cd, self.obs_id) or []
        for p in self._photos:
            item = QListWidgetItem()
            pid = str(p.get("photo_id") or "")
            item.setData(PHOTO_ROLE_ID, pid)
            item.setData(PHOTO_ROLE_PATH, p.get("file_path") or "")
            label = str(p.get("original_nm") or pid or "사진")
            pm = load_thumb_pixmap(p.get("thumb_path") or "", THUMB_LIST_PX)
            if pm is not None and not pm.isNull():
                item.setIcon(QIcon(pm))
                item.setText(label[:24])
            else:
                item.setIcon(QIcon())
                item.setText("파일 없음")
            item.setSizeHint(QSize(THUMB_LIST_PX + 16, THUMB_LIST_PX + 28))
            item.setToolTip(label)
            self.list.addItem(item)
        self.lbl_count.setText(f"{len(self._photos)}장")
        self._loading = False
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        else:
            self.cb_shot.setCurrentIndex(0)
            self.ed_memo.clear()

    def _current_photo_id(self) -> str | None:
        it = self.list.currentItem()
        if not it:
            return None
        return it.data(PHOTO_ROLE_ID)

    def _photo_by_id(self, photo_id: str) -> dict | None:
        for p in self._photos:
            if str(p.get("photo_id") or "") == photo_id:
                return p
        return None

    def _on_selection_changed(self, cur, _prev):
        self._loading = True
        if not cur:
            self.cb_shot.setCurrentIndex(0)
            self.ed_memo.clear()
            self._loading = False
            return
        pid = cur.data(PHOTO_ROLE_ID)
        p = self._photo_by_id(pid) or {}
        _set_combo_data(self.cb_shot, p.get("shot_type_cd"))
        self.ed_memo.setText(str(p.get("photo_rmk") or ""))
        self._loading = False

    def _on_meta_edited(self):
        if self._loading or self.read_only or not self.db or self._importing:
            return
        pid = self._current_photo_id()
        if not pid:
            return
        p = self._photo_by_id(pid) or {}
        ok, msg = self.db.update_observation_photo_meta(
            self.farm_cd,
            pid,
            self.cb_shot.currentData(),
            self.ed_memo.text().strip(),
            p.get("sort_no"),
            self.user_id,
        )
        if not ok:
            QMessageBox.warning(self, "사진 수정", msg)
            return
        p["shot_type_cd"] = self.cb_shot.currentData()
        p["photo_rmk"] = self.ed_memo.text().strip()

    def _resolve_obs_dt(self) -> str:
        if self.obs_dt:
            return self.obs_dt
        if self.db and self.farm_cd and self.obs_id:
            rec = self.db.get_observation(self.farm_cd, self.obs_id)
            if rec:
                return str(rec.get("obs_dt") or "")
        return ""

    def _compensate_metas(self, metas: list[dict]) -> list[str]:
        rels: list[str] = []
        for meta in metas or []:
            rels.extend(photo_meta_rel_paths(meta))
        deleted, errors = compensate_photo_files(rels)
        if deleted:
            print(f"[OBS] photo_panel compensate deleted={deleted}")
        return errors

    def _on_add(self):
        if not self.obs_id or not self.db:
            QMessageBox.information(
                self, "안내", "기본 정보 저장 후 사진을 추가할 수 있습니다"
            )
            return
        if self._importing:
            return
        if self._unsaved_guard and self._unsaved_guard():
            QMessageBox.information(
                self,
                "안내",
                "변경된 기본 정보를 먼저 저장해 주세요.",
            )
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "사진 추가", "", _image_filter()
        )
        if not paths:
            return

        self._import_req_id += 1
        req_id = self._import_req_id
        farm = self.farm_cd
        obs_id = self.obs_id
        obs_dt = self._resolve_obs_dt()
        self._import_ctx = (farm, obs_id, req_id)

        items: list[tuple[str, str]] = []
        for src in paths:
            items.append((src, self.db.generate_photo_id(farm)))

        self._set_import_busy(True, f"사진 처리 중 0/{len(items)}")

        thread = QThread()
        worker = PhotoImportWorker(farm, obs_id, obs_dt, items, req_id)
        worker.moveToThread(thread)
        self._import_thread_req_id = req_id
        self._import_thread = thread
        self._import_worker = worker

        thread.started.connect(worker.run)
        worker.progress.connect(
            partial(self._on_import_progress, req_id, farm, obs_id)
        )
        worker.finished.connect(
            partial(self._on_import_finished, req_id, farm, obs_id)
        )
        worker.fatal_error.connect(
            partial(self._on_import_fatal, req_id, farm, obs_id)
        )
        worker.finished.connect(thread.quit)
        worker.fatal_error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            partial(self._on_import_thread_finished, req_id, thread)
        )
        thread.start()

    def _on_import_progress(self, req_id, farm, obs_id, current, total, filename):
        if not self._is_live_import(req_id, farm, obs_id):
            return
        text = f"사진 처리 중 {current}/{total} — {filename}"
        self._import_progress_text = text
        self.lbl_progress.setText(text)

    def _on_import_fatal(self, req_id, farm, obs_id, message):
        if not self._is_live_import(req_id, farm, obs_id):
            return
        QMessageBox.warning(self, "사진 처리", message)

    def _is_live_import(self, req_id: int, farm: str, obs_id: str) -> bool:
        if req_id != self._import_req_id:
            return False
        if farm != self.farm_cd or obs_id != self.obs_id:
            return False
        try:
            return self.isVisible() or self.parent() is not None
        except RuntimeError:
            return False

    def _on_import_finished(
        self, req_id: int, farm: str, obs_id: str, metas: list, failed: list
    ):
        ctx_farm, ctx_obs, ctx_req = self._import_ctx
        stale = (
            req_id != self._import_req_id
            or farm != self.farm_cd
            or obs_id != self.obs_id
            or ctx_req != req_id
        )
        if stale:
            if metas:
                errs = self._compensate_metas(metas)
                if errs:
                    print(f"[OBS] stale import compensate errors: {errs}")
            return

        shot = self.cb_shot.currentData()
        memo = self.ed_memo.text().strip() or None
        for meta in metas or []:
            meta["shot_type_cd"] = shot
            meta["photo_rmk"] = memo

        if not metas:
            self._finish_import_ui(failed, [], [])
            return

        try:
            ok, msg, _ids, dup_names, cleanup_metas = (
                self.db.add_observation_photos_batch(
                    self.farm_cd, self.obs_id, metas, self.user_id
                )
            )
        except Exception as e:
            print(f"[OBS] photo batch unexpected error: {e}")
            comp_errs = self._compensate_metas(metas)
            extra = ""
            if comp_errs:
                extra = "\n파일 정리 중 일부 오류가 발생했습니다."
            QMessageBox.warning(
                self,
                "사진 등록",
                f"사진 DB 저장 중 오류가 발생했습니다.{extra}",
            )
            self._finish_import_ui(failed, [], [])
            return

        if not ok:
            comp_errs = self._compensate_metas(metas)
            extra = ""
            if comp_errs:
                extra = "\n파일 정리 중 일부 오류가 발생했습니다."
            QMessageBox.warning(
                self,
                "사진 등록",
                f"{msg}{extra}",
            )
            self._finish_import_ui(failed, [], [])
            return

        if cleanup_metas:
            comp_errs = self._compensate_metas(cleanup_metas)
            if comp_errs:
                print(f"[OBS] duplicate cleanup errors: {comp_errs}")

        self.reload()
        self.photosChanged.emit()
        self._finish_import_ui(failed, dup_names, _ids)

    def _finish_import_ui(
        self,
        failed: list,
        dup_names: list,
        inserted_ids: list,
    ):
        lines: list[str] = []
        if inserted_ids:
            lines.append(f"{len(inserted_ids)}장이 등록되었습니다.")
        if dup_names:
            lines.append(f"중복 제외 {len(dup_names)}장")
        if failed:
            lines.append(f"처리 실패 {len(failed)}장")
        if lines:
            detail = "\n".join(lines)
            if failed:
                fail_lines = [
                    f"{Path(p).name}: {m}" for p, m in failed[:8]
                ]
                detail += "\n\n실패:\n" + "\n".join(fail_lines)
                if len(failed) > 8:
                    detail += "\n..."
            if dup_names:
                detail += "\n\n중복:\n" + "\n".join(dup_names[:8])
                if len(dup_names) > 8:
                    detail += "\n..."
            if failed or dup_names:
                QMessageBox.warning(self, "사진 추가", detail)
            elif inserted_ids:
                QMessageBox.information(self, "사진 추가", detail)

    def _on_import_thread_finished(self, req_id: int, thread: QThread):
        """QThread 종료 후에만 busy 해제·참조 정리."""
        if self._import_thread is not thread:
            return
        if self._import_thread_req_id != req_id:
            return

        self._import_thread = None
        self._import_worker = None
        self._import_thread_req_id = 0

        ctx_farm, ctx_obs, ctx_req = self._import_ctx
        if ctx_req == req_id:
            self._import_ctx = ("", "", 0)

        self._set_import_busy(False, "")

    def _on_delete(self):
        if self.read_only or not self.db or self._importing:
            return
        pid = self._current_photo_id()
        if not pid:
            QMessageBox.information(self, "안내", "삭제할 사진을 선택해 주세요.")
            return
        ans = QMessageBox.question(
            self,
            "삭제 확인",
            "선택한 사진을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        ok, msg = self.db.soft_delete_observation_photo(
            self.farm_cd, pid, self.user_id
        )
        if not ok:
            QMessageBox.warning(self, "삭제 실패", msg)
            return
        self.reload()
        self.photosChanged.emit()

    def _on_move(self, delta: int):
        if self.read_only or not self.db or self._importing:
            return
        row = self.list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.list.count():
            return
        ids = [self.list.item(i).data(PHOTO_ROLE_ID) for i in range(self.list.count())]
        ids[row], ids[new_row] = ids[new_row], ids[row]
        ok, msg = self.db.reorder_observation_photos(
            self.farm_cd, self.obs_id, ids, self.user_id
        )
        if not ok:
            QMessageBox.warning(self, "순서 변경", msg)
            return
        self.reload()
        self.list.setCurrentRow(new_row)
        self.photosChanged.emit()

    def _on_open_original(self, *_args):
        pid = self._current_photo_id()
        if not pid:
            return
        p = self._photo_by_id(pid) or {}
        rel = p.get("file_path") or ""
        abs_path = resolve_media_path(rel)
        if abs_path is not None and abs_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(abs_path)))
            return
        pm = load_thumb_pixmap(p.get("thumb_path") or "", 800)
        if pm is None or pm.isNull():
            QMessageBox.warning(self, "원본 열기", "파일을 찾을 수 없습니다.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(str(p.get("original_nm") or "사진 미리보기"))
        dlg.setMinimumSize(480, 360)
        v = QVBoxLayout(dlg)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setPixmap(
            pm.scaled(
                640,
                480,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        v.addWidget(lbl)
        dlg.exec()
