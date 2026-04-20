import re
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ---------------------------------------------------------------------------
# 폰트: QFont::setPointSize <= 0 / -1 경고 방지 및 레이아웃 안정화
# - QFont(family) 단일 인자만 쓰면 pointSize=-1 이 될 수 있음 → make_app_font 사용 권장.
# ---------------------------------------------------------------------------
DEFAULT_FONT_FAMILY = "Malgun Gothic"
DEFAULT_FONT_PT = 10


def safe_font(size):
    """
    QFont용 point size (정수). None/비정수/0 이하 → DEFAULT_FONT_PT.
    양수는 입력값 그대로 사용.
    """
    try:
        s = int(size) if size is not None else 0
    except (TypeError, ValueError):
        s = 0
    if s <= 0:
        return DEFAULT_FONT_PT
    return int(s)


def ensure_qfont_point_size(font: QFont, fallback: Optional[int] = None) -> None:
    """
    QFont::setPointSize 경고 방지: pointSize()가 -1/0 이하일 때만 유효 크기로 보정.
    위젯에서 font()를 복사한 뒤 조정할 때 등에 사용.
    """
    if font is None:
        return
    fb = fallback if (fallback is not None and fallback > 0) else DEFAULT_FONT_PT
    try:
        ps = font.pointSize()
    except Exception:
        ps = -1
    if ps <= 0:
        font.setPointSize(fb)


def make_app_font(point_size=DEFAULT_FONT_PT, family=DEFAULT_FONT_FAMILY, weight=None, bold=False):
    """애플리케이션/위젯 공통 QFont (유효한 point size만 사용)."""
    sz = safe_font(point_size)
    f = QFont()
    f.setFamily(family or DEFAULT_FONT_FAMILY)
    f.setPointSize(sz)
    if bold:
        f.setBold(True)
    elif weight is not None:
        f.setWeight(weight)
    # setWeight 등 이후에도 pointSize가 비정상인 경우 대비(플랫폼/스타일 조합)
    ensure_qfont_point_size(f, sz)
    return f


