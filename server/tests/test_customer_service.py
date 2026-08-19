# -*- coding: utf-8 -*-
"""고객 등록 — m_customer SSOT (PC 주문 팝업과 동일)."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_SERVER = _HERE.parents[1]
_ROOT = _HERE.parents[2]
for p in (_SERVER, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from core.customer_service import (  # noqa: E402
    CustomerService,
    CustomerValidationError,
    generate_custm_id,
)
from core.order_constants import CUSTOMER_ID_PREFIX, CUSTOMER_TP_CD  # noqa: E402
from test_order_service import _open_tmp  # noqa: E402


FARM = "OR001"


class CustomerServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path, self.conn = _open_tmp()

    def tearDown(self) -> None:
        self.conn.close()
        self.path.unlink(missing_ok=True)

    def test_create_customer_pc_ssot(self) -> None:
        row = CustomerService(self.conn).create_customer(
            FARM,
            custm_nm="홍길동",
            mobile="010-1111-2222",
            addr1="경기",
            addr2="1층",
            rmk="단골",
            user_id="PC",
        )
        self.assertTrue(str(row["custm_id"]).startswith(CUSTOMER_ID_PREFIX))
        self.assertEqual(len(row["custm_id"]), 1 + 12)
        saved = self.conn.execute(
            "SELECT custm_nm, mobile, addr1, addr2, custm_tp, use_yn FROM m_customer WHERE custm_id = ?",
            (row["custm_id"],),
        ).fetchone()
        self.assertEqual(saved["custm_nm"], "홍길동")
        self.assertEqual(saved["mobile"], "010-1111-2222")
        self.assertEqual(saved["addr1"], "경기")
        self.assertEqual(saved["custm_tp"], CUSTOMER_TP_CD)
        self.assertEqual(saved["use_yn"], "Y")

    def test_create_requires_name_and_mobile(self) -> None:
        with self.assertRaises(CustomerValidationError):
            CustomerService(self.conn).create_customer(
                FARM, custm_nm="", mobile="010-0000-0000"
            )

    def test_generate_custm_id_prefix(self) -> None:
        cid = generate_custm_id()
        self.assertTrue(cid.startswith(CUSTOMER_ID_PREFIX))
        self.assertEqual(len(cid), 13)


if __name__ == "__main__":
    unittest.main()
