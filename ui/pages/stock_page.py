import sys
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt6.QtGui import QColor

# 📍 외부 스타일 파일 임포트
from ui.styles import MainStyles

# =================================================================
# 1. 커스텀 레이아웃: FlowLayout (자동 줄바꿈 최적화)
# =================================================================
class FlowLayout(QLayout):
    """위젯들을 가로로 나열하다가 공간이 부족하면 자동으로 다음 줄로 배치합니다."""
    def __init__(self, parent=None, margin=0, hspacing=10, vspacing=10):
        super(FlowLayout, self).__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, index): return self._items[index] if 0 <= index < len(self._items) else None
    def takeAt(self, index): return self._items.pop(index) if 0 <= index < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self.doLayout(QRect(0, 0, width, 0), True)
    def setGeometry(self, rect): super(FlowLayout, self).setGeometry(rect); self.doLayout(rect, False)
    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins().top()
        return size + QSize(2 * margin, 2 * margin)

    def doLayout(self, rect, testOnly):
        x, y = rect.x(), rect.y()
        lineHeight = 0
        for item in self._items:
            nextX = x + item.sizeHint().width() + self._hspacing
            if nextX - self._hspacing > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + self._vspacing
                nextX = x + item.sizeHint().width() + self._hspacing
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()


# =================================================================
# 2. UI 컴포넌트: 재고 및 작업대 카드
# =================================================================

class InventoryCard(QFrame):
    """[원물 전용] 초록색 테마 카드"""
    clicked = pyqtSignal(object)
    def __init__(self, data):
        super().__init__()
        self.data, self.current_qty = data, int(data.get('available_qty', 0))
        self.setFixedSize(138, 80); self.setStyleSheet(MainStyles.CARD + " border: none; ")
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(2)
        layout.addWidget(QLabel(f"📅 {data['storage_dt']}", styleSheet=MainStyles.TXT_CAPTION))
        layout.addWidget(QLabel(f"<b>{data['size_nm']}</b>", styleSheet=MainStyles.TXT_BODY))
        layout.addStretch()
        self.qty_lbl = QLabel(f"{self.current_qty}개"); self.qty_lbl.setStyleSheet(MainStyles.TXT_STATUS_GREEN)
        layout.addWidget(self.qty_lbl, alignment=Qt.AlignmentFlag.AlignRight)

    def update_display(self, change):
        try: self.current_qty += change; self.qty_lbl.setText(f"{self.current_qty}개"); self.setEnabled(self.current_qty > 0)
        except RuntimeError: pass
    def mousePressEvent(self, e): 
        if self.current_qty > 0: self.clicked.emit(self)

class ProductCard(QFrame):
    """[수정] 상품 카드: 상단 정렬 적용 및 품종명 추가"""
    clicked = pyqtSignal(object)
    def __init__(self, data):
        super().__init__()
        self.data, self.current_qty = data, int(data.get('available_qty', 0))
        self.setFixedSize(138, 95) # 품종 추가로 높이 소폭 조정
        self.setStyleSheet(MainStyles.CARD + " border: 2px solid #ED8936; ")
        
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(2)
        # 📍 [해결 1] 세로 상단 정렬 강제
        layout.setAlignment(Qt.AlignmentFlag.AlignTop) 
        
        # 📍 [해결 2] 품종 및 등급 표시 (예: 신고 / 특)
        v_nm = data.get('variety_nm', '').replace('배', '') # '배' 글자 제외하여 간결하게
        header_txt = f"<b style='color:#C05621;'>{v_nm} / {data.get('grade_nm', 'NONE')}</b>"
        header = QLabel(header_txt)
        header.setStyleSheet(MainStyles.TXT_CAPTION); layout.addWidget(header)
        
        # 중량 및 규격
        spec_lbl = QLabel(f"{data.get('weight', 0)}kg | {data.get('size_nm','')}")
        spec_lbl.setStyleSheet(MainStyles.LBL_GRID_HEADER); layout.addWidget(spec_lbl)
        
        layout.addStretch() # 아래 여백 확보
        
        self.qty_lbl = QLabel(f"{self.current_qty}박스")
        self.qty_lbl.setStyleSheet(MainStyles.TXT_SUMMARY_VALUE_EMPH + " color: #DD6B20;")
        layout.addWidget(self.qty_lbl, alignment=Qt.AlignmentFlag.AlignRight)

    def update_display(self, change):
        try: self.current_qty += change; self.qty_lbl.setText(f"{self.current_qty}박스"); self.setEnabled(self.current_qty > 0)
        except RuntimeError: pass
    def mousePressEvent(self, e): 
        if self.current_qty > 0: self.clicked.emit(self)


