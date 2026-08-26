# -*- coding: utf-8 -*-
"""PC 판매 재저장 — order_no 보존(P1) + 선입금 행 불변(P2) + 판매일 우회차단(P2b)
+ 출고확정 CONFIRMED 판매 read-only(DEC-031 · Stage7A)
+ 기존 수금 immutable + 판매금액 backstop(DEC-032/034 · Stage7B-1).

Service 계층이 아님. SalesPage.execute_full_save와 테스트가 동일 규칙을 쓴다.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping, Sequence

MSG_PREPAY_CASH_IMMUTABLE = (
    "출고 시 자동 적용된 선입금 내역은 판매관리에서 수정하거나 삭제할 수 없습니다.\n"
    "선입금 관련 변경이 필요한 경우 주문/출고 이력을 확인해 주세요."
)
MSG_PREPAY_SALES_DT_IMMUTABLE = (
    "출고 시 자동 적용된 선입금이 있는 판매는 판매일을 변경할 수 없습니다.\n"
    "선입금 관련 변경이 필요한 경우 주문/출고 이력을 확인해 주세요."
)
MSG_SHIPMENT_CONFIRMED_SALE_LOCKED = (
    "출고 확정 판매는 재고·주문 정합성을 위해 수정할 수 없습니다."
)
MSG_SHIPMENT_CONFIRMED_SALE_SAVE_BLOCKED = (
    "출고 확정 판매는 수정할 수 없습니다."
)
MSG_SHIPMENT_CONFIRMED_SALE_DELETE_BLOCKED = (
    "출고 확정 판매는 삭제할 수 없습니다."
)
MSG_SALES_AMT_BELOW_PAID = (
    "판매금액은 이미 수금된 금액보다 작게 변경할 수 없습니다."
)
MSG_SALES_DELETE_HAS_PAYMENTS = (
    "수금 내역이 있는 판매는 삭제할 수 없습니다."
)
MSG_SAVE_BEFORE_PAYMENT = (
    "판매 변경사항을 먼저 저장한 후 수금을 등록해 주세요."
)

SALES_STATUS_CONFIRMED = "CONFIRMED"
_AMT_EPSILON = 1e-9


class PcPrepayImmutableError(Exception):
    """Stage4 자동 선입금 cash 행 수정·삭제 시도."""

    def __init__(self, message: str = MSG_PREPAY_CASH_IMMUTABLE):
        super().__init__(message)


class PcShipmentConfirmedSaleLockedError(Exception):
    """DEC-031 — 출고 생성 CONFIRMED 판매 mutation 차단."""

    def __init__(self, message: str = MSG_SHIPMENT_CONFIRMED_SALE_LOCKED):
        super().__init__(message)


class PcSalesAmtBelowPaidError(Exception):
    """DEC-034 — 판매금액 < 실제 누적수금액."""

    def __init__(self, message: str = MSG_SALES_AMT_BELOW_PAID):
        super().__init__(message)


class PcSalesDeleteHasPaymentsError(Exception):
    """DEC-032 — 수금 존재 판매 삭제 차단."""

    def __init__(self, message: str = MSG_SALES_DELETE_HAS_PAYMENTS):
        super().__init__(message)


class PcPaymentStaleScreenError(Exception):
    """DEC-033 — 미저장 판매금액/판매일 변경 시 수금등록 차단."""

    def __init__(self, message: str = MSG_SAVE_BEFORE_PAYMENT):
        super().__init__(message)


def _norm_order_no(raw: Any) -> str | None:
    text = str(raw or "").strip()
    return text or None


def _has_linkage_value(raw: Any) -> bool:
    """NULL/blank는 추적키 존재로 보지 않는다."""
    if raw is None:
        return False
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, (int, float)):
        return raw != 0
    return bool(str(raw).strip())


def is_shipment_confirmed_sale_locked(
    sales_status: Any,
    master_order_no: Any,
    detail_rows: Sequence[Mapping[str, Any]] | None,
) -> bool:
    """DEC-031 — CONFIRMED + (order_no | order_detail_id | stock_seq) → read-only."""
    if str(sales_status or "").strip().upper() != SALES_STATUS_CONFIRMED:
        return False
    if _has_linkage_value(master_order_no):
        return True
    for row in detail_rows or []:
        if _has_linkage_value(row.get("order_detail_id")):
            return True
        if _has_linkage_value(row.get("stock_seq")):
            return True
    return False


def fetch_sale_lock_from_db(
    cur: sqlite3.Cursor, farm_cd: str, sales_no: str
) -> bool:
    """DB master/detail 실값으로 DEC-031 보호 여부를 재계산한다."""
    cur.execute(
        """
        SELECT sales_status, order_no
          FROM t_sales_master
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    master = cur.fetchone()
    if master is None:
        return False
    if isinstance(master, sqlite3.Row):
        sales_status = master["sales_status"]
        order_no = master["order_no"]
    else:
        sales_status, order_no = master[0], master[1]

    cur.execute(
        """
        SELECT order_detail_id, stock_seq
          FROM t_sales_detail
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    detail_rows = [
        dict(r) if isinstance(r, sqlite3.Row) else {"order_detail_id": r[0], "stock_seq": r[1]}
        for r in cur.fetchall()
    ]
    return is_shipment_confirmed_sale_locked(sales_status, order_no, detail_rows)


def assert_sale_mutable(
    cur: sqlite3.Cursor,
    farm_cd: str,
    sales_no: str,
    *,
    action: str = "save",
) -> None:
    """write/delete 직전 DB 재확인. 보호 대상이면 즉시 차단."""
    if not sales_no or not fetch_sale_lock_from_db(cur, farm_cd, sales_no):
        return
    if action == "delete":
        raise PcShipmentConfirmedSaleLockedError(MSG_SHIPMENT_CONFIRMED_SALE_DELETE_BLOCKED)
    raise PcShipmentConfirmedSaleLockedError(MSG_SHIPMENT_CONFIRMED_SALE_SAVE_BLOCKED)


def _apply_widget_lock(widget: Any, locked: bool) -> None:
    if widget is None:
        return
    widget.setEnabled(not locked)
    if hasattr(widget, "setReadOnly"):
        widget.setReadOnly(locked)


def is_protected_delivery_edit_blocked(is_protected_confirmed_sale: bool) -> bool:
    """DEC-031 — protected 판매 배송 수정/등록 popup 진입 차단."""
    return bool(is_protected_confirmed_sale)


def apply_protected_confirmed_sale_ui_lock(page: Any, locked: bool) -> None:
    """DEC-031 UI read-only. SalesPage가 위임한다. PyQt import 없음."""
    page.is_protected_confirmed_sale = locked
    hint = getattr(page, "lbl_protected_sale_hint", None)
    if hint is not None:
        hint.setText(MSG_SHIPMENT_CONFIRMED_SALE_LOCKED if locked else "")
        hint.setVisible(locked)

    master_inputs = [
        getattr(page, "sales_dt", None),
        getattr(page, "custm_nm", None),
        getattr(page, "sales_tp", None),
        getattr(page, "rmk", None),
        getattr(page, "bill_no", None),
        getattr(page, "pay_method_cd", None),
        getattr(page, "receipt_yn", None),
        getattr(page, "receipt_dt", None),
        getattr(page, "auction_fee", None),
        getattr(page, "extra_cost", None),
    ]
    master_buttons = [
        getattr(page, "btn_save", None),
        getattr(page, "btn_delete", None),
        getattr(page, "btn_item_add", None),
        getattr(page, "btn_cust_search", None),
        getattr(page, "btn_manual_reg", None),
        getattr(page, "btn_history", None),
        getattr(page, "btn_select_all", None),
        getattr(page, "btn_del_row", None),
        getattr(page, "btn_form_down", None),
        getattr(page, "btn_excel_upload", None),
        getattr(page, "btn_excel_down", None),
    ]
    for widget in master_inputs + master_buttons:
        _apply_widget_lock(widget, locked)

    item_table = getattr(page, "item_table", None)
    if item_table is not None:
        for r in range(item_table.rowCount()):
            for c in (0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 12):
                _apply_widget_lock(item_table.cellWidget(r, c), locked)

    pay_table = getattr(page, "pay_table", None)
    if pay_table is not None:
        for r in range(pay_table.rowCount()):
            for c in range(5):
                _apply_widget_lock(pay_table.cellWidget(r, c), locked)

    if not locked:
        active_row = getattr(page, "active_row", -1)
        handler = getattr(page, "handle_delivery_tp_change", None)
        if active_row >= 0 and callable(handler):
            handler(active_row)


def apply_payment_immutable_ui_lock(page: Any) -> None:
    """DEC-032 — 기존 수금 read-only · edit/delete 항상 disable. btn_pay_add는 별도 제어."""
    for name in ("btn_pay_edit", "btn_pay_del"):
        widget = getattr(page, name, None)
        if widget is not None:
            widget.setEnabled(False)

    pay_table = getattr(page, "pay_table", None)
    if pay_table is None:
        return
    for r in range(pay_table.rowCount()):
        for c in range(5):
            _apply_widget_lock(pay_table.cellWidget(r, c), True)


def is_payment_add_allowed(sales_status: Any, unpaid_amt: float) -> bool:
    """CONFIRMED + unpaid > 0 이면 신규수금 등록 허용 (Stage7A protected 포함)."""
    if str(sales_status or "").strip().upper() != SALES_STATUS_CONFIRMED:
        return False
    try:
        unpaid = float(unpaid_amt)
    except (TypeError, ValueError):
        unpaid = 0.0
    return unpaid > _AMT_EPSILON


def set_payment_add_enabled(page: Any, enabled: bool) -> None:
    """btn_pay_add만 제어. immutable helper와 분리 (Stage7B-2)."""
    widget = getattr(page, "btn_pay_add", None)
    if widget is not None:
        widget.setEnabled(bool(enabled))


def assert_payment_screen_not_stale(
    *,
    ui_tot_sales_amt: float,
    db_tot_sales_amt: float,
    ui_sales_dt: Any,
    db_sales_dt: Any,
) -> None:
    """미저장 판매금액/판매일 불일치 시 add_payment 호출 전 차단."""
    ui_total = float(ui_tot_sales_amt)
    db_total = float(db_tot_sales_amt)
    if abs(ui_total - db_total) > _AMT_EPSILON:
        raise PcPaymentStaleScreenError()
    ui_dt = str(ui_sales_dt or "").strip()[:10]
    db_dt = str(db_sales_dt or "").strip()[:10]
    if ui_dt != db_dt:
        raise PcPaymentStaleScreenError()


def fetch_actual_paid_amt(conn: sqlite3.Connection, farm_cd: str, sales_no: str) -> float:
    """기존 판매 actual paid SSOT — SalesPaymentService cash 합계."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
              FROM t_sales_master
             WHERE farm_cd = ? AND sales_no = ?
            """,
            (farm_cd, sales_no),
        )
        if not cur.fetchone():
            return 0.0
        from core.sales_payment_service import SalesPaymentService

        summary = SalesPaymentService(conn).get_payment_summary(farm_cd, sales_no)
        return float(summary.get("tot_paid_amt") or 0)
    finally:
        cur.close()


def assert_sales_total_not_below_paid(new_total: float, actual_paid: float) -> None:
    """DEC-034 — DELETE/INSERT 전 판매금액 backstop."""
    if float(new_total) + _AMT_EPSILON < float(actual_paid):
        raise PcSalesAmtBelowPaidError()


def compute_master_paid_unpaid(new_total: float, actual_paid: float) -> tuple[float, float]:
    """master tot_paid/tot_unpaid — UI pay_table 합계가 아닌 actual_paid 기준."""
    paid = float(actual_paid)
    unpaid = max(0.0, float(new_total) - paid)
    return paid, unpaid


def assert_no_cash_for_delete(
    cur: sqlite3.Cursor, farm_cd: str, sales_no: str
) -> None:
    """DEC-032 — 수금 1건 이상이면 판매 삭제 차단 (confirm dialog 이전)."""
    cur.execute(
        """
        SELECT 1
          FROM t_cash_ledger
         WHERE farm_cd = ? AND sales_no = ?
         LIMIT 1
        """,
        (farm_cd, sales_no),
    )
    if cur.fetchone():
        raise PcSalesDeleteHasPaymentsError()


def validate_protected_prepay_sales_dt_from_db(
    cur: sqlite3.Cursor,
    farm_cd: str,
    sales_no: str,
    *,
    original_sales_dt: Any,
    current_sales_dt: Any,
) -> None:
    """DB cash 실값으로 선입금 판매일 변경 차단 (full-save cash mutation 제거 후)."""
    cur.execute(
        """
        SELECT pay_dt, pay_method_cd, pay_amt, order_no, slip_no, paid_detail_no
          FROM t_cash_ledger
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    pay_basket: list[dict[str, Any]] = []
    for row in cur.fetchall():
        orig = dict(row) if isinstance(row, sqlite3.Row) else {
            "pay_dt": row[0],
            "pay_method_cd": row[1],
            "pay_amt": row[2],
            "order_no": row[3],
            "slip_no": row[4],
            "paid_detail_no": row[5],
        }
        pay_basket.append(
            {
                "status": "ORG",
                "orig_data": orig,
                "pay_dt": orig.get("pay_dt"),
                "method": orig.get("pay_method_cd"),
                "pay_method_cd": orig.get("pay_method_cd"),
                "amt": orig.get("pay_amt"),
                "pay_amt": orig.get("pay_amt"),
            }
        )
    validate_protected_prepay_sales_dt(
        pay_basket, original_sales_dt, current_sales_dt
    )


def _norm_pay_dt(raw: Any) -> str:
    return str(raw or "").strip()[:10]


def _norm_method(raw: Any) -> str:
    return str(raw or "").strip()


def _norm_amt(raw: Any) -> float:
    try:
        return round(float(raw if raw is not None else 0), 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_master_order_no(
    cur: sqlite3.Cursor, farm_cd: str, sales_no: str
) -> str | None:
    """DELETE 전 DB의 t_sales_master.order_no만 읽는다. UI/역산 금지."""
    cur.execute(
        """
        SELECT order_no
          FROM t_sales_master
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return _norm_order_no(row["order_no"])
    return _norm_order_no(row[0])


def fetch_master_sales_dt(
    cur: sqlite3.Cursor, farm_cd: str, sales_no: str
) -> str | None:
    """DELETE 전 DB의 t_sales_master.sales_dt만 읽는다. UI/역산 금지."""
    cur.execute(
        """
        SELECT sales_dt
          FROM t_sales_master
         WHERE farm_cd = ? AND sales_no = ?
        """,
        (farm_cd, sales_no),
    )
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        raw = row["sales_dt"]
    else:
        raw = row[0]
    text = _norm_pay_dt(raw)
    return text or None


def cash_order_no_on_resave(
    *, status: str, orig_data: Mapping[str, Any] | None
) -> str | None:
    """cash 행별 order_no.

    ORG/MOD → orig_data.order_no 보존
    INS     → 항상 NULL (PC 신규 일반수금)
    """
    st = str(status or "").strip().upper()
    if st == "INS":
        return None
    if st in {"ORG", "MOD"}:
        if not orig_data:
            return None
        return _norm_order_no(orig_data.get("order_no"))
    return None


def is_protected_prepay_orig(orig_data: Mapping[str, Any] | None) -> bool:
    """보호 대상 = orig_data.order_no IS NOT NULL (Stage4 자동 선입금)."""
    if not orig_data:
        return False
    return _norm_order_no(orig_data.get("order_no")) is not None


def validate_protected_prepay_row(
    *,
    status: str,
    orig_data: Mapping[str, Any] | None,
    pay_dt: Any = None,
    pay_method_cd: Any = None,
    pay_amt: Any = None,
) -> None:
    """보호 행이면 MOD/DEL 및 ORG 핵심값 변경을 거부한다."""
    if not is_protected_prepay_orig(orig_data):
        return

    st = str(status or "").strip().upper()
    if st in {"MOD", "DEL"}:
        raise PcPrepayImmutableError()

    # ORG(및 UI 상태 누락)라도 핵심값 변경이면 거부
    o = orig_data or {}
    if (
        _norm_pay_dt(o.get("pay_dt")) != _norm_pay_dt(pay_dt)
        or _norm_method(o.get("pay_method_cd")) != _norm_method(pay_method_cd)
        or _norm_amt(o.get("pay_amt")) != _norm_amt(pay_amt)
    ):
        raise PcPrepayImmutableError()


def validate_pc_prepay_basket(pay_basket: Sequence[Mapping[str, Any]]) -> None:
    """pay_basket(+deleted) 전체에 대해 Stage4 선입금 불변성 검증."""
    for item in pay_basket:
        orig = item.get("orig_data")
        method = item.get("pay_method_cd")
        if method is None:
            method = item.get("method")
        amt = item.get("pay_amt")
        if amt is None:
            amt = item.get("amt")
        pay_dt = item.get("pay_dt")
        if pay_dt is None and isinstance(orig, Mapping):
            pay_dt = orig.get("pay_dt")
        validate_protected_prepay_row(
            status=str(item.get("status") or ""),
            orig_data=orig if isinstance(orig, Mapping) else None,
            pay_dt=pay_dt,
            pay_method_cd=method,
            pay_amt=amt,
        )


def basket_has_protected_prepay(pay_basket: Sequence[Mapping[str, Any]]) -> bool:
    for item in pay_basket:
        orig = item.get("orig_data")
        if isinstance(orig, Mapping) and is_protected_prepay_orig(orig):
            return True
    return False


def validate_protected_prepay_sales_dt(
    pay_basket: Sequence[Mapping[str, Any]],
    original_sales_dt: Any,
    current_sales_dt: Any,
) -> None:
    """보호 선입금 cash가 있으면 master.sales_dt 변경 금지 (P2b)."""
    if not basket_has_protected_prepay(pay_basket):
        return
    orig = _norm_pay_dt(original_sales_dt)
    cur = _norm_pay_dt(current_sales_dt)
    if not orig:
        # 신규 판매(기존 row 없음) — 판매일 변경 이슈 없음
        return
    if orig != cur:
        raise PcPrepayImmutableError(MSG_PREPAY_SALES_DT_IMMUTABLE)


def validate_pc_prepay_save(
    pay_basket: Sequence[Mapping[str, Any]],
    *,
    original_sales_dt: Any,
    current_sales_dt: Any,
) -> None:
    """SalesPage 저장 직전 통합 검증 (행 불변 + 판매일 불변)."""
    validate_pc_prepay_basket(pay_basket)
    validate_protected_prepay_sales_dt(
        pay_basket, original_sales_dt, current_sales_dt
    )
