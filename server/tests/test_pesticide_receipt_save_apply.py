# -*- coding: utf-8 -*-
"""입고 저장=재고반영 · 수정/삭제 역분개 · 사전 info_id 연결."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SERVER = _REPO / "server"
for p in (_SERVER, _REPO):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from app.services.pesticide_service import PesticideService  # noqa: E402
from app.schemas.pesticide_ext import (  # noqa: E402
    PesticideReceiptLineDto,
    PesticideReceiptSaveRequest,
)


def _build_tmp_db() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE m_farm_info (
            farm_cd TEXT PRIMARY KEY, farm_nm TEXT
        );
        INSERT INTO m_farm_info VALUES ('OR001', '테스트농장');

        CREATE TABLE m_pesticide_info (
            info_id INTEGER PRIMARY KEY,
            pesticide_nm TEXT,
            ingredient_nm TEXT,
            maker_nm TEXT,
            category_nm TEXT,
            brand_nm TEXT,
            use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO m_pesticide_info VALUES
          (10, '빅카드', '플루피라디퓨론', '바이엘', '살충제', '빅카드', 'Y');

        CREATE TABLE m_pesticide_item (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT NOT NULL,
            item_nm TEXT NOT NULL,
            spec_nm TEXT,
            pest_category_nm TEXT DEFAULT '',
            qty_box INTEGER DEFAULT 0,
            qty_piece INTEGER NOT NULL DEFAULT 0,
            warn_piece_below INTEGER,
            sort_ord INTEGER DEFAULT 0,
            use_yn TEXT DEFAULT 'Y',
            rmk TEXT,
            info_id INTEGER,
            mod_id TEXT,
            mod_dt TEXT,
            reg_id TEXT,
            reg_dt TEXT
        );

        CREATE TABLE t_pesticide_receipt (
            receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT NOT NULL,
            receipt_dt TEXT NOT NULL,
            supplier_id INTEGER,
            supplier_nm_text TEXT,
            recipient_nm TEXT,
            rmk TEXT,
            stock_applied_yn TEXT NOT NULL DEFAULT 'N',
            stock_applied_dt TEXT,
            stock_applied_by TEXT,
            reg_id TEXT,
            reg_dt TEXT,
            mod_id TEXT,
            mod_dt TEXT
        );

        CREATE TABLE t_pesticide_receipt_line (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER NOT NULL,
            line_no INTEGER NOT NULL DEFAULT 1,
            link_item_id INTEGER,
            info_id INTEGER,
            item_nm TEXT NOT NULL,
            spec_nm TEXT,
            qty INTEGER NOT NULL DEFAULT 0,
            unit_price REAL,
            supply_amt REAL,
            tax_amt REAL,
            line_rmk TEXT,
            checked_yn TEXT NOT NULL DEFAULT 'N'
        );

        CREATE TABLE t_pesticide_stock_hist (
            hist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_cd TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            trans_type TEXT NOT NULL,
            ref_table TEXT,
            ref_id INTEGER,
            ref_line_id INTEGER,
            qty_delta INTEGER NOT NULL,
            qty_after INTEGER,
            trans_dt TEXT,
            rmk TEXT,
            reg_id TEXT,
            reg_dt TEXT
        );

        CREATE TABLE m_pesticide_supplier (
            supplier_id INTEGER PRIMARY KEY,
            farm_cd TEXT,
            supplier_nm TEXT,
            use_yn TEXT DEFAULT 'Y'
        );
        """
    )
    conn.commit()
    conn.close()
    return path


class ReceiptSaveApplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()
        self.svc = PesticideService(self.db)

    def tearDown(self) -> None:
        try:
            self.db.unlink(missing_ok=True)
        except OSError:
            pass

    def _qty(self, item_nm: str) -> tuple[int, str, int | None]:
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT qty_piece, pest_category_nm, info_id
            FROM m_pesticide_item
            WHERE farm_cd='OR001' AND item_nm=? AND use_yn='Y'
            """,
            (item_nm,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        return (
            int(row["qty_piece"]),
            str(row["pest_category_nm"] or ""),
            int(row["info_id"]) if row["info_id"] is not None else None,
        )

    def test_save_applies_stock_with_info_category(self) -> None:
        res = self.svc.save_receipt(
            "OR001",
            PesticideReceiptSaveRequest(
                receipt_dt="2026-07-26",
                lines=[
                    PesticideReceiptLineDto(
                        item_nm="빅카드",
                        spec_nm="250ml",
                        qty=15,
                        info_id=10,
                    )
                ],
            ),
            user_id="u1",
        )
        qty, cat, iid = self._qty("빅카드")
        self.assertEqual(qty, 15)
        self.assertEqual(cat, "살충제")
        self.assertEqual(iid, 10)
        detail = self.svc.get_receipt_detail("OR001", res.receipt_id)
        self.assertEqual(detail.stock_applied_yn, "Y")
        self.assertEqual(detail.lines[0].info_id, 10)

    def test_update_after_apply_adjusts_qty(self) -> None:
        created = self.svc.save_receipt(
            "OR001",
            PesticideReceiptSaveRequest(
                receipt_dt="2026-07-26",
                lines=[
                    PesticideReceiptLineDto(
                        item_nm="빅카드", qty=15, info_id=10
                    )
                ],
            ),
            user_id="u1",
        )
        detail = self.svc.get_receipt_detail("OR001", created.receipt_id)
        link_id = detail.lines[0].link_item_id
        self.svc.save_receipt(
            "OR001",
            PesticideReceiptSaveRequest(
                receipt_dt="2026-07-26",
                lines=[
                    PesticideReceiptLineDto(
                        item_nm="빅카드",
                        qty=20,
                        info_id=10,
                        link_item_id=link_id,
                    )
                ],
            ),
            receipt_id=created.receipt_id,
            user_id="u1",
        )
        qty, cat, _ = self._qty("빅카드")
        self.assertEqual(qty, 20)
        self.assertEqual(cat, "살충제")

    def test_delete_after_apply_reverses_stock(self) -> None:
        created = self.svc.save_receipt(
            "OR001",
            PesticideReceiptSaveRequest(
                receipt_dt="2026-07-26",
                lines=[
                    PesticideReceiptLineDto(
                        item_nm="빅카드", qty=15, info_id=10
                    )
                ],
            ),
            user_id="u1",
        )
        self.svc.delete_receipt("OR001", created.receipt_id, user_id="u1")
        qty, _, _ = self._qty("빅카드")
        self.assertEqual(qty, 0)


if __name__ == "__main__":
    unittest.main()
