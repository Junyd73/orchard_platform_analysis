# -*- coding: utf-8 -*-
"""농약 재고 API 서비스 테스트 — SCR-020."""

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

from app.core.exceptions import EntityNotFoundError  # noqa: E402
from app.services.pesticide_service import PesticideService  # noqa: E402
from core.pesticide_constants import PESTICIDE_DEFAULT_WARN_PIECE_BELOW  # noqa: E402


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
            spec_nm TEXT,
            dilution_guide TEXT,
            usage_note TEXT,
            caution_note TEXT,
            use_yn TEXT DEFAULT 'Y',
            rmk TEXT
        );
        INSERT INTO m_pesticide_info (
            info_id, pesticide_nm, ingredient_nm, maker_nm, use_yn
        ) VALUES
          (1, '공식살충', '성분A', '메이커A', 'Y'),
          (2, '공식살충', '성분A', '메이커A', 'Y');

        CREATE TABLE m_pesticide_pest_map (
            map_id INTEGER PRIMARY KEY,
            info_id INTEGER NOT NULL,
            pest_nm TEXT NOT NULL,
            use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO m_pesticide_pest_map VALUES
          (1, 1, '깍지벌레', 'Y'),
          (2, 2, '진딧물', 'Y');

        CREATE TABLE m_pesticide_item (
            item_id INTEGER PRIMARY KEY,
            farm_cd TEXT NOT NULL,
            item_nm TEXT NOT NULL,
            spec_nm TEXT,
            pest_category_nm TEXT DEFAULT '',
            qty_piece INTEGER NOT NULL DEFAULT 0,
            warn_piece_below INTEGER,
            sort_ord INTEGER DEFAULT 0,
            use_yn TEXT DEFAULT 'Y',
            rmk TEXT,
            info_id INTEGER,
            mod_id TEXT,
            mod_dt TEXT
        );
        INSERT INTO m_pesticide_item (
            item_id, farm_cd, item_nm, spec_nm, pest_category_nm, qty_piece,
            warn_piece_below, sort_ord, use_yn, rmk, info_id
        ) VALUES
          (1, 'OR001', '부족약', '500ml', '', 0, NULL, 0, 'Y', '', 1),
          (2, 'OR001', '여유약', '1L', '', 5, 3, 1, 'Y', '비고', NULL);

        CREATE TABLE m_farm_site (
            site_id INTEGER PRIMARY KEY, farm_cd TEXT, site_nm TEXT
        );
        INSERT INTO m_farm_site VALUES (1, 'OR001', '1번지');

        CREATE TABLE t_pesticide_use (
            use_id INTEGER PRIMARY KEY,
            farm_cd TEXT NOT NULL,
            use_dt TEXT NOT NULL,
            site_id INTEGER,
            worker_nm TEXT,
            work_id TEXT,
            stock_applied_yn TEXT DEFAULT 'Y',
            cancel_yn TEXT DEFAULT 'N',
            use_yn TEXT DEFAULT 'Y'
        );
        INSERT INTO t_pesticide_use VALUES
          (10, 'OR001', '2026-07-15', 1, '홍길동', '20260715-01', 'Y', 'N', 'Y'),
          (11, 'OR001', '2026-06-01', NULL, '', NULL, 'Y', 'N', 'Y'),
          (12, 'OR001', '2026-05-01', NULL, '', NULL, 'Y', 'Y', 'Y');

        CREATE TABLE t_pesticide_use_line (
            use_line_id INTEGER PRIMARY KEY,
            use_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            item_id INTEGER NOT NULL,
            item_nm_snapshot TEXT,
            use_qty INTEGER DEFAULT 0,
            purpose_nm TEXT
        );
        INSERT INTO t_pesticide_use_line VALUES
          (101, 10, 1, 1, '부족약', 2, '깍지벌레'),
          (102, 11, 1, 1, '부족약', 1, ''),
          (103, 12, 1, 2, '여유약', 1, '취소건');

        CREATE TABLE t_pesticide_stock_hist (
            hist_id INTEGER PRIMARY KEY,
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
        INSERT INTO t_pesticide_stock_hist (
            hist_id, farm_cd, item_id, trans_type, ref_table, ref_id,
            qty_delta, qty_after, trans_dt, rmk
        ) VALUES
          (1, 'OR001', 1, 'USE', 't_pesticide_use', 10, -2, 0, '2026-07-15 10:00:00', '');
        """
    )
    conn.commit()
    conn.close()
    return path


class PesticideServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _build_tmp_db()
        self.svc = PesticideService(self.db)

    def tearDown(self) -> None:
        try:
            self.db.unlink(missing_ok=True)
        except OSError:
            pass

    def test_list_items_low_first(self) -> None:
        body = self.svc.list_items("OR001")
        self.assertEqual(body.summary.total_count, 2)
        self.assertEqual(body.summary.low_count, 1)
        self.assertEqual(
            body.summary.default_warn_piece_below,
            PESTICIDE_DEFAULT_WARN_PIECE_BELOW,
        )
        self.assertTrue(body.items[0].is_low)
        self.assertEqual(body.items[0].item_nm, "부족약")
        self.assertEqual(body.items[0].ingredient_nm, "성분A")
        self.assertIn("깍지벌레", body.items[0].pest_target_nm or "")
        self.assertIn("진딧물", body.items[0].pest_target_nm or "")
        self.assertEqual(body.items[0].warn_source, "default")
        self.assertFalse(body.items[1].is_low)
        self.assertEqual(body.items[1].warn_source, "item")
        self.assertIsNone(body.items[1].ingredient_nm)
        self.assertIsNone(body.items[1].pest_target_nm)
        self.assertEqual(body.summary.last_spray_dt, "2026-07-15")

    def test_list_recent_usage(self) -> None:
        body = self.svc.list_recent_usage("OR001", days=90, max_days=10)
        self.assertEqual(body.last_spray_dt, "2026-07-15")
        self.assertGreaterEqual(len(body.days), 1)
        top = body.days[0]
        self.assertEqual(top.use_dt, "2026-07-15")
        self.assertEqual(top.lines[0].item_nm, "부족약")
        self.assertEqual(top.lines[0].use_qty, 2)
        self.assertEqual(top.lines[0].unit, "개")

    def test_yearly_stats(self) -> None:
        body = self.svc.get_yearly_stats("OR001", 2026)
        self.assertEqual(body.year, 2026)
        self.assertGreaterEqual(body.spray_count_total, 1)
        self.assertTrue(any(it.item_nm == "부족약" for it in body.items))

    def test_info_list_and_detail(self) -> None:
        listed = self.svc.list_info("OR001", keyword="공식")
        # 동일 품목명(대상병해충만 다른 행)은 목록에서 1건
        self.assertEqual(len(listed.items), 1)
        self.assertEqual(listed.items[0].pesticide_nm, "공식살충")
        detail = self.svc.get_info_detail("OR001", 1, year=2026)
        self.assertEqual(detail.pesticide_nm, "공식살충")
        pests = detail.pest_target_nm or ""
        self.assertIn("깍지벌레", pests)
        self.assertIn("진딧물", pests)

    def test_info_list_keyword_by_pest(self) -> None:
        listed = self.svc.list_info("OR001", keyword="깍지")
        self.assertEqual(len(listed.items), 1)
        self.assertEqual(listed.items[0].pesticide_nm, "공식살충")

    def test_info_list_keyword_by_ingredient(self) -> None:
        listed = self.svc.list_info("OR001", keyword="성분A")
        self.assertEqual(len(listed.items), 1)
        self.assertEqual(listed.items[0].ingredient_nm, "성분A")

    def test_stock_hist(self) -> None:
        body = self.svc.list_stock_hist("OR001", 1)
        self.assertEqual(body.item_nm, "부족약")
        self.assertEqual(len(body.rows), 1)
        self.assertEqual(body.rows[0].trans_type, "USE")
        self.assertEqual(body.rows[0].qty_delta, -2)
        self.assertEqual(body.rows[0].qty_after, 0)

    def test_stock_out_sale(self) -> None:
        from app.schemas.pesticide_ext import PesticideStockOutRequest

        # 여유약 재고 5 → 3병 판매
        res = self.svc.issue_stock_out(
            "OR001",
            2,
            PesticideStockOutRequest(qty=3, buyer_nm="A농가", rmk="현금"),
        )
        self.assertEqual(res.qty, 3)
        self.assertEqual(res.qty_after, 2)
        items = self.svc.list_items("OR001", keyword="여유")
        self.assertEqual(items.items[0].qty_piece, 2)
        hist = self.svc.list_stock_hist("OR001", 2)
        self.assertTrue(any(r.trans_type == "OUT" and r.qty_delta == -3 for r in hist.rows))
        top = next(r for r in hist.rows if r.trans_type == "OUT")
        self.assertEqual(top.qty_after, 2)
        self.assertIn("A농가", top.rmk or "")

    def test_stock_out_insufficient(self) -> None:
        from app.core.exceptions import BusinessRuleError
        from app.schemas.pesticide_ext import PesticideStockOutRequest

        with self.assertRaises(BusinessRuleError):
            self.svc.issue_stock_out(
                "OR001",
                1,
                PesticideStockOutRequest(qty=1, buyer_nm="B농가"),
            )

    def test_list_items_keyword(self) -> None:
        body = self.svc.list_items("OR001", keyword="여유")
        self.assertEqual(len(body.items), 1)
        self.assertEqual(body.items[0].item_id, 2)

    def test_list_items_keyword_by_sibling_pest(self) -> None:
        """연결 info에 없는 병해충이라도 동일 품목·제조사 형제 행이면 검색됨."""
        body = self.svc.list_items("OR001", keyword="진딧물")
        self.assertEqual(len(body.items), 1)
        self.assertEqual(body.items[0].item_id, 1)
        self.assertIn("진딧물", body.items[0].pest_target_nm or "")

    def test_item_detail_and_usage(self) -> None:
        body = self.svc.get_item_detail("OR001", 1)
        self.assertEqual(body.item.info_pesticide_nm, "공식살충")
        usage = self.svc.list_item_usage("OR001", 1)
        self.assertEqual(usage.total, 2)
        self.assertGreaterEqual(len(usage.rows), 1)
        latest = usage.rows[0]
        self.assertEqual(latest.purpose_nm, "깍지벌레")
        self.assertEqual(latest.work_id, "20260715-01")

    def test_item_not_found(self) -> None:
        with self.assertRaises(EntityNotFoundError):
            self.svc.get_item_detail("OR001", 999)


if __name__ == "__main__":
    unittest.main()
