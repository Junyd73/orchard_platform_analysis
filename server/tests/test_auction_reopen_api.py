# -*- coding: utf-8 -*-
"""DEC-037 Stage F-2 — auction match reopen REST (temp SQLite + TestClient)."""

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
    get_auction_correction_api_service,
    get_auction_finalize_api_service,
    get_auction_ship_api_service,
    get_sales_api_service,
)
from app.main import app  # noqa: E402
from app.services.auction_candidate_api_service import AuctionCandidateApiService  # noqa: E402
from app.services.auction_correction_api_service import AuctionCorrectionApiService  # noqa: E402
from app.services.auction_finalize_api_service import AuctionFinalizeApiService  # noqa: E402
from app.services.auction_ship_api_service import AuctionShipApiService  # noqa: E402
from app.services.sales_api_service import SalesApiService  # noqa: E402
from core.auction_match_constants import (  # noqa: E402
    CODE_AUCTION_CORRECTION_MATCH,
    CODE_AUCTION_CORRECTION_PAYMENT,
    CODE_AUCTION_CORRECTION_RETURN,
    CODE_AUCTION_CORRECTION_SALES,
    CODE_AUCTION_CORRECTION_STATUS,
    MSG_AUCTION_CORRECTION_PAYMENT,
    MSG_AUCTION_CORRECTION_RETURN,
    REASON_RETURN,
    SALES_SOURCE_AUCTION,
    TABLE_AUCTION_MATCH_DETAIL,
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
from core.order_constants import WAREHOUSE_CD_DEFAULT  # noqa: E402
from core.order_ship_constants import (  # noqa: E402
    SALES_SOURCE_ORDER,
    SALES_STATUS_CANCELLED,
)
from core.sales_payment_constants import SALES_STATUS_DRAFT  # noqa: E402
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

_INTERNAL_KEYS = ("stock_seq", "match_seq", "discrepancy_seq", "return_seq", "sale_detail_no")
_CASH_DDL = """
DROP TABLE IF EXISTS t_cash_ledger;
CREATE TABLE t_cash_ledger (
    paid_detail_no TEXT, sales_no TEXT, farm_cd TEXT, pay_dt TEXT,
    pay_method_cd TEXT, pay_amt REAL, rmk TEXT, reg_id TEXT, reg_dt TEXT,
    slip_no TEXT, order_no TEXT
);
"""


def _base(farm: str = FARM) -> str:
    return f"/api/v1/farms/{farm}/auction-shipments"


class AuctionReopenApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_finalize()
        self.conn.executescript(_CASH_DDL)
        self.conn.commit()
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
        self.corr_svc = AuctionCorrectionApiService(self.path)
        app.dependency_overrides[get_auction_ship_api_service] = lambda: self.ship_svc
        app.dependency_overrides[get_auction_finalize_api_service] = lambda: self.fin_svc
        app.dependency_overrides[get_auction_candidate_api_service] = lambda: self.cand_svc
        app.dependency_overrides[get_auction_correction_api_service] = lambda: self.corr_svc
        app.dependency_overrides[get_sales_api_service] = lambda: SalesApiService(self.path)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for dep in (
            get_auction_ship_api_service,
            get_auction_finalize_api_service,
            get_auction_candidate_api_service,
            get_auction_correction_api_service,
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

    def _finalize(self, sid: str, key: str, **extra) -> dict:
        body = {
            "trade_dt": TRADE_DT,
            "selected_candidates": [{"source_key": key}],
            "discrepancies": [],
        }
        body.update(extra)
        res = self.client.post(
            f"{_base()}/{sid}/finalize",
            json=body,
            headers={"X-User-Id": "MOBILE"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def _complete(self, qty: float = 2, *, stock_seq: int = 202) -> tuple[str, str, str]:
        sid = self._create(qty, stock_seq=stock_seq)
        self.settlement_rows = [_row(qty=qty, price=90000)]
        key = self._lookup_key(sid)
        out = self._finalize(sid, key)
        return sid, str(out["sales_no"]), key

    def _reopen(self, sid: str, farm: str = FARM, **kwargs):
        return self.client.post(
            f"{_base(farm)}/{sid}/reopen",
            json=kwargs.get("json", {}),
            headers={"X-User-Id": "MOBILE"},
        )

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

    def _log_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM t_stock_log").fetchone()[0])

    def _flags(self, body: dict) -> tuple[bool, bool]:
        return bool(body["cancel_allowed"]), bool(body["reopen_allowed"])

    def test_completed_detail_reopen_allowed(self) -> None:
        sid, _, _ = self._complete()
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertEqual(self._flags(body), (False, True))
        listed = self.client.get(
            _base(), params={"status": AUCTION_SHIP_STATUS_COMPLETED}
        ).json()["items"][0]
        self.assertEqual(self._flags(listed), (False, True))
        self._assert_no_internal(body)
        self._assert_no_internal(listed)

    def test_completed_return_reopen_blocked(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=1, price=90000)]
        key = self._lookup_key(sid)
        self._finalize(
            sid,
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
        )
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertEqual(self._flags(body), (False, False))
        res = self._reopen(sid)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CORRECTION_RETURN)
        self.assertEqual(res.json()["detail"], MSG_AUCTION_CORRECTION_RETURN)

    def test_completed_payment_reopen_blocked(self) -> None:
        sid, sales_no, _ = self._complete()
        self.conn.execute(
            """
            INSERT INTO t_cash_ledger (paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt)
            VALUES ('P01', ?, ?, '2026-09-02', 'AS010101', 1000)
            """,
            (sales_no, FARM),
        )
        self.conn.commit()
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertEqual(self._flags(body), (False, False))
        res = self._reopen(sid)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CORRECTION_PAYMENT)
        self.assertEqual(res.json()["detail"], MSG_AUCTION_CORRECTION_PAYMENT)

    def test_partial_payment_reopen_blocked(self) -> None:
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
            VALUES ('P02', ?, ?, '2026-09-02', 'AS010101', ?)
            """,
            (sales_no, FARM, tot / 2),
        )
        self.conn.commit()
        res = self._reopen(sid)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CORRECTION_PAYMENT)

    def test_in_transit_never_matched_cancel_allowed(self) -> None:
        sid = self._create(2)
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertEqual(self._flags(body), (True, False))
        listed = self.client.get(_base()).json()["items"]
        item = next(i for i in listed if i["shipment_id"] == sid)
        self.assertEqual(self._flags(item), (True, False))
        cancel = self.client.post(f"{_base()}/{sid}/cancel")
        self.assertEqual(cancel.status_code, 200, cancel.text)
        self.assertEqual(cancel.json()["status"], AUCTION_SHIP_STATUS_CANCELLED)

    def test_in_transit_reopened_cancel_blocked(self) -> None:
        sid, _, _ = self._complete()
        self.assertEqual(self._reopen(sid).status_code, 200)
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertEqual(self._flags(body), (False, False))
        listed = self.client.get(_base()).json()["items"]
        item = next(i for i in listed if i["shipment_id"] == sid)
        self.assertEqual(self._flags(item), (False, False))
        stock_before = self._stock()
        log_before = self._log_count()
        res = self.client.post(f"{_base()}/{sid}/cancel")
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_SHIP_CANCEL_MATCHED)
        self.assertEqual(self._stock(), stock_before)
        self.assertEqual(self._log_count(), log_before)

    def test_cancelled_flags_false(self) -> None:
        sid = self._create(2)
        self.assertEqual(self.client.post(f"{_base()}/{sid}/cancel").status_code, 200)
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_CANCELLED)
        self.assertEqual(self._flags(body), (False, False))
        listed = self.client.get(
            _base(), params={"status": AUCTION_SHIP_STATUS_CANCELLED}
        ).json()["items"][0]
        self.assertEqual(self._flags(listed), (False, False))

    def test_reopen_success_and_sales_history(self) -> None:
        sid, sales_no, _ = self._complete()
        detail_before = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_sales_detail WHERE farm_cd=? AND sales_no=?",
                (FARM, sales_no),
            ).fetchone()[0]
        )
        stock_before = self._stock()
        log_before = self._log_count()
        res = self._reopen(sid, json={"remark": "테스트"})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["shipment_id"], sid)
        self.assertEqual(body["status"], AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertIsNone(body["sales_no"])
        self.assertIsNone(body["match_trade_dt"])
        self.assertEqual(body["cancelled_sales_no"], sales_no)
        self._assert_no_internal(body)
        ship = self.conn.execute(
            "SELECT status, sales_no, match_trade_dt FROM t_auction_ship_master WHERE shipment_id=?",
            (sid,),
        ).fetchone()
        self.assertEqual(str(ship[0]), AUCTION_SHIP_STATUS_IN_TRANSIT)
        self.assertFalse(str(ship[1] or "").strip())
        self.assertFalse(str(ship[2] or "").strip())
        master = self.conn.execute(
            "SELECT sales_status FROM t_sales_master WHERE sales_no=? AND farm_cd=?",
            (sales_no, FARM),
        ).fetchone()
        self.assertEqual(str(master[0]), SALES_STATUS_CANCELLED)
        self.assertEqual(
            int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM t_sales_detail WHERE farm_cd=? AND sales_no=?",
                    (FARM, sales_no),
                ).fetchone()[0]
            ),
            detail_before,
        )
        self.assertEqual(self._stock(), stock_before)
        self.assertEqual(self._log_count(), log_before)
        out_logs = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM t_stock_log WHERE ref_type=? AND io_type=? AND ref_id=?",
                (REF_TYPE_AUCTION_SHIP, IO_TYPE_OUT, sid),
            ).fetchone()[0]
        )
        self.assertEqual(out_logs, 1)

    def test_second_reopen_409(self) -> None:
        sid, sales_no, _ = self._complete()
        self.assertEqual(self._reopen(sid).status_code, 200)
        sales_cnt = int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0])
        invalid = int(
            self.conn.execute(
                f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE shipment_id=? AND is_valid=0",
                (sid,),
            ).fetchone()[0]
        )
        stock_before = self._stock()
        log_before = self._log_count()
        res = self._reopen(sid)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CORRECTION_STATUS)
        self.assertEqual(
            int(self.conn.execute("SELECT COUNT(*) FROM t_sales_master").fetchone()[0]),
            sales_cnt,
        )
        self.assertEqual(
            int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE shipment_id=? AND is_valid=0",
                    (sid,),
                ).fetchone()[0]
            ),
            invalid,
        )
        self.assertEqual(self._stock(), stock_before)
        self.assertEqual(self._log_count(), log_before)
        still = self.conn.execute(
            "SELECT sales_status FROM t_sales_master WHERE sales_no=?",
            (sales_no,),
        ).fetchone()
        self.assertEqual(str(still[0]), SALES_STATUS_CANCELLED)

    def test_wrong_farm_and_missing_404(self) -> None:
        sid, _, _ = self._complete()
        other = self._reopen(sid, farm=FARM2)
        self.assertEqual(other.status_code, 404, other.text)
        self.assertEqual(other.json()["error_code"], CODE_AUCTION_SHIP_NOT_FOUND)
        miss = self._reopen("AUC20990101-999")
        self.assertEqual(miss.status_code, 404)
        self.assertEqual(miss.json()["error_code"], CODE_AUCTION_SHIP_NOT_FOUND)

    def test_no_active_match_409(self) -> None:
        sid, _, _ = self._complete()
        self.conn.execute(
            f"UPDATE {TABLE_AUCTION_MATCH_DETAIL} SET is_valid=0 WHERE shipment_id=?",
            (sid,),
        )
        self.conn.commit()
        res = self._reopen(sid)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CORRECTION_MATCH)
        body = self.client.get(f"{_base()}/{sid}").json()
        self.assertFalse(body["reopen_allowed"])

    def test_non_auction_and_draft_sales_409(self) -> None:
        sid, sales_no, _ = self._complete()
        self.conn.execute(
            "UPDATE t_sales_master SET sales_source=? WHERE sales_no=?",
            (SALES_SOURCE_ORDER, sales_no),
        )
        self.conn.commit()
        res = self._reopen(sid)
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(res.json()["error_code"], CODE_AUCTION_CORRECTION_SALES)
        self.conn.execute(
            "UPDATE t_sales_master SET sales_source=?, sales_status=? WHERE sales_no=?",
            (SALES_SOURCE_AUCTION, SALES_STATUS_DRAFT, sales_no),
        )
        self.conn.commit()
        res2 = self._reopen(sid)
        self.assertEqual(res2.status_code, 409, res2.text)
        self.assertEqual(res2.json()["error_code"], CODE_AUCTION_CORRECTION_SALES)

    def test_source_key_reuse_after_reopen(self) -> None:
        sid, old_no, key = self._complete()
        self.assertEqual(self._reopen(sid).status_code, 200)
        out = self._finalize(sid, key)
        new_no = str(out["sales_no"])
        self.assertNotEqual(new_no, old_no)
        self.assertEqual(out["status"], AUCTION_SHIP_STATUS_COMPLETED)
        old = self.conn.execute(
            "SELECT sales_status FROM t_sales_master WHERE sales_no=? AND farm_cd=?",
            (old_no, FARM),
        ).fetchone()
        self.assertEqual(str(old[0]), SALES_STATUS_CANCELLED)
        active = int(
            self.conn.execute(
                f"SELECT COUNT(*) FROM {TABLE_AUCTION_MATCH_DETAIL} WHERE source_key=? AND is_valid=1",
                (key,),
            ).fetchone()[0]
        )
        self.assertEqual(active, 1)

    def test_existing_finalize_and_list_regression(self) -> None:
        sid = self._create(2)
        self.settlement_rows = [_row(qty=2, price=90000)]
        key = self._lookup_key(sid)
        out = self._finalize(sid, key)
        self.assertEqual(out["status"], AUCTION_SHIP_STATUS_COMPLETED)
        self._assert_no_internal(out)
        listed = self.client.get(
            _base(), params={"status": AUCTION_SHIP_STATUS_COMPLETED}
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        item = listed.json()["items"][0]
        self.assertEqual(item["shipment_id"], sid)
        self.assertEqual(item["sales_no"], out["sales_no"])
        self._assert_no_internal(item)


if __name__ == "__main__":
    unittest.main()
