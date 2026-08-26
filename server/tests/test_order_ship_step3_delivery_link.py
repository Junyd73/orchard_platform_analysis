# -*- coding: utf-8 -*-
"""Step3 §22 — order_dlvry_id 실배송 추적 (Core).

주문 배송지(t_order_delivery.order_dlvry_id)를 출고 시 물리 배송행
(t_sales_delivery.order_dlvry_id)에 남기고, 조회에서 배송지별 출고누계·잔여를
집계하는지 검증한다. 스키마 헬퍼는 정상경로 테스트에서만 호출한다.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in (_HERE.parent, _HERE.parents[1], _HERE.parents[2]):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from core.ops_biz_date import today_ops_iso  # noqa: E402
from core.order_allocation_service import OrderAllocationService  # noqa: E402
from core.order_constants import (  # noqa: E402
    DELIVERY_TP_PARCEL_CD,
    DELIVERY_TP_VISIT_CD,
    ORDER_STATUS_CONFIRMED_CD,
    ORDER_STATUS_DELIVERED_CD,
    ORDER_STATUS_PREP_CD,
)
from core.order_ship_constants import SHIP_MODE_DIRECT, SHIP_MODE_STOCK  # noqa: E402
from core.order_ship_delivery import (  # noqa: E402
    ShipDeliveryAllocIn,
    bridge_allocs_to_fifo_details,
)
from core.order_ship_service import (  # noqa: E402
    OrderShipService,
    ShipConfirmIn,
    ShipError,
    ShipLineIn,
    ShipValidationError,
)
from core.order_service import (  # noqa: E402
    OrderDeliveryInput,
    OrderLineInput,
    OrderSaveInput,
    OrderService,
)

# 2C 테스트의 스키마·픽스처를 재사용한다(중복 금지). _open()이 ensure_*를 호출한다.
from test_order_ship_delivery_2c import (  # noqa: E402
    CUST,
    FARM,
    GRADE,
    ITEM,
    SIZE,
    VARIETY,
    WEIGHT,
    WH,
    YEAR,
    _alloc,
    _confirm_direct,
    _insert_stock,
    _open,
)

SND = {"snd_name": "삼육농원", "snd_tel": "010-1111-2222", "snd_addr": "전남 나주"}
UNIT_PRICE = 1000.0

_DELIVERY_NO_LINK_SQL = """
    CREATE TABLE t_sales_delivery (
        dlvry_no TEXT, sale_detail_no TEXT, sales_no TEXT, farm_cd TEXT,
        snd_name TEXT, snd_tel TEXT, snd_addr TEXT,
        rcv_name TEXT, rcv_tel TEXT, rcv_addr TEXT,
        dlvry_qty REAL, dlvry_msg TEXT, ship_no TEXT, ship_dt TEXT,
        dlvry_group_no TEXT, ship_fee REAL, reg_id TEXT, reg_dt TEXT,
        PRIMARY KEY (dlvry_no, farm_cd)
    )
