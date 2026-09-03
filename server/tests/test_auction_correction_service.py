# -*- coding: utf-8 -*-
"""DEC-037 Stage F-1 — 경락매칭 정정 Core (temp SQLite)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_HERE.parent, _SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.auction_candidate_service import AuctionCandidateService  # noqa: E402
from core.auction_correction_service import (  # noqa: E402
    AuctionCorrectionError,
    AuctionCorrectionIn,
    AuctionCorrectionService,
    auction_cancel_allowed,
    has_auction_match_history,
)
from core.auction_finalize_service import (  # noqa: E402
    AuctionDiscrepancyIn,
    AuctionFinalizeIn,
    AuctionFinalizeService,
    AuctionSelectedIn,
)
from core.auction_match_constants import (  # noqa: E402
    CODE_AUCTION_CORRECTION_MATCH,
    CODE_AUCTION_CORRECTION_PAYMENT,
    CODE_AUCTION_CORRECTION_RETURN,
    CODE_AUCTION_CORRECTION_SALES,
    CODE_AUCTION_CORRECTION_STATUS,
    MSG_REMARK_AUCTION_CORRECTION,
    REASON_QTY_ERROR,
    REASON_RETURN,
    SALES_SOURCE_AUCTION,
    TABLE_AUCTION_MATCH_DETAIL,
    TABLE_AUCTION_QTY_DISCREPANCY,
    TABLE_AUCTION_RETURN_LINE,
)
from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_CANCELLED,
    AUCTION_SHIP_STATUS_COMPLETED,
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_CANCEL_MATCHED,
    CODE_AUCTION_SHIP_NOT_FOUND,
    IO_TYPE_OUT,
    REF_TYPE_AUCTION_SHIP,
)
from core.auction_ship_service import AuctionShipError, AuctionShipService  # noqa: E402
from core.order_ship_constants import (  # noqa: E402
    SALES_STATUS_CANCELLED,
    SALES_STATUS_CONFIRMED,
    SALES_SOURCE_ORDER,
)
from core.sales_payment_constants import SALES_STATUS_DRAFT  # noqa: E402
from core.sales_query_service import SalesQueryService  # noqa: E402
from test_auction_candidate_service import TRADE_DT, _row  # noqa: E402
from test_auction_finalize_service import (  # noqa: E402
    FARM,
    FARM2,
    _disc,
    _open_finalize,
)
from test_auction_ship_service import _insert_stock, _payload  # noqa: E402


_CASH_DDL = """
DROP TABLE IF EXISTS t_cash_ledger;
CREATE TABLE t_cash_ledger (
    paid_detail_no TEXT, sales_no TEXT, farm_cd TEXT, pay_dt TEXT,
    pay_method_cd TEXT, pay_amt REAL, rmk TEXT, reg_id TEXT, reg_dt TEXT,
    slip_no TEXT, order_no TEXT
);
"""


class AuctionCorrectionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_finalize()
        self.conn.executescript(_CASH_DDL)
        self.conn.commit()
        self.settlement_rows: list[dict] = []
        self.realtime_rows: list[dict] = []

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _finalize_svc(self) -> AuctionFinalizeService:
        return AuctionFinalizeService(
            self.conn,
            settlement_fetch=lambda *_: list(self.settlement_rows),
            realtime_fetch=lambda *_: list(self.realtime_rows),
        )

    def _corr(self) -> AuctionCorrectionService:
        return AuctionCorrectionService(self.conn)

    def _ship(self, qty: float = 2) -> str:
        _insert_stock(
            self.conn,
            storage_dt="2026-08-28",
            in_qty=20,
            stock_seq=202,
        )
        return str(AuctionShipService(self.conn).create_shipment(_payload(qty))["shipment_id"])

    def _lookup(self, sid: str) -> dict:
        return AuctionCandidateService(
            self.conn,
            settlement_fetch=lambda *_: list(self.settlement_rows),
            realtime_fetch=lambda *_: list(self.realtime_rows),
        ).list_candidates(FARM, sid, TRADE_DT)

    def _complete(
        self,
        qty: int = 2,
        *,
        matched_qty: int | None = None,
        discrepancies: list[AuctionDiscrepancyIn] | None = None,
    ) -> tuple[str, str, str]:
        sid = self._ship(qty)
        matched = qty if matched_qty is None else matched_qty
        self.settlement_rows = [_row(qty=matched, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        out = self._finalize_svc().finalize(
            AuctionFinalizeIn(
                farm_cd=FARM,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=[AuctionSelectedIn(key)],
                discrepancies=discrepancies or (),
                user_id="TEST",
            )
        )
        return sid, str(out["sales_no"]), str(key)

    def _reopen(self, sid: str, remark: str | None = None) -> dict:
        return self._corr().reopen(
            AuctionCorrectionIn(
                farm_cd=FARM,
                shipment_id=sid,
                user_id="TEST",
                remark=remark,
            )
        )

    def _stock(self) -> tuple[float, float, float]:
        row = self.conn.execute(
            "SELECT in_qty, out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=202"
        ).fetchone()
        return float(row["in_qty"]), float(row["out_qty"]), float(row["reserved_qty"])

    def _log_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0])

    def test_reopen_happy_path(self) -> None:
        sid, sales_no, key = self._complete()
        self.conn.execute(
            "UPDATE t_sales_master SET rmk = ? WHERE sales_no = ? AND farm_cd = ?",
            ("기존메모", sales_no, FARM),
        )
        self.conn.commit()
        stock_before = self._stock()
        log_before = self._log_count()
        detail_before = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_sales_detail WHERE farm_cd=? AND sales_no=?",
                (FARM, sales_no),
            ).fetchone()[0]
        )
        out = self._reopen(sid, remark="사용자입력")
        self.assertEqual(out["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertIsNone(out["sales_no"])
        self.assertEqual(out["cancelled_sales_no"], sales_no)
        ship = self.conn.execute(
            "SELECT status, sales_no, match_trade_dt FROM t_auction_ship_master WHERE shipment_id=?",
            (sid,),
        ).fetchone()
        self.assertEqual(ship["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertIsNone(ship["sales_no"])
        self.assertIsNone(ship["match_trade_dt"])
        master = self.conn.execute(
            "SELECT sales_status, rmk FROM t_sales_master WHERE sales_no=? AND farm_cd=?",
            (sales_no, FARM),
        ).fetchone()
        self.assertEqual(master["sales_status"], SALES_STATUS_CANCELLED)
        self.assertEqual(
            master["rmk"],
            f"기존메모 | {MSG_REMARK_AUCTION_CORRECTION} | 사용자입력",
        )
        self.assertEqual(
            int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM t_sales_detail WHERE farm_cd=? AND sales_no=?",
                    (FARM, sales_no),
                ).fetchone()[0]
            ),
            detail_before,
        )
        self.assertEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE shipment_id=? AND is_valid=1",
                    (sid,),
                ).fetchone()[0]
            ),
            0,
        )
        self.assertGreaterEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE shipment_id=? AND is_valid=0",
                    (sid,),
                ).fetchone()[0]
            ),
            1,
        )
        self.assertEqual(self._stock(), stock_before)
        self.assertEqual(self._log_count(), log_before)
        self.assertTrue(has_auction_match_history(self.conn.cursor(), sid))
        self.assertFalse(auction_cancel_allowed(AUCTION_SHIP_STATUS_IN_TRANSIT, has_match_history=True))

    def test_reopen_invalidates_discrepancy(self) -> None:
        sid, _, _ = self._complete(
            qty=2,
            matched_qty=1,
            discrepancies=[_disc(reason=REASON_QTY_ERROR)],
        )
        self.assertGreaterEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_QTY_DISCREPANCY} WHERE shipment_id=? AND is_valid=1",
                    (sid,),
                ).fetchone()[0]
            ),
            1,
        )
        self._reopen(sid)
        self.assertEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_QTY_DISCREPANCY} WHERE shipment_id=? AND is_valid=1",
                    (sid,),
                ).fetchone()[0]
            ),
            0,
        )
        self.assertGreaterEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_QTY_DISCREPANCY} WHERE shipment_id=? AND is_valid=0",
                    (sid,),
                ).fetchone()[0]
            ),
            1,
        )

    def test_source_key_reuse_and_new_sales_no(self) -> None:
        sid, old_no, key = self._complete()
        self._reopen(sid)
        out = self._finalize_svc().finalize(
            AuctionFinalizeIn(
                farm_cd=FARM,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=[AuctionSelectedIn(key)],
                user_id="TEST",
            )
        )
        new_no = str(out["sales_no"])
        self.assertNotEqual(new_no, old_no)
        old = self.conn.execute(
            "SELECT sales_status FROM t_sales_master WHERE sales_no=? AND farm_cd=?",
            (old_no, FARM),
        ).fetchone()
        new = self.conn.execute(
            "SELECT sales_status, sales_source FROM t_sales_master WHERE sales_no=? AND farm_cd=?",
            (new_no, FARM),
        ).fetchone()
        self.assertEqual(old["sales_status"], SALES_STATUS_CANCELLED)
        self.assertEqual(new["sales_status"], SALES_STATUS_CONFIRMED)
        self.assertEqual(new["sales_source"], SALES_SOURCE_AUCTION)
        active = self.conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE source_key=? AND is_valid=1",
            (key,),
        ).fetchone()[0]
        self.assertEqual(int(active), 1)

    def test_return_rejects(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._finalize_svc().finalize(
            AuctionFinalizeIn(
                farm_cd=FARM,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=[AuctionSelectedIn(key)],
                discrepancies=[_disc(reason=REASON_RETURN, return_confirmed=True)],
                user_id="TEST",
            )
        )
        n_ret = int(
            self.conn.execute(
                f"SELECT COUNT(*) FROM {TABLE_AUCTION_RETURN_LINE} WHERE shipment_id=? AND is_valid=1",
                (sid,),
            ).fetchone()[0]
        )
        self.assertGreaterEqual(n_ret, 1)
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._reopen(sid)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CORRECTION_RETURN)
        self.assertEqual(
            self.conn.execute(
                "SELECT status FROM t_auction_ship_master WHERE shipment_id=?",
                (sid,),
            ).fetchone()[0],
            AUCTION_SHIP_STATUS_COMPLETED,
        )

    def test_payment_rejects(self) -> None:
        sid, sales_no, _ = self._complete()
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger (paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt)
            VALUES ('P01', ?, ?, '2026-09-02', 'AS010101', 1000)
            """,
            (sales_no, FARM),
        )
        self.conn.commit()
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._reopen(sid)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CORRECTION_PAYMENT)

    def test_partial_payment_rejects(self) -> None:
        sid, sales_no, _ = self._complete()
        tot = float(
            self.conn.execute(
                "SELECT tot_sales_amt FROM t_sales_master WHERE sales_no=?",
                (sales_no,),
            ).fetchone()[0]
        )
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger (paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt)
            VALUES ('P01', ?, ?, '2026-09-02', 'AS010101', ?)
            """,
            (sales_no, FARM, tot / 2),
        )
        self.conn.commit()
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._reopen(sid)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CORRECTION_PAYMENT)

    def test_non_auction_and_draft_reject(self) -> None:
        sid, sales_no, _ = self._complete()
        self.conn.execute(
            "UPDATE t_sales_master SET sales_source=? WHERE sales_no=?",
            (SALES_SOURCE_ORDER, sales_no),
        )
        self.conn.commit()
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._reopen(sid)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CORRECTION_SALES)
        self.conn.execute(
            "UPDATE t_sales_master SET sales_source=?, sales_status=? WHERE sales_no=?",
            (SALES_SOURCE_AUCTION, SALES_STATUS_DRAFT, sales_no),
        )
        self.conn.commit()
        with self.assertRaises(AuctionCorrectionError) as ctx2:
            self._reopen(sid)
        self.assertEqual(ctx2.exception.code, CODE_AUCTION_CORRECTION_SALES)

    def test_no_active_match_reject(self) -> None:
        sid, _, _ = self._complete()
        self.conn.execute(
            f"UPDATE {TABLE_AUCTION_MATCH_DETAIL} SET is_valid=0 WHERE shipment_id=?",
            (sid,),
        )
        self.conn.commit()
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._reopen(sid)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CORRECTION_MATCH)

    def test_double_reopen_reject(self) -> None:
        sid, _, _ = self._complete()
        self._reopen(sid)
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._reopen(sid)
        self.assertEqual(ctx.exception.code, CODE_AUCTION_CORRECTION_STATUS)

    def test_other_farm_reject(self) -> None:
        sid, _, _ = self._complete()
        with self.assertRaises(AuctionCorrectionError) as ctx:
            self._corr().reopen(
                AuctionCorrectionIn(farm_cd=FARM2, shipment_id=sid, user_id="TEST")
            )
        self.assertEqual(ctx.exception.code, CODE_AUCTION_SHIP_NOT_FOUND)

    def test_reopen_then_cancel_rejected(self) -> None:
        sid, _, _ = self._complete()
        stock_before = self._stock()
        log_before = self._log_count()
        self._reopen(sid)
        with self.assertRaises(AuctionShipError) as ctx:
            AuctionShipService(self.conn).cancel_shipment(FARM, sid, user_id="TEST")
        self.assertEqual(ctx.exception.code, CODE_AUCTION_SHIP_CANCEL_MATCHED)
        self.assertEqual(self._stock(), stock_before)
        self.assertEqual(self._log_count(), log_before)
        status = self.conn.execute(
            "SELECT status FROM t_auction_ship_master WHERE shipment_id=?",
            (sid,),
        ).fetchone()[0]
        self.assertEqual(status, AUCTION_SHIP_STATUS_IN_TRANSIT)

    def test_never_matched_cancel_ok(self) -> None:
        sid = self._ship(2)
        cancelled = AuctionShipService(self.conn).cancel_shipment(FARM, sid, user_id="TEST")
        self.assertEqual(cancelled["status"], AUCTION_SHIP_STATUS_CANCELLED)
        self.assertAlmostEqual(self._stock()[1], 0.0)

    def test_cancelled_excluded_from_list_and_totals(self) -> None:
        sid, old_no, key = self._complete()
        self.conn.execute(
            """
            INSERT INTO t_sales_master (
                sales_no, farm_cd, sales_dt, tot_sales_amt, tot_ship_fee, tot_item_amt,
                tot_paid_amt, tot_unpaid_amt, sales_status, sales_source
            ) VALUES ('20260901-99', ?, ?, 50000, 0, 50000, 0, 50000, ?, ?)
            """,
            (FARM, TRADE_DT, SALES_STATUS_CONFIRMED, SALES_SOURCE_ORDER),
        )
        self.conn.commit()
        self._reopen(sid)
        out = self._finalize_svc().finalize(
            AuctionFinalizeIn(
                farm_cd=FARM,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=[AuctionSelectedIn(key)],
                user_id="TEST",
            )
        )
        new_no = str(out["sales_no"])
        q = SalesQueryService(self.conn)
        listed = {row["sales_no"] for row in q.list_sales(FARM, from_date=TRADE_DT, to_date=TRADE_DT)["items"]}
        self.assertNotIn(old_no, listed)
        self.assertIn(new_no, listed)
        self.assertIn("20260901-99", listed)
        detail = q.get_sale_detail(FARM, old_no)
        self.assertEqual(detail["sales_status"], SALES_STATUS_CANCELLED)
        unpaid = q.sum_active_unpaid_amt(FARM)
        old_unpaid = float(
            self.conn.execute(
                "SELECT tot_unpaid_amt FROM t_sales_master WHERE sales_no=?",
                (old_no,),
            ).fetchone()[0]
        )
        new_unpaid = float(
            self.conn.execute(
                "SELECT tot_unpaid_amt FROM t_sales_master WHERE sales_no=?",
                (new_no,),
            ).fetchone()[0]
        )
        self.assertAlmostEqual(unpaid, 50000 + new_unpaid)
        self.assertGreater(old_unpaid, 0)
        sales_sum = q.sum_active_sales_amt(FARM, sales_dt=TRADE_DT)
        new_amt = float(
            self.conn.execute(
                "SELECT tot_sales_amt FROM t_sales_master WHERE sales_no=?",
                (new_no,),
            ).fetchone()[0]
        )
        self.assertAlmostEqual(sales_sum, 50000 + new_amt)

    def test_rollback_after_sales_cancel(self) -> None:
        sid, sales_no, _ = self._complete()
        with patch.object(
            AuctionCorrectionService,
            "_invalidate_matches",
            side_effect=RuntimeError("after-sales"),
        ):
            with self.assertRaises(RuntimeError):
                self._reopen(sid)
        self._assert_completed_untouched(sid, sales_no)

    def test_rollback_after_match_invalidate(self) -> None:
        sid, sales_no, _ = self._complete()
        with patch.object(
            AuctionCorrectionService,
            "_invalidate_discrepancies",
            side_effect=RuntimeError("after-match"),
        ):
            with self.assertRaises(RuntimeError):
                self._reopen(sid)
        self._assert_completed_untouched(sid, sales_no)

    def test_rollback_after_disc_invalidate(self) -> None:
        sid, sales_no, _ = self._complete()
        with patch.object(
            AuctionCorrectionService,
            "_reopen_shipment",
            side_effect=RuntimeError("after-disc"),
        ):
            with self.assertRaises(RuntimeError):
                self._reopen(sid)
        self._assert_completed_untouched(sid, sales_no)

    def test_rollback_after_shipment_update(self) -> None:
        sid, sales_no, _ = self._complete()
        with patch.object(
            AuctionCorrectionService,
            "_assert_invariants",
            side_effect=RuntimeError("after-ship"),
        ):
            with self.assertRaises(RuntimeError):
                self._reopen(sid)
        self._assert_completed_untouched(sid, sales_no)

    def _assert_completed_untouched(self, sid: str, sales_no: str) -> None:
        ship = self.conn.execute(
            "SELECT status, sales_no FROM t_auction_ship_master WHERE shipment_id=?",
            (sid,),
        ).fetchone()
        self.assertEqual(ship["status"], AUCTION_SHIP_STATUS_COMPLETED)
        self.assertEqual(str(ship["sales_no"]), sales_no)
        master = self.conn.execute(
            "SELECT sales_status FROM t_sales_master WHERE sales_no=?",
            (sales_no,),
        ).fetchone()
        self.assertEqual(master["sales_status"], SALES_STATUS_CONFIRMED)
        self.assertGreaterEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE shipment_id=? AND is_valid=1",
                    (sid,),
                ).fetchone()[0]
            ),
            1,
        )
        out_logs = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_stock_log WHERE ref_type=? AND io_type=? AND ref_id=?",
                (REF_TYPE_AUCTION_SHIP, IO_TYPE_OUT, sid),
            ).fetchone()[0]
        )
        self.assertEqual(out_logs, 1)

    def test_permissions_never_matched_in_transit(self) -> None:
        sid = self._ship(2)
        p = self._corr().get_action_permissions(FARM, sid)
        self.assertTrue(p["cancel_allowed"])
        self.assertFalse(p["reopen_allowed"])

    def test_permissions_completed_and_reopened(self) -> None:
        sid, _, _ = self._complete()
        p = self._corr().get_action_permissions(FARM, sid)
        self.assertFalse(p["cancel_allowed"])
        self.assertTrue(p["reopen_allowed"])
        self._reopen(sid)
        p2 = self._corr().get_action_permissions(FARM, sid)
        self.assertFalse(p2["cancel_allowed"])
        self.assertFalse(p2["reopen_allowed"])

    def test_permissions_cancelled(self) -> None:
        sid = self._ship(2)
        AuctionShipService(self.conn).cancel_shipment(FARM, sid, user_id="TEST")
        p = self._corr().get_action_permissions(FARM, sid)
        self.assertFalse(p["cancel_allowed"])
        self.assertFalse(p["reopen_allowed"])

    def test_permissions_return_blocks_reopen(self) -> None:
        sid = self._ship(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup(sid)["items"][0]["source_key"]
        self._finalize_svc().finalize(
            AuctionFinalizeIn(
                farm_cd=FARM,
                shipment_id=sid,
                trade_dt=TRADE_DT,
                selected=[AuctionSelectedIn(key)],
                discrepancies=[_disc(reason=REASON_RETURN, return_confirmed=True)],
                user_id="TEST",
            )
        )
        p = self._corr().get_action_permissions(FARM, sid)
        self.assertFalse(p["cancel_allowed"])
        self.assertFalse(p["reopen_allowed"])

    def test_permissions_payment_blocks_reopen(self) -> None:
        sid, sales_no, _ = self._complete()
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger (paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt)
            VALUES ('P01', ?, ?, '2026-09-02', 'AS010101', 1000)
            """,
            (sales_no, FARM),
        )
        self.conn.commit()
        p = self._corr().get_action_permissions(FARM, sid)
        self.assertFalse(p["cancel_allowed"])
        self.assertFalse(p["reopen_allowed"])


if __name__ == "__main__":
    unittest.main()