class WorkCartCard(QFrame):
    """공용 작업대 카드 (상한선 제어 포함)"""
    removed = pyqtSignal(object); qty_changed = pyqtSignal()
    def __init__(self, data, max_stock=9999):
        super().__init__()
        self.data, self.work_qty, self.max_allowed = data, 0, int(max_stock)
        self.setFixedSize(138, 80)
        # 모드별 스타일 분기
        is_p = data.get('item_cd') in ['FR010100', 'FR010200']
        style = "border: 2px solid #ED8936; background: #FFFAF0;" if is_p else "border: 2px solid #48BB78; background: #F0FFF4;"
        if data.get('is_new'): style = "border: 2px dashed #3182CE; background: #EBF8FF;"
        self.setStyleSheet(MainStyles.CARD + style)
        
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 5, 10, 5); layout.setSpacing(2)
        header = QHBoxLayout()
        title = f"{data.get('grade_nm','')[:1]} {data.get('size_nm','')}" if is_p else data.get('size_nm','')
        header.addWidget(QLabel(f"<b>{title}</b>", styleSheet=MainStyles.TXT_BODY))
        btn_close = QPushButton("×"); btn_close.setFixedSize(18, 18); btn_close.setStyleSheet(MainStyles.BTN_DANGER + "border-radius: 9px; padding:0;"); btn_close.clicked.connect(lambda: self.removed.emit(self)); header.addWidget(btn_close); layout.addLayout(header)
        self.spin = QSpinBox(); self.spin.setRange(0, self.max_allowed); self.spin.setSuffix(" C" if not is_p else " B"); self.spin.setFixedHeight(26); self.spin.setStyleSheet("border: 1px solid #CBD5E0;"); self.spin.valueChanged.connect(self.sync_qty); layout.addWidget(self.spin)

    def sync_qty(self, value): self.work_qty = value; self.qty_changed.emit()

class GradeInputTile(QFrame):
    """등급별 박스 생산량 입력 패드"""
    value_changed = pyqtSignal(str, int)

    def __init__(self, grade_code, grade_nm, initial_val=0):
        super().__init__()
        self.grade_code = grade_code; self.grade_nm = grade_nm
        self.setFixedSize(133, 105); self.setStyleSheet(MainStyles.CARD + " border: none; ")
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 10, 10, 10); layout.setSpacing(5)
        layout.addWidget(QLabel(f"<b>{self.grade_nm}</b>", styleSheet=MainStyles.TXT_CARD_TITLE))
        self.spin = QSpinBox()
        self.spin.setRange(0, 999); self.spin.setValue(initial_val); self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setStyleSheet("color: #3182CE; border: 1px solid #CBD5E0; height: 30px;")
        self.spin.valueChanged.connect(lambda v: self.value_changed.emit(self.grade_code, v)); layout.addWidget(self.spin)
        btns = QHBoxLayout(); btns.setSpacing(5)
        for v in [1, 10]:
            b = QPushButton(f"+{v}"); b.setFixedHeight(26); b.setStyleSheet(MainStyles.BTN_PRIMARY)
            b.clicked.connect(lambda _, val=v: self.spin.setValue(self.spin.value() + val)); btns.addWidget(b)
        layout.addLayout(btns)

class AuditHistoryDialog(QDialog):
    """[신규] 재고 실사 이력을 조회하는 팝업 창입니다."""
    def __init__(self, db, farm_cd, parent=None):
        super().__init__(parent)
        self.db = db
        self.farm_cd = farm_cd
        self.init_ui()

    def init_ui(self):
        """[수정] 중량(kg) 컬럼을 추가하여 테이블 구성을 8컬럼으로 확장합니다."""
        self.setWindowTitle("🔍 재고 실사 이력 조회")
        self.resize(1000, 500) # 컬럼 추가에 따른 너비 확장
        layout = QVBoxLayout(self)

        title = QLabel("📋 최근 실사 조정 내역", styleSheet=MainStyles.LBL_TITLE)
        layout.addWidget(title)

        self.table = QTableWidget()
        # 📍 [수정] 컬럼 개수를 8개로 늘리고 헤더에 '중량(kg)' 추가
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["일시", "품목", "품종", "등급", "규격", "중량(kg)", "실사수량", "조정 사유"])
        self.table.setStyleSheet(MainStyles.TABLE)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        """[수정] DB에서 weight 필드를 조회하여 테이블에 표시합니다."""
        # 📍 SQL 쿼리에 l.weight 추가
        sql = """
            SELECT l.reg_dt, p.code_nm as item_nm, v.code_nm as variety_nm, 
                   g.code_nm as grade_nm, s.code_nm as size_nm, l.weight, l.qty, l.remark
            FROM t_stock_log l
            LEFT JOIN m_common_code p ON l.item_cd = p.code_cd
            LEFT JOIN m_common_code v ON l.variety_cd = v.code_cd
            LEFT JOIN m_common_code g ON l.grade_cd = g.code_cd
            LEFT JOIN m_common_code s ON l.size_cd = s.code_cd
            WHERE l.farm_cd = ? AND l.io_type = 'AUDIT'
            ORDER BY l.reg_dt DESC
        """
        rows = self.db.fetch_all(sql, (self.farm_cd,))
        self.table.setRowCount(len(rows))
        
        for r, row in enumerate(rows):
            # 수량 단위 구분 (배즙은 '포', 나머지는 '박스')
            unit = "포" if row['item_nm'] == "배즙" else "박스"
            qty_text = f"{int(row['qty'])} {unit}"
            
            # 📍 인덱스 재배치 (5번에 중량 삽입)
            self.table.setItem(r, 0, QTableWidgetItem(row['reg_dt']))
            self.table.setItem(r, 1, QTableWidgetItem(row['item_nm']))
            self.table.setItem(r, 2, QTableWidgetItem(row['variety_nm']))
            self.table.setItem(r, 3, QTableWidgetItem(row['grade_nm']))
            self.table.setItem(r, 4, QTableWidgetItem(row['size_nm']))
            # 📍 추가된 중량 데이터 표시
            self.table.setItem(r, 5, QTableWidgetItem(f"{row['weight']} kg")) 
            self.table.setItem(r, 6, QTableWidgetItem(qty_text))
            self.table.setItem(r, 7, QTableWidgetItem(row['remark']))

