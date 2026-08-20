# -*- coding: utf-8 -*-
"""판매 confirm — logical 배송 allocation ↔ FIFO sales_detail bridge (2C).

사용자 배송배분과 Core FIFO stock split은 별개다.
qty 기준으로 detail에 배분하며, allocation이 FIFO 경계를 넘을 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_QTY_EPS = 1e-9


@dataclass
class ShipDeliveryAllocIn:
    qty: float
    rcv_name: str = ""
    rcv_tel: str = ""
    rcv_addr: str = ""
    dlvry_msg: str = ""
    ship_fee: float = 0.0


def alloc_qty_sum(allocs: list[ShipDeliveryAllocIn] | None) -> float:
    if not allocs:
        return 0.0
    return sum(float(a.qty or 0) for a in allocs)


def alloc_ship_fee_sum(allocs: list[ShipDeliveryAllocIn] | None) -> float:
    if not allocs:
        return 0.0
    return sum(max(0.0, float(a.ship_fee or 0)) for a in allocs)


def bridge_allocs_to_fifo_details(
    *,
    sales_no: str,
    detail_rows: list[tuple[str, float]],
    allocations: list[ShipDeliveryAllocIn],
    group_seq_start: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    """FIFO detail 목록에 allocation을 qty로 연결.

    Returns:
        (physical delivery rows, next group_seq)
    """
    if not detail_rows or not allocations:
        return [], group_seq_start

    det_i = 0
    det_remain = float(detail_rows[0][1])
    group_seq = int(group_seq_start)
    per_detail_dseq: dict[str, int] = {}
    out: list[dict[str, Any]] = []

    for alloc in allocations:
        need = float(alloc.qty or 0)
        if need <= _QTY_EPS:
            continue
        group_no = f"{sales_no}-G{group_seq:03d}"
        group_seq += 1
        first_physical = True
        while need > _QTY_EPS:
            while det_remain <= _QTY_EPS:
                det_i += 1
                if det_i >= len(detail_rows):
                    raise ValueError("delivery_bridge_overflow")
                det_remain = float(detail_rows[det_i][1])
            take = min(need, det_remain)
            det_no = detail_rows[det_i][0]
            dseq = per_detail_dseq.get(det_no, 0) + 1
            per_detail_dseq[det_no] = dseq
            fee = float(alloc.ship_fee or 0) if first_physical else 0.0
            first_physical = False
            out.append(
                {
                    "dlvry_no": f"{det_no}-D{dseq:03d}",
                    "sale_detail_no": det_no,
                    "dlvry_group_no": group_no,
                    "dlvry_qty": take,
                    "ship_fee": fee,
                    "rcv_name": str(alloc.rcv_name or "").strip(),
                    "rcv_tel": str(alloc.rcv_tel or "").strip(),
                    "rcv_addr": str(alloc.rcv_addr or "").strip(),
                    "dlvry_msg": str(alloc.dlvry_msg or "").strip(),
                }
            )
            need -= take
            det_remain -= take
    return out, group_seq
