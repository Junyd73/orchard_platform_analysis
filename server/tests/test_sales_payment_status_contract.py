# -*- coding: utf-8 -*-
"""Stage6-0 — 수금상태 계산 계약 (공통 helper)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.order_ship_constants import SALES_STATUS_CONFIRMED  # noqa: E402
from core.sales_payment_constants import (
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIAL,
    PAYMENT_STATUS_UNPAID,
    SALES_STATUS_DRAFT,
    compute_payment_status,
    compute_unpaid_amt,
)


class SalesPaymentStatusContractTest(unittest.TestCase):
    def test_a_confirmed_zero_total_zero_paid(self) -> None:
        self.assertEqual(
            compute_payment_status(SALES_STATUS_CONFIRMED, 0, 0),
            PAYMENT_STATUS_UNPAID,
        )
        self.assertEqual(compute_unpaid_amt(0, 0), 0.0)

    def test_b_confirmed_unpaid(self) -> None:
        self.assertEqual(
            compute_payment_status(SALES_STATUS_CONFIRMED, 100000, 0),
            PAYMENT_STATUS_UNPAID,
        )
        self.assertEqual(compute_unpaid_amt(100000, 0), 100000.0)

    def test_c_confirmed_partial(self) -> None:
        self.assertEqual(
            compute_payment_status(SALES_STATUS_CONFIRMED, 100000, 40000),
            PAYMENT_STATUS_PARTIAL,
        )
        self.assertEqual(compute_unpaid_amt(100000, 40000), 60000.0)

    def test_d_confirmed_paid(self) -> None:
        self.assertEqual(
            compute_payment_status(SALES_STATUS_CONFIRMED, 100000, 100000),
            PAYMENT_STATUS_PAID,
        )
        self.assertEqual(compute_unpaid_amt(100000, 100000), 0.0)

    def test_e_confirmed_overpay_legacy(self) -> None:
        self.assertEqual(
            compute_payment_status(SALES_STATUS_CONFIRMED, 100000, 120000),
            PAYMENT_STATUS_PAID,
        )
        self.assertEqual(compute_unpaid_amt(100000, 120000), 0.0)

    def test_f_draft_null(self) -> None:
        self.assertIsNone(
            compute_payment_status(SALES_STATUS_DRAFT, 100000, 0),
        )


if __name__ == "__main__":
    unittest.main()
