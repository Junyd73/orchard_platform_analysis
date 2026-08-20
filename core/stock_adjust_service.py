# -*- coding: utf-8 -*-
"""재고 증감(실사·폐기). 판매 전표 없음. available = in-out-reserved."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from core.ops_biz_date import now_ops_str
from core.stock_adjust_constants import (
    ADJUST_IO_TYPES,
    ADJUST_REASON_ROWS,
    IO_TYPE_IN,
    IO_TYPE_OUT,
    LABEL_ADJUST_GROUP,
    MSG_ADJUST_DIR,
    MSG_ADJUST_IO,
    MSG_ADJUST_NO_AVAIL,
    MSG_ADJUST_NOT_FOUND,
    MSG_ADJUST_QTY,
    MSG_ADJUST_REASON,
    MSG_REMARK_PREFIX,
    PARENT_ADJUST_MAJOR,
    PARENT_ADJUST_REASON,
    REF_TYPE_ADJUST,
    reason_allows_io,
)


class StockAdjustError(Exception):
    def __init__(self, message: str, *, code: str = "STOCK_ADJUST"):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class StockAdjustIn:
    farm_cd: str
    wh_cd: str
    item_cd: str
    variety_cd: str
    grade_cd: str
    size_cd: str
    weight: float
    harvest_year: int
    storage_dt: str
    io_type: str
    qty: float
    reason_cd: str
    # PC(실사) 등에서 사용자 메모를 remark에 보존하기 위한 optional 필드.
    # DB 컬럼 추가 없이 t_stock_log.remark 텍스트로만 반영합니다.
    memo: str = ""


@dataclass
class StockAdjustBySpecIn:
    """판매규격(storage_dt 제외) 단위 조정. 단일-row adjust() 계약을 바꾸지 않음."""

    farm_cd: str
    wh_cd: str
    item_cd: str
    variety_cd: str
    grade_cd: str
    size_cd: str
    weight: float
    harvest_year: int
    io_type: str
    qty: float
    reason_cd: str
    memo: str = ""


def ensure_adjust_reason_codes(conn: sqlite3.Connection, farm_cd: str) -> None:
    farm = str(farm_cd or "").strip()
    if not farm:
        return
    conn.execute(
        """
        INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn)
        SELECT ?, ?, ?, ?, 'Y'
        WHERE NOT EXISTS (
            SELECT 1 FROM m_common_code WHERE farm_cd = ? AND code_cd = ?
        )
        """,
        (
            farm,
            PARENT_ADJUST_REASON,
            LABEL_ADJUST_GROUP,
            PARENT_ADJUST_MAJOR,
            farm,
            PARENT_ADJUST_REASON,
        ),
    )
    for code_cd, code_nm in ADJUST_REASON_ROWS:
        conn.execute(
            """
            INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn)
            SELECT ?, ?, ?, ?, 'Y'
            WHERE NOT EXISTS (
                SELECT 1 FROM m_common_code WHERE farm_cd = ? AND code_cd = ?
            )
            """,
            (farm, code_cd, code_nm, PARENT_ADJUST_REASON, farm, code_cd),
        )


def _row_avail(row: sqlite3.Row) -> float:
    return float(row["in_qty"] or 0) - float(row["out_qty"] or 0) - float(row["reserved_qty"] or 0)


class StockAdjustService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        if self.conn.row_factory is None:
            self.conn.row_factory = sqlite3.Row

    def adjust(self, payload: StockAdjustIn, *, user_id: str) -> dict:
        farm = str(payload.farm_cd or "").strip()
        io_type = str(payload.io_type or "").strip().upper()
        qty = float(payload.qty or 0)
        reason_cd = str(payload.reason_cd or "").strip()
        self._validate_common(qty, io_type, reason_cd)
        now_dt = now_ops_str()
        uid = str(user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            ensure_adjust_reason_codes(cur, farm)
            reason_nm = self._reason_nm(cur, farm, reason_cd)
            if not reason_nm:
                raise StockAdjustError(MSG_ADJUST_REASON, code="ADJUST_REASON")
            if not reason_allows_io(reason_cd, io_type):
                raise StockAdjustError(MSG_ADJUST_DIR, code="ADJUST_DIR")
            row = self._load_stock(cur, payload)
            if row is None:
                raise StockAdjustError(MSG_ADJUST_NOT_FOUND, code="STOCK_NOT_FOUND")
            avail = _row_avail(row)
            seq = int(row["stock_seq"])
            if io_type == IO_TYPE_OUT and qty > avail + 1e-9:
                raise StockAdjustError(MSG_ADJUST_NO_AVAIL, code="STOCK_UNAVAILABLE")
            self._apply_delta(
                cur,
                farm=farm,
                payload=payload,
                seq=seq,
                io_type=io_type,
                qty=qty,
                reason_cd=reason_cd,
                reason_nm=reason_nm,
                now_dt=now_dt,
                uid=uid,
            )
            self.conn.commit()
            return {"ok": True, "stock_seq": seq, "io_type": io_type, "qty": qty, "reason_cd": reason_cd}
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def adjust_by_sale_spec(self, payload: StockAdjustBySpecIn, *, user_id: str) -> dict:
        """동일 판매규격(storage_dt 제외) source들을 한 TX에서 조정.

        OUT: storage_dt ASC, stock_seq ASC (DIRECT FIFO와 동일)로 available 분할.
        IN: 신규 storage_dt/LOT 생성 없이, 기존 source 중 최신(storage_dt DESC, stock_seq DESC)
            1건에만 증가. (확정 포장일 정책 없음 — 최소 안전대안)
        """
        farm = str(payload.farm_cd or "").strip()
        io_type = str(payload.io_type or "").strip().upper()
        qty = float(payload.qty or 0)
        reason_cd = str(payload.reason_cd or "").strip()
        self._validate_common(qty, io_type, reason_cd)
        now_dt = now_ops_str()
        uid = str(user_id or "").strip() or "SYSTEM"
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            ensure_adjust_reason_codes(cur, farm)
            reason_nm = self._reason_nm(cur, farm, reason_cd)
            if not reason_nm:
                raise StockAdjustError(MSG_ADJUST_REASON, code="ADJUST_REASON")
            if not reason_allows_io(reason_cd, io_type):
                raise StockAdjustError(MSG_ADJUST_DIR, code="ADJUST_DIR")
            rows = self._load_stocks_by_spec(cur, payload)
            if not rows:
                raise StockAdjustError(MSG_ADJUST_NOT_FOUND, code="STOCK_NOT_FOUND")

            if io_type == IO_TYPE_OUT:
                total_avail = sum(_row_avail(r) for r in rows)
                if qty > total_avail + 1e-9:
                    raise StockAdjustError(MSG_ADJUST_NO_AVAIL, code="STOCK_UNAVAILABLE")
                remaining = qty
                primary_seq: int | None = None
                for row in rows:
                    if remaining <= 1e-9:
                        break
                    avail = _row_avail(row)
                    if avail <= 1e-9:
                        continue
                    take = min(remaining, avail)
                    seq = int(row["stock_seq"])
                    if primary_seq is None:
                        primary_seq = seq
                    self._apply_delta(
                        cur,
                        farm=farm,
                        payload=payload,
                        seq=seq,
                        io_type=io_type,
                        qty=take,
                        reason_cd=reason_cd,
                        reason_nm=reason_nm,
                        now_dt=now_dt,
                        uid=uid,
                    )
                    remaining -= take
                if remaining > 1e-9 or primary_seq is None:
                    raise StockAdjustError(MSG_ADJUST_NO_AVAIL, code="STOCK_UNAVAILABLE")
                self.conn.commit()
                return {
                    "ok": True,
                    "stock_seq": primary_seq,
                    "io_type": io_type,
                    "qty": qty,
                    "reason_cd": reason_cd,
                }

            # IN — 기존 최신 source 1건만 (신규 포장일 생성 금지)
            target = max(
                rows,
                key=lambda r: (str(r["storage_dt"] or ""), int(r["stock_seq"])),
            )
            seq = int(target["stock_seq"])
            self._apply_delta(
                cur,
                farm=farm,
                payload=payload,
                seq=seq,
                io_type=io_type,
                qty=qty,
                reason_cd=reason_cd,
                reason_nm=reason_nm,
                now_dt=now_dt,
                uid=uid,
            )
            self.conn.commit()
            return {"ok": True, "stock_seq": seq, "io_type": io_type, "qty": qty, "reason_cd": reason_cd}
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    @staticmethod
    def _validate_common(qty: float, io_type: str, reason_cd: str) -> None:
        if qty <= 1e-9:
            raise StockAdjustError(MSG_ADJUST_QTY, code="ADJUST_QTY")
        if io_type not in ADJUST_IO_TYPES:
            raise StockAdjustError(MSG_ADJUST_IO, code="ADJUST_IO")
        if not reason_cd:
            raise StockAdjustError(MSG_ADJUST_REASON, code="ADJUST_REASON")

    def _apply_delta(
        self,
        cur: sqlite3.Cursor,
        *,
        farm: str,
        payload: StockAdjustIn | StockAdjustBySpecIn,
        seq: int,
        io_type: str,
        qty: float,
        reason_cd: str,
        reason_nm: str,
        now_dt: str,
        uid: str,
    ) -> None:
        if io_type == IO_TYPE_IN:
            cur.execute(
                "UPDATE t_stock_master SET in_qty = in_qty + ?, mod_dt=?, mod_id=? WHERE stock_seq=?",
                (qty, now_dt, uid, seq),
            )
        else:
            cur.execute(
                "UPDATE t_stock_master SET out_qty = out_qty + ?, mod_dt=?, mod_id=? WHERE stock_seq=?",
                (qty, now_dt, uid, seq),
            )
        remark = f"{MSG_REMARK_PREFIX} {reason_nm}"
        memo = str(getattr(payload, "memo", "") or "").strip()
        if memo:
            remark = f"{remark} · {memo}"
        cur.execute(
            """
            INSERT INTO t_stock_log (
                farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd,
                weight, io_type, qty, remark, reg_id, reg_dt,
                stock_seq, ref_type, ref_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                farm,
                payload.item_cd,
                payload.variety_cd,
                int(payload.harvest_year),
                payload.grade_cd,
                payload.size_cd,
                float(payload.weight),
                io_type,
                qty,
                remark,
                uid,
                now_dt,
                seq,
                REF_TYPE_ADJUST,
                reason_cd,
            ),
        )

    def _reason_nm(self, cur: sqlite3.Cursor, farm: str, reason_cd: str) -> str:
        row = cur.execute(
            """
            SELECT code_nm FROM m_common_code
            WHERE farm_cd=? AND code_cd=? AND parent_cd=?
            LIMIT 1
            """,
            (farm, reason_cd, PARENT_ADJUST_REASON),
        ).fetchone()
        if not row:
            return ""
        return str(row[0] if not isinstance(row, sqlite3.Row) else row["code_nm"] or "")

    def _load_stock(self, cur: sqlite3.Cursor, payload: StockAdjustIn) -> sqlite3.Row | None:
        cur.execute(
            """
            SELECT stock_seq, in_qty, out_qty, reserved_qty, storage_dt
            FROM t_stock_master
            WHERE farm_cd=? AND wh_cd=? AND item_cd=? AND variety_cd=?
              AND grade_cd=? AND size_cd=? AND ABS(weight-?)<1e-9
              AND harvest_year=? AND storage_dt=?
            LIMIT 1
            """,
            (
                payload.farm_cd,
                payload.wh_cd,
                payload.item_cd,
                payload.variety_cd,
                payload.grade_cd,
                payload.size_cd,
                float(payload.weight),
                int(payload.harvest_year),
                str(payload.storage_dt)[:10],
            ),
        )
        return cur.fetchone()

    def _load_stocks_by_spec(
        self, cur: sqlite3.Cursor, payload: StockAdjustBySpecIn,
    ) -> list[sqlite3.Row]:
        cur.execute(
            """
            SELECT stock_seq, in_qty, out_qty, reserved_qty, storage_dt
            FROM t_stock_master
            WHERE farm_cd=? AND wh_cd=? AND item_cd=? AND variety_cd=?
              AND grade_cd=? AND size_cd=? AND ABS(weight-?)<1e-9
              AND harvest_year=?
            ORDER BY storage_dt ASC, stock_seq ASC
            """,
            (
                payload.farm_cd,
                payload.wh_cd,
                payload.item_cd,
                payload.variety_cd,
                payload.grade_cd,
                payload.size_cd,
                float(payload.weight),
                int(payload.harvest_year),
            ),
        )
        return list(cur.fetchall())
