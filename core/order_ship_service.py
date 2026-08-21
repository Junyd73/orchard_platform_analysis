# -*- coding: utf-8 -*-
"""공통 출고/판매 확정 — 단일 TX (Stage 5C, DEC-027)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from core.ops_biz_date import now_ops_str, today_ops
from core.order_alloc_constants import COL_ALLOCATED_QTY, TABLE_ORDER_ALLOC
from core.order_constants import (
    DELIVERY_TP_PARCEL_CD,
    ORDER_STATUS_CANCEL_CD,
    ORDER_STATUS_DELIVERED_CD,
    ORDER_STATUS_PREP_CD,
    ORDER_STATUS_SHIPABLE,
    WAREHOUSE_CD_DEFAULT,
)
from core.order_service import OrderNotFoundError, OrderSaveError
from core.order_ship_constants import (
    CODE_SHIP_ORDER_NOT_CONFIRMED,
    IO_TYPE_OUT,
    MSG_ALLOC_OVER_SHIP,
    MSG_DATA_INTEGRITY,
    MSG_DELIVERY_SCHEMA,
    MSG_DETAIL_REQUIRED,
    MSG_ORDER_LOCKED,
    MSG_ORDER_OVER_SHIP,
    MSG_PARCEL_DEST_INCOMPLETE,
    MSG_PARCEL_DEST_QTY,
    MSG_PARCEL_DEST_REQUIRED,
    MSG_PARCEL_QTY_MISMATCH,
    MSG_PARCEL_SHIP_FEE_MISMATCH,
    MSG_PARCEL_SHIP_FEE_NEG,
    MSG_REMARK_SALE_OUT,
    MSG_SCHEMA_PRECONDITION,
    MSG_SENDER_REQUIRED,
    MSG_SHIP_LINES_REQUIRED,
    MSG_SHIP_MODE_INVALID,
    MSG_SHIP_ORDER_NOT_CONFIRMED,
    MSG_SHIP_QTY_INVALID,
    MSG_STOCK_REQUIRES_ORDER,
    MSG_STOCK_UNAVAILABLE,
    SALES_DETAIL_SEQ_LEN,
    SALES_SOURCE_ORDER,
    SALES_STATUS_CONFIRMED,
    SHIP_MODE_STOCK,
    SHIP_MODES,
    STOCK_STATUS_DONE,
)
from core.order_ship_delivery import (
    ShipDeliveryAllocIn,
    alloc_qty_sum,
    alloc_ship_fee_sum,
    bridge_allocs_to_fifo_details,
)
from core.order_ship_qty import confirmed_shipped_qty, order_line_ship_remainder
from core.sales_stock_trace_schema import REF_TYPE_SALE

_QTY_EPS = 1e-9


class ShipError(OrderSaveError):
    def __init__(self, message: str, *, code: str = "SHIP_ERROR"):
        super().__init__(message, code=code)


class ShipValidationError(ShipError):
    def __init__(self, message: str, *, code: str = "SHIP_VALIDATION"):
        super().__init__(message, code=code)


class ShipConflictError(ShipError):
    def __init__(self, message: str, *, code: str = "SHIP_CONFLICT"):
        super().__init__(message, code=code)


@dataclass
class ShipLineIn:
    qty: float
    order_detail_id: str | None = None
    item_cd: str = ""
    variety_cd: str = ""
    grade_cd: str = ""
    size_cd: str = ""
    weight: float = 0.0
    harvest_year: int = 0
    wh_cd: str = ""
    unit_price: float = 0.0
    # None = legacy caller (미전송). list = 2C 명시(빈 배열이면 택배 검증 실패).
    delivery_allocations: list[ShipDeliveryAllocIn] | None = None


@dataclass
class ShipConfirmIn:
    farm_cd: str
    ship_mode: str
    lines: list[ShipLineIn] = field(default_factory=list)
    order_no: str | None = None
    sales_dt: str = ""
    custm_id: str | None = None
    user_id: str = "SYSTEM"
    rmk: str = ""
    dlvry_tp: str = ""
    ship_fee: float = 0.0
    rcv_name: str = ""
    rcv_tel: str = ""
    rcv_addr: str = ""
    dlvry_msg: str = ""
    snd_name: str = ""
    snd_tel: str = ""
    snd_addr: str = ""


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _qty_pos(value: float) -> bool:
    return value > _QTY_EPS


def _qty_le(a: float, b: float) -> bool:
    return a <= b + _QTY_EPS


def _qty_eq(a: float, b: float) -> bool:
    return abs(a - b) <= _QTY_EPS


def _row_val(row: Any, key: str, idx: int) -> Any:
    if isinstance(row, sqlite3.Row):
        try:
            return row[key]
        except (KeyError, IndexError):
            return row[idx]
    return row[idx]


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    return column in {str(r[1]) for r in cur.execute(f"PRAGMA table_info({table})")}


def generate_sales_no(cur: sqlite3.Cursor, farm_cd: str, sales_dt: str) -> str:
    date_part = str(sales_dt or "").replace("-", "")
    if len(date_part) != 8 or not date_part.isdigit():
        date_part = today_ops().strftime("%Y%m%d")
    pattern = f"{date_part}-%"
    cur.execute(
        """
        SELECT MAX(sales_no) AS max_no
        FROM t_sales_master
        WHERE sales_no LIKE ? AND farm_cd = ?
        """,
        (pattern, str(farm_cd or "").strip()),
    )
    row = cur.fetchone()
    max_no = None
    if row is not None:
        max_no = row["max_no"] if isinstance(row, sqlite3.Row) else row[0]
    new_seq = 1
    if max_no:
        try:
            new_seq = int(str(max_no).split("-")[1]) + 1
        except (TypeError, ValueError, IndexError):
            new_seq = 1
    return f"{date_part}-{new_seq:02d}"


class OrderShipService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def confirm(self, payload: ShipConfirmIn) -> dict[str, Any]:
        farm = str(payload.farm_cd or "").strip()
        mode = str(payload.ship_mode or "").strip().upper()
        order_no = str(payload.order_no or "").strip() or None
        if mode not in SHIP_MODES:
            raise ShipValidationError(MSG_SHIP_MODE_INVALID, code="SHIP_MODE_INVALID")
        if mode == SHIP_MODE_STOCK and not order_no:
            raise ShipValidationError(MSG_STOCK_REQUIRES_ORDER, code="SHIP_STOCK_REQUIRES_ORDER")
        if not payload.lines:
            raise ShipValidationError(MSG_SHIP_LINES_REQUIRED, code="SHIP_LINES_REQUIRED")
        now_dt = now_ops_str()
        sales_dt = str(payload.sales_dt or "").strip() or today_ops().strftime("%Y-%m-%d")
        user_id = str(payload.user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            self._require_trace_schema(cur)
            if mode == SHIP_MODE_STOCK:
                self._require_alloc_schema(cur)
            result = self._confirm_in_tx(
                cur,
                farm=farm,
                mode=mode,
                order_no=order_no,
                payload=payload,
                sales_dt=sales_dt,
                user_id=user_id,
                now_dt=now_dt,
            )
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def _confirm_in_tx(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        mode: str,
        order_no: str | None,
        payload: ShipConfirmIn,
        sales_dt: str,
        user_id: str,
        now_dt: str,
    ) -> dict[str, Any]:
        custm_id = str(payload.custm_id or "").strip() or None
        if order_no:
            master = self._load_order_master(cur, farm, order_no)
            if not custm_id:
                custm_id = str(master.get("custm_id") or "").strip() or None

        # 재고 차감 전 배송배분 검증 (실패 시 OUT/sales 0건)
        multi_delivery = self._validate_and_normalize_delivery(payload)

        splits: list[dict[str, Any]] = []
        for line_idx, line in enumerate(payload.lines):
            planned = self._plan_line(
                cur, farm=farm, mode=mode, order_no=order_no, line=line,
            )
            for sp in planned:
                sp["_line_idx"] = line_idx
            splits.extend(planned)
        for sp in splits:
            self._apply_stock(cur, mode=mode, split=sp, user_id=user_id, now_dt=now_dt)

        sales_no = generate_sales_no(cur, farm, sales_dt)
        tot_item = sum(_as_float(s["qty"]) * _as_float(s["unit_price"]) for s in splits)
        ship_fee = max(0.0, _as_float(getattr(payload, "ship_fee", 0) or 0))
        tot_sales = tot_item + ship_fee
        dlvry_tp = str(getattr(payload, "dlvry_tp", "") or "").strip()
        self._insert_sales_master(
            cur,
            farm=farm,
            sales_no=sales_no,
            sales_dt=sales_dt,
            order_no=order_no,
            custm_id=custm_id,
            tot_item=tot_item,
            tot_ship_fee=ship_fee,
            tot_sales=tot_sales,
            rmk=str(payload.rmk or ""),
            user_id=user_id,
            now_dt=now_dt,
        )

        # logical line → FIFO detail 목록 (배송 bridge / line별 배송비)
        line_details: dict[int, list[tuple[str, float]]] = {}
        line_fee_applied: set[int] = set()
        detail_rows: list[dict[str, Any]] = []
        stock_effects: list[dict[str, Any]] = []

        for idx, sp in enumerate(splits, start=1):
            det_no = f"{sales_no}-S{idx:0{SALES_DETAIL_SEQ_LEN}d}"
            line_idx = int(sp.get("_line_idx", 0))
            if multi_delivery:
                # 2C: logical line 배송비 합 → 해당 line 첫 FIFO detail만
                if line_idx not in line_fee_applied:
                    allocs = payload.lines[line_idx].delivery_allocations or []
                    line_ship_fee = alloc_ship_fee_sum(allocs)
                    line_fee_applied.add(line_idx)
                else:
                    line_ship_fee = 0.0
            else:
                # legacy: 판매 전체 배송비를 첫 detail에만
                line_ship_fee = ship_fee if idx == 1 else 0.0

            self._insert_sales_detail(
                cur,
                farm=farm,
                sales_no=sales_no,
                det_no=det_no,
                split=sp,
                dlvry_tp=dlvry_tp,
                ship_fee=line_ship_fee,
                user_id=user_id,
                now_dt=now_dt,
            )
            self._insert_stock_log(
                cur, farm=farm, det_no=det_no, split=sp, user_id=user_id, now_dt=now_dt,
            )
            line_details.setdefault(line_idx, []).append((det_no, _as_float(sp["qty"])))
            detail_rows.append(
                {
                    "sale_detail_no": det_no,
                    "order_detail_id": sp.get("order_detail_id"),
                    "stock_seq": int(sp["stock_seq"]),
                    "qty": sp["qty"],
                }
            )
            stock_effects.append(
                {
                    "stock_seq": int(sp["stock_seq"]),
                    "qty": sp["qty"],
                    "ship_mode": mode,
                }
            )

        if multi_delivery:
            self._persist_multi_deliveries(
                cur,
                farm=farm,
                sales_no=sales_no,
                payload=payload,
                line_details=line_details,
                user_id=user_id,
            )
        else:
            for det_no, qty in (
                (d["sale_detail_no"], _as_float(d["qty"])) for d in detail_rows
            ):
                self._insert_sales_delivery(
                    cur,
                    farm=farm,
                    sales_no=sales_no,
                    det_no=det_no,
                    qty=qty,
                    payload=payload,
                    user_id=user_id,
                )

        order_status = None
        stock_status = None
        remaining: list[dict[str, Any]] = []
        if order_no:
            order_status, stock_status, remaining = self._update_order_status(
                cur, farm=farm, order_no=order_no, user_id=user_id, now_dt=now_dt,
            )
            self._touch_order_sales_no(cur, farm, order_no, sales_no, user_id, now_dt)

        return {
            "ok": True,
            "sales_no": sales_no,
            "ship_mode": mode,
            "order_no": order_no,
            "sales_details": detail_rows,
            "stock_effects": stock_effects,
            "order_status_cd": order_status,
            "stock_status": stock_status,
            "remaining_order": remaining,
        }

    def _validate_and_normalize_delivery(self, payload: ShipConfirmIn) -> bool:
        """택배 2C allocation 검증. True면 multi-delivery 경로.

        null/미전송 = legacy. 택배에서 한 line이라도 list면 전 line 배열 필수.
        """
        dlvry_tp = str(getattr(payload, "dlvry_tp", "") or "").strip()
        is_parcel = dlvry_tp == DELIVERY_TP_PARCEL_CD
        any_explicit = any(ln.delivery_allocations is not None for ln in payload.lines)
        if not any_explicit:
            return False
        if not is_parcel:
            # 방문/직접: allocation 미사용(legacy 유지). 명시해도 무시.
            return False

        snd_name = str(getattr(payload, "snd_name", "") or "").strip()
        snd_tel = str(getattr(payload, "snd_tel", "") or "").strip()
        snd_addr = str(getattr(payload, "snd_addr", "") or "").strip()
        if not (snd_name and snd_tel and snd_addr):
            raise ShipValidationError(MSG_SENDER_REQUIRED, code="SENDER_REQUIRED")

        fee_total = 0.0
        for line in payload.lines:
            allocs = line.delivery_allocations
            if allocs is None:
                raise ShipValidationError(
                    MSG_PARCEL_DEST_REQUIRED, code="PARCEL_DEST_REQUIRED"
                )
            if not allocs:
                raise ShipValidationError(
                    MSG_PARCEL_DEST_REQUIRED, code="PARCEL_DEST_REQUIRED"
                )
            for alloc in allocs:
                if not _qty_pos(_as_float(alloc.qty)):
                    raise ShipValidationError(
                        MSG_PARCEL_DEST_QTY, code="PARCEL_DEST_QTY"
                    )
                name = str(alloc.rcv_name or "").strip()
                tel = str(alloc.rcv_tel or "").strip()
                addr = str(alloc.rcv_addr or "").strip()
                if not (name and tel and addr):
                    raise ShipValidationError(
                        MSG_PARCEL_DEST_INCOMPLETE, code="PARCEL_DEST_INCOMPLETE"
                    )
                fee = _as_float(alloc.ship_fee)
                if fee < -_QTY_EPS:
                    raise ShipValidationError(
                        MSG_PARCEL_SHIP_FEE_NEG, code="PARCEL_SHIP_FEE_NEG"
                    )
                alloc.ship_fee = max(0.0, fee)
                fee_total += alloc.ship_fee
            if not _qty_eq(alloc_qty_sum(allocs), _as_float(line.qty)):
                raise ShipValidationError(
                    MSG_PARCEL_QTY_MISMATCH, code="PARCEL_QTY_MISMATCH"
                )

        req_fee = max(0.0, _as_float(getattr(payload, "ship_fee", 0) or 0))
        if not _qty_eq(req_fee, fee_total):
            raise ShipValidationError(
                MSG_PARCEL_SHIP_FEE_MISMATCH, code="PARCEL_SHIP_FEE_MISMATCH"
            )
        payload.ship_fee = fee_total
        return True

    def _persist_multi_deliveries(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        sales_no: str,
        payload: ShipConfirmIn,
        line_details: dict[int, list[tuple[str, float]]],
        user_id: str,
    ) -> None:
        # 2C multi_delivery: table/columns 필수 (legacy silent skip과 분리)
        if not _table_exists(cur, "t_sales_delivery"):
            raise ShipError(MSG_DELIVERY_SCHEMA, code="SCHEMA_PRECONDITION")
        has_group = _column_exists(cur, "t_sales_delivery", "dlvry_group_no")
        has_fee = _column_exists(cur, "t_sales_delivery", "ship_fee")
        has_snd = (
            _column_exists(cur, "t_sales_delivery", "snd_name")
            and _column_exists(cur, "t_sales_delivery", "snd_tel")
            and _column_exists(cur, "t_sales_delivery", "snd_addr")
        )
        if not (has_group and has_fee):
            raise ShipError(MSG_DELIVERY_SCHEMA, code="SCHEMA_PRECONDITION")
        if not has_snd:
            raise ShipError(MSG_DELIVERY_SCHEMA, code="SCHEMA_PRECONDITION")

        snd_name = str(getattr(payload, "snd_name", "") or "").strip() or None
        snd_tel = str(getattr(payload, "snd_tel", "") or "").strip() or None
        snd_addr = str(getattr(payload, "snd_addr", "") or "").strip() or None

        group_seq = 1
        for line_idx, line in enumerate(payload.lines):
            allocs = line.delivery_allocations or []
            details = line_details.get(line_idx) or []
            try:
                rows, group_seq = bridge_allocs_to_fifo_details(
                    sales_no=sales_no,
                    detail_rows=details,
                    allocations=allocs,
                    group_seq_start=group_seq,
                )
            except ValueError as exc:
                raise ShipValidationError(
                    MSG_PARCEL_QTY_MISMATCH, code="PARCEL_QTY_MISMATCH"
                ) from exc
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO t_sales_delivery (
                        dlvry_no, sale_detail_no, sales_no, farm_cd,
                        snd_name, snd_tel, snd_addr,
                        rcv_name, rcv_tel, rcv_addr, dlvry_qty, dlvry_msg,
                        dlvry_group_no, ship_fee, reg_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["dlvry_no"],
                        row["sale_detail_no"],
                        sales_no,
                        farm,
                        snd_name,
                        snd_tel,
                        snd_addr,
                        row["rcv_name"] or None,
                        row["rcv_tel"] or None,
                        row["rcv_addr"] or None,
                        row["dlvry_qty"],
                        row["dlvry_msg"] or None,
                        row["dlvry_group_no"],
                        float(row["ship_fee"] or 0),
                        user_id,
                    ),
                )

    def _require_trace_schema(self, cur: sqlite3.Cursor) -> None:
        need = (
            ("t_sales_master", None),
            ("t_sales_detail", "stock_seq"),
            ("t_stock_master", "stock_seq"),
            ("t_stock_log", "stock_seq"),
            ("t_stock_log", "ref_type"),
            ("t_stock_log", "ref_id"),
        )
        for table, col in need:
            if not _table_exists(cur, table):
                raise ShipError(MSG_SCHEMA_PRECONDITION, code="SCHEMA_PRECONDITION")
            if col and not _column_exists(cur, table, col):
                raise ShipError(MSG_SCHEMA_PRECONDITION, code="SCHEMA_PRECONDITION")

    def _require_alloc_schema(self, cur: sqlite3.Cursor) -> None:
        if not _table_exists(cur, TABLE_ORDER_ALLOC):
            raise ShipError(MSG_SCHEMA_PRECONDITION, code="SCHEMA_PRECONDITION")
        if not _column_exists(cur, "t_order_detail", COL_ALLOCATED_QTY):
            raise ShipError(MSG_SCHEMA_PRECONDITION, code="SCHEMA_PRECONDITION")

    def _load_order_master(
        self, cur: sqlite3.Cursor, farm: str, order_no: str
    ) -> dict[str, Any]:
        cur.execute(
            """
            SELECT order_no, custm_id, status_cd, stock_status, sales_no
            FROM t_order_master
            WHERE farm_cd = ? AND order_no = ?
            """,
            (farm, order_no),
        )
        row = cur.fetchone()
        if row is None:
            raise OrderNotFoundError()
        status = str(_row_val(row, "status_cd", 2) or "")
        if status in {ORDER_STATUS_CANCEL_CD, ORDER_STATUS_DELIVERED_CD}:
            raise ShipValidationError(MSG_ORDER_LOCKED, code="SHIP_ORDER_LOCKED")
        if status not in ORDER_STATUS_SHIPABLE:
            raise ShipValidationError(
                MSG_SHIP_ORDER_NOT_CONFIRMED,
                code=CODE_SHIP_ORDER_NOT_CONFIRMED,
            )
        return {
            "order_no": str(_row_val(row, "order_no", 0) or ""),
            "custm_id": _row_val(row, "custm_id", 1),
            "status_cd": status,
        }

    def _plan_line(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        mode: str,
        order_no: str | None,
        line: ShipLineIn,
    ) -> list[dict[str, Any]]:
        qty = _as_float(line.qty)
        if not _qty_pos(qty):
            raise ShipValidationError(MSG_SHIP_QTY_INVALID, code="SHIP_QTY_INVALID")
        det_id = str(line.order_detail_id or "").strip() or None
        if det_id:
            if not order_no:
                raise ShipValidationError(
                    MSG_STOCK_REQUIRES_ORDER, code="SHIP_STOCK_REQUIRES_ORDER"
                )
            spec = self._load_order_detail(cur, farm, order_no, det_id)
            remaining = spec["qty"] - self._confirmed_shipped(cur, farm, det_id)
            if not _qty_le(qty, remaining):
                raise ShipConflictError(MSG_ORDER_OVER_SHIP, code="ORDER_OVER_SHIP")
        else:
            if mode == SHIP_MODE_STOCK:
                raise ShipValidationError(MSG_DETAIL_REQUIRED, code="SHIP_DETAIL_REQUIRED")
            spec = {
                "item_cd": str(line.item_cd or "").strip(),
                "variety_cd": str(line.variety_cd or "").strip(),
                "grade_cd": str(line.grade_cd or "").strip(),
                "size_cd": str(line.size_cd or "").strip(),
                "weight": _as_float(line.weight),
                "harvest_year": int(line.harvest_year or 0),
                "wh_cd": str(line.wh_cd or "").strip() or WAREHOUSE_CD_DEFAULT,
                "order_detail_id": None,
            }
        unit_price = _as_float(line.unit_price)
        if mode == SHIP_MODE_STOCK:
            return self._plan_stock(
                cur, farm, order_no or "", det_id or "", qty, spec, unit_price
            )
        return self._plan_direct(cur, farm, qty, spec, unit_price, det_id)

    def _load_order_detail(
        self, cur: sqlite3.Cursor, farm: str, order_no: str, det_id: str
    ) -> dict[str, Any]:
        cur.execute(
            """
            SELECT item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year,
                   wh_cd, qty, order_detail_id
            FROM t_order_detail
            WHERE farm_cd = ? AND order_no = ? AND order_detail_id = ?
            """,
            (farm, order_no, det_id),
        )
        row = cur.fetchone()
        if row is None:
            raise ShipValidationError(MSG_DETAIL_REQUIRED, code="SHIP_DETAIL_NOT_FOUND")
        return {
            "item_cd": str(_row_val(row, "item_cd", 0) or ""),
            "variety_cd": str(_row_val(row, "variety_cd", 1) or ""),
            "grade_cd": str(_row_val(row, "grade_cd", 2) or ""),
            "size_cd": str(_row_val(row, "size_cd", 3) or ""),
            "weight": _as_float(_row_val(row, "weight", 4)),
            "harvest_year": int(_as_float(_row_val(row, "harvest_year", 5))),
            "wh_cd": str(_row_val(row, "wh_cd", 6) or "") or WAREHOUSE_CD_DEFAULT,
            "qty": _as_float(_row_val(row, "qty", 7)),
            "order_detail_id": str(_row_val(row, "order_detail_id", 8) or det_id),
        }

    def _confirmed_shipped(self, cur: sqlite3.Cursor, farm: str, det_id: str) -> float:
        return confirmed_shipped_qty(cur, farm, det_id)

    def _plan_stock(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        det_id: str,
        qty: float,
        spec: dict[str, Any],
        unit_price: float,
    ) -> list[dict[str, Any]]:
        cur.execute(
            f"""
            SELECT alloc_id, allocated_qty, shipped_qty,
                   wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                   weight, harvest_year, storage_dt
            FROM {TABLE_ORDER_ALLOC}
            WHERE farm_cd = ? AND order_no = ? AND order_detail_id = ?
              AND (allocated_qty - shipped_qty) > ?
            ORDER BY storage_dt ASC, alloc_id ASC
            """,
            (farm, order_no, det_id, _QTY_EPS),
        )
        rows = list(cur.fetchall())
        leftover = sum(
            _as_float(_row_val(r, "allocated_qty", 1))
            - _as_float(_row_val(r, "shipped_qty", 2))
            for r in rows
        )
        if not _qty_le(qty, leftover):
            raise ShipConflictError(MSG_ALLOC_OVER_SHIP, code="ALLOC_OVER_SHIP")
        remaining = qty
        splits: list[dict[str, Any]] = []
        for row in rows:
            if remaining <= _QTY_EPS:
                break
            alloc_id = str(_row_val(row, "alloc_id", 0) or "")
            allocated = _as_float(_row_val(row, "allocated_qty", 1))
            shipped = _as_float(_row_val(row, "shipped_qty", 2))
            take = min(allocated - shipped, remaining)
            if not _qty_pos(take):
                continue
            stock = self._lock_stock_row(
                cur,
                farm,
                wh_cd=str(_row_val(row, "wh_cd", 3) or ""),
                item_cd=str(_row_val(row, "item_cd", 4) or ""),
                variety_cd=str(_row_val(row, "variety_cd", 5) or ""),
                grade_cd=str(_row_val(row, "grade_cd", 6) or ""),
                size_cd=str(_row_val(row, "size_cd", 7) or ""),
                weight=_as_float(_row_val(row, "weight", 8)),
                harvest_year=int(_as_float(_row_val(row, "harvest_year", 9))),
                storage_dt=str(_row_val(row, "storage_dt", 10) or ""),
            )
            real_qty = stock["in_qty"] - stock["out_qty"]
            if real_qty + _QTY_EPS < take or stock["reserved_qty"] + _QTY_EPS < take:
                raise ShipConflictError(MSG_DATA_INTEGRITY, code="DATA_INTEGRITY")
            splits.append(self._split_row(stock, take, unit_price, det_id, alloc_id))
            remaining -= take
        if remaining > _QTY_EPS:
            raise ShipConflictError(MSG_ALLOC_OVER_SHIP, code="ALLOC_OVER_SHIP")
        return splits

    def _plan_direct(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        qty: float,
        spec: dict[str, Any],
        unit_price: float,
        det_id: str | None,
    ) -> list[dict[str, Any]]:
        rows = self._fifo_available(cur, farm, spec)
        total_avail = sum(r["available"] for r in rows)
        if not _qty_le(qty, total_avail):
            raise ShipConflictError(MSG_STOCK_UNAVAILABLE, code="STOCK_UNAVAILABLE")
        remaining = qty
        splits: list[dict[str, Any]] = []
        for row in rows:
            if remaining <= _QTY_EPS:
                break
            take = min(row["available"], remaining)
            if not _qty_pos(take):
                continue
            splits.append(self._split_row(row["stock"], take, unit_price, det_id, None))
            remaining -= take
        if remaining > _QTY_EPS:
            raise ShipConflictError(MSG_STOCK_UNAVAILABLE, code="STOCK_UNAVAILABLE")
        return splits

    def _split_row(
        self,
        stock: dict[str, Any],
        qty: float,
        unit_price: float,
        det_id: str | None,
        alloc_id: str | None,
    ) -> dict[str, Any]:
        return {
            "alloc_id": alloc_id,
            "stock_seq": stock["stock_seq"],
            "qty": qty,
            "unit_price": unit_price,
            "order_detail_id": det_id,
            "item_cd": stock["item_cd"],
            "variety_cd": stock["variety_cd"],
            "grade_cd": stock["grade_cd"],
            "size_cd": stock["size_cd"],
            "weight": stock["weight"],
            "harvest_year": stock["harvest_year"],
            "wh_cd": stock["wh_cd"],
            "storage_dt": stock["storage_dt"],
        }

    def _fifo_available(
        self, cur: sqlite3.Cursor, farm: str, spec: dict[str, Any]
    ) -> list[dict[str, Any]]:
        cur.execute(
            """
            SELECT stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                   weight, harvest_year, storage_dt,
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
            ORDER BY storage_dt ASC, stock_seq ASC
            """,
            (
                farm,
                spec["wh_cd"],
                spec["item_cd"],
                spec["variety_cd"],
                spec["grade_cd"],
                spec["size_cd"],
                spec["weight"],
                spec["harvest_year"],
            ),
        )
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            stock = self._stock_dict(row)
            avail = stock["in_qty"] - stock["out_qty"] - stock["reserved_qty"]
            if avail <= _QTY_EPS:
                continue
            out.append({"stock": stock, "available": avail})
        return out

    def _lock_stock_row(self, cur: sqlite3.Cursor, farm: str, **key: Any) -> dict[str, Any]:
        cur.execute(
            """
            SELECT stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                   weight, harvest_year, storage_dt,
                   COALESCE(in_qty, 0) AS in_qty,
                   COALESCE(out_qty, 0) AS out_qty,
                   COALESCE(reserved_qty, 0) AS reserved_qty
            FROM t_stock_master
            WHERE farm_cd = ? AND wh_cd = ? AND item_cd = ? AND variety_cd = ?
              AND grade_cd = ? AND size_cd = ? AND ABS(weight - ?) < 1e-9
              AND harvest_year = ? AND storage_dt = ?
            """,
            (
                farm, key["wh_cd"], key["item_cd"], key["variety_cd"],
                key["grade_cd"], key["size_cd"], key["weight"],
                key["harvest_year"], key["storage_dt"],
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise ShipConflictError(MSG_DATA_INTEGRITY, code="DATA_INTEGRITY")
        return self._stock_dict(row)

    def _stock_dict(self, row: Any) -> dict[str, Any]:
        seq = _row_val(row, "stock_seq", 0)
        if seq is None:
            raise ShipError(MSG_SCHEMA_PRECONDITION, code="SCHEMA_PRECONDITION")
        return {
            "stock_seq": int(seq),
            "farm_cd": str(_row_val(row, "farm_cd", 1) or ""),
            "wh_cd": str(_row_val(row, "wh_cd", 2) or ""),
            "item_cd": str(_row_val(row, "item_cd", 3) or ""),
            "variety_cd": str(_row_val(row, "variety_cd", 4) or ""),
            "grade_cd": str(_row_val(row, "grade_cd", 5) or ""),
            "size_cd": str(_row_val(row, "size_cd", 6) or ""),
            "weight": _as_float(_row_val(row, "weight", 7)),
            "harvest_year": int(_as_float(_row_val(row, "harvest_year", 8))),
            "storage_dt": str(_row_val(row, "storage_dt", 9) or ""),
            "in_qty": _as_float(_row_val(row, "in_qty", 10)),
            "out_qty": _as_float(_row_val(row, "out_qty", 11)),
            "reserved_qty": _as_float(_row_val(row, "reserved_qty", 12)),
        }

    def _apply_stock(
        self,
        cur: sqlite3.Cursor,
        *,
        mode: str,
        split: dict[str, Any],
        user_id: str,
        now_dt: str,
    ) -> None:
        qty = _as_float(split["qty"])
        seq = int(split["stock_seq"])
        if mode == SHIP_MODE_STOCK:
            cur.execute(
                f"""
                UPDATE {TABLE_ORDER_ALLOC}
                SET shipped_qty = shipped_qty + ?, mod_id = ?, mod_dt = ?
                WHERE alloc_id = ?
                  AND shipped_qty + ? <= allocated_qty + 1e-9
                """,
                (qty, user_id, now_dt, split["alloc_id"], qty),
            )
            if cur.rowcount != 1:
                raise ShipConflictError(MSG_DATA_INTEGRITY, code="DATA_INTEGRITY")
            cur.execute(
                """
                UPDATE t_stock_master
                SET reserved_qty = reserved_qty - ?,
                    out_qty = out_qty + ?,
                    mod_id = ?, mod_dt = ?
                WHERE stock_seq = ?
                  AND reserved_qty + 1e-9 >= ?
                  AND (in_qty - out_qty) + 1e-9 >= ?
                """,
                (qty, qty, user_id, now_dt, seq, qty, qty),
            )
        else:
            cur.execute(
                """
                UPDATE t_stock_master
                SET out_qty = out_qty + ?,
                    mod_id = ?, mod_dt = ?
                WHERE stock_seq = ?
                  AND (in_qty - out_qty - COALESCE(reserved_qty, 0)) + 1e-9 >= ?
                """,
                (qty, user_id, now_dt, seq, qty),
            )
        if cur.rowcount != 1:
            raise ShipConflictError(MSG_DATA_INTEGRITY, code="DATA_INTEGRITY")

    def _insert_sales_master(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        sales_no: str,
        sales_dt: str,
        order_no: str | None,
        custm_id: str | None,
        tot_item: float,
        tot_ship_fee: float = 0.0,
        tot_sales: float | None = None,
        rmk: str,
        user_id: str,
        now_dt: str,
    ) -> None:
        sales_amt = tot_item if tot_sales is None else float(tot_sales)
        unpaid = sales_amt
        cur.execute(
            """
            INSERT INTO t_sales_master (
                sales_no, farm_cd, sales_dt, sales_tp, custm_id,
                tot_sales_amt, tot_ship_fee, tot_item_amt, tot_paid_amt, tot_unpaid_amt,
                status_cd, rmk, reg_id, reg_dt, order_no, sales_status, sales_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, '10', ?, ?, ?, ?, ?, ?)
            """,
            (
                sales_no, farm, sales_dt, "NORMAL", custm_id,
                sales_amt, float(tot_ship_fee or 0), tot_item, unpaid,
                rmk, user_id, now_dt,
                order_no, SALES_STATUS_CONFIRMED, SALES_SOURCE_ORDER,
            ),
        )

    def _insert_sales_detail(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        sales_no: str,
        det_no: str,
        split: dict[str, Any],
        dlvry_tp: str = "",
        ship_fee: float = 0.0,
        user_id: str,
        now_dt: str,
    ) -> None:
        qty = _as_float(split["qty"])
        price = _as_float(split["unit_price"])
        amt = qty * price
        seq = split.get("stock_seq")
        if seq is None:
            raise ShipError(MSG_SCHEMA_PRECONDITION, code="SCHEMA_PRECONDITION")
        has_dlvry = _column_exists(cur, "t_sales_detail", "dlvry_tp")
        has_ship_fee = _column_exists(cur, "t_sales_detail", "ship_fee")
        if has_dlvry and has_ship_fee:
            cur.execute(
                """
                INSERT INTO t_sales_detail (
                    sale_detail_no, sales_no, farm_cd, item_cd, variety_cd,
                    grade_cd, size_cd, qty, unit_price, tot_item_amt,
                    ship_fee, tot_sale_amt, order_detail_id, wh_cd, stock_seq,
                    dlvry_tp, reg_id, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    det_no, sales_no, farm, split["item_cd"], split["variety_cd"],
                    split["grade_cd"], split["size_cd"], qty, price, amt,
                    float(ship_fee or 0), amt + float(ship_fee or 0),
                    split.get("order_detail_id"), split["wh_cd"], int(seq),
                    str(dlvry_tp or "") or None,
                    user_id, now_dt,
                ),
            )
            return
        cur.execute(
            """
            INSERT INTO t_sales_detail (
                sale_detail_no, sales_no, farm_cd, item_cd, variety_cd,
                grade_cd, size_cd, qty, unit_price, tot_item_amt,
                tot_sale_amt, order_detail_id, wh_cd, stock_seq, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                det_no, sales_no, farm, split["item_cd"], split["variety_cd"],
                split["grade_cd"], split["size_cd"], qty, price, amt, amt,
                split.get("order_detail_id"), split["wh_cd"], int(seq),
                user_id, now_dt,
            ),
        )

    def _insert_sales_delivery(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        sales_no: str,
        det_no: str,
        qty: float,
        payload: ShipConfirmIn,
        user_id: str,
    ) -> None:
        if not _table_exists(cur, "t_sales_delivery"):
            return
        rcv_name = str(getattr(payload, "rcv_name", "") or "").strip()
        rcv_tel = str(getattr(payload, "rcv_tel", "") or "").strip()
        rcv_addr = str(getattr(payload, "rcv_addr", "") or "").strip()
        dlvry_msg = str(getattr(payload, "dlvry_msg", "") or "").strip()
        if not (rcv_name or rcv_tel or rcv_addr or dlvry_msg):
            return
        dlvry_no = f"{det_no}-D001"
        cur.execute(
            """
            INSERT INTO t_sales_delivery (
                dlvry_no, sale_detail_no, sales_no, farm_cd,
                rcv_name, rcv_tel, rcv_addr, dlvry_qty, dlvry_msg, reg_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dlvry_no, det_no, sales_no, farm,
                rcv_name or None, rcv_tel or None, rcv_addr or None,
                qty, dlvry_msg or None, user_id,
            ),
        )

    def _insert_stock_log(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        det_no: str,
        split: dict[str, Any],
        user_id: str,
        now_dt: str,
    ) -> None:
        cur.execute(
            """
            INSERT INTO t_stock_log (
                farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
                weight, io_type, qty, remark, reg_id, reg_dt,
                stock_seq, ref_type, ref_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                farm, split["item_cd"], split["variety_cd"], split["harvest_year"],
                split["grade_cd"], split["size_cd"], split["weight"],
                IO_TYPE_OUT, split["qty"], MSG_REMARK_SALE_OUT, user_id, now_dt,
                int(split["stock_seq"]), REF_TYPE_SALE, det_no,
            ),
        )

    def _update_order_status(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        order_no: str,
        user_id: str,
        now_dt: str,
    ) -> tuple[str, str | None, list[dict[str, Any]]]:
        cur.execute(
            """
            SELECT order_detail_id, qty
            FROM t_order_detail
            WHERE farm_cd = ? AND order_no = ?
            ORDER BY order_detail_id
            """,
            (farm, order_no),
        )
        remaining: list[dict[str, Any]] = []
        all_done = True
        any_shipped = False
        for row in cur.fetchall():
            det_id = str(_row_val(row, "order_detail_id", 0) or "")
            order_qty = _as_float(_row_val(row, "qty", 1))
            shipped = self._confirmed_shipped(cur, farm, det_id)
            shipped_qty, left = order_line_ship_remainder(order_qty, shipped)
            remaining.append(
                {
                    "order_detail_id": det_id,
                    "order_qty": order_qty,
                    "confirmed_shipped_qty": shipped_qty,
                    "remaining_order_qty": left,
                }
            )
            if shipped > _QTY_EPS:
                any_shipped = True
            if not _qty_eq(shipped, order_qty):
                all_done = False
        if all_done and any_shipped:
            status = ORDER_STATUS_DELIVERED_CD
            stock_status = STOCK_STATUS_DONE
        elif any_shipped:
            status = ORDER_STATUS_PREP_CD
            stock_status = None
        else:
            return "", None, remaining
        if stock_status:
            cur.execute(
                """
                UPDATE t_order_master
                SET status_cd = ?, stock_status = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND order_no = ?
                """,
                (status, stock_status, user_id, now_dt, farm, order_no),
            )
        else:
            cur.execute(
                """
                UPDATE t_order_master
                SET status_cd = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND order_no = ?
                """,
                (status, user_id, now_dt, farm, order_no),
            )
        if cur.rowcount != 1:
            raise ShipConflictError(MSG_DATA_INTEGRITY, code="DATA_INTEGRITY")
        return status, stock_status, remaining

    def _touch_order_sales_no(
        self,
        cur: sqlite3.Cursor,
        farm: str,
        order_no: str,
        sales_no: str,
        user_id: str,
        now_dt: str,
    ) -> None:
        cur.execute(
            """
            UPDATE t_order_master
            SET sales_no = CASE
                    WHEN COALESCE(sales_no, '') = '' THEN ?
                    ELSE sales_no
                END,
                mod_id = ?, mod_dt = ?
            WHERE farm_cd = ? AND order_no = ?
            """,
            (sales_no, user_id, now_dt, farm, order_no),
        )
