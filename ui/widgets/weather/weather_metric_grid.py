from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from ui.styles import MainStyles


class WeatherMetricGrid(QFrame):
    EMPTY_VALUE = "—"
    COLOR_TEXT_MAIN = "#2D3748"
    COLOR_TEXT_SUB = "#718096"
    COLOR_CELL_BG = "#F8FAFC"
    COLOR_CELL_BORDER = "#E2E8F0"
    FIELD_SPECS = [
        ("temp", "🌡", "기온"),
        ("feels_like", "🧊", "체감"),
        ("rain", "☔", "강수"),
        ("wind", "🧭", "바람"),
        ("humidity", "💧", "습도"),
        ("pressure", "⏲", "기압"),
    ]
    CARD_STYLE = MainStyles.CARD
    CELL_STYLE = (
        f"QFrame {{ background:{COLOR_CELL_BG}; border:1px solid {COLOR_CELL_BORDER}; border-radius:8px; }}"
    )
    TITLE_STYLE = MainStyles.TXT_CARD_TITLE
    NAME_STYLE = MainStyles.TXT_CAPTION
    VALUE_STYLE_EMPH = MainStyles.TXT_SUMMARY_VALUE_EMPH
    VALUE_STYLE_NORMAL = MainStyles.TXT_BODY
    EMPH_KEYS = {"temp", "feels_like"}

    def __init__(self, title: str = "", columns: int = 3, parent=None):
        super().__init__(parent)
        self._title = str(title or "")
        self._columns = max(2, int(columns or 3))
        self._cells = {}
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(self.CARD_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        if self._title:
            lbl_title = QLabel(self._title)
            lbl_title.setStyleSheet(self.TITLE_STYLE)
            root.addWidget(lbl_title)

        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)
        root.addLayout(self._grid)

        for idx, (key, icon, label) in enumerate(self.FIELD_SPECS):
            row, col = divmod(idx, self._columns)
            cell, value_lbl = self._build_cell(key, icon, label)
            self._grid.addWidget(cell, row, col)
            self._cells[key] = value_lbl

    def _build_cell(self, key: str, icon: str, name: str):
        box = QFrame()
        box.setStyleSheet(self.CELL_STYLE)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        top = QWidget()
        top_lay = QGridLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setHorizontalSpacing(4)
        top_lay.setVerticalSpacing(0)
        lbl_icon = QLabel(icon)
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(self.NAME_STYLE)
        top_lay.addWidget(lbl_icon, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        top_lay.addWidget(lbl_name, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        top_lay.setColumnStretch(2, 1)
        lay.addWidget(top)

        lbl_val = QLabel(self.EMPTY_VALUE)
        val_style = self.VALUE_STYLE_EMPH if key in self.EMPH_KEYS else self.VALUE_STYLE_NORMAL
        lbl_val.setStyleSheet(val_style)
        lbl_val.setWordWrap(True)
        lay.addWidget(lbl_val)
        lay.addStretch()
        return box, lbl_val

    def set_data(self, data: dict):
        payload = data or {}
        for key, _, _ in self.FIELD_SPECS:
            v = payload.get(key, self.EMPTY_VALUE)
            if v in (None, ""):
                v = self.EMPTY_VALUE
            self._cells[key].setStyleSheet(
                self.VALUE_STYLE_EMPH if key in self.EMPH_KEYS else self.VALUE_STYLE_NORMAL
            )
            self._cells[key].setText(str(v))
