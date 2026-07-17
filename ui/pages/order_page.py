# -*- coding: utf-8 -*-
"""
=============================================================================
order_page.py - 주문 관리 모듈
=============================================================================
과수원 플랫폼의 주문 등록·조회·편집·배송계획 관리 화면을 담당합니다.
주문번호 규칙: ORD + YYYYMMDD + - + SEQ(3자리) 예) ORD20260101-001

[클래스 구조]
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. ClickCounterWidget      재고 수량 입력용 커스텀 위젯                  │
│    - 좌클릭 +1 / 우클릭 -1 / 장 press 시 직접입력 다이얼로그              │
│    - 재고(avail_qty)에 따라 색상 구분 (부족: 빨강, 여유: 녹색)            │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. CustomerSearchPopup     고객 검색 팝업                                │
│    - 고객명/연락처 검색, m_customer 조회, 선택 시 메인에 이식             │
│    - 신규고객등록 버튼 → CustomerRegistrationPopup 연계                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. CustomerRegistrationPopup  신규 고객 등록 팝업                        │
│    - ID: C + YYMMDDHHMMSS, custm_tp: CT01, reg_id/mod_id 기록            │
├─────────────────────────────────────────────────────────────────────────┤
│ 4. StockMatrixPopup        재고 매트릭스 팝업                            │
│    - 품목별 가변 격자(배: 등급×사이즈, 배즙/원물: 별도 구조)              │
│    - t_stock_master 집계, ClickCounterWidget로 주문 수량 선택             │
├─────────────────────────────────────────────────────────────────────────┤
│ 5. PriceSettingPopup       단가 설정 팝업                                │
│    - 시즌/판매년도/생산년도 기준 m_item_unit_price CRUD                   │
│    - 트랜잭션(BEGIN/COMMIT/ROLLBACK) 기반 무결성 보장                    │
├─────────────────────────────────────────────────────────────────────────┤
│ 6. OrderManagementPage     [메인] 주문 관리 페이지                       │
│    ┌─────────┬──────────────────────────┬─────────┐                     │
│    │ 좌 패널 │    중앙 패널 (상시)       │ 우 패널 │                     │
│    │ 주문목록│ 신규주문 / 상세편집       │ 배송계획│                     │
│    │ 필터/검색│ 고객검색·재고·단가 팝업   │ 엑셀업로드│                    │
│    │ 일괄확정│ 주문상세 테이블·배송비    │ 배송지연리스트│                  │
│    └─────────┴──────────────────────────┴─────────┘                     │
│    - 슬라이드 토글(> / <) 핸들로 좌/우 패널 애니메이션 전환               │
│    - db_manager, session, CodeManager, AccountManager 활용               │
└─────────────────────────────────────────────────────────────────────────┘

[의존 모듈] styles, code_manager, account_manager
=============================================================================
"""
import sys
from pathlib import Path
for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402
import re
import sqlite3
from datetime import datetime

from PyQt6.QtWidgets import *
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QSplitter, QFrame, QTabWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QDate, QTimer, QPropertyAnimation, QEasingCurve, QPoint, Qt, QParallelAnimationGroup

from ui.styles import MainStyles
from core.code_manager import CodeManager
from core.account_manager import AccountManager

# [커스텀 위젯] 마우스 클릭 카운터 (어제 제작본 유지)
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel

class ClickCounterWidget(QFrame):
    def __init__(self, avail_qty, parent=None):
        super().__init__(parent)
        self.value = 0
        self.avail_qty = avail_qty
        self.is_long_press = False
        
        self.long_press_timer = QTimer(self)
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self.trigger_input_dialog) # 지연 실행 연결
        
        self.init_ui()

    def init_ui(self):
        bg_color = "#FFF5F5" if self.avail_qty <= 0 else "#F0FFF4"  # 재고 부족: 연빨강, 여유: 연녹색
        self.setStyleSheet(MainStyles.CARD + f"\nQFrame {{ background-color: {bg_color}; border-color: #E2E8F0; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        color = "#E53E3E" if self.avail_qty <= 0 else "#2F855A"
        self.lbl_stock = QLabel(f"재고: {int(self.avail_qty)}")
        self.lbl_stock.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_stock.setStyleSheet(MainStyles.TXT_LABEL_BOLD + f" color: {color};")
        self.lbl_stock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_value = QLabel("0")
        self.lbl_value.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_value.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH + " color: #2D3748;")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_stock); layout.addWidget(self.lbl_value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_long_press = False
            self.long_press_timer.start(1000) # 1초(1000ms)로 정확히 설정
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.long_press_timer.stop()
        if not self.is_long_press:
            if event.button() == Qt.MouseButton.LeftButton:
                self.value += 1
            elif event.button() == Qt.MouseButton.RightButton:
                if self.value > 0: self.value -= 1
            self.update_display()
        self.is_long_press = False
        super().mouseReleaseEvent(event)

    def trigger_input_dialog(self):
        """이벤트를 분리하여 입력창을 띄움 (먹통 방지 핵심)"""
        self.is_long_press = True
        # 마우스 포커스 꼬임을 방지하기 위해 0.01초 뒤에 실행되도록 예약
        QTimer.singleShot(10, self.handle_long_press)

    def handle_long_press(self):
        # 최상위 윈도우를 부모로 하여 포커스 강제 확보
        num, ok = QInputDialog.getInt(
            self.window(), "수량 직접 입력", 
            "주문 수량을 입력하세요:", 
            self.value, 0, 999999, 1
        )
        if ok:
            self.value = num
            self.update_display()

    def update_display(self):
        self.lbl_value.setText(str(self.value))
        color = "#3182CE" if self.value > 0 else "#2D3748"
        self.lbl_value.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH + f" color: {color};")

