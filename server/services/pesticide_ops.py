# -*- coding: utf-8 -*-
"""농약 확장 연산 — 통계·사전·입고·재고 CRUD (PesticideManager 위임)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.schemas.pesticide_ext import (
    PesticideInfoDetailDto,
    PesticideInfoListResponse,
    PesticideInfoSummaryDto,
    PesticideItemUpdateRequest,
    PesticideMessageResponse,
    PesticideReceiptApplyResponse,
    PesticideReceiptDetailDto,
    PesticideReceiptLineDto,
    PesticideReceiptListResponse,
    PesticideReceiptSaveRequest,
    PesticideReceiptSaveResponse,
    PesticideReceiptSummaryDto,
    PesticideStockHistListResponse,
    PesticideStockHistRowDto,
    PesticideStockOutRequest,
    PesticideStockOutResponse,
    PesticideSupplierDto,
    PesticideSupplierListResponse,
    PesticideYearlyStatsItemDto,
    PesticideYearlyStatsResponse,
)
from app.services._core_path import ensure_repo_root_on_path
from app.services.observation_ai_db_bridge import ServerDbBridge


def _s(v: Any) -> str:
    return str(v or "").strip()


def _uid(user_id: str | None) -> str:
    return _s(user_id) or "MOBILE"


def _fill_stock_hist_qty_after(
    rows: list[PesticideStockHistRowDto],
    current_qty: int,
) -> list[PesticideStockHistRowDto]:
    """최신→과거로 순회하며 qty_after 누락행(입고 가상행 등)에 잔량을 채운다.

    미반영 입고(rmk에 '미반영')는 재고에 미포함이므로 잔량만 표시하고
    역추적 running에는 반영하지 않는다.
    """
    running = int(current_qty)
    filled: list[PesticideStockHistRowDto] = []
    for row in rows:
        pending = "미반영" in _s(row.rmk)
        if pending:
            # 아직 재고 미반영 — 현재고를 참고 잔량으로 표시
            filled.append(row.model_copy(update={"qty_after": running}))
            continue
        if row.qty_after is not None:
            after = int(row.qty_after)
            filled.append(row)
            running = after - int(row.qty_delta or 0)
            continue
        after = running
        filled.append(row.model_copy(update={"qty_after": after}))
        running = after - int(row.qty_delta or 0)
    return filled


class PesticideOpsMixin:
    """PesticideService에 mix-in. self._db_path / self._ensure_farm 사용."""

    def _mgr(self, conn):
        ensure_repo_root_on_path()
        from core.pesticide_manager import PesticideManager  # noqa: WPS433

        return PesticideManager(ServerDbBridge(conn))

    def get_yearly_stats(self, farm_cd: str, year: int) -> PesticideYearlyStatsResponse:
        farm = self._ensure_farm(farm_cd)
        y = int(year)
        if y < 2000 or y > 2100:
            raise BusinessRuleError("연도 형식이 올바르지 않습니다.")
        with get_sqlite_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            matrix = mgr.get_yearly_usage_matrix(y, farm)
            monthly = mgr.get_monthly_usage_count(y, farm)
        spray_total = sum(int(v or 0) for v in monthly.values())
        items: list[PesticideYearlyStatsItemDto] = []
        for iid, row in matrix.items():
            if int(row.get("total_qty") or 0) <= 0 and not row.get("daily"):
                continue
            daily_raw = row.get("daily") or {}
            daily = {str(k): int(v or 0) for k, v in daily_raw.items() if int(v or 0)}
            items.append(
                PesticideYearlyStatsItemDto(
                    item_id=int(iid),
                    item_nm=_s(row.get("item_nm")) or f"품목{iid}",
                    spec_nm=_s(row.get("spec_nm")) or None,
                    pest_category_nm=_s(row.get("pest_category_nm")) or None,
                    total_qty=int(row.get("total_qty") or 0),
                    current_stock=int(row.get("current_stock") or 0),
                    daily=daily,
                )
            )
        items.sort(key=lambda x: (-x.total_qty, x.item_nm))
        return PesticideYearlyStatsResponse(
            year=y,
            spray_count_total=spray_total,
            monthly_spray_counts={str(m): int(monthly.get(m) or 0) for m in range(1, 13)},
            items=items,
        )

    def list_info(
        self,
        farm_cd: str,
        *,
        keyword: str = "",
        limit: int = 100,
    ) -> PesticideInfoListResponse:
        farm = self._ensure_farm(farm_cd)
        lim = max(1, min(int(limit), 300))
        with get_sqlite_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            rows = mgr.get_pesticide_info_summary_list(farm, nm_sub=keyword)
        out: list[PesticideInfoSummaryDto] = []
        for r in rows[:lim]:
            out.append(
                PesticideInfoSummaryDto(
                    info_id=int(r["info_id"]),
                    pesticide_nm=_s(r.get("pesticide_nm")) or f"정보{r['info_id']}",
                    maker_nm=_s(r.get("maker_nm")) or None,
                    ingredient_nm=_s(r.get("ingredient_nm")) or None,
                    category_nm=_s(r.get("category_nm")) or None,
                    brand_nm=_s(r.get("brand_nm")) or None,
                    stock_qty=int(r.get("stock_qty") or 0),
                )
            )
        return PesticideInfoListResponse(items=out)

    def get_info_detail(
        self,
        farm_cd: str,
        info_id: int,
        *,
        year: int | None = None,
    ) -> PesticideInfoDetailDto:
        farm = self._ensure_farm(farm_cd)
        y = int(year) if year else date.today().year
        with get_sqlite_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            row = mgr.get_pesticide_info_detail(int(info_id), farm, y)
            if not row:
                raise EntityNotFoundError("Pesticide info not found")
            sibling_ids = mgr.list_pesticide_info_sibling_ids(int(info_id))
            id_ph = ",".join("?" * len(sibling_ids))
            pest_row = conn.execute(
                f"""
                SELECT GROUP_CONCAT(pest_nm, ', ') AS pest_target_nm
                FROM (
                  SELECT DISTINCT TRIM(pest_nm) AS pest_nm
                  FROM m_pesticide_pest_map
                  WHERE info_id IN ({id_ph})
                    AND IFNULL(use_yn, 'Y') = 'Y'
                    AND TRIM(IFNULL(pest_nm, '')) != ''
                  ORDER BY 1
                )
                """,
                tuple(sibling_ids),
            ).fetchone()
        pest_nm = _s(dict(pest_row).get("pest_target_nm")) if pest_row else ""
        return PesticideInfoDetailDto(
            info_id=int(row["info_id"]),
            pesticide_nm=_s(row.get("pesticide_nm")) or f"정보{info_id}",
            maker_nm=_s(row.get("maker_nm")) or None,
            ingredient_nm=_s(row.get("ingredient_nm")) or None,
            category_nm=_s(row.get("category_nm")) or None,
            brand_nm=_s(row.get("brand_nm")) or None,
            spec_nm=_s(row.get("spec_nm")) or None,
            dilution_guide=_s(row.get("dilution_guide")) or None,
            usage_note=_s(row.get("usage_note")) or None,
            caution_note=_s(row.get("caution_note")) or None,
            rmk=_s(row.get("rmk")) or None,
            stock_qty=int(row.get("stock_qty") or 0),
            last_use_dt=_s(row.get("last_use_dt")) or None,
            annual_use_qty=int(row.get("annual_use_qty") or 0),
            annual_use_cnt=int(row.get("annual_use_cnt") or 0),
            pest_target_nm=pest_nm or None,
        )

    def list_suppliers(self, farm_cd: str) -> PesticideSupplierListResponse:
        farm = self._ensure_farm(farm_cd)
        with get_sqlite_connection(self._db_path) as conn:
            rows = self._mgr(conn).list_suppliers(farm)
        return PesticideSupplierListResponse(
            items=[
                PesticideSupplierDto(
                    supplier_id=int(r["supplier_id"]),
                    supplier_nm=_s(r.get("supplier_nm")) or "",
                    biz_reg_no=_s(r.get("biz_reg_no")) or None,
                    ceo_nm=_s(r.get("ceo_nm")) or None,
                    addr=_s(r.get("addr")) or None,
                )
                for r in rows
            ]
        )

    def list_receipts(self, farm_cd: str, limit: int = 100) -> PesticideReceiptListResponse:
        farm = self._ensure_farm(farm_cd)
        lim = max(1, min(int(limit), 300))
        with get_sqlite_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            heads = mgr.list_receipts(farm, limit=lim)
            items: list[PesticideReceiptSummaryDto] = []
            for h in heads:
                rid = int(h["receipt_id"])
                lines = mgr.list_receipt_lines(rid)
                supplier_nm = _s(h.get("supplier_nm_joined")) or _s(
                    h.get("supplier_nm_text")
                )
                items.append(
                    PesticideReceiptSummaryDto(
                        receipt_id=rid,
                        receipt_dt=_s(h.get("receipt_dt"))[:10],
                        supplier_id=int(h["supplier_id"])
                        if h.get("supplier_id") is not None
                        else None,
                        supplier_nm=supplier_nm or None,
                        recipient_nm=_s(h.get("recipient_nm")) or None,
                        rmk=_s(h.get("rmk")) or None,
                        stock_applied_yn=_s(h.get("stock_applied_yn")) or "N",
                        line_count=len(lines),
                        total_qty=sum(int(ln.get("qty") or 0) for ln in lines),
                    )
                )
        return PesticideReceiptListResponse(items=items)

    def get_receipt_detail(
        self, farm_cd: str, receipt_id: int
    ) -> PesticideReceiptDetailDto:
        farm = self._ensure_farm(farm_cd)
        with get_sqlite_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            head = mgr.get_receipt(farm, int(receipt_id))
            if not head:
                raise EntityNotFoundError("Receipt not found")
            lines = mgr.list_receipt_lines(int(receipt_id))
        return PesticideReceiptDetailDto(
            receipt_id=int(head["receipt_id"]),
            receipt_dt=_s(head.get("receipt_dt"))[:10],
            supplier_id=int(head["supplier_id"])
            if head.get("supplier_id") is not None
            else None,
            supplier_nm_text=_s(head.get("supplier_nm_text")) or None,
            recipient_nm=_s(head.get("recipient_nm")) or None,
            rmk=_s(head.get("rmk")) or None,
            stock_applied_yn=_s(head.get("stock_applied_yn")) or "N",
            stock_applied_dt=_s(head.get("stock_applied_dt")) or None,
            lines=[
                PesticideReceiptLineDto(
                    line_id=int(ln["line_id"]) if ln.get("line_id") is not None else None,
                    line_no=int(ln.get("line_no") or i),
                    link_item_id=int(ln["link_item_id"])
                    if ln.get("link_item_id") is not None
                    else None,
                    info_id=int(ln["info_id"])
                    if ln.get("info_id") is not None
                    else None,
                    item_nm=_s(ln.get("item_nm")) or "",
                    spec_nm=_s(ln.get("spec_nm")) or None,
                    qty=int(ln.get("qty") or 0),
                    unit_price=float(ln["unit_price"])
                    if ln.get("unit_price") is not None
                    else None,
                    supply_amt=float(ln["supply_amt"])
                    if ln.get("supply_amt") is not None
                    else None,
                    tax_amt=float(ln["tax_amt"]) if ln.get("tax_amt") is not None else None,
                    line_rmk=_s(ln.get("line_rmk")) or None,
                )
                for i, ln in enumerate(lines, start=1)
            ],
        )

    def save_receipt(
        self,
        farm_cd: str,
        body: PesticideReceiptSaveRequest,
        *,
        receipt_id: int | None = None,
        user_id: str | None = None,
    ) -> PesticideReceiptSaveResponse:
        """입고 저장 후 즉시 재고 반영(이미 반영분이면 역분개 후 재반영)."""
        farm = self._ensure_farm(farm_cd)
        dt = _s(body.receipt_dt)[:10]
        if len(dt) != 10:
            raise BusinessRuleError("입고일(YYYY-MM-DD)이 필요합니다.")
        if not body.lines:
            raise BusinessRuleError("입고 라인이 필요합니다.")
        line_dicts = [
            {
                "link_item_id": ln.link_item_id,
                "info_id": ln.info_id,
                "item_nm": ln.item_nm,
                "spec_nm": ln.spec_nm or "",
                "qty": ln.qty,
                "unit_price": ln.unit_price,
                "supply_amt": ln.supply_amt,
                "tax_amt": ln.tax_amt,
                "line_rmk": ln.line_rmk or "",
                "checked_yn": "N",
            }
            for ln in body.lines
            if _s(ln.item_nm)
        ]
        if not line_dicts:
            raise BusinessRuleError("유효한 입고 라인이 없습니다.")
        uid = _uid(user_id)
        from core.pesticide_receipt_schema import ensure_pesticide_receipt_schema

        ensure_pesticide_receipt_schema(self._db_path)
        with get_sqlite_write_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            if receipt_id is not None:
                head = mgr.get_receipt(farm, int(receipt_id))
                if not head:
                    raise EntityNotFoundError("Receipt not found")
            rid = mgr.save_receipt_full(
                farm,
                uid,
                int(receipt_id) if receipt_id is not None else None,
                dt,
                body.supplier_id,
                body.supplier_nm_text or "",
                body.recipient_nm or "",
                body.rmk or "",
                line_dicts,
            )
            if not rid:
                raise BusinessRuleError("입고 저장에 실패했습니다.")
            applied, _created, notes = mgr.apply_receipt_to_stock(
                farm, uid, int(rid)
            )
        msg = "저장하고 재고에 반영했습니다."
        if applied <= 0 and notes:
            msg = f"저장되었습니다. 재고 반영: {notes[0]}"
        elif notes:
            msg = f"{msg} ({notes[0]})"
        return PesticideReceiptSaveResponse(receipt_id=int(rid), message=msg)

    def apply_receipt(
        self,
        farm_cd: str,
        receipt_id: int,
        *,
        user_id: str | None = None,
    ) -> PesticideReceiptApplyResponse:
        farm = self._ensure_farm(farm_cd)
        uid = _uid(user_id)
        with get_sqlite_write_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            applied, created, notes = mgr.apply_receipt_to_stock(
                farm, uid, int(receipt_id)
            )
        return PesticideReceiptApplyResponse(
            applied_count=int(applied),
            created_names=list(created or []),
            notes=list(notes or []),
            message=f"재고 반영 {applied}건",
        )

    def delete_receipt(
        self,
        farm_cd: str,
        receipt_id: int,
        *,
        user_id: str | None = None,
    ) -> PesticideMessageResponse:
        farm = self._ensure_farm(farm_cd)
        uid = _uid(user_id)
        with get_sqlite_write_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            head = mgr.get_receipt(farm, int(receipt_id))
            if not head:
                raise EntityNotFoundError("Receipt not found")
            ok = mgr.delete_receipt(farm, int(receipt_id), user_id=uid)
        if not ok:
            raise BusinessRuleError("입고 삭제에 실패했습니다.")
        return PesticideMessageResponse(message="삭제되었습니다.")

    def update_item(
        self,
        farm_cd: str,
        item_id: int,
        body: PesticideItemUpdateRequest,
        *,
        user_id: str | None = None,
    ) -> PesticideMessageResponse:
        farm = self._ensure_farm(farm_cd)
        uid = _uid(user_id)
        nm = _s(body.item_nm)
        if not nm:
            raise BusinessRuleError("품목명이 필요합니다.")
        with get_sqlite_write_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            exists = conn.execute(
                """
                SELECT 1 FROM m_pesticide_item
                WHERE farm_cd = ? AND item_id = ? AND IFNULL(use_yn, 'Y') = 'Y'
                LIMIT 1
                """,
                (farm, int(item_id)),
            ).fetchone()
            if not exists:
                raise EntityNotFoundError("Pesticide item not found")
            ok = mgr.update_item_full(
                farm,
                uid,
                int(item_id),
                nm,
                body.spec_nm or "",
                body.pest_category_nm or "",
                0,
                int(body.qty_piece or 0),
                None,
                body.warn_piece_below,
                body.rmk or "",
                body.info_id,
            )
        if not ok:
            raise BusinessRuleError("품목 수정에 실패했습니다.")
        return PesticideMessageResponse(message="저장되었습니다.")

    def issue_stock_out(
        self,
        farm_cd: str,
        item_id: int,
        body: PesticideStockOutRequest,
        *,
        user_id: str | None = None,
    ) -> PesticideStockOutResponse:
        farm = self._ensure_farm(farm_cd)
        uid = _uid(user_id)
        with get_sqlite_write_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            ok, msg, qty_after = mgr.issue_stock_out(
                farm,
                uid,
                int(item_id),
                int(body.qty),
                body.buyer_nm or "",
                body.rmk or "",
            )
        if not ok:
            if "찾을 수 없습니다" in (msg or ""):
                raise EntityNotFoundError("Pesticide item not found")
            raise BusinessRuleError(msg or "출고에 실패했습니다.")
        return PesticideStockOutResponse(
            item_id=int(item_id),
            qty=int(body.qty),
            qty_after=int(qty_after or 0),
            message=msg or "출고되었습니다.",
        )

    def delete_item(
        self,
        farm_cd: str,
        item_id: int,
        *,
        user_id: str | None = None,
    ) -> PesticideMessageResponse:
        farm = self._ensure_farm(farm_cd)
        uid = _uid(user_id)
        with get_sqlite_write_connection(self._db_path) as conn:
            mgr = self._mgr(conn)
            ok = mgr.soft_delete_item(farm, uid, int(item_id))
        if not ok:
            raise EntityNotFoundError("Pesticide item not found")
        return PesticideMessageResponse(message="삭제되었습니다.")

    def list_stock_hist(
        self,
        farm_cd: str,
        item_id: int,
        *,
        limit: int = 100,
    ) -> PesticideStockHistListResponse:
        farm = self._ensure_farm(farm_cd)
        lim = max(1, min(int(limit), 300))
        iid = int(item_id)
        with get_sqlite_connection(self._db_path) as conn:
            item = conn.execute(
                """
                SELECT item_nm, IFNULL(qty_piece, 0) AS qty_piece
                FROM m_pesticide_item
                WHERE farm_cd = ? AND item_id = ? AND IFNULL(use_yn, 'Y') = 'Y'
                LIMIT 1
                """,
                (farm, iid),
            ).fetchone()
            if not item:
                raise EntityNotFoundError("Pesticide item not found")
            current_qty = int(dict(item).get("qty_piece") or 0)
            try:
                rows = conn.execute(
                    """
                    SELECT
                        h.hist_id,
                        h.trans_type,
                        h.ref_table,
                        h.ref_id,
                        h.qty_delta,
                        h.qty_after,
                        h.trans_dt,
                        h.rmk,
                        CASE
                          WHEN h.ref_table = 't_pesticide_receipt'
                          THEN substr(IFNULL(r.receipt_dt, ''), 1, 10)
                          ELSE NULL
                        END AS receipt_dt,
                        CASE
                          WHEN h.ref_table = 't_pesticide_receipt'
                          THEN COALESCE(
                            NULLIF(TRIM(IFNULL(s.supplier_nm, '')), ''),
                            NULLIF(TRIM(IFNULL(r.supplier_nm_text, '')), '')
                          )
                          ELSE NULL
                        END AS supplier_nm
                    FROM t_pesticide_stock_hist h
                    LEFT JOIN t_pesticide_receipt r
                      ON h.ref_table = 't_pesticide_receipt'
                     AND h.ref_id = r.receipt_id
                     AND r.farm_cd = h.farm_cd
                    LEFT JOIN m_pesticide_supplier s
                      ON r.supplier_id = s.supplier_id
                    WHERE h.farm_cd = ? AND h.item_id = ?
                    ORDER BY datetime(h.trans_dt) DESC, h.hist_id DESC
                    LIMIT ?
                    """,
                    (farm, iid, lim),
                ).fetchall()
            except Exception:
                # 입고 조인 실패(구 DB 등) 시 기본 이력만
                try:
                    rows = conn.execute(
                        """
                        SELECT hist_id, trans_type, ref_table, ref_id, qty_delta,
                               qty_after, trans_dt, rmk,
                               NULL AS receipt_dt, NULL AS supplier_nm
                        FROM t_pesticide_stock_hist
                        WHERE farm_cd = ? AND item_id = ?
                        ORDER BY datetime(trans_dt) DESC, hist_id DESC
                        LIMIT ?
                        """,
                        (farm, iid, lim),
                    ).fetchall()
                except Exception:
                    rows = []

            # 재고이력에 없는 입고 명세(연결 품목)도 함께 표시
            receipt_extra: list[dict[str, Any]] = []
            try:
                seen_receipt_ids = {
                    int(dict(r)["ref_id"])
                    for r in (rows or [])
                    if _s(dict(r).get("ref_table")) == "t_pesticide_receipt"
                    and dict(r).get("ref_id") is not None
                }
                rcpt_rows = conn.execute(
                    """
                    SELECT
                        r.receipt_id,
                        substr(IFNULL(r.receipt_dt, ''), 1, 10) AS receipt_dt,
                        l.qty AS qty_delta,
                        r.stock_applied_yn,
                        COALESCE(
                          NULLIF(TRIM(IFNULL(s.supplier_nm, '')), ''),
                          NULLIF(TRIM(IFNULL(r.supplier_nm_text, '')), '')
                        ) AS supplier_nm,
                        IFNULL(r.stock_applied_dt, r.receipt_dt) AS trans_dt
                    FROM t_pesticide_receipt_line l
                    INNER JOIN t_pesticide_receipt r ON r.receipt_id = l.receipt_id
                    LEFT JOIN m_pesticide_supplier s ON r.supplier_id = s.supplier_id
                    WHERE r.farm_cd = ?
                      AND l.link_item_id = ?
                      AND IFNULL(l.qty, 0) > 0
                    ORDER BY datetime(IFNULL(r.stock_applied_dt, r.receipt_dt)) DESC,
                             r.receipt_id DESC
                    LIMIT ?
                    """,
                    (farm, iid, lim),
                ).fetchall()
                for raw in rcpt_rows or []:
                    rd = dict(raw)
                    rid = int(rd["receipt_id"])
                    # 이미 hist에 연결된 입고는 중복 제외
                    if rid in seen_receipt_ids:
                        continue
                    receipt_extra.append(rd)
            except Exception:
                receipt_extra = []

        item_d = dict(item)
        hist_rows: list[PesticideStockHistRowDto] = []
        for raw in rows or []:
            r = dict(raw)
            hist_rows.append(
                PesticideStockHistRowDto(
                    hist_id=int(r["hist_id"]),
                    trans_type=_s(r.get("trans_type")) or "",
                    ref_table=_s(r.get("ref_table")) or None,
                    ref_id=int(r["ref_id"]) if r.get("ref_id") is not None else None,
                    qty_delta=int(r.get("qty_delta") or 0),
                    qty_after=int(r["qty_after"])
                    if r.get("qty_after") is not None
                    else None,
                    trans_dt=_s(r.get("trans_dt")),
                    rmk=_s(r.get("rmk")) or None,
                    receipt_dt=_s(r.get("receipt_dt")) or None,
                    supplier_nm=_s(r.get("supplier_nm")) or None,
                )
            )

        # 명세만 있고 hist 없는 입고 → 가상 이력(음수 hist_id로 구분)
        next_virtual = -1
        for rd in receipt_extra:
            applied = _s(rd.get("stock_applied_yn")) == "Y"
            hist_rows.append(
                PesticideStockHistRowDto(
                    hist_id=next_virtual,
                    trans_type="IN",
                    ref_table="t_pesticide_receipt",
                    ref_id=int(rd["receipt_id"]),
                    qty_delta=int(rd.get("qty_delta") or 0),
                    qty_after=None,
                    trans_dt=_s(rd.get("trans_dt")),
                    rmk="입고명세" + ("" if applied else " · 미반영"),
                    receipt_dt=_s(rd.get("receipt_dt")) or None,
                    supplier_nm=_s(rd.get("supplier_nm")) or None,
                )
            )
            next_virtual -= 1

        hist_rows.sort(
            key=lambda x: (_s(x.trans_dt), x.hist_id),
            reverse=True,
        )
        # 입고·가상행 등 qty_after 누락 시 현재고부터 역추적해 잔량 보강
        hist_rows = _fill_stock_hist_qty_after(hist_rows, current_qty)
        return PesticideStockHistListResponse(
            item_id=iid,
            item_nm=_s(item_d.get("item_nm")) or f"품목{iid}",
            rows=hist_rows[:lim],
        )
