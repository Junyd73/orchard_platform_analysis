# -*- coding: utf-8 -*-
"""
market_price_page.py - 시장/경매 가격 상세 페이지(UI 구조 우선)
"""
from PyQt6.QtCore import Qt, QDate, QPoint, QTimer, QPointF, QRectF
from PyQt6.QtWidgets import (
    QLabel,
    QFrame,
    QWidget,
    QToolTip,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QComboBox,
    QLineEdit,
    QDateEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QPushButton,
    QTabWidget,
    QProgressBar,
    QDialog,
    QApplication,
    QMessageBox,
    QTextEdit,
    QDialogButtonBox,
    QToolButton,
    QAbstractItemView,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

from ui.styles import DEFAULT_FONT_FAMILY, MainStyles
from ui.pages.dashboard_detail_base import DashboardDetailBase
from ui.widgets.dashboard_card_widget import DecisionDonutWidget
from core.code_manager import CodeManager
from core.market_price_manager import MarketPriceManager, MarketSettlementManager
from core.market_price_service import MarketPriceService
from core.services.market_analysis_service import MarketAnalysisService
from ui.components.auction_filter_bar import AuctionFilterBar
from concurrent.futures import ThreadPoolExecutor
import os
import json
import re
from pathlib import Path
from datetime import date, datetime, timedelta

SECTION_CONTENT_MARGINS = MainStyles.MARKET_SECTION_CONTENT_MARGINS
SECTION_SPACING = MainStyles.MARKET_SECTION_SPACING
ROW_SPACING = MainStyles.MARKET_ROW_SPACING

# 시장분석 카드: ? 툴팁(9pt) — 본문 안내 제거 후 통합
MARKET_ANALYSIS_HELP_TOOLTIP = (
    "출하 판단용 요약과 가격·거래량·품질 추이만 표시합니다.\n"
    "데이터 검증은 상단 '데이터 검증' 버튼을 사용하세요.\n\n"
    "누락 적재가 필요하면 '기초데이터 가져오기'를 눌러주세요."
)
MARKET_ANALYSIS_STATUS_LBL_STYLE = MainStyles.DASH_LABEL + " color:#4A5568;"
MARKET_ANALYSIS_LATEST_LBL_STYLE = MainStyles.TXT_CAPTION + " color:#718096;"
FILTER_CONTROL_HEIGHT = 28
# 필터 한 줄(날짜·콤보=FILTER_CONTROL_HEIGHT) 옆 버튼: BTN_*_COMPACT + 고정 높이 없음.
# BTN_PRIMARY/BTN_SECONDARY(큰 padding)와 setFixedHeight(28) 병용 시 한글 세로 clipping 발생.
KPI_TILE_MIN_HEIGHT = MainStyles.MARKET_KPI_TILE_MIN_HEIGHT
UI_TREND_DAYS = 30
HEADER_LOAD_STEPS = 2
DETAIL_LOAD_STEPS = 3
ANALYSIS_LOAD_STEPS = 3
SUMMARY_LOAD_STEPS = HEADER_LOAD_STEPS
TREND_LOAD_STEPS = ANALYSIS_LOAD_STEPS
DEBUG_MARKET_VERIFY = os.getenv("ORCHARD_DEBUG_MARKET_VERIFY", "1").lower() not in ("0", "false", "off")
ANALYSIS_LOOKBACK_DAYS = 90
ANALYSIS_MARKET_CODE_BY_NAME = {
    "가락": "110001",
    "부평": "230001",
}
ANALYSIS_ITEM_CODE_BY_VARIETY = {
    "신고": "06-02-01",
    "원황": "06-02-02",
    "화산": "06-02-03",
    "추황": "06-02-04",
}
ANALYSIS_DEFAULT_MARKET_CODE = "110001"
ANALYSIS_DEFAULT_ITEM_CODE = "06-02-01"

# 시장분석 탭: 품목/품종/시장/법인 UI 제거 후 DB·헤더 조회 고정값
MARKET_ANALYSIS_FIXED_ITEM_NAME = "배"
MARKET_ANALYSIS_FIXED_ITEM_CD = "FR010100"
MARKET_ANALYSIS_FIXED_VARIETY_NAME = "신고"
MARKET_ANALYSIS_FIXED_MARKET_NAME = "가락"
MARKET_ANALYSIS_FIXED_CORP_NAME = "전체"


def _market_analysis_filters_snapshot() -> dict:
    """AuctionFilterBar.get_filters()와 동일 키. target_date는 호출 시점의 당일."""
    return {
        "target_date": QDate.currentDate().toString("yyyy-MM-dd"),
        "item_cd": MARKET_ANALYSIS_FIXED_ITEM_CD,
        "variety_cd": ANALYSIS_DEFAULT_ITEM_CODE,
        "market_cd": ANALYSIS_DEFAULT_MARKET_CODE,
        "corp_cd": None,
        "item_name": MARKET_ANALYSIS_FIXED_ITEM_NAME,
        "variety_name": MARKET_ANALYSIS_FIXED_VARIETY_NAME,
        "market_name": MARKET_ANALYSIS_FIXED_MARKET_NAME,
        "corp_name": MARKET_ANALYSIS_FIXED_CORP_NAME,
    }


def _map_price_type(text: str) -> str:
    """가격 구조 콤보 표시문 → 내부 키."""
    if text == "최고가":
        return "max"
    if text == "평균가":
        return "avg"
    if text == "최저가":
        return "min"
    return "max"


class AuctionToSalesMapDialog(QDialog):
    """실시간 경매 선택행을 판매관리 전송 전 수정/검증."""

    HEADERS = ["규격", "등급", "과수", "건수", "단가", "금액"]

    def __init__(self, owner: "MarketPricePage", common: dict, rows: list[dict], parent=None):
        super().__init__(parent)
        self._owner = owner
        self._rows = rows or []
        self._common = common or {}
        self._result = None
        self._updating_table = False
        self.setWindowTitle("판매관리 전송 - 매핑 수정/검증")
        self.resize(980, 640)
        self.setStyleSheet(MainStyles.MAIN_BG)
        self._build_ui()
        self._load_rows()

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QGridLayout()
        self.edt_date = QDateEdit()
        self.edt_date.setCalendarPopup(True)
        self.edt_market = QLineEdit()
        self.cmb_corp = QComboBox()
        self.cmb_item = QComboBox()
        self.cmb_variety = QComboBox()
        self.edt_market.setStyleSheet(MainStyles.INPUT_CENTER)
        for cb in (self.cmb_corp, self.cmb_item, self.cmb_variety):
            cb.setStyleSheet(MainStyles.COMBO)
        self.edt_date.setStyleSheet(MainStyles.COMBO)
        d = QDate.fromString(str(self._common.get("target_date") or ""), "yyyy-MM-dd")
        self.edt_date.setDate(d if d.isValid() else QDate.currentDate())
        self.edt_market.setText(str(self._common.get("market_name") or "").strip())
        self._load_header_combos()
        top.addWidget(QLabel("일자"), 0, 0); top.addWidget(self.edt_date, 0, 1)
        top.addWidget(QLabel("시장"), 0, 2); top.addWidget(self.edt_market, 0, 3)
        top.addWidget(QLabel("법인"), 0, 4); top.addWidget(self.cmb_corp, 0, 5)
        top.addWidget(QLabel("품목"), 1, 0); top.addWidget(self.cmb_item, 1, 1)
        top.addWidget(QLabel("품종"), 1, 2); top.addWidget(self.cmb_variety, 1, 3)
        root.addLayout(top)

        guide = QLabel("규격/등급/과수를 콤보로 확인/수정 후 [전송 적용]을 누르세요.")
        guide.setStyleSheet(MainStyles.CARD_LBL_STYLE)
        root.addWidget(guide)

        self.tbl = QTableWidget(0, len(self.HEADERS))
        self.tbl.setHorizontalHeaderLabels(self.HEADERS)
        self.tbl.setStyleSheet(MainStyles.TABLE)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.tbl.horizontalHeader()
        for c, w in enumerate((170, 130, 130, 100, 120, 130)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self.tbl.setColumnWidth(c, w)
        h.setStretchLastSection(True)
        self.tbl.itemChanged.connect(self._on_table_item_changed)
        root.addWidget(self.tbl, 1)

        btns = QHBoxLayout()
        self.btn_apply = QPushButton("전송 적용")
        self.btn_apply.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_apply.clicked.connect(self._accept_payload)
        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_close.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.btn_apply)
        btns.addWidget(btn_close)
        root.addLayout(btns)

    @staticmethod
    def _norm(text: str) -> str:
        return str(text or "").strip().replace(" ", "").replace("-", "")

    def _match_combo_by_text_only(self, cb: QComboBox, raw_text: str):
        target = self._norm(raw_text)
        if not target:
            return
        for i in range(cb.count()):
            t = self._norm(cb.itemText(i))
            if t == target or (t and (t in target or target in t)):
                cb.setCurrentIndex(i)
                return

    def _load_header_combos(self):
        self.cmb_corp.clear()
        self.cmb_corp.addItem("선택", "")
        try:
            rows = self._owner.db.execute_query(
                """
                SELECT custm_id, custm_nm
                FROM m_customer
                WHERE farm_cd = ? AND IFNULL(use_yn,'Y')='Y'
                ORDER BY custm_nm
                """,
                (self._owner.farm_cd,),
            ) or []
            for r in rows:
                cust_id = str(self._row_value(r, "custm_id", "") or "").strip()
                cust_nm = str(self._row_value(r, "custm_nm", "") or "").strip()
                if cust_id and cust_nm:
                    self.cmb_corp.addItem(cust_nm, cust_id)
        except Exception:
            pass

        self.cmb_item.clear()
        self.cmb_item.addItem("선택", "")
        for it in (self._owner._auction_code_mgr.get_common_codes("FR01") or []):
            self.cmb_item.addItem(
                str(self._row_value(it, "code_nm", "") or ""),
                str(self._row_value(it, "code_cd", "") or ""),
            )

        self.cmb_variety.clear()
        self.cmb_variety.addItem("선택", "")
        self.cmb_item.currentIndexChanged.connect(self._on_item_changed)

        self._match_combo_by_text_only(self.cmb_corp, str(self._common.get("corp_name") or ""))
        self._match_combo_by_text_only(self.cmb_item, str(self._common.get("item_name") or ""))
        self._on_item_changed()
        self._match_combo_by_text_only(self.cmb_variety, str(self._common.get("variety_name") or ""))

    def _on_item_changed(self):
        item_cd = str(self.cmb_item.currentData() or "").strip()
        self.cmb_variety.blockSignals(True)
        self.cmb_variety.clear()
        self.cmb_variety.addItem("선택", "")
        if item_cd:
            for v in (self._owner._auction_code_mgr.get_common_codes(item_cd) or []):
                self.cmb_variety.addItem(
                    str(self._row_value(v, "code_nm", "") or ""),
                    str(self._row_value(v, "code_cd", "") or ""),
                )
        self.cmb_variety.blockSignals(False)

    @staticmethod
    def _extract_kg_value(text: str):
        m = re.search(r"(\d+(?:\.\d+)?)\s*kg", str(text or "").lower())
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None

    def _match_combo_by_text(self, cb: QComboBox, raw_text: str):
        target = self._norm(raw_text)
        if not target:
            return
        # 규격 콤보는 kg 숫자 정확 매칭 우선 (15kg -> 5kg 오매칭 방지)
        t_kg = self._extract_kg_value(raw_text)
        if t_kg is not None:
            for i in range(cb.count()):
                c_kg = self._extract_kg_value(cb.itemText(i))
                if c_kg is not None and abs(c_kg - t_kg) < 1e-9:
                    cb.setCurrentIndex(i)
                    return
        for i in range(cb.count()):
            t = self._norm(cb.itemText(i))
            if t == target or (t and (t in target or target in t)):
                cb.setCurrentIndex(i)
                return

    @staticmethod
    def _row_value(row, key: str, default=""):
        """sqlite3.Row / dict 겸용 안전 접근."""
        try:
            if isinstance(row, dict):
                return row.get(key, default)
            return row[key]
        except Exception:
            return default

    def _grade_count_options(self, grade_cd: str):
        if not grade_cd:
            return []
        rows = self._owner.db.execute_query(
            """
            SELECT code_cd, code_nm
            FROM m_common_code
            WHERE farm_cd = ? AND parent_cd = ? AND IFNULL(use_yn,'Y')='Y'
            ORDER BY code_cd
            """,
            (self._owner.farm_cd, grade_cd),
        )
        return [(str(r[0] or "").strip(), str(r[1] or "").strip()) for r in (rows or [])]

    def _reload_crop_combo(self, crop_cb: QComboBox, grade_cd: str, raw_crop_text: str = ""):
        crop_cb.blockSignals(True)
        crop_cb.clear()
        crop_cb.addItem("선택", "")
        for cd, nm in self._grade_count_options(grade_cd):
            crop_cb.addItem(nm, cd)
        crop_cb.blockSignals(False)
        if raw_crop_text:
            self._match_combo_by_text(crop_cb, raw_crop_text)

    @staticmethod
    def _make_number_item(value: int) -> QTableWidgetItem:
        item = QTableWidgetItem(f"{int(value):,}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _set_amount_item(self, row: int, amount: int):
        item = self._make_number_item(amount)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.tbl.setItem(row, 5, item)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if self._updating_table or item is None:
            return
        col = item.column()
        if col not in (3, 4):
            return
        row = item.row()
        self._updating_table = True
        try:
            cnt = self._to_int(self.tbl.item(row, 3).text() if self.tbl.item(row, 3) else "0")
            price = self._to_int(self.tbl.item(row, 4).text() if self.tbl.item(row, 4) else "0")
            # 사용자가 입력한 숫자도 즉시 천단위 포맷/우측 정렬로 통일한다.
            self.tbl.setItem(row, 3, self._make_number_item(cnt))
            self.tbl.setItem(row, 4, self._make_number_item(price))
            self._set_amount_item(row, cnt * price)
        finally:
            self._updating_table = False

    def _load_rows(self):
        specs = self._owner._auction_code_mgr.get_common_codes("SZ01") or []
        grades = self._owner._auction_code_mgr.get_common_codes("GR01") or []
        self._updating_table = True
        try:
            for src in self._rows:
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                cb_spec = QComboBox(); cb_spec.setStyleSheet(MainStyles.COMBO_TABLE_CELL_WORK_LOG)
                cb_spec.addItem("선택", "")
                for s in specs:
                    cb_spec.addItem(
                        str(self._row_value(s, "code_nm", "") or ""),
                        str(self._row_value(s, "code_cd", "") or ""),
                    )
                self._match_combo_by_text(cb_spec, str(src.get("spec_name") or src.get("size_name") or ""))
                self.tbl.setCellWidget(r, 0, cb_spec)

                cb_grade = QComboBox(); cb_grade.setStyleSheet(MainStyles.COMBO_TABLE_CELL_WORK_LOG)
                cb_grade.addItem("선택", "")
                for g in grades:
                    cb_grade.addItem(
                        str(self._row_value(g, "code_nm", "") or ""),
                        str(self._row_value(g, "code_cd", "") or ""),
                    )
                self._match_combo_by_text(cb_grade, str(src.get("grade_name") or ""))
                self.tbl.setCellWidget(r, 1, cb_grade)

                cb_crop = QComboBox(); cb_crop.setStyleSheet(MainStyles.COMBO_TABLE_CELL_WORK_LOG)
                self.tbl.setCellWidget(r, 2, cb_crop)
                self._reload_crop_combo(cb_crop, cb_grade.currentData() or "", str(src.get("grade_count_name") or ""))
                cb_grade.currentIndexChanged.connect(
                    lambda *_a, gcb=cb_grade, ccb=cb_crop: self._reload_crop_combo(ccb, gcb.currentData() or "", "")
                )

                self.tbl.setItem(r, 3, self._make_number_item(int(src.get("count") or 0)))
                self.tbl.setItem(r, 4, self._make_number_item(int(src.get("unit_price") or 0)))
                amt = int(src.get("amount") or 0) or int(src.get("count") or 0) * int(src.get("unit_price") or 0)
                self._set_amount_item(r, amt)
        finally:
            self._updating_table = False

    @staticmethod
    def _to_int(v) -> int:
        try:
            return int(float(str(v).replace(",", "").strip()))
        except Exception:
            return 0

    def _accept_payload(self):
        rows = []
        errs = []
        for r in range(self.tbl.rowCount()):
            spec_cb = self.tbl.cellWidget(r, 0)
            grade_cb = self.tbl.cellWidget(r, 1)
            crop_cb = self.tbl.cellWidget(r, 2)
            cnt = self._to_int(self.tbl.item(r, 3).text() if self.tbl.item(r, 3) else "0")
            price = self._to_int(self.tbl.item(r, 4).text() if self.tbl.item(r, 4) else "0")
            if not spec_cb.currentData():
                errs.append(f"{r+1}행 규격 미선택")
            if not grade_cb.currentData():
                errs.append(f"{r+1}행 등급 미선택")
            if not crop_cb.currentData():
                errs.append(f"{r+1}행 과수 미선택")
            if cnt <= 0 or price <= 0:
                errs.append(f"{r+1}행 건수/단가 확인")
            rows.append(
                {
                    "time": "",
                    "spec_name": spec_cb.currentText().strip(),
                    "size_cd": str(spec_cb.currentData() or "").strip(),
                    "grade_name": grade_cb.currentText().strip(),
                    "grade_cd": str(grade_cb.currentData() or "").strip(),
                    "grade_count_name": crop_cb.currentText().strip(),
                    "crop_nm": crop_cb.currentText().strip(),
                    "crop_cd": str(crop_cb.currentData() or "").strip(),
                    "count": cnt,
                    "unit_price": price,
                    "amount": cnt * price,
                }
            )
        if errs:
            QMessageBox.warning(self, "검증 오류", "\n".join(errs[:12]))
            return
        if not str(self.cmb_corp.currentData() or "").strip():
            QMessageBox.warning(self, "검증 오류", "상단 법인을 선택하세요.")
            return
        if not str(self.cmb_item.currentData() or "").strip():
            QMessageBox.warning(self, "검증 오류", "상단 품목을 선택하세요.")
            return
        if not str(self.cmb_variety.currentData() or "").strip():
            QMessageBox.warning(self, "검증 오류", "상단 품종을 선택하세요.")
            return
        self._result = {
            "common": {
                "target_date": self.edt_date.date().toString("yyyy-MM-dd"),
                "market_name": self.edt_market.text().strip(),
                "corp_name": self.cmb_corp.currentText().strip(),
                "custm_id": str(self.cmb_corp.currentData() or "").strip(),
                "item_name": self.cmb_item.currentText().strip(),
                "item_cd": str(self.cmb_item.currentData() or "").strip(),
                "variety_name": self.cmb_variety.currentText().strip(),
                "variety_cd": str(self.cmb_variety.currentData() or "").strip(),
            },
            "rows": rows,
        }
        self.accept()

    def get_payload(self):
        return self._result


# 시장분석 차트 공통 여백 (텍스트·축·플롯 충돌 완화)
CHART_TEXT_INSET_L = 4
# Y눈금 숫자만 두는 좌측 띠. 플롯·그리드·시리즈는 CHART_PLOT_INSET_L 오른쪽부터(값과 시각적으로 분리)
CHART_Y_AXIS_GUTTER_W = 56
CHART_Y_TICK_TO_PLOT_GAP = 6
CHART_PLOT_INSET_L = CHART_TEXT_INSET_L + CHART_Y_AXIS_GUTTER_W
CHART_MARGIN_R = 36
CHART_MARGIN_B = 30
# 플롯 아래 한 줄(Y최소·X날짜 공유)에 필요한 최소 세로 여유
CHART_X_AXIS_LABEL_ROW = 8
# 날짜 첫 글자가 Y축 눈금(좌측)과 수평 겹치지 않게 plot 경계에서 최소 이격
CHART_X_DATE_LEFT_PAD = 10
CHART_X_DATE_BASELINE_GAP = 3
# 플롯 세로: 하단 = 일반 여백 + X날짜 전용 행
CHART_PLOT_BOTTOM_MARGIN = CHART_MARGIN_B + CHART_X_AXIS_LABEL_ROW
# X축: 라벨 겹침 완화(우측 끝 여백 + 플롯 가로 스케일 동일 적용)
CHART_X_AXIS_END_PAD = 16.0
CHART_X_AXIS_MAX_DISPLAY_LABELS = 7
CHART_HOVER_TIP_STYLE = (
    f"QToolTip {{ background-color: #FFFFFF; color: #2D3748; "
    f"border: 1px solid #E2E8F0; padding: 6px; "
    f"font-family: '{DEFAULT_FONT_FAMILY}'; }}"
)
# 제목·값은 외부 QLabel — 플롯 상단만
CHART_BODY_MARGIN_T = 6
# Y최대 눈금(72,675·100% 등)을 플롯 밖(상단선 위)에만 두기 위한 세로 확보
CHART_Y_MAX_TICK_ROW = 16
CHART_PLOT_TOP_MARGIN = CHART_BODY_MARGIN_T + CHART_Y_MAX_TICK_ROW
# 헤더/범례/푸터 QLabel 우측 끝 = 플롯(chart_rect.right)과 맞춤 (paintEvent의 CHART_MARGIN_R과 동일)
CHART_HEADER_MARGIN_R = CHART_MARGIN_R

# 시장분석: 타이틀(10pt bold)만 강조. 축·날짜(_chart_font_axis 9pt #718096)과 동일 폰트로
# 우측값·범례 글자·푸터(캡션) 통일
CHART_AXIS_LABEL_FONT_PT = 9
CHART_AXIS_LABEL_COLOR = "#718096"
# QLabel은 부모/탭 스타일의 font-size(px)를 물려받을 수 있어, 축(QPainter 9pt)과 동일하게
# family·pt·weight를 스타일시트에 명시한다(setFont만으로는 픽셀 크기가 어긋날 수 있음).
_QAXIS_QLABEL_FONT = (
    f"font-family:'{DEFAULT_FONT_FAMILY}'; font-weight:normal;"
)
ANALYSIS_CHART_AUX_STYLE = (
    f"{_QAXIS_QLABEL_FONT} color:{CHART_AXIS_LABEL_COLOR}; border:none; background:transparent;"
)
ANALYSIS_CHART_FOOTER_STYLE = (
    f"{_QAXIS_QLABEL_FONT} color:{CHART_AXIS_LABEL_COLOR}; border:none; background:transparent;"
    "margin-top:2px; margin-bottom:5px;"
)
# 가격 구조 우측 4줄: 줄간만 조금 압축
ANALYSIS_STRUCTURE_VALUE_STYLE = (
    f"{_QAXIS_QLABEL_FONT} color:{CHART_AXIS_LABEL_COLOR}; border:none; background:transparent;"
    "line-height:1.1;"
)

# 1·3번 차트: 축 눈금 (8pt, #A0AEC0) — 2·4번은 기존 CHART_AXIS_LABEL_* 유지
CHART_REFINED_TICK_FONT_PT = 8
CHART_REFINED_TICK_COLOR = "#A0AEC0"
CHART_Y_TICK_MIN_COLOR = "#CBD5E0"
# 대표 가격 메인 라인·영역 그라데이션 기준색
REPRESENTATIVE_PRICE_LINE_COLOR = "#2F855A"
# 거래량 등 단일 추세 라인·영역 (SimpleTrendChartWidget)
VOLUME_TREND_LINE_COLOR = "#2B6CB0"
# 가격 구조 범례(QLabel): 8pt 본문 #718096, ●만 라인색과 동일
STRUCTURE_CHART_LEGEND_HTML = (
    f'<div style="font-family:\'{DEFAULT_FONT_FAMILY}\'; color:#718096;">'
    '<span style="color:#2F855A">●</span> 특≤20  '
    '<span style="color:#3182CE">●</span> 특≤25  '
    '<span style="color:#DD6B20">●</span> 상≤20  '
    '<span style="color:#805AD5">●</span> 상≤25'
    "</div>"
)
ANALYSIS_STRUCTURE_LEGEND_LABEL_STYLE = (
    f"font-family:'{DEFAULT_FONT_FAMILY}'; font-weight:normal;"
    "color:#718096; border:none; background:transparent;"
    "margin-top:2px; margin-bottom:0px;"
)
ANALYSIS_CHART12_FOOTER_STYLE = (
    f"font-family:'{DEFAULT_FONT_FAMILY}'; font-weight:normal;"
    "color:#A0AEC0; border:none; background:transparent;"
    "margin-top:2px; margin-bottom:5px;"
)


def _parse_trade_date(val):
    """trade_date(문자열 등) → date. 실패 시 None."""
    t = str(val or "").strip()
    if len(t) >= 10 and t[4] == "-" and t[7] == "-":
        try:
            return date(int(t[0:4]), int(t[5:7]), int(t[8:10]))
        except ValueError:
            pass
    return None


def _x_axis_date_label(dates: list, index: int) -> str:
    """첫 날·월(연) 변경 시 M/D, 같은 달은 일만."""
    if not dates or index < 0 or index >= len(dates):
        return ""
    d = dates[index]
    if d is None:
        return ""
    if index == 0:
        return f"{d.month}/{d.day}"
    prev = dates[index - 1]
    if prev is None:
        return f"{d.month}/{d.day}"
    if d.year != prev.year or d.month != prev.month:
        return f"{d.month}/{d.day}"
    return str(d.day)


def _x_axis_date_label_ymd(dates: list, index: int) -> str:
    """시장분석 4그래프 X축 통일: YYYY-MM-DD."""
    if not dates or index < 0 or index >= len(dates):
        return ""
    d = dates[index]
    if d is None:
        return ""
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def _x_axis_date_label_mmdd(dates: list, index: int) -> str:
    """대표 가격·가격 구조 X축: %m-%d."""
    if not dates or index < 0 or index >= len(dates):
        return ""
    d = dates[index]
    if d is None:
        return ""
    return f"{d.month:02d}-{d.day:02d}"


def _chart_plot_width_for_x(chart_rect: QRectF) -> float:
    """플롯 가로(데이터·X라벨 공통). 우측 CHART_X_AXIS_END_PAD 만큼 라벨 공간 확보."""
    return max(10.0, float(chart_rect.width()) - CHART_X_AXIS_END_PAD)


def _chart_x_at_index(chart_rect: QRectF, idx: int, n: int) -> float:
    """시장분석 차트: 인덱스 → x(좌~plot폭). n>=2."""
    if n < 2:
        return float(chart_rect.left())
    w = _chart_plot_width_for_x(chart_rect)
    return float(chart_rect.left()) + (idx / (n - 1)) * w


def _chart_x_axis_tick_indices(dates: list) -> list:
    """최대 CHART_X_AXIS_MAX_DISPLAY_LABELS개 근방, 등간격 step + 마지막 인덱스 항상 포함."""
    n = len(dates)
    if n < 2:
        return [0] if n == 1 else []
    last_i = n - 1
    cap = max(2, min(CHART_X_AXIS_MAX_DISPLAY_LABELS, n))
    step = max(1, (last_i + cap - 2) // max(1, cap - 1))
    idxs = list(range(0, last_i + 1, step))
    if idxs[-1] != last_i:
        idxs.append(last_i)
    return sorted(set(idxs))


def _analysis_chart_plot_rect(w: int, h: int) -> QRectF:
    """paintEvent와 동일한 플롯 사각형."""
    left, top, right, bottom = (
        CHART_PLOT_INSET_L,
        CHART_PLOT_TOP_MARGIN,
        CHART_MARGIN_R,
        CHART_PLOT_BOTTOM_MARGIN,
    )
    return QRectF(
        left,
        top,
        max(10, w - left - right),
        max(10, h - top - bottom),
    )


def _chart_hover_index_from_x(mx: float, chart_rect: QRectF, n: int) -> int | None:
    """플롯 내 x → 가장 가까운 데이터 인덱스. 플롯 밖이면 None."""
    if n < 2:
        return None
    left = float(chart_rect.left())
    w_plot = _chart_plot_width_for_x(chart_rect)
    if mx < left - 1 or mx > left + w_plot + 1:
        return None
    t = (mx - left) / w_plot
    t = max(0.0, min(1.0, t))
    idx = int(round(t * (n - 1)))
    return max(0, min(n - 1, idx))


def _legend_line_short(name: str) -> str:
    """hover용 짧은 라벨(괄호 앞만)."""
    s = str(name or "").strip()
    if "(" in s:
        return s.split("(", 1)[0].strip()
    return s


def _apply_chart_size_policy_expand_horizontal(widget: QWidget) -> None:
    """요약 카드와 동일 폭으로 보이도록 가로로 확장."""
    widget.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )


def _create_analysis_chart_block(
    chart_widget: QWidget,
    *,
    footer_style_sheet: str | None = None,
):
    """시장분석 4그래프 공통: 헤더(제목+우측값) + 차트 + 푸터."""
    block = QWidget()
    _apply_chart_size_policy_expand_horizontal(block)
    lay = QVBoxLayout(block)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(1)
    header = QHBoxLayout()
    header.setContentsMargins(CHART_TEXT_INSET_L, 0, CHART_HEADER_MARGIN_R, 0)
    header.setSpacing(10)
    title_label = QLabel("")
    title_label.setStyleSheet(MainStyles.DASH_SUBCARD_TITLE + " color:#2D3748;")
    title_label.setWordWrap(False)
    title_label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )
    value_label = QLabel("")
    value_label.setStyleSheet(ANALYSIS_CHART_AUX_STYLE)
    value_label.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
    )
    value_label.setWordWrap(True)
    value_label.setMaximumWidth(240)
    header.addWidget(title_label, 1)
    header.addWidget(value_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    footer_label = QLabel("")
    fss = footer_style_sheet if footer_style_sheet is not None else ANALYSIS_CHART_FOOTER_STYLE
    footer_label.setStyleSheet(fss)
    footer_label.setWordWrap(True)
    footer_label.setContentsMargins(0, 0, CHART_HEADER_MARGIN_R, 0)
    lay.addLayout(header)
    lay.addWidget(chart_widget)
    lay.addWidget(footer_label)
    return block, title_label, value_label, footer_label


def _create_price_structure_chart_block(
    chart_widget: QWidget,
    *,
    legend_style_sheet: str | None = None,
    footer_style_sheet: str | None = None,
    title_right_widget: QWidget | None = None,
):
    """가격 구조: 헤더 + 작은 범례 + 차트 + 푸터. title_right_widget: 타이틀 바로 우측(예: 가격 기준 콤보)."""
    block = QWidget()
    _apply_chart_size_policy_expand_horizontal(block)
    lay = QVBoxLayout(block)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(1)
    header = QHBoxLayout()
    header.setContentsMargins(CHART_TEXT_INSET_L, 0, CHART_HEADER_MARGIN_R, 0)
    header.setSpacing(10)
    title_label = QLabel("")
    title_label.setStyleSheet(MainStyles.DASH_SUBCARD_TITLE + " color:#2D3748;")
    title_label.setWordWrap(False)
    title_label.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Preferred,
    )
    value_label = QLabel("")
    value_label.setStyleSheet(ANALYSIS_STRUCTURE_VALUE_STYLE)
    value_label.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
    )
    value_label.setWordWrap(True)
    value_label.setMaximumWidth(240)
    header.addWidget(title_label, 0)
    if title_right_widget is not None:
        header.addWidget(title_right_widget, 0)
    header.addStretch(1)
    header.addWidget(value_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    legend_label = QLabel("")
    legend_label.setTextFormat(Qt.TextFormat.RichText)
    legend_label.setText(STRUCTURE_CHART_LEGEND_HTML)
    legend_label.setContentsMargins(CHART_TEXT_INSET_L, 3, CHART_HEADER_MARGIN_R, 0)
    lss = legend_style_sheet if legend_style_sheet is not None else ANALYSIS_STRUCTURE_LEGEND_LABEL_STYLE
    legend_label.setStyleSheet(lss)
    footer_label = QLabel("")
    fss = footer_style_sheet if footer_style_sheet is not None else ANALYSIS_CHART_FOOTER_STYLE
    footer_label.setStyleSheet(fss)
    footer_label.setWordWrap(True)
    footer_label.setContentsMargins(0, 0, CHART_HEADER_MARGIN_R, 0)
    lay.addLayout(header)
    lay.addWidget(legend_label)
    lay.addWidget(chart_widget)
    lay.addWidget(footer_label)
    return block, title_label, value_label, legend_label, footer_label


def _chart_y_tick_x(p: QPainter, text: str, plot_left: float) -> int:
    """
    Y눈금을 좌측 전용 띠 안에 오른쪽 정렬.
    plot_left는 데이터 플롯의 왼쪽 경계; 숫자 오른쪽 끝과 플롯 사이에 CHART_Y_TICK_TO_PLOT_GAP 유지.
    """
    tw = p.fontMetrics().horizontalAdvance(text)
    x = int(plot_left) - CHART_Y_TICK_TO_PLOT_GAP - tw
    return max(CHART_TEXT_INSET_L, x)


def _chart_shared_bottom_label_baseline_y(chart_rect: QRectF, fm) -> int:
    """Y최소 눈금과 X날짜를 동일 baseline에 둠(플롯 하단선·데이터 포인트와 겹침 방지)."""
    return int(chart_rect.bottom() + fm.ascent() + CHART_X_DATE_BASELINE_GAP)


def _chart_shared_top_max_label_baseline_y(chart_rect: QRectF, fm) -> int:
    """
    Y최댓값·100% 눈금 baseline.
    이전에는 top + ascent로 플롯 내부에 글자를 그려 최고 그리드·시리즈와 겹쳤음.
    chart_rect.top()이 플롯 상단선이므로, 글자 하단이 그 선 위에 오도록 baseline을 위로 뺀다.
    """
    return int(chart_rect.top() - 2 - fm.descent())


def _paint_chart_x_axis_dates(
    p: QPainter,
    chart_rect: QRectF,
    dates: list,
    *,
    label_fn=None,
    axis_font=None,
    axis_color: str | None = None,
):
    """trade_date 기준 축 라벨. baseline은 플롯 하단(chart_rect.bottom) 기준으로 Y눈금과 겹치지 않게 배치."""
    n = len(dates)
    if n < 2:
        return
    clr = axis_color if axis_color is not None else CHART_AXIS_LABEL_COLOR
    p.setPen(QPen(QColor(clr), 1))
    fm = p.fontMetrics()
    y = _chart_shared_bottom_label_baseline_y(chart_rect, fm)
    tick_idxs = _chart_x_axis_tick_indices(dates)
    for ti in tick_idxs:
        lab = (
            label_fn(dates, ti)
            if label_fn is not None
            else _x_axis_date_label(dates, ti)
        )
        if not lab:
            continue
        tw = fm.horizontalAdvance(lab)
        x_center = _chart_x_at_index(chart_rect, ti, n)
        x = int(x_center - tw / 2)
        min_x = int(chart_rect.left() + CHART_X_DATE_LEFT_PAD)
        plot_right = chart_rect.left() + _chart_plot_width_for_x(chart_rect)
        max_x = int(plot_right - tw - 2)
        if x < min_x:
            x = min_x
        if x > max_x:
            x = max_x
        p.drawText(x, y, lab)


def _chart_font_body():
    f = QFont()
    f.setPointSize(9)
    f.setBold(False)
    return f


def _chart_font_axis():
    """가로·세로 축 눈금·날짜 — QLabel의 make_app_font와 동일(맑은 고딕 등)."""
    f = QFont()
    f.setPointSize(CHART_AXIS_LABEL_FONT_PT)
    return f


def _chart_font_axis_refined():
    """1·3번 차트 축: 8pt (스펙 #A0AEC0는 펜 색으로 별도 지정)."""
    f = QFont()
    f.setPointSize(CHART_REFINED_TICK_FONT_PT)
    return f


def _paint_analysis_chart_grid(
    p: QPainter,
    chart_rect: QRectF,
    dates: list,
    n_points: int,
) -> None:
    """점선 그리드 — matplotlib grid(True, linestyle='--', color='#E2E8F0') 대응."""
    pen = QPen(QColor("#E2E8F0"))
    pen.setWidthF(0.5)
    pen.setStyle(Qt.PenStyle.DashLine)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    for i in range(5):
        t = i / 4.0
        y = chart_rect.bottom() - t * chart_rect.height()
        p.drawLine(QPointF(chart_rect.left(), y), QPointF(chart_rect.right(), y))
    if n_points >= 2 and dates:
        for ti in _chart_x_axis_tick_indices(dates):
            x = _chart_x_at_index(chart_rect, ti, n_points)
            p.drawLine(QPointF(x, chart_rect.top()), QPointF(x, chart_rect.bottom()))


def _paint_analysis_chart_spines(p: QPainter, chart_rect: QRectF) -> None:
    """상·우 스파인 숨김, 좌·하만 #E2E8F0."""
    spine_pen = QPen(QColor("#E2E8F0"))
    spine_pen.setWidthF(1.0)
    p.setPen(spine_pen)
    p.drawLine(
        QPointF(chart_rect.left(), chart_rect.top()),
        QPointF(chart_rect.left(), chart_rect.bottom()),
    )
    p.drawLine(
        QPointF(chart_rect.left(), chart_rect.bottom()),
        QPointF(chart_rect.right(), chart_rect.bottom()),
    )


def _paint_chart_gradient_fill_line_area(
    p: QPainter,
    chart_rect: QRectF,
    points_xy: list,
    color_hex: str,
    *,
    top_alpha: float = 0.25,
) -> None:
    """라인~x축 사이 영역 세로 그라데이션 (하단 투명 → 상단 rgba 알파). fill_between 단색 대체."""
    if len(points_xy) < 2:
        return
    path = QPainterPath()
    path.moveTo(chart_rect.left(), chart_rect.bottom())
    path.lineTo(points_xy[0].x(), chart_rect.bottom())
    path.lineTo(points_xy[0])
    for i in range(1, len(points_xy)):
        path.lineTo(points_xy[i])
    path.lineTo(points_xy[-1].x(), chart_rect.bottom())
    plot_right = chart_rect.left() + _chart_plot_width_for_x(chart_rect)
    path.lineTo(plot_right, chart_rect.bottom())
    path.closeSubpath()
    c = QColor(color_hex)
    g = QLinearGradient(chart_rect.bottomLeft(), chart_rect.topLeft())
    t0 = QColor(c)
    t0.setAlpha(0)
    t1 = QColor(c)
    t1.setAlpha(min(255, max(0, int(255 * top_alpha))))
    g.setColorAt(0.0, t0)
    g.setColorAt(1.0, t1)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawPath(path)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _paint_chart_gradient_fill_segment_area(
    p: QPainter,
    chart_rect: QRectF,
    seg_xy: list,
    color_hex: str,
    *,
    top_alpha: float = 0.25,
) -> None:
    """구간 단절 시계열 한 덩어리씩 그라데이션 영역."""
    if len(seg_xy) < 2:
        return
    path = QPainterPath()
    path.moveTo(seg_xy[0].x(), chart_rect.bottom())
    path.lineTo(seg_xy[0])
    for i in range(1, len(seg_xy)):
        path.lineTo(seg_xy[i])
    path.lineTo(seg_xy[-1].x(), chart_rect.bottom())
    path.closeSubpath()
    c = QColor(color_hex)
    g = QLinearGradient(chart_rect.bottomLeft(), chart_rect.topLeft())
    t0 = QColor(c)
    t0.setAlpha(0)
    t1 = QColor(c)
    t1.setAlpha(min(255, max(0, int(255 * top_alpha))))
    g.setColorAt(0.0, t0)
    g.setColorAt(1.0, t1)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawPath(path)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _simple_trend_line_xy_runs(points: list, points_xy: list, volume_mode: bool) -> list:
    """SimpleTrendChartWidget의 drawLine과 동일 조건으로 연속 구간 QPointF 목록."""
    runs = []
    cur = []
    n = len(points_xy)
    for idx in range(1, n):
        a, b = points_xy[idx - 1], points_xy[idx]
        if a is None or b is None:
            if len(cur) >= 2:
                runs.append(cur[:])
            cur = []
            continue
        _, v0 = points[idx - 1]
        _, v1 = points[idx]
        try:
            f0 = float(v0) if v0 is not None else None
            f1 = float(v1) if v1 is not None else None
        except Exception:
            if len(cur) >= 2:
                runs.append(cur[:])
            cur = []
            continue
        if volume_mode and (f0 is None or f1 is None or f0 <= 0 or f1 <= 0):
            if len(cur) >= 2:
                runs.append(cur[:])
            cur = []
            continue
        if not cur:
            cur.append(a)
        cur.append(b)
    if len(cur) >= 2:
        runs.append(cur)
    return runs


class SimpleTrendChartWidget(QWidget):
    """거래량 등 단일 시계열. 기준일 값은 우측 상단 고정, 0거래량은 회색 점."""

    def __init__(self, title: str, unit: str = "", parent=None):
        super().__init__(parent)
        self._title = str(title or "")
        self._unit = str(unit or "")
        self._points = []
        self._base_index = -1
        self._annotate_base_value = False
        self._annotation_suffix = ""
        self._volume_mode = False
        self._date_start_mmdd = ""
        self._date_end_mmdd = ""
        self._unit_caption = ""
        self.setMinimumHeight(175)
        self.setMouseTracking(True)
        self.setStyleSheet(CHART_HOVER_TIP_STYLE)
        self._hover_tip_idx = None

    def set_title(self, title: str):
        self._title = str(title or "")
        self.update()

    def set_volume_mode(self, enabled: bool):
        self._volume_mode = bool(enabled)
        self.update()

    def set_date_range_caption(self, start_mmdd: str, end_mmdd: str):
        self._date_start_mmdd = str(start_mmdd or "").strip()
        self._date_end_mmdd = str(end_mmdd or "").strip()
        self.update()

    def set_unit_caption(self, text: str):
        self._unit_caption = str(text or "").strip()
        self.update()

    def set_chart_data(self, points, base_index: int = -1):
        self._points = list(points or [])
        self._base_index = int(base_index)
        self.update()

    def set_base_value_annotation(self, enabled: bool, suffix: str = ""):
        self._annotate_base_value = bool(enabled)
        self._annotation_suffix = str(suffix or "")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#FFFFFF"))

        if len(self._points) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        values = []
        for _, v in self._points:
            if v is None:
                continue
            try:
                fv = float(v)
            except Exception:
                continue
            if self._volume_mode and fv <= 0:
                continue
            values.append(fv)
        if len(values) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        left, top, right, bottom = (
            CHART_PLOT_INSET_L,
            CHART_PLOT_TOP_MARGIN,
            CHART_MARGIN_R,
            CHART_PLOT_BOTTOM_MARGIN,
        )
        chart_rect = QRectF(
            left,
            top,
            max(10, self.width() - left - right),
            max(10, self.height() - top - bottom),
        )

        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v = min_v + 1.0

        n_pt = len(self._points)

        def to_xy(idx, value):
            x = _chart_x_at_index(chart_rect, idx, n_pt)
            y_ratio = (float(value) - min_v) / (max_v - min_v)
            y = chart_rect.bottom() - (y_ratio * chart_rect.height())
            return QPointF(x, y)

        def val_for_plot(i):
            _, v = self._points[i]
            if v is None:
                return None
            try:
                fv = float(v)
            except Exception:
                return None
            if self._volume_mode and fv <= 0:
                return min_v
            return fv

        points_xy = []
        for i in range(len(self._points)):
            vp = val_for_plot(i)
            if vp is None:
                points_xy.append(None)
            else:
                points_xy.append(to_xy(i, vp))

        dates = [_parse_trade_date(row[0]) for row in self._points]
        for seg in _simple_trend_line_xy_runs(self._points, points_xy, self._volume_mode):
            _paint_chart_gradient_fill_segment_area(
                p, chart_rect, seg, VOLUME_TREND_LINE_COLOR, top_alpha=0.25
            )

        _paint_analysis_chart_grid(p, chart_rect, dates, len(self._points))
        _paint_analysis_chart_spines(p, chart_rect)

        line_col = QColor(VOLUME_TREND_LINE_COLOR)
        main_pen = QPen(line_col)
        main_pen.setWidthF(1.5)
        main_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(main_pen)
        for idx in range(1, len(points_xy)):
            a, b = points_xy[idx - 1], points_xy[idx]
            if a is None or b is None:
                continue
            _, v0 = self._points[idx - 1]
            _, v1 = self._points[idx]
            try:
                f0 = float(v0) if v0 is not None else None
                f1 = float(v1) if v1 is not None else None
            except Exception:
                continue
            if self._volume_mode and (f0 is None or f1 is None or f0 <= 0 or f1 <= 0):
                continue
            p.drawLine(a, b)

        for i, pt in enumerate(points_xy):
            if pt is None:
                continue
            _, v = self._points[i]
            try:
                fv = float(v) if v is not None else 0.0
            except Exception:
                fv = 0.0
            if self._volume_mode and fv <= 0:
                p.setBrush(QColor("#A0AEC0"))
                p.setPen(QPen(QColor("#A0AEC0"), 1))
                p.drawEllipse(pt, 2.0, 2.0)
            else:
                p.setBrush(line_col)
                p.setPen(QPen(line_col, 1))
                p.drawEllipse(pt, 2.5, 2.5)

        fm_ax = p.fontMetrics()
        y_bot = _chart_shared_bottom_label_baseline_y(chart_rect, fm_ax)
        y_top = _chart_shared_top_max_label_baseline_y(chart_rect, fm_ax)
        pl = float(chart_rect.left())
        min_txt = f"{int(round(min_v)):,}{self._unit}"
        max_txt = f"{int(round(max_v)):,}{self._unit}"
        p.setPen(QPen(QColor(CHART_Y_TICK_MIN_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, min_txt, pl), y_bot, min_txt)
        p.setPen(QPen(QColor(CHART_REFINED_TICK_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, max_txt, pl), y_top, max_txt)

        _paint_chart_x_axis_dates(
            p,
            chart_rect,
            dates,
            label_fn=_x_axis_date_label_mmdd,
            axis_font=_chart_font_axis_refined(),
            axis_color=CHART_REFINED_TICK_COLOR,
        )

    def leaveEvent(self, event):
        QToolTip.hideText()
        self._hover_tip_idx = None
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if len(self._points) < 2:
            return
        values = []
        for _, v in self._points:
            if v is None:
                continue
            try:
                fv = float(v)
            except Exception:
                continue
            if self._volume_mode and fv <= 0:
                continue
            values.append(fv)
        if len(values) < 2:
            return
        cr = _analysis_chart_plot_rect(self.width(), self.height())
        n = len(self._points)
        idx = _chart_hover_index_from_x(event.position().x(), cr, n)
        if idx is None:
            if self._hover_tip_idx is not None:
                QToolTip.hideText()
                self._hover_tip_idx = None
            return
        d = _parse_trade_date(self._points[idx][0])
        if d is None:
            return
        mmdd = _x_axis_date_label_mmdd([d], 0)
        _, raw_v = self._points[idx]
        if self._volume_mode:
            try:
                qv = float(raw_v) if raw_v is not None else None
            except Exception:
                qv = None
            if qv is None or qv <= 0:
                tip = f"{mmdd}\n—"
            else:
                tip = f"{mmdd}\n{int(round(qv)):,}{self._unit}"
        else:
            if raw_v is None:
                return
            try:
                tip = f"{mmdd}\n{float(raw_v):,.0f}{self._unit}"
            except Exception:
                return
        if self._hover_tip_idx != idx:
            self._hover_tip_idx = idx
            QToolTip.showText(
                self.mapToGlobal(event.position().toPoint()) + QPoint(12, 12),
                tip,
                self,
            )


class RepresentativePriceChartWidget(QWidget):
    """대표 가격 추이(흐름만 플롯). 대표값은 상위 header QLabel."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = str(title or "")
        self._points = []
        self._base_index = -1
        self._ref_lines = []
        self._date_start_mmdd = ""
        self._date_end_mmdd = ""
        self.setMinimumHeight(175)
        self.setMouseTracking(True)
        self.setStyleSheet(CHART_HOVER_TIP_STYLE)
        self._hover_tip_idx = None

    def set_title(self, title: str):
        self._title = str(title or "")
        self.update()

    def set_date_range_caption(self, start_mmdd: str, end_mmdd: str):
        self._date_start_mmdd = str(start_mmdd or "").strip()
        self._date_end_mmdd = str(end_mmdd or "").strip()
        self.update()

    def set_chart_data(self, points, base_index: int = -1):
        self._points = list(points or [])
        self._base_index = int(base_index)
        self.update()

    def set_reference_lines(self, lines):
        self._ref_lines = list(lines or [])
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#FFFFFF"))

        if len(self._points) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        values = [float(v) for _, v in self._points if v is not None]
        if len(values) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        left, top, right, bottom = (
            CHART_PLOT_INSET_L,
            CHART_PLOT_TOP_MARGIN,
            CHART_MARGIN_R,
            CHART_PLOT_BOTTOM_MARGIN,
        )
        chart_rect = QRectF(
            left,
            top,
            max(10, self.width() - left - right),
            max(10, self.height() - top - bottom),
        )

        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v = min_v + 1.0

        n_pt = len(self._points)

        def to_xy(idx, value):
            x = _chart_x_at_index(chart_rect, idx, n_pt)
            y_ratio = (float(value) - min_v) / (max_v - min_v)
            y = chart_rect.bottom() - (y_ratio * chart_rect.height())
            return QPointF(x, y)

        dates = [_parse_trade_date(pt[0]) for pt in self._points]
        points_xy = [
            to_xy(i, v if v is not None else min_v) for i, (_, v) in enumerate(self._points)
        ]
        _paint_chart_gradient_fill_line_area(
            p, chart_rect, points_xy, REPRESENTATIVE_PRICE_LINE_COLOR, top_alpha=0.35
        )
        _paint_analysis_chart_grid(p, chart_rect, dates, len(self._points))
        _paint_analysis_chart_spines(p, chart_rect)

        line_col = QColor(REPRESENTATIVE_PRICE_LINE_COLOR)
        main_pen = QPen(line_col)
        main_pen.setWidthF(1.5)
        main_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(main_pen)
        for idx in range(1, len(points_xy)):
            p.drawLine(points_xy[idx - 1], points_xy[idx])

        p.setBrush(line_col)
        p.setPen(QPen(line_col, 1))
        marker_r = 2.75
        for pt in points_xy:
            p.drawEllipse(pt, marker_r, marker_r)

        fm_ax = p.fontMetrics()
        y_bot = _chart_shared_bottom_label_baseline_y(chart_rect, fm_ax)
        y_top = _chart_shared_top_max_label_baseline_y(chart_rect, fm_ax)
        pl = float(chart_rect.left())
        mn = f"{int(round(min_v)):,}"
        mx = f"{int(round(max_v)):,}"
        p.setPen(QPen(QColor(CHART_Y_TICK_MIN_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, mn, pl), y_bot, mn)
        p.setPen(QPen(QColor(CHART_REFINED_TICK_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, mx, pl), y_top, mx)

        _paint_chart_x_axis_dates(
            p,
            chart_rect,
            dates,
            label_fn=_x_axis_date_label_mmdd,
            axis_font=_chart_font_axis_refined(),
            axis_color=CHART_REFINED_TICK_COLOR,
        )

    def leaveEvent(self, event):
        QToolTip.hideText()
        self._hover_tip_idx = None
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if len(self._points) < 2:
            return
        values = [float(v) for _, v in self._points if v is not None]
        if len(values) < 2:
            return
        cr = _analysis_chart_plot_rect(self.width(), self.height())
        n = len(self._points)
        idx = _chart_hover_index_from_x(event.position().x(), cr, n)
        if idx is None:
            if self._hover_tip_idx is not None:
                QToolTip.hideText()
                self._hover_tip_idx = None
            return
        d = _parse_trade_date(self._points[idx][0])
        if d is None:
            return
        mmdd = _x_axis_date_label_mmdd([d], 0)
        _, pv = self._points[idx]
        if pv is None:
            return
        try:
            tip = f"{mmdd}\n{float(pv):,.0f}원"
        except Exception:
            return
        if self._hover_tip_idx != idx:
            self._hover_tip_idx = idx
            QToolTip.showText(
                self.mapToGlobal(event.position().toPoint()) + QPoint(12, 12),
                tip,
                self,
            )


class MultiLinePriceChartWidget(QWidget):
    """
    settlement 기반 가격 구조: 4라인 + 주/보조 마커(면 채움 없음).
    None 구간은 선 끊김, 0은 미사용.
    """

    # 주: 특≤20·상≤20 / 보조: 특≤25·상≤25
    _SERIES_DEF = (
        ("특≤20", 1, "#2F855A", Qt.PenStyle.SolidLine, 1.75),
        ("특≤25", 2, "#3182CE", Qt.PenStyle.SolidLine, 1.3),
        ("상≤20", 3, "#DD6B20", Qt.PenStyle.SolidLine, 1.75),
        ("상≤25", 4, "#805AD5", Qt.PenStyle.SolidLine, 1.3),
    )
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = str(title or "")
        self._points = []
        self._base_index = -1
        self._date_start_mmdd = ""
        self._date_end_mmdd = ""
        self._basis_caption = ""
        self._y_axis_caption = ""
        self.setMinimumHeight(230)
        self.setMouseTracking(True)
        self.setStyleSheet(CHART_HOVER_TIP_STYLE)
        self._hover_tip_key = None

    def set_title(self, title: str):
        self._title = str(title or "")
        self.update()

    def set_basis_caption(self, text: str):
        self._basis_caption = str(text or "").strip()
        self.update()

    def set_y_axis_caption(self, text: str):
        self._y_axis_caption = str(text or "").strip()
        self.update()

    def set_date_range_caption(self, start_mmdd: str, end_mmdd: str):
        self._date_start_mmdd = str(start_mmdd or "").strip()
        self._date_end_mmdd = str(end_mmdd or "").strip()
        self.update()

    def set_structure_data(self, points, base_index: int = -1):
        """points: (trade_date, special_20, special_25, gradeA_20, gradeA_25) 튜플 리스트."""
        self._points = list(points or [])
        self._base_index = int(base_index)
        self.update()

    def _valid_y(self, v):
        if v is None:
            return None
        try:
            x = float(v)
        except Exception:
            return None
        return x if x > 0 else None

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#FFFFFF"))

        p.setBrush(Qt.BrushStyle.NoBrush)

        if len(self._points) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        values = []
        for pt in self._points:
            for i in range(1, 5):
                vy = self._valid_y(pt[i] if len(pt) > i else None)
                if vy is not None:
                    values.append(vy)
        if len(values) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        left = CHART_PLOT_INSET_L
        top = CHART_PLOT_TOP_MARGIN
        right = CHART_MARGIN_R
        bottom = CHART_PLOT_BOTTOM_MARGIN
        chart_rect = QRectF(
            left,
            top,
            max(10, self.width() - left - right),
            max(10, self.height() - top - bottom),
        )

        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v = min_v + 1.0

        n_pt = len(self._points)

        def to_xy(idx, value):
            x = _chart_x_at_index(chart_rect, idx, n_pt)
            y_ratio = (float(value) - min_v) / (max_v - min_v)
            y = chart_rect.bottom() - (y_ratio * chart_rect.height())
            return QPointF(x, y)

        dates = [_parse_trade_date(pt[0]) for pt in self._points]

        _paint_analysis_chart_grid(p, chart_rect, dates, len(self._points))
        _paint_analysis_chart_spines(p, chart_rect)

        for _label, col_idx, color_hex, pen_style, pen_w in self._SERIES_DEF:
            col = QColor(color_hex)
            pen = QPen(col, 1, pen_style)
            pen.setWidthF(float(pen_w))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            last_xy = None
            for i, pt in enumerate(self._points):
                vy = self._valid_y(pt[col_idx] if len(pt) > col_idx else None)
                if vy is None:
                    last_xy = None
                    continue
                xy = to_xy(i, vy)
                if last_xy is not None:
                    p.drawLine(last_xy, xy)
                last_xy = xy

        for _label, col_idx, color_hex, _pen_style, _pen_w in self._SERIES_DEF:
            is_primary = col_idx in (1, 3)
            mr = 2.5 if is_primary else 1.9
            mc = QColor(color_hex)
            if not is_primary:
                mc.setAlphaF(0.7)
            p.setBrush(mc)
            p.setPen(QPen(mc, 1))
            for i, pt in enumerate(self._points):
                vy = self._valid_y(pt[col_idx] if len(pt) > col_idx else None)
                if vy is None:
                    continue
                xy = to_xy(i, vy)
                p.drawEllipse(xy, mr, mr)

        fm_ax = p.fontMetrics()
        y_bot = _chart_shared_bottom_label_baseline_y(chart_rect, fm_ax)
        y_top = _chart_shared_top_max_label_baseline_y(chart_rect, fm_ax)
        pl = float(chart_rect.left())
        mn = f"{int(round(min_v)):,}"
        mx = f"{int(round(max_v)):,}"
        p.setPen(QPen(QColor(CHART_Y_TICK_MIN_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, mn, pl), y_bot, mn)
        p.setPen(QPen(QColor(CHART_REFINED_TICK_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, mx, pl), y_top, mx)

        _paint_chart_x_axis_dates(
            p,
            chart_rect,
            dates,
            label_fn=_x_axis_date_label_mmdd,
            axis_font=_chart_font_axis_refined(),
            axis_color=CHART_REFINED_TICK_COLOR,
        )

    def leaveEvent(self, event):
        QToolTip.hideText()
        self._hover_tip_key = None
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if len(self._points) < 2:
            return
        values = []
        for pt in self._points:
            for i in range(1, 5):
                vy = self._valid_y(pt[i] if len(pt) > i else None)
                if vy is not None:
                    values.append(vy)
        if len(values) < 2:
            return
        cr = _analysis_chart_plot_rect(self.width(), self.height())
        n = len(self._points)
        idx = _chart_hover_index_from_x(event.position().x(), cr, n)
        if idx is None:
            if self._hover_tip_key is not None:
                QToolTip.hideText()
                self._hover_tip_key = None
            return
        my = event.position().y()
        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v = min_v + 1.0

        def y_for_val(val: float) -> float:
            y_ratio = (float(val) - min_v) / (max_v - min_v)
            return cr.bottom() - (y_ratio * cr.height())

        best_label = None
        best_vy = None
        best_d = 1e18
        row = self._points[idx]
        for label, col_idx, _c, _s, _w in self._SERIES_DEF:
            vy = self._valid_y(row[col_idx] if len(row) > col_idx else None)
            if vy is None:
                continue
            d = abs(my - y_for_val(vy))
            if d < best_d:
                best_d = d
                best_label = label
                best_vy = vy
        if best_label is None or best_vy is None:
            if self._hover_tip_key is not None:
                QToolTip.hideText()
                self._hover_tip_key = None
            return
        if best_d > 36.0:
            if self._hover_tip_key is not None:
                QToolTip.hideText()
                self._hover_tip_key = None
            return
        dte = _parse_trade_date(row[0])
        if dte is None:
            return
        mmdd = _x_axis_date_label_mmdd([dte], 0)
        tip = f"{best_label}\n{mmdd}\n{int(round(best_vy)):,}원"
        key = (idx, best_label)
        if self._hover_tip_key != key:
            self._hover_tip_key = key
            QToolTip.showText(
                self.mapToGlobal(event.position().toPoint()) + QPoint(12, 12),
                tip,
                self,
            )


class DualRatioTrendChartWidget(QWidget):
    """특품·20과 비중. 세로축 0~100 고정, 기준일 값은 우측 상단 고정 텍스트."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = str(title or "")
        self._points = []
        self._base_index = -1
        self._legend_a = ""
        self._legend_b = ""
        self._date_start_mmdd = ""
        self._date_end_mmdd = ""
        self.setMinimumHeight(185)
        self.setMouseTracking(True)
        self.setStyleSheet(CHART_HOVER_TIP_STYLE)
        self._hover_tip_idx = None

    def set_title(self, title: str):
        self._title = str(title or "")
        self.update()

    def set_date_range_caption(self, start_mmdd: str, end_mmdd: str):
        self._date_start_mmdd = str(start_mmdd or "").strip()
        self._date_end_mmdd = str(end_mmdd or "").strip()
        self.update()

    def set_dual_chart_data(self, points, base_index: int, legend_a: str, legend_b: str):
        self._points = list(points or [])
        self._base_index = int(base_index)
        self._legend_a = str(legend_a or "")
        self._legend_b = str(legend_b or "")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#FFFFFF"))

        if len(self._points) < 2:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        has_any = False
        for _, a, b in self._points:
            if a is not None or b is not None:
                has_any = True
                break
        if not has_any:
            p.setPen(QPen(QColor("#A0AEC0"), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "표시할 데이터가 부족합니다.")
            return

        left, top, right, bottom = (
            CHART_PLOT_INSET_L,
            CHART_PLOT_TOP_MARGIN,
            CHART_MARGIN_R,
            CHART_PLOT_BOTTOM_MARGIN,
        )
        chart_rect = QRectF(
            left,
            top,
            max(10, self.width() - left - right),
            max(10, self.height() - top - bottom),
        )

        min_v, max_v = 0.0, 100.0
        n_pt = len(self._points)

        def clamp_pct(v):
            try:
                x = float(v)
            except Exception:
                return None
            return max(0.0, min(100.0, x))

        def to_xy(idx, value):
            x = _chart_x_at_index(chart_rect, idx, n_pt)
            y_ratio = (float(value) - min_v) / (max_v - min_v)
            y = chart_rect.bottom() - (y_ratio * chart_rect.height())
            return QPointF(x, y)

        def dual_ratio_xy_runs(getter):
            runs = []
            cur = []
            for i, t in enumerate(self._points):
                v = getter(t)
                cv = clamp_pct(v) if v is not None else None
                if cv is None:
                    if len(cur) >= 2:
                        runs.append(cur[:])
                    cur = []
                    continue
                cur.append(to_xy(i, cv))
            if len(cur) >= 2:
                runs.append(cur)
            return runs

        dates = [_parse_trade_date(row[0]) for row in self._points]
        color_a, color_b = "#2B6CB0", "#2F855A"
        for seg in dual_ratio_xy_runs(lambda t: t[1]):
            _paint_chart_gradient_fill_segment_area(
                p, chart_rect, seg, color_a, top_alpha=0.15
            )
        for seg in dual_ratio_xy_runs(lambda t: t[2]):
            _paint_chart_gradient_fill_segment_area(
                p, chart_rect, seg, color_b, top_alpha=0.15
            )

        _paint_analysis_chart_grid(p, chart_rect, dates, len(self._points))
        _paint_analysis_chart_spines(p, chart_rect)

        def line_for(getter, color_hex):
            col = QColor(color_hex)
            pen = QPen(col)
            pen.setWidthF(1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            last_xy = None
            for i, t in enumerate(self._points):
                v = getter(t)
                cv = clamp_pct(v) if v is not None else None
                if cv is None:
                    last_xy = None
                    continue
                xy = to_xy(i, cv)
                if last_xy is not None:
                    p.drawLine(last_xy, xy)
                last_xy = xy
            for i, t in enumerate(self._points):
                v = getter(t)
                cv = clamp_pct(v) if v is not None else None
                if cv is None:
                    continue
                xy = to_xy(i, cv)
                p.setBrush(col)
                p.setPen(QPen(col, 1))
                p.drawEllipse(xy, 2.5, 2.5)

        line_for(lambda t: t[1], color_a)
        line_for(lambda t: t[2], color_b)

        fm_ax = p.fontMetrics()
        y_bot = _chart_shared_bottom_label_baseline_y(chart_rect, fm_ax)
        y_top = _chart_shared_top_max_label_baseline_y(chart_rect, fm_ax)
        pl = float(chart_rect.left())
        p.setPen(QPen(QColor(CHART_Y_TICK_MIN_COLOR), 1))
        p.drawText(_chart_y_tick_x(p, "0%", pl), y_bot, "0%")
        p.setPen(QPen(QColor(CHART_REFINED_TICK_COLOR), 1))
        mid_y = (chart_rect.top() + chart_rect.bottom()) / 2
        y_mid = int(mid_y + (fm_ax.ascent() - fm_ax.descent()) / 2)
        p.drawText(_chart_y_tick_x(p, "50%", pl), y_mid, "50%")
        p.drawText(_chart_y_tick_x(p, "100%", pl), y_top, "100%")

        _paint_chart_x_axis_dates(
            p,
            chart_rect,
            dates,
            label_fn=_x_axis_date_label_mmdd,
            axis_font=_chart_font_axis_refined(),
            axis_color=CHART_REFINED_TICK_COLOR,
        )

    def leaveEvent(self, event):
        QToolTip.hideText()
        self._hover_tip_idx = None
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if len(self._points) < 2:
            return
        has_any = False
        for _, a, b in self._points:
            if a is not None or b is not None:
                has_any = True
                break
        if not has_any:
            return

        def clamp_pct(v):
            try:
                x = float(v)
            except Exception:
                return None
            return max(0.0, min(100.0, x))

        cr = _analysis_chart_plot_rect(self.width(), self.height())
        n = len(self._points)
        idx = _chart_hover_index_from_x(event.position().x(), cr, n)
        if idx is None:
            if self._hover_tip_idx is not None:
                QToolTip.hideText()
                self._hover_tip_idx = None
            return
        row = self._points[idx]
        dte = _parse_trade_date(row[0])
        if dte is None:
            return
        mmdd = _x_axis_date_label_mmdd([dte], 0)
        la = _legend_line_short(self._legend_a)
        lb = _legend_line_short(self._legend_b)
        parts = [mmdd]
        ca = clamp_pct(row[1]) if len(row) > 1 else None
        cb = clamp_pct(row[2]) if len(row) > 2 else None
        if ca is not None:
            parts.append(f"{la}: {ca:.1f}%")
        if cb is not None:
            parts.append(f"{lb}: {cb:.1f}%")
        if len(parts) == 1:
            if self._hover_tip_idx is not None:
                QToolTip.hideText()
                self._hover_tip_idx = None
            return
        tip = "\n".join(parts)
        if self._hover_tip_idx != idx:
            self._hover_tip_idx = idx
            QToolTip.showText(
                self.mapToGlobal(event.position().toPoint()) + QPoint(12, 12),
                tip,
                self,
            )




class RealtimeAuctionPage(QWidget):
    """실시간 경매 API 전용.

    조회 전 조건은 날짜 중심으로 최소화하고,
    조회 후 응답 데이터에서 품목/품종/시장/법인 필터를 동적으로 생성한다.
    """

    def __init__(self, owner: "MarketPricePage", parent=None):
        super().__init__(parent)
        self._owner = owner
        self._executor = owner._trend_executor
        self._rt_cache = {}
        self._cache_ttl_sec = 60
        self._req_seq = 0
        self._suppress_filter_events = False
        self._last_loaded_rows = []

        lay = QVBoxLayout(self)
        # 실시간 탭은 타이틀 상하 여백을 더 타이트하게 유지
        lay.setContentsMargins(8, 2, 8, 4)
        lay.setSpacing(SECTION_SPACING)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        title = QLabel("실시간 경매 조회")
        title.setStyleSheet(MainStyles.DASH_CARD_TITLE + " color:#2D3748;")
        title_row.addWidget(title)

        btn_help = QToolButton()
        btn_help.setText("?")
        btn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_help.setToolTip(
            "날짜 선택 후 조회하면 API 데이터를 불러옵니다.\n"
            "조회 후 응답 기반 필터(품목/품종/시장/법인)가 생성됩니다."
        )
        btn_help.setStyleSheet(MainStyles.BTN_HELP_TOOLTIP + MainStyles.TOOLTIP_LIGHT)
        title_row.addWidget(btn_help, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        lay.addLayout(title_row)

        # 날짜 · 조회 · 필터 한 줄
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        owner._apply_filter_control_style(self.date_edit)
        self.date_edit.setMinimumWidth(118)
        self.date_edit.setMaximumWidth(140)
        self.btn_today = QPushButton("오늘")
        self.btn_yesterday = QPushButton("어제")
        owner._apply_quick_date_button_style(self.btn_today)
        owner._apply_quick_date_button_style(self.btn_yesterday)
        self.btn_today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.btn_yesterday.clicked.connect(
            lambda: self.date_edit.setDate(QDate.currentDate().addDays(-1))
        )
        self.btn_search = QPushButton("조회")
        self.btn_search.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_search.clicked.connect(self.on_search)
        self.btn_to_sales = QPushButton("판매관리전송")
        self.btn_to_sales.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_to_sales.clicked.connect(self._send_selected_to_sales_matrix)
        top_row.addWidget(self.date_edit, 0)
        top_row.addWidget(self.btn_today, 0)
        top_row.addWidget(self.btn_yesterday, 0)
        top_row.addWidget(self.btn_search, 0)
        top_row.addWidget(self.btn_to_sales, 0)

        self.cmb_item = QComboBox()
        self.cmb_variety = QComboBox()
        self.cmb_market = QComboBox()
        self.cmb_corp = QComboBox()
        for cb in (self.cmb_item, self.cmb_variety, self.cmb_market, self.cmb_corp):
            owner._apply_filter_control_style(cb)
            cb.addItem("전체", "")
            cb.setEnabled(False)
        self.cmb_item.currentIndexChanged.connect(self._on_local_filter_changed)
        self.cmb_variety.currentIndexChanged.connect(self._on_local_filter_changed)
        self.cmb_market.currentIndexChanged.connect(self._on_local_filter_changed)
        self.cmb_corp.currentIndexChanged.connect(self._on_local_filter_changed)
        top_row.addWidget(QLabel("품목"), 0)
        top_row.addWidget(self.cmb_item, 1)
        top_row.addWidget(QLabel("품종"), 0)
        top_row.addWidget(self.cmb_variety, 1)
        top_row.addWidget(QLabel("시장"), 0)
        top_row.addWidget(self.cmb_market, 1)
        top_row.addWidget(QLabel("법인"), 0)
        top_row.addWidget(self.cmb_corp, 1)
        lay.addLayout(top_row)

        status_row = QVBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(1)
        
        self.lbl_status = QLabel("실시간 데이터 대기중")
        self.lbl_status.setStyleSheet(
            MainStyles.TXT_CAPTION
            + " color:#718096; padding:0px; margin:0px;"
        )
        self.lbl_status.setMinimumHeight(16)
        self.lbl_status.setMaximumHeight(18)
        status_row.addWidget(self.lbl_status)
        lay.addLayout(status_row)

        self.progress = owner._create_progress_bar()
        lay.addWidget(self.progress)

        self.lbl_count = QLabel("조회 건수: 0건")
        self.lbl_count.setStyleSheet(
            MainStyles.TXT_CAPTION
            + " color:#718096; padding:0px; margin:0px;"
        )
        self.lbl_count.setMinimumHeight(16)
        self.lbl_count.setMaximumHeight(18)
        status_row.addWidget(self.lbl_count)
        lay.setSpacing(2)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(10)
        self.tbl.setHorizontalHeaderLabels(
            [
                "경매시간",
                "품목",
                "품종",
                "등급",
                "사이즈",
                "출하지",
                "규격",
                "건수",
                "경락가",
                "금액",
            ]
        )
        self.tbl.setStyleSheet(MainStyles.TABLE)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.tbl.setMinimumWidth(0)
        self.tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header = self.tbl.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(0, 90)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(1, 70)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(3, 60)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(4, 70)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(5, 110)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(6, 110)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(7, 80)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tbl)
        lay.setStretchFactor(self.tbl, 1)

    def set_filters_busy(self, busy: bool):
        """실시간 조회 중 해당 탭 컨트롤만 잠금."""
        self.date_edit.setEnabled(not busy)
        self.btn_today.setEnabled(not busy)
        self.btn_yesterday.setEnabled(not busy)
        self.btn_search.setEnabled(not busy)
        # 결과 필터는 조회 후 로컬 필터링용이므로 조회 중에도 유지

    def _cache_key(self, target_date: str) -> str:
        return target_date

    @staticmethod
    def _row_text(row: dict, key: str) -> str:
        return str((row or {}).get(key) or "").strip()

    def _query_filters(self) -> dict:
        return {
            "target_date": self.date_edit.date().toString("yyyyMMdd"),
        }

    def _filter_rows(
        self,
        rows,
        item: str | None = None,
        variety: str | None = None,
        market: str | None = None,
        corp: str | None = None,
    ) -> list:
        """rows를 차원별로 필터링. None이면 해당 차원은 조건 없음."""
        out = []
        for row in rows or []:
            if item and self._row_text(row, "item_name") != item:
                continue
            if variety and self._row_text(row, "variety_name") != variety:
                continue
            if market and self._row_text(row, "market_name") != market:
                continue
            if corp and self._row_text(row, "corp_name") != corp:
                continue
            out.append(row)
        return out

    @staticmethod
    def _seconds_since(ts: datetime) -> int:
        return max(0, int((datetime.now() - ts).total_seconds()))

    @staticmethod
    def _unique_sorted_labels(rows, key: str) -> list:
        seen: set = set()
        out: list = []
        for r in rows or []:
            v = RealtimeAuctionPage._row_text(r, key)
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return sorted(out)

    def _populate_filter_combo(
        self, combo: QComboBox, sorted_labels: list[str], previous: str | None
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("전체", "")
        for lab in sorted_labels:
            combo.addItem(lab, lab)
        prev = (previous or "").strip()
        if prev and prev not in ("", "전체"):
            idx = combo.findText(prev, Qt.MatchFlag.MatchExactly)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)
        else:
            combo.setCurrentIndex(0)
        combo.setEnabled(combo.count() > 1)
        combo.blockSignals(False)

    def _get_current_selections(self) -> dict:
        """전체(인덱스 0)가 아닐 때만 선택 문자열 반환."""

        def pick(combo: QComboBox):
            if combo is None or not combo.isEnabled():
                return None
            if combo.currentIndex() <= 0:
                return None
            t = combo.currentText().strip()
            return t if t else None

        return {
            "item": pick(self.cmb_item),
            "variety": pick(self.cmb_variety),
            "market": pick(self.cmb_market),
            "corp": pick(self.cmb_corp),
        }

    def _get_filtered_rows_for_filters(self) -> list:
        """현재 네 차원 필터로 `_last_loaded_rows`를 필터링."""
        s = self._get_current_selections()
        return self._filter_rows(
            self._last_loaded_rows,
            item=s["item"],
            variety=s["variety"],
            market=s["market"],
            corp=s["corp"],
        )

    def _rebuild_filter_options(self) -> None:
        """콤보별로 '자기 자신 제외' 나머지 필터만 적용해 옵션 재구성(피벗형 교차 필터)."""
        rows = self._last_loaded_rows
        sel = self._get_current_selections()

        item_rows = self._filter_rows(
            rows, variety=sel["variety"], market=sel["market"], corp=sel["corp"]
        )
        item_values = self._unique_sorted_labels(item_rows, "item_name")

        variety_rows = self._filter_rows(
            rows, item=sel["item"], market=sel["market"], corp=sel["corp"]
        )
        variety_values = self._unique_sorted_labels(variety_rows, "variety_name")

        market_rows = self._filter_rows(
            rows, item=sel["item"], variety=sel["variety"], corp=sel["corp"]
        )
        market_values = self._unique_sorted_labels(market_rows, "market_name")

        corp_rows = self._filter_rows(
            rows, item=sel["item"], variety=sel["variety"], market=sel["market"]
        )
        corp_values = self._unique_sorted_labels(corp_rows, "corp_name")

        self._suppress_filter_events = True
        try:
            self._populate_filter_combo(self.cmb_item, item_values, sel["item"])
            self._populate_filter_combo(self.cmb_variety, variety_values, sel["variety"])
            self._populate_filter_combo(self.cmb_market, market_values, sel["market"])
            self._populate_filter_combo(self.cmb_corp, corp_values, sel["corp"])
        finally:
            self._suppress_filter_events = False

    @staticmethod
    def _extract_weight_kg_from_spec(spec_name: str | None) -> float | None:
        """규격 문자열에서 '숫자 + kg' 패턴만 추출. 해석 불가 시 None."""
        if not spec_name:
            return None
        text = str(spec_name).strip().lower()
        m = re.search(r"(\d+(?:\.\d+)?)\s*kg", text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    def _build_realtime_summary_metrics(self, rows: list[dict]) -> dict:
        """현재 표시 rows 기준 상단 요약 메트릭 계산."""
        row_count = len(rows or [])
        total_quantity = 0
        total_weight_kg = 0.0
        total_price_weighted = 0  # auction_price * quantity
        total_amount_sum = 0

        for r in rows or []:
            qty = self._owner._to_int(r.get("quantity"))
            price = self._owner._to_int(r.get("auction_price"))
            amount = self._owner._to_int(r.get("total_amount"))
            total_amount_sum += amount
            if qty <= 0:
                continue
            total_quantity += qty
            total_price_weighted += price * qty
            w = self._extract_weight_kg_from_spec(r.get("spec_name"))
            if w is not None and w > 0:
                total_weight_kg += w * qty

        weighted_avg_price = None
        if total_quantity > 0 and total_price_weighted > 0:
            weighted_avg_price = int(round(total_price_weighted / total_quantity))

        avg_price_per_kg = None
        if total_weight_kg > 0 and total_amount_sum > 0:
            avg_price_per_kg = int(round(total_amount_sum / total_weight_kg))

        return {
            "row_count": row_count,
            "total_weight_kg": total_weight_kg,
            "total_quantity": total_quantity,
            "weighted_avg_price": weighted_avg_price,
            "avg_price_per_kg": avg_price_per_kg,
        }

    def _format_realtime_summary_label(self, rows: list[dict]) -> str:
        m = self._build_realtime_summary_metrics(rows)
        row_count = m["row_count"]
        total_weight_kg = m["total_weight_kg"]
        weighted_avg_price = m["weighted_avg_price"]
        avg_price_per_kg = m["avg_price_per_kg"]

        # 총 중량 텍스트
        if total_weight_kg and total_weight_kg > 0:
            if abs(total_weight_kg - round(total_weight_kg)) < 1e-6:
                wt_text = f"{int(round(total_weight_kg)):,}kg"
            else:
                wt_text = f"{total_weight_kg:,.1f}kg"
        else:
            wt_text = "-"

        avg_price_text = "-" if weighted_avg_price is None else f"{weighted_avg_price:,}원"
        avg_per_kg_text = "-" if avg_price_per_kg is None else f"{avg_price_per_kg:,}원"

        return (
            f"조회 건수: {row_count:,}건"
            f" | 총 중량: {wt_text}"
            f" | 건당 평균가: {avg_price_text}"
            f" | kg당 평균가: {avg_per_kg_text}"
        )

    def _apply_local_filters_to_table(self, rows: list | None = None):
        if rows is None:
            rows = self._get_filtered_rows_for_filters()
        self._fill_table(rows)
        self.lbl_count.setText(self._format_realtime_summary_label(rows))

    def _fetch_realtime_by_date(self, target_date: str):
        """실시간 조회는 날짜만 기준으로 사용한다."""
        # manager 시그니처 유지 목적의 placeholder 값(조건 필터로 사용하지 않음)
        return self._owner.market_manager.fetch_real_time_data(target_date, "", "")

    def _fill_table(self, rows):
        ow = self._owner
        self.tbl.clearSpans()
        self.tbl.setRowCount(0)
        self.tbl.clearContents()
        if not rows:
            self.tbl.setRowCount(1)
            self.tbl.setSpan(0, 0, 1, 10)
            it = QTableWidgetItem("데이터 없음")
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl.setItem(0, 0, it)
            return
        self.tbl.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            cols = [
                row.get("auction_time") or "-",
                row.get("item_name") or "-",
                row.get("variety_name") or "-",
                row.get("grade_name") or "-",
                row.get("size_name") or "-",
                row.get("origin_name") or "-",
                row.get("spec_name") or "-",
                ow._to_int(row.get("quantity")),
                ow._to_int(row.get("auction_price")),
                ow._to_int(row.get("total_amount")),
            ]
            for c_idx, value in enumerate(cols):
                if c_idx >= 7:
                    text = f"{ow._to_int(value):,}"
                    align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                else:
                    text = str(value)
                    align = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                self.tbl.setItem(r_idx, c_idx, item)

    def _send_selected_to_sales_matrix(self):
        sm = self.tbl.selectionModel()
        if not sm:
            return
        sel_rows = sorted({idx.row() for idx in sm.selectedRows()})
        if not sel_rows:
            QMessageBox.information(self, "안내", "판매관리로 보낼 경매 행을 선택하세요.")
            return

        payload_rows = []
        for r in sel_rows:
            get = lambda c: self.tbl.item(r, c).text().strip() if self.tbl.item(r, c) else ""
            payload_rows.append(
                {
                    "time": get(0),          # 경매시간(판매 저장 미사용, 입력 참고값)
                    "item_name": get(1),
                    "variety_name": get(2),
                    "grade_name": get(3),
                    "size_name": get(4),
                    "spec_name": get(6),     # 예: 15kg 상자
                    "count": self._owner._to_int(get(7)),
                    "unit_price": self._owner._to_int(get(8)),
                    "amount": self._owner._to_int(get(9)),
                }
            )

        common = {
            "target_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "market_name": self.cmb_market.currentText().strip() if self.cmb_market.currentIndex() > 0 else "",
            "corp_name": self.cmb_corp.currentText().strip() if self.cmb_corp.currentIndex() > 0 else "",
            "item_name": self.cmb_item.currentText().strip() if self.cmb_item.currentIndex() > 0 else "",
            "variety_name": self.cmb_variety.currentText().strip() if self.cmb_variety.currentIndex() > 0 else "",
        }
        dlg = AuctionToSalesMapDialog(self._owner, common, payload_rows, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dlg.get_payload() or {}
        if not payload.get("rows"):
            return
        ok, message = self._owner.save_realtime_auction_draft(payload)
        if ok:
            self.lbl_status.setText(message)
            self._show_sales_draft_saved_message(message)
        else:
            self.lbl_status.setText("판매관리 전송 실패")
            QMessageBox.warning(self, "저장 실패", message)

    def _show_sales_draft_saved_message(self, save_message: str) -> None:
        detail = (
            f"{save_message}\n\n"
            "저장 상태: DRAFT / AUCTION_RT\n"
            "다음 단계는 [판매관리] 화면에서 진행해 주세요.\n"
            "- 저장된 초안 조회/수정\n"
            "- 입금 입력 및 경비 입력\n"
            "- 배송 처리\n"
            "- 확정 처리(CONFIRMED)\n\n"
            "※ 전표 반영은 CONFIRMED 상태에서만 가능합니다."
        )
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("저장 완료")
        msg.setText(detail)
        # Windows 네이티브 다이얼로그(다크 테마) 대신 Qt 위젯 다이얼로그로 강제하여 가독성 보장
        msg.setOption(QMessageBox.Option.DontUseNativeDialog, True)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet(
            "QMessageBox { background-color: #FFFFFF; }"
            "QWidget { background-color: #FFFFFF; color: #1F2937; }"
            "QLabel { color: #1F2937; background-color: #FFFFFF; }"
            "QPushButton { min-width: 88px; padding: 6px 12px; background-color: #F3F4F6; color: #111827; border: 1px solid #D1D5DB; }"
            "QPushButton:hover { background-color: #E5E7EB; }"
        )
        msg.exec()

    def on_search(self):
        self.run_realtime_search()

    def run_realtime_search(self):
        if self._owner.market_manager is None:
            self.lbl_status.setText("실시간 API를 사용할 수 없습니다.")
            return
        g = self._query_filters()
        ck = self._cache_key(g["target_date"])
        cached = self._rt_cache.get(ck)
        if cached:
            elapsed = self._seconds_since(cached.get("timestamp"))
            if elapsed < self._cache_ttl_sec:
                self._last_loaded_rows = list(cached.get("data") or [])
                self._rebuild_filter_options()
                self._apply_local_filters_to_table()
                self.lbl_status.setText(f"캐시 사용 ({elapsed}초 전 데이터)")
                self.progress.hide()
                self.progress.setValue(0)
                return
            self._rt_cache.pop(ck, None)

        self._req_seq += 1
        rid = self._req_seq
        self.set_filters_busy(True)
        self.lbl_status.setText("실시간 데이터 조회 중...")
        self.progress.show()
        self.progress.setValue(30)
        future = self._executor.submit(
            self._fetch_realtime_by_date,
            g["target_date"],
        )
        QTimer.singleShot(120, lambda: self._poll_realtime_future(rid, future, ck))

    def _poll_realtime_future(self, req_id, future, cache_key):
        if req_id != self._req_seq:
            return
        if not future.done():
            QTimer.singleShot(
                120,
                lambda: self._poll_realtime_future(req_id, future, cache_key),
            )
            return
        self.set_filters_busy(False)
        self.progress.setValue(100)
        self.progress.hide()
        try:
            rows = list(future.result() or [])
        except Exception as e:
            self.lbl_status.setText(f"실시간 조회 실패: {e}")
            self._fill_table([])
            self.lbl_count.setText("조회 건수: 0건")
            return
        self._rt_cache[cache_key] = {
            "data": list(rows),
            "timestamp": datetime.now(),
        }
        self._last_loaded_rows = list(rows)
        self._rebuild_filter_options()
        self._apply_local_filters_to_table()
        self.lbl_status.setText("실시간 데이터 조회 완료")

    def _on_local_filter_changed(self, *_args):
        if self._suppress_filter_events:
            return
        if not self._last_loaded_rows:
            return
        self._rebuild_filter_options()
        filtered = self._get_filtered_rows_for_filters()
        self._apply_local_filters_to_table(filtered)


class SettlementPage(QWidget):
    """정산(sale) 전용. 실시간 탭과 동일 UX(날짜 조회 + 결과기반 cascading 필터)."""

    def __init__(self, owner: "MarketPricePage", parent=None):
        super().__init__(parent)
        self._owner = owner
        self._executor = owner._trend_executor
        self._cache = {}
        self._cache_ttl_sec = 60
        self._req_seq = 0
        self._suppress_filter_events = False
        self._last_loaded_rows = []
        root = QVBoxLayout(self)
        root.setContentsMargins(*SECTION_CONTENT_MARGINS)
        root.setSpacing(SECTION_SPACING)

        title = QLabel("정산 정보 조회")
        title.setStyleSheet(MainStyles.DASH_CARD_TITLE + " color:#2D3748;")
        root.addWidget(title)
        # 기존 외부 연동 호환용 라벨(숨김)
        self.lbl_base_date = QLabel("조회 기준일: —")
        self.lbl_base_date.hide()
        self.lbl_notice = QLabel("")
        self.lbl_notice.hide()

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        owner._apply_filter_control_style(self.date_edit)
        self.date_edit.setMinimumWidth(118)
        self.date_edit.setMaximumWidth(140)
        self.btn_today = QPushButton("오늘")
        self.btn_yesterday = QPushButton("어제")
        owner._apply_quick_date_button_style(self.btn_today)
        owner._apply_quick_date_button_style(self.btn_yesterday)
        self.btn_today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.btn_yesterday.clicked.connect(
            lambda: self.date_edit.setDate(QDate.currentDate().addDays(-1))
        )
        self.btn_search = QPushButton("조회")
        self.btn_search.setStyleSheet(MainStyles.BTN_PRIMARY_COMPACT)
        self.btn_search.clicked.connect(self.on_search)
        top_row.addWidget(self.date_edit, 0)
        top_row.addWidget(self.btn_today, 0)
        top_row.addWidget(self.btn_yesterday, 0)
        top_row.addWidget(self.btn_search, 0)

        self.cmb_item = QComboBox()
        self.cmb_variety = QComboBox()
        self.cmb_market = QComboBox()
        self.cmb_corp = QComboBox()
        for cb in (self.cmb_item, self.cmb_variety, self.cmb_market, self.cmb_corp):
            owner._apply_filter_control_style(cb)
            cb.addItem("전체", "")
            cb.setEnabled(False)
        self.cmb_item.currentIndexChanged.connect(self._on_filter_text_changed)
        self.cmb_variety.currentIndexChanged.connect(self._on_filter_text_changed)
        self.cmb_market.currentIndexChanged.connect(self._on_filter_text_changed)
        self.cmb_corp.currentIndexChanged.connect(self._on_filter_text_changed)
        top_row.addWidget(QLabel("품목"), 0)
        top_row.addWidget(self.cmb_item, 1)
        top_row.addWidget(QLabel("품종"), 0)
        top_row.addWidget(self.cmb_variety, 1)
        top_row.addWidget(QLabel("시장"), 0)
        top_row.addWidget(self.cmb_market, 1)
        top_row.addWidget(QLabel("법인"), 0)
        top_row.addWidget(self.cmb_corp, 1)
        root.addLayout(top_row)

        self.lbl_status = QLabel("정산 데이터 대기중 · 조회 버튼을 눌러 주세요")
        self.lbl_status.setStyleSheet(MainStyles.TXT_CAPTION + " color:#718096;")
        root.addWidget(self.lbl_status)

        self.progress = owner._create_progress_bar()
        root.addWidget(self.progress)

        if DEBUG_MARKET_VERIFY:
            self.lbl_debug_info = QLabel("")
            self.lbl_debug_info.setStyleSheet(MainStyles.TXT_CAPTION + " color:#8A94A6;")
            root.addWidget(self.lbl_debug_info)
        else:
            self.lbl_debug_info = None

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(13)
        self.tbl.setHorizontalHeaderLabels(
            [
                "거래일",
                "법인",
                "품목",
                "품종",
                "등급",
                "사이즈",
                "규격",
                "출하지",
                "수량",
                "평균가",
                "최고가",
                "최저가",
                "금액",
            ]
        )
        self.tbl.setStyleSheet(MainStyles.TABLE)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        h = self.tbl.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)   # 거래일 (yyyy-mm-dd 전체)
        self.tbl.setColumnWidth(0, 118)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)   # 법인
        self.tbl.setColumnWidth(1, 120)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)   # 품목
        self.tbl.setColumnWidth(2, 60)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)   # 품종
        self.tbl.setColumnWidth(3, 80)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)   # 등급
        self.tbl.setColumnWidth(4, 60)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)   # 사이즈 (긴 표기 대응)
        self.tbl.setColumnWidth(5, 150)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)   # 규격
        self.tbl.setColumnWidth(6, 90)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)   # 출하지
        self.tbl.setColumnWidth(7, 90)
        h.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)   # 수량 (숫자만, 폭 절약)
        self.tbl.setColumnWidth(8, 72)
        h.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)   # 평균가
        self.tbl.setColumnWidth(9, 84)
        h.setSectionResizeMode(10, QHeaderView.ResizeMode.Fixed)  # 최고가
        self.tbl.setColumnWidth(10, 84)
        h.setSectionResizeMode(11, QHeaderView.ResizeMode.Fixed)  # 최저가
        self.tbl.setColumnWidth(11, 84)
        h.setSectionResizeMode(12, QHeaderView.ResizeMode.Stretch)  # 금액만 남는 폭 흡수
        self.tbl.setColumnWidth(12, 102)
        # 셀 말줄임 완화: 텍스트 컬럼은 내용 우선 표시
        self.tbl.setTextElideMode(Qt.TextElideMode.ElideNone)
        root.addWidget(self.tbl)

    def set_filters_busy(self, busy: bool):
        self.date_edit.setEnabled(not busy)
        self.btn_today.setEnabled(not busy)
        self.btn_yesterday.setEnabled(not busy)
        self.btn_search.setEnabled(not busy)

    def _cache_key(self, target_date: str) -> str:
        return target_date

    @staticmethod
    def _row_text(row: dict, key: str) -> str:
        return str((row or {}).get(key) or "").strip()

    def _query_filters(self) -> dict:
        return {"target_date": self.date_edit.date().toString("yyyyMMdd")}

    @staticmethod
    def _compact_origin_region(origin_name: str) -> str:
        """출하지를 핵심 지역명(시/군/구) 중심으로 축약한다."""
        name = str(origin_name or "").strip()
        if not name:
            return "-"
        tokens = [t.strip(" ,./") for t in name.split() if t.strip(" ,./")]
        for token in reversed(tokens):
            if token.endswith(("시", "군", "구")):
                return token
        return tokens[-1] if tokens else "-"

    @staticmethod
    def _origin_tooltip(origin_name: str) -> str:
        name = str(origin_name or "").strip() or "-"
        return f"출하지(원문): {name}"

    def _on_filter_text_changed(self, *_a):
        if self._suppress_filter_events:
            return
        if not self._last_loaded_rows:
            return
        self._rebuild_filter_options()
        self._apply_local_and_sync_owner()

    def on_search(self):
        self.run_settlement_search()

    def run_settlement_search(self, filters: dict | None = None):
        ow = self._owner
        if ow.settlement_manager is None:
            self.lbl_status.setText("정산 API를 사용할 수 없습니다.")
            return
        g = dict(filters or self._query_filters())
        ck = self._cache_key(g["target_date"])
        cached = self._cache.get(ck)
        if cached:
            elapsed = max(0, int((datetime.now() - cached.get("timestamp")).total_seconds()))
            if elapsed < self._cache_ttl_sec:
                self._apply_payload(cached.get("payload") or {}, g, from_cache=True)
                return
            self._cache.pop(ck, None)
        self._req_seq += 1
        rid = self._req_seq
        self.set_filters_busy(True)
        self.lbl_status.setText("정산 API 호출 중…")
        self.progress.show()
        self.progress.setValue(30)
        future = self._executor.submit(
            ow.settlement_manager.fetch_settlement_data,
            g["target_date"],
            "",
            "",
        )
        QTimer.singleShot(120, lambda: self._poll_future(rid, future, dict(g), ck))

    def get_filters(self) -> dict:
        item_nm = self.cmb_item.currentText().strip() if self.cmb_item.isEnabled() else ""
        variety_nm = self.cmb_variety.currentText().strip() if self.cmb_variety.isEnabled() else ""
        market_nm = self.cmb_market.currentText().strip() if self.cmb_market.isEnabled() else ""
        corp_nm = self.cmb_corp.currentText().strip() if self.cmb_corp.isEnabled() else ""
        return {
            "target_date": self.date_edit.date().toString("yyyyMMdd"),
            "item_name": "" if item_nm in ("", "전체") else item_nm,
            "variety_name": "" if variety_nm in ("", "전체") else variety_nm,
            "market_name": "" if market_nm in ("", "전체") else market_nm,
            "corp_name": "" if corp_nm in ("", "전체") else corp_nm,
        }

    @staticmethod
    def _settlement_sort_token_cd(value) -> str:
        """코드 정렬용 토큰(순수 숫자 코드는 자릿수 맞춰 비교, 빈 값은 뒤로)."""
        s = str(value or "").strip()
        if not s:
            return "\uffff"
        if s.isdigit():
            return s.zfill(12)
        return s

    def _sort_settlement_rows(self, rows: list) -> list:
        """표시 순서: 거래일 → 법인코드 → 품목코드·품종코드 → 출하지(plor_cd) → 등급·사이즈코드 → 규격코드."""
        if not rows:
            return []

        def key(r: dict):
            return (
                str(r.get("trade_date") or ""),
                self._settlement_sort_token_cd(r.get("corp_code")),
                self._settlement_sort_token_cd(r.get("item_code_middle")),
                self._settlement_sort_token_cd(r.get("item_code_small")),
                self._settlement_sort_token_cd(r.get("farmer_code")),
                self._settlement_sort_token_cd(r.get("grade_code")),
                self._settlement_sort_token_cd(r.get("size_code")),
                str(r.get("spec_code") or ""),
            )

        return sorted(rows, key=key)

    def _get_filtered_rows_for_filters(self):
        filtered = self._filter_rows(self._last_loaded_rows, self.get_filters())
        return self._sort_settlement_rows(filtered)

    def _set_combo_values_from_rows(self, combo: QComboBox, rows, key_text: str):
        prev = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("전체", "")
        seen = set()
        for r in rows or []:
            txt = str(r.get(key_text) or "").strip()
            if txt and txt not in seen:
                seen.add(txt)
                combo.addItem(txt, txt)
        idx = combo.findText(prev, Qt.MatchFlag.MatchExactly) if prev else -1
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.setEnabled(combo.count() > 1)
        combo.blockSignals(False)

    def _rebuild_filter_options(self):
        rows = self._last_loaded_rows
        g = self.get_filters()
        self._suppress_filter_events = True
        try:
            self._set_combo_values_from_rows(
                self.cmb_item, self._filter_rows(rows, {**g, "item_name": ""}), "item_name"
            )
            self._set_combo_values_from_rows(
                self.cmb_variety, self._filter_rows(rows, {**g, "variety_name": ""}), "variety_name"
            )
            self._set_combo_values_from_rows(
                self.cmb_market, self._filter_rows(rows, {**g, "market_name": ""}), "market_name"
            )
            self._set_combo_values_from_rows(
                self.cmb_corp, self._filter_rows(rows, {**g, "corp_name": ""}), "corp_name"
            )
        finally:
            self._suppress_filter_events = False

    def _aggregate_rows(self, rows):
        grouped = {}
        for r in rows or []:
            key = (
                r.get("trade_date"),
                r.get("item_name"),
                r.get("variety_name"),
                r.get("grade_name"),
                r.get("size_name"),
                r.get("origin_name"),
                r.get("spec_name"),
                r.get("market_name"),
                r.get("corp_name"),
                r.get("farmer_code"),
                r.get("farmer_name"),
            )
            qty = self._owner._to_int(r.get("quantity"))
            amt = self._owner._to_int(r.get("total_amount"))
            avgp = self._owner._to_int(r.get("avg_price"))
            maxp = self._owner._to_int(r.get("max_price"))
            minp = self._owner._to_int(r.get("min_price"))
            g = grouped.get(key)
            if g is None:
                g = dict(r)
                g["_sum_qty"] = max(0, qty)
                g["_sum_amt"] = max(0, amt)
                g["_sum_avg_x_qty"] = max(0, avgp) * max(0, qty)
                g["max_price"] = maxp
                g["min_price"] = minp if minp > 0 else 0
                grouped[key] = g
                continue
            g["_sum_qty"] += max(0, qty)
            g["_sum_amt"] += max(0, amt)
            g["_sum_avg_x_qty"] += max(0, avgp) * max(0, qty)
            g["max_price"] = max(g["max_price"], maxp)
            if minp > 0:
                g["min_price"] = min([x for x in (g["min_price"], minp) if x > 0] or [0])

        out = []
        for g in grouped.values():
            q = self._owner._to_int(g.get("_sum_qty"))
            a = self._owner._to_int(g.get("_sum_amt"))
            avg = int(round(g.get("_sum_avg_x_qty", 0) / q)) if q > 0 else self._owner._to_int(g.get("avg_price"))
            row = {k: v for k, v in g.items() if not str(k).startswith("_")}
            row["quantity"] = q
            row["total_amount"] = a
            row["avg_price"] = avg
            out.append(row)
        # 정렬 기준: 출하지(시/군) → 법인 → 농가명 → 품목/품종/등급코드/사이즈코드/규격코드
        # 화면 표시는 기존 이름 컬럼을 그대로 사용한다.
        out.sort(
            key=lambda r: (
                str(r.get("origin_name") or ""),
                str(r.get("corp_name") or ""),
                str(r.get("farmer_name") or ""),
                str(r.get("item_code_middle") or r.get("item_name") or ""),
                str(r.get("item_code_small") or r.get("variety_name") or ""),
                str(r.get("grade_code") or r.get("grade_name") or ""),
                str(r.get("size_code") or r.get("size_name") or ""),
                str(r.get("spec_code") or r.get("spec_name") or ""),
            )
        )
        return out

    def _poll_future(self, req_id, future, g_snap, cache_key):
        if req_id != self._req_seq:
            return
        if not future.done():
            QTimer.singleShot(
                120, lambda: self._poll_future(req_id, future, g_snap, cache_key)
            )
            return
        self.set_filters_busy(False)
        self.progress.setValue(100)
        self.progress.hide()
        try:
            rows = list(future.result() or [])
        except Exception as e:
            self.lbl_status.setText(f"정산 조회 실패: {e}")
            self._fill_table([])
            return
        payload = {
            "rows": rows,
            "source": "sale",
            "requested_date": g_snap["target_date"],
            "base_date": g_snap["target_date"],
            "fallback_used": False,
            "status": "ok" if rows else "empty",
        }
        self._cache[cache_key] = {"timestamp": datetime.now(), "payload": payload}
        self._apply_payload(payload, g_snap, from_cache=False)

    def _show_empty_state(self, date_text: str):
        self.tbl.clearSpans()
        self.tbl.setRowCount(1)
        self.tbl.setSpan(0, 0, 1, 13)
        self.tbl.clearContents()
        it = QTableWidgetItem("데이터 없음")
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tbl.setItem(0, 0, it)
        self._last_loaded_rows = []
        ow = self._owner
        ow._detail_cache = {
            "rows": [],
            "requested_date": date_text,
            "base_date": date_text,
            "source": "empty",
            "fallback_used": False,
            "status": "empty",
        }
        ow._update_base_date_label(ow._detail_cache)
        ow._update_debug_info_label()

    def _apply_payload(self, payload: dict, g_snap: dict, from_cache: bool):
        date_text = g_snap["target_date"]
        rows = list(payload.get("rows") or [])
        if not rows:
            self.lbl_status.setText("캐시 사용 · 0건" if from_cache else "해당 일자 정산 데이터 없음")
            self._show_empty_state(date_text)
            return
        # 정산정보 탭은 원본(정규화 1건=API 1건) 그대로 표시한다.
        self._last_loaded_rows = list(rows)
        self._rebuild_filter_options()
        self._last_payload_source = str(payload.get("source") or "sale")
        self._apply_local_and_sync_owner()
        ow = self._owner
        n = len(ow._collect_filtered_rows_from_cache())
        self.lbl_status.setText(
            (f"캐시 사용 · " if from_cache else "")
            + f"정산({self._last_payload_source}) · 표시 {n}건"
        )

    def _apply_local_and_sync_owner(self):
        rows = self._get_filtered_rows_for_filters()
        ow = self._owner
        src = str(getattr(self, "_last_payload_source", None) or "sale")
        ow._detail_cache = {
            "rows": list(self._last_loaded_rows or []),
            "requested_date": self._query_filters()["target_date"],
            "base_date": self._query_filters()["target_date"],
            "source": src,
            "fallback_used": False,
            "status": "ok",
        }
        ow._update_base_date_label(
            {
                "requested_date": self._query_filters()["target_date"],
                "base_date": self._query_filters()["target_date"],
                "status": "ok",
                "fallback_used": False,
            }
        )
        self._fill_table(rows)
        ow._update_debug_info_label()
        ow._run_ui_verify_checks()

    def _filter_rows(self, rows, g: dict):
        out = []
        vn = g.get("variety_name") or ""
        mn = g.get("market_name") or ""
        cn = g.get("corp_name") or "전체"
        itn = str(g.get("item_name") or "").strip()
        for row in rows or []:
            if vn and str(row.get("variety_name") or "").strip() != vn:
                continue
            if mn and str(row.get("market_name") or "").strip() != mn:
                continue
            if cn not in ("", "전체") and str(row.get("corp_name") or "").strip() != cn:
                continue
            if itn and "전체" not in itn:
                ritem = str(row.get("item_name") or "").strip()
                if itn not in ritem and ritem.find(itn) < 0:
                    continue
            out.append(row)
        return out

    def _fill_table(self, rows):
        ow = self._owner
        self.tbl.clearSpans()
        self.tbl.setRowCount(0)
        self.tbl.clearContents()
        if not rows:
            self.tbl.setRowCount(1)
            self.tbl.setSpan(0, 0, 1, 13)
            it = QTableWidgetItem("데이터 없음")
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl.setItem(0, 0, it)
            return
        self.tbl.setRowCount(len(rows))
        numeric_cols = {8, 9, 10, 11, 12}
        for r_idx, row in enumerate(rows):
            qty = ow._to_int(row.get("quantity"))
            avgp = ow._to_int(row.get("avg_price"))
            maxp = ow._to_int(row.get("max_price"))
            minp = ow._to_int(row.get("min_price"))
            amt = ow._to_int(row.get("total_amount"))
            origin_text = self._compact_origin_region(row.get("origin_name"))
            cols = [
                row.get("trade_date") or "-",
                row.get("corp_name") or "-",
                row.get("item_name") or "-",
                row.get("variety_name") or "-",
                row.get("grade_name") or "-",
                row.get("size_name") or "-",
                row.get("spec_name") or "-",
                origin_text,
                qty,
                avgp,
                maxp,
                minp,
                amt,
            ]
            for c_idx, value in enumerate(cols):
                if c_idx in numeric_cols:
                    text = f"{ow._to_int(value):,}"
                    align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                else:
                    text = str(value)
                    align = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if c_idx == 7:
                    item.setToolTip(self._origin_tooltip(row.get("origin_name")))
                self.tbl.setItem(r_idx, c_idx, item)


