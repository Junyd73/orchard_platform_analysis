# -*- coding: utf-8 -*-
"""열매 측정값 라인차트 (외부 라이브러리 없이 QPainter)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class FruitGrowthChart(QWidget):
    """points: [{"dt": "YYYY-MM-DD", "value": float|None}, ...] 결측은 선으로 연결하지 않음."""

    def __init__(self, unit: str = "mm", parent=None):
        super().__init__(parent)
        self._points: list[dict] = []
        self._unit = unit
        self._title = ""
        self.setMinimumHeight(160)
        self.setToolTip("")

    def set_series(self, title: str, unit: str, points: list[dict] | None):
        self._title = title or ""
        self._unit = unit or ""
        self._points = list(points or [])
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        margin_l, margin_r, margin_t, margin_b = 44, 12, 28, 28
        chart = self.rect().adjusted(margin_l, margin_t, -margin_r, -margin_b)
        painter.setPen(QColor("#2D5A27"))
        font = QFont(painter.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            self.rect().adjusted(8, 4, -8, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"{self._title} ({self._unit})" if self._unit else self._title,
        )

        valid = [
            (i, p)
            for i, p in enumerate(self._points)
            if p.get("value") is not None
        ]
        if not valid:
            painter.setPen(QColor("#718096"))
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(chart, Qt.AlignmentFlag.AlignCenter, "측정 이력이 없습니다")
            return

        if len(valid) == 1:
            _, p = valid[0]
            painter.setPen(QColor("#4A5568"))
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(
                chart,
                Qt.AlignmentFlag.AlignCenter,
                f"{p.get('dt') or ''}\n{p.get('value')} {self._unit}",
            )
            return

        vals = [float(p["value"]) for _, p in valid]
        vmin, vmax = min(vals), max(vals)
        if abs(vmax - vmin) < 1e-9:
            vmax = vmin + 1.0
        pad = (vmax - vmin) * 0.08
        vmin -= pad
        vmax += pad

        painter.setPen(QPen(QColor("#EAE7E2"), 1))
        painter.drawRect(chart)

        n = max(1, len(self._points) - 1)
        coords = []
        for i, p in enumerate(self._points):
            x = chart.left() + int(chart.width() * (i / n))
            if p.get("value") is None:
                coords.append(None)
                continue
            v = float(p["value"])
            y = chart.bottom() - int(chart.height() * ((v - vmin) / (vmax - vmin)))
            coords.append((x, y, p))

        pen = QPen(QColor("#2D5A27"), 2)
        painter.setPen(pen)
        last = None
        for c in coords:
            if c is None:
                last = None
                continue
            if last is not None:
                painter.drawLine(last[0], last[1], c[0], c[1])
            last = c

        painter.setBrush(QColor("#2D5A27"))
        tip_parts = []
        for c in coords:
            if c is None:
                continue
            painter.drawEllipse(c[0] - 3, c[1] - 3, 6, 6)
            tip_parts.append(f"{c[2].get('dt')}: {c[2].get('value')}{self._unit}")
        if tip_parts:
            self.setToolTip("\n".join(tip_parts))
