# -*- coding: utf-8 -*-
"""
kpi_detail_page.py - KPI 지표 상세 페이지
"""
from PyQt6.QtWidgets import QLabel, QFrame, QTableWidget, QTableWidgetItem, QVBoxLayout
from PyQt6.QtCore import Qt

from ui.pages.dashboard_detail_base import DashboardDetailBase


def _norm_ymd_sql(col: str) -> str:
    c = col
    return (
        f"CASE "
        f"WHEN {c} IS NULL THEN NULL "
        f"WHEN length({c})=10 AND instr({c}, '-')=5 THEN {c} "
        f"WHEN length({c})=8 THEN substr({c},1,4)||'-'||substr({c},5,2)||'-'||substr({c},7,2) "
        f"ELSE {c} END"
    )


class KpiDetailPage(DashboardDetailBase):
    """KPI 지표 상세 (매출/수금/미수 요약)"""

    def __init__(self, db_manager, session, parent=None):
        super().__init__("kpi", "KPI 지표", "📊", db_manager, session, parent)
        self._build_content()
        self._build_sidebar()

    def _build_content(self):
        sales_today = 0
        paid_today = 0
        receivables = 0
        recent_rows = []
        try:
            import datetime
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            sales_dt_norm = _norm_ymd_sql("sales_dt")

            r1 = self.db.execute_query(
                f"SELECT COALESCE(SUM(tot_sales_amt + tot_ship_fee), 0) "
                f"FROM t_sales_master WHERE farm_cd = ? AND {sales_dt_norm} = ?",
                (self.farm_cd, today)
            )
            r2 = self.db.execute_query(
                f"SELECT COALESCE(SUM(tot_paid_amt), 0) "
                f"FROM t_sales_master WHERE farm_cd = ? AND {sales_dt_norm} = ?",
                (self.farm_cd, today)
            )
            r3 = self.db.execute_query(
                "SELECT COALESCE(SUM(tot_unpaid_amt), 0) FROM t_sales_master WHERE farm_cd = ?",
                (self.farm_cd,)
            )
            sales_today = int(r1[0][0]) if r1 and r1[0] else 0
            paid_today = int(r2[0][0]) if r2 and r2[0] else 0
            receivables = int(r3[0][0]) if r3 and r3[0] else 0

            # 최근 14일 매출 리스트(차트 대신 표로 노출). 날짜 포맷 혼재 대응.
            sql_recent = f"""
                SELECT
                    {sales_dt_norm} AS sales_dt,
                    sales_no,
                    COALESCE(tot_sales_amt + tot_ship_fee, 0) AS sales_amt,
                    COALESCE(tot_paid_amt, 0) AS paid_amt,
                    COALESCE(tot_unpaid_amt, 0) AS unpaid_amt
                FROM t_sales_master
                WHERE farm_cd = ?
                  AND date({sales_dt_norm}) >= date('now', '-14 days')
                ORDER BY date({sales_dt_norm}) DESC, sales_no DESC
                LIMIT 50
            """
            res = self.db.execute_query(sql_recent, (self.farm_cd,))
            recent_rows = [dict(r) for r in res] if res else []
        except Exception:
            pass

        self.set_summary_cards([
            ("오늘 매출", f"{sales_today:,}원", "판매 기준"),
            ("오늘 수금", f"{paid_today:,}원", "입금 기준"),
            ("총 미수금", f"{receivables:,}원", "전체 미수 합계"),
        ])

        # 메인 콘텐츠: 최근 매출 리스트 (데이터 없을 때도 섹션은 표시)
        section = QFrame()
        section.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(section)
        title = QLabel("최근 14일 판매 내역")
        title.setStyleSheet("font-weight: bold; color: #2D3748; padding: 4px 0;")
        lay.addWidget(title)

        if not recent_rows:
            empty = QLabel("표시할 데이터가 없습니다. (기간: 최근 14일)")
            empty.setStyleSheet("color: #718096; padding: 24px;")
            lay.addWidget(empty)
        else:
            tbl = QTableWidget()
            tbl.setColumnCount(5)
            tbl.setHorizontalHeaderLabels(["일자", "판매번호", "매출", "수금", "미수"])
            tbl.setRowCount(len(recent_rows))
            tbl.setAlternatingRowColors(True)
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            tbl.setStyleSheet("QTableWidget{background:white;border:1px solid #E2E8F0;border-radius:10px;}")
            for i, r in enumerate(recent_rows):
                tbl.setItem(i, 0, QTableWidgetItem(str(r.get("sales_dt") or "")))
                tbl.setItem(i, 1, QTableWidgetItem(str(r.get("sales_no") or "")))
                tbl.setItem(i, 2, QTableWidgetItem(f"{int(r.get('sales_amt') or 0):,}"))
                tbl.setItem(i, 3, QTableWidgetItem(f"{int(r.get('paid_amt') or 0):,}"))
                tbl.setItem(i, 4, QTableWidgetItem(f"{int(r.get('unpaid_amt') or 0):,}"))
                for c in (2, 3, 4):
                    it = tbl.item(i, c)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tbl.resizeColumnsToContents()
            lay.addWidget(tbl)

        self.main_layout.addWidget(section)

    def _build_sidebar(self):
        self.add_sidebar_card("market", "시장/경매", "📈")
        self.add_sidebar_card("weather", "날씨", "🌤️")
        self.add_sidebar_card("labor", "인건비/경비", "👷")