"""


def _bridge_alloc(qty: float, oid: str = "") -> ShipDeliveryAllocIn:
    return ShipDeliveryAllocIn(
        qty=qty, rcv_name="홍", rcv_tel="010", rcv_addr="서울", order_dlvry_id=oid
    )


class Step3BridgeTest(unittest.TestCase):
    """DB 없이 allocation → FIFO detail bridge의 order_dlvry_id 전파만 검증."""

    def test_t3_single_lot_keeps_source_id(self) -> None:
        rows, next_seq = bridge_allocs_to_fifo_details(
            sales_no="20260820-01",
            detail_rows=[("20260820-01-S01", 3.0)],
            allocations=[_bridge_alloc(3.0, "ORD20260101-001-01-P01")],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["order_dlvry_id"], "ORD20260101-001-01-P01")
        self.assertEqual(next_seq, 2)

    def test_t4_two_lot_split_shares_order_dlvry_id(self) -> None:
        rows, _ = bridge_allocs_to_fifo_details(
            sales_no="20260820-01",
            detail_rows=[("20260820-01-S01", 1.0), ("20260820-01-S02", 2.0)],
            allocations=[_bridge_alloc(3.0, "ORD20260101-001-01-P01")],
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["order_dlvry_id"] for r in rows}, {"ORD20260101-001-01-P01"})
        # 동일 배송지이므로 물리 2행이 같은 그룹
        self.assertEqual(rows[0]["dlvry_group_no"], rows[1]["dlvry_group_no"])
        self.assertAlmostEqual(sum(float(r["dlvry_qty"]) for r in rows), 3.0)

    def test_t4b_two_dest_keep_own_ids(self) -> None:
        rows, _ = bridge_allocs_to_fifo_details(
            sales_no="20260820-01",
            detail_rows=[("20260820-01-S01", 1.0), ("20260820-01-S02", 2.0)],
            allocations=[_bridge_alloc(2.0, "D-P01"), _bridge_alloc(1.0, "D-P02")],
        )
        by_id: dict[str, float] = {}
        for r in rows:
            by_id[r["order_dlvry_id"]] = by_id.get(r["order_dlvry_id"], 0.0) + float(
                r["dlvry_qty"]
            )
        self.assertAlmostEqual(by_id["D-P01"], 2.0)
        self.assertAlmostEqual(by_id["D-P02"], 1.0)

    def test_t5_blank_id_stays_blank(self) -> None:
        rows, _ = bridge_allocs_to_fifo_details(
            sales_no="20260820-01",
            detail_rows=[("20260820-01-S01", 2.0)],
            allocations=[_bridge_alloc(2.0)],
        )
        self.assertEqual(rows[0]["order_dlvry_id"], "")


class Step3DeliveryLinkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    # ------------------------------------------------------------------ helpers
    def _create_parcel_order(self, *qtys: float) -> tuple[str, str, list[str]]:
        """택배 주문 1 line + 배송지 n건 생성·확정 → (order_no, det_id, order_dlvry_ids)."""
        svc = OrderService(self.conn)
        order_no = svc.create_order(
            FARM,
            OrderSaveInput(
                custm_id=CUST,
                order_dt=None,
                sales_type_cd="SA010100",
                season_type_cd="SS010100",
                pre_pay_amt=0,
                lines=[
                    OrderLineInput(
                        variety_cd=VARIETY,
                        weight=WEIGHT,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        qty=sum(qtys),
                        unit_price=UNIT_PRICE,
                        harvest_year=YEAR,
                        warehouse_cd=WH,
                        item_cd=ITEM,
                        dlvry_tp=DELIVERY_TP_PARCEL_CD,
                        deliveries=[
                            OrderDeliveryInput(
                                delivery_tp_cd=DELIVERY_TP_PARCEL_CD,
                                qty=q,
                                planned_dt=today_ops_iso(),
                                rcv_name=f"수령{i}",
                                rcv_tel="010-0000-0000",
                                rcv_addr=f"서울 {i}",
                                **SND,
                            )
                            for i, q in enumerate(qtys, start=1)
                        ],
                    )
                ],
            ),
            user_id="T",
        )
        svc.confirm_order(FARM, order_no, user_id="T")
        det_id = f"{order_no}-01"
        return order_no, det_id, [f"{det_id}-P{i:02d}" for i in range(1, len(qtys) + 1)]

    def _ship_order(
        self,
        *,
        order_no: str,
        det_id: str,
        qty: float,
        allocs: list[ShipDeliveryAllocIn] | None,
        mode: str = SHIP_MODE_DIRECT,
        dlvry_tp: str = DELIVERY_TP_PARCEL_CD,
        rcv_name: str = "",
    ) -> dict:
        fee = sum(float(a.ship_fee or 0) for a in (allocs or []))
        return OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=mode,
                order_no=order_no,
                sales_dt="2026-08-20",
                custm_id=CUST,
                user_id="T",
                dlvry_tp=dlvry_tp,
                ship_fee=fee,
                rcv_name=rcv_name,
                rcv_tel="010-0000-0000" if rcv_name else "",
                rcv_addr="서울 legacy" if rcv_name else "",
                lines=[
                    ShipLineIn(
                        qty=qty,
                        order_detail_id=det_id,
                        item_cd=ITEM,
                        variety_cd=VARIETY,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        weight=WEIGHT,
                        harvest_year=YEAR,
                        wh_cd=WH,
                        unit_price=UNIT_PRICE,
                        delivery_allocations=allocs,
                    )
                ],
                **SND,
            )
        )

    def _link_rows(self, sales_no: str) -> list[tuple[str, float]]:
        return [
            (str(r["order_dlvry_id"] or ""), float(r["dlvry_qty"] or 0))
            for r in self.conn.execute(
                """
                SELECT order_dlvry_id, dlvry_qty FROM t_sales_delivery
                WHERE sales_no = ? ORDER BY dlvry_no
                """,
                (sales_no,),
            ).fetchall()
        ]

    def _dest(self, order_no: str) -> tuple[dict, dict[str, dict]]:
        payload = OrderService(self.conn).get_order(FARM, order_no)
        line = payload["lines"][0]
        return payload, {d["order_dlvry_id"]: d for d in line["deliveries"]}

    def _order_status(self, order_no: str) -> str:
        row = self.conn.execute(
            "SELECT status_cd FROM t_order_master WHERE order_no = ?", (order_no,)
        ).fetchone()
        return str(row["status_cd"] or "")

    def _assert_no_sale_side_effects(self, stock_seq: int) -> None:
        for table in ("t_sales_master", "t_sales_detail", "t_stock_log"):
            self.assertEqual(
                self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )
        row = self.conn.execute(
            "SELECT out_qty FROM t_stock_master WHERE stock_seq = ?", (stock_seq,)
        ).fetchone()
        self.assertEqual(float(row["out_qty"]), 0)

    # -------------------------------------------------------------------- tests
    def test_t6_direct_sale_without_link_is_null(self) -> None:
        """주문 없는 직접 택배판매: order_dlvry_id 미지정 → NULL 저장, 기존 동작 유지."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=10)
        out = _confirm_direct(
            self.conn,
            qty=3,
            allocs=[_alloc(2, name="A", fee=4000), _alloc(1, name="B")],
        )
        self.assertTrue(out["ok"])
        rows = self.conn.execute(
            "SELECT order_dlvry_id FROM t_sales_delivery WHERE sales_no = ?",
            (out["sales_no"],),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertIsNone(r["order_dlvry_id"])

    def test_t7_order_parcel_single_lot_persists_link(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        out = self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="수령1", order_dlvry_id=oids[0])],
        )
        self.assertEqual(self._link_rows(out["sales_no"]), [(oids[0], 10.0)])

    def test_t8_order_parcel_fifo_split_shares_link(self) -> None:
        """FIFO 2 LOT 분할 → 물리 2행 모두 동일 order_dlvry_id."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=4)
        _insert_stock(self.conn, storage_dt="2026-01-02", in_qty=20)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        out = self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="수령1", order_dlvry_id=oids[0])],
        )
        rows = self._link_rows(out["sales_no"])
        self.assertEqual(len(rows), 2)
        self.assertEqual({oid for oid, _ in rows}, {oids[0]})
        self.assertAlmostEqual(sum(q for _, q in rows), 10.0)

    def test_t9_stock_mode_persists_link(self) -> None:
        """배정 출고(STOCK) 경로도 동일하게 order_dlvry_id를 남긴다."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        OrderAllocationService(self.conn).allocate(
            FARM, order_no, order_detail_id=det_id, qty=10, auto=False, user_id="T"
        )
        out = self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="수령1", order_dlvry_id=oids[0])],
            mode=SHIP_MODE_STOCK,
        )
        self.assertEqual(self._link_rows(out["sales_no"]), [(oids[0], 10.0)])

    def test_t10_missing_column_schema_precondition(self) -> None:
        """order_dlvry_id 컬럼 없는 스키마 + 링크 요청 → SCHEMA_PRECONDITION, 부작용 0."""
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.execute(_DELIVERY_NO_LINK_SQL)
        self.conn.commit()
        with self.assertRaises(ShipError) as ctx:
            self._ship_order(
                order_no=order_no,
                det_id=det_id,
                qty=10,
                allocs=[_alloc(10, name="수령1", order_dlvry_id=oids[0])],
            )
        self.assertEqual(getattr(ctx.exception, "code", ""), "SCHEMA_PRECONDITION")
        self._assert_no_sale_side_effects(seq)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0], 0
        )
        self.assertEqual(self._order_status(order_no), ORDER_STATUS_CONFIRMED_CD)

    def test_t11_link_without_column_ok_when_not_requested(self) -> None:
        """링크를 요청하지 않으면 컬럼이 없어도 2C 동작 그대로 성공."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, _ = self._create_parcel_order(10, 20)
        self.conn.execute("DROP TABLE t_sales_delivery")
        self.conn.execute(_DELIVERY_NO_LINK_SQL)
        self.conn.commit()
        out = self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="수령1")],
        )
        self.assertTrue(out["ok"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_delivery").fetchone()[0], 1
        )

    def test_t12_failed_tx_no_side_effects(self) -> None:
        """링크가 있어도 수량 불일치면 TX 전체 롤백 — 판매·재고 부작용 0."""
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        with self.assertRaises(ShipValidationError):
            self._ship_order(
                order_no=order_no,
                det_id=det_id,
                qty=10,
                allocs=[_alloc(9, name="수령1", order_dlvry_id=oids[0])],
            )
        self._assert_no_sale_side_effects(seq)
        self.assertEqual(self._order_status(order_no), ORDER_STATUS_CONFIRMED_CD)

    def test_t13_get_order_destination_aggregation(self) -> None:
        """배송지별 출고누계·잔여가 order_dlvry_id 기준으로 집계된다."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="수령1", order_dlvry_id=oids[0])],
        )
        payload, dests = self._dest(order_no)
        line = payload["lines"][0]
        self.assertAlmostEqual(line["confirmed_shipped_qty"], 10.0)
        self.assertAlmostEqual(line["remaining_order_qty"], 20.0)
        self.assertAlmostEqual(line["untracked_delivery_shipped_qty"], 0.0)
        self.assertAlmostEqual(dests[oids[0]]["confirmed_shipped_qty"], 10.0)
        self.assertAlmostEqual(dests[oids[0]]["remaining_qty"], 0.0)
        self.assertAlmostEqual(dests[oids[1]]["confirmed_shipped_qty"], 0.0)
        self.assertAlmostEqual(dests[oids[1]]["remaining_qty"], 20.0)

    def test_t14_partial_ship_then_delivered(self) -> None:
        """10/30 부분출고 → 잔여 20 · ST010300, 남은 20 출고 → ST010400."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="수령1", order_dlvry_id=oids[0])],
        )
        self.assertEqual(self._order_status(order_no), ORDER_STATUS_PREP_CD)
        _, dests = self._dest(order_no)
        self.assertAlmostEqual(dests[oids[1]]["remaining_qty"], 20.0)

        self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=20,
            allocs=[_alloc(20, name="수령2", order_dlvry_id=oids[1])],
        )
        self.assertEqual(self._order_status(order_no), ORDER_STATUS_DELIVERED_CD)
        payload, dests = self._dest(order_no)
        line = payload["lines"][0]
        self.assertAlmostEqual(line["confirmed_shipped_qty"], 30.0)
        self.assertAlmostEqual(line["remaining_order_qty"], 0.0)
        for oid, planned in ((oids[0], 10.0), (oids[1], 20.0)):
            self.assertAlmostEqual(dests[oid]["confirmed_shipped_qty"], planned)
            self.assertAlmostEqual(dests[oid]["remaining_qty"], 0.0)

    def test_t15_untracked_delivery_shipped_qty(self) -> None:
        """order_dlvry_id 없이 출고된 이력 → untracked_delivery_shipped_qty > 0."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        # legacy 경로(allocation 미전송) → t_sales_delivery.order_dlvry_id NULL
        self._ship_order(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=None,
            dlvry_tp=DELIVERY_TP_VISIT_CD,
            rcv_name="레거시수령",
        )
        rows = self.conn.execute(
            "SELECT order_dlvry_id FROM t_sales_delivery"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["order_dlvry_id"])

        payload, dests = self._dest(order_no)
        line = payload["lines"][0]
        self.assertAlmostEqual(line["confirmed_shipped_qty"], 10.0)
        self.assertAlmostEqual(line["untracked_delivery_shipped_qty"], 10.0)
        # 추적 불가 이력은 배송지 잔여에 반영되지 않는다(재확인 안내용 신호)
        self.assertAlmostEqual(dests[oids[0]]["remaining_qty"], 10.0)
        self.assertAlmostEqual(dests[oids[1]]["remaining_qty"], 20.0)


