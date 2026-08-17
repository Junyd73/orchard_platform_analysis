# -*- coding: utf-8 -*-
"""영농일지 통합 저장 Application Service — PyQt / FastAPI 공통.

PC save_all_integrated_data 규칙을 유지한 채 basket·Ledger·농약 확정을
단일 트랜잭션으로 처리한다. AccountManager / Ledger 스키마는 변경하지 않는다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.account_manager import AccountManager
from core.ops_biz_date import today_ops
from core.pesticide_manager import (
    PesticideManager,
    is_nutrient_category,
)
from core.work_log_constants import (
    DAY_OF_WEEK_SHORT,
    LABOR_ACCT_CD,
    PAY_STATUS_N,
    PAY_STATUS_Y,
    PESTICIDE_USE_RMK_WORK_LOG,
    REF_TYPE_EXP,
    REF_TYPE_RES,
    ROW_STATUS_DEL,
    ROW_STATUS_INS,
    ROW_STATUS_MOD,
    STOCK_ITEM_KIND_FERTILIZER,
    STOCK_ITEM_KIND_PESTICIDE,
    WORK_MAIN_CD,
    WORK_MID_CD_FERTILIZER,
    WORK_MID_CD_PESTICIDE,
)

QueryItem = Tuple[str, Any]
CursorOp = Callable[[sqlite3.Cursor], None]


class WorkLogSaveError(Exception):
    """통합 저장 비즈니스 규칙 위반."""

    def __init__(self, message: str, *, code: str = "SAVE_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class LaborRowDto:
    status: str  # INS/MOD/ORG
    res_id: Optional[int] = None
    emp_cd: str = ""
    emp_nm: str = ""
    man_hour: float = 0.0
    daily_wage: float = 0.0
    pay_method_cd: str = ""
    pay_status: str = PAY_STATUS_N
    orig_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpenseRowDto:
    status: str
    exp_id: Optional[int] = None
    acct_cd: str = ""
    item_nm: str = ""
    amt: float = 0.0
    pay_method_cd: str = ""
    pay_status: str = PAY_STATUS_N
    trans_dt: str = ""
    orig_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PesticideLineDto:
    item_id: int
    use_qty: int = 0
    item_nm_snapshot: str = ""
    spec_nm_snapshot: str = ""
    purpose_nm: str = ""
    line_rmk: str = ""


@dataclass
class WorkDetailDto:
    work_id: str
    work_mid_cd: str
    work_mid_nm: str = ""
    work_loc_id: Optional[Any] = None
    rmk: str = ""
    start_tm: str = ""
    end_tm: str = ""
    status_cd: str = ""
    is_pesticide: Optional[bool] = None
    pesticide_lines: List[PesticideLineDto] = field(default_factory=list)
    # 확정 농약 수정 저장 시: 기존 use_id 취소 후 신규 생성 (화면 진입만으로는 취소하지 않음)
    replace_pesticide_use_id: Optional[int] = None


@dataclass
class PesticideReplacePayload:
    use_dt: str
    site_id: Optional[Any] = None
    worker_nm: str = ""
    worker_id: str = ""
    work_type_nm: str = ""
    rmk: str = PESTICIDE_USE_RMK_WORK_LOG
    work_id: Optional[str] = None
    lines: List[PesticideLineDto] = field(default_factory=list)


@dataclass
class MasterDto:
    work_dt: str
    day_of_week: str = ""
    weather_cd: str = ""
    temp_max: float = 0.0
    temp_min: float = 0.0
    precip: float = 0.0
    humidity: float = 0.0
    sun_rise: str = ""
    sun_set: str = ""
    sunshine_hr: float = 0.0
    wind_max: float = 0.0
    wind_min: float = 0.0
    work_rmk: str = ""


@dataclass
class WorkLogSavePayload:
    master: MasterDto
    works: List[WorkDetailDto]
    # 인력/경비는 선택 work_id 1건에만 반영 (PC와 동일)
    labor_work_id: Optional[str] = None
    labor_rows: List[LaborRowDto] = field(default_factory=list)
    removed_res_ids: List[Any] = field(default_factory=list)
    expense_work_id: Optional[str] = None
    expense_rows: List[ExpenseRowDto] = field(default_factory=list)
    removed_exp_ids: List[Any] = field(default_factory=list)
    worker_nm: str = ""
    worker_id: str = ""


@dataclass
class SaveResult:
    ok: bool = True
    work_dt: str = ""
    message: str = ""


@dataclass
class CancelResult:
    ok: bool = True
    message: str = ""
    errors: List[str] = field(default_factory=list)


def is_pesticide_work(work_mid_cd: str = "", work_mid_nm: str = "") -> bool:
    """방제 판별: 중분류 코드 또는 작업명 휴리스틱 (PC+서버 통일)."""
    cd = (work_mid_cd or "").strip().upper()
    if cd == WORK_MID_CD_PESTICIDE:
        return True
    nm = (work_mid_nm or "").strip()
    if "방제" in nm:
        return True
    if "약제살포" in nm or ("약제" in nm and "살포" in nm):
        return True
    return False


def is_fertilizer_work(work_mid_cd: str = "", work_mid_nm: str = "") -> bool:
    """비료/영양제작업 판별 — 품목 카테고리 '영양제' 재고 연동 대상."""
    cd = (work_mid_cd or "").strip().upper()
    if cd == WORK_MID_CD_FERTILIZER:
        return True
    nm = (work_mid_nm or "").strip()
    return ("비료" in nm) or ("영양제" in nm)


def is_stock_linked_work(work_mid_cd: str = "", work_mid_nm: str = "") -> bool:
    """농약·비료 재고(t_pesticide_use) 연동 작업."""
    return is_pesticide_work(work_mid_cd, work_mid_nm) or is_fertilizer_work(
        work_mid_cd, work_mid_nm
    )


def day_of_week_from_ymd(work_dt: str) -> str:
    ymd = (work_dt or "")[:10]
    try:
        d = date.fromisoformat(ymd)
    except ValueError:
        return ""
    return DAY_OF_WEEK_SHORT[d.weekday()]


class WorkLogIntegratedSaveService:
    """영농일지 통합 저장·농약 사용 취소."""

    def __init__(self, db: Any, farm_cd: str):
        self.db = db
        self.farm_cd = farm_cd
        self.acct = AccountManager(db, farm_cd)
        self.pest = PesticideManager(db)

    def save_work_log_basic(self, user_id: str, payload: WorkLogSavePayload) -> SaveResult:
        """작업-only 저장: 마스터·작업행만. 인력·경비·Ledger·농약 없음.

        payload에 없는 기존 작업은 삭제하지 않는다(업서트 전용).
        삭제는 DELETE /works/{work_id} 등 명시 API에서만 수행한다.
        """
        slim = WorkLogSavePayload(
            master=payload.master,
            works=payload.works,
            labor_work_id=None,
            labor_rows=[],
            removed_res_ids=[],
            expense_work_id=None,
            expense_rows=[],
            removed_exp_ids=[],
            worker_nm=payload.worker_nm,
            worker_id=payload.worker_id,
        )
        # 농약 라인 제거
        slim.works = [
            WorkDetailDto(
                work_id=w.work_id,
                work_mid_cd=w.work_mid_cd,
                work_mid_nm=w.work_mid_nm,
                work_loc_id=w.work_loc_id,
                rmk=w.rmk,
                start_tm=w.start_tm,
                end_tm=w.end_tm,
                status_cd=w.status_cd,
                is_pesticide=False,
                pesticide_lines=[],
            )
            for w in (payload.works or [])
        ]
        return self._save_core(
            user_id,
            slim,
            include_finance_and_pest=False,
            sync_delete_missing=False,
        )

    def save_integrated(self, user_id: str, payload: WorkLogSavePayload) -> SaveResult:
        # PC 최종승인: 화면 작업 목록을 일자 전체로 동기화(누락 행 삭제)
        return self._save_core(
            user_id,
            payload,
            include_finance_and_pest=True,
            sync_delete_missing=True,
        )

    def _save_core(
        self,
        user_id: str,
        payload: WorkLogSavePayload,
        *,
        include_finance_and_pest: bool,
        sync_delete_missing: bool = True,
    ) -> SaveResult:
        work_dt = (payload.master.work_dt or "")[:10]
        if not work_dt:
            raise WorkLogSaveError("작업일이 없습니다.", code="NO_WORK_DT")
        # 미래일: 기본정보(작업-only)만 허용 · 인력/경비/농약/전표는 거부
        if work_dt > today_ops().isoformat():
            if include_finance_and_pest:
                raise WorkLogSaveError(
                    "미래 일자의 인력·경비·농약·최종승인은 할 수 없습니다. "
                    "기본정보만 준비중으로 등록해 주세요.",
                    code="FUTURE_DETAIL",
                )
            for w in payload.works or []:
                st = (w.status_cd or "").strip()
                if st and st != "WO010100":
                    raise WorkLogSaveError(
                        "미래 일자는 준비중(WO010100) 상태만 저장할 수 있습니다.",
                        code="FUTURE_STATUS",
                    )
                w.status_cd = "WO010100"

        master = payload.master
        if not (master.day_of_week or "").strip():
            master.day_of_week = day_of_week_from_ymd(work_dt)

        preview_ids = [w.work_id for w in payload.works if (w.work_mid_cd or "").strip()]
        has_work_rows = len(preview_ids) > 0
        labor_wid = payload.labor_work_id or payload.expense_work_id
        if include_finance_and_pest and has_work_rows:
            if not labor_wid:
                raise WorkLogSaveError(
                    "작업이 등록된 경우, 작업을 선택한 뒤 저장해 주세요.",
                    code="NO_SELECTED_WORK",
                )
            if labor_wid not in preview_ids:
                raise WorkLogSaveError(
                    "작업이 등록된 경우, 해당 작업을 선택한 뒤 저장해 주세요.",
                    code="SELECTED_WORK_MISMATCH",
                )

        prev_rows = self.db.execute_query(
            "SELECT work_id FROM t_work_detail WHERE work_dt = ? AND farm_cd = ?",
            (work_dt, self.farm_cd),
        )
        prev_ids = {str(x[0]) for x in (prev_rows or []) if x and x[0]}

        # 누락 삭제하는 경로에서만: 확정 농약이 있는 작업 제거 차단
        if sync_delete_missing:
            for gone in prev_ids - set(preview_ids):
                chk = self.db.execute_query(
                    """
                    SELECT stock_applied_yn FROM t_pesticide_use
                    WHERE farm_cd = ? AND work_id = ?
                      AND IFNULL(use_yn,'Y')='Y'
                      AND IFNULL(cancel_yn,'N')!='Y'
                      AND IFNULL(stock_applied_yn,'N')='Y'
                    """,
                    (self.farm_cd, gone),
                )
                if chk:
                    raise WorkLogSaveError(
                        f"작업 [{gone}]에 이미 확정된 농약 사용이 연결되어 있어 해당 작업행을 제거할 수 없습니다.",
                        code="PESTICIDE_APPLIED_BLOCK",
                    )

        queries: List[QueryItem] = []
        queries.append(self._build_master_query(master, user_id))

        for w in payload.works:
            if not (w.work_mid_cd or "").strip():
                continue
            queries.append(self._build_detail_query(w, work_dt, user_id))

        # 일자 전체 동기화(PC integrated): payload 밖 작업 삭제
        # 작업-only(basic/upsert): 누락 삭제 금지 — 명시 DELETE API만 삭제
        if sync_delete_missing:
            if preview_ids:
                placeholders = ",".join(["?"] * len(preview_ids))
                queries.append(
                    (
                        f"""
                        DELETE FROM t_work_detail
                        WHERE work_dt = ? AND farm_cd = ?
                        AND work_id NOT IN ({placeholders})
                        """,
                        [work_dt, self.farm_cd] + list(preview_ids),
                    )
                )
            elif prev_ids:
                ph = ",".join(["?"] * len(prev_ids))
                pid_list = list(prev_ids)
                queries.append(
                    (f"DELETE FROM t_work_expense WHERE work_id IN ({ph})", pid_list)
                )
                queries.append(
                    (f"DELETE FROM t_work_resource WHERE work_id IN ({ph})", pid_list)
                )
                queries.append(
                    (
                        "DELETE FROM t_work_detail WHERE work_dt = ? AND farm_cd = ?",
                        (work_dt, self.farm_cd),
                    )
                )

        if include_finance_and_pest and has_work_rows and labor_wid:
            queries.extend(
                self._build_res_queries(
                    labor_wid,
                    work_dt,
                    user_id,
                    payload.labor_rows,
                    payload.removed_res_ids,
                )
            )
            exp_wid = payload.expense_work_id or labor_wid
            queries.extend(
                self._build_exp_queries(
                    exp_wid,
                    work_dt,
                    user_id,
                    payload.expense_rows,
                    payload.removed_exp_ids,
                )
            )

        pest_ops: List[CursorOp] = []
        if include_finance_and_pest:
            pest_ops = self._build_pesticide_cursor_ops(
                payload, work_dt, user_id, preview_ids
            )
        self._execute_transaction(queries, pest_ops)
        return SaveResult(ok=True, work_dt=work_dt, message="저장 완료")

    def cancel_pesticide_use(
        self,
        user_id: str,
        *,
        use_id: int,
    ) -> CancelResult:
        """기본 취소 단위: use_id. work_id 단독 취소는 금지."""
        if use_id is None or int(use_id) <= 0:
            return CancelResult(ok=False, message="use_id가 필요합니다.")

        def _op(cur: sqlite3.Cursor) -> None:
            ok, errs = self.pest.cancel_use_restore_stock_on_cursor(
                cur, self.farm_cd, user_id, int(use_id), already_cancelled_ok=False
            )
            if not ok:
                raise WorkLogSaveError(
                    errs[0] if errs else "농약 사용 취소 실패",
                    code="PESTICIDE_CANCEL_FAIL",
                )

        try:
            self._execute_transaction([], [_op])
            return CancelResult(ok=True, message="농약 사용이 취소되었습니다.")
        except WorkLogSaveError as e:
            return CancelResult(ok=False, message=e.message, errors=[e.message])
        except Exception as e:
            return CancelResult(ok=False, message=str(e), errors=[str(e)])

    def cancel_all_pesticide_uses_for_work(
        self,
        user_id: str,
        work_id: str,
    ) -> CancelResult:
        """작업 연결 확정 농약 전건 취소 — 단일 트랜잭션."""
        wid = (work_id or "").strip()
        if not wid:
            return CancelResult(ok=False, message="work_id가 필요합니다.")
        use_ids = self.pest.list_use_ids_by_work_id(self.farm_cd, wid)
        if not use_ids:
            return CancelResult(ok=True, message="취소할 확정 농약 사용이 없습니다.")

        def _op(cur: sqlite3.Cursor) -> None:
            for uid in use_ids:
                ok, errs = self.pest.cancel_use_restore_stock_on_cursor(
                    cur, self.farm_cd, user_id, int(uid), already_cancelled_ok=False
                )
                if not ok:
                    raise WorkLogSaveError(
                        errs[0] if errs else f"use_id={uid} 취소 실패",
                        code="PESTICIDE_CANCEL_ALL_FAIL",
                    )

        try:
            self._execute_transaction([], [_op])
            return CancelResult(
                ok=True,
                message=f"작업 [{wid}] 농약 사용 {len(use_ids)}건이 취소되었습니다.",
            )
        except WorkLogSaveError as e:
            return CancelResult(ok=False, message=e.message, errors=[e.message])
        except Exception as e:
            return CancelResult(ok=False, message=str(e), errors=[str(e)])

    def purge_work_related(
        self,
        user_id: str,
        work_id: str,
        work_dt: str,
        *,
        extra_cursor_ops: Optional[Sequence[CursorOp]] = None,
    ) -> None:
        """작업 삭제용 연관 정리 — 기존 인력/경비 역분개·농약 취소·사진 soft 재사용.

        detail DELETE 및 schedule/Google 은 호출측(extra_cursor_ops / TX 밖)에서 처리.
        """
        wid = (work_id or "").strip()
        dt = (work_dt or "")[:10]
        if not wid or not dt:
            raise WorkLogSaveError("삭제할 작업이 없습니다.", code="NO_WORK")

        res_rows = self.db.fetch_all(
            "SELECT res_id FROM t_work_resource WHERE farm_cd = ? AND work_id = ?",
            (self.farm_cd, wid),
        )
        exp_rows = self.db.fetch_all(
            "SELECT exp_id FROM t_work_expense WHERE farm_cd = ? AND work_id = ?",
            (self.farm_cd, wid),
        )
        res_ids = [r[0] for r in (res_rows or []) if r and r[0] is not None]
        exp_ids = [e[0] for e in (exp_rows or []) if e and e[0] is not None]

        queries: List[QueryItem] = []
        # 빈 유지목록 + removed_ids → DELETE 행 + AccountManager 역분개
        queries.extend(
            self._build_res_queries(wid, dt, user_id, [], res_ids)
        )
        queries.extend(
            self._build_exp_queries(wid, dt, user_id, [], exp_ids)
        )

        applied_ids = [
            int(x) for x in self.pest.list_use_ids_by_work_id(self.farm_cd, wid)
        ]
        draft_rows = self.db.fetch_all(
            """
            SELECT use_id FROM t_pesticide_use
            WHERE farm_cd = ? AND work_id = ?
              AND IFNULL(use_yn, 'Y') = 'Y'
              AND IFNULL(cancel_yn, 'N') != 'Y'
              AND IFNULL(stock_applied_yn, 'N') != 'Y'
            ORDER BY use_id
            """,
            (self.farm_cd, wid),
        )
        draft_ids = []
        for row in draft_rows or []:
            try:
                draft_ids.append(int(row[0]))
            except (TypeError, ValueError, IndexError):
                continue

        def _related_op(cur: sqlite3.Cursor) -> None:
            for uid in applied_ids:
                ok, errs = self.pest.cancel_use_restore_stock_on_cursor(
                    cur,
                    self.farm_cd,
                    user_id,
                    int(uid),
                    already_cancelled_ok=False,
                )
                if not ok:
                    raise WorkLogSaveError(
                        errs[0] if errs else f"use_id={uid} 취소 실패",
                        code="PESTICIDE_CANCEL_FAIL",
                    )
            for uid in draft_ids:
                ok, errs = self.pest.soft_deactivate_use_on_cursor(
                    cur, self.farm_cd, user_id, int(uid)
                )
                if not ok:
                    raise WorkLogSaveError(
                        errs[0] if errs else f"use_id={uid} 비활성 실패",
                        code="PESTICIDE_DRAFT_CLEAR",
                    )
            # 기존 soft_delete_work_photo 와 동일 정책 (use_yn='N', 파일은 유지)
            try:
                cur.execute(
                    """
                    UPDATE t_work_photo
                    SET use_yn = 'N', mod_id = ?, mod_dt = datetime('now','localtime')
                    WHERE farm_cd = ? AND work_id = ?
                      AND COALESCE(use_yn, 'Y') = 'Y'
                    """,
                    (user_id, self.farm_cd, wid),
                )
            except sqlite3.OperationalError:
                # 스키마 미적용 환경 — 사진 테이블 없음
                pass
            cur.execute(
                "DELETE FROM t_work_detail WHERE farm_cd = ? AND work_id = ?",
                (self.farm_cd, wid),
            )
            for op in extra_cursor_ops or []:
                op(cur)

        self._execute_transaction(queries, [_related_op])

    def replace_pesticide_use(
        self,
        user_id: str,
        use_id: int,
        new_payload: PesticideReplacePayload,
    ) -> CancelResult:
        """확정 농약 수정 저장: 기존 취소+복원 → 신규 저장+차감 (단일 TX)."""
        if use_id is None or int(use_id) <= 0:
            return CancelResult(ok=False, message="use_id가 필요합니다.")
        lines = [
            {
                "item_id": ln.item_id,
                "use_qty": int(ln.use_qty or 0),
                "item_nm_snapshot": ln.item_nm_snapshot or "",
                "spec_nm_snapshot": ln.spec_nm_snapshot or "",
                "purpose_nm": ln.purpose_nm or "",
                "line_rmk": ln.line_rmk or "",
            }
            for ln in (new_payload.lines or [])
            if int(ln.item_id or 0) > 0 and int(ln.use_qty or 0) > 0
        ]
        if not lines:
            return CancelResult(ok=False, message="수정할 농약 사용 수량이 없습니다.")

        def _op(cur: sqlite3.Cursor) -> None:
            new_uid, errs = self.pest.replace_use_on_cursor(
                cur,
                self.farm_cd,
                user_id,
                int(use_id),
                (new_payload.use_dt or "")[:10],
                new_payload.site_id,
                new_payload.worker_nm or user_id,
                new_payload.worker_id or user_id,
                new_payload.work_type_nm or "",
                new_payload.rmk or PESTICIDE_USE_RMK_WORK_LOG,
                lines,
                work_id=new_payload.work_id,
            )
            if new_uid is None or errs:
                raise WorkLogSaveError(
                    (errs[0] if errs else "농약 교체 저장 실패"),
                    code="PESTICIDE_REPLACE_FAIL",
                )

        try:
            self._execute_transaction([], [_op])
            return CancelResult(ok=True, message="농약 사용이 수정·확정되었습니다.")
        except WorkLogSaveError as e:
            return CancelResult(ok=False, message=e.message, errors=[e.message])
        except Exception as e:
            return CancelResult(ok=False, message=str(e), errors=[str(e)])

    # ------------------------------------------------------------------
    # master / detail
    # ------------------------------------------------------------------
    def _build_master_query(self, master: MasterDto, user_id: str) -> QueryItem:
        data = {
            "work_dt": master.work_dt[:10],
            "day_of_week": master.day_of_week,
            "weather_cd": master.weather_cd or "",
            "temp_max": float(master.temp_max or 0),
            "temp_min": float(master.temp_min or 0),
            "precip": float(master.precip or 0),
            "humidity": float(master.humidity or 0),
            "sun_rise": master.sun_rise or "",
            "sun_set": master.sun_set or "",
            "sunshine_hr": float(master.sunshine_hr or 0),
            "wind_max": float(master.wind_max or 0),
            "wind_min": float(master.wind_min or 0),
            "work_rmk": master.work_rmk or "",
            "farm_cd": self.farm_cd,
            "reg_id": user_id,
            "mod_id": user_id,
        }
        sql = """
            INSERT INTO t_work_master (
                work_dt, day_of_week, weather_cd,
                temp_max, temp_min, precip, humidity,
                sun_rise, sun_set, sunshine_hr, wind_max, wind_min,
                work_rmk, farm_cd, reg_id, reg_dt
            ) VALUES (
                :work_dt, :day_of_week, :weather_cd,
                :temp_max, :temp_min, :precip, :humidity,
                :sun_rise, :sun_set, :sunshine_hr, :wind_max, :wind_min,
                :work_rmk, :farm_cd, :reg_id, datetime('now','localtime')
            )
            ON CONFLICT(work_dt) DO UPDATE SET
                day_of_week = excluded.day_of_week,
                weather_cd = excluded.weather_cd,
                temp_max = excluded.temp_max,
                temp_min = excluded.temp_min,
                precip = excluded.precip,
                humidity = excluded.humidity,
                sun_rise = excluded.sun_rise,
                sun_set = excluded.sun_set,
                sunshine_hr = excluded.sunshine_hr,
                wind_max = excluded.wind_max,
                wind_min = excluded.wind_min,
                work_rmk = excluded.work_rmk,
                mod_id = :mod_id,
                mod_dt = datetime('now','localtime')
        """
        return (sql, data)

    def _build_detail_query(self, w: WorkDetailDto, work_dt: str, user_id: str) -> QueryItem:
        sql = """
            INSERT INTO t_work_detail (
                work_id, work_dt, farm_cd, work_main_cd, work_mid_cd,
                work_loc_id, rmk, start_tm, end_tm, status_cd, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(work_id) DO UPDATE SET
                work_mid_cd = excluded.work_mid_cd,
                work_loc_id = excluded.work_loc_id,
                rmk = excluded.rmk,
                start_tm = excluded.start_tm,
                end_tm = excluded.end_tm,
                status_cd = excluded.status_cd,
                mod_id = ?,
                mod_dt = datetime('now','localtime')
        """
        params = (
            w.work_id,
            work_dt,
            self.farm_cd,
            WORK_MAIN_CD,
            w.work_mid_cd,
            w.work_loc_id,
            w.rmk or "",
            w.start_tm or "",
            w.end_tm or "",
            w.status_cd or "",
            user_id,
            user_id,
        )
        return (sql, params)

    # ------------------------------------------------------------------
    # labor / expense + ledger
    # ------------------------------------------------------------------
    def _build_res_queries(
        self,
        work_id: str,
        work_date: str,
        user_id: str,
        rows: Sequence[LaborRowDto],
        removed_ids: Sequence[Any],
    ) -> List[QueryItem]:
        queries: List[QueryItem] = []
        basket: List[Dict[str, Any]] = []

        for rid in removed_ids or []:
            if not rid or str(rid).upper() == "NEW":
                continue
            res_list = self.db.fetch_all(
                "SELECT pay_method_cd, pay_status, slip_no, daily_wage, emp_cd FROM t_work_resource WHERE res_id=?",
                (rid,),
            )
            if res_list:
                old = res_list[0]
                orig = {
                    "detail_no": rid,
                    "pay_method_cd": old[0],
                    "pay_status": old[1],
                    "slip_no": old[2],
                    "daily_wage": old[3],
                    "emp_cd": old[4],
                    "acct_cd": LABOR_ACCT_CD,
                }
                basket.append(
                    {
                        "status": ROW_STATUS_DEL,
                        "orig_data": orig,
                        "acct_cd": LABOR_ACCT_CD,
                        "method": old[0],
                        "amt": 0,
                        "pay_status": PAY_STATUS_N,
                        "rmk": old[4],
                    }
                )
            queries.append(("DELETE FROM t_work_resource WHERE res_id = ?", (rid,)))

        rows_to_save: List[Dict[str, Any]] = []
        for row in rows or []:
            status = (row.status or "").strip().upper() or ROW_STATUS_ORG
            res_id = row.res_id
            if res_id is not None and str(res_id).upper() == "NEW":
                res_id = None
            orig = dict(row.orig_data or {})
            if res_id is not None and "res_id" not in orig:
                orig["res_id"] = res_id
            item_data = {
                "status": status,
                "id": res_id,
                "orig_data": orig,
                "acct_cd": LABOR_ACCT_CD,
                "method": row.pay_method_cd,
                "amt": int(float(row.daily_wage or 0)),
                "pay_status": row.pay_status or PAY_STATUS_N,
                "rmk": row.emp_cd,
                "rmk_nm": row.emp_nm or row.emp_cd,
                "work_time": float(row.man_hour or 0),
                "emp_cd": row.emp_cd,
            }
            basket.append(item_data)
            if status in (ROW_STATUS_INS, ROW_STATUS_MOD):
                rows_to_save.append(item_data)

        ledger_queries, slip_map = self.acct.sync_ledger_by_basket(
            REF_TYPE_RES, work_id, work_date, basket, user_id
        )
        queries.extend(ledger_queries)

        sql_upsert = """
            INSERT INTO t_work_resource (
                res_id, work_id, farm_cd, trans_dt, emp_cd, man_hour, daily_wage, meal_cost, other_cost,
                pay_method_cd, pay_status, reg_id, slip_no, reg_dt
            ) VALUES (
                :id, :work_id, :farm_cd, :trans_dt, :emp_cd, :work_time, :amt, 0, 0,
                :method, :pay_status, :reg_id, :slip_no, datetime('now','localtime')
            )
            ON CONFLICT(res_id) DO UPDATE SET
                emp_cd=excluded.emp_cd, man_hour=excluded.man_hour, daily_wage=excluded.daily_wage,
                pay_method_cd=excluded.pay_method_cd, pay_status=excluded.pay_status,
                slip_no=excluded.slip_no, mod_id=:reg_id, mod_dt=datetime('now','localtime')
        """
        for item in rows_to_save:
            key = f"{item['acct_cd']}_{item['method']}"
            paid_positive = (
                item["pay_status"] == PAY_STATUS_Y
                and float(item.get("amt") or 0) > 0
            )
            item["slip_no"] = slip_map.get(key) if paid_positive else None
            item.update(
                {
                    "work_id": work_id,
                    "farm_cd": self.farm_cd,
                    "trans_dt": work_date,
                    "reg_id": user_id,
                }
            )
            queries.append((sql_upsert, dict(item)))
        return queries

    def _build_exp_queries(
        self,
        work_id: str,
        work_date: str,
        user_id: str,
        rows: Sequence[ExpenseRowDto],
        removed_ids: Sequence[Any],
    ) -> List[QueryItem]:
        queries: List[QueryItem] = []
        basket: List[Dict[str, Any]] = []

        for eid in removed_ids or []:
            if not eid or str(eid).upper() == "NEW":
                continue
            exp_list = self.db.fetch_all(
                "SELECT acct_cd, pay_method_cd, pay_status, total_amt, slip_no, item_nm FROM t_work_expense WHERE exp_id=?",
                (eid,),
            )
            if exp_list:
                old = exp_list[0]
                orig = {
                    "detail_no": eid,
                    "acct_cd": old[0],
                    "pay_method_cd": old[1],
                    "pay_status": old[2],
                    "total_amt": old[3],
                    "slip_no": old[4],
                    "item_nm": old[5] or "",
                }
                basket.append(
                    {
                        "status": ROW_STATUS_DEL,
                        "orig_data": orig,
                        "acct_cd": old[0],
                        "method": old[1],
                        "amt": 0,
                        "pay_status": PAY_STATUS_N,
                        "rmk": old[5] or "",
                    }
                )
            queries.append(("DELETE FROM t_work_expense WHERE exp_id = ?", (eid,)))

        rows_to_save: List[Dict[str, Any]] = []
        for row in rows or []:
            status = (row.status or "").strip().upper() or ROW_STATUS_ORG
            exp_id = row.exp_id
            if exp_id is not None and str(exp_id).upper() == "NEW":
                exp_id = None
            orig = dict(row.orig_data or {})
            if exp_id is not None and "exp_id" not in orig:
                orig["exp_id"] = exp_id
            item_data = {
                "status": status,
                "id": exp_id,
                "orig_data": orig,
                "acct_cd": row.acct_cd,
                "method": row.pay_method_cd,
                "amt": int(float(row.amt or 0)),
                "pay_status": row.pay_status or PAY_STATUS_N,
                "rmk": row.item_nm or "",
                "item_nm": row.item_nm or "",
            }
            basket.append(item_data)
            if status in (ROW_STATUS_INS, ROW_STATUS_MOD):
                rows_to_save.append(item_data)

        ledger_queries, slip_map = self.acct.sync_ledger_by_basket(
            REF_TYPE_EXP, work_id, work_date, basket, user_id
        )
        queries.extend(ledger_queries)

        sql_upsert = """
            INSERT INTO t_work_expense (
                exp_id, work_id, farm_cd, trans_dt, acct_cd, item_nm, qty, unit_price, total_amt,
                pay_method_cd, pay_status, reg_id, slip_no, reg_dt
            ) VALUES (
                :id, :work_id, :farm_cd, :trans_dt, :acct_cd, :item_nm, 1, :amt, :amt,
                :method, :pay_status, :reg_id, :slip_no, datetime('now','localtime')
            )
            ON CONFLICT(exp_id) DO UPDATE SET
                trans_dt=excluded.trans_dt,
                acct_cd=excluded.acct_cd, item_nm=excluded.item_nm, total_amt=excluded.total_amt,
                pay_method_cd=excluded.pay_method_cd, pay_status=excluded.pay_status,
                slip_no=excluded.slip_no, mod_id=:reg_id, mod_dt=datetime('now','localtime')
        """
        for item in rows_to_save:
            key = f"{item['acct_cd']}_{item['method']}"
            paid_positive = (
                item["pay_status"] == PAY_STATUS_Y
                and float(item.get("amt") or 0) > 0
            )
            item["slip_no"] = slip_map.get(key) if paid_positive else None
            item.update(
                {
                    "work_id": work_id,
                    "farm_cd": self.farm_cd,
                    "trans_dt": work_date,
                    "reg_id": user_id,
                }
            )
            queries.append((sql_upsert, dict(item)))
        return queries

    # ------------------------------------------------------------------
    # pesticide (save = apply)
    # ------------------------------------------------------------------
    def _build_pesticide_cursor_ops(
        self,
        payload: WorkLogSavePayload,
        work_dt: str,
        user_id: str,
        preview_ids: List[str],
    ) -> List[CursorOp]:
        ops: List[CursorOp] = []
        ymd = work_dt[:10]
        worker_nm = payload.worker_nm or user_id
        worker_id = payload.worker_id or user_id
        work_by_id = {w.work_id: w for w in payload.works}

        def orphan_cleanup(cur: sqlite3.Cursor) -> None:
            cur.execute(
                """
                SELECT u.use_id, u.work_id, u.stock_applied_yn,
                       IFNULL(u.cancel_yn, 'N') AS cancel_yn
                FROM t_pesticide_use u
                WHERE u.farm_cd = ? AND substr(u.use_dt, 1, 10) = ?
                  AND u.work_id IS NOT NULL AND TRIM(u.work_id) != ''
                  AND IFNULL(u.use_yn, 'Y') = 'Y'
                  AND IFNULL(u.cancel_yn, 'N') != 'Y'
                  AND NOT EXISTS (
                      SELECT 1 FROM t_work_detail d
                      WHERE d.work_id = u.work_id AND d.farm_cd = u.farm_cd
                  )
                """,
                (self.farm_cd, ymd),
            )
            for ow in cur.fetchall() or []:
                uid = int(ow[0] if not hasattr(ow, "keys") else ow["use_id"])
                applied = str(
                    ow[2] if not hasattr(ow, "keys") else ow["stock_applied_yn"] or "N"
                ).strip().upper()
                if applied == "Y":
                    raise WorkLogSaveError(
                        "작업 목록에서 제거된 행에 확정된 농약 사용이 남아 있어 처리할 수 없습니다.",
                        code="ORPHAN_APPLIED",
                    )
                ok, errs = self.pest.soft_deactivate_use_on_cursor(
                    cur, self.farm_cd, user_id, uid
                )
                if not ok:
                    raise WorkLogSaveError(
                        errs[0] if errs else "농약 orphan 정리 실패",
                        code="ORPHAN_CLEANUP",
                    )

        ops.append(orphan_cleanup)

        for wid in preview_ids:
            w = work_by_id.get(wid)
            if not w:
                continue
            # 작업구분(WK010800/WK010200)이 기준. is_pesticide 플래그는
            # 비료 작업에서 농약으로 오인하지 않도록 비료가 우선한다.
            is_fert = is_fertilizer_work(w.work_mid_cd, w.work_mid_nm)
            if is_fert:
                is_pest = False
            elif w.is_pesticide is not None:
                is_pest = bool(w.is_pesticide)
            else:
                is_pest = is_pesticide_work(w.work_mid_cd, w.work_mid_nm)
            # 방제·비료 모두 동일 t_pesticide_use 재고 경로 사용
            stock_linked = is_pest or is_fert
            stock_kind = (
                STOCK_ITEM_KIND_FERTILIZER
                if is_fert
                else STOCK_ITEM_KIND_PESTICIDE
            )
            lines = [
                {
                    "item_id": ln.item_id,
                    "use_qty": int(ln.use_qty or 0),
                    "item_nm_snapshot": ln.item_nm_snapshot or "",
                    "spec_nm_snapshot": ln.spec_nm_snapshot or "",
                    "purpose_nm": ln.purpose_nm or "",
                    "line_rmk": ln.line_rmk or "",
                }
                for ln in (w.pesticide_lines or [])
                if int(ln.item_id or 0) > 0 and int(ln.use_qty or 0) > 0
            ]

            def make_op(
                work: WorkDetailDto,
                linked: bool,
                kind: str,
                pest_lines: List[Dict[str, Any]],
            ) -> CursorOp:
                def _op(cur: sqlite3.Cursor) -> None:
                    if pest_lines and not linked:
                        raise WorkLogSaveError(
                            "농약/비료 등록은 방제살포(WK010200) 또는 "
                            "비료영양(WK010800) 작업에서만 가능합니다.",
                            code="STOCK_WORK_TYPE_MISMATCH",
                        )
                    if pest_lines:
                        self._assert_stock_item_categories(
                            cur, pest_lines, kind=kind
                        )
                    replace_uid = work.replace_pesticide_use_id
                    if replace_uid and pest_lines:
                        new_uid, errs = self.pest.replace_use_on_cursor(
                            cur,
                            self.farm_cd,
                            user_id,
                            int(replace_uid),
                            ymd,
                            work.work_loc_id,
                            worker_nm,
                            worker_id,
                            work.work_mid_nm or "",
                            PESTICIDE_USE_RMK_WORK_LOG,
                            pest_lines,
                            work_id=work.work_id,
                        )
                        if new_uid is None or errs:
                            raise WorkLogSaveError(
                                (errs[0] if errs else "농약/비료 교체 저장 실패"),
                                code="PESTICIDE_REPLACE",
                            )
                        return

                    cur.execute(
                        """
                        SELECT use_id, stock_applied_yn
                        FROM t_pesticide_use
                        WHERE farm_cd = ? AND work_id = ?
                          AND IFNULL(use_yn, 'Y') = 'Y'
                          AND IFNULL(cancel_yn, 'N') != 'Y'
                        LIMIT 1
                        """,
                        (self.farm_cd, work.work_id),
                    )
                    row = cur.fetchone()
                    uid = None
                    applied = "N"
                    if row:
                        uid = int(row[0] if not hasattr(row, "keys") else row["use_id"])
                        applied = str(
                            row[1] if not hasattr(row, "keys") else row["stock_applied_yn"] or "N"
                        ).strip().upper()

                    if not linked:
                        if uid is None:
                            return
                        if applied == "Y":
                            raise WorkLogSaveError(
                                f"작업 [{work.work_id}]에 연결된 사용이 이미 확정되어 변경할 수 없습니다. "
                                "사용 취소 후 다시 시도하세요.",
                                code="PESTICIDE_APPLIED_BLOCK",
                            )
                        ok, errs = self.pest.soft_deactivate_use_on_cursor(
                            cur, self.farm_cd, user_id, uid
                        )
                        if not ok:
                            raise WorkLogSaveError(
                                errs[0] if errs else "사용 비활성화 실패",
                                code="PESTICIDE_DEACTIVATE",
                            )
                        return

                    if applied == "Y":
                        # 확정 건은 저장 시 건드리지 않음(멱등). 수정은 replace_pesticide_use_id로만.
                        return

                    if not pest_lines:
                        if uid is not None:
                            ok, errs = self.pest.soft_deactivate_use_on_cursor(
                                cur, self.farm_cd, user_id, uid
                            )
                            if not ok:
                                raise WorkLogSaveError(
                                    errs[0] if errs else "사용 초기화 실패",
                                    code="PESTICIDE_CLEAR",
                                )
                        return

                    new_uid, errs = self.pest.save_and_apply_use_on_cursor(
                        cur,
                        self.farm_cd,
                        user_id,
                        uid,
                        ymd,
                        work.work_loc_id,
                        worker_nm,
                        worker_id,
                        work.work_mid_nm or "",
                        PESTICIDE_USE_RMK_WORK_LOG,
                        pest_lines,
                        work_id=work.work_id,
                    )
                    if errs or new_uid is None:
                        raise WorkLogSaveError(
                            (errs[0] if errs else "사용·재고 확정 실패"),
                            code="PESTICIDE_APPLY",
                        )

                return _op

            ops.append(make_op(w, stock_linked, stock_kind, lines))
        return ops

    def _assert_stock_item_categories(
        self,
        cur: sqlite3.Cursor,
        lines: Sequence[Dict[str, Any]],
        *,
        kind: str,
    ) -> None:
        """농약 탭↔영양제 / 비료 탭↔비영양제 교차 등록 거부."""
        ids = sorted(
            {
                int(ln.get("item_id") or 0)
                for ln in lines
                if int(ln.get("item_id") or 0) > 0
            }
        )
        if not ids:
            return
        ph = ",".join(["?"] * len(ids))
        cur.execute("PRAGMA table_info(m_pesticide_item)")
        col_rows = cur.fetchall() or []
        col_names = {
            str(r[1] if not hasattr(r, "keys") else r["name"]) for r in col_rows
        }
        has_cat = "pest_category_nm" in col_names
        if has_cat:
            cur.execute(
                f"""
                SELECT item_id, item_nm, IFNULL(pest_category_nm, '') AS cat
                FROM m_pesticide_item
                WHERE farm_cd = ? AND item_id IN ({ph})
                """,
                [self.farm_cd, *ids],
            )
        else:
            cur.execute(
                f"""
                SELECT item_id, item_nm, '' AS cat
                FROM m_pesticide_item
                WHERE farm_cd = ? AND item_id IN ({ph})
                """,
                [self.farm_cd, *ids],
            )
        rows = cur.fetchall() or []
        found: Dict[int, Tuple[str, str]] = {}
        for r in rows:
            iid = int(r[0] if not hasattr(r, "keys") else r["item_id"])
            nm = str(r[1] if not hasattr(r, "keys") else r["item_nm"] or "")
            cat = str(r[2] if not hasattr(r, "keys") else r["cat"] or "")
            found[iid] = (nm, cat)
        missing = [i for i in ids if i not in found]
        if missing:
            raise WorkLogSaveError(
                f"품목을 찾을 수 없습니다: {missing}",
                code="STOCK_ITEM_NOT_FOUND",
            )
        if not has_cat:
            # 구스키마 — 교차검증 생략
            return
        want_fert = kind == STOCK_ITEM_KIND_FERTILIZER
        for iid, (nm, cat) in found.items():
            is_nut = is_nutrient_category(cat)
            if want_fert and not is_nut:
                raise WorkLogSaveError(
                    f"비료 등록에는 영양제 품목만 사용할 수 있습니다"
                    f" ({nm or iid}: {cat or '미분류'}).",
                    code="FERTILIZER_CATEGORY_MISMATCH",
                )
            if not want_fert and is_nut:
                raise WorkLogSaveError(
                    f"농약 등록에는 영양제 품목을 사용할 수 없습니다"
                    f" ({nm or iid}).",
                    code="PESTICIDE_CATEGORY_MISMATCH",
                )

    # ------------------------------------------------------------------
    # transaction
    # ------------------------------------------------------------------
    def _execute_transaction(
        self,
        queries: List[QueryItem],
        cursor_ops: Optional[Sequence[CursorOp]] = None,
    ) -> None:
        """동일 connection/cursor 트랜잭션. Manager 내부 BEGIN 금지(on_cursor만)."""

        def _run(cur: sqlite3.Cursor) -> None:
            for query, params in queries:
                cur.execute(query, params)
            for op in cursor_ops or []:
                op(cur)

        txn = getattr(self.db, "transaction", None)
        if callable(txn):
            with txn() as cur:
                _run(cur)
            return

        conn = self.db.conn
        try:
            conn.isolation_level = None
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            _run(cur)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.isolation_level = ""
