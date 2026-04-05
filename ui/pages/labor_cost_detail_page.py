# -*- coding: utf-8 -*-
"""
labor_cost_detail_page.py - 인건비/경비 상세 페이지
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

from ui.pages.dashboard_detail_base import DashboardDetailBase


class LaborCostDetailPage(DashboardDetailBase):
    """인건비·경비 상세 (t_work_resource, t_work_expense)"""

    def __init__(self, db_manager, session, parent=None):
        super().__init__("labor", "인건비/경비", "👷", db_manager, session, parent)
        self._build_content()
        self._build_sidebar()

    def _build_content(self):
        labor_sum = 0
        exp_sum = 0
        try:
            sql_res = """
                SELECT COALESCE(SUM(daily_wage), 0) FROM t_work_resource
                WHERE farm_cd = ? AND trans_dt >= date('now', '-30 days') AND pay_status = 'Y'
            """
            sql_exp = """
                SELECT COALESCE(SUM(total_amt), 0) FROM t_work_expense
                WHERE farm_cd = ? AND trans_dt >= date('now', '-30 days') AND pay_status = 'Y'
            """
            r1 = self.db.execute_query(sql_res, (self.farm_cd,))
            r2 = self.db.execute_query(sql_exp, (self.farm_cd,))
            labor_sum = int(r1[0][0]) if r1 and r1[0] else 0
            exp_sum = int(r2[0][0]) if r2 and r2[0] else 0
        except Exception:
            pass

        self.set_summary_cards([
            ("30일 인건비", f"{labor_sum:,}원", "지급 완료 건"),
            ("30일 경비", f"{exp_sum:,}원", "지급 완료 건"),
            ("합계", f"{labor_sum + exp_sum:,}원", "인건비+경비"),
        ])

        ph = QLabel("인건비/경비 상세 내역\n(영농일지 데이터 기반)")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet("font-size: 14px; color: #718096; padding: 40px;")
        self.main_layout.addWidget(ph)

    def _build_sidebar(self):
        self.add_sidebar_card("market", "시장/경매", "📈")
        self.add_sidebar_card("weather", "날씨", "🌤️")
        self.add_sidebar_card("kpi", "KPI 지표", "📊")