class MarketPricePage(DashboardDetailBase):
    """시장/경매 상세 - 요약 → 검증 → 근거 구조 화면."""
    SALES_STATUS_DRAFT = "DRAFT"
    SALES_SOURCE_AUCTION_RT = "AUCTION_RT"
    SALES_DEFAULT_STATUS_CD = "10"
    SALES_RMK_FORMAT = "[경매] {market} / {corp} / 실시간 경매"

    def __init__(self, db_manager, session, parent=None):
        super().__init__("market", "시장/경매 가격", "📈", db_manager, session, parent)
        self.user_id = (
            (session or {}).get("user_id")
            or (session or {}).get("login_id")
            or "SYSTEM"
        )
        self._is_filter_updating = False
        self._trend_executor = ThreadPoolExecutor(max_workers=4)
        self._auction_code_mgr = CodeManager(self.db, self.farm_cd or "")
        self._header_data = None
        self._detail_cache = None
        self._analysis_cache = None
        self._analysis_cache_key = None
        self._analysis_loading = False
        self.current_price_type = "max"
        self.market_manager = None
        self.settlement_manager = None
        self.market_service = None
        self.market_analysis_service = None
        self._market_analysis_detail_pack = {}
        self._init_services()
        self._move_back_button_right()
        self._build_content()
        self._build_sidebar()
        self._connect_signals()
        self._init_loading_state()
        QTimer.singleShot(0, self._load_market_analysis_from_db)

    def _move_back_button_right(self):
        root_layout = self.layout()
        if root_layout is None or root_layout.count() <= 0:
            return
        header_item = root_layout.itemAt(0)
        header_layout = header_item.layout() if header_item else None
        if header_layout is None:
            return
        title_widget = None
        while header_layout.count() > 0:
            item = header_layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            if widget is self.btn_back:
                continue
            if title_widget is None:
                title_widget = widget
            else:
                widget.hide()
        if title_widget is not None:
            header_layout.addWidget(title_widget)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_back)

    def _ensure_sales_master_workflow_columns(self) -> None:
        try:
            cols = self.db.execute_query("PRAGMA table_info(t_sales_master)") or []
            names = {str(c[1]).strip().lower() for c in cols}
            if names and "sales_status" not in names:
                self.db.execute_query(
                    "ALTER TABLE t_sales_master ADD COLUMN sales_status TEXT DEFAULT 'CONFIRMED'"
                )
            if names and "sales_source" not in names:
                self.db.execute_query(
                    "ALTER TABLE t_sales_master ADD COLUMN sales_source TEXT DEFAULT 'ORDER'"
                )
        except Exception:
            pass

    def save_realtime_auction_draft(self, payload: dict) -> tuple[bool, str]:
        self._ensure_sales_master_workflow_columns()
        reg_id = str(self.user_id or "SYSTEM").strip() or "SYSTEM"
        common = (payload or {}).get("common") or {}
        rows = (payload or {}).get("rows") or []
        if not rows:
            return False, "저장할 행이 없습니다."

        sales_dt = str(common.get("target_date") or "").strip()
        if not QDate.fromString(sales_dt, "yyyy-MM-dd").isValid():
            sales_dt = QDate.currentDate().toString("yyyy-MM-dd")

        custm_id = str(common.get("custm_id") or "").strip()
        item_cd = str(common.get("item_cd") or "").strip()
        variety_cd = str(common.get("variety_cd") or "").strip()
        market_name = str(common.get("market_name") or "").strip() or "시장미상"
        corp_name = str(common.get("corp_name") or "").strip() or "법인미상"

        errors = []
        if not custm_id:
            errors.append("법인(고객) 매핑 실패: 상단 법인을 확인하세요.")
        if not item_cd:
            errors.append("품목 확인 실패: 상단 품목을 확인하세요.")
        if not variety_cd:
            errors.append("품종 확인 실패: 상단 품종을 확인하세요.")

        for idx, rec in enumerate(rows, start=1):
            if not str(rec.get("size_cd") or "").strip():
                errors.append(f"{idx}행 규격 매핑 미완료")
            if not str(rec.get("grade_cd") or "").strip():
                errors.append(f"{idx}행 등급 매핑 미완료")
            if not str(rec.get("crop_cd") or "").strip():
                errors.append(f"{idx}행 과수 매핑 미완료")
            qty = self._to_int(rec.get("count"))
            unit_price = self._to_int(rec.get("unit_price"))
            if qty <= 0:
                errors.append(f"{idx}행 건수 오류: {qty}")
            if unit_price <= 0:
                errors.append(f"{idx}행 단가 오류: {unit_price}")

        if errors:
            return False, "\n".join(errors[:20])

        sales_no = self.db.generate_sales_no(self.farm_cd, sales_dt)
        total_item_amt = 0
        detail_queries = []
        sql_detail = """
            INSERT INTO t_sales_detail (
                sale_detail_no, sales_no, farm_cd, item_cd, variety_cd,
                crop_nm, grade_cd, size_cd, qty, unit_price, tot_item_amt,
                ship_fee, tot_sale_amt, tot_paid_amt, tot_unpaid_amt,
                dlvry_tp, rmk, reg_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for idx, rec in enumerate(rows, start=1):
            qty = self._to_int(rec.get("count"))
            unit_price = self._to_int(rec.get("unit_price"))
            amount = self._to_int(rec.get("amount")) or (qty * unit_price)
            total_item_amt += amount
            sale_detail_no = f"{sales_no}-S{idx:02d}"
            detail_queries.append(
                (
                    sql_detail,
                    (
                        sale_detail_no,
                        sales_no,
                        self.farm_cd,
                        item_cd,
                        variety_cd,
                        str(rec.get("crop_cd") or "").strip(),
                        str(rec.get("grade_cd") or "").strip(),
                        str(rec.get("size_cd") or "").strip(),
                        qty,
                        unit_price,
                        amount,
                        0,
                        amount,
                        0,
                        amount,
                        "LO010300",
                        "",
                        reg_id,
                    ),
                )
            )

        rmk = self.SALES_RMK_FORMAT.format(market=market_name, corp=corp_name)
        sql_master = """
            INSERT INTO t_sales_master (
                sales_no, farm_cd, sales_dt, custm_id, sales_tp,
                tot_sales_amt, tot_ship_fee, tot_item_amt, tot_paid_amt, tot_unpaid_amt,
                auction_fee, extra_cost, bill_yn, bill_dt, bill_no,
                pay_method_cd, status_cd, rmk, reg_id, reg_dt,
                sales_status, sales_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?)
        """
        master_query = (
            sql_master,
            (
                sales_no,
                self.farm_cd,
                sales_dt,
                custm_id,
                None,
                total_item_amt,
                0,
                total_item_amt,
                0,
                total_item_amt,
                0,
                0,
                "N",
                None,
                None,
                None,
                self.SALES_DEFAULT_STATUS_CD,
                rmk,
                reg_id,
                self.SALES_STATUS_DRAFT,
                self.SALES_SOURCE_AUCTION_RT,
            ),
        )

        queries = [master_query]
        queries.extend(detail_queries)
        ok = self.db.execute_transaction(queries)
        if not ok:
            return False, "판매 초안 저장 트랜잭션이 실패했습니다."
        return True, f"판매 초안 저장 완료: {sales_no} ({len(rows)}건, DRAFT)"

    def open_market_analysis_tab(self):
        """대시보드 등에서 시장분석 탭으로 진입. 기본 탭이 0이라 인덱스가 안 바뀌면 currentChanged가 안 뜸 → 직접 로딩."""
        if not hasattr(self, "tabs") or self.tabs is None:
            return
        if self.tabs.currentIndex() == 0:
            self._load_market_analysis_from_db(
                prompt_if_missing=True,
                prefer_latest=False,
                update_date_picker=False,
            )
        else:
            self.tabs.setCurrentIndex(0)

    def _on_tab_changed(self, index: int):
        # 시장분석 탭(0) 진입 시 DB에 이미 존재하는 summary를 우선 표시한다.
        if int(index) == 0:
            self._load_market_analysis_from_db(
                prompt_if_missing=True,
                prefer_latest=False,
                update_date_picker=False,
            )

    def _build_content(self):
        # 상세 페이지는 자체 3섹션을 사용하므로 기본 summary 영역은 숨긴다.
        self.summary_frame.hide()
        self.main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)
        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.tabs.addTab(self._build_section_market_analysis_placeholder(), "시장분석")
        self.realtime_tab = RealtimeAuctionPage(self)
        self.settlement_tab = SettlementPage(self)
        self.tabs.addTab(self.realtime_tab, "실시간 경매")
        self.tabs.addTab(self.settlement_tab, "정산정보")
        self.tabs.setCurrentIndex(0)
        self.main_layout.addWidget(self.tabs)
        self.main_layout.addStretch()
        self.main_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

    def _build_sidebar(self):
        # 시장/경매 상세는 우측 바로가기 프레임 없이 본문에 집중한다.
        if hasattr(self, "sidebar") and self.sidebar is not None:
            self.sidebar.hide()
            self.sidebar.setFixedWidth(0)

    def _create_section_card(self, title: str, subtitle: str = ""):
        card = QFrame()
        card.setStyleSheet(MainStyles.CARD)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(*SECTION_CONTENT_MARGINS)
        layout.setSpacing(SECTION_SPACING)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(MainStyles.DASH_CARD_TITLE + " color:#2D3748;")
        layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(MainStyles.TXT_CAPTION + " color:#718096;")
            layout.addWidget(sub_lbl)

        return card, layout

    def _build_section_market_analysis_placeholder(self):
        card = QFrame()
        card.setStyleSheet(MainStyles.CARD)
        root = QVBoxLayout(card)
        root.setContentsMargins(*SECTION_CONTENT_MARGINS)
        root.setSpacing(SECTION_SPACING)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        title_lbl = QLabel("시장분석")
        title_lbl.setStyleSheet(MainStyles.DASH_CARD_TITLE + " color:#2D3748;")
        title_row.addWidget(title_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        help_btn = QToolButton()
        help_btn.setText("?")
        help_btn.setToolTip(MARKET_ANALYSIS_HELP_TOOLTIP)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setAutoRaise(True)
        help_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        help_btn.setStyleSheet(MainStyles.BTN_HELP_TOOLTIP + MainStyles.TOOLTIP_LIGHT)
        title_row.addWidget(help_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch()
        root.addLayout(title_row)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        self.btn_market_analysis_fetch = QPushButton("기초데이터 가져오기")
        self.btn_market_analysis_fetch.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_market_analysis_fetch.clicked.connect(self._on_market_analysis_fetch_clicked)
        btn_row.addWidget(self.btn_market_analysis_fetch)
        self.btn_market_analysis_reset = QPushButton("기존 분석 데이터 초기화")
        self.btn_market_analysis_reset.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_market_analysis_reset.clicked.connect(self._on_market_analysis_reset_clicked)
        btn_row.addWidget(self.btn_market_analysis_reset)
        self.btn_market_analysis_verify_popup = QPushButton("데이터 검증")
        self.btn_market_analysis_verify_popup.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
        self.btn_market_analysis_verify_popup.clicked.connect(self._on_market_analysis_verify_clicked)
        btn_row.addWidget(self.btn_market_analysis_verify_popup)
        if DEBUG_MARKET_VERIFY:
            self.btn_download_verify = QPushButton("데이터 검증 다운로드")
            self.btn_download_verify.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)
            self.btn_download_verify.clicked.connect(self._download_verify_data)
            btn_row.addWidget(self.btn_download_verify)
        btn_row.addStretch()
        root.addLayout(btn_row)
        self.lbl_market_analysis_status = QLabel("준비됨")
        self.lbl_market_analysis_status.setStyleSheet(MARKET_ANALYSIS_STATUS_LBL_STYLE)
        root.addWidget(self.lbl_market_analysis_status)
        self.lbl_market_analysis_latest = QLabel("최신 업데이트: -")
        self.lbl_market_analysis_latest.setStyleSheet(MARKET_ANALYSIS_LATEST_LBL_STYLE)
        root.addWidget(self.lbl_market_analysis_latest)

        self.analysis_placeholder_card = QFrame()
        self.analysis_placeholder_card.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px dashed #CBD5E0;border-radius:10px;}"
        )
        _apply_chart_size_policy_expand_horizontal(self.analysis_placeholder_card)
        ph_lay = QVBoxLayout(self.analysis_placeholder_card)
        ph_lay.setContentsMargins(8, 8, 8, 8)
        ph_lay.setSpacing(6)
        self.analysis_signal_card = QFrame()
        _apply_chart_size_policy_expand_horizontal(self.analysis_signal_card)
        self.analysis_signal_card.setStyleSheet(
            "QFrame{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;}"
        )
        sig_outer = QVBoxLayout(self.analysis_signal_card)
        sig_outer.setContentsMargins(10, 8, 10, 8)
        sig_outer.setSpacing(6)
        sig_row = QHBoxLayout()
        sig_row.setSpacing(16)

        # 왼쪽: 판단 도넛 — 가로 3등분 중 1열
        left_box = QWidget()
        left_lay = QVBoxLayout(left_box)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)
        lbl_pan_title = QLabel("판단")
        lbl_pan_title.setStyleSheet(MainStyles.DASH_LABEL + " color:#718096;")
        lbl_pan_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        left_lay.addWidget(lbl_pan_title)
        self.analysis_signal_donut = DecisionDonutWidget()
        left_lay.addWidget(self.analysis_signal_donut, 0, Qt.AlignmentFlag.AlignHCenter)
        dc0, dp0 = self._analysis_signal_donut_style("관망")
        self.analysis_signal_donut.set_decision("관망", dc0, dp0)
        sig_row.addWidget(left_box, 1, Qt.AlignmentFlag.AlignTop)

        def _metric_pair(key: str, default: str):
            """라벨·값은 10px 간격으로 붙이고, 남는 폭만 행 끝에 배치."""
            wrap = QWidget()
            hl = QHBoxLayout(wrap)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(0)
            lk = QLabel(key)
            lk.setStyleSheet(MainStyles.DASH_LABEL + " color:#718096;")
            lv = QLabel(default)
            lv.setStyleSheet(MainStyles.DASH_SUMMARY_VALUE + " color:#4A5568;")
            hl.addWidget(lk, 0, Qt.AlignmentFlag.AlignVCenter)
            hl.addSpacing(10)
            hl.addWidget(lv, 0, Qt.AlignmentFlag.AlignVCenter)
            hl.addStretch(1)
            return wrap, lv

        mid_col = QWidget()
        mid_lay = QVBoxLayout(mid_col)
        mid_lay.setContentsMargins(0, 0, 0, 0)
        mid_lay.setSpacing(6)
        w1, v1 = _metric_pair("대표 가격", "-")
        w2, v2 = _metric_pair("7일 대비", "-")
        mid_lay.addWidget(w1)
        mid_lay.addWidget(w2)
        sig_row.addWidget(mid_col, 1)

        right_col = QWidget()
        right_lay = QVBoxLayout(right_col)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)
        w3, v3 = _metric_pair("전일 대비", "-")
        w4, v4 = _metric_pair("30일 대비", "-")
        right_lay.addWidget(w3)
        right_lay.addWidget(w4)
        sig_row.addWidget(right_col, 1)

        self.analysis_signal_labels = {
            "대표 가격": v1,
            "7일 대비": v2,
            "전일 대비": v3,
            "30일 대비": v4,
        }
        sig_outer.addLayout(sig_row)
        self.lbl_analysis_signal_hint = QLabel("기준: 특·골드특 / 25과 이내 / 15kg")
        self.lbl_analysis_signal_hint.setStyleSheet(MainStyles.TXT_CAPTION + " color:#A0AEC0;")
        sig_outer.addWidget(self.lbl_analysis_signal_hint)

        # 요약 카드 + 그래프 4개를 동일 가로 폭 컬럼으로 묶어 정렬 일치
        self.analysis_charts_column = QWidget()
        _apply_chart_size_policy_expand_horizontal(self.analysis_charts_column)
        acc_lay = QVBoxLayout(self.analysis_charts_column)
        acc_lay.setContentsMargins(0, 0, 0, 0)
        acc_lay.setSpacing(8)
        acc_lay.addWidget(self.analysis_signal_card)

        charts_wrap = QFrame()
        charts_wrap.setStyleSheet("QFrame{background:transparent; border:none;}")
        _apply_chart_size_policy_expand_horizontal(charts_wrap)
        charts_lay = QVBoxLayout(charts_wrap)
        charts_lay.setContentsMargins(0, 2, 0, 0)
        charts_lay.setSpacing(8)
        self.chart_rep_price = RepresentativePriceChartWidget("")
        self.chart_volume = SimpleTrendChartWidget("", "")
        self.chart_volume.set_volume_mode(True)
        self.chart_volume.set_unit_caption("")
        self.chart_volume.set_base_value_annotation(True, "")
        self.chart_quality = DualRatioTrendChartWidget("")
        self.chart_price_structure = MultiLinePriceChartWidget("")
        for _cw in (
            self.chart_rep_price,
            self.chart_price_structure,
            self.chart_volume,
            self.chart_quality,
        ):
            _apply_chart_size_policy_expand_horizontal(_cw)

        box_rep, self.lbl_chart_title_rep, self.lbl_chart_value_rep, self.lbl_chart_footer_price = (
            _create_analysis_chart_block(
                self.chart_rep_price,
                footer_style_sheet=ANALYSIS_CHART12_FOOTER_STYLE,
            )
        )
        self.lbl_chart_title_rep.setText(
            "대표 가격 추이 (최근 30거래일 · 특·골드특·25과·15kg)"
        )
        charts_lay.addWidget(box_rep)

        price_type_header = QWidget()
        pth_lay = QHBoxLayout(price_type_header)
        pth_lay.setContentsMargins(0, 0, 0, 0)
        pth_lay.setSpacing(6)
        lbl_pt = QLabel("가격 기준:")
        lbl_pt.setStyleSheet(MainStyles.DASH_LABEL + " color:#4A5568;")
        self.cmb_price_type = QComboBox()
        self._apply_filter_control_style(self.cmb_price_type)
        self.cmb_price_type.addItems(["최고가", "평균가", "최저가"])
        self.cmb_price_type.setCurrentText("최고가")
        self.cmb_price_type.currentTextChanged.connect(self._on_price_type_changed)
        pth_lay.addWidget(lbl_pt)
        pth_lay.addWidget(self.cmb_price_type)

        box_struct, self.lbl_chart_title_structure, self.lbl_chart_value_structure, self.lbl_chart_legend_structure, self.lbl_chart_footer_structure = (
            _create_price_structure_chart_block(
                self.chart_price_structure,
                footer_style_sheet=ANALYSIS_CHART12_FOOTER_STYLE,
                title_right_widget=price_type_header,
            )
        )
        self.lbl_chart_title_structure.setText(self._structure_chart_title())
        charts_lay.addWidget(box_struct)

        box_vol, self.lbl_chart_title_volume, self.lbl_chart_value_volume, self.lbl_chart_footer_volume = (
            _create_analysis_chart_block(
                self.chart_volume,
                footer_style_sheet=ANALYSIS_CHART12_FOOTER_STYLE,
            )
        )
        self.lbl_chart_title_volume.setText("거래량 추이 (15kg 환산 상자수)")
        charts_lay.addWidget(box_vol)

        box_qual, self.lbl_chart_title_quality, self.lbl_chart_value_quality, self.lbl_chart_footer_quality = (
            _create_analysis_chart_block(
                self.chart_quality,
                footer_style_sheet=ANALYSIS_CHART12_FOOTER_STYLE,
            )
        )
        self.lbl_chart_title_quality.setText("품질 비중 추이 (최근 30거래일 · %)")
        charts_lay.addWidget(box_qual)
        acc_lay.addWidget(charts_wrap)
        ph_lay.addWidget(self.analysis_charts_column)

        root.addWidget(self.analysis_placeholder_card)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        return card

    def _execute_market_analysis_import_pipeline(self):
        """기초데이터 가져오기 버튼과 동일: 적재 → 요약 표시 → DB 기준 화면 갱신."""
        result = self._run_analysis_import()
        self._render_analysis_result(result)
        # fetch 완료 후 자동 갱신(중복 로딩은 _load_market_analysis_from_db 내부 플래그로 방지)
        self._load_market_analysis_from_db(
            prompt_if_missing=False,
            prefer_latest=True,
            update_date_picker=False,
        )
        return result

    @staticmethod
    def _verification_fully_matches(rep: dict) -> bool:
        """SALE API·DB·summary 비교가 모두 일치하면 True."""
        if not rep:
            return False
        if int(rep.get("miss") or 0) > 0:
            return False
        if int(rep.get("extra") or 0) > 0:
            return False
        if int(rep.get("mismatch") or 0) > 0:
            return False
        sc = rep.get("summary_cmp") or {}
        if sc.get("status") == "missing_summary":
            return False

        def _near_zero(v) -> bool:
            if v is None:
                return True
            try:
                return abs(float(v)) < 1e-5
            except (TypeError, ValueError):
                return False

        for key in (
            "avg_price_diff",
            "representative_avg_price_diff",
            "max_price_diff",
            "min_price_diff",
            "quantity_diff",
            "special_ratio_diff",
            "large_ratio_diff",
            "within20_ratio_diff",
            "representative_max_price_diff",
            "representative_min_price_diff",
            "representative_quantity_diff",
        ):
            if not _near_zero(sc.get(key)):
                return False
        return True

    def _run_market_analysis_validation(self) -> dict:
        """API↔DB↔summary 정합성 검증을 실행하고 리포트를 반환."""
        return self._build_market_analysis_verify_report()

    def _has_market_analysis_validation_error(self, rep: dict) -> bool:
        """검증 오류 판정: API/DB 불일치, summary 누락/불일치, 경고 텍스트."""
        if not rep:
            return True
        if int(rep.get("miss") or 0) > 0:
            return True
        if int(rep.get("extra") or 0) > 0:
            return True
        if int(rep.get("mismatch") or 0) > 0:
            return True
        sc = rep.get("summary_cmp") or {}
        if sc.get("status") in ("missing_summary", "error"):
            return True
        for key in (
            "avg_price_diff",
            "representative_avg_price_diff",
            "max_price_diff",
            "min_price_diff",
            "quantity_diff",
            "special_ratio_diff",
            "large_ratio_diff",
            "within20_ratio_diff",
            "representative_max_price_diff",
            "representative_min_price_diff",
            "representative_quantity_diff",
        ):
            v = sc.get(key)
            if v in (None, ""):
                continue
            try:
                if abs(float(v)) > 1e-5:
                    return True
            except (TypeError, ValueError):
                return True
        text = str(rep.get("text") or "").lower()
        if ("error" in text) or ("warning" in text):
            return True
        return False

    def _recover_market_analysis_data_if_needed(self) -> tuple[bool, str]:
        """오류 시 1회 자동 복구: 데이터 재가져오기 + 재집계 + 화면 갱신."""
        try:
            self.btn_market_analysis_fetch.setEnabled(False)
            self.btn_market_analysis_fetch.setText("가져오는 중...")
            self._execute_market_analysis_import_pipeline()
            return True, ""
        except Exception as e:
            return False, str(e)
        finally:
            self.btn_market_analysis_fetch.setEnabled(True)
            self.btn_market_analysis_fetch.setText("기초데이터 가져오기")

    def _on_market_analysis_fetch_clicked(self):
        if self.market_analysis_service is None or self.settlement_manager is None:
            self.lbl_market_analysis_status.setText("시장분석 서비스 초기화 실패")
            return
        self.btn_market_analysis_fetch.setEnabled(False)
        self.btn_market_analysis_fetch.setText("가져오는 중...")
        try:
            self._execute_market_analysis_import_pipeline()
        except Exception as e:
            self.lbl_market_analysis_status.setText(f"시장분석 처리 실패: {e}")
        finally:
            self.btn_market_analysis_fetch.setEnabled(True)
            self.btn_market_analysis_fetch.setText("기초데이터 가져오기")

    def _on_market_analysis_reset_clicked(self):
        if self.market_analysis_service is None:
            self._set_market_analysis_status("초기화 실패: 서비스 미초기화")
            return
        reply = QMessageBox.question(
            self,
            "분석 데이터 초기화",
            (
                "집계 요약(summary)만 삭제합니다.\n"
                "API로 저장된 기초 데이터(settlement)는 그대로 둡니다.\n\n"
                "계속할까요?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.market_analysis_service.reset_analysis_data()
            self._market_analysis_detail_pack = {}
            self._render_analysis_metrics({})
            self._render_analysis_charts({}, None)
            self._update_market_analysis_latest_label("")
            self._set_market_analysis_status(
                "초기화 완료: summary 삭제됨. 기초데이터(settlement)는 유지."
            )
            # reset 완료 후 자동 재조회(중복 로딩은 _analysis_loading 플래그로 방지)
            self._load_market_analysis_from_db(
                prompt_if_missing=False,
                prefer_latest=False,
                update_date_picker=False,
            )
            QMessageBox.information(
                self,
                "초기화 완료",
                (
                    "집계 요약(summary)을 삭제했습니다.\n"
                    "기초 데이터는 유지되었습니다.\n"
                    "다시 집계하려면 '기초데이터 가져오기'를 실행하세요."
                ),
            )
        except Exception as e:
            self._set_market_analysis_status(f"초기화 실패: {e}")

    def _build_market_analysis_verify_report(self):
        """SALE API·DB·summary 검증 텍스트 (디버그 버튼·팝업 공용)."""
        if self.market_analysis_service is None:
            return {"text": "서비스 미초기화", "compare_trade_date": "", "miss": 0, "extra": 0, "mismatch": 0}
        filters = self._current_filter_values()
        base_date = self._get_analysis_base_date()
        compare_trade_date = base_date
        latest = self.market_analysis_service.get_latest_summary_date(
            variety=filters.get("variety"),
            market=filters.get("market"),
            on_or_before=base_date,
        )
        if latest:
            compare_trade_date = latest
        api_vs_db = self.market_analysis_service.compare_api_vs_db(
            compare_trade_date,
            filters.get("variety"),
            filters.get("market"),
        )
        summary_cmp = self.market_analysis_service.compare_summary(
            compare_trade_date,
            filters.get("variety"),
            filters.get("market"),
        )
        miss = len(api_vs_db.get("missing_in_db") or [])
        extra = len(api_vs_db.get("extra_in_db") or [])
        mismatch = len(api_vs_db.get("mismatch_rows") or [])
        lines = [
            "SALE API vs DB 비교 결과",
            f"- 거래일: {compare_trade_date}",
            f"- API 건수: {api_vs_db.get('api_count', 0)} (raw {api_vs_db.get('api_raw_count', 0)})",
            f"- DB 건수: {api_vs_db.get('db_count', 0)}",
            f"- 누락(missing_in_db): {miss}건",
            f"- 초과(extra_in_db): {extra}건",
            f"- 값 불일치(mismatch): {mismatch}건",
            "",
            "Summary 비교",
            f"- avg diff: {summary_cmp.get('avg_price_diff')}",
            f"- representative_avg diff: {summary_cmp.get('representative_avg_price_diff')}",
            f"- max diff: {summary_cmp.get('max_price_diff')}",
            f"- min diff: {summary_cmp.get('min_price_diff')}",
            f"- qty diff: {summary_cmp.get('quantity_diff')}",
                f"- special diff: {summary_cmp.get('special_ratio_diff')}",
                f"- large diff: {summary_cmp.get('large_ratio_diff')}",
                f"- within20 diff: {summary_cmp.get('within20_ratio_diff')}",
            ]
        mismatch_rows = list(api_vs_db.get("mismatch_rows") or [])
        if mismatch_rows:
            lines.append("")
            lines.append("미스매치 상위 5건")
            for idx, row in enumerate(mismatch_rows[:5], start=1):
                key = row.get("key") or {}
                corp = str(key.get("corporation") or "-")
                grade = str(key.get("grade") or "-")
                size = str(key.get("size") or "-")
                spec = str(key.get("spec") or "-")
                lines.append(
                    (
                        f"{idx}) 법인={corp}, 등급={grade}, 크기={size}, 규격={spec} | "
                        f"가격 API/DB={row.get('api_price', 0)}/{row.get('db_price', 0)}, "
                        f"수량 API/DB={row.get('api_qty', 0)}/{row.get('db_qty', 0)}"
                    )
                )
                raw_sale = list(row.get("raw_sale_values") or [])
                final_row = row.get("final_row") or {}
                db_row = row.get("db_row") or {}
                sale_pick = raw_sale[0] if raw_sale else {}
                lines.append(
                    f"   - raw sale(1st): price={sale_pick.get('price')}, qty={sale_pick.get('quantity')}, evidence={sale_pick.get('qty_evidence')}"
                )
                lines.append(
                    f"   - final_rows: price={final_row.get('price')}, qty={final_row.get('quantity')}, source={final_row.get('source')}, evidence={final_row.get('qty_evidence')}"
                )
                lines.append(
                    f"   - db 저장값: price={db_row.get('price')}, qty={db_row.get('quantity')}"
                )
        missing_list = list(api_vs_db.get("missing_in_db") or [])
        if miss > 0:
            lines.append("")
            lines.append("【누락·조치 안내】")
            lines.append(
                "· '기초데이터 가져오기'는 (1) summary가 없는 날과 "
                "(2) summary가 있어도 SALE API와 DB가 불일치하는 날을 재적재합니다."
            )
            lines.append(
                "· 아래 누락은 검증 시점 기준일 수 있습니다. "
                "가져오기 직후에는 검증을 다시 실행해 보세요."
            )
            dedup_col = api_vs_db.get("dedup_collision_count")
            raw_lost = api_vs_db.get("raw_to_final_lost_count")
            if dedup_col is not None or raw_lost is not None:
                lines.append(
                    f"· API 측 참고: 중복 병합 {dedup_col}건, "
                    f"raw→최종키 제외 {raw_lost}건 (API raw는 동일 키가 여러 줄일 수 있음)."
                )
            lines.append("")
            lines.append("누락 키 샘플 (최대 15건, 법인·등급·크기·규격)")
            for idx, mk in enumerate(missing_list[:15], start=1):
                lines.append(
                    f"  {idx}) {mk.get('corporation', '-')}"
                    f" | {mk.get('grade', '-')}"
                    f" | {mk.get('size', '-')}"
                    f" | {mk.get('spec', '-')}"
                )
            if len(missing_list) > 15:
                lines.append(f"  … 외 {len(missing_list) - 15}건")
        return {
            "text": "\n".join(lines),
            "compare_trade_date": compare_trade_date,
            "miss": miss,
            "extra": extra,
            "mismatch": mismatch,
            "summary_cmp": summary_cmp,
        }

    def _on_market_analysis_verify_clicked(self):
        if self._analysis_loading:
            QMessageBox.information(self, "데이터 검증", "현재 로딩 중입니다. 잠시 후 다시 시도하세요.")
            return
        if self.market_analysis_service is None:
            self._set_market_analysis_status("검증 실패: 서비스 미초기화")
            return
        if self.settlement_manager is None:
            self._set_market_analysis_status("검증 후 적재 불가: settlement 서비스 미초기화")
            return
        try:
            rep_before = self._run_market_analysis_validation()
            has_error = self._has_market_analysis_validation_error(rep_before)
            if not has_error:
                QMessageBox.information(self, "데이터 검증", "데이터 검증 완료: 이상이 없습니다.")
                self._set_market_analysis_status("데이터 검증 완료: 이상이 없습니다.")
                self._on_market_analysis_verify_dialog(report=rep_before)
                return

            QMessageBox.information(
                self,
                "데이터 검증",
                "데이터 오류가 감지되었습니다. 최신 데이터를 다시 가져오고 재집계를 진행합니다.",
            )
            self._set_market_analysis_status("데이터 오류 감지 → 자동 재처리 진행 중...")
            ok, err = self._recover_market_analysis_data_if_needed()
            rep_after = self._run_market_analysis_validation()
            if ok:
                QMessageBox.information(
                    self,
                    "데이터 검증",
                    "데이터 재정합이 완료되었습니다. 검증 결과를 확인하세요.",
                )
                self._set_market_analysis_status("데이터 재정합이 완료되었습니다. 검증 결과를 확인하세요.")
            else:
                QMessageBox.warning(
                    self,
                    "데이터 검증",
                    "데이터 재처리에 실패했습니다. 검증 결과를 확인하세요.",
                )
                self._set_market_analysis_status(f"데이터 재처리 실패: {err}")
            self._on_market_analysis_verify_dialog(report=rep_after)
        except Exception as e:
            self._set_market_analysis_status(f"검증 실패: {e}")

    def _fill_market_analysis_preview_table(self, table: QTableWidget, rows: list):
        table.clearContents()
        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows or []):
            values = [
                row.get("trade_date") or "-",
                row.get("normalized_variety") or "-",
                row.get("market") or "-",
                f"{self._to_int(row.get('avg_price')):,}",
                f"{self._to_int(row.get('representative_avg_price')):,}",
                f"{self._to_int(row.get('max_price')):,}",
                f"{self._to_int(row.get('min_price')):,}",
            ]
            for c_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r_idx, c_idx, item)

    def _on_market_analysis_verify_dialog(self, report: dict | None = None):
        pack = self._market_analysis_detail_pack or {}
        metrics = pack.get("metrics") or {}
        dlg = QDialog(self)
        dlg.setWindowTitle("데이터 검증 결과")
        dlg.resize(920, 560)
        lay = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        top_parts = [
            "【summary·적재 요약】",
            "\n".join(pack.get("import_lines") or ["데이터를 불러오면 여기에 요약이 표시됩니다."]),
            "",
            "【판단 근거 문구】",
        ]
        rl = list(metrics.get("reason_lines") or [])
        if rl:
            top_parts.extend(f"- {x}" for x in rl)
        else:
            top_parts.append("(근거 문구 없음)")
        top_parts.append("")
        if report is not None:
            top_parts.append("【API·DB·summary 검증】")
            top_parts.append(str(report.get("text") or ""))
        elif self.market_analysis_service:
            try:
                rep = self._build_market_analysis_verify_report()
                top_parts.append("【API·DB·summary 검증】")
                top_parts.append(rep.get("text") or "")
            except Exception as e:
                top_parts.append(f"검증 조회 실패: {e}")
        else:
            top_parts.append("시장분석 서비스가 초기화되지 않았습니다.")
        te.setPlainText("\n".join(top_parts))
        lay.addWidget(te, 1)
        tbl = QTableWidget()
        tbl.setColumnCount(7)
        tbl.setHorizontalHeaderLabels(
            ["거래일", "품종", "시장", "전체평균", "대표평균", "최고가", "최저가"]
        )
        tbl.setStyleSheet(MainStyles.TABLE)
        _vh = tbl.horizontalHeader()
        _vh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for _ci in range(1, 7):
            _vh.setSectionResizeMode(_ci, QHeaderView.ResizeMode.Stretch)
        _vh.setMinimumSectionSize(72)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._fill_market_analysis_preview_table(tbl, pack.get("preview_rows") or [])
        lay.addWidget(tbl, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    def _wrap_filter(self, widget: QWidget):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(widget)
        return wrap

    def _apply_filter_control_style(self, widget: QWidget):
        widget.setStyleSheet(MainStyles.COMBO)
        if hasattr(widget, "setFixedHeight"):
            widget.setFixedHeight(FILTER_CONTROL_HEIGHT)
        # 차트 등 위에 팝업이 겹칠 때 투명해지는 환경 대비(공통 콤보 가독성)
        if isinstance(widget, QComboBox):
            v = widget.view()
            if v is not None:
                v.setAutoFillBackground(True)

    def _apply_quick_date_button_style(self, btn: QPushButton):
        btn.setStyleSheet(MainStyles.BTN_SECONDARY_COMPACT)

    def _set_market_analysis_status(self, text: str):
        if hasattr(self, "lbl_market_analysis_status") and self.lbl_market_analysis_status is not None:
            self.lbl_market_analysis_status.setText(str(text or ""))
            QApplication.processEvents()

    def _resolve_analysis_market_code(self, market_name: str):
        text = str(market_name or "").strip()
        return ANALYSIS_MARKET_CODE_BY_NAME.get(text, ANALYSIS_DEFAULT_MARKET_CODE)

    def _resolve_analysis_item_code(self, variety_name: str):
        text = str(variety_name or "").strip()
        return ANALYSIS_ITEM_CODE_BY_VARIETY.get(text, ANALYSIS_DEFAULT_ITEM_CODE)

    def _get_analysis_base_date(self):
        return QDate.currentDate().toString("yyyy-MM-dd")

    def _collect_missing_dates(self, base_date: str, lookback_days: int = ANALYSIS_LOOKBACK_DAYS):
        base_dt = datetime.strptime(base_date, "%Y-%m-%d")
        start_dt = base_dt - timedelta(days=max(1, int(lookback_days)) - 1)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = base_date
        all_dates = []
        for idx in range(max(1, int(lookback_days))):
            d = (start_dt + timedelta(days=idx)).strftime("%Y-%m-%d")
            all_dates.append(d)
        existing_dates = set(
            self.market_analysis_service.get_existing_dates(start_date, end_date) or []
        )
        missing_dates = [d for d in all_dates if d not in existing_dates]
        return {
            "start_date": start_date,
            "end_date": end_date,
            "all_dates": all_dates,
            "existing_dates": sorted(existing_dates),
            "missing_dates": missing_dates,
        }

    def _fetch_analysis_settlement_rows(self, trade_date: str, market_code: str, item_code: str):
        collected_rows = []
        had_error = False
        try:
            sale_rows = self.settlement_manager.fetch_sale_data(trade_date, market_code, item_code) or []
            for row in sale_rows:
                if isinstance(row, dict):
                    row["__source"] = "sale"
            collected_rows.extend(sale_rows)
        except Exception as e:
            print(f"[MarketAnalysis] sale fetch failed date={trade_date} error={e}")
            had_error = True
        return collected_rows, had_error

    def _run_analysis_import(self):
        filters = self._current_filter_values()
        base_date = self._get_analysis_base_date()
        missing_pack = self._collect_missing_dates(base_date, ANALYSIS_LOOKBACK_DAYS)
        all_dates = list(missing_pack.get("all_dates") or [])
        start_date = missing_pack.get("start_date")
        end_date = missing_pack.get("end_date")

        # 중요: 적재 대상은 "전체 settlement 존재 여부"가 아니라
        # 선택한 품종/시장 기준 summary 존재 여부로 계산해야 한다.
        existing_summary_rows = self.market_analysis_service.get_summary(
            start_date,
            end_date,
            filters.get("variety"),
            filters.get("market"),
        ) or []
        existing_dates_before = sorted(
            {
                str(r.get("trade_date") or "").strip()
                for r in existing_summary_rows
                if str(r.get("trade_date") or "").strip()
            }
        )
        existing_dates_set = set(existing_dates_before)
        missing_dates = [d for d in all_dates if d not in existing_dates_set]

        # summary가 있어도 API·DB 불일치면 재적재 대상에 포함
        reconcile_dates = []
        sorted_existing = sorted(existing_dates_set)
        for trade_date in sorted_existing:
            if trade_date not in all_dates:
                continue
            self._set_market_analysis_status(
                f"API·DB 정합성 점검... ({trade_date})"
            )
            try:
                if self.market_analysis_service.needs_settlement_reconcile(
                    trade_date,
                    filters.get("variety"),
                    filters.get("market"),
                ):
                    reconcile_dates.append(trade_date)
            except Exception as e:
                print(f"[MarketAnalysis] reconcile check failed date={trade_date} err={e}")

        fetch_dates = sorted(set(missing_dates) | set(reconcile_dates))

        market_code = self._resolve_analysis_market_code(filters.get("market"))
        item_code = self._resolve_analysis_item_code(filters.get("variety"))
        imported_dates = []
        failed_dates = []
        merge_collision_total = 0
        merge_selected_sale_total = 0

        self._set_market_analysis_status(
            f"최근 {ANALYSIS_LOOKBACK_DAYS}일 | "
            f"summary 없음 {len(missing_dates)}일 | "
            f"정합성 재적재 {len(reconcile_dates)}일 | "
            f"적재 예정 {len(fetch_dates)}일"
        )
        total_fetch = len(fetch_dates)
        for idx, trade_date in enumerate(fetch_dates, start=1):
            self._set_market_analysis_status(
                f"기초데이터 적재 중... ({idx}/{total_fetch}) {trade_date}"
            )
            rows, had_error = self._fetch_analysis_settlement_rows(
                trade_date, market_code, item_code
            )
            if rows:
                inserted = self.market_analysis_service.insert_settlement_data(rows)
                insert_stats = self.market_analysis_service.get_last_insert_stats()
                merge_collision_total += int(insert_stats.get("collision_count", 0))
                merge_selected_sale_total += int(insert_stats.get("selected_sale_count", 0))
                if inserted > 0:
                    imported_dates.append(trade_date)
            elif had_error:
                failed_dates.append(trade_date)
        self._set_market_analysis_status("summary 생성 대상 계산 중...")
        summary_missing_dates = self.market_analysis_service.get_dates_missing_summary(
            missing_pack["start_date"],
            missing_pack["end_date"],
            filters.get("variety"),
            filters.get("market"),
        ) or []
        summary_target_dates = []
        for d in imported_dates:
            if d not in summary_target_dates:
                summary_target_dates.append(d)
        summary_fill_dates = [d for d in summary_missing_dates if d not in summary_target_dates]
        summary_target_dates.extend(summary_fill_dates)

        self._set_market_analysis_status(
            f"summary 생성 중... (신규 {len(imported_dates)}일 / 보완 {len(summary_fill_dates)}일)"
        )
        summary_created_count = 0
        for trade_date in summary_target_dates:
            summary_created_count += int(
                self.market_analysis_service.build_summary_for_date(trade_date) or 0
            )

        summary_rows = self.market_analysis_service.get_summary(
            start_date,
            end_date,
            filters.get("variety"),
            filters.get("market"),
        ) or []
        metrics = self.market_analysis_service.get_analysis_metrics(
            base_date=base_date,
            variety=filters.get("variety"),
            market=filters.get("market"),
        )
        chart_series = self.market_analysis_service.get_chart_series(
            base_date=base_date,
            variety=filters.get("variety"),
            market=filters.get("market"),
            window=30,
        )
        # 예외 허용: 가격구조 4라인 차트는 summary 집계값이 아닌
        # settlement 세부 구간(특/상 × 20/25과) 계산이 필요해 직접 조회를 사용한다.
        price_structure_series = self.market_analysis_service.get_price_structure_series(
            base_date=base_date,
            variety=filters.get("variety"),
            market=filters.get("market"),
            window=30,
            price_type=self.current_price_type,
        )
        return {
            "base_date": base_date,
            "start_date": start_date,
            "end_date": end_date,
            "existing_before_count": len(existing_dates_before),
            "missing_count": len(missing_dates),
            "reconcile_dates": reconcile_dates,
            "reconcile_count": len(reconcile_dates),
            "fetch_dates_count": len(fetch_dates),
            "imported_count": len(imported_dates),
            "imported_dates": imported_dates,
            "failed_dates": failed_dates,
            "summary_new_dates_count": len(imported_dates),
            "summary_fill_dates_count": len(summary_fill_dates),
            "summary_target_dates_count": len(summary_target_dates),
            "summary_created_count": summary_created_count,
            "summary_rows": summary_rows,
            "summary_row_count": len(summary_rows),
            "merge_collision_count": merge_collision_total,
            "merge_selected_sale_count": merge_selected_sale_total,
            "metrics": metrics,
            "chart_series": chart_series,
            "price_structure_series": price_structure_series,
        }

    def _render_analysis_result(self, result: dict):
        payload = result or {}
        failed_dates = payload.get("failed_dates") or []
        metrics = payload.get("metrics") or {}
        self._render_analysis_metrics(metrics)
        self._render_analysis_charts(
            payload.get("chart_series") or {},
            metrics,
            payload.get("price_structure_series") or {},
        )
        lines = [
            f"기준일: {payload.get('base_date')}",
            f"조회범위: {payload.get('start_date')} ~ {payload.get('end_date')}",
            f"기존 존재 날짜 수: {payload.get('existing_before_count', 0)}",
            (
                f"적재: summary 없음 {payload.get('missing_count', 0)}일 + "
                f"API·DB 불일치 재적재 {payload.get('reconcile_count', 0)}일 "
                f"(처리 {payload.get('fetch_dates_count', 0)}일)"
            ),
            f"적재 완료(행 저장) 일수: {payload.get('imported_count', 0)}",
            (
                "summary 생성 대상: "
                f"신규 {payload.get('summary_new_dates_count', 0)}일 / "
                f"보완 {payload.get('summary_fill_dates_count', 0)}일"
            ),
            f"summary 생성 건수: {payload.get('summary_created_count', 0)} (대상 {payload.get('summary_target_dates_count', 0)}일)",
            f"summary 조회 건수: {payload.get('summary_row_count', 0)}",
            (
                "sale 적재 점검: "
                f"충돌 {payload.get('merge_collision_count', 0)}건, "
                f"선택 sale {payload.get('merge_selected_sale_count', 0)}건"
            ),
        ]
        reason_lines = list((metrics or {}).get("reason_lines") or [])
        if reason_lines:
            lines.append("근거:")
            for idx, reason in enumerate(reason_lines[:20], start=1):
                lines.append(f"{idx}. {reason}")
        if failed_dates:
            lines.append(f"적재 실패 날짜: {', '.join(failed_dates[:10])}")
        rows = list(payload.get("summary_rows") or [])
        # 데이터 검증 결과 테이블에 summary 전체 표시(이전 [:20] 미리보기 제한 제거)
        preview_rows = rows
        self._market_analysis_detail_pack = {
            "base_date": payload.get("base_date"),
            "requested_date": payload.get("requested_date"),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "summary_row_count": payload.get("summary_row_count"),
            "metrics": metrics,
            "import_lines": lines,
            "preview_rows": preview_rows,
            "failed_dates": failed_dates,
        }

        rc = int(payload.get("reconcile_count") or 0)
        if failed_dates:
            self._set_market_analysis_status(
                f"완료 (적재 {payload.get('imported_count', 0)}일"
                f", 정합성 재적재 대상 {rc}일, 실패 {len(failed_dates)}일)"
            )
        else:
            self._set_market_analysis_status(
                f"완료 (적재 {payload.get('imported_count', 0)}일"
                f", 정합성 재적재 적용 {rc}일)"
            )

    def _trade_date_to_mmdd(self, trade_date) -> str:
        t = str(trade_date or "").strip()
        if len(t) >= 10 and t[4] == "-" and t[7] == "-":
            return f"{t[5:7]}-{t[8:10]}"
        return ""

    def _build_chart_footer_price(self, metrics: dict) -> str:
        if (metrics or {}).get("status") != "ok":
            return ""
        d30 = metrics.get("d30")
        if d30 is None:
            return ""
        try:
            v = float(d30)
        except Exception:
            return ""
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f}% (30일 평균)"

    def _build_chart_footer_volume(self, metrics: dict) -> str:
        if (metrics or {}).get("status") != "ok":
            return ""
        qd = metrics.get("quantity_delta")
        if qd is None:
            return "30일 평균 대비 비교 없음"
        try:
            qf = float(qd)
        except Exception:
            return "비교 정보 없음"
        if qf > 0.5:
            return "30일 평균보다 높음"
        if qf < -0.5:
            return "30일 평균보다 낮음"
        return "30일 평균과 유사"

    def _build_chart_footer_quality(self, metrics: dict) -> str:
        if (metrics or {}).get("status") != "ok":
            return ""
        sd = metrics.get("special_ratio_delta")
        wd = metrics.get("within20_ratio_delta")
        parts = []
        try:
            sf = float(sd) if sd is not None else None
        except Exception:
            sf = None
        try:
            wf = float(wd) if wd is not None else None
        except Exception:
            wf = None
        if sf is not None:
            if sf > 0.5:
                parts.append("특↑")
            elif sf < -0.5:
                parts.append("특↓")
        if wf is not None:
            if wf > 0.5:
                parts.append("20과↑")
            elif wf < -0.5:
                parts.append("20과↓")
        if not parts:
            return "최근 30일 변화 작음"
        return " / ".join(parts)

    def _structure_chart_title(self):
        t = getattr(self, "current_price_type", "max")
        label = {"max": "최고가", "avg": "평균가", "min": "최저가"}.get(t, "최고가")
        return f"가격 구조 추이 (30거래일, {label} 기준)"

    def _structure_footer_text(self):
        t = getattr(self, "current_price_type", "max")
        if t == "avg":
            return "평균가 기준"
        if t == "min":
            return "최저가 기준"
        return "최고가 기준"

    def _structure_series_value_lines(self, ps_rows: list, base_idx: int) -> str:
        """기준일 행의 4계열 값(차트 외 QLabel). 플롯 내부 drawText와 동일한 유효성(>0)."""
        short = ("특≤20", "특≤25", "상≤20", "상≤25")
        keys = ("special_20", "special_25", "gradeA_20", "gradeA_25")
        if base_idx < 0 or not ps_rows or base_idx >= len(ps_rows):
            return ""
        pt = ps_rows[base_idx]
        lines = []
        for si, key in enumerate(keys):
            raw = pt.get(key)
            vy = None
            if raw is not None:
                try:
                    fv = float(raw)
                    vy = fv if fv > 0 else None
                except Exception:
                    vy = None
            if vy is None:
                continue
            lines.append(f"{short[si]} {float(vy):,.0f}")
        return "\n".join(lines)

    def _fmt_analysis_chart_header_rep_price(self, rep_points: list, base_idx: int) -> str:
        if base_idx < 0 or not rep_points or base_idx >= len(rep_points):
            return ""
        _, v = rep_points[base_idx]
        if v is None:
            return ""
        try:
            return f"{float(v):,.0f}원"
        except Exception:
            return ""

    def _fmt_analysis_chart_header_volume(self, vol_points: list, base_idx: int) -> str:
        if base_idx < 0 or not vol_points or base_idx >= len(vol_points):
            return ""
        _, v = vol_points[base_idx]
        if v is None:
            return ""
        try:
            return f"{float(v):,.0f}"
        except Exception:
            return ""

    def _fmt_analysis_chart_header_quality(self, qual_points: list, base_idx: int) -> str:
        if base_idx < 0 or not qual_points or base_idx >= len(qual_points):
            return ""
        _, av, bv = qual_points[base_idx]
        lines = []
        if av is not None:
            lines.append(f"특 {float(av):.1f}%")
        if bv is not None:
            lines.append(f"20과 {float(bv):.1f}%")
        return "\n".join(lines)

    def _apply_price_structure_ui(self, ps_pack):
        if not hasattr(self, "chart_price_structure"):
            return
        ps_pack = ps_pack or {}
        self.chart_price_structure.set_title("")
        self.chart_price_structure.set_basis_caption("")
        self.chart_price_structure.set_y_axis_caption("")
        ps_rows = list(ps_pack.get("series") or [])
        ps_points = []
        for r in ps_rows:
            ps_points.append(
                (
                    r.get("trade_date"),
                    r.get("special_20"),
                    r.get("special_25"),
                    r.get("gradeA_20"),
                    r.get("gradeA_25"),
                )
            )
        base_ps = next((i for i, r in enumerate(ps_rows) if r.get("is_base")), -1)
        if len(ps_points) >= 2:
            self.chart_price_structure.set_structure_data(ps_points, base_ps)
            ds_ps = self._trade_date_to_mmdd(ps_points[0][0])
            if base_ps >= 0:
                de_ps = self._trade_date_to_mmdd(ps_points[base_ps][0])
            else:
                de_ps = self._trade_date_to_mmdd(ps_points[-1][0])
            self.chart_price_structure.set_date_range_caption(ds_ps, de_ps)
        else:
            self.chart_price_structure.set_structure_data([], -1)
            self.chart_price_structure.set_date_range_caption("", "")
        if hasattr(self, "lbl_chart_footer_structure"):
            self.lbl_chart_footer_structure.setText(self._structure_footer_text())
        if hasattr(self, "lbl_chart_title_structure"):
            self.lbl_chart_title_structure.setText(self._structure_chart_title())
        if hasattr(self, "lbl_chart_value_structure"):
            self.lbl_chart_value_structure.setText("")

    def _on_price_type_changed(self, text):
        self.current_price_type = _map_price_type(text)
        self._reload_analysis_graphs()

    def _reload_analysis_graphs(self):
        if self.market_analysis_service is None or not hasattr(self, "chart_price_structure"):
            return
        filters = self._current_filter_values()
        base_date, _requested = self._resolve_analysis_base_date(
            prompt_if_missing=False,
            prefer_latest=False,
            update_date_picker=False,
        )
        if not base_date:
            return
        # 예외 허용: 가격구조 차트는 settlement 기반 직접 계산.
        ps = self.market_analysis_service.get_price_structure_series(
            base_date,
            filters.get("variety"),
            filters.get("market"),
            window=30,
            price_type=self.current_price_type,
        )
        self._apply_price_structure_ui(ps)

    def _render_analysis_charts(
        self, chart_payload: dict, metrics=None, price_structure_payload: dict = None
    ):
        if not all(
            hasattr(self, attr)
            for attr in (
                "chart_rep_price",
                "chart_price_structure",
                "chart_volume",
                "chart_quality",
            )
        ):
            return
        m = metrics if metrics is not None else (self._market_analysis_detail_pack or {}).get("metrics") or {}
        for fn in (
            "lbl_chart_footer_price",
            "lbl_chart_footer_structure",
            "lbl_chart_footer_volume",
            "lbl_chart_footer_quality",
        ):
            if hasattr(self, fn):
                getattr(self, fn).setText("")
        for attr in (
            "lbl_chart_value_rep",
            "lbl_chart_value_volume",
            "lbl_chart_value_quality",
            "lbl_chart_value_structure",
        ):
            if hasattr(self, attr):
                getattr(self, attr).setText("")
        self.chart_rep_price.set_date_range_caption("", "")
        self.chart_price_structure.set_date_range_caption("", "")
        self.chart_volume.set_date_range_caption("", "")
        self.chart_quality.set_date_range_caption("", "")

        series_rows = list((chart_payload or {}).get("series") or [])
        if len(series_rows) < 2:
            self.chart_rep_price.set_chart_data([], -1)
            self.chart_rep_price.set_reference_lines([])
            self.chart_volume.set_chart_data([], -1)
            self.chart_volume.set_base_value_annotation(True, "")
            self.chart_quality.set_dual_chart_data([], -1, "", "")
            ps_empty = price_structure_payload if price_structure_payload is not None else {}
            self._apply_price_structure_ui(ps_empty)
            return
        base_idx = next((i for i, r in enumerate(series_rows) if r.get("is_base")), -1)
        rep_points = []
        vol_points = []
        qual_points = []
        for r in series_rows:
            rp = r.get("representative_avg_price")
            if rp is None:
                rp = r.get("avg_price")
            rep_points.append((r.get("trade_date"), rp))
            vol_points.append((r.get("trade_date"), r.get("total_quantity")))
            qual_points.append(
                (
                    r.get("trade_date"),
                    r.get("special_ratio"),
                    r.get("within20_ratio"),
                )
            )

        before = series_rows[:base_idx] if base_idx > 0 else []
        rep_vals = []
        for r in before:
            v = r.get("representative_avg_price")
            if v is None:
                v = r.get("avg_price")
            if v is not None:
                try:
                    rep_vals.append(float(v))
                except Exception:
                    pass
        last7 = rep_vals[-7:] if len(rep_vals) >= 7 else rep_vals
        last30 = rep_vals[-30:] if len(rep_vals) >= 30 else rep_vals
        h7 = sum(last7) / len(last7) if last7 else None
        h30 = sum(last30) / len(last30) if last30 else None
        ref_lines = []
        if h7 is not None:
            ref_lines.append(
                {"value": h7, "label": f"7일 {h7:,.0f}원", "color": "#805AD5"}
            )
        if h30 is not None:
            ref_lines.append(
                {"value": h30, "label": f"30일 {h30:,.0f}원", "color": "#DD6B20"}
            )
        self.chart_rep_price.set_reference_lines(ref_lines)
        self.chart_rep_price.set_chart_data(rep_points, base_idx)
        self.chart_volume.set_chart_data(vol_points, base_idx)
        self.chart_volume.set_base_value_annotation(True, "")
        self.chart_quality.set_dual_chart_data(
            qual_points,
            base_idx,
            "특품비중(전체 15kg 기준)",
            "20과 이내 비중(전체 15kg 기준)",
        )
        if hasattr(self, "lbl_chart_value_rep"):
            self.lbl_chart_value_rep.setText(
                self._fmt_analysis_chart_header_rep_price(rep_points, base_idx)
            )
        if hasattr(self, "lbl_chart_value_volume"):
            self.lbl_chart_value_volume.setText("")
        if hasattr(self, "lbl_chart_value_quality"):
            self.lbl_chart_value_quality.setText(
                self._fmt_analysis_chart_header_quality(qual_points, base_idx)
            )

        ds = self._trade_date_to_mmdd(series_rows[0].get("trade_date"))
        if base_idx >= 0:
            de = self._trade_date_to_mmdd(series_rows[base_idx].get("trade_date"))
        else:
            de = self._trade_date_to_mmdd(series_rows[-1].get("trade_date"))
        self.chart_rep_price.set_date_range_caption(ds, de)
        self.chart_volume.set_date_range_caption(ds, de)
        self.chart_quality.set_date_range_caption(ds, de)

        ps_pack = price_structure_payload if price_structure_payload is not None else {}
        self._apply_price_structure_ui(ps_pack)

        if hasattr(self, "lbl_chart_footer_price"):
            self.lbl_chart_footer_price.setText(self._build_chart_footer_price(m))
        if hasattr(self, "lbl_chart_footer_volume"):
            self.lbl_chart_footer_volume.setText(self._build_chart_footer_volume(m))
        if hasattr(self, "lbl_chart_footer_quality"):
            self.lbl_chart_footer_quality.setText(self._build_chart_footer_quality(m))

    def _set_analysis_judgment_label(self, text: str):
        """시장분석 탭 카드 왼쪽 도넛(판단 신호) 갱신."""
        if not hasattr(self, "analysis_signal_donut") or self.analysis_signal_donut is None:
            return
        decision = str(text or "관망").strip()
        d_color, d_progress = self._analysis_signal_donut_style(decision)
        self.analysis_signal_donut.set_decision(decision, d_color, d_progress)

    def _sync_analysis_judgment_with_canonical_base(self):
        """상단 요약 기준일과 동일한 신호로 「판단」을 맞춤(요약 갱신 후 재동기화)."""
        bd = self._canonical_market_base_date()
        if not bd:
            return
        self._set_analysis_judgment_label(
            self._resolve_unified_signal_text(bd, None, metrics=None)
        )

    def _render_analysis_metrics(self, metrics: dict):
        if not hasattr(self, "analysis_signal_labels") or not self.analysis_signal_labels:
            return
        data = metrics or {}
        bd = self._canonical_market_base_date() or str(data.get("base_date") or "").strip()
        decision = self._resolve_unified_signal_text(
            bd,
            data.get("signal"),
            metrics=data,
        )
        self._set_analysis_judgment_label(decision)
        kpi_price = data.get("representative_avg_price")
        if kpi_price in (None, "", 0):
            kpi_price = data.get("base_avg_price")
        self.analysis_signal_labels["대표 가격"].setText(self._fmt_analysis_price(kpi_price))
        self.analysis_signal_labels["전일 대비"].setText(
            self._fmt_analysis_pct(data.get("d1"))
        )
        self.analysis_signal_labels["7일 대비"].setText(
            self._fmt_analysis_pct(data.get("d7"))
        )
        self.analysis_signal_labels["30일 대비"].setText(
            self._fmt_analysis_pct(data.get("d30"))
        )
    def _fmt_analysis_pct(self, value):
        if value in ("", None):
            return "-"
        try:
            v = float(value)
        except Exception:
            return "-"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f}%"

    def _fmt_analysis_price(self, value):
        if value in ("", None):
            return "-"
        return f"{self._to_int(value):,}원"

    def _create_progress_bar(self):
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setStyleSheet(
            "QProgressBar{border:1px solid #E2E8F0;border-radius:3px;background:#F7FAFC;}"
            "QProgressBar::chunk{background:#38A169;border-radius:3px;}"
        )
        bar.hide()
        return bar

    def _simplify_decision_text(self, decision: str) -> str:
        text = str(decision or "").strip()
        if text in ("출하 권장", "강한 출하 권장", "적극 출하", "강세"):
            return "강세"
        if text in ("출하 유보", "강한 유보", "약세"):
            return "약세"
        return "관망"

    def _analysis_signal_donut_style(self, signal: str) -> tuple[str, float]:
        """시장분석 metrics.signal(강세/약세/관망)용 도넛 색·진행률. _render_analysis_metrics 판단 라벨과 동일 체계."""
        s = str(signal or "").strip()
        if s == "강세":
            return "#2F855A", 75.0
        if s == "약세":
            return "#C53030", 30.0
        return "#B7791F", 55.0

    def _canonical_market_base_date(self) -> str:
        """상단 요약·도넛과 맞출 기준 거래일(실제 거래일 우선)."""
        h = self._header_data or {}
        d = str(h.get("base_date") or h.get("trade_date") or "").strip()
        if d:
            return d
        dc = self._detail_cache or {}
        d = str(dc.get("base_date") or "").strip()
        if d:
            return d
        pack = getattr(self, "_market_analysis_detail_pack", None) or {}
        m = pack.get("metrics") or {}
        return str(m.get("base_date") or "").strip()

    def _resolve_unified_signal_text(self, base_date, fallback_decision=None, metrics=None) -> str:
        """
        화면 전역 단일 신호(강세/약세/관망).
        - market_price_summary가 있으면 get_analysis_metrics.signal
        - 없으면 MarketPriceService 쪽 문구를 _simplify_decision_text로 3단계화
        metrics: 이미 조회한 get_analysis_metrics 결과가 있으면 전달(중복 조회 생략).
                 단, metrics.base_date가 요청 base_date와 같을 때만 사용(다르면 도넛과 판단 불일치).
        """
        req_bd = str(base_date or "").strip()
        if metrics is not None and (metrics or {}).get("status") == "ok":
            mb = str((metrics or {}).get("base_date") or "").strip()
            if req_bd and mb and mb == req_bd:
                return str(metrics.get("signal") or "관망").strip()
        if self.market_analysis_service is None:
            return self._simplify_decision_text(str(fallback_decision or "관망"))
        if not req_bd:
            return self._simplify_decision_text(str(fallback_decision or "관망"))
        filters = self._current_filter_values()
        try:
            m = self.market_analysis_service.get_analysis_metrics(
                base_date=req_bd,
                variety=filters.get("variety"),
                market=filters.get("market"),
            )
            if (m or {}).get("status") == "ok":
                return str(m.get("signal") or "관망").strip()
        except Exception as e:
            print(f"[MarketPricePage] unified signal resolve failed: {e}")
        return self._simplify_decision_text(str(fallback_decision or "관망"))

    def _apply_unified_market_signal_to_payload(self, payload: dict) -> dict:
        """요약 payload의 decision을 항상 강세/약세/관망 중 하나로 맞춘다."""
        out = dict(payload or {})
        bd = str(out.get("base_date") or out.get("trade_date") or "").strip()
        if not bd:
            out["decision"] = self._simplify_decision_text(str(out.get("decision") or "관망"))
            return out
        out["decision"] = self._resolve_unified_signal_text(bd, out.get("decision"))
        return out

    def _init_services(self):
        try:
            self.market_manager = MarketPriceManager()
            self.settlement_manager = MarketSettlementManager(
                service_key=getattr(self.market_manager, "service_key", None)
            )
            self.market_service = MarketPriceService(self.market_manager)
            self.market_analysis_service = MarketAnalysisService(self.db)
        except Exception as e:
            print(f"[MarketPricePage] service init failed: {e}")
            self.market_manager = None
            self.settlement_manager = None
            self.market_service = None
            self.market_analysis_service = None

    def _connect_signals(self):
        if hasattr(self, "tabs") and self.tabs is not None:
            self.tabs.currentChanged.connect(self._on_tab_changed)

    def _resolve_analysis_base_date(self, prompt_if_missing=False, prefer_latest=False, update_date_picker=False):
        requested_date = self._get_analysis_base_date()
        filters = self._current_filter_values()
        if self.market_analysis_service is None:
            return requested_date, requested_date

        latest_date = self.market_analysis_service.get_latest_summary_date(
            variety=filters.get("variety"),
            market=filters.get("market"),
            on_or_before=requested_date,
        )
        if not latest_date:
            return requested_date, requested_date

        target_date = requested_date
        if prefer_latest:
            target_date = latest_date
        elif latest_date != requested_date and prompt_if_missing:
            answer = QMessageBox.question(
                self,
                "시장분석 기준일 확인",
                (
                    f"{requested_date} 기준 summary 데이터가 없습니다.\n"
                    f"최신 거래일({latest_date})로 로딩할까요?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                target_date = latest_date

        return target_date, requested_date

    def _update_market_analysis_latest_label(self, latest_date: str):
        if hasattr(self, "lbl_market_analysis_latest") and self.lbl_market_analysis_latest is not None:
            text = str(latest_date or "").strip()
            self.lbl_market_analysis_latest.setText(
                f"최신 업데이트: {text}" if text else "최신 업데이트: -"
            )

    def _load_market_analysis_from_db(self, prompt_if_missing=False, prefer_latest=False, update_date_picker=False):
        if self._analysis_loading:
            return
        if self.market_analysis_service is None:
            self._set_market_analysis_status("시장분석 서비스 초기화 실패")
            return
        self._analysis_loading = True
        filters = self._current_filter_values()
        base_date, requested_date = self._resolve_analysis_base_date(
            prompt_if_missing=prompt_if_missing,
            prefer_latest=prefer_latest,
            update_date_picker=update_date_picker,
        )
        try:
            range_pack = self._collect_missing_dates(base_date, ANALYSIS_LOOKBACK_DAYS)
            start_date = range_pack.get("start_date") or base_date
            end_date = range_pack.get("end_date") or base_date
            summary_rows = self.market_analysis_service.get_summary(
                start_date,
                end_date,
                filters.get("variety"),
                filters.get("market"),
            ) or []
            metrics = self.market_analysis_service.get_analysis_metrics(
                base_date=base_date,
                variety=filters.get("variety"),
                market=filters.get("market"),
            )
            chart_series = self.market_analysis_service.get_chart_series(
                base_date=base_date,
                variety=filters.get("variety"),
                market=filters.get("market"),
                window=30,
            )
            # 예외 허용: 가격구조 차트는 summary 외 settlement 기반 직접 계산.
            price_structure_series = self.market_analysis_service.get_price_structure_series(
                base_date=base_date,
                variety=filters.get("variety"),
                market=filters.get("market"),
                window=30,
                price_type=self.current_price_type,
            )
            payload = {
                "base_date": base_date,
                "requested_date": requested_date,
                "start_date": start_date,
                "end_date": end_date,
                "existing_before_count": len(summary_rows),
                "missing_count": 0,
                "reconcile_count": 0,
                "fetch_dates_count": 0,
                "imported_count": 0,
                "imported_dates": [],
                "failed_dates": [],
                "summary_new_dates_count": 0,
                "summary_fill_dates_count": 0,
                "summary_target_dates_count": 0,
                "summary_created_count": 0,
                "summary_rows": summary_rows,
                "summary_row_count": len(summary_rows),
                "merge_collision_count": 0,
                "merge_selected_sale_count": 0,
                "metrics": metrics,
                "chart_series": chart_series,
                "price_structure_series": price_structure_series,
            }
            self._render_analysis_result(payload)
            latest_date = ""
            if summary_rows:
                latest_date = str(summary_rows[-1].get("trade_date") or "")
            self._update_market_analysis_latest_label(latest_date)
            if summary_rows:
                self._set_market_analysis_status(
                    (
                        f"DB summary 표시 완료 ({len(summary_rows)}건)"
                        f" | 요청일 {requested_date}"
                        f" | 기준일 {base_date}"
                    )
                )
            else:
                self._set_market_analysis_status("DB summary 데이터가 없습니다.")
                self._update_market_analysis_latest_label("")
        except Exception as e:
            self._set_market_analysis_status(f"DB summary 조회 실패: {e}")
        finally:
            self._analysis_loading = False

    def _init_loading_state(self):
        self._header_data = None
        self._detail_cache = None
        self._analysis_cache = None
        self._analysis_cache_key = None
        self._analysis_loading = False
        self._set_market_analysis_status("요약 데이터 확인중...")
        self._render_analysis_metrics({})
        self._render_analysis_charts({}, {}, {})
        if hasattr(self, "settlement_tab") and self.settlement_tab is not None:
            self.settlement_tab.lbl_status.setText("정산 데이터 대기중 · 조회 버튼을 눌러 주세요")
            self.settlement_tab.lbl_notice.hide()
            self.settlement_tab._fill_table([])
        if hasattr(self, "realtime_tab") and self.realtime_tab is not None:
            self.realtime_tab.lbl_status.setText("실시간 데이터 대기중")
            self.realtime_tab._fill_table([])
        self._update_base_date_label({})
        self._update_debug_info_label()

    # NOTE:
    # 과거 MarketPriceService 기반 요약/추이 로더(_load_header_summary/_load_analysis_data 등)는 제거.
    # 시장분석 탭은 _load_market_analysis_from_db/_run_analysis_import를 통한
    # MarketAnalysisService(summary/metrics/chart_series) 중심으로만 동작한다.

    def _collect_filtered_rows_from_cache(self):
        raw = list((self._detail_cache or {}).get("rows") or [])
        if not raw:
            return []
        st = getattr(self, "settlement_tab", None)
        if st is None:
            return raw
        if hasattr(st, "get_filters"):
            return st._filter_rows(raw, st.get_filters())
        return st._filter_rows(raw, st.filter_bar.get_filters())

    def _build_analysis_verify_data(self):
        rows = self._collect_filtered_rows_from_cache()
        prices = [self._to_int(r.get("unit_price") or r.get("avg_price")) for r in rows if self._to_int(r.get("unit_price") or r.get("avg_price")) > 0]
        qtys = [self._to_int(r.get("qty") or r.get("total_qty")) for r in rows if self._to_int(r.get("qty") or r.get("total_qty")) > 0]
        ratio_pack = self.market_service._calculate_special_large_ratios(rows) if self.market_service else {
            "total_qty": 0, "special_qty": 0, "large_qty": 0, "special_ratio": 0.0, "large_ratio": 0.0
        }
        trend = (self._analysis_cache or {}).get("trend") or {}
        prev_price = trend.get("prev_price")
        return {
            "total_qty": sum(qtys) if qtys else ratio_pack.get("total_qty", 0),
            "filtered_row_count": len(rows),
            "avg_price": int(round(sum(prices) / len(prices))) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "min_price": min(prices) if prices else 0,
            "special_qty": ratio_pack.get("special_qty", 0),
            "special_ratio": ratio_pack.get("special_ratio", 0.0),
            "large_qty": ratio_pack.get("large_qty", 0),
            "large_ratio": ratio_pack.get("large_ratio", 0.0),
            "prev_price": prev_price,
            "avg_7d": trend.get("avg_7d"),
            "avg_30d": trend.get("avg_30d"),
            "d1": trend.get("d1"),
            "d7": trend.get("d7"),
            "d30": trend.get("d30"),
            "trend": trend.get("trend", "-"),
            "decision": self._resolve_unified_signal_text(
                trend.get("base_date"),
                trend.get("decision"),
            ),
            "reason": trend.get("reason", "-"),
            "prev_trading_date": trend.get("prev_trading_date") or "-",
            "compare_7d_date": trend.get("compare_7d_date") or "-",
            "compare_30d_date": trend.get("compare_30d_date") or "-",
        }

    def _debug_market_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "debug" / "market_api"

    def _debug_target_dates(self):
        dates = []
        for value in [
            (self._header_data or {}).get("requested_date"),
            (self._header_data or {}).get("base_date"),
            (self._detail_cache or {}).get("requested_date"),
            (self._detail_cache or {}).get("base_date"),
        ]:
            date_text = str(value or "").strip()
            if date_text and date_text not in dates:
                dates.append(date_text)
        if not dates:
            dates.append(self._get_analysis_base_date())
        return dates

    def _extract_raw_row_count(self, payload):
        if payload is None:
            return 0
        if isinstance(payload, list):
            if payload and all(isinstance(x, dict) for x in payload):
                return len(payload)
            return 0
        if isinstance(payload, dict):
            if "response" in payload:
                return self._extract_raw_row_count(payload.get("response"))
            body = payload.get("body")
            if isinstance(body, dict):
                items = body.get("items")
                if isinstance(items, dict):
                    item = items.get("item")
                    if isinstance(item, list):
                        return len(item)
                    if isinstance(item, dict):
                        return 1
        return 0

    def _load_debug_raw_index_rows(self):
        debug_dir = self._debug_market_dir()
        if not debug_dir.exists():
            return []
        out = []
        for base_date in self._debug_target_dates():
            for source in ("realtime", "origin", "sale"):
                file_name = f"{base_date}_{source}_raw.json"
                target = debug_dir / file_name
                if not target.exists():
                    continue
                try:
                    payload = json.loads(target.read_text(encoding="utf-8"))
                except Exception:
                    payload = {}
                status = str((payload or {}).get("status") or "-")
                row_count = self._extract_raw_row_count((payload or {}).get("response"))
                out.append(
                    {
                        "date": base_date,
                        "source": source,
                        "status": status,
                        "row_count": row_count,
                        "file_name": file_name,
                    }
                )
        return out

    def _verify_download_dir(self, selected_date: str) -> Path:
        return Path(__file__).resolve().parents[2] / "debug" / "market_verify" / selected_date

    def _save_verify_json(self, target: Path, payload):
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _mark_download_status(self, message: str, progress: int):
        self._set_market_analysis_status(f"{message} ({int(progress)}%)")
        QApplication.processEvents()

    def _fetch_verify_source_rows(
        self,
        source: str,
        requested_date: str,
        market_code: str,
        item_code: str,
        max_lookback: int = 10,
    ):
        fetcher_map = {
            "realtime": (
                self.market_manager.fetch_real_time_data
                if self.market_manager is not None
                else None
            ),
            "origin": (
                self.settlement_manager.fetch_origin_data
                if self.settlement_manager is not None
                else None
            ),
            "sale": (
                self.settlement_manager.fetch_sale_data
                if self.settlement_manager is not None
                else None
            ),
        }
        fetcher = fetcher_map.get(source)
        if fetcher is None:
            return {
                "requested_date": requested_date,
                "base_date": requested_date,
                "row_count": 0,
                "data": [],
                "status": "error",
                "error": "fetcher_not_ready",
            }
        start_dt = self.market_service._parse_date(requested_date) if self.market_service else None
        if start_dt is None:
            start_dt = datetime.now()
        first_error = ""
        for idx in range(max(1, int(max_lookback))):
            target_date = (start_dt - timedelta(days=idx)).strftime("%Y-%m-%d")
            try:
                rows = list(fetcher(target_date, market_code, item_code) or [])
            except Exception as e:
                if not first_error:
                    first_error = str(e)
                continue
            if rows:
                return {
                    "requested_date": requested_date,
                    "base_date": target_date,
                    "row_count": len(rows),
                    "data": rows,
                    "status": "ok",
                    "error": "",
                }
        return {
            "requested_date": requested_date,
            "base_date": requested_date,
            "row_count": 0,
            "data": [],
            "status": "empty" if not first_error else "error",
            "error": first_error,
        }

    def _download_verify_data(self):
        if not DEBUG_MARKET_VERIFY:
            return
        if self.market_service is None:
            self._set_market_analysis_status("데이터 검증 다운로드 실패 (서비스 미초기화)")
            return
        selected_date = self._get_analysis_base_date()
        filters = self._current_filter_values()
        query = self.market_service._build_query_params(
            date=selected_date,
            variety=filters["variety"],
            market=filters["market"],
            corp=filters["corp"],
            item_code=None,
        )
        target_dir = self._verify_download_dir(selected_date)
        target_dir.mkdir(parents=True, exist_ok=True)
        self._mark_download_status("데이터 검증 수집 중...", 5)
        self._mark_download_status("실시간 데이터 수집 중...", 15)
        realtime_payload = self._fetch_verify_source_rows(
            "realtime",
            selected_date,
            query["market_code"],
            query["item_code"],
            max_lookback=10,
        )
        self._mark_download_status("정산 데이터 수집 중...", 40)
        origin_payload = self._fetch_verify_source_rows(
            "origin",
            selected_date,
            query["market_code"],
            query["item_code"],
            max_lookback=10,
        )
        self._mark_download_status("거래 데이터 수집 중...", 65)
        sale_payload = self._fetch_verify_source_rows(
            "sale",
            selected_date,
            query["market_code"],
            query["item_code"],
            max_lookback=10,
        )
        self._mark_download_status("파일 저장 중...", 85)
        self._save_verify_json(target_dir / "realtime.json", realtime_payload)
        self._save_verify_json(target_dir / "origin.json", origin_payload)
        self._save_verify_json(target_dir / "sale.json", sale_payload)
        meta_payload = {
            "requested_date": selected_date,
            "base_date": {
                "realtime": realtime_payload.get("base_date"),
                "origin": origin_payload.get("base_date"),
                "sale": sale_payload.get("base_date"),
            },
            "download_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "realtime_count": int(realtime_payload.get("row_count") or 0),
            "origin_count": int(origin_payload.get("row_count") or 0),
            "sale_count": int(sale_payload.get("row_count") or 0),
            "realtime_status": realtime_payload.get("status"),
            "origin_status": origin_payload.get("status"),
            "sale_status": sale_payload.get("status"),
            "realtime_error": realtime_payload.get("error"),
            "origin_error": origin_payload.get("error"),
            "sale_error": sale_payload.get("error"),
            "saved_path": str(target_dir),
        }
        self._save_verify_json(target_dir / "meta.json", meta_payload)
        self._mark_download_status("완료", 100)
        print(f"[VERIFY-DOWNLOAD] saved_path={target_dir}")
        self._set_market_analysis_status(f"데이터 검증 다운로드 완료: debug/market_verify/{selected_date}")

    def _populate_verify_raw_table(self, table: QTableWidget):
        rows = self._load_debug_raw_index_rows()
        table.clearSpans()
        table.clearContents()
        if not rows:
            table.setRowCount(1)
            item = QTableWidgetItem("raw 파일이 없습니다.")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            table.setSpan(0, 0, 1, table.columnCount())
            table.setItem(0, 0, item)
            return
        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            values = [
                row.get("date") or "-",
                row.get("source") or "-",
                row.get("status") or "-",
                str(row.get("row_count", "-")),
                row.get("file_name") or "-",
            ]
            for c_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r_idx, c_idx, item)

    def _populate_verify_analysis_table(self, table: QTableWidget):
        verify = self._build_analysis_verify_data()
        service_verify = self.market_service.get_last_verify_snapshot() if self.market_service else {}
        merged = dict(service_verify)
        merged.update(verify)
        rows = [
            "stage", "source", "requested_date", "base_date", "fallback_used",
            "prev_trading_date", "compare_7d_date", "compare_30d_date",
            "api_call_count", "cache_hit", "elapsed_ms", "row_count",
            "total_qty", "filtered_row_count", "avg_price", "max_price", "min_price",
            "special_qty", "special_ratio", "large_qty", "large_ratio",
            "prev_price", "avg_7d", "avg_30d", "d1", "d7", "d30",
            "trend", "decision", "reason",
        ]
        table.clearSpans()
        table.clearContents()
        table.setRowCount(len(rows))
        for r_idx, key in enumerate(rows):
            key_item = QTableWidgetItem(key)
            value = merged.get(key, "-")
            if value in (None, ""):
                value = "-"
            val_item = QTableWidgetItem(str(value))
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(r_idx, 0, key_item)
            table.setItem(r_idx, 1, val_item)

    def _parse_price_text(self, text):
        s = str(text or "").strip().replace(",", "").replace("원", "")
        try:
            return int(float(s)) if s else 0
        except Exception:
            return 0

    def _run_ui_verify_checks(self):
        if not DEBUG_MARKET_VERIFY:
            return
        rows = self._collect_filtered_rows_from_cache()
        if not rows:
            return
        recalc = self._build_analysis_verify_data()
        displayed_avg = self._parse_price_text(
            (self.analysis_signal_labels.get("대표 가격").text() if hasattr(self, "analysis_signal_labels") else "")
        )
        displayed_row_count = self._to_int((self._header_data or {}).get("row_count"))
        displayed_special = float((self._header_data or {}).get("special_ratio") or 0.0)
        displayed_large = float((self._header_data or {}).get("large_ratio") or 0.0)
        if displayed_row_count > 0 and displayed_row_count != recalc["filtered_row_count"]:
            print(
                "[VERIFY ERROR] row_count mismatch "
                f"recalc={recalc['filtered_row_count']} displayed={displayed_row_count}"
            )
        if abs(recalc["avg_price"] - displayed_avg) > 1:
            print(f"[VERIFY ERROR] avg_price mismatch recalc={recalc['avg_price']} displayed={displayed_avg}")
        if abs(float(recalc["special_ratio"]) - displayed_special) > 0.2 and displayed_special > 0:
            print(f"[VERIFY ERROR] special_ratio mismatch recalc={recalc['special_ratio']} displayed={displayed_special}")
        if abs(float(recalc["large_ratio"]) - displayed_large) > 0.2 and displayed_large > 0:
            print(f"[VERIFY ERROR] large_ratio mismatch recalc={recalc['large_ratio']} displayed={displayed_large}")

    def _update_debug_info_label(self):
        if not DEBUG_MARKET_VERIFY:
            return
        st = getattr(self, "settlement_tab", None)
        lbl = getattr(st, "lbl_debug_info", None) if st is not None else None
        if lbl is None:
            return
        total_rows = len((self._detail_cache or {}).get("rows") or [])
        filtered_rows = len(self._collect_filtered_rows_from_cache()) if self._detail_cache else 0
        source = (
            (self._detail_cache or {}).get("source")
            or (self._header_data or {}).get("source")
            or "-"
        )
        cache_hit = (self._detail_cache or {}).get("cache_hit")
        elapsed_ms = (
            (self._analysis_cache or {}).get("elapsed_ms")
            or (self._detail_cache or {}).get("elapsed_ms")
            or (self._header_data or {}).get("elapsed_ms")
            or 0
        )
        lbl.setText(
            f"DEBUG | rows={total_rows} | filtered={filtered_rows} | source={source} | cache_hit={cache_hit} | elapsed_ms={elapsed_ms}"
        )

    def _current_filter_values(self):
        """시장분석 고정 필터 키(시장분석 탭은 MarketAnalysisService 중심)."""
        g = _market_analysis_filters_snapshot()
        return {
            "date": g.get("target_date") or "",
            "variety": (g.get("variety_name") or MARKET_ANALYSIS_FIXED_VARIETY_NAME).strip()
            or MARKET_ANALYSIS_FIXED_VARIETY_NAME,
            "market": (g.get("market_name") or MARKET_ANALYSIS_FIXED_MARKET_NAME).strip()
            or MARKET_ANALYSIS_FIXED_MARKET_NAME,
            "corp": (g.get("corp_name") or MARKET_ANALYSIS_FIXED_CORP_NAME).strip()
            or MARKET_ANALYSIS_FIXED_CORP_NAME,
        }

    def _update_base_date_label(self, payload: dict):
        st = getattr(self, "settlement_tab", None)
        if st is None or not hasattr(st, "lbl_base_date"):
            return
        st.lbl_base_date.setText(self._format_base_date_text(payload))

    def _format_base_date_text(self, payload: dict):
        data = payload or {}
        requested = str(data.get("requested_date") or "").strip()
        base = str(data.get("base_date") or "").strip()
        status = str(data.get("status") or "").strip()
        if status in ("error", "empty"):
            return "기준일자: 없음"
        if not base:
            return "기준일자: 확인중..."
        if requested and requested != base:
            return f"기준일자: {base} (최근 거래일)"
        return f"기준일자: {base}"

    def _update_table_section(self, detail_rows):
        st = getattr(self, "settlement_tab", None)
        if st is not None:
            st._fill_table(detail_rows or [])
            return
        rows = detail_rows or []
        if not rows:
            return

    def _to_int(self, value, default=0):
        if value in ("", None):
            return default
        try:
            return int(float(str(value).replace(",", "")))
        except Exception:
            return default

    def closeEvent(self, event):
        try:
            self._trend_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        super().closeEvent(event)
