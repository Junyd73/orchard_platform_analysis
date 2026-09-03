# -*- coding: utf-8 -*-
"""DEC-037 Stage D — auction shipment detail/cancel/finalize REST."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_HERE.parent, _ROOT, _SERVER):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

_fd, _SETTINGS_SQLITE = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SQLITE_DB_PATH", _SETTINGS_SQLITE)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.dependencies import (  # noqa: E402
    get_auction_candidate_api_service,
    get_auction_finalize_api_service,
    get_auction_ship_api_service,
    get_sales_api_service,
)
from app.main import app  # noqa: E402
from app.services.auction_candidate_api_service import AuctionCandidateApiService  # noqa: E402
from app.services.auction_finalize_api_service import AuctionFinalizeApiService  # noqa: E402
from app.services.auction_ship_api_service import AuctionShipApiService  # noqa: E402
from app.services.sales_api_service import SalesApiService  # noqa: E402
from core.auction_candidate_constants import (  # noqa: E402
    CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE,
    CODE_AUCTION_CANDIDATE_STALE,
    SOURCE_REALTIME,
)
from core.auction_match_constants import (  # noqa: E402
    CODE_AUCTION_MATCH_DISCREPANCY,
    CODE_AUCTION_MATCH_DUPLICATE_SOURCE,
    CODE_AUCTION_MATCH_GRADE,
    CODE_AUCTION_MATCH_STATUS,
    CODE_AUCTION_MATCH_UNRESOLVED,
    REASON_OTHER,
    REASON_RETURN,
    SALES_SOURCE_AUCTION,
)
from core.auction_ship_constants import (  # noqa: E402
    AUCTION_SHIP_STATUS_CANCELLED,
    AUCTION_SHIP_STATUS_COMPLETED,
    AUCTION_SHIP_STATUS_IN_TRANSIT,
    CODE_AUCTION_SHIP_CANCEL_STATUS,
    CODE_AUCTION_SHIP_LIST_STATUS,
    CODE_AUCTION_SHIP_NOT_FOUND,
    CODE_AUCTION_SHIP_STOCK_LOG_MISMATCH,
    IO_TYPE_IN,
    IO_TYPE_OUT,
    REF_TYPE_AUCTION_SHIP,
)
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from core.sales_query_service import SalesQueryService  # noqa: E402
from test_auction_candidate_service import (  # noqa: E402
    CORP,
    FARM,
    MARKET_CD,
    TRADE_DT,
    _ensure_farm,
    _row,
)
from test_auction_finalize_service import FARM2, _open_finalize  # noqa: E402
from test_auction_ship_service import (  # noqa: E402
    GRADE,
    ITEM,
    SIZE,
    VARIETY,
    WEIGHT,
    YEAR,
    _insert_stock,
    _spec_line,
)
from core.auction_ship_service import AuctionShipCreateIn, AuctionShipService  # noqa: E402

OTHER_FARM = "OR999"
_INTERNAL_KEYS = ("stock_seq", "match_seq", "discrepancy_seq", "return_seq", "sale_detail_no")


def _base(farm: str = FARM) -> str:
    return f"/api/v1/farms/{farm}/auction-shipments"


class AuctionCompleteApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_finalize()
        _ensure_farm(self.conn)
        self.settlement_rows: list[dict] = []
        self.realtime_rows: list[dict] = []

        def settlement(*_a):
            return list(self.settlement_rows)

        def realtime(*_a):
            return list(self.realtime_rows)

        self.ship_svc = AuctionShipApiService(self.path)
        self.fin_svc = AuctionFinalizeApiService(
            self.path,
            settlement_fetch=settlement,
            realtime_fetch=realtime,
        )
        self.cand_svc = AuctionCandidateApiService(
            self.path,
            settlement_fetch=settlement,
            realtime_fetch=realtime,
        )
        app.dependency_overrides[get_auction_ship_api_service] = lambda: self.ship_svc
        app.dependency_overrides[get_auction_finalize_api_service] = lambda: self.fin_svc
        app.dependency_overrides[get_auction_candidate_api_service] = lambda: self.cand_svc
        app.dependency_overrides[get_sales_api_service] = lambda: SalesApiService(self.path)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for dep in (
            get_auction_ship_api_service,
            get_auction_finalize_api_service,
            get_auction_candidate_api_service,
            get_sales_api_service,
        ):
            app.dependency_overrides.pop(dep, None)
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def _create(self, qty: float = 2, *, stock_seq: int = 202) -> str:
        day = (int(stock_seq) % 27) + 1
        _insert_stock(
            self.conn,
            storage_dt=f"2026-08-{day:02d}",
            in_qty=20,
            stock_seq=stock_seq,
        )
        res = self.client.post(
            _base(),
            json={
                "ship_dt": "2026-08-31",
                "market_cd": MARKET_CD,
                "market_name": "서울가락",
                "corporation_name": CORP,
                "lines": [
                    {
                        "wh_cd": WAREHOUSE_CD_DEFAULT,
                        "item_cd": ITEM,
                        "variety_cd": VARIETY,
                        "grade_cd": GRADE,
                        "size_cd": SIZE,
                        "weight": WEIGHT,
                        "harvest_year": YEAR,
                        "qty": qty,
                    }
                ],
            },
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        return str(res.json()["shipment_id"])

    def _lookup_key(self, sid: str, farm: str = FARM) -> str:
        res = self.client.get(
            f"{_base(farm)}/{sid}/auction-candidates",
            params={"trade_dt": TRADE_DT},
        )
        self.assertEqual(res.status_code, 200, res.text)
        items = res.json()["items"]
        self.assertGreaterEqual(len(items), 1)
        return str(items[0]["source_key"])

    def _finalize_body(self, key: str, **extra) -> dict:
        body = {
            "trade_dt": TRADE_DT,
            "selected_candidates": [{"source_key": key}],
            "discrepancies": [],
        }
        body.update(extra)
        return body

    def _assert_no_internal(self, payload: object) -> None:
        dumped = json.dumps(payload)
        for key in _INTERNAL_KEYS:
            self.assertNotIn(key, dumped)

    def _stock(self, seq: int = 202) -> tuple[float, float, float]:
        row = self.conn.execute(
            "SELECT in_qty, out_qty, reserved_qty FROM t_stock_master WHERE stock_seq=?",
            (seq,),
        ).fetchone()
        return float(row[0]), float(row[1]), float(row[2])

    def _log_count(self, sid: str, io_type: str) -> int:
        return int(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM t_stock_log
                WHERE ref_type=? AND ref_id=? AND io_type=?
                """,
                (REF_TYPE_AUCTION_SHIP, sid, io_type),
            ).fetchone()[0]
        )

    def _sale_log_count(self, sales_no: str) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_stock_log WHERE ref_type=? AND ref_id=?",
                ("SALE", sales_no),
            ).fetchone()[0]
        )

    def _ship_other_farm(self, qty: float = 2) -> str:
        _ensure_farm(self.conn, farm=FARM2)
        for row in self.conn.execute(
            "SELECT code_cd, code_nm, parent_cd FROM m_common_code WHERE farm_cd=?",
            (FARM,),
        ):
            self.conn.execute(
                """
                INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd)
                VALUES (?, ?, ?, ?)
                """,
                (FARM2, row[0], row[1], row[2]),
            )
        self.conn.execute(
            """
            INSERT INTO t_stock_master (
                stock_seq, farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
                weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
            ) VALUES (302, ?, ?, ?, ?, ?, ?, ?, ?, '2026-08-28', 20, 0, 0, 'TEST')
            """,
            (FARM2, WAREHOUSE_CD_DEFAULT, ITEM, VARIETY, GRADE, SIZE, WEIGHT, YEAR),
        )
        self.conn.commit()
        return str(
            AuctionShipService(self.conn).create_shipment(
                AuctionShipCreateIn(
                    farm_cd=FARM2,
                    ship_dt="2026-08-30",
                    market_cd=MARKET_CD,
                    market_name="서울가락",
                    corporation_name=CORP,
                    lines=[_spec_line(qty)],
                    user_id="TEST",
                )
            )["shipment_id"]
        )

    def test_in_transit_detail_200(self) -> None:
        sid = self._create(2)
        res = self.client.get(f"{_base()}/{sid}")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertIsNone(body["sales_no"])
        self.assertAlmostEqual(body["total_shipped_qty"], 2.0)
        self.assertEqual(len(body["specs"]), 1)
        self.assertEqual(body["specs"][0]["variety_cd"], VARIETY)
        self._assert_no_internal(body)

    def test_completed_detail_and_sales_summary(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        fin = self.client.post(
            f"{_base()}/{sid}/finalize",
            json=self._finalize_body(key),
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(fin.status_code, 200, fin.text)
        out = fin.json()
        self.assertEqual(out["status"], AUCTION_SHIP_STATUS_COMPLETED)
        self.assertTrue(out["sales_no"])
        self.assertEqual(out["match_trade_dt"], TRADE_DT)
        self.assertEqual(out["gross_sales_amount"], 180000)
        self.assertEqual(out["total_sales_qty"], 2)
        self._assert_no_internal(out)
        res = self.client.get(f"{_base()}/{sid}")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_COMPLETED)
        self.assertEqual(body["sales_no"], out["sales_no"])
        self.assertEqual(body["gross_sales_amount"], 180000)
        spec = body["specs"][0]
        self.assertEqual(spec["matched_qty"], 2)
        self.assertEqual(spec["diff_qty"], 0)
        self._assert_no_internal(body)

    def test_cancelled_detail_200(self) -> None:
        sid = self._create(2)
        cancel = self.client.post(f"{_base()}/{sid}/cancel")
        self.assertEqual(cancel.status_code, 200, cancel.text)
        res = self.client.get(f"{_base()}/{sid}")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_CANCELLED)
        self.assertIsNone(body["sales_no"])
        self._assert_no_internal(body)

    def test_nonexistent_and_other_farm_404(self) -> None:
        sid = self._create(2)
        miss = self.client.get(f"{_base()}/AUC20990101-999")
        self.assertEqual(miss.status_code, 404)
        self.assertEqual(miss.json()["error_code"], CODE_AUCTION_SHIP_NOT_FOUND)
        other = self.client.get(f"{_base(OTHER_FARM)}/{sid}")
        self.assertEqual(other.status_code, 404)
        self.assertEqual(other.json()["error_code"], CODE_AUCTION_SHIP_NOT_FOUND)

    def test_list_status_filters(self) -> None:
        transit = self._create(2, stock_seq=201)
        done = self._create(2, stock_seq=202)
        cancelled = self._create(2, stock_seq=203)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(done)
        self.assertEqual(
            self.client.post(
                f"{_base()}/{done}/finalize",
                json=self._finalize_body(key),
            ).status_code,
            200,
        )
        self.assertEqual(self.client.post(f"{_base()}/{cancelled}/cancel").status_code, 200)

        default = self.client.get(_base())
        self.assertEqual(default.status_code, 200, default.text)
        ids = {i["shipment_id"] for i in default.json()["items"]}
        self.assertIn(transit, ids)
        self.assertNotIn(done, ids)
        self.assertNotIn(cancelled, ids)

        completed = self.client.get(_base(), params={"status": AUCTION_SHIP_STATUS_COMPLETED})
        self.assertEqual(completed.status_code, 200)
        citem = completed.json()["items"][0]
        self.assertEqual(citem["shipment_id"], done)
        self.assertTrue(citem["sales_no"])
        self.assertEqual(citem["match_trade_dt"], TRADE_DT)
        self.assertEqual(citem["gross_sales_amount"], 180000)
        self._assert_no_internal(citem)

        cancelled_list = self.client.get(_base(), params={"status": AUCTION_SHIP_STATUS_CANCELLED})
        self.assertEqual(cancelled_list.status_code, 200)
        kitem = cancelled_list.json()["items"][0]
        self.assertEqual(kitem["shipment_id"], cancelled)
        self.assertIsNone(kitem["sales_no"])

        bad = self.client.get(_base(), params={"status": "ALL"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error_code"], CODE_AUCTION_SHIP_LIST_STATUS)

    def test_cancel_success_restore_and_second_conflict(self) -> None:
        sid = self._create(2)
        before_in, before_out, before_rsv = self._stock()
        self.assertAlmostEqual(before_out, 2.0)
        res = self.client.post(f"{_base()}/{sid}/cancel", json={})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_CANCELLED)
        self.assertAlmostEqual(body["restored_qty"], 2.0)
        self._assert_no_internal(body)
        after_in, after_out, after_rsv = self._stock()
        self.assertAlmostEqual(after_in, before_in)
        self.assertAlmostEqual(after_out, 0.0)
        self.assertAlmostEqual(after_rsv, before_rsv)
        self.assertEqual(self._log_count(sid, IO_TYPE_IN), 1)
        second = self.client.post(f"{_base()}/{sid}/cancel")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["error_code"], CODE_AUCTION_SHIP_CANCEL_STATUS)
        self.assertEqual(self._log_count(sid, IO_TYPE_IN), 1)

    def test_completed_cancel_409(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        self.assertEqual(
            self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key)).status_code,
            200,
        )
        res = self.client.post(f"{_base()}/{sid}/cancel")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_CANCEL_STATUS)

    def test_cancel_log_mismatch_409(self) -> None:
        sid = self._create(2)
        self.conn.execute(
            """
            UPDATE t_stock_log SET qty = qty + 1
            WHERE ref_type=? AND io_type=? AND ref_id=?
            """,
            (REF_TYPE_AUCTION_SHIP, IO_TYPE_OUT, sid),
        )
        self.conn.commit()
        res = self.client.post(f"{_base()}/{sid}/cancel")
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_STOCK_LOG_MISMATCH)

    def test_cancel_other_farm_404(self) -> None:
        sid = self._create(2)
        res = self.client.post(f"{_base(OTHER_FARM)}/{sid}/cancel")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_NOT_FOUND)

    def test_finalize_rejects_client_price_fields(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        res = self.client.post(
            f"{_base()}/{sid}/finalize",
            json={
                "trade_dt": TRADE_DT,
                "selected_candidates": [
                    {"source_key": key, "qty": 99, "unit_price": 1, "amount": 1}
                ],
            },
        )
        self.assertEqual(res.status_code, 422)

    def test_stale_candidate_409(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        self.settlement_rows = [_row(qty=2, price=88000)]
        res = self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key))
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CANDIDATE_STALE)
        self.assertIn("경락정보가 변경되었습니다", res.json()["detail"])

    def test_second_finalize_409(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        self.assertEqual(
            self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key)).status_code,
            200,
        )
        res = self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key))
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_MATCH_STATUS)

    def test_same_farm_duplicate_source_409(self) -> None:
        sid1 = self._create(2, stock_seq=201)
        sid2 = self._create(2, stock_seq=202)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid1)
        self.assertEqual(
            self.client.post(f"{_base()}/{sid1}/finalize", json=self._finalize_body(key)).status_code,
            200,
        )
        res = self.client.post(f"{_base()}/{sid2}/finalize", json=self._finalize_body(key))
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_MATCH_DUPLICATE_SOURCE)

    def test_different_farm_duplicate_source_409(self) -> None:
        sid1 = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid1)
        self.assertEqual(
            self.client.post(f"{_base()}/{sid1}/finalize", json=self._finalize_body(key)).status_code,
            200,
        )
        sid2 = self._ship_other_farm(2)
        before_in, before_out, before_rsv = self._stock(302)
        match_before = int(
            self.conn.execute("SELECT COUNT(*) FROM t_auction_match_detail").fetchone()[0]
        )
        sales_before = int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0])
        res = self.client.post(
            f"{_base(FARM2)}/{sid2}/finalize",
            json=self._finalize_body(key),
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_MATCH_DUPLICATE_SOURCE)
        ship2 = self.conn.execute(
            "SELECT status, sales_no FROM t_auction_ship_master WHERE shipment_id=?",
            (sid2,),
        ).fetchone()
        self.assertEqual(str(ship2[0]), AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertFalse(str(ship2[1] or "").strip())
        after_in, after_out, after_rsv = self._stock(302)
        self.assertEqual((after_in, after_out, after_rsv), (before_in, before_out, before_rsv))
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_auction_match_detail").fetchone()[0]),
            match_before,
        )
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]),
            sales_before,
        )

    def test_invalid_realtime_grade(self) -> None:
        sid = self._create(2)
        self.settlement_rows = []
        self.realtime_rows = [_row(qty=2, price=90000, grade="", grade_cd="")]
        key = self._lookup_key(sid)
        res = self.client.post(
            f"{_base()}/{sid}/finalize",
            json={
                "trade_dt": TRADE_DT,
                "selected_candidates": [{"source_key": key, "user_grade_cd": "GR999999"}],
            },
        )
        self.assertEqual(res.status_code, 400, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_MATCH_GRADE)

    def test_unresolved_and_other_without_remark(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup_key(sid)
        unresolved = self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key))
        self.assertEqual(unresolved.status_code, 400)
        self.assertEqual(unresolved.json()["error_code"], CODE_AUCTION_MATCH_UNRESOLVED)
        other = self.client.post(
            f"{_base()}/{sid}/finalize",
            json=self._finalize_body(
                key,
                discrepancies=[
                    {
                        "variety_cd": VARIETY,
                        "grade_cd": GRADE,
                        "size_cd": SIZE,
                        "weight": WEIGHT,
                        "reason_cd": REASON_OTHER,
                    }
                ],
            ),
        )
        self.assertEqual(other.status_code, 400)
        self.assertEqual(other.json()["error_code"], CODE_AUCTION_MATCH_DISCREPANCY)

    def test_return_only_in_and_non_return_out_zero(self) -> None:
        sid = self._create(2)
        out_before = self._stock()[1]
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup_key(sid)
        res = self.client.post(
            f"{_base()}/{sid}/finalize",
            json=self._finalize_body(
                key,
                discrepancies=[
                    {
                        "variety_cd": VARIETY,
                        "grade_cd": GRADE,
                        "size_cd": SIZE,
                        "weight": WEIGHT,
                        "reason_cd": REASON_RETURN,
                        "return_confirmed": True,
                    }
                ],
            ),
        )
        self.assertEqual(res.status_code, 200, res.text)
        after_in, after_out, _rsv = self._stock()
        self.assertAlmostEqual(after_out, out_before)
        self.assertAlmostEqual(after_in, 21.0)
        self.assertEqual(self._log_count(sid, IO_TYPE_IN), 1)
        self.assertEqual(self._sale_log_count(res.json()["sales_no"]), 0)

    def test_non_return_no_extra_out_or_sale_log(self) -> None:
        sid = self._create(2)
        out_before = self._stock()[1]
        in_before = self._stock()[0]
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        res = self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key))
        self.assertEqual(res.status_code, 200, res.text)
        after_in, after_out, _rsv = self._stock()
        self.assertAlmostEqual(after_out, out_before)
        self.assertAlmostEqual(after_in, in_before)
        self.assertEqual(self._log_count(sid, IO_TYPE_OUT), 1)
        self.assertEqual(self._log_count(sid, IO_TYPE_IN), 0)
        self.assertEqual(self._sale_log_count(res.json()["sales_no"]), 0)

    def test_finalize_rollback(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup_key(sid)
        self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key))
        ship = self.conn.execute(
            "SELECT status, sales_no FROM t_auction_ship_master WHERE shipment_id=?",
            (sid,),
        ).fetchone()
        self.assertEqual(str(ship[0]), AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertFalse(str(ship[1] or "").strip())
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_auction_match_detail").fetchone()[0]),
            0,
        )
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]),
            0,
        )

    def test_source_error_502(self) -> None:
        sid = self._create(2)

        def boom(*_a):
            raise RuntimeError("settlement down")

        self.fin_svc._settlement_fetch = boom
        self.cand_svc._settlement_fetch = boom
        res = self.client.post(
            f"{_base()}/{sid}/finalize",
            json=self._finalize_body("deadkey"),
        )
        self.assertEqual(res.status_code, 502, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE)
        cand = self.client.get(
            f"{_base()}/{sid}/auction-candidates",
            params={"trade_dt": TRADE_DT},
        )
        self.assertEqual(cand.status_code, 502)
        self.assertEqual(cand.json()["error_code"], CODE_AUCTION_CANDIDATE_SETTLEMENT_SOURCE)

    def test_auction_sales_query_and_regressions(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        fin = self.client.post(f"{_base()}/{sid}/finalize", json=self._finalize_body(key))
        self.assertEqual(fin.status_code, 200, fin.text)
        sales_no = fin.json()["sales_no"]
        cash_cols = {str(r[1]) for r in self.conn.execute("PRAGMA table_info(t_cash_ledger)")}
        if "sales_no" not in cash_cols:
            self.conn.execute("ALTER TABLE t_cash_ledger ADD COLUMN sales_no TEXT")
        if "pay_amt" not in cash_cols:
            self.conn.execute("ALTER TABLE t_cash_ledger ADD COLUMN pay_amt REAL DEFAULT 0")
        if "pay_dt" not in cash_cols:
            self.conn.execute("ALTER TABLE t_cash_ledger ADD COLUMN pay_dt TEXT")
        if "pay_method_cd" not in cash_cols:
            self.conn.execute("ALTER TABLE t_cash_ledger ADD COLUMN pay_method_cd TEXT")
        self.conn.execute(
            """
            INSERT INTO t_sales_master (
                sales_no, farm_cd, sales_dt, sales_status, sales_source,
                custm_id, tot_sales_amt, tot_paid_amt, tot_unpaid_amt
            ) VALUES ('ORD-1', ?, '2026-08-01', 'CONFIRMED', 'ORDER', NULL, 50000, 0, 50000)
            """,
            (FARM,),
        )
        self.conn.execute(
            """
            INSERT INTO t_sales_master (
                sales_no, farm_cd, sales_dt, sales_status, sales_source,
                custm_id, tot_sales_amt, tot_paid_amt, tot_unpaid_amt
            ) VALUES ('DIR-1', ?, '2026-08-02', 'CONFIRMED', 'DIRECT', NULL, 30000, 0, 30000)
            """,
            (FARM,),
        )
        self.conn.commit()
        listed = SalesQueryService(self.conn).list_sales(FARM)
        sources = {i["sales_source"]: i for i in listed["items"]}
        self.assertIn(SALES_SOURCE_AUCTION, sources)
        self.assertEqual(sources[SALES_SOURCE_AUCTION]["sales_no"], sales_no)
        self.assertEqual(sources[SALES_SOURCE_AUCTION]["tot_sales_amt"], 180000)
        self.assertEqual(sources[SALES_SOURCE_AUCTION]["rep_weight"], 0.0)
        self.assertEqual(sources["ORDER"]["tot_sales_amt"], 50000)
        self.assertEqual(sources["DIRECT"]["tot_sales_amt"], 30000)
        detail = SalesQueryService(self.conn).get_sale_detail(FARM, sales_no)
        self.assertEqual(detail["sales_source"], SALES_SOURCE_AUCTION)
        self.assertEqual(detail["tot_sales_amt"], 180000)
        self.assertGreaterEqual(len(detail["lines"]), 1)
        line = detail["lines"][0]
        self.assertIsNone(line.get("stock_seq"))
        self.assertEqual(line["variety_cd"], VARIETY)
        api_list = self.client.get(f"/api/v1/farms/{FARM}/sales")
        self.assertEqual(api_list.status_code, 200, api_list.text)
        api_detail = self.client.get(f"/api/v1/farms/{FARM}/sales/{sales_no}")
        self.assertEqual(api_detail.status_code, 200, api_detail.text)
        self.assertEqual(api_detail.json()["sales_source"], SALES_SOURCE_AUCTION)

    def test_finalize_other_farm_404(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        res = self.client.post(
            f"{_base(OTHER_FARM)}/{sid}/finalize",
            json=self._finalize_body(key),
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
