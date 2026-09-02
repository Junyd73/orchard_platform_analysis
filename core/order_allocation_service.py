# -*- coding: utf-8 -*-
"""저장재고형: 이미 있는 상품재고(FR010100/200)를 주문에 예약 — FIFO/LIFO (Stage 3A).

전체 판매 필수단계 아님. allocated_qty=0 정상. 품종 if 금지 (DEC-020/021).
업무 전체: docs/mobile_order_sales/09_production_inventory_flow.md
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from core.ops_biz_date import now_ops_str
from core.order_alloc_constants import (
    ALLOC_ID_SEQ_LEN,
    ALLOC_ID_SUFFIX,
    COL_ALLOCATED_QTY,
    IO_TYPE_CANCEL_HOLD,
    IO_TYPE_HOLD,
    MSG_ALLOC_CANCELLED,
    MSG_ALLOC_DETAIL_NOT_FOUND,
    MSG_ALLOC_INVARIANT,
    MSG_ALLOC_LOCKED,
    MSG_ALLOC_NO_STOCK,
    MSG_ALLOC_ORDER_NOT_FOUND,
    MSG_ALLOC_OVER_ORDER,
    MSG_ALLOC_QTY_INVALID,
    MSG_ALLOC_QTY_UNAVAILABLE,
    MSG_ALLOC_SHIPPED_CANCEL,
    MSG_RELEASE_OVER,
    MSG_RELEASE_QTY_INVALID,
    TABLE_ORDER_ALLOC,
    alloc_remark,
)
from core.order_constants import ORDER_STATUS_CANCEL_CD, ORDER_STATUS_LOCKED
from core.order_service import OrderNotFoundError, OrderSaveError, OrderValidationError
from core.stock_availability import (
    compute_available_qty,
    get_active_auction_transit_map,
    get_active_auction_transit_qty,
    stock_seq_column_ref,
    stock_seq_select_sql,
)

_QTY_EPS = 1e-9


class AllocationError(OrderSaveError):
    def __init__(self, message: str, *, code: str = "ALLOCATION_ERROR"):
        super().__init__(message, code=code)


class AllocationConflictError(AllocationError):
    def __init__(self, message: str, *, code: str = "ALLOCATION_CONFLICT"):
        super().__init__(message, code=code)


@dataclass(frozen=True)
class StockKey:
    farm_cd: str
    wh_cd: str
    item_cd: str
    variety_cd: str
    grade_cd: str
    size_cd: str
    weight: float
    harvest_year: int
    storage_dt: str

    def as_tuple(self) -> tuple[Any, ...]:
        return (
            self.farm_cd,
            self.wh_cd,
            self.item_cd,
            self.variety_cd,
            self.grade_cd,
            self.size_cd,
            self.weight,
            self.harvest_year,
            self.storage_dt,
        )


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_val(row: Any, key: str, idx: int) -> Any:
    if isinstance(row, sqlite3.Row):
        try:
            return row[key]
        except (KeyError, IndexError):
            return row[idx]
    return row[idx]


def _qty_pos(value: float) -> bool:
    return value > _QTY_EPS


class OrderAllocationService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_available_stock(
        self,
        farm_cd: str,
        *,
        item_cd: str | None = None,
        variety_cd: str | None = None,
        wh_cd: str | None = None,
        include_zero: bool = False,
    ) -> list[dict[str, Any]]:
        farm = str(farm_cd or "").strip()
        seq_col = stock_seq_select_sql(self.conn, "m")
        sql = f"""
            SELECT {seq_col}, m.farm_cd, m.wh_cd, m.item_cd, m.variety_cd, m.grade_cd, m.size_cd,
                   m.weight, m.harvest_year, m.storage_dt,
                   COALESCE(m.in_qty, 0)       AS in_qty,
                   COALESCE(m.out_qty, 0)      AS out_qty,
                   COALESCE(m.reserved_qty, 0) AS reserved_qty,
                   COALESCE(ci.code_nm, '')    AS item_nm,
                   COALESCE(cv.code_nm, '')    AS variety_nm,
                   COALESCE(cg.code_nm, '')    AS grade_nm,
                   COALESCE(cs.code_nm, '')    AS size_nm
            FROM t_stock_master m
            LEFT JOIN m_common_code ci ON m.item_cd    = ci.code_cd
            LEFT JOIN m_common_code cv ON m.variety_cd = cv.code_cd
            LEFT JOIN m_common_code cg ON m.grade_cd   = cg.code_cd
            LEFT JOIN m_common_code cs ON m.size_cd    = cs.code_cd
            WHERE m.farm_cd = ?
        """
        params: list[Any] = [farm]
        if item_cd:
            sql += " AND m.item_cd = ?"
            params.append(item_cd)
        if variety_cd:
            sql += " AND m.variety_cd = ?"
            params.append(variety_cd)
        if wh_cd:
            sql += " AND m.wh_cd = ?"
            params.append(wh_cd)
        if not include_zero:
            # 현재고(real_qty)가 0이고 배정도 0인 행 숨김 (소진 재고 기본 숨김)
            sql += " AND (COALESCE(m.in_qty,0) - COALESCE(m.out_qty,0)) != 0"
        sql += " ORDER BY m.storage_dt ASC, m.rowid ASC"
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            transit_map = get_active_auction_transit_map(self.conn, farm)
            rows = []
            for row in cur.fetchall():
                stock_seq = int(_as_float(_row_val(row, "stock_seq", 0)))
                in_qty   = _as_float(_row_val(row, "in_qty", 10))
                out_qty  = _as_float(_row_val(row, "out_qty", 11))
                reserved = _as_float(_row_val(row, "reserved_qty", 12))
                real_qty = in_qty - out_qty
                transit = float(transit_map.get(stock_seq, 0.0))
                rows.append(
                    {
                        "farm_cd":    str(_row_val(row, "farm_cd", 1) or ""),
                        "wh_cd":      str(_row_val(row, "wh_cd", 2) or ""),
                        "item_cd":    str(_row_val(row, "item_cd", 3) or ""),
                        "variety_cd": str(_row_val(row, "variety_cd", 4) or ""),
                        "grade_cd":   str(_row_val(row, "grade_cd", 5) or ""),
                        "size_cd":    str(_row_val(row, "size_cd", 6) or ""),
                        "weight":     _as_float(_row_val(row, "weight", 7)),
                        "harvest_year": int(_as_float(_row_val(row, "harvest_year", 8))),
                        "storage_dt": str(_row_val(row, "storage_dt", 9) or ""),
                        "in_qty":       in_qty,
                        "out_qty":      out_qty,
                        "real_qty":     real_qty,
                        "reserved_qty": reserved,
                        "available_qty": compute_available_qty(
                            in_qty, out_qty, reserved, transit,
                        ),
                        "item_nm":    str(_row_val(row, "item_nm", 13) or ""),
                        "variety_nm": str(_row_val(row, "variety_nm", 14) or ""),
                        "grade_nm":   str(_row_val(row, "grade_nm", 15) or ""),
                        "size_nm":    str(_row_val(row, "size_nm", 16) or ""),
                    }
                )
            return rows
        finally:
            cur.close()

    # ── 재고 이력 조회 ────────────────────────────────────────────────────
    # io_type → 사람이 이해하는 명칭 매핑
    _IO_TYPE_NM: dict[str, str] = {
        "IN":          "생산입고",
        "HOLD":        "주문배정",
        "CANCEL_HOLD": "배정해제",
    }

    def _io_type_nm(self, io_type: str, remark: str) -> str:
        """io_type + remark로 표시명. OUT은 원물사용 vs 향후 판매출고를 remark로 구분."""
        t = str(io_type or "")
        r = str(remark or "")
        if t == "OUT":
            if "원물" in r:
                return "원물사용"
            if "재고조정" in r or "폐기" in r:
                return r.replace("재고조정", "").strip() or "폐기"
            return "출고"
        if t == "IN" and "재고조정" in r:
            return r.replace("재고조정", "").strip() or "재고증가"
        return self._IO_TYPE_NM.get(t, t)

    def list_stock_logs(
        self,
        farm_cd: str,
        *,
        item_cd: str | None = None,
        variety_cd: str | None = None,
        grade_cd: str | None = None,
        size_cd: str | None = None,
        weight: float | None = None,
        storage_dt: str | None = None,
        harvest_year: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        farm = str(farm_cd or "").strip()
        sql = """
            SELECT l.log_seq AS log_id, l.farm_cd, l.item_cd, l.variety_cd, l.harvest_year,
                   l.grade_cd, l.size_cd, l.weight, l.io_type, l.qty,
                   COALESCE(l.remark, '') AS remark,
                   COALESCE(l.reg_id, '') AS reg_id,
                   COALESCE(l.reg_dt, '') AS reg_dt,
                   COALESCE(cv.code_nm, '') AS variety_nm,
                   COALESCE(cg.code_nm, '') AS grade_nm,
                   COALESCE(cs.code_nm, '') AS size_nm
            FROM t_stock_log l
            LEFT JOIN m_common_code cv ON l.variety_cd = cv.code_cd
            LEFT JOIN m_common_code cg ON l.grade_cd   = cg.code_cd
            LEFT JOIN m_common_code cs ON l.size_cd    = cs.code_cd
            WHERE l.farm_cd = ?
        """
        params: list[Any] = [farm]
        for col, val in [
            ("l.item_cd",    item_cd),
            ("l.variety_cd", variety_cd),
            ("l.grade_cd",   grade_cd),
            ("l.size_cd",    size_cd),
        ]:
            if val is not None:
                sql += f" AND {col} = ?"
                params.append(str(val))
        if weight is not None:
            sql += " AND ABS(l.weight - ?) < 1e-9"
            params.append(float(weight))
        if harvest_year is not None:
            sql += " AND l.harvest_year = ?"
            params.append(int(harvest_year))
        # t_stock_log에는 storage_dt 컬럼이 없음. 마스터 입고일과 조인하지 않음.
        sql += " ORDER BY l.log_seq DESC LIMIT ?"
        params.append(int(limit))
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            rows = []
            for row in cur.fetchall():
                io_type = str(_row_val(row, "io_type", 8) or "")
                rows.append(
                    {
                        "log_id":      int(_as_float(_row_val(row, "log_id", 0))),
                        "farm_cd":     str(_row_val(row, "farm_cd", 1) or ""),
                        "item_cd":     str(_row_val(row, "item_cd", 2) or ""),
                        "variety_cd":  str(_row_val(row, "variety_cd", 3) or ""),
                        "harvest_year": int(_as_float(_row_val(row, "harvest_year", 4))),
                        "grade_cd":    str(_row_val(row, "grade_cd", 5) or ""),
                        "size_cd":     str(_row_val(row, "size_cd", 6) or ""),
                        "weight":      _as_float(_row_val(row, "weight", 7)),
                        "io_type":     io_type,
                        "io_type_nm":  self._io_type_nm(io_type, str(_row_val(row, "remark", 10) or "")),
                        "qty":         _as_float(_row_val(row, "qty", 9)),
                        "remark":      str(_row_val(row, "remark", 10) or ""),
                        "reg_id":      str(_row_val(row, "reg_id", 11) or ""),
                        "reg_dt":      str(_row_val(row, "reg_dt", 12) or ""),
                        "variety_nm":  str(_row_val(row, "variety_nm", 13) or ""),
                        "grade_nm":    str(_row_val(row, "grade_nm", 14) or ""),
                        "size_nm":     str(_row_val(row, "size_nm", 15) or ""),
                    }
                )
            return rows
        finally:
            cur.close()

    def get_allocation_summary(self, farm_cd: str, order_no: str) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        cur = self.conn.cursor()
        try:
            self._require_order(cur, farm, no)
            return self._summary(cur, farm, no)
        finally:
            cur.close()

    def allocate(
        self,
        farm_cd: str,
        order_no: str,
        *,
        order_detail_id: str,
        qty: float | None = None,
        auto: bool = False,
        user_id: str,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        det_id = str(order_detail_id or "").strip()
        if not farm or not no or not det_id:
            raise OrderValidationError(MSG_ALLOC_DETAIL_NOT_FOUND)
        now_dt = now_ops_str()
        reg_id = str(user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            result = self._allocate_in_tx(
                cur,
                farm,
                no,
                det_id=det_id,
                qty=qty,
                auto=auto,
                user_id=reg_id,
                now_dt=now_dt,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def release(
        self,
        farm_cd: str,
        order_no: str,
        *,
        order_detail_id: str,
        qty: float,
        user_id: str,
    ) -> dict[str, Any]:
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        det_id = str(order_detail_id or "").strip()
        release_qty = _as_float(qty)
        if not farm or not no or not det_id:
            raise OrderValidationError(MSG_ALLOC_DETAIL_NOT_FOUND)
        if not _qty_pos(release_qty):
            raise OrderValidationError(MSG_RELEASE_QTY_INVALID)
        now_dt = now_ops_str()
        reg_id = str(user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            self._require_order(cur, farm, no)
            self._release_detail_in_tx(
                cur,
                farm,
                no,
                det_id=det_id,
                qty=release_qty,
                user_id=reg_id,
                now_dt=now_dt,
            )
            self._assert_invariants(cur, farm, no)
            summary = self._summary(cur, farm, no)
            self.conn.commit()
            return summary
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def release_all_unshipped_in_tx(
        self,
        cur: sqlite3.Cursor,
        farm_cd: str,
        order_no: str,
        *,
        user_id: str,
        now_dt: str,
    ) -> None:
        """주문 취소 TX 안에서 미출고 배정 전량 해제. BEGIN은 호출측."""
        farm = str(farm_cd or "").strip()
        no = str(order_no or "").strip()
        cur.execute(
            f"""
            SELECT order_detail_id, SUM(shipped_qty) AS shipped
            FROM {TABLE_ORDER_ALLOC}
            WHERE farm_cd = ? AND order_no = ?
            GROUP BY order_detail_id
            """,
            (farm, no),
        )
        for row in cur.fetchall():
            if _qty_pos(_as_float(_row_val(row, "shipped", 1))):
                raise OrderValidationError(MSG_ALLOC_SHIPPED_CANCEL)
        cur.execute(
            f"""
            SELECT order_detail_id,
                   SUM(allocated_qty - shipped_qty) AS leftover
            FROM {TABLE_ORDER_ALLOC}
            WHERE farm_cd = ? AND order_no = ?
            GROUP BY order_detail_id
            """,
            (farm, no),
        )
        leftovers = [
            (
                str(_row_val(r, "order_detail_id", 0) or ""),
                _as_float(_row_val(r, "leftover", 1)),
            )
            for r in cur.fetchall()
        ]
        for det_id, leftover in leftovers:
            if _qty_pos(leftover):
                self._release_detail_in_tx(
                    cur,
                    farm,
                    no,
                    det_id=det_id,
                    qty=leftover,
                    user_id=user_id,
                    now_dt=now_dt,
                )
        self._assert_invariants(cur, farm, no)

    def _allocate_in_tx(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        *,
        det_id: str,
        qty: float | None,
        auto: bool,
        user_id: str,
        now_dt: str,
    ) -> dict[str, Any]:
        self._require_order(cur, farm, order_no, for_alloc=True)
        detail = self._lock_detail(cur, farm, order_no, det_id)
        order_qty = _as_float(detail["qty"])
        allocated = _as_float(detail["allocated_qty"])
        unallocated = order_qty - allocated
        explicit = qty is not None and not auto
        if explicit:
            request = _as_float(qty)
            if not _qty_pos(request):
                raise OrderValidationError(MSG_ALLOC_QTY_INVALID)
            if request - unallocated > _QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_OVER_ORDER)
        else:
            cap = unallocated
            if qty is not None:
                request = min(_as_float(qty), cap)
            else:
                request = cap
            if not _qty_pos(request):
                raise OrderValidationError(MSG_ALLOC_QTY_INVALID)
        candidates = self._fifo_stock_rows(cur, farm, detail)
        total_avail = sum(c["available"] for c in candidates)
        if explicit:
            if request - total_avail > _QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_QTY_UNAVAILABLE)
            need = request
        else:
            need = min(request, total_avail)
            if not _qty_pos(need):
                raise AllocationConflictError(MSG_ALLOC_NO_STOCK)
        remaining = need
        for cand in candidates:
            if remaining <= _QTY_EPS:
                break
            take = min(cand["available"], remaining)
            if not _qty_pos(take):
                continue
            key: StockKey = cand["key"]
            self._upsert_alloc(
                cur, farm, order_no, det_id, key=key, add_qty=take,
                user_id=user_id, now_dt=now_dt,
            )
            self._add_reserved(cur, key, take)
            self._insert_log(
                cur, key, io_type=IO_TYPE_HOLD, qty=take,
                remark=alloc_remark(
                    hold=True, order_no=order_no,
                    order_detail_id=det_id, storage_dt=key.storage_dt,
                ),
                user_id=user_id, now_dt=now_dt,
            )
            remaining -= take
        if remaining > _QTY_EPS:
            raise AllocationConflictError(MSG_ALLOC_QTY_UNAVAILABLE)
        cur.execute(
            f"""
            UPDATE t_order_detail
            SET {COL_ALLOCATED_QTY} = COALESCE({COL_ALLOCATED_QTY}, 0) + ?
            WHERE farm_cd = ? AND order_no = ? AND order_detail_id = ?
            """,
            (need, farm, order_no, det_id),
        )
        self._assert_invariants(cur, farm, order_no)
        return self._summary(cur, farm, order_no)

    def _release_detail_in_tx(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        *,
        det_id: str,
        qty: float,
        user_id: str,
        now_dt: str,
    ) -> None:
        leftover = self._unshipped_allocated(cur, farm, det_id)
        if qty - leftover > _QTY_EPS:
            raise AllocationConflictError(MSG_RELEASE_OVER)
        cur.execute(
            f"""
            SELECT alloc_id, allocated_qty, shipped_qty,
                   wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                   weight, harvest_year, storage_dt
            FROM {TABLE_ORDER_ALLOC}
            WHERE farm_cd = ? AND order_no = ? AND order_detail_id = ?
              AND (allocated_qty - shipped_qty) > ?
            ORDER BY storage_dt DESC, alloc_id DESC
            """,
            (farm, order_no, det_id, _QTY_EPS),
        )
        remaining = qty
        for row in cur.fetchall():
            if remaining <= _QTY_EPS:
                break
            alloc_id = str(_row_val(row, "alloc_id", 0) or "")
            allocated = _as_float(_row_val(row, "allocated_qty", 1))
            shipped = _as_float(_row_val(row, "shipped_qty", 2))
            take = min(allocated - shipped, remaining)
            if not _qty_pos(take):
                continue
            key = StockKey(
                farm_cd=farm,
                wh_cd=str(_row_val(row, "wh_cd", 3) or ""),
                item_cd=str(_row_val(row, "item_cd", 4) or ""),
                variety_cd=str(_row_val(row, "variety_cd", 5) or ""),
                grade_cd=str(_row_val(row, "grade_cd", 6) or ""),
                size_cd=str(_row_val(row, "size_cd", 7) or ""),
                weight=_as_float(_row_val(row, "weight", 8)),
                harvest_year=int(_as_float(_row_val(row, "harvest_year", 9))),
                storage_dt=str(_row_val(row, "storage_dt", 10) or ""),
            )
            new_alloc = allocated - take
            if new_alloc <= _QTY_EPS and shipped <= _QTY_EPS:
                cur.execute(
                    f"DELETE FROM {TABLE_ORDER_ALLOC} WHERE alloc_id = ?",
                    (alloc_id,),
                )
            else:
                cur.execute(
                    f"""
                    UPDATE {TABLE_ORDER_ALLOC}
                    SET allocated_qty = ?, mod_id = ?, mod_dt = ?
                    WHERE alloc_id = ?
                    """,
                    (new_alloc, user_id, now_dt, alloc_id),
                )
            self._add_reserved(cur, key, -take)
            self._insert_log(
                cur, key, io_type=IO_TYPE_CANCEL_HOLD, qty=take,
                remark=alloc_remark(
                    hold=False, order_no=order_no,
                    order_detail_id=det_id, storage_dt=key.storage_dt,
                ),
                user_id=user_id, now_dt=now_dt,
            )
            remaining -= take
        if remaining > _QTY_EPS:
            raise AllocationConflictError(MSG_RELEASE_OVER)
        cur.execute(
            f"""
            UPDATE t_order_detail
            SET {COL_ALLOCATED_QTY} = COALESCE({COL_ALLOCATED_QTY}, 0) - ?
            WHERE farm_cd = ? AND order_no = ? AND order_detail_id = ?
            """,
            (qty, farm, order_no, det_id),
        )

    def _require_order(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        *,
        for_alloc: bool = False,
    ) -> None:
        cur.execute(
            """
            SELECT status_cd FROM t_order_master
            WHERE farm_cd = ? AND order_no = ?
            """,
            (farm, order_no),
        )
        row = cur.fetchone()
        if row is None:
            raise OrderNotFoundError(MSG_ALLOC_ORDER_NOT_FOUND)
        status_cd = str(_row_val(row, "status_cd", 0) or "")
        if for_alloc:
            if status_cd == ORDER_STATUS_CANCEL_CD:
                raise OrderValidationError(MSG_ALLOC_CANCELLED)
            if status_cd in ORDER_STATUS_LOCKED:
                raise OrderValidationError(MSG_ALLOC_LOCKED)

    def _lock_detail(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        det_id: str,
    ) -> dict[str, Any]:
        cur.execute(
            f"""
            SELECT order_detail_id, item_cd, variety_cd, grade_cd, size_cd,
                   weight, qty, COALESCE({COL_ALLOCATED_QTY}, 0) AS allocated_qty,
                   wh_cd, harvest_year
            FROM t_order_detail
            WHERE farm_cd = ? AND order_no = ? AND order_detail_id = ?
            """,
            (farm, order_no, det_id),
        )
        row = cur.fetchone()
        if row is None:
            raise OrderValidationError(MSG_ALLOC_DETAIL_NOT_FOUND)
        return {
            "order_detail_id": str(_row_val(row, "order_detail_id", 0) or ""),
            "item_cd": str(_row_val(row, "item_cd", 1) or ""),
            "variety_cd": str(_row_val(row, "variety_cd", 2) or ""),
            "grade_cd": str(_row_val(row, "grade_cd", 3) or ""),
            "size_cd": str(_row_val(row, "size_cd", 4) or ""),
            "weight": _as_float(_row_val(row, "weight", 5)),
            "qty": _as_float(_row_val(row, "qty", 6)),
            "allocated_qty": _as_float(_row_val(row, "allocated_qty", 7)),
            "wh_cd": str(_row_val(row, "wh_cd", 8) or ""),
            "harvest_year": int(_as_float(_row_val(row, "harvest_year", 9))),
        }

    def _fifo_stock_rows(
        self, cur: sqlite3.Cursor, farm: str, detail: dict[str, Any]
    ) -> list[dict[str, Any]]:
        seq_col = stock_seq_select_sql(self.conn)
        cur.execute(
            f"""
            SELECT {seq_col}, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight,
                   harvest_year, storage_dt,
                   COALESCE(in_qty, 0) AS in_qty,
                   COALESCE(out_qty, 0) AS out_qty,
                   COALESCE(reserved_qty, 0) AS reserved_qty
            FROM t_stock_master
            WHERE farm_cd = ?
              AND wh_cd = ?
              AND item_cd = ?
              AND variety_cd = ?
              AND grade_cd = ?
              AND size_cd = ?
              AND ABS(weight - ?) < 1e-9
              AND harvest_year = ?
            ORDER BY storage_dt ASC, rowid ASC
            """,
            (
                farm,
                detail["wh_cd"],
                detail["item_cd"],
                detail["variety_cd"],
                detail["grade_cd"],
                detail["size_cd"],
                detail["weight"],
                detail["harvest_year"],
            ),
        )
        out: list[dict[str, Any]] = []
        transit_map = get_active_auction_transit_map(self.conn, farm)
        for row in cur.fetchall():
            stock_seq = int(_as_float(_row_val(row, "stock_seq", 0)))
            in_qty = _as_float(_row_val(row, "in_qty", 9))
            out_qty = _as_float(_row_val(row, "out_qty", 10))
            reserved = _as_float(_row_val(row, "reserved_qty", 11))
            transit = float(transit_map.get(stock_seq, 0.0))
            avail = compute_available_qty(in_qty, out_qty, reserved, transit)
            if avail <= _QTY_EPS:
                continue
            key = StockKey(
                farm_cd=farm,
                wh_cd=str(_row_val(row, "wh_cd", 1) or ""),
                item_cd=str(_row_val(row, "item_cd", 2) or ""),
                variety_cd=str(_row_val(row, "variety_cd", 3) or ""),
                grade_cd=str(_row_val(row, "grade_cd", 4) or ""),
                size_cd=str(_row_val(row, "size_cd", 5) or ""),
                weight=_as_float(_row_val(row, "weight", 6)),
                harvest_year=int(_as_float(_row_val(row, "harvest_year", 7))),
                storage_dt=str(_row_val(row, "storage_dt", 8) or ""),
            )
            out.append({"key": key, "available": avail})
        return out

    def _upsert_alloc(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        det_id: str,
        *,
        key: StockKey,
        add_qty: float,
        user_id: str,
        now_dt: str,
    ) -> None:
        cur.execute(
            f"""
            SELECT alloc_id, allocated_qty FROM {TABLE_ORDER_ALLOC}
            WHERE farm_cd = ? AND order_detail_id = ?
              AND wh_cd = ? AND item_cd = ? AND variety_cd = ?
              AND grade_cd = ? AND size_cd = ?
              AND ABS(weight - ?) < 1e-9
              AND harvest_year = ? AND storage_dt = ?
            """,
            (
                farm, det_id, key.wh_cd, key.item_cd, key.variety_cd,
                key.grade_cd, key.size_cd, key.weight, key.harvest_year,
                key.storage_dt,
            ),
        )
        row = cur.fetchone()
        if row is not None:
            alloc_id = str(_row_val(row, "alloc_id", 0) or "")
            new_qty = _as_float(_row_val(row, "allocated_qty", 1)) + add_qty
            cur.execute(
                f"""
                UPDATE {TABLE_ORDER_ALLOC}
                SET allocated_qty = ?, mod_id = ?, mod_dt = ?
                WHERE alloc_id = ?
                """,
                (new_qty, user_id, now_dt, alloc_id),
            )
            return
        alloc_id = self._next_alloc_id(cur, det_id)
        cur.execute(
            f"""
            INSERT INTO {TABLE_ORDER_ALLOC} (
                alloc_id, farm_cd, order_no, order_detail_id,
                wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt,
                allocated_qty, shipped_qty, reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                alloc_id, farm, order_no, det_id,
                key.wh_cd, key.item_cd, key.variety_cd, key.grade_cd, key.size_cd,
                key.weight, key.harvest_year, key.storage_dt,
                add_qty, user_id, now_dt, user_id, now_dt,
            ),
        )

    def _next_alloc_id(self, cur: sqlite3.Cursor, det_id: str) -> str:
        prefix = f"{det_id}-{ALLOC_ID_SUFFIX}"
        cur.execute(
            f"""
            SELECT alloc_id FROM {TABLE_ORDER_ALLOC}
            WHERE alloc_id LIKE ?
            ORDER BY alloc_id DESC LIMIT 1
            """,
            (prefix + "%",),
        )
        row = cur.fetchone()
        seq = 1
        if row is not None:
            last = str(_row_val(row, "alloc_id", 0) or "")
            tail = last.rsplit(ALLOC_ID_SUFFIX, 1)[-1]
            try:
                seq = int(tail) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{seq:0{ALLOC_ID_SEQ_LEN}d}"

    def _add_reserved(self, cur: sqlite3.Cursor, key: StockKey, delta: float) -> None:
        cur.execute(
            f"""
            UPDATE t_stock_master
            SET reserved_qty = COALESCE(reserved_qty, 0) + ?
            WHERE farm_cd = ? AND wh_cd = ? AND item_cd = ? AND variety_cd = ?
              AND grade_cd = ? AND size_cd = ? AND ABS(weight - ?) < 1e-9
              AND harvest_year = ? AND storage_dt = ?
            """,
            (delta, *key.as_tuple()),
        )
        if cur.rowcount != 1:
            raise AllocationConflictError(MSG_ALLOC_INVARIANT)
        seq_ref = stock_seq_column_ref(self.conn)
        cur.execute(
            f"""
            SELECT COALESCE(reserved_qty, 0),
                   COALESCE(in_qty, 0) - COALESCE(out_qty, 0),
                   {seq_ref}
            FROM t_stock_master
            WHERE farm_cd = ? AND wh_cd = ? AND item_cd = ? AND variety_cd = ?
              AND grade_cd = ? AND size_cd = ? AND ABS(weight - ?) < 1e-9
              AND harvest_year = ? AND storage_dt = ?
            """,
            key.as_tuple(),
        )
        row = cur.fetchone()
        reserved = _as_float(row[0])
        real_qty = _as_float(row[1])
        stock_seq = int(_as_float(row[2]))
        transit = get_active_auction_transit_qty(
            self.conn, farm_cd=key.farm_cd, stock_seq=stock_seq,
        )
        if reserved < -_QTY_EPS or reserved + transit - real_qty > _QTY_EPS:
            raise AllocationConflictError(MSG_ALLOC_INVARIANT)

    def _insert_log(
        self,
        cur: sqlite3.Cursor,
        key: StockKey,
        *,
        io_type: str,
        qty: float,
        remark: str,
        user_id: str,
        now_dt: str,
    ) -> None:
        cur.execute(
            """
            INSERT INTO t_stock_log (
                farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
                weight, io_type, qty, remark, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key.farm_cd, key.item_cd, key.variety_cd, key.harvest_year,
                key.grade_cd, key.size_cd, key.weight, io_type, qty,
                remark, user_id, now_dt,
            ),
        )

    def _unshipped_allocated(
        self, cur: sqlite3.Cursor, farm: str, det_id: str
    ) -> float:
        cur.execute(
            f"""
            SELECT COALESCE(SUM(allocated_qty - shipped_qty), 0)
            FROM {TABLE_ORDER_ALLOC}
            WHERE farm_cd = ? AND order_detail_id = ?
            """,
            (farm, det_id),
        )
        return _as_float(cur.fetchone()[0])

    def _summary(self, cur: sqlite3.Cursor, farm: str, order_no: str) -> dict[str, Any]:
        cur.execute(
            f"""
            SELECT order_detail_id, qty,
                   COALESCE({COL_ALLOCATED_QTY}, 0) AS allocated_qty
            FROM t_order_detail
            WHERE farm_cd = ? AND order_no = ?
            ORDER BY order_detail_id
            """,
            (farm, order_no),
        )
        details = []
        for row in cur.fetchall():
            det_id = str(_row_val(row, "order_detail_id", 0) or "")
            order_qty = _as_float(_row_val(row, "qty", 1))
            allocated = _as_float(_row_val(row, "allocated_qty", 2))
            cur.execute(
                f"""
                SELECT alloc_id, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                       weight, harvest_year, storage_dt,
                       allocated_qty, shipped_qty
                FROM {TABLE_ORDER_ALLOC}
                WHERE farm_cd = ? AND order_detail_id = ?
                ORDER BY storage_dt ASC, alloc_id ASC
                """,
                (farm, det_id),
            )
            allocs = []
            shipped = 0.0
            for a in cur.fetchall():
                a_ship = _as_float(_row_val(a, "shipped_qty", 10))
                shipped += a_ship
                allocs.append(
                    {
                        "alloc_id": str(_row_val(a, "alloc_id", 0) or ""),
                        "wh_cd": str(_row_val(a, "wh_cd", 1) or ""),
                        "item_cd": str(_row_val(a, "item_cd", 2) or ""),
                        "variety_cd": str(_row_val(a, "variety_cd", 3) or ""),
                        "grade_cd": str(_row_val(a, "grade_cd", 4) or ""),
                        "size_cd": str(_row_val(a, "size_cd", 5) or ""),
                        "weight": _as_float(_row_val(a, "weight", 6)),
                        "harvest_year": int(_as_float(_row_val(a, "harvest_year", 7))),
                        "storage_dt": str(_row_val(a, "storage_dt", 8) or ""),
                        "allocated_qty": _as_float(_row_val(a, "allocated_qty", 9)),
                        "shipped_qty": a_ship,
                    }
                )
            details.append(
                {
                    "order_detail_id": det_id,
                    "order_qty": order_qty,
                    "allocated_qty": allocated,
                    "unallocated_qty": order_qty - allocated,
                    "reserved_unshipped_qty": allocated - shipped,
                    "allocations": allocs,
                }
            )
        return {"order_no": order_no, "farm_cd": farm, "details": details}

    def _assert_invariants(self, cur: sqlite3.Cursor, farm: str, order_no: str) -> None:
        cur.execute(
            f"""
            SELECT d.order_detail_id, d.qty,
                   COALESCE(d.{COL_ALLOCATED_QTY}, 0) AS allocated_qty,
                   COALESCE(SUM(a.allocated_qty), 0) AS alloc_sum,
                   COALESCE(SUM(a.shipped_qty), 0) AS shipped_sum
            FROM t_order_detail d
            LEFT JOIN {TABLE_ORDER_ALLOC} a
              ON a.farm_cd = d.farm_cd AND a.order_detail_id = d.order_detail_id
            WHERE d.farm_cd = ? AND d.order_no = ?
            GROUP BY d.order_detail_id
            """,
            (farm, order_no),
        )
        for row in cur.fetchall():
            qty = _as_float(_row_val(row, "qty", 1))
            allocated = _as_float(_row_val(row, "allocated_qty", 2))
            alloc_sum = _as_float(_row_val(row, "alloc_sum", 3))
            shipped = _as_float(_row_val(row, "shipped_sum", 4))
            if allocated < -_QTY_EPS or shipped < -_QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
            # STOCK 경로: shipped <= allocated. DIRECT 출고는 Stage 4 (DEC-020).
            if shipped - allocated > _QTY_EPS or allocated - qty > _QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
            if abs(allocated - alloc_sum) > 1e-6:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
        cur.execute(
            f"""
            SELECT s.wh_cd, s.item_cd, s.variety_cd, s.grade_cd, s.size_cd,
                   s.weight, s.harvest_year, s.storage_dt,
                   COALESCE(s.reserved_qty, 0) AS reserved_qty,
                   COALESCE(s.in_qty, 0) - COALESCE(s.out_qty, 0) AS real_qty,
                   COALESCE(SUM(a.allocated_qty - a.shipped_qty), 0) AS hold_sum
            FROM t_stock_master s
            LEFT JOIN {TABLE_ORDER_ALLOC} a
              ON a.farm_cd = s.farm_cd AND a.wh_cd = s.wh_cd
             AND a.item_cd = s.item_cd AND a.variety_cd = s.variety_cd
             AND a.grade_cd = s.grade_cd AND a.size_cd = s.size_cd
             AND ABS(a.weight - s.weight) < 1e-9
             AND a.harvest_year = s.harvest_year
             AND a.storage_dt = s.storage_dt
            WHERE s.farm_cd = ?
            GROUP BY s.wh_cd, s.item_cd, s.variety_cd, s.grade_cd, s.size_cd,
                     s.weight, s.harvest_year, s.storage_dt
            """,
            (farm,),
        )
        for row in cur.fetchall():
            reserved = _as_float(_row_val(row, "reserved_qty", 8))
            real_qty = _as_float(_row_val(row, "real_qty", 9))
            hold_sum = _as_float(_row_val(row, "hold_sum", 10))
            if reserved < -_QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
            # 과거 과출고(real<0) + reserved=0 은 다른 로트 배정을 막지 않는다.
            if real_qty >= -_QTY_EPS and reserved - real_qty > _QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
            if real_qty < -_QTY_EPS and reserved > _QTY_EPS:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
            if abs(reserved - hold_sum) > 1e-6:
                raise AllocationConflictError(MSG_ALLOC_INVARIANT)