class CustomerSearchPopup(QDialog):
    def __init__(self, db_manager, farm_cd, user_id, search_keyword="", parent=None):
        super().__init__(parent) # 부모 위젯 연결 (모달 안정성 확보)
        self.db = db_manager
        self.farm_cd = farm_cd
        self.user_id = user_id
        self.keyword = search_keyword # 초기 검색어 저장
        self.selected_customer = None
        
        self.setWindowTitle("🔍 고객 검색")
        self.setFixedSize(600, 450)
        self.init_ui()
        
        # 📍 팝업이 뜨자마자 초기 검색어로 조회 수행
        if self.keyword:
            self.edit_search.setText(self.keyword)
            self.search_customer(self.keyword)

    def init_ui(self):
        # 1. 팝업창 크기 확장 (가로를 넓게 하여 주소 시인성 확보)
        self.setFixedSize(800, 550) 
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 2. 검색 바 영역
        search_layout = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("고객명 또는 연락처를 입력하세요...")
        self.edit_search.setStyleSheet(MainStyles.INPUT_LEFT)
        self.edit_search.setFixedHeight(35)
        self.edit_search.returnPressed.connect(self.search_customer)
        
        btn_search = QPushButton("🔍 검색")
        btn_search.setFixedWidth(80)
        btn_search.setFixedHeight(35)
        btn_search.setStyleSheet(MainStyles.BTN_FETCH)
        btn_search.clicked.connect(self.search_customer)
        
        # 신규고객등록 버튼
        btn_new_cust = QPushButton("👤 신규고객등록")
        btn_new_cust.setFixedWidth(110); btn_new_cust.setFixedHeight(35)
        btn_new_cust.setStyleSheet(MainStyles.BTN_PRIMARY) # 강조색
        btn_new_cust.clicked.connect(self.open_registration_popup)
        
        search_layout.addWidget(self.edit_search)
        search_layout.addWidget(btn_search)
        search_layout.addWidget(btn_new_cust) # 👈 지시하신 위치
        layout.addLayout(search_layout)

        # 3. 결과 테이블 (주소 칸을 길게 설정)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["고객명", "연락처", "기본주소", "ID"])
        self.table.setStyleSheet(MainStyles.TABLE)
        self.table.setColumnHidden(3, True) # ID 숨김
        
        # [핵심] 컬럼 너비 정책 설정
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive) # 고객명 (조절 가능)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive) # 연락처 (조절 가능)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)     # 주소 (남은 공간 모두 차지)
        
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 150)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # 편집 금지
        self.table.doubleClicked.connect(self.select_customer)
        layout.addWidget(self.table)

        # 4. 하단 버튼
        btn_select = QPushButton("✓ 선택 완료")
        btn_select.setFixedHeight(45)
        btn_select.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_select.clicked.connect(self.select_customer)
        layout.addWidget(btn_select)

    def search_customer(self, *args):
        text = self.edit_search.text().strip()
        # farm_cd는 메인 페이지에서 넘겨받은 값을 사용
        sql = """
            SELECT custm_nm, mobile, addr1, addr2, rmk, custm_id 
            FROM m_customer 
            WHERE farm_cd = ? AND (custm_nm LIKE ? OR mobile LIKE ?)
        """
        res = self.db.execute_query(sql, (self.farm_cd, f"%{text}%", f"%{text}%"))
        
        self.table.setRowCount(0)
        for r in res:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # [에러 방지] sqlite3.Row를 dict로 즉시 변환
            cust_data = dict(r) 
            
            # 테이블 아이템 생성 및 데이터 심기
            name_item = QTableWidgetItem(str(cust_data['custm_nm']))
            name_item.setData(Qt.ItemDataRole.UserRole, cust_data) # 전체 딕셔너리 저장
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            mobile_item = QTableWidgetItem(str(cust_data['mobile']))
            mobile_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            addr_item = QTableWidgetItem(str(cust_data['addr1'])) # 기본 주소만 표시
            # 주소는 길기 때문에 왼쪽 정렬 유지
            
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, mobile_item)
            self.table.setItem(row, 2, addr_item)

    def select_customer(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            # 0번 셀에 숨겨둔 딕셔너리 데이터를 꺼냄
            name_item = self.table.item(curr_row, 0)
            self.selected_customer = name_item.data(Qt.ItemDataRole.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "알림", "고객을 먼저 선택해 주세요.")

    def get_selected_customer(self):
        """본부에서 팝업이 닫힌 후 호출하여 선택된 고객 정보를 가져갑니다."""
        return self.selected_customer

    def open_registration_popup(self):
        """[Action] 등록 팝업을 열고, 성공 시 즉시 선택 상태로 종료"""
        # 현재 검색창의 텍스트를 이름으로 제안
        name_hint = self.edit_search.text() if not self.edit_search.text().isdigit() else ""
        mobile_hint = self.edit_search.text() if self.edit_search.text().isdigit() else ""
        
        reg_popup = CustomerRegistrationPopup(
            self.db, self.farm_cd, self.user_id, name_hint, mobile_hint
        )
        
        if reg_popup.exec():
            # 등록 성공 시 저장된 데이터를 바로 가로채서 팝업을 닫습니다.
            self.selected_customer = reg_popup.new_customer_data
            if self.selected_customer:
                # print(f"[System] 신규 고객 등록 후 즉시 이식: {self.selected_customer['custm_nm']}")
                self.accept() # 검색 팝업도 함께 닫으며 메인으로 데이터 전달

# 신규 고객 등록
class CustomerRegistrationPopup(QDialog):
    # 📍 user_id 인자 추가 (누가 등록했는지 기록하기 위함)
    def __init__(self, db_manager, farm_cd, user_id, initial_name="", initial_mobile=""):
        super().__init__()
        self.db = db_manager
        self.farm_cd = farm_cd
        self.user_id = user_id # 등록자 ID 저장
        self.new_customer_data = None
        
        self.setWindowTitle("👤 신규 고객 등록")
        self.setFixedSize(500, 480) # 높이 약간 늘림
        self.init_ui(initial_name, initial_mobile)

    def init_ui(self, name, mobile):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setVerticalSpacing(15)

        # 입력 필드
        self.txt_name = QLineEdit(name); self.txt_name.setStyleSheet(MainStyles.INPUT_LEFT)
        self.txt_mobile = QLineEdit(mobile); self.txt_mobile.setPlaceholderText("010-0000-0000"); self.txt_mobile.setStyleSheet(MainStyles.INPUT_LEFT)
        self.txt_addr1 = QLineEdit(); self.txt_addr1.setPlaceholderText("기본 주소"); self.txt_addr1.setStyleSheet(MainStyles.INPUT_LEFT)
        self.txt_addr2 = QLineEdit(); self.txt_addr2.setPlaceholderText("상세 주소"); self.txt_addr2.setStyleSheet(MainStyles.INPUT_LEFT)
        self.txt_rmk = QLineEdit(); self.txt_rmk.setPlaceholderText("메모 (예: 지인, 단골)"); self.txt_rmk.setStyleSheet(MainStyles.INPUT_LEFT)

        # 라벨 스타일 함수 (공통 라벨 스타일 사용)
        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(MainStyles.TXT_CARD_TITLE)
            return l

        form_layout.addRow(lbl("고객명 *"), self.txt_name)
        form_layout.addRow(lbl("연락처 *"), self.txt_mobile)
        form_layout.addRow(lbl("주소"), self.txt_addr1)
        form_layout.addRow(lbl(""), self.txt_addr2)
        form_layout.addRow(lbl("비고"), self.txt_rmk)
        
        layout.addLayout(form_layout); layout.addStretch(1)

        btn_save = QPushButton("✨ 저장하고 바로 적용")
        btn_save.setFixedHeight(45); btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_save.clicked.connect(self.save_customer)
        layout.addWidget(btn_save)

    def save_customer(self):
        name = self.txt_name.text().strip()
        mobile = self.txt_mobile.text().strip()
        
        if not name or not mobile:
            QMessageBox.warning(self, "입력 오류", "고객명과 연락처는 필수입니다.")
            return

        try:
            # ID 생성 (C + 년월일시분초)
            cust_id = f"C{datetime.now().strftime('%y%m%d%H%M%S')}"
            
            # 📍 [보강된 쿼리] 등록자(reg_id), 수정자(mod_id), 유형(custm_tp), 사용여부(use_yn) 모두 포함
            sql = """
                INSERT INTO m_customer (
                    custm_id, farm_cd, custm_nm, mobile, 
                    zip_cd, addr1, addr2, 
                    custm_tp, rmk, use_yn, 
                    reg_id, reg_dt, mod_id, mod_dt
                ) VALUES (
                    ?, ?, ?, ?, 
                    '', ?, ?, 
                    'CT01', ?, 'Y', 
                    ?, datetime('now', 'localtime'), ?, datetime('now', 'localtime')
                )
            """
            # 파라미터 매핑 (self.user_id 추가)
            self.db.execute_query(sql, (
                cust_id, self.farm_cd, name, mobile,
                self.txt_addr1.text(), self.txt_addr2.text(),
                self.txt_rmk.text(),
                self.user_id, self.user_id
            ))
            
            self.new_customer_data = {
                'custm_id': cust_id,  # 👈 핵심 추가
                'custm_nm': name,
                'mobile': mobile,
                'addr1': self.txt_addr1.text(),
                'addr2': self.txt_addr2.text(),
                'rmk': self.txt_rmk.text()
            }
            
            QMessageBox.information(self, "완료", "신규 고객이 등록되었습니다.")
            self.accept()
            
        except Exception as e:
            if "UNIQUE" in str(e): QMessageBox.warning(self, "중복", "이미 등록된 연락처입니다.")
            else: QMessageBox.critical(self, "오류", f"저장 실패: {e}")

# [재고 매트릭스 팝업] 
class StockMatrixPopup(QDialog):
    def __init__(self, harvest_year, item_cd, v_cd, v_nm, weight, db_manager, code_manager, farm_cd, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.codes = code_manager
        self.farm_cd = farm_cd
        
        # [지휘 정보]
        self.init_h_year = str(harvest_year)
        self.init_item_cd = item_cd
        self.init_v_cd = v_cd
        self.init_v_nm = v_nm
        self.init_weight = weight
        
        self.init_ui()
        self.setup_combos()
        self.set_initial_filters()
        self.load_matrix_data() # 최초 로드

    def init_ui(self):
        """[UI] 1단(전략 조회) / 2단(가변 격자판)"""
        self.setWindowTitle("📊 재고 매트릭스 지휘소")
        self.resize(900, 750)
        self.setStyleSheet(MainStyles.MAIN_BG)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # ---------------------------------------------------------------------
        # [1단] 조회 및 지휘 영역 (품목/품종/무게 + 담기)
        # ---------------------------------------------------------------------
        filter_group = QGroupBox("📋 1단: 재고 조회 및 주문 지휘")
        filter_group.setStyleSheet(MainStyles.GROUP_BOX)
        filter_lay = QHBoxLayout(filter_group)

        self.sel_item = QComboBox()
        self.sel_v = QComboBox()
        self.sel_w = QComboBox()
        
        for w in [self.sel_item, self.sel_v, self.sel_w]:
            w.setStyleSheet(MainStyles.COMBO)
            w.setFixedWidth(115)

        self.btn_search = QPushButton("🔍 재고조회")
        self.btn_search.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_search.clicked.connect(self.load_matrix_data)

        self.btn_confirm = QPushButton("✓ 주문서 담기")
        self.btn_confirm.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_confirm.setFixedSize(140, 38)
        self.btn_confirm.clicked.connect(self.accept)

        filter_lay.addWidget(self.make_lbl("품목")); filter_lay.addWidget(self.sel_item)
        filter_lay.addWidget(self.make_lbl("품종")); filter_lay.addWidget(self.sel_v)
        filter_lay.addWidget(self.make_lbl("무게")); filter_lay.addWidget(self.sel_w)
        filter_lay.addWidget(self.btn_search)
        filter_lay.addStretch()
        filter_lay.addWidget(self.btn_confirm)
        layout.addWidget(filter_group)

        # ---------------------------------------------------------------------
        # [2단] 가변 매트릭스 격자 (QTableWidget)
        # ---------------------------------------------------------------------
        matrix_box = QGroupBox("🍏 2단: 품목별 맞춤 재고 격자")
        matrix_box.setStyleSheet(MainStyles.GROUP_BOX)
        matrix_lay = QVBoxLayout(matrix_box)

        self.table = QTableWidget()
        self.table.setStyleSheet(MainStyles.TABLE)
        # 행/열 헤더가 테이블 크기에 맞게 자동 확장되도록 설정
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        matrix_lay.addWidget(self.table)
        layout.addWidget(matrix_box)

    def setup_combos(self):
        self.load_codes(self.sel_item, "FR01")
        self.sel_item.currentIndexChanged.connect(self.on_item_changed)
        self.on_item_changed()

    def on_item_changed(self):
        item_cd = self.sel_item.currentData()
        if not item_cd: return
        self.load_codes(self.sel_v, item_cd)
        self.sel_w.clear()
        unit = "kg" if item_cd == "FR010100" else "포"
        for row in self.codes.get_common_codes("SZ01"):
            d = dict(row)
            if unit in d.get('code_nm', ''):
                self.sel_w.addItem(d.get('code_nm'), d.get('code_cd'))

    def set_initial_filters(self):
        idx_i = self.sel_item.findData(self.init_item_cd)
        if idx_i >= 0: self.sel_item.setCurrentIndex(idx_i)
        idx_v = self.sel_v.findData(self.init_v_cd)
        if idx_v >= 0: self.sel_v.setCurrentIndex(idx_v)
        for i in range(self.sel_w.count()):
            if str(self.init_weight) in self.sel_w.itemText(i):
                self.sel_w.setCurrentIndex(i); break

    # ---------------------------------------------------------------------
    # [핵심 수술 부위 1] 품목별 가변 컬럼 로직
    # ---------------------------------------------------------------------
    def load_matrix_data(self):
        """품목에 따라 행/열 구성을 변경하고 재고를 로드합니다."""
        item_cd = self.sel_item.currentData()
        v_cd = self.sel_v.currentData()
        w_text = self.sel_w.currentText()
        weight_val = float(re.findall(r"[-+]?\d*\.\d+|\d+", w_text)[0]) if w_text else 0.0

        if not v_cd: return

        # 📍 [수정] 품목별 가변 컬럼/로우 부모 코드 설정
        if item_cd == 'FR010100':   # 배
            col_p, row_p = 'GR01', 'FR020100'  # 열: 등급, 행: 사이즈
        elif item_cd == 'FR010200': # 배즙
            col_p, row_p = 'QT01', item_cd     # 열: 배즙수량(포), 행: 품종
        else:                       # 원물(FR010300 등)
            col_p, row_p = 'CT01', item_cd     # 열: 저장배종류, 행: 품종

        self.rows_list = [dict(r) for r in self.codes.get_common_codes(row_p)]
        self.cols_list = [dict(r) for r in self.codes.get_common_codes(col_p)]

        self.table.setRowCount(len(self.rows_list))
        self.table.setColumnCount(len(self.cols_list))
        self.table.setHorizontalHeaderLabels([c['code_nm'] for c in self.cols_list])
        self.table.setVerticalHeaderLabels([r['code_nm'] for r in self.rows_list])

        # 재고 데이터 로드 (📍 검색 조건에 item_cd 포함)
        stock_map = self.get_stock_map(item_cd, v_cd, weight_val)

        for r_idx, r_code in enumerate(self.rows_list):
            for c_idx, c_code in enumerate(self.cols_list):
                # 품목별 매핑 키 생성
                if item_cd == 'FR010100':
                    key = (v_cd, c_code['code_cd'], r_code['code_cd'])
                else:
                    # 배즙/원물은 행이 품종(variety), 열이 등급(grade) 자리에 위치
                    key = (r_code['code_cd'], c_code['code_cd'], 'SZ010100')
                
                qty_info = stock_map.get(key, {'real_qty': 0, 'hold_qty': 0})
                avail = qty_info['real_qty'] - qty_info['hold_qty']
                
                # ClickCounterWidget 배치 (대표님 기존 위젯 활용)
                self.table.setCellWidget(r_idx, c_idx, ClickCounterWidget(avail))

    # ---------------------------------------------------------------------
    # [핵심 수술 부위 2] 재고 조회 쿼리 교정
    # ---------------------------------------------------------------------
    def get_stock_map(self, item_cd, v_cd, weight_val):
        """[Data Engine] SUM과 GROUP BY를 사용한 정밀 재고 집계"""
        # 배(Pear)일 때는 선택한 품종만, 그 외엔 해당 품목 전체 품종을 집계하도록 유연하게 대응
        v_filter = "AND variety_cd = ?" if item_cd == 'FR010100' else ""
        
        sql = f"""
            SELECT variety_cd, grade_cd, size_cd, 
                   SUM(in_qty - out_qty) as real_qty, 
                   SUM(reserved_qty) as hold_qty 
            FROM t_stock_master 
            WHERE farm_cd = ? 
              AND CAST(harvest_year AS TEXT) = ? 
              AND item_cd = ?
              {v_filter}
              AND CAST(weight AS FLOAT) = ?
            GROUP BY variety_cd, grade_cd, size_cd
        """
        
        params = [self.farm_cd, str(self.init_h_year), item_cd]
        if item_cd == 'FR010100':
            params.append(v_cd)
        params.append(float(weight_val))

        try:
            res = self.db.execute_query(sql, tuple(params))
            return {(r['variety_cd'], r['grade_cd'], r['size_cd']): dict(r) for r in res}
        except Exception as e:
            print(f"[재고 조회 오류] {e}")
            return {}

    def get_selected_data(self):
        """[Output] 선택된 데이터를 추출할 때 harvest_year를 반드시 포함합니다."""
        selected = []
        for r_idx, r_code in enumerate(self.rows_list):
            for c_idx, c_code in enumerate(self.cols_list):
                widget = self.table.cellWidget(r_idx, c_idx)
                if widget and widget.value > 0:
                    selected.append({
                        'harvest_year': self.init_h_year, # 📍 [필수 추가] 지휘관의 수확년도
                        'item_cd': self.sel_item.currentData(),
                        'v_cd': r_code['code_cd'] if self.sel_item.currentData() != 'FR010100' else self.sel_v.currentData(),
                        'grade_cd': self.cols_list[c_idx]['code_cd'],
                        'size_cd': r_code['code_cd'] if self.sel_item.currentData() == 'FR010100' else 'SZ010100',
                        'qty': widget.value,
                        'weight': self.sel_w.currentText()
                    })
        return selected

    def load_codes(self, combo, p):
        combo.clear()
        for r in self.codes.get_common_codes(p):
            d = dict(r); combo.addItem(d.get('code_nm'), d.get('code_cd'))

    def make_lbl(self, text):
        l = QLabel(text); l.setStyleSheet(MainStyles.TXT_LABEL_BOLD); return l

# 📍 [신규] 단가 설정을 위한 전용 팝업창
class PriceSettingPopup(QDialog):
    def __init__(self, db_manager, code_manager, farm_cd, sales_year, harvest_year, season_cd, season_nm, parent=None):
        """
        [Constructor] 단가 관리 팝업 초기화
        - code_manager(self.codes)를 통해 명칭 조회를 수행하므로 별도 메소드는 삭제합니다.
        """
        super().__init__(parent)
        self.db = db_manager
        self.codes = code_manager  # 📍 코드 관리 전담 매니저
        self.farm_cd = farm_cd
        
        self.init_sales_year = sales_year
        self.init_harvest_year = harvest_year
        self.init_season_cd = season_cd
        
        self.init_ui()
        self.setup_combos()
        self.set_initial_filters()
        self.load_existing_prices() # 초기 필터 기반 자동 조회

    def init_ui(self):
        """[UI] 1단(시즌/년도 조회) / 2단(단가 등록) / 3단(목록) 최적화 배치"""
        self.setWindowTitle(f"💰 단가 지휘 통제실")
        self.resize(800, 700)
        self.setStyleSheet(MainStyles.MAIN_BG)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # ---------------------------------------------------------------------
        # [1단] 전략 조회 구역 (📍 시즌 콤보화 및 삼각 조회 체계)
        # ---------------------------------------------------------------------
        filter_group = QGroupBox("📋 1단: 조회 전략 (시즌/년도)")
        filter_group.setStyleSheet(MainStyles.GROUP_BOX)
        filter_lay = QHBoxLayout(filter_group)
        
        self.sel_season = QComboBox() # 📍 시즌 콤보
        self.sel_sales_year = QSpinBox()
        self.sel_harvest_year = QSpinBox()
        
        for w in [self.sel_season, self.sel_sales_year, self.sel_harvest_year]:
            w.setStyleSheet(MainStyles.COMBO)
            if isinstance(w, QSpinBox):
                w.setRange(2020, 2035)
                w.setFixedWidth(80)
            else:
                w.setFixedWidth(120)

        self.btn_search = QPushButton("🔍 조회")
        self.btn_search.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_search.setFixedWidth(70)
        self.btn_search.clicked.connect(self.load_existing_prices)

        filter_lay.addWidget(self.make_lbl("🌟 시즌"))
        filter_lay.addWidget(self.sel_season)
        filter_lay.addSpacing(10)
        filter_lay.addWidget(self.make_lbl("📅 판매"))
        filter_lay.addWidget(self.sel_sales_year)
        filter_lay.addWidget(self.make_lbl("🍏 생산"))
        filter_lay.addWidget(self.sel_harvest_year)
        filter_lay.addStretch()
        filter_lay.addWidget(self.btn_search)
        
        main_layout.addWidget(filter_group)

        # ---------------------------------------------------------------------
        # [2단] 전술 등록 구역 (📍 단가 포맷팅 및 추가 로직)
        # ---------------------------------------------------------------------
        input_group = QGroupBox("🍎 2단: 단가 등록 전술")
        input_group.setStyleSheet(MainStyles.GROUP_BOX)
        input_lay = QGridLayout(input_group)

        self.sel_item = QComboBox(); self.sel_variety = QComboBox()
        self.sel_grade = QComboBox(); self.sel_size = QComboBox()
        self.sel_weight = QComboBox()
        
        self.edit_unit_price = QLineEdit("0") # 📍 단가 포맷팅 대상
        self.edit_unit_price.setStyleSheet(MainStyles.INPUT_RIGHT)
        self.edit_unit_price.textChanged.connect(self.format_price_input)

        for w in [self.sel_item, self.sel_variety, self.sel_grade, self.sel_size, self.sel_weight]:
            w.setStyleSheet(MainStyles.COMBO)

        self.btn_add_price = QPushButton("➕ 단가 리스트에 추가")
        self.btn_add_price.setStyleSheet(MainStyles.BTN_FETCH)
        self.btn_add_price.setFixedHeight(35)
        self.btn_add_price.clicked.connect(self.add_item_row_action) # 📍 추가 로직

        input_lay.addWidget(self.make_lbl("📦 품목"), 0, 0); input_lay.addWidget(self.sel_item, 0, 1)
        input_lay.addWidget(self.make_lbl("🎨 품종"), 0, 2); input_lay.addWidget(self.sel_variety, 0, 3)
        input_lay.addWidget(self.make_lbl("🎖️ 등급"), 0, 4); input_lay.addWidget(self.sel_grade, 0, 5)
        input_lay.addWidget(self.make_lbl("📏 크기"), 1, 0); input_lay.addWidget(self.sel_size, 1, 1)
        input_lay.addWidget(self.make_lbl("⚖️ 중량"), 1, 2); input_lay.addWidget(self.sel_weight, 1, 3)
        input_lay.addWidget(self.make_lbl("💰 단가"), 1, 4); input_lay.addWidget(self.edit_unit_price, 1, 5)
        input_lay.addWidget(self.btn_add_price, 2, 0, 1, 6)
        
        main_layout.addWidget(input_group)

        # ---------------------------------------------------------------------
        # [3단] 목록 관리 구역 (📍 한글 "삭제" 버튼 및 중앙 정렬)
        # ---------------------------------------------------------------------
        self.table = QTableWidget(0, 10)
        self.table.setStyleSheet(MainStyles.TABLE)
        self.table.setHorizontalHeaderLabels([
            "년산", "품목", "품종", "등급", "크기", "중량", "단가", "배송비", "관리", "ID"
        ])
        
        # 컬럼 너비 최적화 (총 800px 대응)
        self.table.setColumnWidth(0, 70); self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 90); self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 75); self.table.setColumnWidth(5, 75)
        self.table.setColumnWidth(6, 90); self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 40) # 📍 삭제 버튼용
        self.table.setColumnHidden(9, True)
        self.table.horizontalHeader().setStretchLastSection(True) 
        
        main_layout.addWidget(self.table)

        self.btn_final_save = QPushButton("💾 단가표 전체 내용 DB 저장")
        self.btn_final_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_final_save.setFixedHeight(45)
        self.btn_final_save.clicked.connect(self.save_to_db)
        main_layout.addWidget(self.btn_final_save)

    # ---------------------------------------------------------------------
    # [📍 핵심 구현 로직]
    # ---------------------------------------------------------------------

    def setup_combos(self):
        """[Initialize] 모든 콤보박스 기초 데이터 주입"""
        self.load_code_to_combo(self.sel_season, "SS01") # 시즌 (1단)
        self.load_code_to_combo(self.sel_item, "FR01")   # 품목 (2단)
        self.sel_item.currentIndexChanged.connect(self.update_sub_combos)
        self.update_sub_combos()

    def set_initial_filters(self):
        """[Initialize] 초기 필터값 세팅"""
        self.sel_sales_year.setValue(int(self.init_sales_year))
        self.sel_harvest_year.setValue(int(self.init_harvest_year))
        
        idx = self.sel_season.findData(self.init_season_cd)
        if idx >= 0: self.sel_season.setCurrentIndex(idx)

    def format_price_input(self):
        """[2단 로직] 단가 입력 시 #,### 포맷 실시간 적용"""
        text = self.edit_unit_price.text().replace(",", "")
        if text.isdigit():
            formatted = f"{int(text):,}"
            self.edit_unit_price.blockSignals(True)
            self.edit_unit_price.setText(formatted)
            self.edit_unit_price.blockSignals(False)

    def update_sub_combos(self):
        """[2단 로직] 품목 변경 시 품종/등급/중량 동적 업데이트"""
        self.sel_variety.clear(); self.sel_grade.clear()
        self.sel_size.clear(); self.sel_weight.clear()
        
        item_cd = self.sel_item.currentData()
        if not item_cd: return

        # 품종 로드
        for v in self.codes.get_common_codes(item_cd):
            d = dict(v); self.sel_variety.addItem(d.get('code_nm'), d.get('code_cd'))

        # 배(FR010100) vs 기타(배즙 등) 분기 로직
        if item_cd == 'FR010100':
            for g in self.codes.get_common_codes('GR01'):
                d = dict(g); self.sel_grade.addItem(d.get('code_nm'), d.get('code_cd'))
            for s in self.codes.get_common_codes('FR020100'):
                d = dict(s); self.sel_size.addItem(d.get('code_nm'), d.get('code_cd'))
            for w in [x for x in self.codes.get_common_codes('SZ01') if 'kg' in x['code_nm']]:
                d = dict(w); self.sel_weight.addItem(d.get('code_nm'), d.get('code_cd'))
        else:
            self.sel_grade.addItem("-", "GR010100")
            for s in [x for x in self.codes.get_common_codes('SZ01') if '포' in x['code_nm']]:
                d = dict(s); self.sel_size.addItem(d.get('code_nm'), d.get('code_cd'))
                self.sel_weight.addItem(d.get('code_nm'), d.get('code_cd'))

    def add_item_row_action(self):
        """[2단 로직] 추가 버튼 클릭 시 테이블에 데이터 추가"""
        price_str = self.edit_unit_price.text().replace(",", "")
        price_val = int(price_str) if price_str.isdigit() else 0
        if price_val <= 0:
            QMessageBox.warning(self, "알림", "단가를 입력하십시오.")
            return
        
        self.add_item_row(harvest_year=self.sel_harvest_year.value(), price=price_val)

    def add_item_row(self, harvest_year=None, item_cd=None, variety_cd=None, grade_cd=None, size_cd=None, weight=None, price=0, ship_fee=5000, is_load=False):
        """[3단 로직] 테이블 행 추가 및 📍삭제 버튼(한글/중앙) 구성"""
        p_year = harvest_year
        if is_load:
            # 📍 get_code_name() 대신 code_manager 로직 활용 (가정: codes가 DB 조회를 대행)
            i_nm = self.get_name_from_codes(item_cd)
            v_nm = self.get_name_from_codes(variety_cd)
            g_nm = self.get_name_from_codes(grade_cd)
            s_nm = self.get_name_from_codes(size_cd)
            w_val = weight
            w_nm = f"{weight}kg" if "FR0101" in str(item_cd) else f"{weight}포"
            i_cd, v_cd, g_cd, s_cd = item_cd, variety_cd, grade_cd, size_cd
        else:
            i_nm, i_cd = self.sel_item.currentText(), self.sel_item.currentData()
            v_nm, v_cd = self.sel_variety.currentText(), self.sel_variety.currentData()
            g_nm, g_cd = self.sel_grade.currentText(), self.sel_grade.currentData()
            s_nm, s_cd = self.sel_size.currentText(), self.sel_size.currentData()
            w_nm = self.sel_weight.currentText()
            w_match = re.findall(r"[-+]?\d*\.\d+|\d+", w_nm)
            w_val = float(w_match[0]) if w_match else 0.0

        code_bundle = f"{p_year}|{i_cd}|{v_cd}|{g_cd}|{s_cd}|{w_val}"
        for r in range(self.table.rowCount()):
            if self.table.item(r, 9).text() == code_bundle: return

        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 텍스트 데이터 배치 (중앙 정렬)
        data = [f"{p_year}년산", i_nm, v_nm, g_nm, s_nm, w_nm]
        for col, txt in enumerate(data):
            it = QTableWidgetItem(txt); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, it)

        # 금액 데이터 배치 (우측 정렬)
        for col, val in [(6, price), (7, ship_fee)]:
            it = QTableWidgetItem(f"{int(val):,}")
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, col, it)

        # 📍 삭제 버튼 (MainStyles.BTN_DANGER 규격)
        btn_del = QPushButton("삭제")
        btn_del.setStyleSheet(MainStyles.BTN_DANGER)
        btn_del.setFixedSize(50, 24)
        btn_del.clicked.connect(self.delete_price_row)
        
        container = QWidget()
        c_lay = QHBoxLayout(container)
        c_lay.addWidget(btn_del); c_lay.setContentsMargins(0, 0, 0, 0); c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 8, container)
        self.table.setItem(row, 9, QTableWidgetItem(code_bundle))

    def get_name_from_codes(self, code_cd):
        """[📍삭제 대체] code_manager의 DB 접근 능력을 활용하여 명칭 조회"""
        sql = "SELECT code_nm FROM m_common_code WHERE farm_cd = ? AND code_cd = ?"
        res = self.db.execute_query(sql, (self.farm_cd, code_cd))
        return dict(res[0]).get('code_nm', code_cd) if res else code_cd

    # 단가 조회
    def load_existing_prices(self):
        """[📍삼각 조회] 시즌 + 판매년도 + 생산년도 기준 조회"""
        sales_y = self.sel_sales_year.value()
        prod_y = self.sel_harvest_year.value()
        season_cd = self.sel_season.currentData()
        if not season_cd: return

        self.table.setRowCount(0)
        sql = """
            SELECT * FROM m_item_unit_price 
            WHERE farm_cd = ? AND sales_year = ? AND harvest_year = ? AND season_cd = ?
        """
        res = self.db.execute_query(sql, (self.farm_cd, str(sales_y), str(prod_y), season_cd))
        for r in res:
            row = dict(r)
            self.add_item_row(
                harvest_year=prod_y, item_cd=row['item_cd'], variety_cd=row['variety_cd'], 
                grade_cd=row['grade_cd'], size_cd=row['size_cd'], weight=row['weight'], 
                price=row['unit_price'], ship_fee=row['base_ship_fee'], is_load=True
            )

    # 단가 삭제 로직
    def delete_price_row(self):
        """
        [3단 로직] 테이블 행 삭제 핸들러
        - 클릭된 버튼의 위치를 계산하여 테이블의 정확한 Row Index를 찾아 삭제합니다.
        """
        button = self.sender() # 클릭된 버튼 객체를 가져옵니다.
        if button:
            # 버튼이 들어있는 컨테이너(QWidget)의 위치를 기반으로 테이블의 인덱스를 찾습니다.
            # 버튼 -> 레이아웃 -> 컨테이너 구조이므로 parent()를 호출합니다.
            container = button.parentWidget()
            
            # 테이블 내에서 해당 컨테이너가 위치한 지점의 인덱스를 추출합니다.
            index = self.table.indexAt(container.pos())
            
            if index.isValid():
                row_to_remove = index.row()
                self.table.removeRow(row_to_remove)

    def save_to_db(self):
        """
        [Persistence] 트랜잭션 기반 DB 동기화
        - 📍 전략: 현재 조건의 데이터를 DELETE 후 일괄 INSERT
        - 📍 무결성: 전체 작업 성공 시 COMMIT, 실패 시 ROLLBACK
        """
        try:
            # 1. 기준 정보 확보
            sales_y = self.sel_sales_year.value()
            prod_y = self.sel_harvest_year.value()
            season_cd = self.sel_season.currentData()

            if not season_cd:
                QMessageBox.warning(self, "알림", "시즌 코드가 올바르지 않아 지휘를 중단합니다.")
                return

            # -----------------------------------------------------------------
            # 📍 [Step 1] 트랜잭션 작전 개시 (BEGIN)
            # -----------------------------------------------------------------
            # DB 커넥션을 통해 수동으로 트랜잭션을 제어합니다.
            self.db.execute_query("BEGIN TRANSACTION")

            # 2. 기존 데이터 일괄 삭제 (삭제 반영의 핵심)
            delete_sql = """
                DELETE FROM m_item_unit_price 
                WHERE farm_cd = ? 
                  AND sales_year = ? 
                  AND harvest_year = ? 
                  AND season_cd = ?
            """
            self.db.execute_query(delete_sql, (self.farm_cd, str(sales_y), str(prod_y), season_cd))

            # 3. 테이블 데이터 순회하며 삽입
            for r in range(self.table.rowCount()):
                # 9번 컬럼(Hidden) 코드뭉치 추출: 생산년도|품목|품종|등급|사이즈|중량
                code_bundle = self.table.item(r, 9).text().split('|')
                
                # 금액 정보 (#,### 제거 후 정수 변환)
                u_price = int(str(self.table.item(r, 6).text()).replace(',', ''))
                s_fee = int(str(self.table.item(r, 7).text()).replace(',', ''))
                w_val = float(code_bundle[5]) # 중량값

                insert_sql = """
                    INSERT INTO m_item_unit_price (
                        farm_cd, sales_year, harvest_year, season_cd, 
                        item_cd, variety_cd, grade_cd, size_cd, weight,
                        unit_price, base_ship_fee, reg_dt
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))
                """
                params = (
                    self.farm_cd, sales_y, code_bundle[0], season_cd, 
                    code_bundle[1], code_bundle[2], code_bundle[3], code_bundle[4], 
                    w_val, u_price, s_fee
                )
                self.db.execute_query(insert_sql, params)

            # -----------------------------------------------------------------
            # 📍 [Step 2] 모든 공정 성공 - 최종 승인 (COMMIT)
            # -----------------------------------------------------------------
            self.db.execute_query("COMMIT")
            
            QMessageBox.information(self, "성공", "모든 데이터가 안전하게 저장 되었습니다.")
            self.accept()

        except Exception as e:
            # -----------------------------------------------------------------
            # 📍 [Step 3] 비상 사태 발생 - 작전 취소 (ROLLBACK)
            # -----------------------------------------------------------------
            # 에러 발생 시 지금까지의 DELETE/INSERT 과정을 모두 되돌려 DB를 보호합니다.
            self.db.execute_query("ROLLBACK")
            
            error_msg = f"저장 중 오류가 발생하여 모든 변경사항을 Rollback 했습니다.\n사유: {str(e)}"
            QMessageBox.critical(self, "무결성 오류", error_msg)

    def load_code_to_combo(self, combo, parent_cd):
        combo.clear()
        for row in self.codes.get_common_codes(parent_cd):
            d = dict(row); combo.addItem(d.get('code_nm'), d.get('code_cd'))

    def make_lbl(self, text):
        l = QLabel(text); l.setStyleSheet(MainStyles.TXT_LABEL_BOLD); return l