# =================================================================
# 3. 메인 페이지: StockPage
# =================================================================

class StockPage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.is_loaded = True
        self.db, self.farm_cd = db_manager, session['farm_cd']
        self.user_id = session.get('user_id', 'SYSTEM')
        self.selected_cards, self.sorting_data, self.size_buttons = [], {}, {}
        
        # 품목 상수 정의
        self.ITEM_PRODUCT = 'FR010100'; self.ITEM_JUICE = 'FR010200'; self.ITEM_RAW = 'FR010300'; self.GRADE_NONE = 'NONE'
        self.init_ui()

    def init_ui(self):
        """[📍 수정] 표준 디자인 적용 및 동적 레이아웃 비중 조절 준비"""
        self.setStyleSheet(MainStyles.MAIN_BG)
        # 📍 동적 비율 조정을 위해 멤버 변수로 설정
        self.master_layout = QVBoxLayout(self)
        self.master_layout.setContentsMargins(15, 10, 15, 10)
        self.master_layout.setSpacing(15)

        # --- [상단] 재고 현황 맵 & 오늘의 작업대 ---
        self.top_layout = QHBoxLayout()
        self.top_layout.setSpacing(15)

        for title, layout_attr, scroll_attr in [("📦 1. 재고 현황 맵", "inv_layout", "inv_scroll"), ("🚜 2. 오늘의 작업대", "cart_layout", "cart_scroll")]:
            box = QVBoxLayout()
            box.setSpacing(8)
            header = QHBoxLayout()
            header.addWidget(QLabel(title, styleSheet=MainStyles.LBL_TITLE))
            header.addStretch()
            
            if "재고" in title:
                # 모드 전환 토글 스위치
                self.mode_group = QButtonGroup(self)
                self.btn_mode_raw = QPushButton("🌱 원물"); self.btn_mode_raw.setCheckable(True); self.btn_mode_raw.setChecked(True)
                self.btn_mode_raw.setFixedSize(70, 28); self.btn_mode_raw.setStyleSheet(MainStyles.BTN_SUB)
                self.btn_mode_prod = QPushButton("📦 상품"); self.btn_mode_prod.setCheckable(True)
                self.btn_mode_prod.setFixedSize(70, 28); self.btn_mode_prod.setStyleSheet(MainStyles.BTN_SUB)
                
                self.mode_group.addButton(self.btn_mode_raw)
                self.mode_group.addButton(self.btn_mode_prod)
                self.mode_group.buttonClicked.connect(self.handle_mode_change)
                header.addWidget(self.btn_mode_raw); header.addWidget(self.btn_mode_prod)
            
            if "작업대" in title:
                # 동적 버튼이 들어갈 레이아웃
                self.action_layout = QHBoxLayout()
                self.action_layout.setSpacing(5)
                header.addLayout(self.action_layout)
            
            box.addLayout(header)
            scroll = QScrollArea()
            # 📍 최소 높이를 350으로 설정하여 상품 모드 시 확장성 확보
            scroll.setMinimumHeight(200)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: 1px solid #E2E8F0; background: white; border-radius: 8px;")
            
            container = QWidget()
            setattr(self, layout_attr, FlowLayout(container, margin=8))
            scroll.setWidget(container)
            setattr(self, scroll_attr, scroll)
            box.addWidget(scroll)
            self.top_layout.addLayout(box, 1)
        
        # 📍 상단 레이아웃 추가 (Index 0)
        self.master_layout.addLayout(self.top_layout)

        # --- [하단] 선별 패드 구역 (원물 모드 전용) ---
        self.bottom_panel = QFrame()
        self.bottom_panel.setStyleSheet("background: white; border-top: 1px solid #E2E8F0;")
        bottom_vbox = QVBoxLayout(self.bottom_panel)
        bottom_vbox.setContentsMargins(20, 15, 20, 15); bottom_vbox.setSpacing(10)
        
        # 수율 게이지 및 포장단위 설정
        head_layout = QHBoxLayout()
        gauge_box = QVBoxLayout()
        self.lbl_gauge = QLabel("⚖️ 실시간 수율 밸런스: 0%"); self.lbl_gauge.setStyleSheet(MainStyles.LBL_TITLE)
        self.yield_bar = QProgressBar(); self.yield_bar.setFixedSize(300, 22)
        self.yield_bar.setStyleSheet("QProgressBar { border: 1px solid #CBD5E0; border-radius: 4px; text-align: center; font-weight: bold; color: #2D3748; } QProgressBar::chunk { background-color: #48BB78; }")
        gauge_box.addWidget(self.lbl_gauge); gauge_box.addWidget(self.yield_bar)
        head_layout.addLayout(gauge_box); head_layout.addStretch()
        
        self.target_weight_combo = QComboBox(); self.target_weight_combo.setFixedSize(200, 40)
        self.target_weight_combo.setStyleSheet(MainStyles.COMBO + "border: 2px solid #3182CE; font-weight: bold;")
        weights = self.db.fetch_all("SELECT code_cd, code_nm FROM m_common_code WHERE parent_cd = 'SZ01' ORDER BY code_cd")
        for cd, nm in weights: self.target_weight_combo.addItem(nm, cd)
        self.target_weight_combo.currentIndexChanged.connect(self.init_sorting_pad)
        
        head_layout.addWidget(QLabel("📦 포장 단위: ", styleSheet=MainStyles.LBL_GRID_HEADER))
        head_layout.addWidget(self.target_weight_combo); bottom_vbox.addLayout(head_layout)
        
        # 판매사이즈 가이드 및 타일 레이아웃
        bottom_vbox.addWidget(QLabel("🔍 판매 사이즈 선택", styleSheet=MainStyles.LBL_GRID_HEADER))
        self.size_btn_container = QWidget(); self.size_btn_layout = QHBoxLayout(self.size_btn_container); self.size_btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        size_scroll = QScrollArea(); size_scroll.setFixedHeight(75); size_scroll.setWidgetResizable(True); size_scroll.setWidget(self.size_btn_container); bottom_vbox.addWidget(size_scroll)
        self.tile_container = QWidget(); self.tile_layout = QGridLayout(self.tile_container); tile_scroll = QScrollArea(); tile_scroll.setWidgetResizable(True); tile_scroll.setWidget(self.tile_container); bottom_vbox.addWidget(tile_scroll)
        
        # 📍 하단 패널 추가 (Index 1)
        self.master_layout.addWidget(self.bottom_panel)
        
        # 초기 모드 핸들링
        self.handle_mode_change()

    # =============================================================
    # 4. 모드 전환 및 동적 액션바 핸들러
    # =============================================================

    def handle_mode_change(self):
        """[수정] 상품 모드에 '실사 이력' 확인 버튼을 추가합니다."""
        self.clear_all_refresh()
        while self.action_layout.count():
            item = self.action_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        is_raw = self.btn_mode_raw.isChecked()
        
        if is_raw:
            self.add_action_btn("💾 원물 등록", self.register_raw_material, MainStyles.BTN_PRIMARY)
            self.add_action_btn("🗑️ 폐기 처리", self.dispose_raw_material, MainStyles.BTN_DANGER)
            self.add_action_btn("📦 생산 확정", self.save_production_log, "#2D3748")
            self.bottom_panel.show()
            self.master_layout.setStretch(0, 4) 
            self.master_layout.setStretch(1, 6) 
        else:
            # 🟠 상품 모드: 실사 이력 버튼 추가
            self.add_action_btn("🛠️ 재고 실사", self.audit_product_stock, MainStyles.BTN_PRIMARY)
            self.add_action_btn("📜 실사 이력", self.view_audit_history, MainStyles.BTN_SUB) # 이력 조회 버튼
            self.add_action_btn("🗑️ 폐기 처리", self.dispose_raw_material, MainStyles.BTN_DANGER)
            
            self.bottom_panel.hide()
            self.master_layout.setStretch(0, 1) 
            self.master_layout.setStretch(1, 0) 
            
        self.load_inventory()

    def add_action_btn(self, text, callback, style):
        """표준 버튼 스타일(styles.py)을 적용한 액션 버튼 생성"""
        btn = QPushButton(text); btn.setFixedSize(115, 32)
        btn.setStyleSheet(MainStyles.BTN_PRIMARY + f"background: {style};" if style.startswith('#') else style)
        btn.clicked.connect(callback); self.action_layout.addWidget(btn)

    def load_inventory(self):
        """
        [📍아토스 최종교정] 
        1. 마이너스(-) 재고 표시 허용 (작업 지시 확인용)
        2. 재고 0인 항목 제외 (노이즈 제거)
        3. 마이너스 재고 상단 배치 및 시각적 강조
        4. 품종 -> 중량 -> 등급 -> 사이즈 정렬 순서 준수
        """
        # 1. 기존 레이아웃 비우기
        while self.inv_layout.count():
            item = self.inv_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            
        is_raw = self.btn_mode_raw.isChecked()
        
        # 2. 조건절 설정
        if is_raw:
            where_clause = "m.item_cd = ?"
            params = (self.farm_cd, self.ITEM_RAW)
            # 원물은 신선도와 입고일이 중요하므로 입고일 순 유지
            order_by = "m.storage_dt ASC" 
        else:
            where_clause = f"m.item_cd IN ('{self.ITEM_PRODUCT}', '{self.ITEM_JUICE}')"
            params = (self.farm_cd,)
            # 📍 [핵심] 마이너스 재고(작업필요분)를 가장 위에 올리고, 
            # 그 안에서 대표님이 요청하신 [품종->중량->등급->사이즈] 순으로 정렬합니다.
            # available_qty가 음수인 것이 양수인 것보다 먼저 오게 하려면 
            # (m.available_qty < 0) DESC 조건을 앞에 붙이면 됩니다.
            order_by = "(m.available_qty < 0) DESC, m.variety_cd ASC, m.weight ASC, m.grade_cd ASC, m.size_cd ASC"
        
        # 📍 [SQL 수정] m.available_qty > 0 조건을 제거하고 != 0 으로 변경 (마이너스 포함)
        sql = f"""
            SELECT m.*, c1.code_nm as size_nm, c2.code_nm as grade_nm, 
                   p.code_nm as item_nm, v.code_nm as variety_nm
            FROM t_stock_master m 
            JOIN m_common_code c1 ON m.size_cd = c1.code_cd 
            LEFT JOIN m_common_code c2 ON m.grade_cd = c2.code_cd
            JOIN m_common_code p ON m.item_cd = p.code_cd
            LEFT JOIN m_common_code v ON m.variety_cd = v.code_cd
            WHERE m.farm_cd = ? AND {where_clause} 
              AND m.available_qty != 0  -- 📍 0인 것은 숨기고 마이너스는 표시
            ORDER BY {order_by}
        """
        
        rows = self.db.fetch_all(sql, params)
        for r in rows:
            data = dict(r)
            # 📍 카드 생성
            card = InventoryCard(data) if is_raw else ProductCard(data)
            
            # 📍 [시각적 강조] 마이너스 재고인 경우 카드의 스타일을 변경하여 '작업 필요' 신호를 줍니다.
            if data['available_qty'] < 0:
                # 스타일 시트는 대표님의 styles.py 설정에 맞춰 조정 가능합니다.
                card.setStyleSheet("""
                    background-color: #FFF5F5; 
                    border: 2px solid #FC8181; 
                    border-radius: 10px;
                """)
                # 필요시 카드 내부의 수량 라벨 색상도 변경 로직 추가 가능
            
            card.clicked.connect(self.handle_inventory_click)
            self.inv_layout.addWidget(card)

    def handle_inventory_click(self, card):
        """원물/상품 클릭 시 작업대로 안전하게 이동 (정수 변환 포함)"""
        qty = min(30, int(card.current_qty)); card.update_display(-qty)
        max_limit = int(card.data.get('available_qty', 9999))
        exist = next((c for c in self.selected_cards if c.data == card.data), None)
        if exist: exist.spin.setValue(exist.work_qty + qty)
        else:
            new = WorkCartCard(card.data, max_stock=max_limit); new.spin.setValue(qty); new.qty_changed.connect(self.update_gauge); new.removed.connect(self.remove_from_cart); self.cart_layout.addWidget(new); self.selected_cards.append(new)
        self.init_sorting_pad()

    # =============================================================
    # 5. 비즈니스 로직 (기존 기능 완벽 보존)
    # =============================================================

    def register_raw_material(self):
        """[📍 해결]: 원물(FR010300) 등록 시 CT01(규격) 카드 생성"""
        if not self.selected_cards:
            # 1. 배 품종(FR010100 하위) 리스트업
            v_rows = self.db.fetch_all("SELECT code_cd, code_nm FROM m_common_code WHERE parent_cd = 'FR010100' ORDER BY code_cd")
            v_list = [f"{r['code_nm']}({r['code_cd']})" for r in v_rows]
            v_item, ok = QInputDialog.getItem(self, "신규 수확", "수확 품종을 선택하세요:", v_list, 0, False)
            
            if not ok: return
            sel_v_cd = v_item.split('(')[1].replace(')','')
            sel_v_nm = v_item.split('(')[0]
            
            # 2. 작업대에 CT01(저장배/원물규격) 하위 항목들로 빈 카드 배치
            s_rows = self.db.fetch_all("SELECT code_cd, code_nm FROM m_common_code WHERE parent_cd = 'CT01' ORDER BY code_cd")
            for s in s_rows:
                placeholder = {
                    'wh_cd': 'WH01',
                    'item_cd': self.ITEM_RAW, # 'FR010300'
                    'variety_cd': sel_v_cd,
                    'variety_nm': sel_v_nm,
                    'size_cd': s['code_cd'],
                    'size_nm': s['code_nm'],
                    'is_new': True,
                    'storage_dt': datetime.now().strftime('%Y-%m-%d')
                }
                new_card = WorkCartCard(placeholder)
                new_card.spin.setValue(0)
                new_card.removed.connect(self.remove_from_cart)
                self.cart_layout.addWidget(new_card)
                self.selected_cards.append(new_card)
            return
            
        # 작업대에 카드가 있는 경우 실제 저장 프로세스로 연결
        self.process_db_registration()

    def process_db_registration(self):
        """[📍 수정] 원물 등록 시 20.0kg 중량 정보를 로그에 포함합니다."""
        valid = [c for c in self.selected_cards if c.work_qty > 0]
        if not valid: return
        t_dt, ok = QInputDialog.getText(self, "저장일", "일자:", text=datetime.now().strftime('%Y-%m-%d'))
        if not ok: return
        
        queries = []
        for c in valid:
            r, qty, yr = c.data, c.work_qty, t_dt[:4]
            # 마스터 업데이트
            queries.append(("INSERT OR IGNORE INTO t_stock_master (farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt, in_qty, out_qty, reg_id) VALUES (?, ?, ?, ?, 'NONE', ?, 20.0, ?, ?, 0, 0, ?)", (self.farm_cd, r['wh_cd'], self.ITEM_RAW, r['variety_cd'], r['size_cd'], yr, t_dt, self.user_id)))
            queries.append(("UPDATE t_stock_master SET in_qty = in_qty + ?, mod_dt = datetime('now','localtime'), mod_id = ? WHERE farm_cd=? AND storage_dt=? AND wh_cd=? AND item_cd=? AND size_cd=?", (qty, self.user_id, self.farm_cd, t_dt, r['wh_cd'], self.ITEM_RAW, r['size_cd'])))
            
            # 📍 [핵심]: 로그에 weight(20.0) 추가
            sql_log = """
                INSERT INTO t_stock_log (farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, remark, reg_id) 
                VALUES (?, ?, ?, ?, ?, ?, 20.0, 'IN', ?, '수확 원물 등록', ?)
            """
            queries.append((sql_log, (self.farm_cd, self.ITEM_RAW, r['variety_cd'], yr, self.GRADE_NONE, r['size_cd'], qty, self.user_id)))
            
        if self.db.execute_transaction(queries):
            QMessageBox.information(self, "성공", "원물 장부 및 중량 기록 완료."); self.clear_all_refresh()

    def dispose_raw_material(self):
        """원물/상품 통합 폐기 로직"""
        targets = [c for c in self.selected_cards if c.work_qty > 0]
        if not targets: return
        if QMessageBox.question(self, '폐기', "불량 폐기하시겠습니까?") != QMessageBox.StandardButton.Yes: return
        queries = []
        for c in targets:
            r, qty = c.data, c.work_qty
            queries.append(("UPDATE t_stock_master SET out_qty = out_qty + ?, mod_dt = datetime('now','localtime'), mod_id = ? WHERE farm_cd=? AND storage_dt=? AND wh_cd=? AND item_cd=? AND size_cd=?", (qty, self.user_id, self.farm_cd, r['storage_dt'], r['wh_cd'], r['item_cd'], r['size_cd'])))
            queries.append(("INSERT INTO t_stock_log (farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, io_type, qty, remark, reg_id) VALUES (?, ?, ?, ?, ?, ?, 'OUT', ?, '품질 폐기', ?)", (self.farm_cd, r['item_cd'], r['variety_cd'], r.get('harvest_year', datetime.now().year), r.get('grade_cd','NONE'), r['size_cd'], qty, self.user_id)))
        if self.db.execute_transaction(queries): QMessageBox.information(self, "성공", "폐기 완료."); self.clear_all_refresh()

    # 상품실사 처리 로직(문제가 발생한 상품의 수량을 조정하고 사유를 기록한다.)
    def audit_product_stock(self):
        """[📍 수정] 재고 실사 시 기존 중량(weight) 정보를 로그에 보존합니다."""
        if not self.selected_cards: return
        reason, ok = QInputDialog.getText(self, "재고 실사", "사유를 입력하세요:")
        if not ok or not reason.strip(): return
        
        queries = []
        for c in self.selected_cards:
            r = c.data; audit_qty = int(c.work_qty); in_qty = int(r.get('in_qty', 0))
            # 📍 기존 중량값 확보
            orig_weight = float(r.get('weight', 0))
            
            if audit_qty > in_qty: new_in, new_out = audit_qty, 0
            else: new_in, new_out = in_qty, in_qty - audit_qty
            
            sql_master = "UPDATE t_stock_master SET in_qty = ?, out_qty = ?, mod_dt = datetime('now','localtime'), mod_id = ? WHERE farm_cd=? AND storage_dt=? AND wh_cd=? AND item_cd=? AND size_cd=? AND variety_cd=? AND grade_cd=?"
            queries.append((sql_master, (new_in, new_out, self.user_id, self.farm_cd, r['storage_dt'], r['wh_cd'], r['item_cd'], r['size_cd'], r['variety_cd'], r.get('grade_cd','NONE'))))
            
            # 📍 [핵심]: 로그에 기존 중량(orig_weight) 포함
            sql_log = """
                INSERT INTO t_stock_log (farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, remark, reg_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 'AUDIT', ?, ?, ?)
            """
            queries.append((sql_log, (self.farm_cd, r['item_cd'], r['variety_cd'], r.get('harvest_year'), r.get('grade_cd','NONE'), r['size_cd'], orig_weight, audit_qty, f"실사: {reason}", self.user_id)))

        if self.db.execute_transaction(queries):
            QMessageBox.information(self, "성공", "실사 및 중량 로그 동기화 완료."); self.clear_all_refresh()

    def save_production_log(self):
        """
        [📍아토스 진짜 최종본] 
        1. 다이(FR) 통합 + 시즌 단일 바구니 최적화
        2. 원물 정밀 차감 (오염 방지)
        3. 작업 지시 상태 변경 (t_work_detail -> 'DONE') 추가
        """
        if not self.selected_cards: return
        if QMessageBox.question(self, '확정', "선택한 원물을 소모하여 상품 생산을 저장하시겠습니까?") != QMessageBox.StandardButton.Yes: return

        try:
            cursor = self.db.conn.cursor()
            now = datetime.now()
            p_dt = now.strftime('%Y-%m-%d')
            yr = now.strftime('%Y')
            
            u_w = float(self.target_weight_combo.currentText().replace('kg',''))
            ref = self.selected_cards[0].data  # 기준 정보
            queries = []

            # ==========================================================
            # 1. [작업 상태 변경] work_id가 있는 카드만 완료(DONE) 처리
            # ==========================================================
            sql_work_done = """
                UPDATE t_work_detail 
                SET status_cd = 'DONE', mod_id = ?, mod_dt = datetime('now','localtime')
                WHERE work_id = ?
            """
            work_ids = []
            for c in self.selected_cards:
                w_id = str((c.data or {}).get("work_id") or "").strip()
                if w_id:
                    work_ids.append(w_id)
            for w_id in sorted(set(work_ids)):
                queries.append((sql_work_done, (self.user_id, w_id)))

            # ==========================================================
            # 2. [상품 생산] 다이(FR) 단위 통합 + 단일 바구니 누적 (IN)
            # ==========================================================
            for dai_cd, grades in self.sorting_data.items():
                for g_cd, qty in grades.items():
                    if qty > 0:
                        # 올해 해당 규격 최초 입력일 조회
                        check_sql = """
                            SELECT storage_dt FROM t_stock_master 
                            WHERE farm_cd=? AND wh_cd=? AND item_cd=? AND variety_cd=? AND grade_cd=? AND size_cd=? AND weight=? AND harvest_year=?
                        """
                        cursor.execute(check_sql, (self.farm_cd, ref['wh_cd'], self.ITEM_PRODUCT, ref['variety_cd'], g_cd, dai_cd, u_w, yr))
                        existing_record = cursor.fetchone()

                        target_storage_dt = existing_record[0] if existing_record else p_dt

                        # UPSERT (Insert or Ignore + Update)
                        ins_sql = """
                            INSERT OR IGNORE INTO t_stock_master 
                            (farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt, in_qty, out_qty, reserved_qty, reg_id) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
                        """
                        queries.append((ins_sql, (self.farm_cd, ref['wh_cd'], self.ITEM_PRODUCT, ref['variety_cd'], g_cd, dai_cd, u_w, yr, target_storage_dt, self.user_id)))

                        upd_sql = """
                            UPDATE t_stock_master 
                            SET in_qty = in_qty + ?, mod_dt = datetime('now','localtime'), mod_id = ? 
                            WHERE farm_cd=? AND wh_cd=? AND item_cd=? AND variety_cd=? AND grade_cd=? AND size_cd=? AND weight=? AND harvest_year=? AND storage_dt=?
                        """
                        queries.append((upd_sql, (qty, self.user_id, self.farm_cd, ref['wh_cd'], self.ITEM_PRODUCT, ref['variety_cd'], g_cd, dai_cd, u_w, yr, target_storage_dt)))
                        
                        # 상품 생산 로그
                        log_sql = """
                            INSERT INTO t_stock_log 
                            (farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, remark, reg_id) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'IN', ?, '선별생산 (다이통합)', ?)
                        """
                        queries.append((log_sql, (self.farm_cd, self.ITEM_PRODUCT, ref['variety_cd'], yr, g_cd, dai_cd, u_w, qty, self.user_id)))

            # ==========================================================
            # 3. [원물 소모] 선택된 원물 카드별 재고 정밀 차감 (OUT)
            # ==========================================================
            for c in self.selected_cards:
                c_data = c.data
                raw_upd = """
                    UPDATE t_stock_master 
                    SET out_qty = out_qty + ?, mod_dt = datetime('now','localtime'), mod_id = ? 
                    WHERE farm_cd=? AND wh_cd=? AND item_cd=? AND variety_cd=? AND size_cd=? AND weight=? AND harvest_year=? AND storage_dt=?
                """
                queries.append((raw_upd, (c.work_qty, self.user_id, self.farm_cd, c_data['wh_cd'], self.ITEM_RAW, c_data['variety_cd'], c_data['size_cd'], c_data['weight'], c_data['harvest_year'], c_data['storage_dt'])))

                raw_log = """
                    INSERT INTO t_stock_log 
                    (farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, remark, reg_id) 
                    VALUES (?, ?, ?, ?, 'NONE', ?, ?, 'OUT', ?, '생산 원물 소모', ?)
                """
                queries.append((raw_log, (self.farm_cd, self.ITEM_RAW, c_data['variety_cd'], c_data['harvest_year'], c_data['size_cd'], c_data['weight'], c.work_qty, self.user_id)))

            # 4. 트랜잭션 실행
            if self.db.execute_transaction(queries):
                QMessageBox.information(self, "성공", "상품 생산 및 작업 지시 완료 처리가 모두 성공했습니다.")
                self.clear_all_refresh()
            else:
                raise Exception("트랜잭션 실행 중 오류가 발생했습니다.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "저장 실패", f"에러 발생: {str(e)}")

    def clear_all_refresh(self):
        self.selected_cards.clear(); self.sorting_data.clear()
        while self.cart_layout.count(): self.cart_layout.takeAt(0).widget().deleteLater()
        self.load_inventory(); self.init_sorting_pad()

    def remove_from_cart(self, card):
        if card in self.selected_cards: self.selected_cards.remove(card)
        card.setParent(None); card.deleteLater(); self.load_inventory(); self.init_sorting_pad()

    def init_sorting_pad(self):
        """[📍수정] 과수(SZ) 대신 다이(FR) 코드로 버튼 생성"""
        self.sorting_data.clear()
        while self.size_btn_layout.count(): self.size_btn_layout.takeAt(0).widget().deleteLater()
        while self.tile_layout.count(): 
            item = self.tile_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.size_buttons.clear()
        
        targets = [c for c in self.selected_cards if c.work_qty > 0]
        if not targets or not self.btn_mode_raw.isChecked(): 
            self.update_gauge()
            return

        # 📍 [변경] 배 다이(판매사이즈) 공통코드 그룹(FR020100)을 불러옵니다.
        # 이 코드는 DB의 m_common_code 설정에 따라 달라질 수 있습니다.
        sql = "SELECT code_cd, code_nm FROM m_common_code WHERE parent_cd = 'FR020100' ORDER BY code_cd"
        sizes = self.db.fetch_all(sql)
        
        for s_cd, s_nm in sizes:
            self.sorting_data[s_cd] = {}
            btn = QPushButton(s_nm)
            btn.setCheckable(True)
            btn.setFixedHeight(50)
            btn.setMinimumWidth(140)
            btn.setStyleSheet(MainStyles.BTN_SUB) # 기존 스타일 유지
            btn.clicked.connect(lambda _, sc=s_cd: self.switch_size(sc))
            self.size_btn_layout.addWidget(btn)
            self.size_buttons[s_cd] = (btn, s_nm)
            
        if sizes: 
            self.size_btn_layout.itemAt(0).widget().setChecked(True)
            self.switch_size(sizes[0][0])
            
        self.update_gauge()

    def switch_size(self, size_code):
        self.current_size_cd = size_code
        for s_cd, (btn, base_nm) in self.size_buttons.items(): btn.setChecked(s_cd == size_code)
        while self.tile_layout.count(): item = self.tile_layout.takeAt(0); [item.widget().deleteLater() if item.widget() else None]
        grades = self.db.fetch_all("SELECT code_cd, code_nm FROM m_common_code WHERE parent_cd = 'GR01' ORDER BY code_cd")
        for i, (g_cd, g_nm) in enumerate(grades):
            val = self.sorting_data.get(self.current_size_cd, {}).get(g_cd, 0)
            tile = GradeInputTile(g_cd, g_nm, val); tile.value_changed.connect(lambda gc, v: (self.sorting_data[self.current_size_cd].update({gc: v}), self.update_gauge())); self.tile_layout.addWidget(tile, 0, i)
        self.update_gauge()

    def update_gauge(self):
        """
        수율 계산 공식:
        $$Ratio = \\frac{TotalOutKg}{TotalInKg} \\times 100$$
        """
        total_in_kg = sum(c.work_qty * 20.0 for c in self.selected_cards)
        unit_w = float(self.target_weight_combo.currentText().replace('kg','')) if 'kg' in self.target_weight_combo.currentText() else 15.0
        for s_cd, (btn, base_nm) in self.size_buttons.items():
            tot = sum(self.sorting_data.get(s_cd, {}).values()); btn.setText(f"{base_nm}\n({tot}박스)" if tot > 0 else base_nm)
        total_out_qty = sum(sum(g.values()) for g in self.sorting_data.values()); total_out_kg = total_out_qty * unit_w
        ratio = (total_out_kg / total_in_kg * 100) if total_in_kg > 0 else 0
        self.yield_bar.setValue(int(ratio)); self.lbl_gauge.setText(f"⚖️ 실시간 수율 밸런스: {ratio:.1f}% ({int(total_out_kg)}kg / {int(total_in_kg)}kg)")

    def view_audit_history(self):
            """[신규] 실사 이력 팝업을 실행합니다."""
            dialog = AuditHistoryDialog(self.db, self.farm_cd, self)
            dialog.exec()