class MainStyles:
    """
    과수원 관리 시스템 통합 디자인 가이드
    작성자: 지니 & 지기님
    최종수정: 테이블 중앙정렬 및 입력창 단위/형식 최적화
    """

    # 1. 전체 배경 및 공통 폰트 (명시적 기본 글자 크기)
    MAIN_BG = (
        "background-color: #FDFBF7; font-family: 'Malgun Gothic'; font-size: 10px;"
    )

    # 2. 카드/프레임 디자인 (섹션 구분용)
    CARD = """
        QFrame {
            background-color: white; 
            border: 1px solid #EAE7E2; 
            border-radius: 12px;
        }
    """
    CARD_LBL_STYLE = "font-size: 12px; background: transparent; color: #4A5568; font-weight: bold; padding: 4px; border: none;"
    # 시장/경매 상세 UI 컴팩트 레이아웃 상수
    MARKET_SECTION_CONTENT_MARGINS = (8, 6, 8, 6)
    MARKET_SECTION_SPACING = 4
    MARKET_ROW_SPACING = 5
    MARKET_KPI_TILE_MIN_HEIGHT = 42

    # 3. 테이블 스타일 (작업상세/인력투입 공용)
    # 헤더와 셀의 중앙 정렬 및 딥그린 선택 강조가 핵심입니다.
    TABLE = """
        QTableWidget {
            background-color: white;
            gridline-color: #F2F2F2;
            border: none;
            font-size: 10px;
            selection-background-color: #E8F0E7;
            selection-color: #2D5A27;
            outline: none;
        }
        QHeaderView::section {
            background-color: #F8F9FA;
            padding: 1px;
            min-height:25px;
            border: none;
            border-bottom: 1px solid #EAE7E2;
            font-weight: bold;
            font-size: 10px;
            color: #444;
            qproperty-alignment: 'AlignCenter'; /* 헤더 중앙 정렬 */
        }
        QTableWidget::item {
            padding: 5px;
            font-size: 10px;
        }
        QTableWidget::item:hover {
            background-color: #E3F2FD; /* 연한 하늘색 */
            color: black;
        }
    """
    # TABLE 위에 덧씌워 10px 본문·헤더(비용 상세 등)
    TABLE_CONTENT_10 = """
        QTableWidget { font-size: 10pt; }
        QTableWidget::item { font-size: 10pt; padding: 4px; }
        QHeaderView::section {
            font-size: 10pt;
            min-height: 22px;
            padding: 2px 4px;
        }
    """
    # 인력관리·인력 목록: 헤더 10pt bold, 행·셀 10pt normal (TABLE과 함께 사용)
    TABLE_WORKFORCE_LIST = """
        QTableWidget { font-size: 10pt; font-weight: normal; }
        QTableWidget::item { font-size: 10pt; font-weight: normal; padding: 4px; }
        QHeaderView::section {
            font-size: 10pt;
            font-weight: bold;
            min-height: 22px;
            padding: 2px 4px;
        }
    """
    # 인력 목록 인라인 입력(이름·연락처·은행·계좌)
    INPUT_WORKFORCE_LIST_CELL = """
        QLineEdit {
            font-size: 10pt;
            font-weight: normal;
            border: 1px solid #F0F0F0;
            padding: 5px;
            border-radius: 4px;
            qproperty-alignment: 'AlignCenter';
            background-color: #FAFAFA;
        }
        QLineEdit:focus {
            border: 1px solid #2D5A27;
            background-color: white;
        }
    """
    # 인력 목록 기본단가(우측·천단위 텍스트)
    INPUT_WORKFORCE_LIST_PRICE = """
        QLineEdit {
            font-size: 10pt;
            font-weight: normal;
            padding: 5px 6px;
            border: 1px solid #F0F0F0;
            border-radius: 4px;
            background-color: #FAFAFA;
            qproperty-alignment: 'AlignRight';
        }
        QLineEdit:focus {
            border: 1px solid #2D5A27;
            background-color: white;
        }
    """
    # 인력 목록 테이블 셀 콤보: 인라인 QLineEdit(10pt)과 동일 단위·굵기 (상위 테이블 폰트 전파와 충돌 방지)
    COMBO_WORKFORCE_LIST_CELL = """
        QComboBox {
            font-size: 10pt;
            font-weight: normal;
            border: 1px solid #F0F0F0;
            padding: 4px 24px 4px 6px;
            border-radius: 4px;
            background-color: #FAFAFA;
            min-height: 22px;
        }
        QComboBox:focus {
            border: 1px solid #2D5A27;
            background-color: white;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border: none;
            border-left: 1px solid #EEE;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: #FAFAFA;
        }
        QComboBox::down-arrow {
            image: none;
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666;
        }
        QComboBox::down-arrow:on {
            border-top: none;
            border-bottom: 5px solid #2D5A27;
        }
        QComboBox QAbstractItemView {
            font-size: 10pt;
            font-weight: normal;
            background-color: #FFFFFF;
            color: #2D3748;
            border: 1px solid #E2E8F0;
            border-radius: 4px;
            outline: none;
            padding: 2px;
            selection-background-color: #E6F4EA;
            selection-color: #1A202C;
        }
        QComboBox QAbstractItemView::item {
            font-size: 10pt;
            font-weight: normal;
            min-height: 22px;
            padding: 4px 8px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #F7FAFC;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #E6F4EA;
            color: #1A202C;
        }
    """
    # 영농일지(작업목록·인력·경비·사용농약): 그리드 최소화·행·헤더 여유 (가독성)
    TABLE_WORK_LOG = """
        QTableWidget {
            background-color: white;
            gridline-color: transparent;
            border: none;
            font-size: 10px;
            selection-background-color: #E8F0E7;
            selection-color: #2D5A27;
            outline: none;
        }
        QHeaderView::section {
            background-color: #F8F9FA;
            padding: 4px 6px;
            min-height: 28px;
            border: none;
            border-bottom: 1px solid #EAE7E2;
            font-weight: bold;
            font-size: 10px;
            color: #444;
            qproperty-alignment: 'AlignCenter';
        }
        QTableWidget::item {
            padding: 4px 6px;
            font-size: 10px;
        }
        QTableWidget::item:hover {
            background-color: #E3F2FD;
            color: black;
        }
    """
    # 용도 등록 팝업 테이블: 행·헤더 폰트 10px (좁은 열·콤보와 균형)
    TABLE_PURPOSE_DLG = """
        QTableWidget {
            background-color: white;
            gridline-color: #F2F2F2;
            border: none;
            font-size: 10px;
            selection-background-color: #E8F0E7;
            selection-color: #2D5A27;
            outline: none;
        }
        QHeaderView::section {
            background-color: #F8F9FA;
            padding: 2px 4px;
            min-height: 22px;
            border: none;
            border-bottom: 1px solid #EAE7E2;
            font-weight: bold;
            font-size: 10px;
            color: #444;
            qproperty-alignment: 'AlignCenter';
        }
        QTableWidget::item {
            padding: 3px 6px;
            font-size: 10px;
        }
        QTableWidget::item:hover {
            background-color: #E3F2FD;
            color: black;
        }
    """
    # 용도 등록 팝업 셀 콤보: 10px + 좌우 여백으로 글자 잘림 완화
    COMBO_PURPOSE_DLG = """
        QComboBox {
            border: 1px solid #DDD;
            padding: 2px 6px 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            background-color: white;
            min-height: 22px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border: none;
            border-left: 1px solid #EEE;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: #FAFAFA;
        }
        /* 스타일 시트만 쓰면 기본 화살표가 숨겨질 수 있어 삼각형으로 명시 */
        QComboBox::down-arrow {
            image: none;
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666;
            position: relative;
            top: 1px;
        }
        QComboBox::down-arrow:on {
            border-top: none;
            border-bottom: 5px solid #2D5A27;
        }
        QComboBox QAbstractItemView {
            font-size: 10px;
        }
        QComboBox QLineEdit {
            font-size: 10px;
            padding: 0px 2px;
        }
    """
    # 테이블 셀 내 숫자 입력: 테두리 제거·배경 투명에 가깝게 해 행과 한 덩어리로 보이게 함
    SPINBOX_TABLE_CELL = """
        QSpinBox {
            border: none;
            background-color: transparent;
            padding: 2px 4px;
            font-size: 10px;
            min-height: 22px;
        }
        QSpinBox:focus {
            border: none;
            background-color: #F7FAFC;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            width: 0px;
            height: 0px;
            border: none;
            margin: 0px;
            padding: 0px;
        }
    """
    # 테이블 셀 내 콤보(구분 등) — 동일하게 플랫
    COMBO_TABLE_CELL = """
        QComboBox {
            border: none;
            background-color: transparent;
            padding: 2px 4px;
            font-size: 10px;
            min-height: 22px;
        }
        QComboBox:focus {
            border: none;
            background-color: #F7FAFC;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 18px;
            border: none;
            background: transparent;
        }
        QComboBox::down-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666;
        }
    """
    # 영농일지 작업목록 등: 셀 콤보(테두리 없음·약간 큰 행)
    COMBO_TABLE_CELL_WORK_LOG = """
        QComboBox {
            border: none;
            background-color: transparent;
            padding: 3px 6px;
            font-size: 10px;
            min-height: 26px;
        }
        QComboBox:focus {
            border: none;
            background-color: #F7FAFC;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 18px;
            border: none;
            background: transparent;
        }
        QComboBox::down-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666;
        }
    """
    # 영농일지 작업목록: 시작/종료 QTimeEdit (화살표는 CSS 삼각형으로 명시 — Windows에서 기본 아이콘 누락 보완)
    TIME_EDIT_TABLE_CELL_WORK_LOG = """
        QTimeEdit {
            border: none;
            background-color: transparent;
            padding: 2px 2px 2px 6px;
            font-size: 10px;
            min-height: 26px;
        }
        QTimeEdit:focus {
            border: none;
            background-color: #F7FAFC;
        }
        QTimeEdit::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 18px;
            height: 12px;
            border: none;
            background: #E8EDE8;
            border-radius: 2px 2px 0 0;
            margin-right: 2px;
        }
        QTimeEdit::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 18px;
            height: 12px;
            border: none;
            background: #E8EDE8;
            border-radius: 0 0 2px 2px;
            margin-right: 2px;
        }
        QTimeEdit::up-button:hover, QTimeEdit::down-button:hover {
            background: #D8E0D8;
        }
        QTimeEdit::up-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid #3D4F3D;
            width: 0px;
            height: 0px;
        }
        QTimeEdit::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #3D4F3D;
            width: 0px;
            height: 0px;
        }
    """
    # 영농일지 사용 농약: 수량 스핀과 동일 계열
    SPINBOX_TABLE_CELL_WORK_LOG = """
        QSpinBox {
            border: none;
            background-color: transparent;
            padding: 3px 6px;
            font-size: 10px;
            min-height: 26px;
        }
        QSpinBox:focus {
            border: none;
            background-color: #F7FAFC;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            width: 0px;
            height: 0px;
            border: none;
            margin: 0px;
            padding: 0px;
        }
    """
    LINEEDIT_TABLE_CELL_WORK_LOG = """
        QLineEdit {
            border: none;
            background-color: transparent;
            padding: 3px 6px;
            font-size: 10px;
            min-height: 26px;
        }
        QLineEdit:focus {
            background-color: #F7FAFC;
        }
    """
    DATE_EDIT_TABLE_CELL_WORK_LOG = """
        QDateEdit {
            border: none;
            background-color: transparent;
            padding: 3px 4px;
            font-size: 10px;
            min-height: 26px;
            min-width: 102px;
        }
        QDateEdit:focus {
            background-color: #F7FAFC;
        }
        QDateEdit::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 18px;
            border: none;
            background: transparent;
        }
    """
    # 버튼스타일
    # 4. 메인 액션 버튼 (저장, 완료 등 중요 동작)
    BTN_PRIMARY = """
        QPushButton {
            background-color: #2D5A27;
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-radius: 6px;
            padding: 8px 15px;
            border: none;
        }
        QPushButton:hover {
            background-color: #3D7A37;
        }
        QPushButton:pressed {
            background-color: #1E3D1A;
        }
    """
    # BTN_PRIMARY 대비 폰트·패딩·모서리 약 80% (소형 강조 버튼)
    BTN_PRIMARY_COMPACT = """
        QPushButton {
            background-color: #2D5A27;
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-radius: 5px;
            padding: 4px 10px;
            border: none;
        }
        QPushButton:hover {
            background-color: #3D7A37;
        }
        QPushButton:pressed {
            background-color: #1E3D1A;
        }
    """

    # 5. 서브 액션 버튼 (추가, 삭제, 조회 등 보조 동작)
    # padding·font·radius는 BTN_PRIMARY/BTN_DANGER와 동일하게 두어 툴바 나란히 높이가 맞도록 함
    BTN_SECONDARY = """
        QPushButton {
            background-color: #F1F4F1;
            color: #444;
            border: 1px solid #DDD;
            border-radius: 6px;
            padding: 8px 15px;
            font-size: 10px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #E2E8E2;
            border: 1px solid #CCC;
        }
    """
    # BTN_SECONDARY 대비 폰트·패딩·모서리 약 80% (소형 보조 버튼)
    BTN_SECONDARY_COMPACT = """
        QPushButton {
            background-color: #F1F4F1;
            color: #444;
            border: 1px solid #DDD;
            border-radius: 5px;
            padding: 4px 10px;
            font-size: 10px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #E2E8E2;
            border: 1px solid #CCC;
        }
    """
    # 날씨 가져오기 전용 버튼 (오렌지색 계열)
    BTN_FETCH = """
        QPushButton {
            background-color: #ED8936;
            color:  white;
            border: none; 
            font-size: 10px;
            font-weight: bold;
            border-radius: 6px;
            padding: 8px 15px;
        }
        QPushButton:hover {
            background-color: #F1A96E;
        }
        QPushButton:pressed {
            background-color: #DB6F14;
        }
    """ 
    BTN_SUCCESS = "background-color: #27AE60; color: white; font-size: 10px; font-weight: bold; border-radius: 6px; padding: 5px 12px;"

    # 삭제/취소 버튼 스타일 (BTN_SECONDARY와 padding/font 통일로 나란히 배치 시 정렬 일치)
    BTN_DANGER = """
        QPushButton {
            background-color: #F56565; 
            color: white; 
            font-weight: bold; 
            border-radius: 6px;
            font-size: 10px;
            padding: 8px 15px;
            border: none;
        }
        QPushButton:hover { background-color: #E53E3E; }
        QPushButton:pressed { background-color: #C53030; }
    """
    
    # 일반 액션 버튼 스타일 (관리, 조회 등)
    BTN_ACTION = """
        QPushButton {
            font-size: 10px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 5px;
            color: #495057;
        }
        QPushButton:hover {
            background-color: #e2e6ea;
        }
        QPushButton:pressed {
            background-color: #dae0e5;
        }
    """
    BTN_SUB = """
        QPushButton {
            background-color: white;
            border: 1px solid #CBD5E0;
            border-radius: 6px;
            color: #4A5568;
            padding: 6px 12px;
            font-size: 10px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #EDF2F7;
            border-color: #A0AEC0;
        }
    """
    TOOLTIP_LIGHT = (
        f"QToolTip {{ "
        f"background-color: #FFFFFF; color: #2D3748; "
        f"border: 1px solid #CBD5E0; padding: 6px; border-radius: 4px; "
        f"font-size: 9pt; font-family: '{DEFAULT_FONT_FAMILY}'; "
        f"}}"
    )
    BTN_HELP_TOOLTIP = (
        "QToolButton{min-width:20px;max-width:20px;min-height:20px;max-height:20px;"
        "border:1px solid #CBD5E0;border-radius:10px;background:#FFFFFF;color:#4A5568;"
        "font-weight:700;padding:0;}"
        "QToolButton:hover{background:#F7FAFC;border-color:#A0AEC0;}"
    )

    # 6. 입력창 스타일 (기상 정보 등 숫자 입력용)
    # qproperty-alignment를 통해 텍스트를 중앙으로 배치합니다.
    INPUT_CENTER = """
        QLineEdit {
            font-size: 10px;
            border: 1px solid #F0F0F0;
            padding: 5px;
            border-radius: 4px;
            font-size: 10px;
            qproperty-alignment: 'AlignCenter';
            background-color: #FAFAFA;
        }
        QLineEdit:focus {
            border: 1px solid #2D5A27;
            background-color: white;
        }
        QSpinBox {
            font-size: 10px;
            border: 1px solid #F0F0F0;
            padding: 4px 2px 4px 6px;
            border-radius: 4px;
            background-color: #FAFAFA;
            min-height: 28px;
            max-height: 28px;
        }
        QSpinBox:focus {
            border: 1px solid #2D5A27;
            background-color: white;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            subcontrol-origin: border;
            width: 16px;
            border: none;
            border-left: 1px solid #E8E8E8;
            background-color: #F3F3F3;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background-color: #E8E8E8;
        }
        QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
            background-color: #DDDDDD;
        }
    """
    INPUT_FLAT = "border: 0px; background-color: #EDF2F7; border-radius: 8px; padding: 8px; color: #2D3748;"
    # 읽기전용(ReadOnly) 입력창 스타일
    INPUT_READONLY = """
        QLineEdit {
            font-size: 10px;
            padding: 5px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            background-color: #F5F5F5;
            color: #333333;
        }
    """
    INPUT_RIGHT = """
        QLineEdit {
            font-size: 10px;
            padding: 5px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            background-color: white;
        }
        QLineEdit:focus {
            border: 1px solid #3498db;
        }
    """

    # 숫자(기본단가 등): 텍스트 입력·천단위 콤마 표시·우측 정렬 (스핀박스 대신)
    INPUT_PRICE_TEXT = """
        QLineEdit {
            font-size: 10px;
            padding: 5px 6px;
            border: 1px solid #F0F0F0;
            border-radius: 4px;
            background-color: #FAFAFA;
            qproperty-alignment: 'AlignRight';
        }
        QLineEdit:focus {
            border: 1px solid #2D5A27;
            background-color: white;
        }
    """

    INPUT_LEFT = """
        QLineEdit {
            font-size: 10px;
            padding: 5px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            background-color: white;
        }
        QLineEdit:focus {
            border: 1px solid #3498db;
        }
    """

    # 합계(a+b) 강조 스타일
    INPUT_TOTAL = """
        QLineEdit {
            font-size: 10px;
            font-weight: bold;      /* 세미콜론 필수 */
            border: 1px solid #3498db;
            border-radius: 4px;
            padding: 5px;
            background-color: #EBF5FB;
            color: #1B4F72;
        }
    """

    #7. 콤보박스, Date_Edit 스타일
    COMBO = """
        QComboBox, QDateEdit {
        border: 1px solid #DDD;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 10px;
        background-color: white;
        height: 25px;        
        }

        /* 1. 달력 전체 기본 배경 및 글씨색 */
        QCalendarWidget QWidget {
            background-color: white;
            color: black;
        }

        /* 2. 상단 네비게이션 바 (년/월/화살표 있는 영역) */
        QCalendarWidget QWidget#qt_calendar_navigationbar {
            background-color: #F8F9FA; /* 헤더 배경을 살짝 회색으로 구분 */
            border-bottom: 1px solid #E2E8F0;
        }

        /* 3. 상단 네비게이션 버튼 (년도, 월, 좌우 화살표) 폰트 색상 강제 지정 */
        QCalendarWidget QToolButton {
            color: #333333; /* 진한 회색 (흰색 배경 위에서 잘 보임) */
            background-color: transparent;
            border: none;
            font-weight: bold;
            icon-size: 20px; /* 화살표 아이콘 크기 */
        }

        /* 4. 버튼에 마우스 올렸을 때 효과 */
        QCalendarWidget QToolButton:hover {
            background-color: #E2E8F0;
            border-radius: 4px;
        }

        /* 5. 년도 직접 입력하는 스핀박스 (숫자 입력창) */
        QCalendarWidget QSpinBox {
            font-size:10px;
            color: black;
            background-color: white;
            selection-background-color: #4A90E2;
            selection-color: white;
        }
        
        /* 드롭다운 버튼 영역 정밀 설정 */
        QComboBox::drop-down, QDateEdit::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left: 1px solid #EEE;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: #FAFAFA;
        }

        /* QDateEdit 전용 버튼 위치 강제 고정 */
        QDateEdit::down-button {
            subcontrol-origin: margin;
            subcontrol-position: center;
        }

        /* 화살표 삼각형 그리기 (이 부분이 없으면 버튼이 비어 보임) */
        QComboBox::down-arrow, QDateEdit::down-arrow {
            image: none; 
            width: 0; height: 0; 
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #666;
            position: relative;
            top: 1px;
        }
        
        /* 클릭 시 색상 변경 */
        QComboBox::down-arrow:on, QDateEdit::down-arrow:on {
            border-top: none;
            border-bottom: 5px solid #2D5A27;
        }

        /* 팝업 목록: 차트·다른 위젯 위에 올라와도 가독성 유지 (불투명 배경·테두리) */
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            color: #2D3748;
            border: 1px solid #E2E8F0;
            border-radius: 4px;
            outline: none;
            padding: 2px;
            selection-background-color: #E6F4EA;
            selection-color: #1A202C;
        }
        QComboBox QAbstractItemView::item {
            min-height: 22px;
            padding: 4px 8px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #F7FAFC;
            color: #2D3748;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #E6F4EA;
            color: #1A202C;
        }

        /* QDateEdit 팝업 내 캘린더 그리드(Windows 기본 어두운 톤 방지) */
        QCalendarWidget QTableView {
            background-color: #FFFFFF;
            color: #2D3748;
            gridline-color: #E2E8F0;
            selection-background-color: #E6F4EA;
            selection-color: #1A202C;
            alternate-background-color: #F8FAF8;
        }
        QCalendarWidget QAbstractItemView {
            background-color: #FFFFFF;
            color: #2D3748;
        }
    """

    # 8. 라벨 텍스트 스타일
    LBL_TITLE = "font-size: 12px; font-weight: bold; color: #2D5A27; border: none;"
    # 영농일지 작성: 상단 대제목(강조) vs 카드/탭 내 구역 제목(상대적으로 작게)
    WORK_LOG_PAGE_TITLE = (
        "font-size: 13px; font-weight: bold; color: #2D5A27; border: none;"
    )
    WORK_LOG_SECTION_TITLE = (
        "font-size: 12px; font-weight: bold; color: #444; border: none;"
    )
    LBL_GRID_HEADER = " font-size: 10px; font-weight: bold; color: #444; border: none; background: transparent;"
    LBL_SUB = "font-size: 10px; color: #777; border: none; qproperty-alignment: 'AlignCenter'; margin-bottom: 2px;"
    # QLabel용 LBL_SUB의 alignment는 QCheckBox 등에 적용 시 Qt 경고 발생 → 보조 텍스트용만 사용
    CHK_CAPTION = (
        "QCheckBox { font-size: 10px; color: #777; spacing: 6px; }"
        "QCheckBox::indicator { width: 14px; height: 14px; margin-left: 1px; }"
    )
    LBL_TABLE_SUB = "font-size: 10px; background: transparent; color: #4A5568; font-weight: bold; padding: 4px; border-radius: 3px; border: none;"
    LbL_HIGHTLIGHT = "font-size: 12px; color: #27AE60; font-weight: bold; margin-left: 10px; "
    LBL_TEXT_LEFT_LIGHT = " font-size: 10px; font-weight: bold; color: #444; border: none; background: transparent; qproperty-alignment: 'AlignLeft';"
    LBL_TEXT_RIGHT_LIGHT = " font-size: 10px; font-weight: bold; color: #444; border: none; background: transparent; qproperty-alignment: 'AlignRight';"
    LBL_TEXT_CENTER_LIGHT = " font-size: 10px; font-weight: bold; color: #444; border: none; background: transparent; qproperty-alignment: 'AlignCenter';"
    LBL_DATE = "font-size: 10px; font-weight: bold; color: #333; border: none;"
    LBL_DASH_UNPAID = "font-size: 11px; color: #D32F2F; font-weight: bold; border: none; background: transparent;"
    
    # 대시보드 카드 공통 텍스트 위계(1차: 비용 현황 카드 적용)
    DASH_CARD_TITLE = (
        "font-size: 12px; font-weight: bold; color: #2D5A27; border: none; background: transparent;"
    )
    DASH_SUBCARD_TITLE = (
        "font-size: 11px; font-weight: bold; color: #444; border: none; background: transparent;"
    )
    # 비용 상세: 요약 숫자·미지급 RichText와 테이블(10pt) 동일 크기
    DASH_COST_NUM_PT = "10pt"
    DASH_KPI_VALUE = (
        "font-size: 10px; font-weight: bold; color: #2D3748; border: none; background: transparent;"
    )
    # 비용 상세 상단 — 총비용(굵기만 강조, 크기는 동일)
    DASH_KPI_VALUE_PRIMARY = (
        "font-size: 10px; font-weight: bold; color: #1A202C; border: none; background: transparent;"
    )
    DASH_SUMMARY_VALUE = (
        "font-size: 10px; font-weight: normal; color: #2D3748; border: none; background: transparent;"
    )
    DASH_BODY_TEXT = (
        "font-size: 10px; font-weight: normal; color: #666; border: none; background: transparent;"
    )
    DASH_BODY_EMPH = (
        "font-size: 10px; font-weight: bold; color: #4A5568; border: none; background: transparent;"
    )
    DASH_LABEL = (
        "font-size: 9px; font-weight: normal; color: #888; border: none; background: transparent;"
    )
    # 비용 상세 필터 라벨(한 줄 배치용, DASH_LABEL보다 눈에 띄게)
    DASH_FILTER_LABEL = (
        "font-size: 10px; font-weight: bold; color: #4A5568; border: none; background: transparent;"
    )
    # 비용 상세·미지급 패널 강조(건수·금액)
    DASH_UNPAID_HIGHLIGHT = (
        "font-size: 10px; font-weight: bold; color: #C53030; border: none; background: transparent;"
    )
    # 미지급 금액만 HTML 등에서 사용
    DASH_UNPAID_AMOUNT_COLOR = "#E53E3E"
    # 메인 작업 테이블: 행 hover(기본 TABLE보다 은은하게 덮어씀)
    TABLE_COST_MAIN_HOVER = """
        QTableWidget::item:hover {
            background-color: #EDF2F7;
            color: #1A202C;
        }
    """
    
    # 9. 텍스트 에디트 (비고란 등)
    TEXT_EDIT = """
        QTextEdit {
            border: 1px solid #F0F0F0;
            border-radius: 6px;
            font-size: 10px;
            padding: 8px;
            background-color: white;
        }
    """
    # 10. 그리드 헤더용 표준 스타일 (신설)
    #DATE_EDIT스타일
    DATE_EDIT = """
        QDateEdit {
            border: 1px solid #ced4da;
            border-radius: 4px;
            padding: 5px;
            background-color: white;
            font-size: 10px;
            min-width: 120px;
        }
        QDateEdit::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #ced4da;
        }
    """  
    # 10. 탭 스타일 — 메인 배경(#FDFBF7)과 구분, 카드·포인트 그린(#2D5A27)과 통일
    STYLE_TABS = """
        QTabWidget::pane {
            border: 1px solid #EAE7E2;
            background: #FFFFFF;
            margin-top: -1px;
        }
        QTabBar::tab {
            background: #E8EDE8;
            color: #5F6B5F;
            border: 1px solid #CDD6CD;
            border-bottom: none;
            padding: 8px 20px;
            font-size: 11px;
            font-weight: bold;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 4px;
        }
        QTabBar::tab:hover:!selected {
            background: #DCE8DC;
            color: #2D5A27;
        }
        QTabBar::tab:selected {
            background: #FFFFFF;
            color: #2D5A27;
            border: 1px solid #EAE7E2;
            border-bottom: none;
        }
    """
    
    # 11. 입력 위젯 Flat 디자인 (Border 0)
    

    # 12. group_box
    GROUP_BOX = """
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            border: 1px solid #EAE7E2;
            border-radius: 8px;
            margin-top: 15px;
            padding-top: 15px;
            background-color: white;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 15px;
            padding: 0 5px;
            color: #2D5A27;
        }
    """

    # Typography 기준 체계 (기본 10)
    TXT_BODY = "font-size: 10px; font-weight: normal; color: #2D3748; border: none; background: transparent;"
    TXT_LABEL_BOLD = "font-size: 10px; font-weight: bold; color: #444; border: none; background: transparent;"
    TXT_TAB_TITLE = "font-size: 11px; font-weight: bold;"
    TXT_CARD_TITLE = "font-size: 13px; font-weight: bold;"
    TXT_SUMMARY_VALUE = "font-size: 10px; font-weight: normal; color: #2D3748; border: none; background: transparent;"
    TXT_SUMMARY_VALUE_EMPH = "font-size: 11px; font-weight: bold; color: #2D3748; border: none; background: transparent;"
    TXT_STATUS_GREEN = "font-size: 10px; font-weight: bold; color: #2E7D32; border: none; background: transparent;"
    TXT_CAPTION = "font-size: 10px; font-weight: normal; color: #666; border: none; background: transparent;"
    BADGE_NEW = "background-color: #FF5722; color: white; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 1px 4px;"

    # 뱃지 디자인
    # 12. 주문관리 전용 요약 배지 스타일
    ORDER_BADGE = """
        QPushButton {
            background-color: white;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 8px 15px;
            font-size: 10px;
            font-weight: bold;
            color: #4A5568;
            text-align: left;
        }
        QPushButton:hover {
            background-color: #F8FAFC;
            border-color: #4A90E2;
        }
        /* 경고 상태 (미수금 존재/수량 미달 시) */
        QPushButton[state="warning"] {
            background-color: #FFF5F5;
            border: 1px solid #FEB2B2;
            color: #C53030;
        }
        /* 완료 상태 (모두 일치 시) */
        QPushButton[state="success"] {
            background-color: #F0FFF4;
            border: 1px solid #9AE6B4;
            color: #2F855A;
        }
    """
    # [수정] 주문관리 전용 고품격 요약 배지
    ORDER_BADGE_BASE = """
        QPushButton {
            background-color: white;
            border: 1px solid #EAE7E2;
            border-radius: 12px;
            padding: 12px 25px;
            font-size: 11px;
            font-weight: bold;
            color: #4A5568;
            text-align: center;
        }
        QPushButton:hover {
            border-color: #4A90E2;
            background-color: #F8FBFF;
        }
    """
    
    # 상태별 포인트 보더 (주의/완료)
    BADGE_WARNING = "border: 1.5px solid #F6AD55; color: #DD6B20; background-color: #FFFAF0;"
    BADGE_SUCCESS = "border: 1.5px solid #68D391; color: #2F855A; background-color: #F0FFF4;"

    AI_RESULT_CONTAINER = (
        "background-color: #F0FFF4; "
        "padding: 15px; "
        "border-radius: 10px; "
        "border: 1px solid #C6F6D5;"
    )
    
    # 규격별 텍스트 색상 가이드
    AI_TEXT_NORMAL = "color: #2D3748; font-weight: bold;"
    AI_TEXT_LOSS = "color: #E53E3E; font-weight: normal;"

    SEARCH_BAR_STYLE ="""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                font-weight: bold;
                color: #495057;
            }
        """
    
    EDGE_HANDLE = """
        QPushButton {
            background-color: #2E7D32; 
            color: white; 
            border: none;
            border-radius: 0px 8px 8px 0px; 
            font-weight: bold;
        }
        QPushButton:hover { background-color: #1B5E20; }
    """

    # 대시보드 카드 (흰색, 둥근모서리, hover 시 테두리 강조)
    DASHBOARD_CARD = """
        QFrame {
            background-color: white;
            border: 1px solid #EAE7E2;
            border-radius: 12px;
        }
        QFrame:hover {
            border: 1px solid #4A90E2;
            background-color: #FAFDFF;
        }
    """

    # 대시보드 브리핑 바: «대시보드 편집» ON(드래그 재정렬 활성)
    BTN_DASHBOARD_EDIT_ON = """
        QPushButton {
            background-color: #E8F4FD;
            color: #2B6CB0;
            border: 1px solid #90CDF4;
            font-weight: 600;
            border-radius: 4px;
            padding: 5px 12px;
        }
        QPushButton:hover {
            background-color: #D6EEFB;
            border: 1px solid #63B3ED;
        }
        QPushButton:pressed {
            background-color: #BEE3F8;
        }
    """

    # 대시보드 카드 우하단 «상세 →» (보조 액션, 과도한 그림자 없음)
    BTN_DASHBOARD_CARD_DETAIL = """
        QPushButton {
            background-color: #F1F4F1;
            color: #4A5568;
            border: 1px solid #CBD5E0;
            border-radius: 4px;
            padding: 2px 10px;
        }
        QPushButton:hover {
            background-color: #E2E8F0;
            color: #2D3748;
            border: 1px solid #A0AEC0;
        }
        QPushButton:pressed {
            background-color: #CBD5E0;
            color: #2D3748;
        }
    """

    # [추가] 좌측 카드 리스트 표준 디자인 (선택 시 딥그린 보더)
    LIST_CARD_STYLE = """
        QListWidget { border: none; background: transparent; outline: none; }
        QListWidget::item { 
            background-color: white; 
            border: 1px solid #EAE7E2; 
            border-radius: 10px; 
            margin-bottom: 8px; 
            padding: 10px;
            color: #2D3748; /* 기본 텍스트 색상 */
        }
        QListWidget::item:selected { 
            background-color: #F1F8F1; 
            border: 2px solid #2E7D32; 
            color: #1B5E20; 
        }
    """


def _normalize_qss_font_size_px_to_pt(qss: str) -> str:
    """
    Qt font 경고 완화:
    `font-size: Npx`를 `font-size: Npt`로 바꿔 pointSize=-1 경로를 줄인다.
    """
    if not isinstance(qss, str) or "font-size" not in qss or "px" not in qss:
        return qss
    return re.sub(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)\s*px", r"\1\2pt", qss)


for _name, _value in list(vars(MainStyles).items()):
    if _name.startswith("_"):
        continue
    if isinstance(_value, str):
        setattr(MainStyles, _name, _normalize_qss_font_size_px_to_pt(_value))