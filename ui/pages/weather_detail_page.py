# -*- coding: utf-8 -*-
"""
weather_detail_page.py - 날씨 상세 페이지
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

from ui.pages.dashboard_detail_base import DashboardDetailBase


class WeatherDetailPage(DashboardDetailBase):
    """날씨 상세 (t_work_log 기반 요약)"""

    def __init__(self, db_manager, session, parent=None):
        super().__init__("weather", "날씨", "🌤️", db_manager, session, parent)
        self._build_content()
        self._build_sidebar()

    def _build_content(self):
        # DB에서 최근 날씨 요약 (t_work_log.weather_cd)
        rows = []
        try:
            sql = """
                SELECT weather_cd, COUNT(*) as cnt 
                FROM t_work_log 
                WHERE farm_cd = ? AND work_dt >= date('now', '-30 days')
                GROUP BY weather_cd
            """
            res = self.db.execute_query(sql, (self.farm_cd,))
            rows = [dict(r) for r in res] if res else []
        except Exception:
            pass

        summary = [("최근 30일 기록", str(len(rows)) + "건", "날씨별 집계")] if rows else [("데이터", "없음", "영농일지 기록 필요")]
        for r in rows[:3]:
            summary.append((r.get('weather_cd', '-'), str(r.get('cnt', 0)) + "건", ""))
        self.set_summary_cards(summary[:4])

        ph = QLabel("날씨 상세 분석 및 예보\n(WeatherManager 연동 예정)")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setStyleSheet("color: #718096; padding: 40px;")
        self.main_layout.addWidget(ph)

    def _build_sidebar(self):
        self.add_sidebar_card("market", "시장/경매", "📈")
        self.add_sidebar_card("labor", "인건비/경비", "👷")
        self.add_sidebar_card("kpi", "KPI 지표", "📊")
