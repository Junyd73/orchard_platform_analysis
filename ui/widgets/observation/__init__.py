# -*- coding: utf-8 -*-
"""관찰일지 전용 위젯 패키지."""

from ui.widgets.observation.ai_analysis_panel import AiAnalysisPanel
from ui.widgets.observation.fruit_growth_chart import FruitGrowthChart
from ui.widgets.observation.photo_compare_dialog import PhotoCompareDialog
from ui.widgets.observation.photo_panel import PhotoPanel

__all__ = (
    "FruitGrowthChart",
    "PhotoPanel",
    "PhotoCompareDialog",
    "AiAnalysisPanel",
)