# [메인 페이지] 주문 관리
class OrderManagementPage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        # 1. 기초 엔진 및 세션
        self.db = db_manager
        self.session = session
        self.farm_cd = self.session.get('farm_cd')
        self.user_id = self.session.get('user_id')
        self.code_manager = CodeManager(self.db, self.farm_cd)
        self.is_loaded = True
        
        # 2. 레이아웃 제원 및 상태
        self.left_width = 750
        self.right_width = 850
        self._left_visible = False
        self._right_visible = False
        self._ui_ready = False
        self.current_order_no = None

        # 3. 오버레이 패널 선행 생성 (Z-Order 확보)
        self.left_panel = QFrame(self)
        self.left_panel.setFixedWidth(self.left_width)
        self.left_panel.setStyleSheet(MainStyles.CARD + "border-right: 3px solid #2E7D32; border-radius: 0px;")
        
        self.right_panel = QFrame(self)
        self.right_panel.setFixedWidth(self.right_width)
        self.right_panel.setStyleSheet(MainStyles.CARD + "border-left: 2px solid #EAE7E2; border-radius: 0px;")

        # 4. 애니메이션 객체
        self.left_anim = QPropertyAnimation(self.left_panel, b"pos")
        self.right_anim = QPropertyAnimation(self.right_panel, b"pos")
        for anim in [self.left_anim, self.right_anim]:
            anim.setDuration(350)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.init_ui()
        self._ui_ready = True

        # 2. [📍 핵심] 센터패널 콤보호출
        # UI가 모두 생성된 직후에 호출해야 에러가 없습니다.
        self.init_page_data()

    def init_ui(self):
        """[📍시스템 통합] 3단 지휘소 레이아웃 엔진 가동"""
        # (A) 중앙 상시 작업 패널 (New Order / Detail Edit)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.center_panel = QFrame()
        self.center_panel.setStyleSheet(MainStyles.MAIN_BG)
        self.setup_center_panel()
        self.main_layout.addWidget(self.center_panel)

        # (B) 좌/우 오버레이 UI 구성
        self.setup_left_panel()
        self.setup_right_panel()

        # (C) 엣지 핸들 설정
        self.btn_left_handle = QPushButton(">", self)
        self.btn_left_handle.setFixedSize(20, 100)
        self.btn_left_handle.setStyleSheet(MainStyles.EDGE_HANDLE)
        self.btn_left_handle.clicked.connect(lambda: self.toggle_panel("LEFT"))

        self.btn_right_handle = QPushButton("<", self)
        self.btn_right_handle.setFixedSize(20, 100)
        self.btn_right_handle.setStyleSheet(MainStyles.EDGE_HANDLE)
        self.btn_right_handle.clicked.connect(lambda: self.toggle_panel("RIGHT"))

        # 최상단 정렬
        for w in [self.left_panel, self.right_panel, self.btn_left_handle, self.btn_right_handle]:
            w.raise_()

        # 초기 배치 강제 실행
        self.update_geometries()

    # [1] 좌측 주문마스터 관리하기 불러오기
    def setup_left_panel(self):
        """[Master] 좌측 주문 목록 및 필터링 섹션"""
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 1. 상단 필터 박스 (3단 구조)
        filter_box = QFrame()
        filter_box.setStyleSheet(MainStyles.CARD)
        f_lay = QGridLayout(filter_box)
        f_lay.setContentsMargins(15, 15, 15, 15)
        f_lay.setVerticalSpacing(10)

        # 스타일 헬퍼
        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(MainStyles.TXT_LABEL_BOLD)
            return l

        # 1단: 고객/연락처
        f_lay.addWidget(_lbl("👤 고객명"), 0, 0)
        self.search_cust_nm = QLineEdit(); self.search_cust_nm.setStyleSheet(MainStyles.INPUT_LEFT)
        f_lay.addWidget(self.search_cust_nm, 0, 1)
        f_lay.addWidget(_lbl("📞 연락처"), 0, 2)
        self.search_tel = QLineEdit(); self.search_tel.setStyleSheet(MainStyles.INPUT_LEFT)
        f_lay.addWidget(self.search_tel, 0, 3)

        # 2단: 상태/시즌 (CodeManager 연동)
        f_lay.addWidget(_lbl("📌 상태"), 1, 0)
        self.combo_status_filter = QComboBox(); self.combo_status_filter.setStyleSheet(MainStyles.COMBO)
        self.combo_status_filter.addItem("전체상태", "")
        for item in self.code_manager.get_common_codes('ST01'):
            self.combo_status_filter.addItem(item['code_nm'], item['code_cd'])
        f_lay.addWidget(self.combo_status_filter, 1, 1)

        f_lay.addWidget(_lbl("🍂 시즌"), 1, 2)
        self.combo_season_filter = QComboBox(); self.combo_season_filter.setStyleSheet(MainStyles.COMBO)
        self.combo_season_filter.addItem("전체시즌", "")
        for item in self.code_manager.get_common_codes('SS01'):
            self.combo_season_filter.addItem(item['code_nm'], item['code_cd'])
        f_lay.addWidget(self.combo_season_filter, 1, 3)

        # 3단: 처리 버튼
        btn_lay = QHBoxLayout()
        self.btn_batch_confirm = QPushButton("✅ 일괄확정"); self.btn_batch_confirm.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_batch_cancel = QPushButton("❌ 일괄취소"); self.btn_batch_cancel.setStyleSheet(MainStyles.BTN_DANGER)
        self.btn_master_search = QPushButton("🔍 주문조회"); self.btn_master_search.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_master_search.setFixedWidth(120)
        self.btn_master_search.clicked.connect(self.load_master_list) # 아직 미생성

        btn_lay.addWidget(self.btn_batch_confirm); btn_lay.addWidget(self.btn_batch_cancel); btn_lay.addStretch()
        btn_lay.addWidget(self.btn_master_search)
        f_lay.addLayout(btn_lay, 2, 0, 1, 4)
        
        layout.addWidget(filter_box)

        # 2. 마스터 목록 테이블
        self.table_order_master = QTableWidget()
        self.table_order_master.setColumnCount(7)
        self.table_order_master.setHorizontalHeaderLabels(["선택", "시즌정보", "주문자명", "주문일자", "판매금액", "배송비", "미수금액"])
        self.table_order_master.setStyleSheet(MainStyles.TABLE)
        
        # 헤더 설정
        h = self.table_order_master.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table_order_master.setColumnWidth(0, 40); self.table_order_master.setColumnWidth(1, 100)
        self.table_order_master.setColumnWidth(2, 120); self.table_order_master.setColumnWidth(3, 100)
        self.table_order_master.setColumnWidth(4, 100); self.table_order_master.setColumnWidth(5, 80)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        
        self.table_order_master.verticalHeader().setVisible(False)
        self.table_order_master.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_order_master.cellClicked.connect(self.on_master_selected)
        layout.addWidget(self.table_order_master)

        self.lbl_master_count = QLabel("조회 결과: 0건")
        self.lbl_master_count.setStyleSheet(MainStyles.DASH_LABEL)
        layout.addWidget(self.lbl_master_count)

    def load_master_list(self):
        """[Master] DB에서 주문 목록을 읽어와 테이블에 출력 (미수금 실시간 연산)"""
        sql = """
            SELECT m.order_no, m.order_dt, m.tot_order_amt, m.tot_ship_fee, m.tot_pay_amt, m.season_type_cd,
                   c.custm_nm,
                   (SELECT code_nm FROM m_common_code WHERE parent_cd = 'SS01' AND code_cd = m.season_type_cd) as season_nm
            FROM t_order_master m
            LEFT JOIN m_customer c ON m.custm_id = c.custm_id
            WHERE m.farm_cd = ?
        """
        params = [self.farm_cd]

        # 필터링 적용
        if self.search_cust_nm.text():
            sql += " AND c.custm_nm LIKE ?"; params.append(f"%{self.search_cust_nm.text()}%")
        if self.search_tel.text():
            sql += " AND (c.mobile LIKE ? OR c.tel LIKE ?)"; params.extend([f"%{self.search_tel.text()}%", f"%{self.search_tel.text()}%"])
        if self.combo_status_filter.currentData():
            sql += " AND m.status_cd = ?"; params.append(self.combo_status_filter.currentData())
        if self.combo_season_filter.currentData():
            sql += " AND m.season_type_cd = ?"; params.append(self.combo_season_filter.currentData())
        
        sql += " ORDER BY m.order_dt DESC, m.reg_dt DESC"

        try:
            rows = self.db.fetch_all(sql, tuple(params))
            self.table_order_master.setRowCount(0)
            
            for i, row_raw in enumerate(rows):
                row = dict(row_raw) # sqlite3.Row -> dict 안전 변환
                self.table_order_master.insertRow(i)

                # 선택 체크박스
                chk_box = QCheckBox()
                chk_widget = QWidget(); chk_lay = QHBoxLayout(chk_widget); chk_lay.addWidget(chk_box)
                chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter); chk_lay.setContentsMargins(0,0,0,0)
                self.table_order_master.setCellWidget(i, 0, chk_widget)

                # 데이터 아이템 생성 헬퍼
                def _it(text, align='center', is_red=False):
                    it = QTableWidgetItem(str(text if text is not None else ""))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter if align == 'center' else Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if is_red: it.setForeground(QBrush(QColor("#E53E3E")))
                    return it

                # 미수금 계산: (금액 + 배송비) - 입금액
                tot_order = row.get('tot_order_amt', 0)
                tot_ship = row.get('tot_ship_fee', 0)
                tot_pay = row.get('tot_pay_amt', 0)
                balance = int(tot_order + tot_ship - tot_pay)

                self.table_order_master.setItem(i, 1, _it(row.get('season_nm', '일반')))
                
                # 주문자명에 주문번호 UserRole 저장
                name_item = _it(row.get('custm_nm', '미등록'))
                name_item.setData(Qt.ItemDataRole.UserRole, row.get('order_no'))
                self.table_order_master.setItem(i, 2, name_item)
                
                self.table_order_master.setItem(i, 3, _it(row.get('order_dt')))
                self.table_order_master.setItem(i, 4, _it(f"{int(tot_order):,}", 'right'))
                self.table_order_master.setItem(i, 5, _it(f"{int(tot_ship):,}", 'right'))
                
                # 미수금이 있으면 빨간색 표시
                self.table_order_master.setItem(i, 6, _it(f"{balance:,}", 'right', is_red=(balance > 0)))

            self.lbl_master_count.setText(f"조회 결과: {len(rows)}건")
            
        except Exception as e:
            QMessageBox.critical(self, "조회 에러", f"목록을 불러오지 못했습니다: {str(e)}")

    # [2] 센터판넬 마스터용 코드  로드

    def init_page_data(self):
        """
        [Initialize] 페이지 데이터 초기화 엔진
        - 1단계 마스터용 공통 코드 로드
        - 브릿지 영역 품목/품종 초기화 및 시그널 연결
        """
        # 1. 1단계 마스터 콤보박스 채우기
        # 주문상태 (ST01: 예약접수, 예약확정, 취소 등)
        self.load_code_to_combo(self.detail_status_cd, "ST01")
        
        # 시즌코드 (SS01: 설날, 추석, 일반 등)
        self.load_code_to_combo(self.detail_season_type_cd, "SS01")

        # 2. 브릿지 영역 콤보박스 채우기
        # 판매품목 (FR01: 배, 배즙, 원물 등)
        self.load_code_to_combo(self.bridge_item_cd, "FR01")
        
        # 3. [📍동적 연동] 품목이 변경되면 품종이 자동으로 바뀌도록 연결
        self.bridge_item_cd.currentIndexChanged.connect(self.on_bridge_item_changed)
        
        # 4. 최초 실행 시 첫 번째 품목에 대한 품종 로드 강제 실행
        self.on_bridge_item_changed()

    def on_bridge_item_changed(self):
        """
        [Bridge Logic] 품목 선택 변경 시 호출되는 이벤트 핸들러
        - 현재 선택된 품목 코드(예: FR010100)를 부모로 하는 하위 코드를 품종 콤보에 로드
        """
        # 현재 선택된 품목의 코드값(UserData)을 가져옴
        current_item_cd = self.bridge_item_cd.currentData()
        
        # 품종 콤보박스 초기화 후 해당 품목의 하위 코드 로드
        if current_item_cd:
            self.load_code_to_combo(self.bridge_variety_cd, current_item_cd)
        else:
            self.bridge_variety_cd.clear()

    # [EVENT] 마스터 목록 클릭 이벤트
    def on_master_selected(self, row, col):
        """좌측 목록 클릭 시 주문번호를 추출하여 전체 데이터를 로드합니다."""
        item = self.table_order_master.item(row, 2) # 주문자명(UserRole에 order_no 저장됨)
        if not item: return
        
        order_no = item.data(Qt.ItemDataRole.UserRole)
        if not order_no: return
        
        # 1. 데이터 로드 실행
        self.load_order_all_data(order_no)
        
        # 2. 대표님의 규칙: 선택 시 좌측 판넬은 닫고 중앙 작업에 집중
        self.close_left_panel()

    # [DATA] 통합 데이터 로딩 엔진
    def load_order_all_data(self, order_no):
        """
        [📍아토스 프로 버전] 모듈형 부품 조립 및 정합성 완벽 보장
        - 이벤트 핸들러 오용 금지 / 검증된 자체 UI 컴포넌트(메소드) 활용
        - 과거 장부의 암호(Code)를 명확한 한글(Name)로 변환
        - 수정(Update)을 위한 원본 PK 은닉 및 콤보박스 이벤트 재연결
        """
        self.current_order_no = order_no
        self.is_new_order_mode = False # 📍 기존 데이터 수정 모드임을 시스템에 각인
        
        try:
            # ==========================================================
            # 1. 마스터 정보 (t_order_master) 복원 (기존 로직 유지)
            # ==========================================================
            sql_m = """
                SELECT m.*, c.custm_nm, c.mobile 
                FROM t_order_master m 
                LEFT JOIN m_customer c ON m.custm_id = c.custm_id 
                WHERE m.order_no = ?
            """
            res_m = self.db.execute_query(sql_m, (order_no,))
            
            if res_m:
                m = dict(res_m[0])
                self.current_cust_id = str(m.get('custm_id', 'GUEST'))
                self.detail_cust_nm.setText(str(m.get('custm_nm') or ""))
                self.detail_cust_tel.setText(str(m.get('mobile') or ""))
                
                dt_str = str(m.get('order_dt'))
                if len(dt_str) == 8: dt_str = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:]}"
                self.detail_order_dt.setDate(QDate.fromString(dt_str, "yyyy-MM-dd"))
                
                tot = m.get('tot_order_amt', 0); ship = m.get('tot_ship_fee', 0); pre = m.get('pre_pay_amt', 0)
                self.detail_tot_order_amt.setText(f"{int(tot):,}")
                self.detail_tot_ship_fee.setText(f"{int(ship):,}")
                self.detail_pre_pay_amt.setText(f"{int(pre):,}")
                self.detail_balance_lbl.setText(f"{int(tot + ship - pre):,}")
                
                self.set_combo_by_data(self.detail_status_cd, m.get('status_cd'))
                self.set_combo_by_data(self.detail_season_type_cd, m.get('season_type_cd'))
                self.detail_rmk.setText(str(m.get('rmk') or ""))

            # ==========================================================
            # 2. 상세 내역 (t_order_detail) 복원 및 UI 컴포넌트 결합
            # ==========================================================
            self.table_order_detail.blockSignals(True) # 📍 복원 중 무한루프 방지
            self.table_order_detail.setRowCount(0)
            
            sql_d = "SELECT * FROM t_order_detail WHERE order_no = ?"
            d_rows = self.db.execute_query(sql_d, (order_no,))
            
            for i, d in enumerate(d_rows):
                d = dict(d)
                self.table_order_detail.insertRow(i)
                
                # 📍 [핵심 1] code_manager를 활용한 우아한 명칭 변환
                v_nm = self.code_manager.get_code_nm(d['variety_cd'])
                g_nm = self.code_manager.get_code_nm(d['grade_cd'])
                s_nm = self.code_manager.get_code_nm(d['size_cd'])
                wh_nm = self.code_manager.get_code_nm(d['wh_cd']) if d['wh_cd'] else "본사창고"

                # 기본 데이터 세팅
                self.table_order_detail.setItem(i, 0, QTableWidgetItem(str(d['harvest_year'])))
                self.table_order_detail.setItem(i, 1, QTableWidgetItem(f"{d['weight']}kg" if "FR0101" in str(d['item_cd']) else f"{d['weight']}포"))
                self.table_order_detail.setItem(i, 2, QTableWidgetItem(v_nm))
                self.table_order_detail.setItem(i, 3, QTableWidgetItem(g_nm))
                self.table_order_detail.setItem(i, 4, QTableWidgetItem(s_nm))

                # 수량, 단가, 합계 우측 정렬 세팅
                def _set_right(col, val):
                    it = QTableWidgetItem(f"{int(val):,}")
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table_order_detail.setItem(i, col, it)

                _set_right(5, d['qty'])
                _set_right(6, d['unit_price'])
                _set_right(7, d['item_amt'])
                
                # 📍 [안전장치] 배송비 복원 (택배일 경우 단가테이블에서 base_fee를 찾아 계산)
                fee_sql = "SELECT base_ship_fee FROM m_item_unit_price WHERE farm_cd=? AND harvest_year=? AND item_cd=? AND variety_cd=? AND grade_cd=? AND size_cd=?"
                fee_res = self.db.execute_query(fee_sql, (self.farm_cd, d['harvest_year'], d['item_cd'], d['variety_cd'], d['grade_cd'], d['size_cd']))
                base_fee = dict(fee_res[0])['base_ship_fee'] if fee_res else 5000
                
                curr_fee = int(d['qty']) * base_fee if d['dlvry_tp'] == 'LO010200' else 0
                _set_right(8, curr_fee)
                
                self.table_order_detail.setItem(i, 9, QTableWidgetItem(wh_nm))
                self.table_order_detail.item(i, 9).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # 📍 [핵심 2] 기존 콤보박스 식립 메소드 재활용 및 시그널 재연결
                combo = self.set_table_combo(self.table_order_detail, i, 10, 'LO01', default_val=d['dlvry_tp'])
                combo.setProperty("row", i)
                combo.setProperty("base_fee", base_fee) # 수정 시 배송비 재계산을 위한 필수 속성
                combo.currentIndexChanged.connect(self.handle_shipping_method_change)
                combo.currentIndexChanged.connect(self.update_delivery_target_combo)

                # 📍 [핵심 3] 기존 삭제 버튼 식립 메소드 재활용
                self.insert_delete_button(i, 11)

                # 📍 [핵심 4] 수정을 위한 비밀 주머니 세팅 (12번, 13번 컬럼)
                bundle = f"{d['item_cd']}|{d['variety_cd']}|{d['grade_cd']}|{d['size_cd']}|{d.get('wh_cd', 'WH01')}"
                self.table_order_detail.setItem(i, 12, QTableWidgetItem(bundle))
                
                # 13번 컬럼에 원래의 DB PK (order_detail_id) 저장
                self.table_order_detail.setItem(i, 13, QTableWidgetItem(str(d['order_detail_id'])))
                # 0번 컬럼 UserRole에도 이중 은닉 (확실한 추적용)
                self.table_order_detail.item(i, 0).setData(Qt.ItemDataRole.UserRole, str(d['order_detail_id']))

            self.table_order_detail.blockSignals(False) # 시그널 봉쇄 해제

            # ==========================================================
            # 3. 배송 계획 (t_order_delivery) 복원
            # ==========================================================
            self.table_delivery_plan.setRowCount(0)
            sql_v = "SELECT * FROM t_order_delivery WHERE order_no = ?"
            v_rows = self.db.execute_query(sql_v, (order_no,))
            for v in v_rows:
                # 📍 기존의 안전한 add_delivery_plan_row 재활용
                self.add_delivery_plan_row(dict(v))

            # 4. 마무리 UI 동기화 (우측 콤보박스 최신화)
            self.update_delivery_target_combo()

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "데이터 연동 오류", f"사유: {str(e)}")

    def set_combo_by_data(self, combo, data):
        """[Helper] 콤보박스 내부 데이터값으로 인덱스 찾기"""
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # [2] 중앙 신규 주문 등록하기
    def setup_center_panel(self):
        """
        [Center] 주문 상세 지휘부 UI 초기화
        - 📍 수정사항: 조회 버튼 우측에 '신규주문' 버튼 추가 및 컬럼 명칭 최적화
        """
        layout = QVBoxLayout(self.center_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ---------------------------------------------------------------------
        # [0단계] 최상단 액션 바 (신규 추가)
        # ---------------------------------------------------------------------
        top_action_lay = QHBoxLayout()
        
        self.btn_search_existing = QPushButton("🔍 기존주문조회")
        self.btn_search_existing.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_search_existing.setFixedWidth(130)
        self.btn_search_existing.setFixedHeight(35)
        # 📍 기존 주문 판넬(왼쪽)을 열어주는 역할
        self.btn_search_existing.clicked.connect(lambda: self.toggle_panel("LEFT"))

        self.btn_register_new = QPushButton("✨ 신규주문등록")
        self.btn_register_new.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_register_new.setFixedWidth(130)
        self.btn_register_new.setFixedHeight(35)
        # 📍 신규 주문 모드 진입 로직 연결
        self.btn_register_new.clicked.connect(self.initiate_new_order)

        top_action_lay.addWidget(self.btn_search_existing)
        top_action_lay.addWidget(self.btn_register_new)
        top_action_lay.addStretch() # 우측 여백 확보
        
        layout.addLayout(top_action_lay) # 주문고객 정보 위로 배치

        # ---------------------------------------------------------------------
        # [1단계] 주문 마스터 및 정산 정보 (4x3 균등 배치)
        # ---------------------------------------------------------------------
        master_group = QGroupBox("📋 1단계: 주문 마스터 및 정산 정보")
        master_group.setStyleSheet(MainStyles.GROUP_BOX)
        
        master_layout = QGridLayout(master_group)
        master_layout.setContentsMargins(15, 25, 15, 15)
        master_layout.setSpacing(12)

        master_layout.setColumnStretch(1, 1)
        master_layout.setColumnStretch(3, 1)
        master_layout.setColumnStretch(5, 1)
        master_layout.setColumnStretch(7, 1)

        # --- [1행: 기본 주문 정보] ---
        lbl_cust = QLabel("주문고객")
        lbl_cust.setStyleSheet(MainStyles.TXT_LABEL_BOLD)
        self.detail_cust_nm = QLineEdit()
        self.detail_cust_nm.setStyleSheet(MainStyles.INPUT_LEFT)
        self.detail_cust_nm.setPlaceholderText("고객명 검색...")

        # 🔍 조회 버튼
        self.btn_cust_search = QPushButton("고객조회")
        self.btn_cust_search.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_cust_search.setFixedWidth(92)
        self.btn_cust_search.clicked.connect(self.open_customer_search_popup)
        
        h_cust_box = QHBoxLayout()
        h_cust_box.addWidget(self.detail_cust_nm)
        h_cust_box.addWidget(self.btn_cust_search)
        
        # 연락처 / 주문일자 / 주문상태
        self.detail_cust_tel = QLineEdit()
        self.detail_cust_tel.setStyleSheet(MainStyles.INPUT_LEFT)
        self.detail_order_dt = QDateEdit(QDate.currentDate())
        self.detail_order_dt.setCalendarPopup(True)
        self.detail_order_dt.setStyleSheet(MainStyles.DATE_EDIT)
        self.detail_status_cd = QComboBox()
        self.detail_status_cd.setStyleSheet(MainStyles.COMBO)

        master_layout.addWidget(lbl_cust, 0, 0)
        master_layout.addLayout(h_cust_box, 0, 1)
        master_layout.addWidget(self.make_lbl("연락처"), 0, 2)
        master_layout.addWidget(self.detail_cust_tel, 0, 3)
        master_layout.addWidget(self.make_lbl("주문일자"), 0, 4)
        master_layout.addWidget(self.detail_order_dt, 0, 5)
        master_layout.addWidget(self.make_lbl("주문상태"), 0, 6)
        master_layout.addWidget(self.detail_status_cd, 0, 7)

        # --- [2행: 정산 정보] ---
        self.detail_tot_order_amt = QLineEdit("0")
        self.detail_tot_order_amt.setStyleSheet(MainStyles.INPUT_RIGHT)
        self.detail_tot_ship_fee = QLineEdit("0")
        self.detail_tot_ship_fee.setStyleSheet(MainStyles.INPUT_RIGHT)
        self.detail_pre_pay_amt = QLineEdit("0")
        self.detail_pre_pay_amt.setStyleSheet(MainStyles.INPUT_RIGHT)
        self.detail_balance_lbl = QLabel("0")
        self.detail_balance_lbl.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH + " qproperty-alignment: 'AlignRight'; color: #E53E3E; padding-right: 5px;")
        self.detail_balance_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        master_layout.addWidget(self.make_lbl("총주문금액"), 1, 0)
        master_layout.addWidget(self.detail_tot_order_amt, 1, 1)
        master_layout.addWidget(self.make_lbl("총배송비"), 1, 2)
        master_layout.addWidget(self.detail_tot_ship_fee, 1, 3)
        master_layout.addWidget(self.make_lbl("입금액"), 1, 4)
        master_layout.addWidget(self.detail_pre_pay_amt, 1, 5)
        master_layout.addWidget(self.make_lbl("미수금"), 1, 6)
        master_layout.addWidget(self.detail_balance_lbl, 1, 7)

        # --- [3행: 기타 및 비고] ---
        self.detail_stock_status = QLabel("미처리")
        self.detail_stock_status.setStyleSheet(MainStyles.LBL_TEXT_LEFT_LIGHT)
        self.detail_season_type_cd = QComboBox()
        self.detail_season_type_cd.setStyleSheet(MainStyles.COMBO)
        self.detail_rmk = QLineEdit()
        self.detail_rmk.setStyleSheet(MainStyles.INPUT_LEFT)

        master_layout.addWidget(self.make_lbl("재고현황"), 2, 0)
        master_layout.addWidget(self.detail_stock_status, 2, 1)
        master_layout.addWidget(self.make_lbl("시즌코드"), 2, 2)
        master_layout.addWidget(self.detail_season_type_cd, 2, 3)
        master_layout.addWidget(self.make_lbl("주문비고"), 2, 4)
        master_layout.addWidget(self.detail_rmk, 2, 5, 1, 3)

        layout.addWidget(master_group)

        # ---------------------------------------------------------------------
        # [브릿지] 전략 바 (기존 유지)
        # ---------------------------------------------------------------------
        bridge_frame = QFrame()
        bridge_frame.setStyleSheet(MainStyles.SEARCH_BAR_STYLE)
        bridge_lay = QHBoxLayout(bridge_frame)
        
        self.bridge_price_year = QSpinBox() # 연도 표시는 일반 텍스트 형태로 고정
        self.bridge_price_year.setRange(2020, 2030)
        self.bridge_price_year.setFixedWidth(80)
        self.bridge_price_year.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.bridge_price_year.setReadOnly(False)
        self.bridge_price_year.setStyleSheet(MainStyles.INPUT_CENTER)
        self.btn_call_price = QPushButton("⚙️ 단가호출")
        self.btn_call_price.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_call_price.clicked.connect(self.open_price_setting)

        self.bridge_harvest_year = QSpinBox()
        self.bridge_harvest_year.setRange(2023, 2030)
        self.bridge_harvest_year.setFixedWidth(80)
        self.bridge_harvest_year.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.bridge_harvest_year.setReadOnly(False)
        self.bridge_harvest_year.setStyleSheet(MainStyles.INPUT_CENTER)
        self.bridge_item_cd = QComboBox()
        self.bridge_item_cd.setFixedWidth(100)
        self.bridge_variety_cd = QComboBox()
        self.bridge_variety_cd.setFixedWidth(120)

        self.btn_stock_matrix = QPushButton("📊 세부주문등록(Matrix)")
        self.btn_stock_matrix.setStyleSheet(MainStyles.BTN_FETCH)
        self.btn_stock_matrix.clicked.connect(self.open_stock_matrix)

        current_year = datetime.now().year
        last_year = current_year - 1

        self.bridge_price_year.setValue(current_year)
        self.bridge_harvest_year.setValue(last_year)
        

        bridge_lay.addWidget(self.make_lbl("📅 단가년도:"))
        bridge_lay.addWidget(self.bridge_price_year)
        bridge_lay.addWidget(self.btn_call_price)
        bridge_lay.addSpacing(20)
        bridge_lay.addWidget(self.make_lbl("🍏 수확년도:"))
        bridge_lay.addWidget(self.bridge_harvest_year)
        bridge_lay.addWidget(self.make_lbl("📦 품목:"))
        bridge_lay.addWidget(self.bridge_item_cd)
        bridge_lay.addWidget(self.make_lbl("🎨 품종:"))
        bridge_lay.addWidget(self.bridge_variety_cd)
        bridge_lay.addStretch()
        bridge_lay.addWidget(self.btn_stock_matrix)

        layout.addWidget(bridge_frame)

        # ---------------------------------------------------------------------
        # [2단계] 명세 테이블 (13개 컬럼 규격 준수)
        # ---------------------------------------------------------------------
        self.table_order_detail = QTableWidget(0, 14)
        self.table_order_detail.setStyleSheet(MainStyles.TABLE)
        self.table_order_detail.setHorizontalHeaderLabels([
            "수확년도", "무게", "품종", "등급", "사이즈", "수량", "단가", "상품주문합계액", "배송비합계", "창고", "배송방법", "삭제", "", ""
        ])
        # 📍 [핵심 1: 스텔스 기능] 12번, 13번 컬럼을 숨깁니다.
        # 데이터는 들어있지만 화면에는 나타나지 않습니다.
        self.table_order_detail.setColumnHidden(12, True) # 코드 번들 벙커
        self.table_order_detail.setColumnHidden(13, True) # 상세 ID 벙커
        self.table_order_detail.itemChanged.connect(self.sync_order_details_and_combo)
        
        # 📍 [핵심 2: 가득 채우기] 우측이 비어 보이지 않게 자동 확장
        header = self.table_order_detail.horizontalHeader()
        
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch) # 모든 컬럼 균등 확장
        layout.addWidget(self.table_order_detail)

        # 최종 저장 버튼
        self.btn_save_all = QPushButton("💾 주문 지휘 확정 및 전체 저장")
        self.btn_save_all.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_save_all.setFixedHeight(40)
        self.btn_save_all.clicked.connect(self.save_entire_order)
        layout.addWidget(self.btn_save_all)

    def make_lbl(self, text):
        """QLabel 스타일 헬퍼"""
        l = QLabel(text)
        l.setStyleSheet(MainStyles.TXT_LABEL_BOLD)
        return l

    # 신규 주문 등록
    def initiate_new_order(self):
        """
        [Action] 신규 주문 모드 가동
        - 모든 입력 필드를 초기화하고 신규 모드 플래그를 활성화합니다.
        - 1, 2단계를 넘어 3단계(우측 배송 계획)까지 완벽하게 초기화합니다.
        """
        # 1. 지휘 상태 설정
        self.current_order_no = None      # 기존 주문 번호 폐기
        self.is_new_order_mode = True     # 📍 신규 모드 깃발 올림
        self.current_cust_id = None

        # 2. [1단계] 마스터 정보 초기화
        self.detail_cust_nm.clear()       # 고객명
        self.detail_cust_tel.clear()      # 연락처
        self.detail_order_dt.setDate(QDate.currentDate()) # 오늘 날짜
        self.detail_rmk.clear()           # 비고
        
        # 콤보박스 초기화 (첫 번째 항목으로)
        if self.detail_status_cd.count() > 0:
            self.detail_status_cd.setCurrentIndex(0)
        if self.detail_season_type_cd.count() > 0:
            self.detail_season_type_cd.setCurrentIndex(0)

        # 3. 정산 정보 초기화
        self.detail_tot_order_amt.setText("0")
        self.detail_tot_ship_fee.setText("0")
        self.detail_pre_pay_amt.setText("0")
        self.detail_balance_lbl.setText("0")
        self.detail_balance_lbl.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH + " qproperty-alignment: 'AlignRight'; color: #3182CE;")
        
        # 4. [2단계] 상세 테이블 초기화
        self.table_order_detail.setRowCount(0)

        # ---------------------------------------------------------
        # 5. 📍 [3단계] 우측 배송 계획 및 입력폼 초기화 (추가됨)
        # ---------------------------------------------------------
        # (A) 테이블 및 콤보 초기화
        self.table_delivery_plan.setRowCount(0)           # 배송 계획 리스트 청소
        self.combo_delivery_target.clear()                # 대상 품목 콤보 비우기
        self.edit_delivery_date.setDate(QDate.currentDate()) # 예정일 오늘로 리셋
        
        # (B) 입력 폼 필드 싹 비우기
        for edit in [self.edit_snd_nm, self.edit_snd_tel, self.edit_snd_addr,
                     self.edit_rcv_nm, self.edit_rcv_tel, self.edit_rcv_qty, 
                     self.edit_rcv_addr, self.edit_rcv_msg]:
            edit.clear()
            
        # (C) UI 상태 복구
        self.input_tabs.setCurrentIndex(0)                # 단건 등록 탭으로 복귀
        self.input_area_container.show()                  # 접혀있던 입력창 열기
        self.btn_toggle_input.setText("🔼 입력창 접기")
        self.adjust_input_tab_height()                    # 동적 높이 재계산
        # ---------------------------------------------------------

        # 6. 시각적 보고 및 포커스 이동
        if hasattr(self, 'lbl_order_no_display'):
            self.lbl_order_no_display.setText("✨ 신규 주문 작성 중")
        
        # 고객명 입력창으로 커서 이동
        self.detail_cust_nm.setFocus()

        # print("[System] 신규 주문 지휘 체계가 가동되었습니다. 장부가 백지로 교체되었습니다.")

    # 고객 찾기 팝업
    def open_customer_search_popup(self):
        """[Action] 고객 검색 팝업 호출 (교정된 규격 적용)"""
        # 현재 입력창에 써놓은 텍스트를 검색어로 활용
        search_keyword = self.detail_cust_nm.text() 
        
        try:
            # 📍 [교정] 인자 순서: db, farm_cd, keyword, self
            popup = CustomerSearchPopup(
                self.db, self.farm_cd, self.user_id, search_keyword, self
            )
            
            if popup.exec():
                customer = popup.get_selected_customer()
                if customer:
                    # 상세주문등록 가능하도록 상태(False -> True) 변경
                    self.is_new_order_mode = True
                    # 📍 대표님의 DB 컬럼명에 맞춰 이식
                    self.detail_cust_nm.setText(str(customer.get('custm_nm', '')))
                    self.detail_cust_tel.setText(str(customer.get('mobile', '')))
                    self.current_cust_id = str(customer.get('custm_id', 'GUEST'))

        except Exception as e:
            QMessageBox.critical(self, "팝업 오류", f"고객 검색 엔진 가동 실패: {str(e)}")

    # 단가 팝업 호출
    def open_price_setting(self):
        """
        [Popup] 단가 설정 팝업 호출 (인자명 교정본)
        - bridge_price_year -> sales_year (판매년도)
        - bridge_harvest_year -> harvest_year (생산년도)
        """
        # 1. 호출을 위한 기준 데이터 확보
        sales_y = self.bridge_price_year.value()
        harvest_y = self.bridge_harvest_year.value()
        
        # 1단계의 시즌코드 (SS01...)
        season_cd = self.detail_season_type_cd.currentData()
        season_nm = self.detail_season_type_cd.currentText()

        # 방어 로직: 시즌 미선택 시 경고
        if not season_cd:
            QMessageBox.warning(self, "알림", "1단계의 [시즌코드]를 먼저 선택해 주십시오.")
            return

        try:
            # 2. PriceSettingPopup 생성 (대표님 소스 코드의 인자명 준수)
            popup = PriceSettingPopup(
                db_manager=self.db,
                code_manager=self.code_manager,
                farm_cd=self.farm_cd,
                sales_year=sales_y,    # start_year가 아닌 sales_year
                harvest_year=harvest_y, # end_year가 아닌 harvest_year
                season_cd=season_cd,
                season_nm=season_nm
            )
            
            # 3. 팝업 실행
            if popup.exec():
                print(f"[지휘소] {sales_y}년도 단가 설정이 업데이트되었습니다.")
                
        except Exception as e:
            QMessageBox.critical(self, "팝업 오류", f"단가 설정 창을 실행할 수 없습니다.\n사유: {str(e)}")

    # 재고, 상세주문팝업 호출
    def open_stock_matrix(self):

        # 신규 주문, 기존 주문 수정일 경우는 통과
        is_new = getattr(self, 'is_new_order_mode', False)
        
        if not self.current_order_no and not is_new:
            QMessageBox.warning(self, "지휘 오류", 
                "주문을 선택하거나 [신규] 버튼을 눌러 작성을 시작해 주십시오.")
            return
        
        """[Bridge Action] 재고 매트릭스 팝업 호출 (완전 동기화 버전)"""
        # 1. 현재 브릿지의 기준 정보 확보
        h_year = self.bridge_harvest_year.value()
        item_cd = self.bridge_item_cd.currentData()
        v_cd = self.bridge_variety_cd.currentData()
        v_nm = self.bridge_variety_cd.currentText()
        
        # 무게(weight) 추출 (콤보 텍스트에서 숫자만 추출)
        import re
        weight_text = self.bridge_item_cd.currentText() # 혹은 별도 무게 콤보
        w_match = re.findall(r"[-+]?\d*\.\d+|\d+", weight_text)
        current_weight = float(w_match[0]) if w_match else 7.5

        try:
            # 2. 📍 인자 명칭을 v_cd로 통일하여 호출
            popup = StockMatrixPopup(
                harvest_year=h_year,
                item_cd=item_cd,
                v_cd=v_cd,
                v_nm=v_nm,
                weight=current_weight,
                db_manager=self.db,
                code_manager=self.code_manager,
                farm_cd=self.farm_cd,
                parent=self
            )
            
            if popup.exec():
                # 팝업에서 [주문서 담기] 성공 시 데이터 처리
                selected_data = popup.get_selected_data()
                self.add_matrix_items_to_table(selected_data)
                
        except Exception as e:
            QMessageBox.critical(self, "엔진 오류", f"매트릭스 가동 실패: {str(e)}")

    def add_matrix_items_to_table(self, data_list):
        """팝업에서 받은 리스트를 상세 테이블에 한 줄씩 추가"""
        if not data_list:
            return
            
        for data in data_list:
            # 실무 엔진 호출
            self.add_order_item_and_sync(data)

        QMessageBox.information(self, "완료", f"{len(data_list)}건의 항목이 주문서에 배치되었습니다.")

    # [📍 통합 엔진] 상세 품목 추가 및 마스터 금액 실시간 정산
    #  - data: 매트릭스나 수동 입력에서 넘어온 품목 정보 (dict)
    #  - refresh_ui: True일 경우 합계 금액을 즉시 재계산 (루프 시 성능 최적화용)        
    def add_order_item_and_sync(self, data, refresh_ui=True):
        """[📍 통합 엔진] 택배 코드(LO010200) 기준 배송비 자동 계산 버전"""
        try:
            is_new = getattr(self, 'is_new_order_mode', False)
            if not self.current_order_no and not is_new: return

            # 1. 단가 및 기본 배송비 조회
            sales_y = self.bridge_price_year.value()
            season_cd = self.detail_season_type_cd.currentData()
            h_year = data.get('harvest_year', self.bridge_harvest_year.value())
            
            sql = """
                SELECT unit_price, base_ship_fee 
                FROM m_item_unit_price 
                WHERE farm_cd=? AND sales_year=? AND harvest_year=? AND season_cd=? 
                  AND item_cd=? AND variety_cd=? AND grade_cd=? AND size_cd=?
            """
            params = (self.farm_cd, str(sales_y), str(h_year), season_cd, 
                      data['item_cd'], data['v_cd'], data['grade_cd'], data['size_cd'])
            res = self.db.execute_query(sql, params)
            
            row_data = dict(res[0]) if res else {'unit_price': 0, 'base_ship_fee': 0}
            unit_price = row_data.get('unit_price', 0)
            base_ship_fee = row_data.get('base_ship_fee', 0)

            # 2. 📍 [교정] 택배(LO010200) 기준으로 초기 배송비 계산
            qty = data['qty']
            amt = qty * unit_price
            
            # 📍 지휘관 확인 사항: 택배 코드는 LO010200입니다.
            default_method_cd = 'LO010200' 
            ship_fee = qty * base_ship_fee # 기본이 택배이므로 바로 배송비 적용

            # 3. 행 추가 및 데이터 배치 (무게, 품종, 등급, 사이즈 순)
            row = self.table_order_detail.rowCount()
            self.table_order_detail.insertRow(row)

            # 명칭 변환 (CodeManager 활용)
            v_nm = self.code_manager.get_code_nm(data['v_cd'])
            g_nm = self.code_manager.get_code_nm(data['grade_cd'])
            s_nm = self.code_manager.get_code_nm(data['size_cd'])
            wh_nm = self.code_manager.get_code_nm("WH01")

            display_values = [
                h_year, data.get('weight', ''), v_nm, g_nm, s_nm, 
                qty, f"{int(unit_price):,}", f"{int(amt):,}", f"{int(ship_fee):,}",
                wh_nm
            ]

            for col, val in enumerate(display_values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col in [4, 5, 6, 7]: # 수량, 단가, 합계, 배송비 우측정렬
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_order_detail.setItem(row, col, item)

            # 4. 배송방법 콤보박스 (10번 컬럼) 및 속성 부여
            # 📍 기본값으로 LO010200(택배) 세팅
            combo = self.set_table_combo(self.table_order_detail, row, 10, 'LO01', default_val=default_method_cd)
            combo.setProperty("row", row)
            combo.setProperty("base_fee", base_ship_fee)
            combo.currentIndexChanged.connect(self.handle_shipping_method_change)
            combo.currentIndexChanged.connect(self.update_delivery_target_combo)

            # 5. 삭제 버튼 및 히든 데이터
            self.insert_delete_button(row, 11)

            self.update_delivery_target_combo()

            code_bundle = f"{data['item_cd']}|{data['v_cd']}|{data['grade_cd']}|{data['size_cd']}|WH01"
            self.table_order_detail.setItem(row, 12, QTableWidgetItem(code_bundle))

            if refresh_ui:
                self.update_master_amounts()

        except Exception as e:
            print(f"[지휘소 통합 오류] {str(e)}")

    def insert_delete_button(self, row, col):
        """
        [UI] 테이블 내 삭제 버튼 식립 (표준 스타일 적용 버전)
        - MainStyles.BTN_DANGER 규격을 사용하여 통일감 확보
        """
        btn = QPushButton("삭제")
        
        # 📍 [표준 스타일 적용] 
        # styles.py에 정의된 위험(Danger) 버튼 스타일을 입힙니다.
        btn.setStyleSheet(MainStyles.BTN_DANGER)
        
        # 테이블 셀 크기에 맞게 미세 조정
        btn.setFixedWidth(40)
        btn.setFixedHeight(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 클릭 시 삭제 핸들러 연결
        btn.clicked.connect(self.handle_row_deletion)
        
        # 📍 중앙 정렬을 위해 레이아웃 컨테이너 사용 (선택 사항)
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.addWidget(btn)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.table_order_detail.setCellWidget(row, col, container)

    def handle_row_deletion(self):
        """[Action] 표준 삭제 프로세스: 행 제거 + 실시간 합계 리프레시"""
        button = self.sender()
        if not button: return

        # 컨테이너(QWidget) 안에 버튼이 있으므로 부모의 위치를 계산합니다.
        pos = button.parentWidget().mapTo(self.table_order_detail, button.pos())
        index = self.table_order_detail.indexAt(pos)
        
        if index.isValid():
            row = index.row()
            self.table_order_detail.removeRow(row)

            # 📍 [핵심] 삭제 시에도 우측 콤보박스 즉시 동기화
            self.update_delivery_target_combo()
            
            # 📍 지휘관의 장부 즉시 갱신
            self.update_master_amounts()
            print(f"[System] {row + 1}번 항목이 제거되었으며, 정산 금액이 재계산되었습니다.")

    # 수량/단가 변경시 마스터의 총합계와 우측판넬의 대상품목을 변경한다.
    def sync_order_details_and_combo(self, item):
        """수량(5)이나 단가(6)가 변경될 때 호출되는 통합 동기화 엔진"""
        if item.column() not in [5, 6]: 
            return # 수량, 단가 외에는 무시
        
        row = item.row()
        
        # 📍 [안전장치] 수량과 단가 아이템이 둘 다 실제로 존재하는지 먼저 확인합니다.
        qty_item = self.table_order_detail.item(row, 5)
        price_item = self.table_order_detail.item(row, 6)
        
        # 둘 중 하나라도 아직 생성되지 않았다면 계산을 건너뜁니다.
        if qty_item is None or price_item is None:
            return

        self.table_order_detail.blockSignals(True) # 무한루프 방지
        try:
            # 이제 안전하게 .text()를 호출할 수 있습니다.
            qty_text = qty_item.text() if qty_item.text() else "0"
            price_text = price_item.text() if price_item.text() else "0"
            
            qty = int(re.sub(r'[^0-9]', '', qty_text))
            price = int(re.sub(r'[^0-9]', '', price_text))
            
            # 1. 수량 * 단가 재계산 후 7번(합계액) 갱신
            self.table_order_detail.setItem(row, 7, QTableWidgetItem(f"{qty * price:,}"))
            
            # 2. 배송비 재계산 (기존 배송방법 콤보의 base_fee 활용)
            method_combo = self.table_order_detail.cellWidget(row, 10)
            if method_combo:
                base_fee = method_combo.property("base_fee") or 0
                new_fee = qty * base_fee if method_combo.currentData() == 'LO010200' else 0
                self.table_order_detail.setItem(row, 8, QTableWidgetItem(f"{int(new_fee):,}"))

        except Exception as e:
            print(f"Sync Error: {e}")
        finally:
            self.table_order_detail.blockSignals(False)

        # 3. 마스터 금액 및 우측 콤보박스 갱신
        self.update_master_amounts()         # 마스터 합계 갱신
        self.update_delivery_target_combo()  # 우측 대상품목 콤보박스 텍스트 갱신

    # 마스터 총주문금액, 총배송비, 입금액, 미수금 셋팅
    def update_master_amounts(self):
        """[Calculation] 상세 내역을 기반으로 마스터 정산 정보를 셋팅합니다."""
        total_order_amt = 0
        total_ship_fee = 0
        
        # 1. 테이블 전체 행 순회하며 합산
        for row in range(self.table_order_detail.rowCount()):
            amt_item = self.table_order_detail.item(row, 7)    # 상품합계
            ship_item = self.table_order_detail.item(row, 8)   # 배송비

            # 상품 합계액 안전하게 읽기
            if amt_item and amt_item.text():
                amt_text = amt_item.text().replace(',', '')
                total_order_amt += int(amt_text) if amt_text.isdigit() else 0
            
            # 배송비 안전하게 읽기
            if ship_item and ship_item.text():
                ship_text = ship_item.text().replace(',', '')
                total_ship_fee += int(ship_text) if ship_text.isdigit() else 0

        # 2. UI 표시
        self.detail_tot_order_amt.setText(f"{total_order_amt:,}")
        self.detail_tot_ship_fee.setText(f"{total_ship_fee:,}")
        
        # 미수금 재계산 로직 호출 (안전하게 처리)
        try:
            # 3. 입금액(예약금) 읽기
            pre_pay = self.detail_pre_pay_amt.text().replace(',', '')
            pre_pay_amt = int(pre_pay) if pre_pay else 0
            
            # 4. 미수금 계산: (총주문 + 총배송비) - 입금액
            balance = (total_order_amt + total_ship_fee) - pre_pay_amt
            self.detail_balance_lbl.setText(f"{balance:,}")
            
            # 미수금이 있으면 빨간색, 완납이면 파란색으로 시각적 경고
            color = "#E53E3E" if balance > 0 else "#3182CE"
            self.detail_balance_lbl.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH + f" qproperty-alignment: 'AlignRight'; color: {color};")
        except:
            self.detail_unpaid_amt.setText("0")

    # 배송방법이 Not 택배일 경우 택배비를 "0" 으로 셋팅
    def handle_shipping_method_change(self):
        """[Action] 배송방법이 '택배(LO010200)'일 때만 배송비 부과"""
        combo = self.sender()
        row = combo.property("row")
        base_fee = combo.property("base_fee")
        
        # 1. 수량 셀 데이터 정제 (숫자만 추출)
        qty_item = self.table_order_detail.item(row, 5)
        if qty_item:
            qty_text = qty_item.text()
            qty_cleaned = re.sub(r'[^0-9]', '', qty_text)
            qty = int(qty_cleaned) if qty_cleaned else 0
        else:
            qty = 0
        
        # 2. 📍 [교정] 택배(LO010200)일 때만 배송비 계산, 그 외는 0원
        if combo.currentData() == 'LO010200':
            new_ship_fee = qty * base_fee
        else:
            new_ship_fee = 0
            
        self.table_order_detail.setItem(row, 8, QTableWidgetItem(f"{int(new_ship_fee):,}"))
        self.table_order_detail.item(row, 8).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # 3. 마스터 합계 즉시 반영
        self.update_master_amounts()

    # ==========================================================================
    # [3] 우측 택배/방문 정보 관리하기
    # ==========================================================================
    def setup_right_panel(self):
        """[Right] 3단계: 배송 계획 (변수명 self.right_layout으로 통일하여 오류 해결)"""
        # 📍 [교정] layout을 self.right_layout으로 선언하여 클래스 전체에서 공유 가능하게 함
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 📍 다른 함수(돋보기)에서 참조할 수 있도록 연결 (변수명 충돌 방지)
        self.right_layout = layout

        # (1) 헤더 및 확장 토글 버튼
        header_lay = QHBoxLayout()
        lbl_main_title = QLabel("🚚 3단계: 배송 및 수령 계획")
        lbl_main_title.setStyleSheet(MainStyles.DASH_CARD_TITLE)
        
        self.btn_toggle_input = QPushButton("🔼 입력창 접기")
        self.btn_toggle_input.setFixedWidth(120)
        self.btn_toggle_input.setStyleSheet(MainStyles.BTN_FETCH)
        self.btn_toggle_input.clicked.connect(self.toggle_input_area)
        
        header_lay.addWidget(lbl_main_title); header_lay.addStretch(); header_lay.addWidget(self.btn_toggle_input)
        self.right_layout.addLayout(header_lay)

        # --- [입력 영역 컨테이너] ---
        self.input_area_container = QWidget()
        input_vlay = QVBoxLayout(self.input_area_container)
        input_vlay.setContentsMargins(5, 5, 5, 5); input_vlay.setSpacing(5)

        # (2) 공통 설정 (대상/예정일)
        base_group = QGroupBox("대상품목설정")
        base_group.setStyleSheet(MainStyles.GROUP_BOX)
        base_lay = QGridLayout(base_group)
        base_lay.setContentsMargins(15, 10, 15, 15) 
        
        self.combo_delivery_target = QComboBox()
        self.combo_delivery_target.setStyleSheet(MainStyles.COMBO); 
        self.combo_delivery_target.setFixedHeight(30)
        
        self.edit_delivery_date = QDateEdit(QDate.currentDate())
        self.edit_delivery_date.setCalendarPopup(True); 
        self.edit_delivery_date.setStyleSheet(MainStyles.COMBO); 
        self.edit_delivery_date.setFixedHeight(30)

        base_lay.addWidget(QLabel("대상 품목", styleSheet=MainStyles.TXT_LABEL_BOLD), 0, 0)
        base_lay.addWidget(self.combo_delivery_target, 0, 1)
        base_lay.addWidget(QLabel("예정 일자", styleSheet=MainStyles.TXT_LABEL_BOLD), 0, 2)
        base_lay.addWidget(self.edit_delivery_date, 0, 3)
        input_vlay.addWidget(base_group)

        # (3) 입력 탭
        self.input_tabs = QTabWidget()
        self.input_tabs.setStyleSheet(MainStyles.STYLE_TABS)
        self.input_tabs.currentChanged.connect(self.adjust_input_tab_height)
        
        # --- 탭 A: 단건 등록 (가변 레이어 섹션) ---
        single_tab = QWidget(); single_lay = QVBoxLayout(single_tab)
        single_lay.setContentsMargins(5, 5, 5, 5); single_lay.setSpacing(5)

        # [레이어 1] 보내는 사람 정보
        self.sender_group = QGroupBox("👤 [택배전용] 보내는 사람 정보")
        self.sender_group.setStyleSheet(MainStyles.GROUP_BOX)
        sender_lay = QGridLayout(self.sender_group); 
        sender_lay.setContentsMargins(15, 10, 15, 15)
        sender_lay.setVerticalSpacing(10)
        self.edit_snd_nm = QLineEdit(); self.edit_snd_tel = QLineEdit(); self.edit_snd_addr = QLineEdit()
        for e in [self.edit_snd_nm, self.edit_snd_tel, self.edit_snd_addr]: 
            e.setStyleSheet(MainStyles.INPUT_LEFT); e.setFixedHeight(28)
        sender_lay.addWidget(QLabel("성함", styleSheet=MainStyles.TXT_LABEL_BOLD), 0, 0); sender_lay.addWidget(self.edit_snd_nm, 0, 1)
        sender_lay.addWidget(QLabel("연락처", styleSheet=MainStyles.TXT_LABEL_BOLD), 0, 2); sender_lay.addWidget(self.edit_snd_tel, 0, 3)
        sender_lay.addWidget(QLabel("주소", styleSheet=MainStyles.TXT_LABEL_BOLD), 1, 0); sender_lay.addWidget(self.edit_snd_addr, 1, 1, 1, 3)
        single_lay.addWidget(self.sender_group); 
        self.sender_group.hide()

        # [레이어 2] 받는 사람 정보
        self.rcv_group = QGroupBox("🎁 받는 사람 상세 정보")
        self.rcv_group.setStyleSheet(MainStyles.GROUP_BOX)
        rcv_lay = QGridLayout(self.rcv_group); 
        rcv_lay.setContentsMargins(15, 10, 15, 15)
        rcv_lay.setVerticalSpacing(10)
        self.edit_rcv_nm = QLineEdit(); self.edit_rcv_tel = QLineEdit()
        self.edit_rcv_qty = QLineEdit(); self.edit_rcv_addr = QLineEdit(); self.edit_rcv_msg = QLineEdit()
        for e in [self.edit_rcv_nm, self.edit_rcv_tel, self.edit_rcv_qty, self.edit_rcv_addr, self.edit_rcv_msg]: 
            e.setStyleSheet(MainStyles.INPUT_LEFT); e.setFixedHeight(28)
        
        rcv_lay.addWidget(QLabel("받는분", styleSheet=MainStyles.TXT_LABEL_BOLD), 0, 0); rcv_lay.addWidget(self.edit_rcv_nm, 0, 1)
        rcv_lay.addWidget(QLabel("연락처", styleSheet=MainStyles.TXT_LABEL_BOLD), 0, 2); rcv_lay.addWidget(self.edit_rcv_tel, 0, 3)
        rcv_lay.addWidget(QLabel("수량", styleSheet=MainStyles.TXT_LABEL_BOLD), 1, 0); rcv_lay.addWidget(self.edit_rcv_qty, 1, 1)
        rcv_lay.addWidget(QLabel("주소", styleSheet=MainStyles.TXT_LABEL_BOLD), 1, 2); rcv_lay.addWidget(self.edit_rcv_addr, 1, 3)
        rcv_lay.addWidget(QLabel("메시지", styleSheet=MainStyles.TXT_LABEL_BOLD), 2, 0); rcv_lay.addWidget(self.edit_rcv_msg, 2, 1, 1, 3)
        single_lay.addWidget(self.rcv_group)

        # [레이어 3] 버튼 구역
        self.btn_add_plan = QPushButton("➕ 계획 리스트에 추가"); self.btn_add_plan.setStyleSheet(MainStyles.BTN_SECONDARY); self.btn_add_plan.setFixedHeight(35)
        self.btn_add_plan.clicked.connect(self.add_delivery_plan_from_form)
        single_lay.addWidget(self.btn_add_plan)
        single_lay.addStretch() 
        self.input_tabs.addTab(single_tab, "✏️ 단건 등록")

        # --- 탭 B: 엑셀 일괄 등록 ---
        excel_tab = QWidget(); excel_vlay = QVBoxLayout(excel_tab)
        excel_vlay.setContentsMargins(15, 10, 15, 15); excel_vlay.setSpacing(10)
        btn_lay = QHBoxLayout()
        btn_excel_down = QPushButton("📥 양식 다운로드"); btn_excel_up = QPushButton("📤 엑셀 업로드")
        btn_excel_down.setStyleSheet(MainStyles.BTN_FETCH); btn_excel_up.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_excel_down.setFixedHeight(35); btn_excel_up.setFixedHeight(35)
        btn_excel_down.clicked.connect(self.download_delivery_template); btn_excel_up.clicked.connect(self.upload_delivery_excel)
        btn_lay.addWidget(btn_excel_down); btn_lay.addWidget(btn_excel_up)
        excel_vlay.addLayout(btn_lay); excel_vlay.addStretch() 
        self.input_tabs.addTab(excel_tab, "📊 엑셀 일괄")
        
        input_vlay.addWidget(self.input_tabs)
        self.right_layout.addWidget(self.input_area_container)

        # (4) 배송 계획 테이블 초기화
        self.table_delivery_plan = QTableWidget(0, 9) 
        self.table_delivery_plan.setHorizontalHeaderLabels([
            "대상 품목", "예정일", "받는분", "연락처", "주소", "수량", "배송메시지", "삭제", "SND_INFO_HIDDEN"
        ])

        self.table_delivery_plan.setStyleSheet(MainStyles.TABLE)
        self.table_delivery_plan.setColumnHidden(8, True)
        self.table_delivery_plan.verticalHeader().setDefaultSectionSize(28)
        self.table_delivery_plan.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # 컬럼 너비 정책 최적화
        header = self.table_delivery_plan.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # 주소 확장
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # 메시지 확장
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table_delivery_plan.setColumnWidth(5, 40)
        self.table_delivery_plan.setColumnWidth(7, 50)

        # (5) 📍 [돋보기 영역] 상세 검수 뷰어 구성
        self.detail_viewer = QTextEdit()
        self.detail_viewer.setReadOnly(True)
        self.detail_viewer.setFixedHeight(80) 
        self.detail_viewer.setStyleSheet(MainStyles.TEXT_EDIT + " background-color: #F8F9FA; border-color: #DEE2E6;")
        self.detail_viewer.setPlaceholderText("💡 검수할 배송지 행을 클릭하면 상세 주소와 메시지가 여기에 표시됩니다.")

        # (6) 최종 레이아웃 배치 (📍 self.right_layout 사용으로 튕김 방지)
        self.right_layout.addWidget(self.table_delivery_plan, stretch=1) 
        self.right_layout.addWidget(self.detail_viewer)

        # (7) 이벤트 및 시그널 연결
        self.table_delivery_plan.cellClicked.connect(self.update_detail_viewer)
        self.combo_delivery_target.currentIndexChanged.connect(self.on_delivery_target_changed)

    # 탭의 높이 변경
    def adjust_input_tab_height(self):
        """[Action] 탭 전환 및 레이어 노출 상태에 따라 높이를 동적으로 계산하여 반납"""
        index = self.input_tabs.currentIndex()
        
        if index == 0: # 단건 등록 탭
            # 📍 핵심: '보내는 사람' 레이어가 보이는지 체크
            if self.sender_group.isVisible():
                # 택배 등 모든 정보 노출 시
                self.input_tabs.setFixedHeight(400)
            else:
                # 방문/화물 등 보내는 사람 숨김 시 -> 높이 대폭 축소 (공간 반납)
                self.input_tabs.setFixedHeight(250) 
        else: # 엑셀 일괄 탭 (index 1)
            # 버튼만 있으므로 최소 높이
            self.input_tabs.setFixedHeight(110)
            
        # 레이아웃 즉시 갱신
        self.input_tabs.update()

    def add_single_delivery_row(self):
        """[Right Panel] 단건 입력 폼의 데이터를 배송지 테이블에 추가"""
        nm = self.edit_recp_nm.text().strip()
        tel = self.edit_recp_tel.text().strip()
        qty = self.edit_recp_qty.text().strip()
        addr = self.edit_recp_addr.text().strip()
        
        if not nm or not qty:
            QMessageBox.warning(self, "알림", "받는분 성함과 수량은 필수입니다.")
            return

        target_idx = self.combo_delivery_target.currentIndex()
        if target_idx < 0:
            QMessageBox.warning(self, "알림", "대상 품목을 먼저 선택해 주세요.")
            return

        target_text = self.combo_delivery_target.currentText().split(" - ")[0]
        
        row = self.table_delivery_plan.rowCount()
        self.table_delivery_plan.insertRow(row)
        self.table_delivery_plan.setItem(row, 0, QTableWidgetItem(target_text)) # 대상품목
        self.table_delivery_plan.setItem(row, 1, QTableWidgetItem(nm))          # 받는분
        self.table_delivery_plan.setItem(row, 2, QTableWidgetItem(tel))         # 연락처
        self.table_delivery_plan.setItem(row, 3, QTableWidgetItem(qty))         # 수량
        self.table_delivery_plan.setItem(row, 4, QTableWidgetItem(addr))        # 주소
        
        # 입력창 초기화
        self.edit_recp_nm.clear(); self.edit_recp_tel.clear(); 
        self.edit_recp_qty.clear(); self.edit_recp_addr.clear()

    def download_delivery_template(self):
        """[Excel] 배송지 등록용 표준 양식 다운로드 (파일 점유 에러 대응)"""
        save_path, _ = QFileDialog.getSaveFileName(
            self, "양식 저장", "배송지_일괄등록_양식.xlsx", "Excel Files (*.xlsx)"
        )
        if not save_path:
            return

        import pandas as pd  # 지연 로딩: 페이지 초기화 속도 개선
        try:
            # 1. 대표님께서 지정하신 8개 컬럼 양식 정의
            columns = [
                '보내는분', '보내는분연락처', '보내는분주소',
                '받는분', '받는분연락처', '받는분주소', 
                '수량', '배송메시지'
            ]
            df = pd.DataFrame(columns=columns)
            
            # 예시 데이터 1건 삽입
            df.loc[0] = [
                '농원', '010-1234-5678', '경기도...',
                '홍길동', '010-0000-0000', '서울시 강남구...', 
                '1', '부재 시 문 앞에 놓아주세요'
            ]

            # 2. 📍 [핵심] 파일 쓰기 시도
            df.to_excel(save_path, index=False)
            QMessageBox.information(self, "완료", "배송지 등록 양식이 성공적으로 생성되었습니다.")

        except PermissionError:
            # 📍 엑셀이 열려 있어 덮어쓰기가 불가능한 경우 (Errno 13)
            QMessageBox.critical(
                self, "저장 실패", 
                "해당 엑셀 파일이 이미 열려 있습니다.\n\n"
                "열려 있는 엑셀 창을 닫으신 후 다시 '양식 다운로드'를 시도해 주세요."
            )

    def upload_delivery_excel(self):
        """[Excel] 8컬럼 순서(Index) 기반 로드 및 수량 정밀 검증 엔진"""
        # 1. 대상 선택 확인
        target_idx = self.combo_delivery_target.currentData()
        if target_idx is None:
            QMessageBox.warning(self, "알림", "배송 대상 품목을 먼저 선택해 주세요.")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "Excel Files (*.xlsx *.xls)")
        if not file_path:
            return

        import pandas as pd  # 지연 로딩: 페이지 초기화 속도 개선
        try:
            # 2. 엑셀 데이터 로드 (헤더가 있어도 순서로 접근하기 위해 values 활용 가능)
            df = pd.read_excel(file_path)
            if df.empty: return

            # 📍 [검증 0] 최소 컬럼 수 확인 (지시하신 8컬럼 규격 준수 여부)
            if len(df.columns) < 8:
                QMessageBox.critical(self, "양식 오류", "엑셀 양식이 올바르지 않습니다.\n최소 8개의 컬럼(보내는이~메시지)이 필요합니다.")
                return

            # 3. 기초 정보 및 중앙 테이블 주문 수량 확보
            import re
            dlv_date = self.edit_delivery_date.date().toString("yyyy-MM-dd")
            full_text = self.combo_delivery_target.currentText().split(" 【")[0]
            target_text = re.sub(r'^\[\d+\]\s*', '', full_text)

            order_qty_item = self.table_order_detail.item(target_idx, 5)
            total_ordered_qty = int(re.sub(r'[^0-9]', '', order_qty_item.text()))

            # 4. 📍 [수량 초과 검문소] - 순서(Index 6) 기반으로 수량 합산
            current_planned_sum = 0
            for r in range(self.table_delivery_plan.rowCount()):
                # UserRole에 숨겨진 인덱스가 현재 선택한 품목과 같은 경우만 합산
                if self.table_delivery_plan.item(r, 0).data(Qt.ItemDataRole.UserRole) == target_idx:
                    current_planned_sum += int(self.table_delivery_plan.item(r, 5).text())

            # 📍 iloc[:, 6]을 사용하여 7번째 컬럼(수량)의 합계를 구함
            excel_total_qty = df.iloc[:, 6].sum()

            if current_planned_sum + excel_total_qty > total_ordered_qty:
                remain = total_ordered_qty - current_planned_sum
                QMessageBox.critical(self, "수량 초과", 
                    f"엑셀 데이터가 주문 수량을 초과했습니다!\n\n"
                    f"총 주문: {total_ordered_qty}개 / 현재 배정: {current_planned_sum}개\n"
                    f"배정 가능 잔량: {remain}개\n"
                    f"----------------------------------\n"
                    f"엑셀 요청 수량: {excel_total_qty}개")
                return

            # 5. [검증 통과] 데이터 주입 (UI 기본값 확보)
            ui_snd_nm = self.edit_snd_nm.text().strip()
            ui_snd_tel = self.edit_snd_tel.text().strip()
            ui_snd_addr = self.edit_snd_addr.text().strip()
            ui_msg = self.edit_rcv_msg.text().strip()

            for i in range(len(df)):
                # 📍 iloc[행, 열인덱스]를 사용하여 명칭과 상관없이 순서대로 가져옴
                # 보내는사람(0,1,2), 받는사람(3,4,5), 수량(6), 메시지(7)
                s_nm = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ui_snd_nm
                s_tel = str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else ui_snd_tel
                s_addr = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ui_snd_addr
                
                r_nm = str(df.iloc[i, 3]).strip() if pd.notna(df.iloc[i, 3]) else ""
                r_tel = str(df.iloc[i, 4]).strip() if pd.notna(df.iloc[i, 4]) else ""
                r_addr = str(df.iloc[i, 5]).strip() if pd.notna(df.iloc[i, 5]) else ""
                
                qty = int(df.iloc[i, 6]) if pd.notna(df.iloc[i, 6]) else 1
                msg = str(df.iloc[i, 7]).strip() if pd.notna(df.iloc[i, 7]) else ui_msg
                
                # sender_info 구성 (보내는이 3종)
                sender_info = f"{s_nm}|{s_tel}|{s_addr}"
                
                # rcv_data 구성 (받는이 정보 및 메시지)
                rcv_data = {
                    '받는분': r_nm,
                    '연락처': r_tel,
                    '주소': r_addr,
                    '수량': qty,
                    '배송메시지': msg
                }
                
                # 테이블에 실제 추가 (target_idx 전달하여 UserRole 태깅 보장)
                self.add_excel_row_to_plan(target_text, dlv_date, rcv_data, sender_info, target_idx)
                
            QMessageBox.information(self, "성공", f"{len(df)}건의 배송 정보가 순서 기반으로 등록되었습니다.")
            
            # 6. [시야 확보] 입력창 자동 숨김 로직
            if len(df) >= 3:
                self.input_area_container.hide()
                self.btn_toggle_input.setText("🔽 입력창 펴기")
                self.adjust_input_tab_height()
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 파싱 중 사고 발생: {e}")
    
    def add_excel_row_to_plan(self, item_nm, date, rcv, sender_data, source_idx):
        """
        [📍최종 완결본] 8컬럼 노출 규격 + 툴팁(ToolTip) 기능 구현
        - 긴 주소와 배송메시지를 마우스 호버 시 즉시 노출하여 검수 편의성 극대화
        """
        r = self.table_delivery_plan.rowCount()
        self.table_delivery_plan.insertRow(r)
        
        # 0. 대상품목 (품목명이 길 수 있으므로 툴팁 추가)
        item_nm_widget = QTableWidgetItem(item_nm)
        item_nm_widget.setData(Qt.ItemDataRole.UserRole, source_idx)
        item_nm_widget.setToolTip(f"📦 대상 품목: {item_nm}") # 📍 툴팁 추가
        self.table_delivery_plan.setItem(r, 0, item_nm_widget)
        
        # 📍 툴팁 설정을 지원하는 개선된 set_it 헬퍼 함수
        def set_it(col, val, align=Qt.AlignmentFlag.AlignCenter, tooltip=None):
            it = QTableWidgetItem(str(val))
            it.setTextAlignment(align) # 정렬만 설정 (폰트/컬러는 테이블 스타일을 따름)
            if tooltip:
                it.setToolTip(tooltip)
            self.table_delivery_plan.setItem(r, col, it)

        # 데이터 배치 (대표님 지시 순서 100% 준수)
        set_it(0, item_nm, tooltip=f"📦 {item_nm}")
        self.table_delivery_plan.item(r, 0).setData(Qt.ItemDataRole.UserRole, source_idx)
        
        set_it(1, date)
        set_it(2, rcv.get('받는분', ''))
        set_it(3, rcv.get('연락처', ''))
        set_it(4, rcv.get('주소', ''), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tooltip=rcv.get('주소', ''))
        
        # 수량 (중앙 정렬)
        set_it(5, str(rcv.get('수량', '1')))
        
        # 메시지 (좌측 정렬)
        set_it(6, rcv.get('배송메시지', ''), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tooltip=rcv.get('배송메시지', ''))
        
        self.insert_plan_delete_button(r, 7)
        self.table_delivery_plan.setItem(r, 8, QTableWidgetItem(f"{sender_data}|{rcv.get('배송메시지', '')}"))
        
        # 7. 삭제 버튼
        self.insert_plan_delete_button(r, 7)
        
        # 8. [히든] 보내는 사람 정보 + 메시지 통합
        full_sender_data = f"{sender_data}|{rcv.get('배송메시지', '')}"
        self.table_delivery_plan.setItem(r, 8, QTableWidgetItem(full_sender_data))

   # [LOGIC] 배송 계획 행 추가 (Manual 및 DB Load 공용)
    def add_delivery_plan_row(self, data=None):
        """
        [📍아토스 프로버전] 배송 계획 테이블 데이터 매핑 (신규 9컬럼 규격)
        - 0:품목 1:예정일 2:받는분 3:연락처 4:주소 5:수량 6:메시지 7:버튼 8:발송인(Hidden)
        - DB 로드 및 수동 추가 모두 완벽 대응
        """
        if data is None: data = {}
        row = self.table_delivery_plan.rowCount()
        self.table_delivery_plan.insertRow(row)

        # -------------------------------------------------------------
        # 1. 대상 품목 (0번 칸) 및 좌측 테이블(table_order_detail) 인덱스 추적
        # -------------------------------------------------------------
        source_idx = -1
        item_nm = "품목지정안됨"
        
        # [A] DB에서 로드하는 경우 (order_detail_id로 좌측 테이블 행 추적)
        if 'order_detail_id' in data:
            target_id = str(data['order_detail_id'])
            for r in range(self.table_order_detail.rowCount()):
                role_data = self.table_order_detail.item(r, 0).data(Qt.ItemDataRole.UserRole)
                if str(role_data) == target_id:
                    source_idx = r
                    # 좌측 테이블 2번 컬럼(품종명)을 가져옵니다
                    item_nm = self.table_order_detail.item(r, 2).text() 
                    break
                    
        # [B] UI에서 신규 배송지를 추가하는 경우 (source_idx를 직접 전달받음)
        elif 'source_idx' in data:
            source_idx = data['source_idx']
            if self.table_order_detail.item(source_idx, 2):
                item_nm = self.table_order_detail.item(source_idx, 2).text()

        col0_item = QTableWidgetItem(item_nm)
        if source_idx != -1:
            # 📍 [핵심] 저장 시 추적을 위해 UserRole에 좌측 테이블 인덱스 바인딩
            col0_item.setData(Qt.ItemDataRole.UserRole, source_idx) 
        self.table_delivery_plan.setItem(row, 0, col0_item)

        # -------------------------------------------------------------
        # 2. 일반 데이터 세팅 (1번 ~ 6번 칸)
        # -------------------------------------------------------------
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 1: 예정일
        planned_dt = data.get('planned_dt') or data.get('delivery_dt', today_str)
        self.table_delivery_plan.setItem(row, 1, QTableWidgetItem(str(planned_dt)))
        
        # 2: 받는분
        rcv_name = data.get('rcv_name') or data.get('receiver_nm', '')
        self.table_delivery_plan.setItem(row, 2, QTableWidgetItem(str(rcv_name)))
        
        # 3: 연락처
        rcv_tel = data.get('rcv_tel') or data.get('mobile', '')
        self.table_delivery_plan.setItem(row, 3, QTableWidgetItem(str(rcv_tel)))
        
        # 4: 주소
        rcv_addr = data.get('rcv_addr') or data.get('address', '')
        self.table_delivery_plan.setItem(row, 4, QTableWidgetItem(str(rcv_addr)))
        
        # 5: 수량 (우측 정렬)
        qty = data.get('dlvry_qty') or data.get('qty', '1')
        qty_item = QTableWidgetItem(str(qty))
        qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table_delivery_plan.setItem(row, 5, qty_item)
        
        # 6: 배송메시지
        dlvry_msg = data.get('dlvry_msg') or data.get('message', '')
        self.table_delivery_plan.setItem(row, 6, QTableWidgetItem(str(dlvry_msg)))
        
        # -------------------------------------------------------------
        # 3. 위젯 및 히든 데이터 세팅 (7번 ~ 8번 칸)
        # -------------------------------------------------------------
        # 7: 삭제 버튼 (기존 메소드 호출)
        if hasattr(self, 'insert_plan_delete_button'):
            self.insert_plan_delete_button(row, 7)
        else:
            btn_del = QPushButton("❌")
            btn_del.setFixedSize(30, 25)
            # btn_del.clicked.connect(...) # 삭제 로직 연결 필요시 추가
            self.table_delivery_plan.setCellWidget(row, 7, btn_del)
            
        # 8: 발송인 정보 (히든 컬럼) - 저장 시 .split('|') 에 대비
        snd_name = data.get('snd_name', '')
        snd_tel = data.get('snd_tel', '')
        snd_addr = data.get('snd_addr', '')
        bundle = f"{snd_name}|{snd_tel}|{snd_addr}|{dlvry_msg}"
        self.table_delivery_plan.setItem(row, 8, QTableWidgetItem(bundle))

        # -------------------------------------------------------------
        # 4. 텍스트 정렬 (수량 5번 제외하고 모두 가운데 정렬)
        # -------------------------------------------------------------
        for col in [0, 1, 2, 3, 4, 6, 8]:
            it = self.table_delivery_plan.item(row, col)
            if it:
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # 📍 중앙 테이블에 상품이 추가될 때마다 호출하여 콤보박스 갱신
    def update_delivery_target_combo(self):
        """[📍 신경망] 중앙 품목 리스트를 우측 선택기에 동기화 (배송방식 실시간 병기)"""
        # 현재 선택된 인덱스 기억 (갱신 시 풀림 방지)
        current_idx = self.combo_delivery_target.currentIndex()
        
        self.combo_delivery_target.blockSignals(True)
        self.combo_delivery_target.clear()
        
        for r in range(self.table_order_detail.rowCount()):
            # 인덱스 규격: 2:품종, 4:사이즈, 5:수량, 10:배송방식
            v_nm = self.table_order_detail.item(r, 2).text()
            s_nm = self.table_order_detail.item(r, 4).text()
            qty = self.table_order_detail.item(r, 5).text()
            
            # 중앙 테이블 10번 컬럼에서 현재 선택된 배송방식 명칭 확보
            method_widget = self.table_order_detail.cellWidget(r, 10)
            method_nm = method_widget.currentText() if method_widget else "미정"
            
            # 텍스트 예시: [1] 신고배(12과) - 5개 【택배】
            item_text = f"[{r+1}] {v_nm}({s_nm}) - {qty}개 【{method_nm}】"
            self.combo_delivery_target.addItem(item_text, userData=r)
            
        # 기존 선택 유지
        if current_idx < self.combo_delivery_target.count():
            self.combo_delivery_target.setCurrentIndex(current_idx)
        self.combo_delivery_target.blockSignals(False)

    def on_delivery_target_changed(self):
        """[Action] 대상 품목 변경 시 레이어 가변 노출 및 자동 완성"""
        if not hasattr(self, 'edit_rcv_qty'): return 

        target_row = self.combo_delivery_target.currentData()
        if target_row is None: return

        # 1. 정보 추출
        method_widget = self.table_order_detail.cellWidget(target_row, 10)
        method_cd = method_widget.currentData() if method_widget else ""
        item_qty = self.table_order_detail.item(target_row, 5).text() if self.table_order_detail.item(target_row, 5) else ""
        orderer_nm = self.detail_cust_nm.text().strip()
        orderer_tel = self.detail_cust_tel.text().strip()

        # 2. 📍 [레이어 및 데이터 제어]
        if method_cd in ['LO010100', 'LO010400']: # 방문/직배
            self.edit_rcv_nm.setText(orderer_nm)
            self.edit_rcv_tel.setText(orderer_tel)
            self.edit_rcv_qty.setText(item_qty)
        elif method_cd == 'LO010200': # 택배
            self.edit_rcv_nm.clear(); self.edit_rcv_tel.clear(); self.edit_rcv_qty.clear(); self.edit_rcv_addr.clear()
        else: # 화물/기타 (정보 유지)
            self.edit_rcv_qty.clear()
            self.edit_rcv_qty.setFocus()

        # 3. 📍 [가변 노출] 택배(LO010200)일 때만 발송인 레이어 활성화
        self.sender_group.setVisible(method_cd == 'LO010200')
        if method_cd == 'LO010200':
            self.edit_snd_nm.setText(orderer_nm)
            self.edit_snd_tel.setText(orderer_tel)

        # 4. 📍 [주소창 제어] 방문수령(LO010100) 주소창 레이어 무력화
        is_pickup = (method_cd == 'LO010100')
        self.edit_rcv_addr.setEnabled(not is_pickup)
        if is_pickup:
            self.edit_rcv_addr.clear()
            self.edit_rcv_addr.setPlaceholderText("방문수령: 주소 입력 불필요")
            self.edit_rcv_addr.setStyleSheet(MainStyles.INPUT_LEFT + "background-color: #F7FAFC; color: #A0AEC0;")
        else:
            method_nm = method_widget.currentText() if method_widget else "배송"
            self.edit_rcv_addr.setPlaceholderText(f"{method_nm} 주소를 입력하세요")
            self.edit_rcv_addr.setStyleSheet(MainStyles.INPUT_LEFT)

        self.adjust_input_tab_height()

    # 📍 단건 등록 처리
    def add_delivery_plan_from_form(self):
        """[📍최종본] 비밀 주머니(UserRole) 활용 정밀 수량 검증 및 데이터 등록"""
        # 1. 대상 선택 확인 (중앙 테이블의 원본 Row Index 추출)
        target_row = self.combo_delivery_target.currentData()
        if target_row is None:
            QMessageBox.warning(self, "알림", "배송 대상 품목을 먼저 선택해 주세요.")
            return

        # 2. 데이터 수집 및 정제
        import re
        rcv_nm = self.edit_rcv_nm.text().strip()
        rcv_tel = self.edit_rcv_tel.text().strip()
        rcv_qty_str = self.edit_rcv_qty.text().strip()
        rcv_addr = self.edit_rcv_addr.text().strip()
        dlv_date = self.edit_delivery_date.date().toString("yyyy-MM-dd")
        
        # [품목명 정제] "[1] 신고배 - 상품" -> "신고배 - 상품" 추출
        full_text = self.combo_delivery_target.currentText().split(" 【")[0]
        target_item_nm = re.sub(r'^\[\d+\]\s*', '', full_text)
        
        # 3. 배송 방식 확인 (중앙 테이블 10번 컬럼)
        method_widget = self.table_order_detail.cellWidget(target_row, 10)
        method_cd = method_widget.currentData() if method_widget else ""
        method_nm = method_widget.currentText() if method_widget else "미정"

        # 4. [검증 1] 주소 필수 체크 (방문 LO010100 제외 전원 체크)
        if method_cd != 'LO010100' and not rcv_addr:
            QMessageBox.warning(self, "주소 누락", f"【{method_nm}】 방식은 배송지 주소가 필수입니다.")
            self.edit_rcv_addr.setFocus()
            return

        # 5. [검증 2] 수량 및 숫자 체크
        try:
            new_qty = int(rcv_qty_str) if rcv_qty_str else 0
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "수량 칸에 숫자만 정확히 입력해 주세요.")
            self.edit_rcv_qty.setFocus()
            return

        if not rcv_nm or new_qty <= 0:
            QMessageBox.warning(self, "알림", "받는분 성함과 유효한 수량을 입력해 주세요.")
            return

        # 6. 📍 [검증 3] 수량 초과 방지 (비밀 주머니 데이터 대조)
        order_qty_item = self.table_order_detail.item(target_row, 5)
        if not order_qty_item: return
        
        total_ordered_qty = int(re.sub(r'[^0-9]', '', order_qty_item.text()))
        
        # 현재 계획 테이블을 순회하며 '동일한 원본 행(Index)'에서 온 수량 합산
        current_planned_sum = 0
        for r in range(self.table_delivery_plan.rowCount()):
            # 📍 [교정] 텍스트가 아닌 UserRole(원본 행 번호)을 꺼내서 비교
            source_idx = self.table_delivery_plan.item(r, 0).data(Qt.ItemDataRole.UserRole)
            qty_item = self.table_delivery_plan.item(r, 5) 
            if qty_item and qty_item.text().strip():
                # '2박스', ' 3 ' 처럼 글자나 공백이 섞여 있어도 순수 숫자만 추출
                num_str = re.sub(r'[^0-9]', '', qty_item.text())
                current_planned_sum += int(num_str) if num_str else 0

        if current_planned_sum + new_qty > total_ordered_qty:
            remain = total_ordered_qty - current_planned_sum
            QMessageBox.critical(self, "수량 초과", 
                               f"'{target_item_nm}'의 배정 가능 수량을 초과했습니다.\n\n"
                               f"총 주문: {total_ordered_qty}개\n"
                               f"현재 배정: {current_planned_sum}개\n"
                               f"남은 여유: {remain}개")
            return

        # 7. 데이터 등록 (8컬럼 표준 규격)
        msg = self.edit_rcv_msg.text().strip()
        snd_nm = self.edit_snd_nm.text().strip()
        snd_tel = self.edit_snd_tel.text().strip()
        snd_addr = self.edit_snd_addr.text().strip()
        sender_data = f"{snd_nm}|{snd_tel}|{snd_addr}|{msg}" 

        row = self.table_delivery_plan.rowCount()
        self.table_delivery_plan.insertRow(row)
        
        # 0번 컬럼 아이템 생성 및 원본 인덱스 은닉
        item_nm_widget = QTableWidgetItem(target_item_nm)
        item_nm_widget.setData(Qt.ItemDataRole.UserRole, target_row) # 주머니에 행번호 보관
        item_nm_widget.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table_delivery_plan.setItem(row, 0, item_nm_widget)

        # 컬럼 순서에 따른 배치
        # 📍 단건 등록 시 스타일 통일 (add_delivery_plan_from_form 내부)
        def set_align_item(col, text, align=Qt.AlignmentFlag.AlignCenter):
            it = QTableWidgetItem(str(text))            
            self.table_delivery_plan.setItem(row, col, it)
        set_align_item(1, dlv_date)   # 예정일
        set_align_item(2, rcv_nm)     # 받는분
        set_align_item(3, rcv_tel)    # 연락처
        set_align_item(4, rcv_addr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # 주소
        set_align_item(5, new_qty)    # 수량
        set_align_item(6, msg, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # 배송메시지

        # 삭제 버튼 (7번 컬럼) 및 Hidden Sender (7번 컬럼)
        self.insert_plan_delete_button(row, 7)
        self.table_delivery_plan.setItem(row, 8, QTableWidgetItem(sender_data))

        # 8. 정보 유지 및 포커스
        self.edit_rcv_qty.clear()
        self.edit_rcv_qty.setFocus()

    # 📍 우측 판넬의 배송리스트 삭제 버튼 생성 (MainStyles.BTN_DANGER 적용)
    def insert_plan_delete_button(self, row, col):
        """[UI] 삭제 버튼 식립 (MainStyles.BTN_DANGER 적용)"""
        btn = QPushButton("삭제")
        btn.setStyleSheet(MainStyles.BTN_DANGER) # 📍 레드 스타일
        btn.setFixedSize(50, 26)
        btn.clicked.connect(self.handle_plan_row_delete)
        
        container = QWidget()
        lay = QHBoxLayout(container); lay.addWidget(btn); lay.setContentsMargins(0,0,0,0); lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_delivery_plan.setCellWidget(row, col, container)

    def handle_plan_row_delete(self):
        """[Action] 배송 계획 행 삭제 실행"""
        button = self.sender()
        if not button: return
        pos = button.parentWidget().mapTo(self.table_delivery_plan, button.pos())
        index = self.table_delivery_plan.indexAt(pos)
        if index.isValid():
            self.table_delivery_plan.removeRow(index.row())

    #  마스터용 시퀀스 생성: 주문번호(ORD20260101-001) 또는 판매번호(20260101-01) 추출

    def save_entire_order(self):
        """
        [📍아토스 최종 통합 엔진 V6] - 파편화 제로, 단일 파일 완결본
        1. 신규/수정 모드 완벽 분기 (Wipe & Replace)
        2. GUEST 초기화 방어막 추가 (수정 시 ID 보존)
        3. 중앙 DB 커넥션 사용으로 Locked 에러 차단
        4. 배송비/입금액 등 회계 정밀도 100% 매칭
        5. 다이(FR) 기준 재고 UPSERT 완벽 적용
        """
        import re
        from datetime import datetime

        # =================================================================
        # 1. [검문소] 사전 데이터 검증
        # =================================================================
        cust_nm = self.detail_cust_nm.text().strip()
        cust_id = getattr(self, 'current_cust_id', None) 
        
        # 📍 [강력한 통제] 고객 ID가 없으면 저장을 원천 차단하고 검색을 유도합니다.
        if not cust_id or cust_id == 'GUEST':
            QMessageBox.warning(self, "고객 지정 필요", 
                "주문자(고객) 정보가 지정되지 않았습니다.\n"
                "성함 옆의 [🔍 돋보기] 버튼을 눌러 고객을 검색하거나 신규 등록해 주십시오.")
            # 고객 이름 입력창으로 포커스 이동
            self.detail_cust_nm.setFocus()
            return
        
        if not cust_nm:
            QMessageBox.warning(self, "정합성 위반", "주문자 성함이 누락되었습니다.")
            return

        detail_row_count = self.table_order_detail.rowCount()
        if detail_row_count == 0:
            QMessageBox.warning(self, "정합성 위반", "상세 품목이 없는 주문은 기록할 수 없습니다.")
            return

        # [수량 정합성 체크]
        for r in range(detail_row_count):
            order_item = self.table_order_detail.item(r, 5)
            order_qty = int(float(re.sub(r'[^0-9.]', '', order_item.text() or "0"))) if order_item else 0
            item_nm = self.table_order_detail.item(r, 2).text() if self.table_order_detail.item(r, 2) else "미지정"
            
            planned_sum = 0
            for p in range(self.table_delivery_plan.rowCount()):
                if self.table_delivery_plan.item(p, 0).data(Qt.ItemDataRole.UserRole) == r:
                    qty_item = self.table_delivery_plan.item(p, 5) 
                    if qty_item:
                        planned_sum += int(re.sub(r'[^0-9]', '', qty_item.text() or "0"))
            
            if order_qty != planned_sum:
                QMessageBox.critical(self, "수량 불일치", 
                    f"품목 [{item_nm}]의 수량이 맞지 않습니다.\n\n"
                    f"주문량: {order_qty} / 배송지 합계: {planned_sum}")
                return

        # =================================================================
        # 2. 중앙 DB 연결 활용 및 트랜잭션
        # =================================================================
        cursor = None 
        try:
            print("\n" + "="*50)
            print("🚀 [저장 시작] 무결성 통합 트랜잭션 가동")

            # 📍 중앙 커넥션 획득 및 락(Lock) 개시
            cursor = self.db.conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("BEGIN IMMEDIATE TRANSACTION")

            today_str = datetime.now().strftime("%Y%m%d")
            today_dash = datetime.now().strftime("%Y-%m-%d")
            now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reg_id = getattr(self, 'user_id', 'SYSTEM') 

            def to_f(v): return float(re.sub(r'[^0-9.]', '', v or '0'))
            
            tot_amt = to_f(self.detail_tot_order_amt.text())
            ship_fee = to_f(self.detail_tot_ship_fee.text())
            pre_pay = to_f(self.detail_pre_pay_amt.text())
            season_cd = self.detail_season_type_cd.currentData()

            is_edit_mode = not getattr(self, 'is_new_order_mode', True)
            existing_order_no = getattr(self, 'current_order_no', None)

            if is_edit_mode and existing_order_no:
                # ---------------------------------------------------------
                # [수정 모드 (UPDATE & WIPE)]
                # ---------------------------------------------------------
                order_no = existing_order_no
                
                # 📍 [GUEST 방어막] 혹시라도 ID를 놓쳤다면 기존 마스터에서 복원
                if cust_id == 'GUEST':
                    cursor.execute("SELECT custm_id FROM t_order_master WHERE order_no = ?", (order_no,))
                    old_cust_row = cursor.fetchone()
                    if old_cust_row and old_cust_row[0]:
                        cust_id = old_cust_row[0]
                        self.current_cust_id = cust_id
                
                # [방어막] 이미 출고된 주문 수정 금지
                cursor.execute("SELECT stock_status, sales_no FROM t_order_master WHERE order_no = ?", (order_no,))
                row = cursor.fetchone()
                if not row: raise Exception("원본 주문 데이터를 찾을 수 없습니다.")
                
                stock_status, sales_no = row
                if stock_status == 'Y':
                    raise Exception("이미 출고(포장) 처리가 완료된 주문입니다. 수정을 원하시면 '주문 취소' 후 다시 등록해 주십시오.")

                print(f"🔍 [1/4] 기존 주문({order_no}) Wipe & Replace 가동...")

                # 📍 기존 예약 재고 복구 (-) 및 취소 로그 기록
                cursor.execute("""
                    SELECT item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, qty 
                    FROM t_order_detail WHERE order_no = ?
                """, (order_no,))
                
                for old_d in cursor.fetchall():
                    o_icd, o_vcd, o_gcd, o_scd, o_wt, o_yr, o_qty = old_d
                    
                    cursor.execute("""
                        UPDATE t_stock_master 
                        SET reserved_qty = reserved_qty - ?
                        WHERE farm_cd=? AND item_cd=? AND variety_cd=? AND grade_cd=? AND size_cd=? AND weight=? AND harvest_year=?
                    """, (o_qty, self.farm_cd, o_icd, o_vcd, o_gcd, o_scd, o_wt, o_yr))

                    cursor.execute("""
                        INSERT INTO t_stock_log (
                            farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight,
                            io_type, qty, remark, reg_id, reg_dt
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'CANCEL_HOLD', ?, ?, ?, ?)
                    """, (self.farm_cd, o_icd, o_vcd, o_yr, o_gcd, o_scd, o_wt, o_qty, f"주문수정전 복구:{order_no}", reg_id, now_dt))

                # 하위 데이터 소각 (WIPE)
                if sales_no:
                    cursor.execute("DELETE FROM t_sales_delivery WHERE sales_no = ?", (sales_no,))
                    cursor.execute("DELETE FROM t_sales_detail WHERE sales_no = ?", (sales_no,))
                cursor.execute("DELETE FROM t_order_delivery WHERE order_no = ?", (order_no,))
                cursor.execute("DELETE FROM t_order_detail WHERE order_no = ?", (order_no,))

                # 마스터 갱신 (UPDATE)
                cursor.execute("""
                    UPDATE t_order_master SET 
                        custm_id=?, tot_order_amt=?, tot_ship_fee=?, tot_pay_amt=?, 
                        rmk=?, mod_id=?, mod_dt=?, season_type_cd=?, pre_pay_amt=?
                    WHERE order_no=?
                """, (cust_id, tot_amt, ship_fee, pre_pay, self.detail_rmk.text(), reg_id, now_dt, season_cd, pre_pay, order_no))

                if sales_no:
                    cursor.execute("""
                        UPDATE t_sales_master SET 
                            custm_id=?, tot_sales_amt=?, tot_ship_fee=?, tot_item_amt=?, 
                            tot_paid_amt=?, tot_unpaid_amt=?, rmk=?, mod_id=?, mod_dt=?
                        WHERE sales_no=?
                    """, (cust_id, tot_amt + ship_fee, ship_fee, tot_amt, pre_pay, (tot_amt + ship_fee) - pre_pay, self.detail_rmk.text(), reg_id, now_dt, sales_no))

            else:
                # ---------------------------------------------------------
                # [신규 모드 (INSERT)]
                # ---------------------------------------------------------
                print("🔍 [1/4] 신규 주문 채번 및 마스터 기록 시도...")
                order_no = self.get_next_seq(cursor, "t_order_master", "order_no", f"ORD{today_str}", 3)
                sales_no = self.get_next_seq(cursor, "t_sales_master", "sales_no", today_str, 2)
                
                cursor.execute("""
                    INSERT INTO t_order_master (
                        order_no, farm_cd, order_dt, custm_id, status_cd, stock_status,
                        tot_order_amt, tot_ship_fee, tot_pay_amt, rmk, reg_id, reg_dt,
                        season_type_cd, pre_pay_amt, sales_no
                    ) VALUES (?, ?, ?, ?, '10', 'N', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_no, self.farm_cd, today_str, cust_id, tot_amt, ship_fee, pre_pay, 
                      self.detail_rmk.text(), reg_id, now_dt, season_cd, pre_pay, sales_no))

                cursor.execute("""
                    INSERT INTO t_sales_master (
                        sales_no, farm_cd, sales_dt, sales_tp, custm_id, tot_sales_amt,
                        tot_ship_fee, tot_item_amt, tot_paid_amt, tot_unpaid_amt, status_cd,
                        rmk, reg_id, reg_dt, order_no
                    ) VALUES (?, ?, ?, 'NORMAL', ?, ?, ?, ?, ?, ?, '10', ?, ?, ?, ?)
                """, (sales_no, self.farm_cd, today_str, cust_id, tot_amt + ship_fee, ship_fee, 
                      tot_amt, pre_pay, (tot_amt + ship_fee) - pre_pay, self.detail_rmk.text(), reg_id, now_dt, order_no))

            # =================================================================
            # 3. 상세 루프 (재고 Hold 및 로그 기록 통합)
            # =================================================================
            print("🔍 [2/4] 상세 내역 및 재고 로그 기록 시도...")
            detail_map = {} 
            for r in range(detail_row_count):
                ord_det_id = f"{order_no}-{str(r+1).zfill(2)}"
                sal_det_no = f"{sales_no}-S{str(r+1).zfill(2)}"
                detail_map[r] = (ord_det_id, sal_det_no)

                bundle_item = self.table_order_detail.item(r, 12)
                if not bundle_item: continue
                
                bundle = bundle_item.text().split('|')
                i_cd, v_cd, g_cd, s_cd, wh_cd = bundle
                
                h_year = self.table_order_detail.item(r, 0).text()
                weight = to_f(self.table_order_detail.item(r, 1).text())
                qty = to_f(self.table_order_detail.item(r, 5).text())
                u_price = to_f(self.table_order_detail.item(r, 6).text())
                
                row_ship_item = self.table_order_detail.item(r, 8)
                row_ship_fee = to_f(row_ship_item.text()) if row_ship_item else 0
                
                method_combo = self.table_order_detail.cellWidget(r, 10)
                method_cd = method_combo.currentData() if method_combo else 'LO010100'

                # [1] 주문 상세 내역 저장
                cursor.execute("""
                    INSERT INTO t_order_detail (
                        order_detail_id, order_no, farm_cd, item_cd, variety_cd, grade_cd, size_cd,
                        weight, qty, unit_price, item_amt, wh_cd, reg_id, reg_dt, dlvry_tp, harvest_year
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ord_det_id, order_no, self.farm_cd, i_cd, v_cd, g_cd, s_cd,
                      weight, qty, u_price, qty * u_price, wh_cd, reg_id, now_dt, method_cd, h_year))

                # [2] 판매 상세 내역 저장
                cursor.execute("""
                    INSERT INTO t_sales_detail (
                        sale_detail_no, sales_no, farm_cd, item_cd, variety_cd, grade_cd, size_cd,
                        qty, unit_price, tot_item_amt, ship_fee, tot_sale_amt, dlvry_tp, order_detail_id, reg_id, reg_dt, wh_cd
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (sal_det_no, sales_no, self.farm_cd, i_cd, v_cd, g_cd, s_cd,
                      qty, u_price, qty * u_price, row_ship_fee, (qty * u_price) + row_ship_fee, method_cd, ord_det_id, reg_id, now_dt, wh_cd))

                # [3] 단일 바구니 방식 재고 마스터 예약 (UPSERT)
                cursor.execute("""
                    SELECT MIN(storage_dt) FROM t_stock_master 
                    WHERE farm_cd=? AND harvest_year=? AND item_cd=? AND variety_cd=? AND grade_cd=? AND size_cd=?
                """, (self.farm_cd, h_year, i_cd, v_cd, g_cd, s_cd))
                dt_row = cursor.fetchone()
                target_dt = dt_row[0] if dt_row and dt_row[0] else today_dash

                cursor.execute("""
                    INSERT OR IGNORE INTO t_stock_master (
                        farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, 
                        harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                """, (self.farm_cd, wh_cd, i_cd, v_cd, g_cd, s_cd, weight, h_year, target_dt, reg_id))

                cursor.execute("""
                    UPDATE t_stock_master 
                    SET reserved_qty = reserved_qty + ?, mod_id = ?, mod_dt = ?
                    WHERE farm_cd = ? AND variety_cd = ? AND grade_cd = ? AND size_cd = ? AND harvest_year = ? AND storage_dt = ?
                """, (qty, reg_id, now_dt, self.farm_cd, v_cd, g_cd, s_cd, h_year, target_dt))

                # [4] 재고 변동 로그 기록
                cursor.execute("""
                    INSERT INTO t_stock_log (
                        farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight,
                        io_type, qty, parent_raw_size, remark, reg_id, reg_dt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'HOLD', ?, ?, ?, ?, ?)
                """, (self.farm_cd, i_cd, v_cd, h_year, g_cd, s_cd, weight, qty, None, f"주문예약:{order_no}", reg_id, now_dt))

            # =================================================================
            # 4. [배송 루프] 인덱스 고도화 및 확장 저장 (N건 풀기)
            # =================================================================
            print("🔍 [3/4] t_order_delivery / t_dlvry_detail 기록 시도...")
            dlvry_counters = {} 
            
            for p in range(self.table_delivery_plan.rowCount()):
                source_idx = self.table_delivery_plan.item(p, 0).data(Qt.ItemDataRole.UserRole)
                ord_det_id, sal_det_no = detail_map[source_idx]
                
                dlvry_counters[ord_det_id] = dlvry_counters.get(ord_det_id, 0) + 1
                order_dlvry_id = f"{ord_det_id}-P{dlvry_counters[ord_det_id]:02d}"

                sender_item = self.table_delivery_plan.item(p, 8)
                if not sender_item: continue
                s_nm, s_tel, s_addr, d_msg = sender_item.text().split('|')

                r_nm = self.table_delivery_plan.item(p, 2).text() or ""
                r_tel = self.table_delivery_plan.item(p, 3).text() or ""
                r_addr = self.table_delivery_plan.item(p, 4).text() or ""
                p_qty = int(self.table_delivery_plan.item(p, 5).text() or "1")
                p_dt = self.table_delivery_plan.item(p, 1).text() or today_dash
                
                method_combo_main = self.table_order_detail.cellWidget(source_idx, 10)
                method_cd = method_combo_main.currentData() if method_combo_main else 'LO010100'

                # [A] t_order_delivery 저장
                cursor.execute("""
                    INSERT INTO t_order_delivery (
                        order_dlvry_id, order_no, farm_cd, order_detail_id, snd_name, snd_tel, snd_addr,
                        rcv_name, rcv_tel, rcv_addr, dlvry_qty, dlvry_msg, delivery_tp_cd, planned_dt, reg_dt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_dlvry_id, order_no, self.farm_cd, ord_det_id, s_nm, s_tel, s_addr, 
                      r_nm, r_tel, r_addr, p_qty, d_msg, method_cd, p_dt, now_dt))

                # [B] t_dlvry_detail (실제 송장용 박스 분할) 저장
                loop_cnt = p_qty if method_cd == 'LO010200' else 1
                box_qty = 1 if method_cd == 'LO010200' else p_qty

                for i in range(loop_cnt):
                    dlvry_no = f"{sal_det_no}-P{dlvry_counters[ord_det_id]:02d}-D{i+1:03d}"
                    cursor.execute("""
                        INSERT INTO t_sales_delivery (
                            dlvry_no, sale_detail_no, sales_no, farm_cd,
                            snd_name, snd_tel, snd_addr, rcv_name, rcv_tel, rcv_addr,
                            dlvry_qty, dlvry_msg, reg_id, reg_dt
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (dlvry_no, sal_det_no, sales_no, self.farm_cd,
                          s_nm, s_tel, s_addr, r_nm, r_tel, r_addr, 
                          box_qty, d_msg, reg_id, now_dt))

            # 📍 커넥션을 이용해 일괄 커밋
            print("🔍 [4/4] 최종 커밋(Commit) 중...")
            self.db.conn.commit()
            
            action_nm = "수정" if (is_edit_mode and existing_order_no) else "저장"
            QMessageBox.information(self, "작전 완료", f"주문서[{order_no}]가 안전하게 {action_nm}되었습니다.")
            
            self.initiate_new_order() 

        except Exception as e:
            if getattr(self, 'db', None) and getattr(self.db, 'conn', None):
                self.db.conn.rollback()
            print(f"❌ [에러 발생] 유형: {type(e).__name__}")
            print(f"❌ [상세 내용] {str(e)}")
            QMessageBox.critical(self, "정합성 위반", f"DB 기록 중 사고가 발생했습니다:\n{e}")
        finally:
            if cursor: 
                cursor.close()
            print("="*50 + "\n")

    def get_next_seq(self, cursor, table, col, prefix, seq_len):
        """[Utility] 날짜별 고유 시퀀스 채번"""
        cursor.execute(f"SELECT MAX({col}) FROM {table} WHERE {col} LIKE '{prefix}-%'")
        res = cursor.fetchone()[0]
        if res:
            last_seq = int(res.split('-')[-1])
            return f"{prefix}-{str(last_seq + 1).zfill(seq_len)}"
        return f"{prefix}-{str(1).zfill(seq_len)}"

    #################################################################################3333
    # 기능구현
    ###################################################################################33
    # 1. 뱃지의 토글기능구현
    def toggle_panel(self, direction):
        """[📍배타적 토글] 한쪽이 열리면 반대쪽은 강제 종료"""
        if direction == "LEFT":
            # 1. 우측이 열려있다면 먼저 닫음 (Exclusive)
            if self._right_visible:
                self.close_right_panel()

            # 2. 좌측 토글 수행
            if not self._left_visible:
                self.open_left_panel()
            else:
                self.close_left_panel()

        elif direction == "RIGHT":
            # 1. 좌측이 열려있다면 먼저 닫음 (Exclusive)
            if self._left_visible:
                self.close_left_panel()

            # 2. 우측 토글 수행
            if not self._right_visible:
                self.open_right_panel()
            else:
                self.close_right_panel()

    # 1. 좌측 열기
    def open_left_panel(self):
        self.left_anim.setStartValue(self.left_panel.pos())
        self.left_anim.setEndValue(QPoint(0, 0))
        self.left_anim.start()
        # [수정] 시작(0), 끝(left_width), 글자("<") 3개 인자를 정확히 전달
        self._animate_handle(self.btn_left_handle, 0, self.left_width, "<")
        self._left_visible = True

    # 2. 좌측 닫기
    def close_left_panel(self):
        self.left_anim.setStartValue(self.left_panel.pos())
        self.left_anim.setEndValue(QPoint(-self.left_width, 0))
        self.left_anim.start()
        # [수정] 시작(left_width), 끝(0), 글자(">") 3개 인자를 정확히 전달
        self._animate_handle(self.btn_left_handle, self.left_width, 0, ">")
        self._left_visible = False

    # 3. 우측 열기
    def open_right_panel(self):
        target_x = self.width() - self.right_width
        self.right_anim.setStartValue(self.right_panel.pos())
        self.right_anim.setEndValue(QPoint(target_x, 0))
        self.right_anim.start()
        # [수정] 현재위치(width-20)에서 목표위치(target_x-20)로 이동
        self._animate_handle(self.btn_right_handle, self.width() - 20, target_x - 20, ">")
        self._right_visible = True

    # 4. 우측 닫기
    def close_right_panel(self):
        target_x = self.width() - self.right_width
        self.right_anim.setStartValue(self.right_panel.pos())
        self.right_anim.setEndValue(QPoint(self.width(), 0))
        self.right_anim.start()
        # [수정] 목표위치(target_x-20)에서 다시 원래위치(width-20)로 복귀
        self._animate_handle(self.btn_right_handle, target_x - 20, self.width() - 20, "<")
        self._right_visible = False

    def _animate_handle(self, target, start_x, end_x, text):
        """[Helper] 엣지 핸들의 위치와 텍스트를 애니메이션으로 변경"""
        anim = QPropertyAnimation(target, b"pos")
        anim.setDuration(350)
        anim.setStartValue(QPoint(start_x, 300)) # 높이는 300 고정
        anim.setEndValue(QPoint(end_x, 300))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        target.setText(text)
        # 가비지 컬렉션 방지
        setattr(self, f"handle_anim_{id(target)}", anim)

    # 토글 리사이즈 구현(좌/우 토글이 사라지고 나타날때 사이즈 구현)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not getattr(self, '_ui_ready', False): return
        self.update_geometries()

    def update_geometries(self):
        """[📍지능형 배치] 창 크기에 따라 모든 위젯 위치 보정"""
        curr_w = self.width()
        curr_h = self.height()
        
        #self.main_bg.resize(curr_w, curr_h)
        self.left_panel.setFixedHeight(curr_h)
        self.right_panel.setFixedHeight(curr_h)

        # 좌측 판넬 주차
        if self._left_visible:
            self.left_panel.move(0, 0)
            self.btn_left_handle.move(self.left_width, 300)
        else:
            self.left_panel.move(-self.left_width, 0)
            self.btn_left_handle.move(0, 300)

        # 우측 판넬 주차 (창 너비 기준 상대 좌표)
        if self._right_visible:
            target_x = max(0, curr_w - self.right_width)
            self.right_panel.move(target_x, 0)
            self.btn_right_handle.move(max(0, target_x - 20), 300)
        else:
            self.right_panel.move(curr_w, 0)
            self.btn_right_handle.move(curr_w - 20, 300)

    # 테이블 특정 셀에 공통 코드 기반 콤보박스 배치
    def set_table_combo(self, table, row, col, parent_cd, default_val=None):
        """
        [Utility] 테이블 특정 셀에 공통 코드 기반 콤보박스 배치
        - table: 대상 QTableWidget
        - parent_cd: 공통 코드 부모값 (예: 'LO01')
        - default_val: 초기 선택될 코드값
        """
        combo = QComboBox()
        combo.setStyleSheet(MainStyles.COMBO)
        
        # 1. 공통 코드 로드 및 데이터 바인딩
        codes = self.code_manager.get_common_codes(parent_cd)
        for r in codes:
            d = dict(r)
            combo.addItem(d.get('code_nm'), d.get('code_cd'))
            
        # 2. 초기값 설정 (findData 활용)
        if default_val:
            idx = combo.findData(default_val)
            if idx >= 0: combo.setCurrentIndex(idx)
            
        # 3. 테이블 식립
        table.setCellWidget(row, col, combo)
        return combo # 필요 시 시그널 연결을 위해 반환
    
    def load_code_to_combo(self, combo, parent_cd):
        """
        [Utility] DB에서 공통 코드를 가져와 콤보박스에 주입
        - combo: 대상 QComboBox 위젯
        - parent_cd: 조회할 부모 코드
        """
        # 1. 기존 항목 제거 (중복 방지)
        combo.clear()
        
        try:
            # 2. CodeManager를 통해 코드 리스트 확보
            # 이 리스트의 각 요소는 sqlite3.Row 객체입니다.
            code_list = self.code_manager.get_common_codes(parent_cd)
            
            if not code_list:
                return

            # 3. 리스트를 순회하며 콤보박스에 항목 추가
            for code_row in code_list:
                # [📍 핵심 교정] Row 객체를 dict로 변환해야 .get() 사용이 가능합니다.
                code_dict = dict(code_row)
                
                # 명칭(code_nm)은 사용자에게 보여주고, 코드(code_cd)는 내부 데이터로 저장
                display_name = code_dict.get('code_nm')
                code_value = code_dict.get('code_cd')
                
                combo.addItem(display_name, code_value)
            
            # 4. 모든 콤보박스에 공통 스타일 적용
            combo.setStyleSheet(MainStyles.COMBO)
            
        except Exception as e:
            # 에러 발생 시 상세 내용을 출력하여 추적을 용이하게 함
            print(f"[Critical Error] 콤보박스 데이터 수혈 실패 (Code: {parent_cd}): {e}")

    # --- [📍 토글 로직 추가] ---
    def toggle_input_area(self):
        """입력 영역을 접어 테이블 공간을 극대화합니다."""
        if self.input_area_container.isVisible():
            self.input_area_container.hide()
            self.btn_toggle_input.setText("🔽 입력창 펴기")
        else:
            self.input_area_container.show()
            self.btn_toggle_input.setText("🔼 입력창 접기")

    # [기능] 주소, 배송메시지등 돋보기 기능
    def update_detail_viewer(self, row, col):
        """사용자가 선택한 행의 주소와 메시지를 하단에 크게 출력"""
        try:
            # 안전하게 데이터 추출 (None 방지)
            addr = self.table_delivery_plan.item(row, 4).text() if self.table_delivery_plan.item(row, 4) else "주소 없음"
            msg = self.table_delivery_plan.item(row, 6).text() if self.table_delivery_plan.item(row, 6) else "메시지 없음"
            rcv_nm = self.table_delivery_plan.item(row, 2).text() if self.table_delivery_plan.item(row, 2) else "미상"
            
            # 돋보기 영역 텍스트 구성 (HTML 스타일 활용 가능)
            detail_html = f"""
                <b style='color:#007BFF;'>[수령인: {rcv_nm}]</b><br>
                <b>🏠 주소:</b> {addr}<br>
                <b>💬 메시지:</b> {msg}
            """
            self.detail_viewer.setHtml(detail_html)
            
        except Exception as e:
            print(f"돋보기 업데이트 오류: {e}")