class Step3OrderDeliveryLinkGateTest(unittest.TestCase):
    """order_dlvry_id 소유권·잔여수량 Gate (TX 내 검증, side effect 0)."""

    def setUp(self) -> None:
        self.path, self.conn = _open()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _create_parcel_order(self, *qtys: float) -> tuple[str, str, list[str]]:
        svc = OrderService(self.conn)
        order_no = svc.create_order(
            FARM,
            OrderSaveInput(
                custm_id=CUST,
                order_dt=None,
                sales_type_cd="SA010100",
                season_type_cd="SS010100",
                pre_pay_amt=0,
                lines=[
                    OrderLineInput(
                        variety_cd=VARIETY,
                        weight=WEIGHT,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        qty=sum(qtys),
                        unit_price=UNIT_PRICE,
                        harvest_year=YEAR,
                        warehouse_cd=WH,
                        item_cd=ITEM,
                        dlvry_tp=DELIVERY_TP_PARCEL_CD,
                        deliveries=[
                            OrderDeliveryInput(
                                delivery_tp_cd=DELIVERY_TP_PARCEL_CD,
                                qty=q,
                                planned_dt=today_ops_iso(),
                                rcv_name=f"수령{i}",
                                rcv_tel="010-0000-0000",
                                rcv_addr=f"서울 {i}",
                                **SND,
                            )
                            for i, q in enumerate(qtys, start=1)
                        ],
                    )
                ],
            ),
            user_id="T",
        )
        svc.confirm_order(FARM, order_no, user_id="T")
        det_id = f"{order_no}-01"
        return order_no, det_id, [f"{det_id}-P{i:02d}" for i in range(1, len(qtys) + 1)]

    def _create_two_line_parcel(self) -> tuple[str, str, str, str, str]:
        """2 line 택배 주문 → (order_no, det1, oid1, det2, oid2)."""
        svc = OrderService(self.conn)
        order_no = svc.create_order(
            FARM,
            OrderSaveInput(
                custm_id=CUST,
                order_dt=None,
                sales_type_cd="SA010100",
                season_type_cd="SS010100",
                pre_pay_amt=0,
                lines=[
                    OrderLineInput(
                        variety_cd=VARIETY,
                        weight=WEIGHT,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        qty=10,
                        unit_price=UNIT_PRICE,
                        harvest_year=YEAR,
                        warehouse_cd=WH,
                        item_cd=ITEM,
                        dlvry_tp=DELIVERY_TP_PARCEL_CD,
                        deliveries=[
                            OrderDeliveryInput(
                                delivery_tp_cd=DELIVERY_TP_PARCEL_CD,
                                qty=10,
                                planned_dt=today_ops_iso(),
                                rcv_name="L1",
                                rcv_tel="010-0000-0000",
                                rcv_addr="서울 1",
                                **SND,
                            )
                        ],
                    ),
                    OrderLineInput(
                        variety_cd=VARIETY,
                        weight=WEIGHT,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        qty=5,
                        unit_price=UNIT_PRICE,
                        harvest_year=YEAR,
                        warehouse_cd=WH,
                        item_cd=ITEM,
                        dlvry_tp=DELIVERY_TP_PARCEL_CD,
                        deliveries=[
                            OrderDeliveryInput(
                                delivery_tp_cd=DELIVERY_TP_PARCEL_CD,
                                qty=5,
                                planned_dt=today_ops_iso(),
                                rcv_name="L2",
                                rcv_tel="010-0000-0000",
                                rcv_addr="서울 2",
                                **SND,
                            )
                        ],
                    ),
                ],
            ),
            user_id="T",
        )
        svc.confirm_order(FARM, order_no, user_id="T")
        det1, det2 = f"{order_no}-01", f"{order_no}-02"
        return order_no, det1, f"{det1}-P01", det2, f"{det2}-P01"

    def _ship(
        self,
        *,
        order_no: str,
        det_id: str,
        qty: float,
        allocs: list[ShipDeliveryAllocIn],
    ) -> dict:
        fee = sum(float(a.ship_fee or 0) for a in allocs)
        return OrderShipService(self.conn).confirm(
            ShipConfirmIn(
                farm_cd=FARM,
                ship_mode=SHIP_MODE_DIRECT,
                order_no=order_no,
                sales_dt="2026-08-20",
                custm_id=CUST,
                user_id="T",
                dlvry_tp=DELIVERY_TP_PARCEL_CD,
                ship_fee=fee,
                lines=[
                    ShipLineIn(
                        qty=qty,
                        order_detail_id=det_id,
                        item_cd=ITEM,
                        variety_cd=VARIETY,
                        grade_cd=GRADE,
                        size_cd=SIZE,
                        weight=WEIGHT,
                        harvest_year=YEAR,
                        wh_cd=WH,
                        unit_price=UNIT_PRICE,
                        delivery_allocations=allocs,
                    )
                ],
                **SND,
            )
        )

    def _assert_clean(self, stock_seq: int) -> None:
        for table in ("t_sales_master", "t_sales_detail", "t_stock_log"):
            self.assertEqual(
                self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )
        row = self.conn.execute(
            "SELECT out_qty FROM t_stock_master WHERE stock_seq = ?", (stock_seq,)
        ).fetchone()
        self.assertEqual(float(row["out_qty"]), 0)

    def test_g1_valid_current_line_id_succeeds(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        out = self._ship(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="A", order_dlvry_id=oids[0])],
        )
        self.assertTrue(out["ok"])
        self.assertEqual(
            self.conn.execute(
                "SELECT order_dlvry_id FROM t_sales_delivery WHERE sales_no=?",
                (out["sales_no"],),
            ).fetchone()[0],
            oids[0],
        )
        _ = seq  # stock used; success path may have OUT

    def test_g2_missing_id_blocked(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, _oids = self._create_parcel_order(10, 20)
        with self.assertRaises(ShipValidationError) as ctx:
            self._ship(
                order_no=order_no,
                det_id=det_id,
                qty=10,
                allocs=[_alloc(10, name="X", order_dlvry_id=f"{det_id}-P99")],
            )
        self.assertEqual(ctx.exception.code, "ORDER_DELIVERY_LINK_INVALID")
        self._assert_clean(seq)

    def test_g3_other_order_id_blocked(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_a, det_a, oids_a = self._create_parcel_order(10, 20)
        order_b, det_b, oids_b = self._create_parcel_order(5)
        with self.assertRaises(ShipValidationError) as ctx:
            self._ship(
                order_no=order_a,
                det_id=det_a,
                qty=5,
                allocs=[_alloc(5, name="B", order_dlvry_id=oids_b[0])],
            )
        self.assertEqual(ctx.exception.code, "ORDER_DELIVERY_LINK_INVALID")
        self._assert_clean(seq)
        self.assertNotEqual(order_a, order_b)
        self.assertNotEqual(det_a, det_b)
        self.assertNotEqual(oids_a[0], oids_b[0])

    def test_g4_other_line_id_same_order_blocked(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det1, oid1, det2, oid2 = self._create_two_line_parcel()
        with self.assertRaises(ShipValidationError) as ctx:
            self._ship(
                order_no=order_no,
                det_id=det1,
                qty=5,
                allocs=[_alloc(5, name="L2", order_dlvry_id=oid2)],
            )
        self.assertEqual(ctx.exception.code, "ORDER_DELIVERY_LINK_INVALID")
        self._assert_clean(seq)
        self.assertNotEqual(oid1, oid2)

    def test_g5_over_planned_after_full_ship_blocked(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=40)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        self._ship(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[_alloc(10, name="A", order_dlvry_id=oids[0])],
        )
        sales_before = self.conn.execute(
            "SELECT COUNT(*) FROM t_sales_master"
        ).fetchone()[0]
        out_before = float(
            self.conn.execute(
                "SELECT out_qty FROM t_stock_master WHERE stock_seq=?", (seq,)
            ).fetchone()[0]
        )
        with self.assertRaises(ShipValidationError) as ctx:
            self._ship(
                order_no=order_no,
                det_id=det_id,
                qty=1,
                allocs=[_alloc(1, name="A", order_dlvry_id=oids[0])],
            )
        self.assertEqual(ctx.exception.code, "ORDER_DELIVERY_OVER_SHIP")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0],
            sales_before,
        )
        self.assertEqual(
            float(
                self.conn.execute(
                    "SELECT out_qty FROM t_stock_master WHERE stock_seq=?", (seq,)
                ).fetchone()[0]
            ),
            out_before,
        )

    def test_g6_partial_then_remainder_succeeds(self) -> None:
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=40)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        self._ship(
            order_no=order_no,
            det_id=det_id,
            qty=4,
            allocs=[_alloc(4, name="A", order_dlvry_id=oids[0])],
        )
        out = self._ship(
            order_no=order_no,
            det_id=det_id,
            qty=6,
            allocs=[_alloc(6, name="A", order_dlvry_id=oids[0])],
        )
        self.assertTrue(out["ok"])
        total_a = self.conn.execute(
            """
            SELECT COALESCE(SUM(dlvry_qty),0) FROM t_sales_delivery
            WHERE order_dlvry_id = ?
            """,
            (oids[0],),
        ).fetchone()[0]
        self.assertAlmostEqual(float(total_a), 10.0)

    def test_g7_same_request_duplicate_id_over_planned_blocked(self) -> None:
        seq = _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=40)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        with self.assertRaises(ShipValidationError) as ctx:
            self._ship(
                order_no=order_no,
                det_id=det_id,
                qty=11,
                allocs=[
                    _alloc(4, name="A1", order_dlvry_id=oids[0]),
                    _alloc(7, name="A2", order_dlvry_id=oids[0]),
                ],
            )
        self.assertEqual(ctx.exception.code, "ORDER_DELIVERY_OVER_SHIP")
        self._assert_clean(seq)

    def test_g8_null_id_new_destination_ok(self) -> None:
        """신규 실제배송지(order_dlvry_id blank)는 Gate 통과."""
        _insert_stock(self.conn, storage_dt="2026-01-01", in_qty=30)
        order_no, det_id, oids = self._create_parcel_order(10, 20)
        out = self._ship(
            order_no=order_no,
            det_id=det_id,
            qty=10,
            allocs=[
                _alloc(10, name="신규", order_dlvry_id=""),
            ],
        )
        self.assertTrue(out["ok"])
        row = self.conn.execute(
            "SELECT order_dlvry_id FROM t_sales_delivery WHERE sales_no=?",
            (out["sales_no"],),
        ).fetchone()
        self.assertIsNone(row["order_dlvry_id"])
        # 예정 A 잔여는 그대로(추적 안 됨)
        dest = OrderService(self.conn).get_order(FARM, order_no)["lines"][0]["deliveries"]
        by_id = {d["order_dlvry_id"]: d for d in dest}
        self.assertAlmostEqual(by_id[oids[0]]["remaining_qty"], 10.0)


if __name__ == "__main__":
    unittest.main()
