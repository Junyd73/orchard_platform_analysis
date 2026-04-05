import sys
import re
import traceback

from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QDate, QRegularExpression, QEvent
from PyQt6.QtGui import QBrush, QColor, QFont, QRegularExpressionValidator

from core.code_manager import CodeManager
from ui.styles import MainStyles, make_app_font
from core.account_manager import AccountManager

# 배송 리스트 팝업
class DeliveryDetailDialog(QDialog):
    def __init__(self, item_nm, total_qty, sender_info, parent=None):
        super().__init__(parent)
        self.item_nm = item_nm
        self.total_qty = total_qty
        self.sender_info = sender_info  # {'name': '', 'tel': '', 'addr': ''}
        self.delivery_list = []
        self.deleted_pay_items = []  # 👈 이 줄이 없어서 에러가 났습니다!
        self.selected_pay_row = -1    # 선택된 행 번호도 미리 준비
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"배송지 상세 관리 - [{self.item_nm}]")
        self.resize(1100, 500) # 컬럼이 늘어나서 창 크기를 키웠습니다.
        layout = QVBoxLayout(self)

        # 배송지 입력 테이블 (발송인 + 수령인 통합)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "보내는사람", "보내는분 연락처", "보내는분 주소", 
            "받는사람", "받는분 연락처", "받는분 주소", 
            "수량", "배송메시지"
        ])
        
        # 헤더 폭 조정 (주소 열을 더 넓게)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(2, 200) # 보내는분 주소
        header.resizeSection(5, 200) # 받는분 주소
        
        layout.addWidget(self.table)

        # 버튼 및 하단 레이아웃 (기존과 동일)
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ 배송지 추가")
        self.btn_add.clicked.connect(self.add_row)
        self.btn_save = QPushButton("적용하기")
        self.btn_save.clicked.connect(self.validate_and_accept)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def add_row(self):
        """행 추가 시 주문자(과수원) 정보를 기본값으로 세팅"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 보내는 사람 정보 기본 세팅 (지기님 요청 반영)
        self.table.setItem(row, 0, QTableWidgetItem(self.sender_info['name']))
        self.table.setItem(row, 1, QTableWidgetItem(self.sender_info['tel']))
        self.table.setItem(row, 2, QTableWidgetItem(self.sender_info['addr']))
        
        # 받는 사람 및 수량 초기화
        self.table.setItem(row, 6, QTableWidgetItem("0")) # 수량
    def delete_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def validate_and_accept(self):
        """설계서의 수량 정합성 체크 로직"""
        current_sum = 0
        temp_list = []
        
        try:
            for i in range(self.table.rowCount()):
                # [수정] 컬럼 인덱스 변경 (0~2는 보내는사람, 3~7이 받는사람 및 수량)
                # 3: 받는분, 4: 연락처, 5: 주소, 6: 수량, 7: 메시지
                
                # 위젯이 없을 경우를 대비한 안전한 가져오기
                t_nm = self.table.item(i, 3); rcv_name = t_nm.text() if t_nm else ""
                t_tel = self.table.item(i, 4); rcv_tel = t_tel.text() if t_tel else ""
                t_addr = self.table.item(i, 5); rcv_addr = t_addr.text() if t_addr else ""
                
                t_qty = self.table.item(i, 6)
                d_qty = float(t_qty.text() or 0) if t_qty else 0.0
                
                t_msg = self.table.item(i, 7); d_msg = t_msg.text() if t_msg else ""

                # 필수값 체크 (이름, 주소)
                if not rcv_name or not rcv_addr:
                    QMessageBox.warning(self, "입력 누락", f"{i+1}번 행의 받는분 이름과 주소를 확인하세요.")
                    return

                current_sum += d_qty
                
                # 리스트에 추가 (보내는 사람 정보도 필요한 경우 여기서 self.sender_info 등을 활용 가능)
                temp_list.append({
                    'rcv_name': rcv_name, 
                    'rcv_tel': rcv_tel, 
                    'rcv_addr': rcv_addr, 
                    'delivery_qty': d_qty, 
                    'delivery_msg': d_msg
                })

            # 수량 검증
            if current_sum > self.total_qty:
                QMessageBox.critical(self, "수량 초과", 
                    f"입력된 배송수량 합계({current_sum})가 \n품목 총 수량({self.total_qty})을 초과합니다.")
                return

            self.delivery_list = temp_list
            self.accept() # 창 닫기 및 결과 반환
            
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "수량은 숫자만 입력 가능합니다.")
'''
    def load_existing_data(self, data_list):
        """저장되어 있던 배송지 목록을 팝업 테이블에 채워넣음"""
        if not data_list:
            return
            
        self.table.setRowCount(0) # 기존 빈 줄 제거
        for d in data_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # DB 컬럼명(dlvry_nm 등)과 팝업 키값(rcv_nm 등)을 모두 대응
            # 총 8개 컬럼: 보내는사람, 연락처, 주소, 받는사람, 연락처, 주소, 수량, 메시지
            row_data = [
                d.get('snd_name') or d.get('snd_nm') or self.sender_info.get('name', ''),
                d.get('snd_tel') or self.sender_info.get('tel', ''),
                d.get('snd_addr') or self.sender_info.get('addr', ''),
                d.get('rcv_name') or d.get('rcv_nm') or '',
                d.get('rcv_tel') or '',
                d.get('rcv_addr') or '',
                str(d.get('dlvry_qty') or d.get('qty') or 1),
                d.get('dlvry_msg') or d.get('delivery_msg') or d.get('msg') or ''
            ]
            
            for col, text in enumerate(row_data):
                item = QTableWidgetItem(str(text))
                self.table.setItem(row, col, item)
'''
# 신규 배송지 정보 등록 (입력 제한 + 실시간 자동 하이픈)
class NewDeliveryDialog(QDialog):
    def __init__(self, default_sender, parent=None):
        super().__init__(parent)
        self.default_sender = default_sender 
        self.data = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("신규 배송지 등록")
        self.resize(600, 350)
        self.setStyleSheet(MainStyles.MAIN_BG)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20)

        # 타이틀
        layout.addWidget(QLabel("배송 정보 입력 (모두 필수)", styleSheet="font-size: 14px; font-weight: bold; color: #C62828;"))

        # 좌우 분할
        content_layout = QHBoxLayout(); content_layout.setSpacing(20)

        # -----------------------------------------------------------
        # [기능] 숫자와 하이픈만 입력 가능하게 하는 제한기 생성
        # -----------------------------------------------------------
        # [0-9]: 숫자만 허용 / [-]: 하이픈 허용
        # 사용자가 하이픈을 직접 지우거나 입력하는 것도 고려하여 '-' 포함
        regex = QRegularExpression("[0-9-]*")
        validator_snd = QRegularExpressionValidator(regex)
        validator_rcv = QRegularExpressionValidator(regex)

        # [좌] 보내는 분
        grp_snd = QGroupBox("보내는 분 (Sender)"); grp_snd.setStyleSheet(MainStyles.GROUP_BOX)
        f_snd = QFormLayout()
        self.snd_nm = QLineEdit(self.default_sender.get('nm', ''))
        self.snd_tel = QLineEdit(self.default_sender.get('tel', '')) # 여기
        self.snd_addr = QLineEdit(self.default_sender.get('addr', ''))
        
        self.snd_nm.setPlaceholderText("이름 (필수)")
        self.snd_tel.setPlaceholderText("숫자만 입력하면 자동 변환됩니다")
        self.snd_addr.setPlaceholderText("주소 (필수)")

        # ★ 1. 입력 제한 적용 (문자 입력 불가)
        self.snd_tel.setValidator(validator_snd) 
        # ★ 2. 실시간 하이픈 자동 생성 연결
        self.snd_tel.textEdited.connect(lambda text: self.on_phone_text_changed(self.snd_tel, text))

        for w in [self.snd_nm, self.snd_tel, self.snd_addr]: w.setStyleSheet(MainStyles.INPUT_LEFT)
        f_snd.addRow("이름:", self.snd_nm); f_snd.addRow("연락처:", self.snd_tel); f_snd.addRow("주소:", self.snd_addr)
        grp_snd.setLayout(f_snd)

        # [우] 받는 분
        grp_rcv = QGroupBox("받는 분 (Receiver)"); grp_rcv.setStyleSheet(MainStyles.GROUP_BOX)
        f_rcv = QFormLayout()
        self.rcv_nm = QLineEdit(); self.rcv_nm.setPlaceholderText("이름 (필수)")
        self.rcv_tel = QLineEdit(); self.rcv_tel.setPlaceholderText("숫자만 입력하면 자동 변환됩니다")
        self.rcv_addr = QLineEdit(); self.rcv_addr.setPlaceholderText("주소 (필수)")
        
        # ★ 1. 입력 제한 적용
        self.rcv_tel.setValidator(validator_rcv)
        # ★ 2. 실시간 하이픈 자동 생성 연결
        self.rcv_tel.textEdited.connect(lambda text: self.on_phone_text_changed(self.rcv_tel, text))

        for w in [self.rcv_nm, self.rcv_tel, self.rcv_addr]: w.setStyleSheet(MainStyles.INPUT_LEFT)
        f_rcv.addRow("이름:", self.rcv_nm); f_rcv.addRow("연락처:", self.rcv_tel); f_rcv.addRow("주소:", self.rcv_addr)
        grp_rcv.setLayout(f_rcv)

        content_layout.addWidget(grp_snd); content_layout.addWidget(grp_rcv)
        layout.addLayout(content_layout)

        # 버튼
        btn_box = QHBoxLayout()
        btn_save = QPushButton("등록 완료"); btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("취소"); btn_cancel.setStyleSheet(MainStyles.BTN_ACTION)
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        self.rcv_nm.setFocus()

    def on_phone_text_changed(self, line_edit, text):
        """숫자를 입력할 때마다 실시간으로 하이픈을 넣어주는 마법사"""
        # 1. 숫자만 남기고 다 제거 (하이픈도 일단 제거 후 재배치)
        numbers = re.sub(r'[^0-9]', '', text)
        length = len(numbers)
        formatted = ""

        # 2. 자릿수에 맞춰 하이픈 삽입
        if length < 4:
            formatted = numbers
        elif numbers.startswith('02'): # 서울 (02)
            if length < 6: # 02-123
                formatted = f"{numbers[:2]}-{numbers[2:]}"
            elif length < 10: # 02-123-4567
                formatted = f"{numbers[:2]}-{numbers[2:5]}-{numbers[5:]}"
            else: # 02-1234-5678 (최대)
                formatted = f"{numbers[:2]}-{numbers[2:6]}-{numbers[6:]}"
        else: # 휴대폰/경기 등 (010, 031...)
            if length < 7:
                formatted = f"{numbers[:3]}-{numbers[3:]}"
            elif length < 11:
                formatted = f"{numbers[:3]}-{numbers[3:6]}-{numbers[6:]}"
            else:
                formatted = f"{numbers[:3]}-{numbers[3:7]}-{numbers[7:]}"
        
        # 3. 텍스트가 달라졌을 때만 업데이트 (무한루프 방지)
        if line_edit.text() != formatted:
            line_edit.setText(formatted)
            # 커서를 맨 끝으로 이동 (입력 편의)
            line_edit.setCursorPosition(len(formatted))

    def save(self):
        # 0. 검증용 정규식 패턴 정의 (이게 있어야 아래에서 오류가 안 납니다)
        phone_pattern = r'^\d{2,3}-\d{3,4}-\d{4}$'

        # 1. 입력값 가져오기
        s_nm = self.snd_nm.text().strip()
        s_tel_raw = self.snd_tel.text().strip()
        s_addr = self.snd_addr.text().strip()
        
        r_nm = self.rcv_nm.text().strip()
        r_tel_raw = self.rcv_tel.text().strip()
        r_addr = self.rcv_addr.text().strip()

        # 화면에 있는 값을 그대로 사용 (이미 자동 포맷팅됨)
        s_tel = s_tel_raw
        r_tel = r_tel_raw

        # 2. [필수 체크]
        if not all([s_nm, s_tel, s_addr, r_nm, r_tel, r_addr]):
            QMessageBox.warning(self, "입력 누락", "모든 정보(이름, 연락처, 주소)를 입력해주세요.")
            return

        # 3. [형식 검증]
        if not re.match(phone_pattern, s_tel):
            QMessageBox.warning(self, "형식 오류", f"보내는 분 연락처가 완성되지 않았습니다.\n({s_tel})")
            self.snd_tel.setFocus(); return
        
        if not re.match(phone_pattern, r_tel):
            QMessageBox.warning(self, "형식 오류", f"받는 분 연락처가 완성되지 않았습니다.\n({r_tel})")
            self.rcv_tel.setFocus(); return

        # 4. 저장
        self.data = {
            'snd_name': s_nm, 'snd_tel': s_tel, 'snd_addr': s_addr,
            'rcv_name': r_nm, 'rcv_tel': r_tel, 'rcv_addr': r_addr
        }
        self.accept()

class SingleDeliveryEditDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("배송지 상세 수정")
        self.resize(750, 520)
        self.setStyleSheet(MainStyles.MAIN_BG) # 표준 배경색 적용
        self.data = data
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        
        # 항목명(Label)용 표준 스타일
        lbl_style = "font-weight: bold; color: #2C3E50; font-size: 14px;"

        # --- [1. 보내는 사람 섹션] ---
        snd_group = QGroupBox("◈ 보내는 사람")
        snd_group.setStyleSheet(MainStyles.GROUP_BOX)
        snd_grid = QGridLayout(snd_group)
        snd_grid.setContentsMargins(15, 25, 15, 15)

        self.snd_nm = QLineEdit(str(self.data.get('snd_name') or "")); self.snd_nm.setStyleSheet(MainStyles.INPUT_LEFT)
        self.snd_tel = QLineEdit(str(self.data.get('snd_tel') or "")); self.snd_tel.setStyleSheet(MainStyles.INPUT_LEFT)
        self.snd_addr = QLineEdit(str(self.data.get('snd_addr') or "")); self.snd_addr.setStyleSheet(MainStyles.INPUT_LEFT)
        
        # 라벨 생성 및 스타일 적용
        l1 = QLabel("성함"); l1.setStyleSheet(lbl_style)
        l2 = QLabel("연락처"); l2.setStyleSheet(lbl_style)
        l3 = QLabel("주소"); l3.setStyleSheet(lbl_style)

        snd_grid.addWidget(l1, 0, 0); snd_grid.addWidget(self.snd_nm, 0, 1)
        snd_grid.addWidget(l2, 0, 2); snd_grid.addWidget(self.snd_tel, 0, 3)
        snd_grid.addWidget(l3, 1, 0); snd_grid.addWidget(self.snd_addr, 1, 1, 1, 3) # 주소는 3칸 차지
        main_layout.addWidget(snd_group)

        # --- [2. 받는 사람 섹션] ---
        rcv_group = QGroupBox("◈ 받는 사람")
        rcv_group.setStyleSheet(MainStyles.GROUP_BOX)
        rcv_grid = QGridLayout(rcv_group)
        rcv_grid.setContentsMargins(15, 25, 15, 15)

        self.rcv_nm = QLineEdit(str(self.data.get('rcv_name') or "")); self.rcv_nm.setStyleSheet(MainStyles.INPUT_LEFT)
        self.rcv_tel = QLineEdit(str(self.data.get('rcv_tel') or "")); self.rcv_tel.setStyleSheet(MainStyles.INPUT_LEFT)
        self.rcv_addr = QLineEdit(str(self.data.get('rcv_addr') or "")); self.rcv_addr.setStyleSheet(MainStyles.INPUT_LEFT)
        self.qty = QLineEdit(str(self.data.get('delivery_qty') or self.data.get('qty') or 1)); self.qty.setStyleSheet(MainStyles.INPUT_LEFT)
        self.msg = QLineEdit(str(self.data.get('dlvry_msg') or "")); self.msg.setStyleSheet(MainStyles.INPUT_LEFT)

        l4 = QLabel("받는분"); l4.setStyleSheet(lbl_style)
        l5 = QLabel("연락처"); l5.setStyleSheet(lbl_style)
        l6 = QLabel("주소"); l6.setStyleSheet(lbl_style)
        l7 = QLabel("수량"); l7.setStyleSheet(lbl_style)
        l8 = QLabel("메시지"); l8.setStyleSheet(lbl_style)

        rcv_grid.addWidget(l4, 0, 0); rcv_grid.addWidget(self.rcv_nm, 0, 1)
        rcv_grid.addWidget(l5, 0, 2); rcv_grid.addWidget(self.rcv_tel, 0, 3)
        rcv_grid.addWidget(l6, 1, 0); rcv_grid.addWidget(self.rcv_addr, 1, 1, 1, 3) # 주소 길게
        rcv_grid.addWidget(l7, 2, 0); rcv_grid.addWidget(self.qty, 2, 1)
        rcv_grid.addWidget(l8, 2, 2); rcv_grid.addWidget(self.msg, 2, 3)
        main_layout.addWidget(rcv_group)

        # 버튼부
        btns = QHBoxLayout()
        self.ok_btn = QPushButton(" 수정 내용 반영"); self.ok_btn.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.no_btn = QPushButton(" 취소"); self.no_btn.setStyleSheet(MainStyles.BTN_ACTION)
        self.ok_btn.clicked.connect(self.accept); self.no_btn.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(self.ok_btn); btns.addWidget(self.no_btn)
        main_layout.addLayout(btns)

    def get_data(self):
        # 팝업을 닫을 때 현재 입력된 정보를 딕셔너리로 반환
        return {
            'snd_name': self.snd_nm.text(), 'snd_tel': self.snd_tel.text(), 'snd_addr': self.snd_addr.text(),
            'rcv_name': self.rcv_nm.text(), 'rcv_tel': self.rcv_tel.text(), 'rcv_addr': self.rcv_addr.text(),
            'delivery_qty': self.qty.text(), 'dlvry_msg': self.msg.text()
        }

# =========================================================
# 2. 기존 배송 이력 조회 (NEW 뱃지 + 통합 로직)
# =========================================================
class PastAddressDialog(QDialog):
    def __init__(self, db, custm_id, limit_qty, parent=None):
        super().__init__(parent)
        self.db = db
        self.custm_id = custm_id
        self.limit_qty = int(limit_qty)
        self.selected_addrs = [] 
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setWindowTitle(f"배송지 선택 (최대 {self.limit_qty}건)")
        self.resize(800, 550) 
        self.setStyleSheet(MainStyles.MAIN_BG)

        layout = QVBoxLayout(self)
        layout.setSpacing(10); layout.setContentsMargins(20, 20, 20, 20)

        # [수정] 고객 ID로 고객명(custm_nm) 조회하기
        display_name = self.custm_id # 기본값은 ID
        try:
            # DB에서 이름 조회 쿼리 실행
            res = self.db.execute_query("SELECT custm_nm FROM m_customer WHERE custm_id = ?", (self.custm_id,))
            if res and res[0]['custm_nm']:
                display_name = res[0]['custm_nm'] # 이름이 있으면 이름으로 교체
        except Exception as e:
            print(f"고객명 조회 실패: {e}")

        # 상단 (신규버튼 포함)
        top = QHBoxLayout()
        # [수정] 제목에 ID 대신 조회한 고객명(display_name) 표시
        top.addWidget(QLabel(f"'{display_name}' 고객 배송 이력", styleSheet="font-size: 14px; font-weight: bold; color: #2D5A27;"))
        top.addStretch()
        
        # [신규 추가] 검색 영역
        search_layout = QHBoxLayout()
        self.edt_search = QLineEdit()
        self.edt_search.setPlaceholderText("받는 분 성함을 입력하세요...")
        self.edt_search.setStyleSheet(MainStyles.INPUT_LEFT)
        self.edt_search.setFixedHeight(30)
        # 엔터키를 누르면 바로 조회되도록 연결
        self.edt_search.returnPressed.connect(self.load_data)

        btn_search = QPushButton("조회")
        btn_search.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_search.setFixedWidth(60)
        btn_search.setFixedHeight(30)
        btn_search.clicked.connect(self.load_data)
        
        layout.addWidget(QLabel("※ 받는 분 정보를 확인하고 체크하세요.", styleSheet="color:#666; font-size:11px;"))

        # 테이블
        self.table = QTableWidget(0, 4)
        self.table.setStyleSheet(MainStyles.TABLE)
        self.table.setHorizontalHeaderLabels(["상태", "받는분", "연락처", "주소"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.select_single_row) # 더블클릭 -> 단일선택

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self.table.setColumnWidth(0, 85) # 뱃지 공간
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        # 하단 버튼
        bot = QHBoxLayout()
        btn_sel = QPushButton("선택 완료"); btn_sel.setStyleSheet(MainStyles.BTN_PRIMARY); btn_sel.setFixedWidth(100)
        btn_sel.clicked.connect(self.confirm_selection)
        btn_cls = QPushButton("닫기"); btn_cls.setStyleSheet(MainStyles.BTN_ACTION); btn_cls.setFixedWidth(80)
        btn_cls.clicked.connect(self.reject)
        
        bot.addStretch(); bot.addWidget(btn_sel); bot.addWidget(btn_cls)
        layout.addLayout(bot)

    def load_data(self):
        """기존 등록 데이터와 상관없이 DB의 과거 이력만 DISTINCT하게 로드"""
        if not self.custm_id: return

        # 검색창에서 텍스트 가져오기
        search_text = self.edt_search.text().strip() if hasattr(self, 'edt_search') else ""
        
        sql = """
            SELECT DISTINCT 
                rcv_name, rcv_tel, rcv_addr,
                snd_name, snd_tel, snd_addr
            FROM t_sales_delivery D
            JOIN t_sales_detail SD ON D.sale_detail_no = SD.sale_detail_no
            JOIN t_sales_master M ON SD.sales_no = M.sales_no
            WHERE M.custm_id = ? 
        """
        params = [self.custm_id]

        # [핵심] 검색어가 있을 경우 SQL 조건 추가
        if search_text:
            sql += " AND D.rcv_name LIKE ?"
            params.append(f"%{search_text}%")

        sql += " ORDER BY M.sales_no DESC LIMIT 100" # 검색 효율을 위해 한도를 조금 늘림

        try:
            results = self.db.execute_query(sql, tuple(params)) 
            self.table.setRowCount(0)
            for row in results: 
                self.insert_row_item(row, is_new=False)
        except Exception as e: 
            print(f"이력 조회 오류: {e}")
    def insert_row_item(self, data, is_new=False):
        """행 추가 공통 함수 (뱃지 & 자동체크 포함)"""
        
        # [🚨 핵심 수정] DB에서 온 Row 객체를 dict로 변환하여 .get() 오류 방지
        if data is not None and not isinstance(data, dict):
            try:
                data = dict(data)
            except Exception:
                pass # 변환 실패 시 그대로 진행 (혹은 에러 처리)

        r = 0 if is_new else self.table.rowCount()
        self.table.insertRow(r)

        # 데이터 추출 (.get() 사용 가능해짐)
        rcv = {k: str(data.get(k) or "") for k in ['rcv_name', 'rcv_tel', 'rcv_addr']}
        snd = {k: str(data.get(k) or "") for k in ['snd_name', 'snd_tel', 'snd_addr']}
        
        # 6개 항목 전체를 UserRole에 저장
        full_data = {**rcv, **snd}

        # 1. 체크박스 & 뱃지 영역
        cw = QWidget(); cl = QHBoxLayout(cw); cl.setContentsMargins(5,2,5,2); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox(); chk.setStyleSheet("QCheckBox::indicator { width: 18px; height: 18px; }")
        cl.addWidget(chk)

        if is_new:
            cl.addSpacing(5)
            badge = QLabel("NEW"); badge.setStyleSheet("background-color: #FF5722; color: white; font-size: 10px; font-weight: bold; border-radius: 4px; padding: 1px 4px;")
            cl.addWidget(badge)
        self.table.setCellWidget(r, 0, cw)
        
        # 2. 텍스트 아이템
        i_nm = QTableWidgetItem(rcv['rcv_name'])
        i_nm.setData(Qt.ItemDataRole.UserRole, full_data) # 데이터 숨김
        i_tel = QTableWidgetItem(rcv['rcv_tel'])
        i_addr = QTableWidgetItem(rcv['rcv_addr'])

        if is_new: # 신규는 파란색 볼드
            i_nm.setForeground(QBrush(QColor("#0066CC")))
            i_nm.setFont(make_app_font(9, weight=QFont.Weight.Bold))

        i_nm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_tel.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_addr.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.table.setItem(r, 1, i_nm); self.table.setItem(r, 2, i_tel); self.table.setItem(r, 3, i_addr)

    def confirm_selection(self):
        sel_rows = []
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 0)
            if w and w.findChild(QCheckBox).isChecked(): sel_rows.append(r)
        
        if not sel_rows: QMessageBox.warning(self, "알림", "선택된 항목이 없습니다."); return
        if len(sel_rows) > self.limit_qty: QMessageBox.warning(self, "초과", f"최대 {self.limit_qty}건만 가능합니다."); return

        self.selected_addrs = [self.table.item(r, 1).data(Qt.ItemDataRole.UserRole) for r in sel_rows]
        self.accept()

    def select_single_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.selected_addrs = [self.table.item(r, 1).data(Qt.ItemDataRole.UserRole)]
            self.accept()

# =========================================================
# 3. [신규] 고객 신규 등록 팝업 (ID 자동 채번)
# =========================================================
class CustomerRegisterDialog(QDialog):
    def __init__(self, db, farm_cd, parent=None):
        super().__init__(parent)
        self.db = db
        self.farm_cd = farm_cd
        self.new_cust_id = None 
        self.init_ui()
        self.generate_new_id() # 자동 채번 실행

    def init_ui(self):
        self.setWindowTitle("신규 고객 등록")
        self.resize(350, 250)
        self.setStyleSheet(MainStyles.MAIN_BG)

        layout = QVBoxLayout(self)
        layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20)

        # 폼 그룹
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 스타일
        def get_lbl(t): 
            l = QLabel(t); l.setStyleSheet("font-weight: bold; color: #555;")
            return l

        # 위젯
        self.edt_id = QLineEdit(); self.edt_id.setReadOnly(True)
        self.edt_id.setStyleSheet(MainStyles.INPUT_READONLY)
        
        self.edt_nm = QLineEdit(); self.edt_nm.setStyleSheet(MainStyles.INPUT_LEFT)
        self.edt_nm.setPlaceholderText("고객명")
        
        self.edt_tel = QLineEdit(); self.edt_tel.setStyleSheet(MainStyles.INPUT_LEFT)
        self.edt_tel.setPlaceholderText("010-0000-0000")

        form_layout.addRow(get_lbl("ID:"), self.edt_id)
        form_layout.addRow(get_lbl("이름(*):"), self.edt_nm)
        form_layout.addRow(get_lbl("연락처(*):"), self.edt_tel)
        
        layout.addLayout(form_layout)

        # 버튼
        btn_box = QHBoxLayout()
        btn_save = QPushButton("저장"); btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_save.clicked.connect(self.save_customer)
        btn_cancel = QPushButton("취소"); btn_cancel.setStyleSheet(MainStyles.BTN_ACTION)
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def generate_new_id(self):
        """가장 마지막 ID + 1"""
        try:
            sql = "SELECT MAX(custm_id) as last_id FROM m_customer WHERE farm_cd = ?"
            res = self.db.execute_query(sql, (self.farm_cd,))
            last_id = res[0]['last_id'] if res and res[0]['last_id'] else None
            
            if last_id:
                # 숫자만 추출해서 +1 (C001 -> 1 -> 2 -> C002)
                num = int(''.join(filter(str.isdigit, last_id)) or 0)
                self.new_cust_id = f"C{num + 1:03d}"
            else:
                self.new_cust_id = "C001"
            self.edt_id.setText(self.new_cust_id)
        except:
            self.edt_id.setText("ERROR")

    def save_customer(self):
        nm = self.edt_nm.text().strip()
        tel = self.edt_tel.text().strip()
        cid = self.edt_id.text()
        
        if not nm or not tel:
            QMessageBox.warning(self, "확인", "이름과 연락처는 필수입니다.")
            return

        sql = """
            INSERT INTO m_customer (custm_id, farm_cd, custm_nm, mobile, use_yn, reg_dt)
            VALUES (?, ?, ?, ?, 'Y', date('now'))
        """
        try:
            self.db.execute_query(sql, (cid, self.farm_cd, nm, tel))
            QMessageBox.information(self, "완료", f"[{nm}] 고객님이 등록되었습니다.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

#고객 조회 팝업
# =========================================================
# 4. [수정] 고객 조회 및 선택 (신규 등록 연결)
# =========================================================
class CustSearchDlg(QDialog):
    def __init__(self, db, ss, parent=None):
        super().__init__(parent)
        self.db = db
        self.ss = ss 
        self.sel_data = None 
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("고객 조회 및 선택")
        self.resize(600, 450)
        self.setStyleSheet(MainStyles.MAIN_BG)

        layout = QVBoxLayout(self)
        layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20)

        # 1. 검색 영역
        search_layout = QHBoxLayout()
        
        self.sch_in = QLineEdit()
        self.sch_in.setPlaceholderText("고객명 또는 휴대폰번호")
        self.sch_in.setStyleSheet(MainStyles.INPUT_LEFT)
        self.sch_in.setFixedHeight(35)
        self.sch_in.returnPressed.connect(self.search_data)
        
        btn_sch = QPushButton("조회")
        btn_sch.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_sch.setFixedWidth(60); btn_sch.setFixedHeight(35)
        btn_sch.clicked.connect(self.search_data)

        # [신규] 등록 버튼 추가 ★
        btn_new = QPushButton("+ 신규")
        btn_new.setStyleSheet(MainStyles.BTN_FETCH) # 오렌지색
        btn_new.setFixedWidth(60); btn_new.setFixedHeight(35)
        btn_new.clicked.connect(self.open_register_popup)
        
        search_layout.addWidget(self.sch_in)
        search_layout.addWidget(btn_sch)
        search_layout.addWidget(btn_new)
        layout.addLayout(search_layout)

        # 2. 결과 테이블
        self.tab = QTableWidget(0, 3)
        self.tab.setStyleSheet(MainStyles.TABLE) 
        self.tab.setHorizontalHeaderLabels(["고객ID", "고객명", "휴대폰"])
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setAlternatingRowColors(True) 
        self.tab.verticalHeader().setVisible(False) 
        self.tab.doubleClicked.connect(self.select_data)
        
        h = self.tab.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self.tab.setColumnWidth(0, 80)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.tab)

        # 3. 하단 버튼
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("선택완료"); btn_ok.setStyleSheet(MainStyles.BTN_PRIMARY); btn_ok.setFixedHeight(40)
        btn_ok.clicked.connect(self.select_data)
        btn_cls = QPushButton("닫기"); btn_cls.setStyleSheet(MainStyles.BTN_ACTION); btn_cls.setFixedHeight(40)
        btn_cls.clicked.connect(self.reject)

    # CustSearchDlg 클래스 내부에 추가하세요
    def search_data(self):
        """고객명 또는 휴대폰 번호로 m_customer 테이블 조회"""
        search_text = self.sch_in.text().strip()
        if not search_text:
            QMessageBox.warning(self, "알림", "검색어를 입력해주세요.")
            return

        # 1. 쿼리 작성 (고객명 또는 휴대폰 포함 검색)
        sql = """
            SELECT custm_id, custm_nm, mobile 
            FROM m_customer 
            WHERE farm_cd = ? 
              AND (custm_nm LIKE ? OR mobile LIKE ?)
            ORDER BY custm_nm ASC
        """
        params = (self.ss['farm_cd'], f"%{search_text}%", f"%{search_text}%")

        try:
            results = self.db.execute_query(sql, params)
            
            # 2. 테이블 초기화 후 데이터 채우기
            self.tab.setRowCount(0)
            for row_idx, row in enumerate(results):
                self.tab.insertRow(row_idx)
                # 데이터 배치
                self.tab.setItem(row_idx, 0, QTableWidgetItem(str(row['custm_id'])))
                self.tab.setItem(row_idx, 1, QTableWidgetItem(str(row['custm_nm'])))
                self.tab.setItem(row_idx, 2, QTableWidgetItem(str(row['mobile'])))
                
                # 중앙 정렬 등 스타일 적용
                for col in range(3):
                    self.tab.item(row_idx, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if not results:
                QMessageBox.information(self, "알림", "검색 결과가 없습니다.")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"고객 조회 중 에러 발생: {e}")

    def select_data(self):
        """테이블에서 선택된 고객 정보를 부모 창으로 전달"""
        curr_row = self.tab.currentRow()
        if curr_row >= 0:
            self.sel_data = {
                'id': self.tab.item(curr_row, 0).text(),
                'nm': self.tab.item(curr_row, 1).text(),
                'tel': self.tab.item(curr_row, 2).text()
            }
            self.accept()
        else:
            QMessageBox.warning(self, "선택", "리스트에서 고객을 먼저 선택해 주세요.")

        # CustSearchDlg 클래스 내부에 추가
    def open_register_popup(self):
        """[+ 신규] 버튼 클릭 시 호출: 고객 신규 등록 팝업을 띄움"""
        from sales_page import CustomerRegisterDialog # 같은 파일 내에 있으므로 임포트 확인
        
        # 1. 신규 등록 팝업 실행 (농장 코드 전달)
        dlg = CustomerRegisterDialog(self.db, self.ss['farm_cd'], self)
        
        if dlg.exec():
            # 2. 등록이 성공적으로 끝나면 (Accept)
            # 새로 등록한 고객의 이름을 검색창에 자동으로 넣고 바로 조회해줍니다.
            new_name = dlg.edt_nm.text().strip()
            if new_name:
                self.sch_in.setText(new_name)
                self.search_data() # 바로 조회 함수 호출

# 판매 리스트 팝업
class SalesSearchDialog(QDialog):
    # 호출 시 전달받는 인자 순서에 맞춰서 수정 (db, farm_cd, parent)
    def __init__(self, db_conn, farm_cd, parent=None):
        super().__init__(parent)
        self.db = db_conn          # 전달받은 DB 연결 객체 저장
        self.farm_cd = farm_cd     # 전달받은 농장 코드 저장
        self.selected_sales_no = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("판매 전표 조회")
        self.resize(900, 600) # 컬럼이 많으므로 조금 더 넉넉하게
        
        # [1] 전체 배경 및 폰트 적용 (MainStyles.MAIN_BG)
        self.setStyleSheet(MainStyles.MAIN_BG)

        layout = QVBoxLayout(self)
        layout.setSpacing(15) # 요소 간 간격 통일
        layout.setContentsMargins(20, 20, 20, 20) # 여백 확보

        # --- 1. 검색 조건 영역 (그룹박스 스타일 적용) ---
        search_group = QGroupBox("검색 조건")
        search_group.setStyleSheet(MainStyles.GROUP_BOX) # 그룹박스 표준 스타일
        search_group.setFixedHeight(80) # 높이 고정으로 깔끔하게
        
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(20, 15, 20, 15) # 내부 여백

        # 날짜 조건
        lbl_date = QLabel("판매일자:"); lbl_date.setStyleSheet(MainStyles.LBL_GRID_HEADER) # 라벨 스타일 (선택)
        search_layout.addWidget(lbl_date)
        
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setFixedWidth(130)
        self.date_edit.setFixedHeight(30)
        self.date_edit.setStyleSheet(MainStyles.COMBO) # 콤보/날짜 표준 스타일
        search_layout.addWidget(self.date_edit)

        search_layout.addSpacing(30) # 조건 사이 간격

        # 주문자명 조건
        lbl_name = QLabel("주문자명:"); lbl_name.setStyleSheet(MainStyles.LBL_GRID_HEADER)
        search_layout.addWidget(lbl_name)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("고객명을 입력하세요...")
        self.name_input.setFixedWidth(180)
        self.name_input.setFixedHeight(30)
        self.name_input.setStyleSheet(MainStyles.INPUT_LEFT) # 입력창 표준 스타일
        # 엔터키 연결
        self.name_input.returnPressed.connect(self.search_data)
        search_layout.addWidget(self.name_input)

        search_layout.addStretch()

        # 조회 버튼 (MainStyles.BTN_PRIMARY)
        self.btn_query = QPushButton("조회")
        self.btn_query.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_query.setFixedWidth(80)
        self.btn_query.setFixedHeight(35)
        self.btn_query.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_query.clicked.connect(self.search_data)
        search_layout.addWidget(self.btn_query)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # --- 2. 결과 테이블 영역 ---
        self.table = QTableWidget(0, 6)
        self.table.setStyleSheet(MainStyles.TABLE) # [핵심] 테이블 표준 스타일
        
        self.table.setHorizontalHeaderLabels([
            "판매번호", "판매일자", "주문자명", "총 합계금액", "미수금", "비고"
        ])
        
        # 기본 설정
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True) # 가독성 향상
        self.table.verticalHeader().setVisible(False) # 행 번호 숨김 (깔끔함)
        self.table.doubleClicked.connect(self.accept_selection)
        
        # 헤더 디자인 및 컬럼 너비 최적화
        header = self.table.horizontalHeader()
        # 내용에 따라 적절히 분배 (금액은 고정, 비고/이름은 늘림)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # 판매번호
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed) # 날짜
        self.table.setColumnWidth(1, 100)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # 주문자명
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed) # 합계금액
        self.table.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed) # 미수금
        self.table.setColumnWidth(4, 100)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # 비고 (나머지 채움)
        
        layout.addWidget(self.table)

        # --- 3. 하단 버튼 영역 ---
        btn_box = QHBoxLayout()
        
        # 닫기 버튼 (BTN_ACTION - 회색)
        self.btn_close = QPushButton("닫기")
        self.btn_close.setStyleSheet(MainStyles.BTN_ACTION)
        self.btn_close.setFixedWidth(80)
        self.btn_close.setFixedHeight(40)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)
        
        # 전표 선택 버튼 (BTN_PRIMARY - 메인 컬러) - 긍정적 액션이므로 Primary 추천
        self.btn_select = QPushButton("전표 선택")
        self.btn_select.setStyleSheet(MainStyles.BTN_PRIMARY) 
        self.btn_select.setFixedWidth(120)
        self.btn_select.setFixedHeight(40)
        self.btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select.clicked.connect(self.accept_selection)
        
        btn_box.addStretch() # 버튼 우측 정렬
        btn_box.addWidget(self.btn_select)
        btn_box.addWidget(self.btn_close)
        layout.addLayout(btn_box)

    def search_data(self):
        search_date = self.date_edit.date().toString("yyyy-MM-dd")
        search_name = self.name_input.text().strip()

        try:
            if hasattr(self.db, 'conn'): cur = self.db.conn.cursor()
            elif hasattr(self.db, 'connection'): cur = self.db.connection.cursor()
            else: cur = self.db.cursor() 

            # ★ 쿼리 수정: m_customer 테이블을 조인하여 정확한 이름을 가져옵니다.
            # sales_dt가 'YYYY-MM-DD'/'YYYYMMDD'로 혼재할 수 있어 정규화 비교를 사용합니다.
            sales_dt_norm = (
                "CASE "
                "WHEN M.sales_dt IS NULL THEN NULL "
                "WHEN length(M.sales_dt)=10 AND instr(M.sales_dt, '-')=5 THEN M.sales_dt "
                "WHEN length(M.sales_dt)=8 THEN substr(M.sales_dt,1,4)||'-'||substr(M.sales_dt,5,2)||'-'||substr(M.sales_dt,7,2) "
                "ELSE M.sales_dt END"
            )
            query = """
                SELECT 
                    M.sales_no, 
                    M.sales_dt, 
                    (SELECT custm_nm FROM m_customer WHERE custm_id = M.custm_id AND farm_cd = M.farm_cd) as custm_nm,
                    M.tot_item_amt, 
                    M.tot_unpaid_amt, 
                    M.rmk
                FROM t_sales_master M
                WHERE M.farm_cd = ? AND {sales_dt_norm} = ?
            """
            params = [self.farm_cd, search_date]

            if search_name:
                query += " AND custm_nm LIKE ?"
                params.append(f"%{search_name}%")

            query += " ORDER BY M.sales_no DESC"

            cur.execute(query.format(sales_dt_norm=sales_dt_norm), params)
            rows = cur.fetchall()

            self.table.setRowCount(0)
            for row_idx, row_data in enumerate(rows):
                self.table.insertRow(row_idx)
                for col_idx, value in enumerate(row_data):
                    if col_idx in [3, 4]: # 금액 포맷
                        val = value if value else 0
                        item = QTableWidgetItem(f"{val:,.0f}")
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    else:
                        item = QTableWidgetItem(str(value) if value else "")
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(row_idx, col_idx, item)

        except Exception as e:
            QMessageBox.critical(self, "조회 오류", f"데이터 로드 실패: {e}")

    def accept_selection(self):
        """선택된 행의 판매번호를 저장하고 팝업 닫기"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.selected_sales_no = self.table.item(current_row, 0).text()
            self.accept()
        else:
            QMessageBox.warning(self, "선택 확인", "가져올 전표를 먼저 선택하세요.")

# 판매관리 메인페이지
class SalesPage(QWidget):
    # 생성자에서 db_manager와 session을 받도록 매개변수 추가
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session  # 세션 전체 저장
        
        # [수정] 세션 꾸러미에서 필요한 정보만 쏙쏙 꺼냅니다.
        self.farm_cd = session.get('farm_cd')
        self.user_id = session.get('user_id')

        # 코드 매니저 초기화 (farm_cd 전달)
        self.code_mgr = CodeManager(self.db, self.farm_cd)
        # [NEW] 회계/장부 매니저 연결
        self.acct_mgr = AccountManager(db_manager, self.farm_cd)
        
        # [추가] 배송지 데이터를 품목 행(row)별로 저장할 딕셔너리
        # Key: 행번호(int), Value: 배송지 리스트(List[dict])
        self.delivery_map = {} 
        
        # 변수초기화
        self.current_sales_no = None  # 현재 작업 중인 전표 번호 (상태 관리용)
        self.custm_id = None          # 선택된 거래처 코드 (상태 관리용)
        
        # 디자인 가이드 적용 및 UI 초기화

        self._is_rendering = False  # 렌더링 중복 실행 방지용 플래그
        self.is_loading = False     # 지금 데이터를 불러오는 중인지 확인하는 변수

        self.init_ui()               # 화면구성
        self.init_sales_type_combo() # [여기!] 화면이 뜨자마자 DB에서 코드를 가져옴

    # 수입(IN)계정코드/코드명 가져오기
    def init_sales_type_combo(self):
        """[수정] DB에서 '매출(RV)' 관련 최하위(Level 4) 계정 코드 로드"""
        # 기존 내용 초기화
        self.sales_tp.clear()
        
        # [수정] 하드코딩 SQL 삭제 -> AccountManager 사용
        if hasattr(self, 'acct_mgr'):
            # RV(수익) 코드 중 4레벨(상세)만 가져오기
            results = self.acct_mgr.get_account_codes('RV', target_level=4)
            
            if not results:
                self.sales_tp.addItem("계정코드 없음", "")
                return

            for row in results:
                # row는 딕셔너리 형태 {'acct_nm':..., 'acct_cd':...}
                self.sales_tp.addItem(row['acct_nm'], row['acct_cd'])

    def init_ui(self):
        # 1. 전체 레이아웃 (스크롤 영역 포함)
        self.main_vbox = QVBoxLayout(self)
        
        # 스크롤 영역 생성
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # 스크롤 안에 들어갈 컨테이너 위젯
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.container.setMinimumWidth(0)
        self.container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.main_layout.setSpacing(20)

        # ---------------------------------------------------------
        # 1. 거래 마스터 영역 (좌: 입력부 / 우: 금액정보 및 버튼)
        # ---------------------------------------------------------
        self.master_group = QGroupBox("1. 거래 마스터 (종합 요약)")
        self.master_group.setStyleSheet(MainStyles.GROUP_BOX)
        master_layout = QGridLayout()
        master_layout.setContentsMargins(15, 15, 15, 15)
        master_layout.setSpacing(10)

        # --- [좌측 입력 위젯 구성] ---
        # 전표번호 & 판매번호 (ReadOnly)
        self.slip_no = QLineEdit(); self.slip_no.setReadOnly(True); self.slip_no.setPlaceholderText("자동 생성")
        self.slip_no.setStyleSheet(MainStyles.INPUT_CENTER + "background-color: #F5F5F5; color: #888888;")
        
        self.sales_no = QLineEdit(); self.sales_no.setReadOnly(True); self.sales_no.setPlaceholderText("자동 생성")
        self.sales_no.setStyleSheet(MainStyles.INPUT_CENTER + "background-color: #F5F5F5; color: #888888;")

        # 고객명 + 조회 버튼 (🔍)
        self.custm_nm = QLineEdit(); self.custm_nm.setStyleSheet(MainStyles.INPUT_CENTER)
        self.btn_cust_search = QPushButton("🔍")
        self.btn_cust_search.setFixedWidth(40); 
        self.btn_cust_search.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_cust_search.clicked.connect(self.open_cust_sch)
        cust_search_lay = QHBoxLayout(); 
        cust_search_lay.addWidget(self.custm_nm); 
        cust_search_lay.addWidget(self.btn_cust_search); 
        cust_search_lay.setContentsMargins(0,0,0,0)

        # 계산서여부 & 발행일자
        self.receipt_yn = QComboBox(); self.receipt_yn.addItems(["N", "Y"]); 
        self.receipt_yn.setStyleSheet(MainStyles.COMBO)        
        self.receipt_yn.installEventFilter(self)
        self.receipt_dt = QDateEdit(QDate.currentDate(), calendarPopup=True); 
        self.receipt_dt.setStyleSheet(MainStyles.COMBO)
        self.receipt_dt.installEventFilter(self)
        
        # 판매일자 & 판매유형 & 비고
        self.sales_dt = QDateEdit(QDate.currentDate(), calendarPopup=True); 
        self.sales_dt.setStyleSheet(MainStyles.COMBO)
        self.sales_dt.installEventFilter(self)
        self.sales_tp = QComboBox(); 
        self.sales_tp.setStyleSheet(MainStyles.COMBO)
            
        self.rmk = QLineEdit(); 
        self.rmk.setStyleSheet(MainStyles.INPUT_CENTER)

        # --- [좌측 레이아웃 배치] ---
        # 0행: 전표번호 | 판매번호
        master_layout.addWidget(QLabel("전표번호:", styleSheet=MainStyles.LBL_GRID_HEADER), 0, 0)
        master_layout.addWidget(self.slip_no, 0, 1)
        master_layout.addWidget(QLabel("판매번호:", styleSheet=MainStyles.LBL_GRID_HEADER), 0, 2)
        master_layout.addWidget(self.sales_no, 0, 3)

        # 1행: 고객명 | 계산서여부
        master_layout.addWidget(QLabel("고객명:", styleSheet=MainStyles.LBL_GRID_HEADER), 1, 0)
        master_layout.addLayout(cust_search_lay, 1, 1)
        master_layout.addWidget(QLabel("판매일자:", styleSheet=MainStyles.LBL_GRID_HEADER), 1, 2)
        master_layout.addWidget(self.sales_dt, 1, 3)

        # 2행: 발행일자 | 판매일자
        master_layout.addWidget(QLabel("계산서여부:", styleSheet=MainStyles.LBL_GRID_HEADER), 2, 0)
        master_layout.addWidget(self.receipt_yn, 2, 1)
        master_layout.addWidget(QLabel("발행일자:", styleSheet=MainStyles.LBL_GRID_HEADER), 2, 2)
        master_layout.addWidget(self.receipt_dt, 2, 3)
        
        # 3행 신규 위젯: 계산서번호 & 결제방식 (PA01 연동)
        self.bill_no = QLineEdit(); self.bill_no.setStyleSheet(MainStyles.INPUT_CENTER)
        self.bill_no.setPlaceholderText("계산서/승인번호")

        # 결제방식
        self.pay_method_cd = QComboBox(); 
        self.pay_method_cd.setStyleSheet(MainStyles.COMBO)
        # 1. 현금성 자산(AS01) 가져오기
        cash_list = self.acct_mgr.get_account_codes('AS', target_level=4)
        
        self.pay_method_cd.addItem("결제방식 선택", "")
        # 1. 현금성 자산(AS01) 가져오기
        for item in cash_list:
            self.pay_method_cd.addItem(item['acct_nm'], item['acct_cd'])            
        self.pay_method_cd.installEventFilter(self)

        master_layout.addWidget(QLabel("계산서번호:", styleSheet=MainStyles.LBL_GRID_HEADER), 3, 0)
        master_layout.addWidget(self.bill_no, 3, 1)
        master_layout.addWidget(QLabel("결제방식:", styleSheet=MainStyles.LBL_GRID_HEADER), 3, 2)
        master_layout.addWidget(self.pay_method_cd, 3, 3)

        # 4행: 기존 판매유형과 비고를 한 줄 아래로 이동
        master_layout.addWidget(QLabel("판매유형:", styleSheet=MainStyles.LBL_GRID_HEADER), 4, 0)
        master_layout.addWidget(self.sales_tp, 4, 1)
        master_layout.addWidget(QLabel("비고:", styleSheet=MainStyles.LBL_GRID_HEADER), 4, 2)
        master_layout.addWidget(self.rmk, 4, 3, 1, 1)

        # --- [우측 영역: 버튼 및 금액 정보 테이블] ---
        # 상단 버튼부
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("신규"); self.btn_new.clicked.connect(self.clear_sales_form)
        self.btn_search = QPushButton("조회")     
        self.btn_search.clicked.connect(self.open_search_dialog) # 조회 버튼 연결 
        self.btn_delete = QPushButton("삭제")
        for b in [self.btn_new, self.btn_search, self.btn_delete]:
            b.setStyleSheet(MainStyles.BTN_SECONDARY); b.setFixedHeight(30)
            btn_layout.addWidget(b)
        master_layout.addLayout(btn_layout, 0, 4)
        self.btn_delete.clicked.connect(self.delete_sales_data) # 삭제 버튼 연결(함께 처리 권장)

        # 금액 정보 패널 (1~3행 병합 배치)
        # 4행은 비고 칸이 사용할 수 있도록 rowSpan을 3으로 설정합니다.
        # 하단 금액 정보 패널
        fin_panel = QFrame(); fin_panel.setStyleSheet(MainStyles.CARD)
        fin_grid = QGridLayout(fin_panel)
        fin_grid.setContentsMargins(10, 10, 10, 10)
        master_layout.addWidget(fin_panel, 1, 4, 3, 1)         
        master_layout.setColumnStretch(3, 1)  # 비고 입력칸이 늘어나는 컬럼
        master_layout.setColumnStretch(4, 0)  # 우측 패널 컬럼은 늘림 최소화(이미 내부에서 카드가 잡음)

        # 금액 정보 위젯 (ReadOnly 항목들)
        self.tot_sales_amt = QLineEdit("0"); self.tot_sales_amt.setReadOnly(True)
        self.tot_ship_fee = QLineEdit("0"); self.tot_ship_fee.setReadOnly(True)
        self.tot_pay_amt = QLineEdit("0"); self.tot_pay_amt.setReadOnly(True)
        self.tot_unpaid_amt = QLineEdit("0"); self.tot_unpaid_amt.setReadOnly(True)

        # 금액 정보 위젯 (입력 가능 항목들)
        self.auction_fee = QLineEdit("0") # 경매수수료
        self.extra_cost = QLineEdit("0")  # 기타비용

        # 공통 스타일 및 정렬 적용
        amount_widgets = [self.tot_sales_amt, self.tot_ship_fee, self.auction_fee, self.extra_cost, self.tot_pay_amt, self.tot_unpaid_amt]
        for aw in amount_widgets:
            aw.setStyleSheet(MainStyles.INPUT_CENTER)
            aw.setAlignment(Qt.AlignmentFlag.AlignRight)

        # 금액 정보 그리드 배치
        # 4. 그리드 배치 (라벨 스타일 포함)
        fin_grid.addWidget(QLabel("상품합계(A):", styleSheet=MainStyles.LBL_TEXT_LEFT_LIGHT), 0, 0)
        self.tot_sales_amt.setStyleSheet(MainStyles.LBL_TEXT_RIGHT_LIGHT)
        fin_grid.addWidget(self.tot_sales_amt, 0, 1)
        fin_grid.addWidget(QLabel("배송비합계(B):", styleSheet=MainStyles.LBL_TEXT_LEFT_LIGHT), 0, 2)
        self.tot_ship_fee.setStyleSheet(MainStyles.LBL_TEXT_RIGHT_LIGHT)
        fin_grid.addWidget(self.tot_ship_fee, 0, 3)
        
        fin_grid.addWidget(QLabel("경매수수료:", styleSheet=MainStyles.LBL_TEXT_LEFT_LIGHT), 1, 0)
        self.auction_fee.setStyleSheet(MainStyles.LBL_TEXT_RIGHT_LIGHT)
        fin_grid.addWidget(self.auction_fee,1,1)
        fin_grid.addWidget(QLabel("기타비용:", styleSheet=MainStyles.LBL_TEXT_LEFT_LIGHT), 1, 2)
        self.extra_cost.setStyleSheet(MainStyles.LBL_TEXT_RIGHT_LIGHT)
        fin_grid.addWidget(self.extra_cost, 1, 3)
        
        # 하단 합계 라벨은 더 강조
        # 수금액합계: 초록색 계열 하이라이트
        fin_grid.addWidget(QLabel("수금액합계(C):", styleSheet=MainStyles.LBL_TEXT_LEFT_LIGHT+"color: #2E7D32;"), 2, 0)
        self.tot_pay_amt.setStyleSheet(MainStyles.LBL_TEXT_RIGHT_LIGHT + "color: #2E7D32;")
        fin_grid.addWidget(self.tot_pay_amt, 2, 1)
        fin_grid.addWidget(QLabel("미수금합계(A+B-C):", styleSheet=MainStyles.LBL_TEXT_LEFT_LIGHT+"color: #C62828;"), 2, 2)
        # 미수금합계: 빨간색 계열 하이라이트
        self.tot_unpaid_amt.setStyleSheet(MainStyles.LBL_TEXT_RIGHT_LIGHT + "font-size:12px;"+ "color: #C62828;")
        fin_grid.addWidget(self.tot_unpaid_amt, 2, 3)

        self.master_group.setLayout(master_layout)
        self.main_layout.addWidget(self.master_group)

        # ---------------------------------------------------------
        # 2. 품목 및 물류 설정 영역 (2단)
        # ---------------------------------------------------------
        self.detail_group = QGroupBox("2. 판매 상세 내역")
        self.detail_group.setStyleSheet(MainStyles.GROUP_BOX)
        self.detail_group.setMinimumHeight(280) 
        
        d_layout = QVBoxLayout()
        self.item_table = QTableWidget(0, 12) 
        self.item_table.setStyleSheet(MainStyles.TABLE)
        
        # [수정] 마우스 오버 시 자동 로드되는 기능 제거 (마우스 트래킹 OFF)
        self.item_table.setMouseTracking(False) 
        self.item_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.item_table.setHorizontalHeaderLabels([
            "선택", "품목", "품종", "규격", "등급", "수량", "단가", 
            "가액", "배송비", "합계", "배송방식", "삭제"
        ])

        header = self.item_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        # [수정] 컬럼 너비 최적화 (조회 버튼 60로 확대하여 글자 잘림 방지)
        column_widths = {
            0: 60,  # 선택
            1: 90,  # 품목
            2: 90,  # 품종
            3: 90,  # 규격
            4: 85,  # 등급
            5: 50,  # 수량
            6: 70,  # 단가
            7: 80,  # 가액
            8: 70,  # 배송비
            9: 90,  # 합계
            10: 100, # 배송방식
            11: 50   # 삭제
        }
        for col, width in column_widths.items():
            self.item_table.setColumnWidth(col, width)

        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # 품종 컬럼 Stretch
        
        self.btn_item_add = QPushButton("+ 품목 추가")
        self.btn_item_add.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_item_add.clicked.connect(self.add_item_row)
        
        d_layout.addWidget(self.item_table)
        d_layout.addWidget(self.btn_item_add)
        self.detail_group.setLayout(d_layout)
        self.main_layout.addWidget(self.detail_group)

        # [3] 하단 배송/결제 관리 (함수 호출로 대체)
        self.bottom_section = self.init_bottom_section()
        self.main_layout.addWidget(self.bottom_section) # 메인 레이아웃에 추가

        # 최종 저장 버튼 #
        self.btn_save = QPushButton("💾 매출 정보 최종 저장"); 
        self.btn_save.setStyleSheet(MainStyles.BTN_PRIMARY); 
        self.btn_save.setFixedHeight(45)
        self.main_layout.addWidget(self.btn_save)
        self.btn_save.clicked.connect(self.execute_full_save)

        # 스크롤 영역 설정 (기존 코드 유지)
        self.scroll_area.setWidget(self.container)
        self.main_vbox.addWidget(self.scroll_area)

        #self.item_table.itemSelectionChanged.connect(self.on_dlvry_item_selected)
        self.selected_pay_row = -1  # ★ [추가] 수금 내역 선택된 행 기억 변수

    # ---------------------------------------------------------
    # [3] 하단 그룹: 배송 및 결제 관리 (메인 진입점)
    # ---------------------------------------------------------
    def init_bottom_section(self):
        """하단 배송/결제 그룹박스와 탭 위젯을 생성합니다."""
        self.bottom_group = QGroupBox("3. 배송 및 결제 관리")
        self.bottom_group.setStyleSheet(MainStyles.GROUP_BOX)
        self.bottom_group.setMinimumHeight(600)

        layout = QVBoxLayout()
        
        # 탭 위젯 설정
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS)

        # 각 탭 생성 함수 호출 (코드를 분리하여 가독성 확보)
        self.tab_delivery = self.create_delivery_tab()
        self.tab_pay = self.create_pay_tab()

        # 탭 추가
        self.tabs.addTab(self.tab_delivery, "🚚 배송지 목록")
        self.tabs.addTab(self.tab_pay, "💰 수금 내역")

        layout.addWidget(self.tabs)
        self.bottom_group.setLayout(layout)

        # 메인 레이아웃에 그룹박스 추가 (init_ui에서 호출 시 사용됨)
        # self.layout.addWidget(self.bottom_group) # (참고용)
        return self.bottom_group

    # ---------------------------------------------------------
    # [3-1] 배송지 탭 생성 (Tab 1)
    # ---------------------------------------------------------
    def create_delivery_tab(self):
        """배송지 관리 탭의 UI를 구성합니다."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        # [A] 버튼 툴바 (왼쪽: 관리 / 오른쪽: 엑셀)
        btn_layout = QHBoxLayout()

        # 1. 왼쪽 그룹: 직접 관리
        self.btn_manual_reg = QPushButton("➕ 등록"); self.btn_manual_reg.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_history = QPushButton("🔍 최근이력"); self.btn_history.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_select_all = QPushButton("✔ 전체선택"); self.btn_select_all.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_del_row = QPushButton("🗑 선택삭제"); self.btn_del_row.setStyleSheet(MainStyles.BTN_ACTION)

        # 버튼 연결
        self.btn_manual_reg.clicked.connect(self.open_manual_registration)
        self.btn_history.clicked.connect(self.open_history_popup_from_bottom)
        self.btn_select_all.clicked.connect(self.select_all_delivery_rows)
        self.btn_del_row.clicked.connect(self.delete_delivery_row)

        # 상태 라벨
        self.lbl_selected_status = QLabel("선택된 주문 없음")
        self.lbl_selected_status.setFixedWidth(280)
        self.lbl_selected_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_selected_status.setStyleSheet("font-size: 13px; color: #2E7D32; font-weight: bold;")

        # 왼쪽 위젯 배치
        for w in [self.btn_manual_reg, self.btn_history, self.btn_select_all, self.btn_del_row, self.lbl_selected_status]:
            btn_layout.addWidget(w)

        # --- 중앙 스프링 (밀어내기) ---
        btn_layout.addStretch()

        # 2. 오른쪽 그룹: 엑셀 기능
        self.btn_form_down = QPushButton("📄 양식받기"); self.btn_form_down.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_excel_upload = QPushButton("📥 엑셀업로드"); self.btn_excel_upload.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_excel_down = QPushButton("📤 엑셀다운로드"); self.btn_excel_down.setStyleSheet(MainStyles.BTN_SECONDARY)

        # 버튼 연결
        self.btn_form_down.clicked.connect(self.download_excel_form)
        self.btn_excel_upload.clicked.connect(self.upload_excel_delivery)
        self.btn_excel_down.clicked.connect(self.download_delivery_list)

        # 오른쪽 위젯 배치
        for w in [self.btn_form_down, self.btn_excel_upload, self.btn_excel_down]:
            btn_layout.addWidget(w)

        layout.addLayout(btn_layout)

        # [B] 배송지 테이블
        self.dlvry_table = QTableWidget(0, 9)
        self.dlvry_table.setStyleSheet(MainStyles.TABLE)
        self.dlvry_table.setHorizontalHeaderLabels([
            "보내는분", "보내는연락처", "보내는주소", 
            "받는분", "받는연락처", "받는주소", 
            "수량", "배송메시지", "송장번호"
        ])
        self.dlvry_table.setMinimumHeight(350)
        
        # 테이블 옵션 (선택모드, 수정불가 등)
        self.dlvry_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dlvry_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.dlvry_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dlvry_table.setMouseTracking(False) # 오버 효과 제거

        # 더블클릭 이벤트 연결
        self.dlvry_table.cellDoubleClicked.connect(self.on_dlvry_table_double_clicked)

        layout.addWidget(self.dlvry_table)
        
        return tab

    # ---------------------------------------------------------
    # [3-2] 수납(결제) 탭 생성 (Tab 2) - ★ MainStyles 정석 적용 ★
    # ---------------------------------------------------------
    def create_pay_tab(self):
        """수납 내역 탭의 UI를 구성합니다."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        # [수정] 삭제 바구니 및 상태 변수 초기화 (init_ui나 생성자에서 호출 권장)
        self.delete_basket = [] 
        self.is_dirty = False

        # [A] 버튼 툴바
        btn_layout = QHBoxLayout()
        
        # 버튼도 표준 스타일 적용
        self.btn_pay_add = QPushButton("➕ 등록"); self.btn_pay_add.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_pay_edit = QPushButton("✏️ 수정"); self.btn_pay_edit.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_pay_del = QPushButton("🗑️ 삭제"); self.btn_pay_del.setStyleSheet(MainStyles.BTN_SECONDARY)

        # 버튼 연결
        self.btn_pay_add.clicked.connect(self.add_pay_row)
        self.btn_pay_edit.clicked.connect(self.focus_pay_row)
        self.btn_pay_del.clicked.connect(self.delete_pay_row)

        # 버튼 배치
        for b in [self.btn_pay_add, self.btn_pay_edit, self.btn_pay_del]:
            b.setFixedWidth(80)
            btn_layout.addWidget(b)
        
        # [지기님 제안] 실시간 합계 레이블 추가 (버튼 오른쪽)
        self.lbl_pay_summary = QLabel("총 매출액: 0 | 수금 합계: 0 | 잔액: 0")
        self.lbl_pay_summary.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
        btn_layout.addWidget(self.lbl_pay_summary)
        
        btn_layout.addStretch() 
        layout.addLayout(btn_layout)

        # [B] 수납 테이블 설정
        self.pay_table = QTableWidget(0, 5)
        self.pay_table.setHorizontalHeaderLabels(["선택", "수금일자", "입금수단", "입금액", "비고"])

        # 1. 기본 선택 모드 끄기 (파란색/회색 시스템 하이라이트 제거 -> 노란색만 남음)
        self.pay_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)        
        # 2. 포커스 테두리 제거 (선택 시 점선 테두리 제거)
        self.pay_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)        
        # 3. 마우스 호버(Hover) 효과 투명화 (마우스 올려도 색 안 변함)
        self.pay_table.setStyleSheet("""
            QTableWidget::item:hover { background-color: transparent; }
            QTableWidget::item:selected { background-color: transparent; }
        """)
        
        # 컬럼 너비 설정 (선택 버튼은 좁게)
        self.pay_table.setColumnWidth(0, 50)  # 선택
        self.pay_table.setColumnWidth(1, 120) # 날짜
        self.pay_table.setColumnWidth(2, 120) # 수단
        self.pay_table.setColumnWidth(3, 100) # 금액
        self.pay_table.setColumnWidth(4, 200) # 비고
        
        # ★ 핵심: 이거 한 줄이면 헤더까지 다 예뻐져야 합니다!
        self.pay_table.setStyleSheet(MainStyles.TABLE)
        
        # 헤더 설정
        #headers = ["수납일자", "입금계좌(수단)", "금액", "비고"]
        #self.pay_table.setHorizontalHeaderLabels(headers)
        
        # 크기 조절 (내용에 맞게)
        h_header = self.pay_table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # 날짜
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # 금액
        
        # 기타 옵션 (표준 스타일에 맞춰서)
        self.pay_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pay_table.setAlternatingRowColors(True) # 줄무늬 효과
        self.pay_table.verticalHeader().setVisible(False) # 행 번호 숨김
        # 마우스 오버 시 색상 변화 제거 (표준 스타일 준수)
        self.pay_table.setMouseTracking(False) 

        layout.addWidget(self.pay_table)

        return tab

    # 판매관리마스터 화면 초기화
    def clear_sales_form(self):
        """화면의 모든 데이터를 초기화하고 신규 등록 모드로 전환합니다."""
        # 1. 상태 변수 및 메모리 데이터 초기화
        self.current_sales_no = None
        self.custm_id = None
        self.active_row = -1  # [추가] 선택된 행 상태 초기화
        self.delivery_map = {}  # [추가] 상세 배송지 데이터 메모리 초기화

        # 2. 마스터 입력 필드 초기화
        self.slip_no.clear()
        self.sales_no.clear()
        self.sales_dt.setDate(QDate.currentDate())
        self.custm_nm.clear()
        self.sales_tp.setCurrentIndex(0)
        self.rmk.clear()
        self.bill_no.clear()
        self.pay_method_cd.setCurrentIndex(0)

        # 3. 모든 테이블 UI 초기화
        self.item_table.setRowCount(0)  # 2단 품목 상세
        self.pay_table.setRowCount(0)   # 3단 수납 내역
        self.dlvry_table.setRowCount(0) # [추가] 3단 배송지 목록 UI 초기화

        # 4. 안내 라벨 및 상태 초기화
        if hasattr(self, 'lbl_selected_status'):
            self.lbl_selected_status.setText("선택된 주문 없음") # [추가] 라벨 초기화

        # 5. 기타 비용 및 금액 라벨 초기화
        if hasattr(self, 'auction_fee'): self.auction_fee.setText("0")
        if hasattr(self, 'extra_cost'): self.extra_cost.setText("0")
        
        self.tot_sales_amt.setText("0")
        self.tot_ship_fee.setText("0")
        self.tot_pay_amt.setText("0")
        self.tot_unpaid_amt.setText("0")
        
        # 6. 사용자 편의를 위해 품목 빈 줄 하나 추가
        self.add_item_row()
        
        print("화면 및 모든 데이터 리스트가 리셋되었습니다. (신규 모드)")

    # TASK 2: 조회 로직
    def open_search_dialog(self):
        dialog = SalesSearchDialog(self.db, self.session['farm_cd'], self)
        if dialog.exec():
            sales_no = dialog.selected_sales_no
            if sales_no:
                self.load_sales_data(sales_no)

    # 고객조회로직
    def open_cust_sch(self):
        """판매 화면: 고객 조회 버튼 클릭 시 호출"""
        dlg = CustSearchDlg(self.db, self.session, self)
        
        if dlg.exec():
            if dlg.sel_data:
                self.custm_nm.setText(dlg.sel_data['nm'])
                # ★ 중요 수정: self.sel_cust_id -> self.custm_id 로 변경
                # 이렇게 해야 배송 팝업에서 이 ID를 가져다 쓸 수 있습니다.
                self.custm_id = dlg.sel_data['id'] 
                print(f"선택 고객: {dlg.sel_data['nm']} ({self.custm_id})")

    def load_sales_data(self, sales_no):
        if not sales_no: return # 📍 번호가 없으면 리로드 금지
        self.is_loading = True
        """팝업에서 선택한 전표 정보를 화면에 완벽하게 복원"""
        self.delivery_map = {}
        try:
            # 1. 마스터 정보 로드
            master = self.db.execute_query(
                "SELECT * FROM t_sales_master WHERE sales_no = ? AND farm_cd = ?",
                (sales_no, self.session['farm_cd'])
            )
            if not master: 
                QMessageBox.warning(self, "로드 실패", f"판매번호 [{sales_no}]를 찾을 수 없습니다.")
                self.clear_sales_form() # 데이터를 못 찾으면 빈 폼이라도 보여줌
                return
            m = master[0]

            # 마스터 필드 복원
            self.current_sales_no = m['sales_no']
            self.sales_no.setText(m['sales_no'])
            self.sales_dt.setDate(QDate.fromString(m['sales_dt'], "yyyy-MM-dd"))
            
            # [고객 정보 복원]
            self.custm_id = m['custm_id'] 
            cust_res = self.db.execute_query(
                "SELECT custm_nm FROM m_customer WHERE custm_id = ? AND farm_cd = ?",
                (self.custm_id, self.session['farm_cd'])
            )
            if cust_res:
                self.custm_nm.setText(cust_res[0]['custm_nm'])
            else:
                self.custm_nm.setText(self.custm_id or "")

            # 
            # [거래유형] DB에 저장된 acct_cd로 콤보박스 인덱스 찾기
            # sqlite3.Row 객체는 dict(m)으로 변환하면 .get()을 사용할 수 있습니다.
            # 컬럼명도 설계에 따라 'sales_tp'로 변경합니다.
            target_code = dict(m).get('sales_tp') 
            idx = self.sales_tp.findData(target_code)

            if idx >= 0:
                self.sales_tp.setCurrentIndex(idx)

            #비고
            self.rmk.setText(m['rmk'] or "")
            
            # 계산서 관련
            self.receipt_yn.setCurrentText(m['bill_yn'] or "N")
            if m['bill_dt']:
                self.receipt_dt.setDate(QDate.fromString(m['bill_dt'], "yyyy-MM-dd"))
            self.bill_no.setText(m['bill_no'] or "")

            # 결제방식 (PA01)
            idx = self.pay_method_cd.findData(m['pay_method_cd'])
            if idx >= 0: self.pay_method_cd.setCurrentIndex(idx)

            # 금액 정보 (None 방어 및 콤마 표시)
            self.tot_sales_amt.setText(f"{m['tot_sales_amt'] or 0:,.0f}")
            self.tot_ship_fee.setText(f"{m['tot_ship_fee'] or 0:,.0f}")
            self.tot_pay_amt.setText(f"{m['tot_paid_amt'] or 0:,.0f}")
            self.tot_unpaid_amt.setText(f"{m['tot_unpaid_amt'] or 0:,.0f}")
            self.auction_fee.setText(f"{m['auction_fee'] or 0:,.0f}")
            self.extra_cost.setText(f"{m['extra_cost'] or 0:,.0f}")

            # ---------------------------------------------------------
            # 2. 품목 상세/ 배송지상세 로드 (인덱스 보정 완료)
            # ---------------------------------------------------------
            self.item_table.setRowCount(0)
            items = self.db.execute_query(
                "SELECT * FROM t_sales_detail WHERE sales_no = ? AND farm_cd = ?",
                (sales_no, self.session['farm_cd'])
            )
            
            for row_data in items:
                # [1] 행 추가 및 위젯 리스트 가져오기
                r, widgets = self.add_item_row()
                
                # [2] 상품 정보 채우기 (데이터 로딩 중 시그널 차단)
                item_cb = widgets[1]
                item_cb.blockSignals(True) # 품목 변경 시 이벤트 발생 방지
                
                # 품목(1), 품종(2), 규격(3), 등급(4) 세팅
                db_item_code = str(row_data['item_cd'] or "").strip()
                i_idx = item_cb.findData(db_item_code)
                if i_idx >= 0: item_cb.setCurrentIndex(i_idx)

                # 품종 목록 갱신 및 선택
                self.update_variety_list(r, db_item_code, variety_cb_widget=widgets[2])
                v_idx = widgets[2].findData(str(row_data['variety_cd'] or "").strip())
                if v_idx >= 0: widgets[2].setCurrentIndex(v_idx)

                # 규격 및 등급
                s_idx = widgets[3].findData(str(row_data['size_cd'] or "").strip())
                if s_idx >= 0: widgets[3].setCurrentIndex(s_idx)
                g_idx = widgets[4].findData(str(row_data['grade_cd'] or "").strip())
                if g_idx >= 0: widgets[4].setCurrentIndex(g_idx)

                # [3] 수량, 단가, 배송비 세팅 (콤마 처리)
                widgets[5].setText(str(int(row_data['qty'] or 0))) # 수량
                widgets[6].setText(f"{row_data['unit_price'] or 0:,.0f}") # 단가
                widgets[8].setText(f"{row_data['ship_fee'] or 0:,.0f}") # 배송비
                
                # 배송유형(10) 세팅
                idx_d = widgets[10].findData(str(row_data['dlvry_tp'] or "").strip())
                if idx_d >= 0: widgets[10].setCurrentIndex(idx_d)

                item_cb.blockSignals(False) # 시그널 다시 켜기

                # [4] 배송지 목록 로드 (메모리 복원)
                sd_no = row_data['sale_detail_no'] # 상세 번호(YYYYMMDD-01-S01) 추출
                deliveries = self.db.execute_query(
                    "SELECT * FROM t_sales_delivery WHERE sale_detail_no = ? AND farm_cd = ?",
                    (sd_no, self.session['farm_cd'])
                )
                
                if deliveries:
                    # DB 행(sqlite3.Row)을 딕셔너리 리스트로 변환하여 맵에 저장
                    # 이렇게 해야 하단 테이블에서 정상적으로 읽어옵니다.
                    self.delivery_map[r] = [dict(d) for d in deliveries]

                # 데이터 로드 직후 버튼 상태 업데이트
                self.handle_delivery_tp_change(r)

            # ---------------------------------------------------------
            # 3. 수납 상세 로드 (pay_table) - 위젯 보존형 매핑
            # ---------------------------------------------------------
            self.pay_table.setRowCount(0)            
            pays = self.db.execute_query(
                "SELECT * FROM t_cash_ledger WHERE sales_no = ? AND farm_cd = ?",
                (sales_no, self.session['farm_cd'])
            )
            
            for row in pays:
                # 🔴 핵심: row 데이터를 통째로 넘겨줍니다. 
                # 이렇게 해야 상태가 'ORG'로 바뀌고 slip_no가 이름표로 박힙니다.
                self.add_pay_row(row) 
                
                # 📍 [주의] 이 아래에 있던 dt_w, cb_w, amt_w 세팅 코드들은 
                # add_pay_row(row)

            # 최종 합계 재계산 및 완료 알림
            if self.item_table.rowCount() > 0:
                self.set_active_row(0)
                # 안내 라벨 갱신
                item_nm = self.item_table.cellWidget(0, 1).currentText()
                self.lbl_selected_status.setText(f"1번 행 [{item_nm}] 선택됨 (배송지 {len(self.delivery_map.get(0, []))}건)")

            self.calculate_amounts()
            # 혹시 남아있을지 모를 깃발도 초기화
            self.is_financial_changed = False
            self.is_info_changed = False 
            QMessageBox.information(self, "조회", f"판매번호 [{sales_no}] 로드 완료")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"데이터 로드 중 치명적 오류 발생: {e}")
        finally:
            self.is_loading = False
            # (깃발 관련 코드 전부 삭제)

    # TASK 3: 삭제 로직 (트랜잭션 활용)
    def delete_sales_data(self):
        """판매번호 기준 통합 삭제 로직 (표준 트랜잭션 적용)"""
        # 1. 대상 확인
        if not self.current_sales_no:
            QMessageBox.warning(self, "알림", "삭제할 판매 건을 먼저 조회해주세요.")
            return

        # 2. 사용자 확인 (중요 비즈니스 로직)
        reply = QMessageBox.question(self, "삭제 확인", 
                                   f"판매번호 [{self.current_sales_no}]와 관련된 모든 상세 내역이 삭제됩니다.\n"
                                   "정말 삭제하시겠습니까?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # 3. 연쇄 삭제를 위한 쿼리 리스트 구성 (자식 -> 부모 순서)
            # DBManager.execute_transaction은 이 리스트를 받아 한 번에 처리합니다.
            delete_queries = [
                ("DELETE FROM t_sales_delivery WHERE sales_no = ? AND farm_cd = ?", (self.current_sales_no, self.session['farm_cd'])),
                ("DELETE FROM t_cash_ledger WHERE sales_no = ? AND farm_cd = ?", (self.current_sales_no, self.session['farm_cd'])),
                ("DELETE FROM t_sales_detail WHERE sales_no = ?", (self.current_sales_no,)),
                ("DELETE FROM t_sales_master WHERE sales_no = ?", (self.current_sales_no,))
            ]
            
            # 4. DBManager 표준 트랜잭션 실행
            success = self.db.execute_transaction(delete_queries)
            
            if success:
                QMessageBox.information(self, "성공", "해당 판매 내역이 안전하게 삭제되었습니다.")
                self.clear_sales_form() # 화면 초기화 (TASK 1 활용)
            else:
                QMessageBox.critical(self, "오류", "삭제 작업 중 DB 오류가 발생했습니다.")

    # 판매상세데이터 처리부분
    def add_item_row(self, checked=False):
        row = self.item_table.rowCount()
        self.item_table.insertRow(row)
        widgets = {}

        # 0번 컬럼: 명시적인 [선택] 버튼 (표준 디자인 적용)
        btn_select = QPushButton("선택")
        btn_select.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_select.setFixedWidth(50) # 너비를 살짝 줄여 가로 스페이스 확보
        btn_select.clicked.connect(lambda _, r=row: self.set_active_row(r))
        self.item_table.setCellWidget(row, 0, btn_select)
        widgets['select_btn'] = btn_select 
        
        # [1, 2, 3, 4, 10] 콤보박스 그룹 (품목, 품종, 규격, 등급, 배송방식)
        for col in [1, 2, 3, 4, 10]:
            combo = QComboBox()
            combo.setStyleSheet(MainStyles.COMBO)
            combo.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            combo.wheelEvent = lambda event: None # 휠 오동작 방지
            self.item_table.setCellWidget(row, col, combo)
            widgets[col] = combo
        
        # --- 데이터 로드 로직 (1: 품목, 3: 규격, 4: 등급) ---
        item_combo = widgets[1]
        items = self.code_mgr.get_common_codes('FR01')
        item_combo.addItem("선택", "")
        for i in items: item_combo.addItem(i['code_nm'], i['code_cd'])
        item_combo.activated.connect(lambda _, r=row: self.update_variety_list(r))

        size_combo = widgets[3]
        sizes = self.code_mgr.get_common_codes('SZ01')
        size_combo.addItem("선택", "")
        for s in sizes: size_combo.addItem(s['code_nm'], s['code_cd'])

        grade_combo = widgets[4]
        grades = self.code_mgr.get_common_codes('GR01')
        grade_combo.addItem("선택", "")
        for g in grades: grade_combo.addItem(g['code_nm'], g['code_cd'])

        # [5, 6, 8] 입력 위젯 (수량, 단가, 배송비) - INPUT_RIGHT 적용
        for col in [5, 6, 8]:
            edit = QLineEdit("0")
            edit.setStyleSheet(MainStyles.INPUT_RIGHT)
            edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            edit.textChanged.connect(lambda _, r=row, e=edit: self.handle_price_input(r, e))
            self.item_table.setCellWidget(row, col, edit)
            widgets[col] = edit

        # [7, 9] 읽기 전용 필드 (가액, 합계) - READONLY/TOTAL 적용
        for col, style in [(7, MainStyles.INPUT_READONLY), (9, MainStyles.INPUT_TOTAL)]:
            edit = QLineEdit("0")
            edit.setReadOnly(True)
            edit.setAlignment(Qt.AlignmentFlag.AlignRight)
            edit.setStyleSheet(style)
            edit.setFocusPolicy(Qt.FocusPolicy.NoFocus) 
            self.item_table.setCellWidget(row, col, edit)
            widgets[col] = edit

        # [10] 배송방식 데이터 로드 및 시그널
        ship_combo = widgets[10]
        methods = self.code_mgr.get_common_codes('LO01')
        ship_combo.addItem("선택", "")
        for m in methods: ship_combo.addItem(m['code_nm'], m['code_cd'])
        ship_combo.currentIndexChanged.connect(lambda _, r=row: self.handle_delivery_tp_change(r))

        # [11] 삭제 버튼 (BTN_ACTION 적용)
        btn_delete = QPushButton("삭제")
        btn_delete.setStyleSheet(MainStyles.BTN_ACTION)
        btn_delete.setFixedWidth(40)
        btn_delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_delete.clicked.connect(self.handle_remove_row)
        self.item_table.setCellWidget(row, 11, btn_delete)
        widgets[11] = btn_delete

        self.item_table.setRowHeight(row, 35) # 표준 행 높이
        return row, widgets

    # 테이블 더블클릭 이벤트 실행 함수
    def on_dlvry_table_double_clicked(self, row, column):
        """[지기님 로직] 더블클릭한 row 번호를 그대로 사용하여 배송지 수정"""
        # 1. 상단 품목 테이블에서 선택된 행 번호 확인 (데이터 맵의 주소)
        active_sales_row = getattr(self, 'active_row', 0)
        
        # 2. 해당 상품의 전체 배송지 리스트 가져오기
        deliveries = self.delivery_map.get(active_sales_row, [])
        if not deliveries or row >= len(deliveries):
            return # 안전 장치
        
        # 3. 팝업창 띄우기 (해당 번호의 데이터 전달)
        target_data = deliveries[row]
        dlg = SingleDeliveryEditDialog(target_data, self)
        
        if dlg.exec():
            # 4. [적용] 클릭 시 메모리 데이터 교체
            updated_data = dlg.get_data()
            self.delivery_map[active_sales_row][row] = updated_data
            
            # 5. 하단 리스트 UI 즉시 갱신 (다시 그리기)
            self.update_delivery_ui(active_sales_row)

    def handle_remove_row(self):
        """삭제 버튼 클릭 시 해당 줄을 정확하게 찾아 삭제"""
        # 1. 클릭된 버튼 객체 찾기
        button = self.sender()
        if not button:
            return

        # 2. 버튼이 위치한 테이블의 인덱스(좌표) 찾기
        # 이 방식은 행이 삭제되어 번호가 바뀌어도 항상 정확한 위치를 찾아냅니다.
        pos = button.pos()
        index = self.item_table.indexAt(pos)
        
        if index.isValid():
            row = index.row()
            
            # 3. 사용자에게 한 번 더 물어보기 (선택 사항)
            # res = QMessageBox.question(self, "삭제 확인", f"{row+1}번 행을 삭제하시겠습니까?")
            # if res == QMessageBox.StandardButton.Yes:
            
            self.item_table.removeRow(row)
            
            # 4. 삭제 후 합계 금액 등을 다시 계산
            self.calculate_amounts()

    def handle_delivery_tp_change(self, row):
        """배송방식이 '택배/화물'이 아니면 3단의 등록 관련 버튼들을 비활성화"""
        combo = self.item_table.cellWidget(row, 10)
        if not combo: return
        
        # 버튼들이 아직 생성되지 않았으면(초기화 단계) 무시 (에러 방지)
        if not hasattr(self, 'btn_manual_reg'): return 

        is_delivery = "택배" in combo.currentText() or "화물" in combo.currentText()
        
        # 3단 컨트롤 버튼 제어 (현재 선택된 행일 때만 의미 있음)
        if getattr(self, 'active_row', -1) == row:
            self.btn_manual_reg.setEnabled(is_delivery)
            self.btn_history.setEnabled(is_delivery)
            self.btn_excel_upload.setEnabled(is_delivery)
            
        self.calculate_amounts()

    # 품목 선택시 품종을 선택하게 함.
    def update_variety_list(self, row, manual_item_code=None, variety_cb_widget=None):
        
        """품목에 따른 품종 목록 갱신 (직속 로드 지원)"""
        if row < 0: return
        
        # 1. 위젯 참조: 직접 전달받은 위젯이 있으면 그것을 최우선으로 사용 ★
        variety_combo = variety_cb_widget if variety_cb_widget else self.item_table.cellWidget(row, 2)
        
        if variety_combo is None: 
            print(f"⚠️ 오류: {row}행의 품종 위젯을 찾을 수 없습니다.")
            return
            
        # 2. 사용할 품목 코드 결정
        item_combo = self.item_table.cellWidget(row, 1)
        item_code = manual_item_code if manual_item_code else (item_combo.currentData() if item_combo else None)
        
        variety_combo.clear()
        variety_combo.addItem("선택", "")
        
        if item_code:
            varieties = self.code_mgr.get_common_codes(item_code) #
            if varieties:
                for v in varieties:
                    variety_combo.addItem(v['code_nm'], v['code_cd'])
                print(f"DEBUG: {row}행 품종 {len(varieties)}개 로드 완료 (코드: {item_code})")

    def update_row_amount(self, row):
        """수량(4), 단가(5), 배송비(7)를 읽어서 가액(6)과 합계(8)를 실시간으로 바꿉니다."""
        try:
            # 1. 등급 추가로 인해 하나씩 밀린 위젯들을 정확한 인덱스로 가져옵니다.
            qty_w = self.item_table.cellWidget(row, 5)      # 수량 (3번 -> 4번)
            price_w = self.item_table.cellWidget(row, 6)    # 단가 (4번 -> 5번)
            amt_w = self.item_table.cellWidget(row, 7)      # 상품가액(a) (5번 -> 6번)
            ship_w = self.item_table.cellWidget(row, 8)     # 배송비(b) (6번 -> 7번)
            total_w = self.item_table.cellWidget(row, 9)    # 합계(a+b) (7번 -> 8번)

            # 모든 위젯이 정상적으로 존재할 때만 계산 시작
            if all([qty_w, price_w, amt_w, ship_w, total_w]):
                # 2. 콤마(#,###) 제거 후 숫자로 변환
                qty = float(qty_w.text().replace(',', '') or 0)
                price = float(price_w.text().replace(',', '') or 0)
                ship = float(ship_w.text().replace(',', '') or 0)
                
                # 3. 상품가액 계산: 수량 * 단가
                prod_amt = qty * price
                amt_w.setText(f"{prod_amt:,.0f}")  # 천 단위 콤마 적용해서 표시
                
                # 4. 행 합계 계산: 상품가액 + 배송비
                row_total = prod_amt + ship
                total_w.setText(f"{row_total:,.0f}")  # 천 단위 콤마 적용해서 표시
                
                # 5. [중요] 개별 행 계산이 끝났으니, 우측 상단의 '전체 합계'도 갱신합니다.
                self.calculate_amounts()
                
        except Exception as e:
            print(f"행 단위 계산 오류(컬럼 인덱스 확인 필요): {e}")

    def handle_price_input(self, row, edit):
        """입력 시 실시간으로 #,### 콤마를 찍고 계산을 호출"""
        edit.blockSignals(True)
        pos = edit.cursorPosition()
        old_text = edit.text()
        raw_text = old_text.replace(',', '')
        
        if raw_text.isdigit():
            formatted_text = f"{int(raw_text):,}"
            edit.setText(formatted_text)
            # 콤마 추가로 인한 커서 위치 보정
            new_pos = pos + (len(formatted_text) - len(old_text))
            edit.setCursorPosition(max(0, new_pos))
        elif raw_text == "":
            edit.setText("0")
            edit.setCursorPosition(1)
            
        edit.blockSignals(False)
        self.update_row_amount(row) # 행 금액 계산 실행

    # 배송지상세내역 기능구현

    # ---------------------------------------------------------
    # [기능] 수납 내역 (입력 기능 구현)
    # ---------------------------------------------------------
    def add_pay_row(self, pay_data=None):
        """수금 행 추가 및 상태(꼬니) 부여와 센서 연결"""
        row_index = self.pay_table.rowCount()
        self.pay_table.insertRow(row_index)
        if pay_data and not isinstance(pay_data, dict):
            pay_data = dict(pay_data)

        # [상태 설정] 0번 컬럼에 상태(꼬니) 아이템 생성 및 전표번호 보관
        status_text = "ORG" if pay_data else "INS"
        status_item = QTableWidgetItem(status_text)
        
        if pay_data:
            # DB에서 가져온 전표번호와 원본 데이터를 숨겨둠 (비교용)
            status_item.setData(Qt.ItemDataRole.UserRole, pay_data.get('slip_no'))
            status_item.setData(Qt.ItemDataRole.UserRole + 1, pay_data) 
        
        self.pay_table.setItem(row_index, 0, status_item)
        
        # 1. [선택] 버튼
        btn_select = QPushButton("선택")
        btn_select.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_select.clicked.connect(lambda _, b=btn_select: self.on_pay_row_selected(b))
        self.pay_table.setCellWidget(row_index, 0, btn_select)

        # 2. 날짜 (DateEdit)
        dt_edit = QDateEdit(calendarPopup=True)
        dt_edit.setDate(QDate.currentDate())
        dt_edit.setStyleSheet(MainStyles.DATE_EDIT)
        # [센서 연결] 날짜 변경 시 수정 여부 체크
        dt_edit.dateChanged.connect(lambda: self.check_row_modified(row_index))
        self.pay_table.setCellWidget(row_index, 1, dt_edit)

        # 3. 입금수단 (ComboBox)
        method_cb = QComboBox()
        method_cb.setStyleSheet(MainStyles.COMBO)
        cash_list = self.acct_mgr.get_account_codes('AS', target_level=4)
        for item in cash_list:
             method_cb.addItem(item['acct_nm'], item['acct_cd'])
        # [센서 연결] 계정 변경 시 수정 여부 체크
        method_cb.currentIndexChanged.connect(lambda: self.check_row_modified(row_index))
        self.pay_table.setCellWidget(row_index, 2, method_cb)

        # 4. 금액 (LineEdit)
        amt_edit = QLineEdit("0")
        amt_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        amt_edit.setStyleSheet(MainStyles.INPUT_RIGHT)
        # [센서 연결] 콤마 포맷팅 + 실시간 합계 + 수정 감시
        amt_edit.textChanged.connect(lambda: self.format_currency(amt_edit))
        amt_edit.textChanged.connect(self.calculate_amounts)
        amt_edit.editingFinished.connect(lambda: self.check_row_modified(row_index))
        self.pay_table.setCellWidget(row_index, 3, amt_edit)

        # 5. 비고 (LineEdit)
        rmk_edit = QLineEdit()
        rmk_edit.setStyleSheet(MainStyles.INPUT_LEFT)
        self.pay_table.setCellWidget(row_index, 4, rmk_edit)

        # 데이터 로딩 시 값 세팅
        if pay_data:
            if pay_data.get('pay_dt'): dt_edit.setDate(QDate.fromString(pay_data['pay_dt'], "yyyy-MM-dd"))
            idx = method_cb.findData(pay_data.get('pay_method_cd'))
            if idx >= 0: method_cb.setCurrentIndex(idx)
            amt_edit.setText(f"{float(pay_data.get('pay_amt') or 0):,.0f}")
            if pay_data.get('rmk'): rmk_edit.setText(pay_data['rmk'])

        self.calculate_amounts()

        # ROW의 색깔을 신규행은 연초록, 기본은 흰색으로 변경
        if not pay_data:
            # 신규 행은 모든 위젯이 올라온 뒤에 연초록색을 입힙니다.
            self._set_pay_row_color(row_index, QColor("#E8F5E9"))
        else:
            # 기존 데이터(ORG)는 기본적으로 흰색으로 초기화
            self._set_pay_row_color(row_index, QColor("white"))

    def _set_pay_row_color(self, row, color):
        """[보정] 위젯이 배경색을 가리지 않도록 스타일을 강제 적용"""
        color_hex = color.name()
        
        # 1. 0번 컬럼 처리 (아이템 배경색 + 버튼 위젯 배경색)
        item_zero = self.pay_table.item(row, 0)
        if item_zero: 
            item_zero.setBackground(QBrush(color))
        
        # 📍 [추가] 0번 컬럼의 '선택' 버튼도 배경색을 바꿔줘야 통일감이 생깁니다.
        btn_w = self.pay_table.cellWidget(row, 0)
        if btn_w:
            btn_w.setStyleSheet(f"{MainStyles.BTN_SECONDARY} background-color: {color_hex};")

        # 2. 1~4번 컬럼(입력 위젯들) 처리
        style_map = {
            1: MainStyles.DATE_EDIT,
            2: MainStyles.COMBO,
            3: MainStyles.INPUT_RIGHT,
            4: MainStyles.INPUT_LEFT
        }

        for c in range(1, 5):
            w = self.pay_table.cellWidget(row, c)
            if w:
                class_name = w.metaObject().className()
                base_style = style_map.get(c, "").strip()
                
                # 🔴 [개선] 클래스 타겟팅 형식을 더 확실하게 구성합니다.
                # 속성 값들을 먼저 나열하고 뒤에 클래스 선택자를 붙이는 방식이 안전합니다.
                new_style = f"{base_style}\n{class_name} {{ background-color: {color_hex}; }}"
                w.setStyleSheet(new_style)

    def delete_pay_row(self):
        """[최종] DEL 상태값을 활용한 정교한 삭제 처리"""
        try:
            # 1. 초기화 확인 (바구니가 없으면 생성)
            if not hasattr(self, 'deleted_pay_items'):
                self.deleted_pay_items = []

            # 2. 선택된 행 확인
            target_row = getattr(self, 'selected_pay_row', -1)
            if target_row < 0 or target_row >= self.pay_table.rowCount():
                QMessageBox.warning(self, "알림", "삭제할 행의 [선택] 버튼을 먼저 눌러주세요.")
                return

            # 3. [핵심] DB 데이터인지 확인 후 삭제 바구니에 박제
            status_item = self.pay_table.item(target_row, 0)
            if status_item:
                # 저장된 원본 데이터(dict)를 가져옵니다.
                orig_data = status_item.data(Qt.ItemDataRole.UserRole + 1)
                
                # DB에서 불러왔던 데이터라면 (원본 데이터가 존재한다면)
                if orig_data and isinstance(orig_data, dict):
                    # 상태를 'DEL'로 마킹하여 삭제 바구니에 추가
                    orig_data['status'] = 'DEL'
                    self.deleted_pay_items.append(orig_data)

            # 4. 행 삭제 및 선택 초기화
            self.pay_table.removeRow(target_row)
            self.selected_pay_row = -1
            
            # 5. 합계 재계산 및 스타일 갱신
            self.calculate_amounts() # 기존 calculate_pay_totals 대신 통합 함수 사용 시
            
            # 스타일 초기화 (삭제 후 번호가 당겨지므로 전체 다시 그림)
            for r in range(self.pay_table.rowCount()):
                s_item = self.pay_table.item(r, 0)
                if not s_item: continue
                
                status = s_item.text()
                color = QColor("white")
                if status == "INS": color = QColor("#E8F5E9")
                elif status == "MOD": color = QColor("#FFF9C4")
                self._set_pay_row_color(r, color)

        except Exception as e:
            QMessageBox.critical(self, "오류", f"삭제 중 에러가 발생했습니다: {e}")
    
    def focus_pay_row(self):
        """상단 [수정] 버튼 클릭 시 선택된 행의 금액 입력칸으로 포커스 이동"""
        curr_row = self.pay_table.currentRow()
        if curr_row >= 0:
            amt_w = self.pay_table.cellWidget(curr_row, 2)
            if amt_w:
                amt_w.setFocus()
                amt_w.selectAll()

    # [기능][정밀 센서] 3가지 항목(날짜, 계정, 금액) 변경 시 MOD 처리
    def check_row_modified(self, row):
        status_item = self.pay_table.item(row, 0)
        if not status_item or status_item.text() == "INS": return 
        
        orig_data = status_item.data(Qt.ItemDataRole.UserRole + 1)
        if not orig_data: return

        # 현재 값 추출 (UI)
        ui_dt = self.pay_table.cellWidget(row, 1).date().toString("yyyy-MM-dd")
        ui_acct = self.pay_table.cellWidget(row, 2).currentData()
        ui_amt = float(self.pay_table.cellWidget(row, 3).text().replace(',', '') or 0)

        # 원본 DB 값과 비교
        is_changed = (round(float(orig_data.get('pay_amt', 0)), 0) != round(ui_amt, 0)) or \
                     (orig_data.get('pay_dt', '')[:10] != ui_dt) or \
                     (orig_data.get('pay_method_cd', '') != ui_acct)

        if is_changed:
            status_item.setText("MOD")
            self._set_pay_row_color(row, QColor("#FFF9C4")) # 수정은 연노랑
        else:
            status_item.setText("ORG")
            self._set_pay_row_color(row, QColor("white"))

    def format_currency(self, edit):
        """입력 시 실시간 콤마 적용"""
        edit.blockSignals(True)
        raw = edit.text().replace(',', '')
        if raw.isdigit():
            edit.setText(f"{int(raw):,}")
        edit.blockSignals(False)

    # ---------------------------------------------------------
    # [기능] 수납 금액 입력 핸들러 (콤마 + 계산 트리거)
    # ---------------------------------------------------------
    def handle_pay_input(self, row, edit):
        """수납 금액 입력 시 콤마 적용 및 전체 계산 호출"""
        edit.blockSignals(True) # 무한루프 방지
        
        text = edit.text().replace(',', '')
        if not text: text = "0"
        
        # 숫자만 남기기 (마이너스 허용)
        if text.replace('-', '').isdigit():
            val = int(text)
            edit.setText(f"{val:,}")
            
            # 커서 위치 보정 (맨 뒤로)
            edit.setCursorPosition(len(edit.text()))
        
        edit.blockSignals(False)
        
        # ★ 전체 금액 재계산 호출
        self.calculate_amounts()

    # ---------------------------------------------------------
    # [핵심] 전체 금액 및 미수금 계산 로직 (수정됨)
    # ---------------------------------------------------------
    def calculate_amounts(self):
        """
        [금액 자동 계산] 품목(2단)과 수납(3단)을 실시간 합산하여 마스터(1단)에 반영
        - 수납 테이블 컬럼 인덱스 수정 반영 (2번 -> 3번)
        - 미수금 상태에 따른 시각적 강조 (Red/Blue)
        """
        try:
            total_prod_amt = 0  # 상품가액 합계 (A)
            total_ship_fee = 0  # 배송비 합계 (B)
            total_paid = 0      # 수금액 합계 (C)

            # 품목 합산
            for i in range(self.item_table.rowCount()):
                w_amt = self.item_table.cellWidget(i, 7)
                if w_amt: total_prod_amt += float(w_amt.text().replace(',', '') or 0)
                w_ship = self.item_table.cellWidget(i, 8)
                if w_ship: total_ship_fee += float(w_ship.text().replace(',', '') or 0)

            # 수금 합산
            for i in range(self.pay_table.rowCount()):
                w_pay = self.pay_table.cellWidget(i, 3)
                if w_pay: total_paid += float(w_pay.text().replace(',', '') or 0)

            total_sales = total_prod_amt + total_ship_fee
            unpaid = total_sales - total_paid

            # 마스터 반영
            self.tot_sales_amt.setText(f"{total_prod_amt:,.0f}")
            self.tot_ship_fee.setText(f"{total_ship_fee:,.0f}")
            self.tot_pay_amt.setText(f"{total_paid:,.0f}")
            self.tot_unpaid_amt.setText(f"{unpaid:,.0f}")

            # [추가] 수금 탭 내 레이블 실시간 갱신
            if hasattr(self, 'lbl_pay_summary'):
                self.lbl_pay_summary.setText(
                    f"총 매출액: {total_sales:,.0f} | 수금 합계: {total_paid:,.0f} | "
                    f"{'잔액' if unpaid >= 0 else '초과'}: {abs(unpaid):,.0f}"
                )

            # 5. 스타일 적용 (MainStyles와 어울리는 표준 색상 적용)
            # - 베이스 스타일: 폰트 키우고, 배경 투명, 테두리 없음
            base_style = "font-size: 12px; font-weight: bold; border: none; background: transparent;"
            
            if unpaid > 0:
                # 미수금 존재 (돈을 덜 받음) -> 경고색 (Red 계열)
                self.tot_unpaid_amt.setStyleSheet(f"{base_style} color: #D32F2F;") 
            elif unpaid < 0:
                # 과수금 (돈을 더 받음) -> 강조색 (Purple 계열)
                self.tot_unpaid_amt.setStyleSheet(f"{base_style} color: #7B1FA2;")
            else:
                # 완납 (0원) -> 안정색 (Blue 계열)
                self.tot_unpaid_amt.setStyleSheet(f"{base_style} color: #1976D2;")

        except Exception as e:
            print(f"금액 계산 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

    def open_manual_registration(self):
        """[➕ 등록] 버튼: 신규 배송지 등록 팝업 호출"""
        cur_row = getattr(self, 'active_row', -1)
        if cur_row < 0:
            QMessageBox.warning(self, "알림", "배송지를 등록할 품목을 먼저 [선택]해주세요."); return

        # ---------------------------------------------------------
        # 🚨 수량 제한 체크 로직
        # ---------------------------------------------------------
        # 1. 현재 이 품목에 등록된 배송지 건수 확인
        current_data = self.delivery_map.get(cur_row, [])
        current_cnt = len(current_data)
        
        # 2. 품목 상세 테이블에서 목표 수량(5번 컬럼) 가져오기
        try:
            qty_widget = self.item_table.cellWidget(cur_row, 5)
            # 콤마 제거 후 숫자로 변환
            total_target_qty = int(float(qty_widget.text().replace(',', ''))) if qty_widget else 0
        except Exception:
            total_target_qty = 0

        # 3. 이미 수량이 꽉 찼다면 차단
        if current_cnt >= total_target_qty:
            QMessageBox.warning(self, "수량 초과", 
                f"현재 품목의 목표 수량은 [{total_target_qty}건]입니다.\n"
                f"이미 [{current_cnt}건]의 배송지가 모두 등록되어 더 이상 추가할 수 없습니다.")
            return

        # 1. 보내는 분 기본 정보 조회
        snd_info = {'nm': '', 'tel': '', 'addr': ''}
        try:
            res = self.db.execute_query("SELECT custm_nm, mobile FROM m_customer WHERE custm_id = ?", (self.custm_id,))
            if res: snd_info = {'nm': res[0]['custm_nm'], 'tel': res[0]['mobile'], 'addr': ''}
        except: pass

        # 2. 신규 등록 팝업(이미 작성해둔 NewDeliveryDialog) 호출
        dlg = NewDeliveryDialog(snd_info, self)
        if dlg.exec() and dlg.data:
            current_data = self.delivery_map.get(cur_row, [])
            # 수량 1건 기본 추가
            new_item = {**dlg.data, 'delivery_qty': 1, 'invoice_no': ''}
            current_data.insert(0, new_item)
            
            self.delivery_map[cur_row] = current_data
            self.update_delivery_ui(cur_row) # 상태 라벨 및 UI 갱신

    def open_history_popup_from_bottom(self):
        """[🔍 최근이력] 버튼: 기존 배송이력 팝업 호출"""
        cur_row = getattr(self, 'active_row', -1)
        if cur_row < 0:
            QMessageBox.warning(self, "알림", "상세내역을 먼저 [선택]해주세요."); return
        
        # 기존에 만들어둔 팝업 로직 재사용 (open_tracking_popup)
        self.open_tracking_popup(cur_row)
    '''
    def open_delivery_popup(self, row):
        # 1. 현재 행의 품목명과 총 수량 가져오기
        item_nm = self.item_table.cellWidget(row, 0).currentText() # 품목 (배/배즙)
        try:
            total_qty = float(self.item_table.item(row, 3).text() or 0) # 수량 컬럼
        except:
            total_qty = 0

        if total_qty <= 0:
            QMessageBox.warning(self, "수량 확인", "배송지를 등록하기 전 품목 수량을 먼저 입력하세요.")
            return

        # 2. 팝업 띄우기
        dialog = DeliveryDetailDialog(item_nm, total_qty, self)
        if dialog.exec():
            # 3. 결과 받아오기
            data = dialog.delivery_list
            # 버튼 텍스트에 배송지 개수 표시 (예: 배송지 관리(2))
            btn = self.item_table.cellWidget(row, 8) # 배송지관리 버튼 위치
            btn.setText(f"배송지({len(data)})")
            # TODO: 이 data를 나중에 DB 저장 시 활용하기 위해 메모리에 저장해둬야 함
    '''
    def open_tracking_popup(self, row):
        """[최근이력] 버튼: 기존 데이터를 보존하며 선택된 주소를 추가(Append)함"""
        if not self.custm_id:
            QMessageBox.warning(self, "알림", "고객이 선택되지 않았습니다."); return

        # 1. 현재 등록된 건수 확인 및 남은 수량 계산
        current_data = self.delivery_map.get(row, [])
        current_cnt = len(current_data)
        
        try:
            qty_widget = self.item_table.cellWidget(row, 5)
            total_target_qty = int(float(qty_widget.text().replace(',', ''))) if qty_widget else 0
        except:
            total_target_qty = 0
        
        remaining_qty = total_target_qty - current_cnt

        if remaining_qty <= 0:
            QMessageBox.information(self, "알림", "이미 목표 수량만큼 배송지가 등록되어 있습니다."); return

        # 2. 팝업 호출 (남은 수량만큼만 선택 가능하도록 제한)
        past_dlg = PastAddressDialog(self.db, self.custm_id, remaining_qty, parent=self)
        
        if past_dlg.exec() and past_dlg.selected_addrs:
            addr_list = past_dlg.selected_addrs
            new_append_list = []
            
            for addr in addr_list:
                new_append_list.append({
                    'rcv_name': addr.get('rcv_name', ''),
                    'rcv_tel': addr.get('rcv_tel', ''),
                    'rcv_addr': addr.get('rcv_addr', ''),
                    'snd_name': addr.get('snd_name', ''), 
                    'snd_tel': addr.get('snd_tel', ''),
                    'snd_addr': addr.get('snd_addr', ''),
                    'delivery_qty': 1, 
                    'invoice_no': '' # 송장번호는 항상 초기화
                })
            
            # 3. [핵심] 덮어쓰기가 아닌 '기존 데이터 + 신규 데이터' 병합
            #current_data.extend(new_append_list)
            #self.delivery_map[row] = new_append_list + current_data
            self.delivery_map[row] = new_append_list + current_data

            # 4. UI 갱신 (309건으로 라벨 업데이트됨)
            self.update_delivery_ui(row)

    def update_delivery_ui(self, row):
        """배송지 건수 라벨 업데이트 및 리스트 렌더링 통합 관리"""
        cnt = len(self.delivery_map.get(row, []))
        item_nm = ""
        item_widget = self.item_table.cellWidget(row, 1)
        if item_widget: item_nm = item_widget.currentText()

        # 라벨 텍스트를 "n건 등록"으로 통일하여 정보 제공 강화
        if hasattr(self, 'lbl_selected_status'):
            self.lbl_selected_status.setText(f"[{item_nm}] 상세주문 선택됨 - 총 {cnt}건 등록")
        
        # 실제 테이블 렌더링 실행
        self.on_dlvry_item_selected()

    def on_dlvry_item_selected(self):
        """상단 품목 선택 시 하단 배송지 목록 갱신 (최적화 버전)"""
        
        # [🚨 핵심] 이미 렌더링 중이면 새로운 요청은 무시합니다.
        if getattr(self, '_is_rendering', False):
            return

        # active_row를 사용하여 데이터 정합성 유지
        cur_row = getattr(self, 'active_row', -1)
        if cur_row < 0: 
            self.dlvry_table.setRowCount(0)
            return

        try:
            # 1. 데이터 가져오기
            d_list = self.delivery_map.get(cur_row, [])
            total_cnt = len(d_list)

            # 2. 테이블 초기화
            self.dlvry_table.setRowCount(0)
            
            # 데이터가 없으면 즉시 종료
            if total_cnt == 0: return

            # 3. 화면 그리기 (성능을 위해 정렬 잠시 해제)
            self.dlvry_table.setSortingEnabled(False)

            self.dlvry_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            
            # 건수에 따른 처리 (기존 309건 처리 로직 유지)
            if total_cnt < 100:
                for r_data in d_list:
                    self._add_single_delivery_row(r_data)
            else:
                progress = QProgressDialog("배송지 목록 렌더링 중...", "중단", 0, total_cnt, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)
                
                for i, r_data in enumerate(d_list):
                    if progress.wasCanceled(): break
                    self._add_single_delivery_row(r_data)
                    if i % 10 == 0:
                        progress.setValue(i + 1)
                progress.setValue(total_cnt)
                    
            self.dlvry_table.setSortingEnabled(True)

            # 버튼 텍스트 초기화
            if hasattr(self, 'btn_select_all'):
                self.btn_select_all.setText("✔ 전체 선택")
                self.btn_select_all.setStyleSheet(MainStyles.BTN_SECONDARY)

        except Exception as e:
            print(f"목록 갱신 오류: {e}")

    def _add_single_delivery_row(self, r_data):
        """행 추가 내부 로직 (Key 값 불일치 해결 및 데이터 검증 강화)"""
        row = self.dlvry_table.rowCount()
        self.dlvry_table.insertRow(row)
        
        # 안전하게 데이터를 가져오기 위한 헬퍼 (None 방지)
        def get_v(key_list):
            for k in key_list:
                if r_data.get(k): return str(r_data.get(k))
            return ""

        # 0~2번: 보내는 사람 정보 (snd_name 또는 snd_nm 등 유연하게 대응)
        self.dlvry_table.setItem(row, 0, QTableWidgetItem(get_v(['snd_name', 'snd_nm', '보내는분'])))
        self.dlvry_table.setItem(row, 1, QTableWidgetItem(get_v(['snd_tel', '보내는연락처'])))
        self.dlvry_table.setItem(row, 2, QTableWidgetItem(get_v(['snd_addr', '보내는주소'])))
        
        # 3~5번: 받는 사람 정보
        self.dlvry_table.setItem(row, 3, QTableWidgetItem(get_v(['rcv_name', 'rcv_nm', '받는분'])))
        self.dlvry_table.setItem(row, 4, QTableWidgetItem(get_v(['rcv_tel', '받는연락처'])))
        self.dlvry_table.setItem(row, 5, QTableWidgetItem(get_v(['rcv_addr', '받는주소'])))
        
        # 6번: 수량 (숫자 포맷)
        try:
            qty_val = float(r_data.get('delivery_qty') or r_data.get('qty') or 1)
        except:
            qty_val = 1.0
        qty_item = QTableWidgetItem(f"{qty_val:,.0f}") 
        qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.dlvry_table.setItem(row, 6, qty_item)
        
        # 7~8번: 메시지 및 송장번호
        self.dlvry_table.setItem(row, 7, QTableWidgetItem(get_v(['dlvry_msg', '배송메시지', 'msg'])))
        self.dlvry_table.setItem(row, 8, QTableWidgetItem(get_v(['invoice_no', '송장번호'])))
    
    def on_delivery_reg_clicked(self):
        """[배송등록] 버튼 클릭 시 호출 - 수정 모드 포함"""
        button = self.sender()
        row = self.item_table.indexAt(button.pos()).row()
        
        # 1. 기존에 등록된 배송지 목록이 있는지 확인 (수정의 핵심!)
        existing_data = self.delivery_map.get(row, [])
        item_nm = self.item_table.cellWidget(row, 1).currentText()
        total_qty = float(self.item_table.cellWidget(row, 5).text() or 0)

        # 2. 팝업창 생성 시 기존 데이터를 넘겨줌
        dlg = DeliveryDetailDialog(item_nm, total_qty, self.sender_info, self)
        
        # [중요] 팝업창에 기존 데이터가 있다면 화면에 뿌려주는 함수 호출
        if existing_data:
            dlg.load_existing_data(existing_data) 

        if dlg.exec():
            # 3. 팝업에서 수정된 내용을 다시 메모리(map)에 저장
            self.delivery_map[row] = dlg.delivery_list
            self.update_delivery_ui(row)

    def load_existing_data(self, data_list):
        """수정 모드: 넘겨받은 기존 배송지 데이터를 테이블에 표시"""
        self.table.setRowCount(0)
        for d in data_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # DB 컬럼명(dlvry_msg)과 팝업 키값(delivery_msg) 모두 대응
            cols = [
                d.get('snd_name') or d.get('snd_nm', ""),
                d.get('snd_tel', ""),
                d.get('snd_addr', ""),
                d.get('rcv_name') or d.get('rcv_nm', ""),
                d.get('rcv_tel', ""),
                d.get('rcv_addr', ""),
                str(d.get('delivery_qty') or d.get('qty') or 1),
                d.get('dlvry_msg')
            ]
            
            for i, text in enumerate(cols):
                self.table.setItem(row, i, QTableWidgetItem(str(text)))

    # =========================================================================
    # [혁신 모델] 통합 판매 저장 (마스터 + 상세 + 수납 + 회계엔진 연동)
    # =========================================================================
    def execute_full_save(self):
        """
        [최종 완성본] 매출 마스터 및 상세 정보 통합 저장
        - 부모/자식 테이블 간의 데이터 정합성 보장
        - 회계 전표(t_ledger)와 수납상세(t_cash_ledger) 완벽 연결
        """
        try:
            # 1. 기초 정보 및 변수 설정
            s_no = self.sales_no.text()
            sales_date_str = self.sales_dt.date().toString("yyyy-MM-dd")
            if not s_no:
                s_no = self.generate_sales_no(sales_date_str)
                self.sales_no.setText(s_no)

            def get_amt(w): return float(w.text().replace(',', '') or 0)
            
            # UI 마스터 데이터 추출
            t_sales = get_amt(self.tot_sales_amt)
            t_ship = get_amt(self.tot_ship_fee)
            t_total = t_sales + t_ship
            t_paid = get_amt(self.tot_pay_amt)
            t_unpaid = get_amt(self.tot_unpaid_amt)
            
            # 위젯이 없을 경우를 대비한 기본값 설정
            ui_bill_yn = self.receipt_yn.currentText() if hasattr(self, 'receipt_yn') else 'N'
            ui_bill_dt = self.receipt_dt.date().toString("yyyy-MM-dd") if hasattr(self, 'receipt_dt') else sales_date_str
            ui_bill_no = self.bill_no.text() if hasattr(self, 'bill_no') else ""
            ui_status_cd = self.sales_tp.currentData() if hasattr(self, 'status_cd') else '10' # 👈 에러 해결 지점
            ui_master_rmk = self.rmk.text() if hasattr(self, 'rmk') else ""
            ui_pay_method = self.pay_method_cd.currentData() if hasattr(self, 'pay_method_cd') else None

            # -----------------------------------------------------------------
            # [Step 1] 회계 전표 바구니 구성 및 쿼리 생성
            # -----------------------------------------------------------------
            pay_basket = []
            for r in range(self.pay_table.rowCount()):
                status_item = self.pay_table.item(r, 0)
                method_w = self.pay_table.cellWidget(r, 2)
                amt_w = self.pay_table.cellWidget(r, 3)
                if not method_w or not amt_w: continue
                
                orig = (status_item.data(Qt.ItemDataRole.UserRole + 1) if status_item else {}) or {}
                pay_basket.append({
                    'status': status_item.text() if status_item else "INS",
                    'orig_data': orig,
                    'acct_cd': method_w.currentData(),
                    'method': method_w.currentData(),
                    'amt': get_amt(amt_w),
                    'pay_status': 'Y',
                    'rmk': self.pay_table.cellWidget(r, 4).text() if self.pay_table.cellWidget(r, 4) else f"판매입금({s_no})"
                })
            for del_item in getattr(self, 'deleted_pay_items', []):
                pay_basket.append({
                    'status': 'DEL',
                    'orig_data': del_item,
                    'acct_cd': del_item.get('acct_cd'),
                    'method': del_item.get('pay_method_cd'),
                    'amt': 0, # 삭제이므로 현재 금액은 0
                    'pay_status': 'N', # 삭제는 미지급과 같음
                    'rmk': '' # 👈 적요 키를 명시적으로 추가
                })

            ledger_queries, slip_map = self.acct_mgr.sync_ledger_by_basket('SALE', s_no, sales_date_str, pay_basket, self.user_id)
            
            self.deleted_pay_items = []
            queries = []
            queries.extend(ledger_queries) # 전표 90/80/10 쿼리 선삽입

            # -----------------------------------------------------------------
            # [Step 2] 기존 내역 삭제 (FK 제약 조건 준수: 자식부터 삭제)
            # -----------------------------------------------------------------
            queries.append(("DELETE FROM t_sales_delivery WHERE sales_no = ?", (s_no,)))
            queries.append(("DELETE FROM t_cash_ledger WHERE sales_no = ?", (s_no,)))
            queries.append(("DELETE FROM t_sales_detail WHERE sales_no = ?", (s_no,)))
            queries.append(("DELETE FROM t_sales_master WHERE sales_no = ?", (s_no,)))

            # -----------------------------------------------------------------
            # [Step 3] 마스터(t_sales_master) 등록
            # -----------------------------------------------------------------
            sql_master = """
                INSERT INTO t_sales_master (
                    sales_no, farm_cd, sales_dt, sales_tp, custm_id,
                    tot_sales_amt, tot_ship_fee, tot_item_amt, tot_paid_amt, tot_unpaid_amt,
                    auction_fee, extra_cost, bill_yn, bill_dt, bill_no, 
                    pay_method_cd, status_cd, rmk, reg_id, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            """
            queries.append((sql_master, (
                s_no, self.farm_cd, sales_date_str, self.sales_tp.currentData(), getattr(self, 'custm_id', None),
                t_total, t_ship, t_sales, t_paid, t_unpaid,
                get_amt(self.auction_fee), get_amt(self.extra_cost),
                ui_bill_yn, ui_bill_dt, ui_bill_no, ui_pay_method, ui_status_cd, ui_master_rmk, self.user_id
            )))

            # -----------------------------------------------------------------
            # [Step 4] 상세 내역(t_sales_detail) 등록 및 배송 정보 수집
            # -----------------------------------------------------------------
            sql_item = """
                INSERT INTO t_sales_detail (
                    sale_detail_no, sales_no, farm_cd, item_cd, variety_cd, 
                    grade_cd, size_cd, qty, unit_price, tot_item_amt, 
                    ship_fee, tot_sale_amt, tot_paid_amt, tot_unpaid_amt, 
                    dlvry_tp, rmk, reg_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            all_delivery_info = []

            for r in range(self.item_table.rowCount()):
                item_cb = self.item_table.cellWidget(r, 1)
                if not item_cb or not item_cb.currentData(): continue

                detail_no = f"{s_no}-S{r+1:02d}"
                row_item_amt = get_amt(self.item_table.cellWidget(r, 7))
                row_ship_fee = get_amt(self.item_table.cellWidget(r, 8))
                row_total_amt = get_amt(self.item_table.cellWidget(r, 9))

                # 상세 테이블 INSERT
                queries.append((sql_item, (
                    detail_no, s_no, self.farm_cd, item_cb.currentData(), 
                    self.item_table.cellWidget(r, 2).currentData(), # Variety
                    self.item_table.cellWidget(r, 4).currentData(), # Grade
                    self.item_table.cellWidget(r, 3).currentData(), # Size
                    get_amt(self.item_table.cellWidget(r, 5)),      # Qty
                    get_amt(self.item_table.cellWidget(r, 6)),      # Price
                    row_item_amt, row_ship_fee, row_total_amt, 
                    0.0, 0.0, # paid/unpaid 상세는 0원 처리
                    self.item_table.cellWidget(r, 10).currentData() if self.item_table.cellWidget(r, 10) else 'LO010100',
                    "", # 상세 rmk는 비움
                    self.user_id
                )))

                # 해당 행의 배송 정보 수령 (delivery_map에서 참조)
                row_deliveries = self.delivery_map.get(r, [])
                for d in row_deliveries:
                    d['sale_detail_no'] = detail_no
                    all_delivery_info.append(d)

            # -----------------------------------------------------------------
            # [Step 5] 수납 상세(t_cash_ledger) 등록
            # -----------------------------------------------------------------
            sql_pay = """
                INSERT INTO t_cash_ledger (
                    paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, 
                    pay_amt, slip_no, rmk, reg_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            for i, item in enumerate(pay_basket):
                if item.get('status') == 'DEL':
                    continue
                pd_no = f"{s_no}-P{i+1:02d}"
                s_key = f"{item['acct_cd']}_{item['method']}"
                slip_no = slip_map.get(s_key)
                queries.append((sql_pay, (
                    pd_no, s_no, self.farm_cd, sales_date_str, item['method'], 
                    item['amt'], slip_no, 
                    item.get('rmk', ''), # 안전하게 get 사용
                    self.user_id
                )))

            # -----------------------------------------------------------------
            # [Step 6] 배송 상세(t_sales_delivery) 등록
            # -----------------------------------------------------------------
            if all_delivery_info:
                sql_deliv = """
                    INSERT INTO t_sales_delivery (
                        dlvry_no, sale_detail_no, sales_no, farm_cd, 
                        snd_name, snd_tel, snd_addr, rcv_name, rcv_tel, rcv_addr, 
                        dlvry_qty, dlvry_msg, reg_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                for i, d in enumerate(all_delivery_info):
                    dl_no = f"{s_no}-D{i+1:03d}"
                    queries.append((sql_deliv, (
                        dl_no, d['sale_detail_no'], s_no, self.farm_cd,
                        d.get('snd_name'), d.get('snd_tel'), d.get('snd_addr'),
                        d.get('rcv_name'), d.get('rcv_tel'), d.get('rcv_addr'),
                        d.get('dlvry_qty', 1), d.get('dlvry_msg'), self.user_id
                    )))

            # -----------------------------------------------------------------
            # [Step 7] 최종 트랜잭션 실행
            # -----------------------------------------------------------------
            if self.db.execute_transaction(queries):
                QMessageBox.information(self, "저장 성공", "모든 데이터가 완벽하게 저장되었습니다! 🍐")
                self.load_sales_data(s_no) # 저장 후 DB 데이터로 화면 갱신
            else:
                QMessageBox.critical(self, "저장 실패", "데이터베이스 트랜잭션 오류가 발생했습니다.")

        except Exception as e:
            QMessageBox.critical(self, "치명적 오류", f"❌ 저장 중 예외 발생: {str(e)}")
            traceback.print_exc()

    # ---------------------------------------------------------
    # [헬퍼] 마스터 테이블(t_sales)용 대표 결제수단 판별
    # ---------------------------------------------------------
    def _get_master_pay_method(self, pay_data_list):
        """
        수금 상세 내역을 분석하여 t_sales에 저장할 대표 코드를 반환한다.
        - AS02... 가 포함되어 있으면 '외상' 혹은 '복합'
        """
        has_cash = False  # AS01 (현금/예금)
        has_credit = False # AS02 (외상매출금)
        
        if not pay_data_list:
            return "AS020101" # 정보 없으면 일단 외상(미수) 처리 or 기타

        for pay in pay_data_list:
            code = pay['method']
            if code.startswith("AS02"): # 외상매출금 계열
                has_credit = True
            elif code.startswith("AS01"): # 현금/예금 계열
                has_cash = True
        
        # 판별 로직
        if has_cash and has_credit:
            return "MIXED"  # 복합결제 (DB에 이 코드가 허용되는지 확인 필요, 아니면 'AS020101'로 퉁침)
        elif has_credit:
            return "AS020101" # 전액 외상
        else:
            return "AS010101" # 전액 현금 (대표코드 하나 선택)

    def generate_sales_no(self, sales_date_str):
        """판매번호 생성 (YYYYMMDD-001)"""
        date_part = sales_date_str.replace('-', '')
        pattern = f"{date_part}-%"
        sql = "SELECT MAX(sales_no) as max_no FROM t_sales_master WHERE sales_no LIKE ? AND farm_cd = ?"
        res = self.db.execute_query(sql, (pattern, self.farm_cd))
        
        if res and res[0]['max_no']:
            last_seq = int(res[0]['max_no'].split('-')[1])
            new_seq = last_seq + 1
        else:
            new_seq = 1
            
        return f"{date_part}-{new_seq:02d}"

    # 배송지 상세 내역 수정 기능
    def on_item_double_clicked(self, row, column):
        """행 더블클릭 시 해당 품목의 배송지 팝업 오픈 (수정 모드)"""
        # [조건 체크] 배송 방식이 '택배' 또는 '화물'일 때만 작동하게 제한 (선택 사항)
        dlvry_tp_cb = self.item_table.cellWidget(row, 10)
        if dlvry_tp_cb:
            tp_cd = dlvry_tp_cb.currentData()
            # 택배(LO010200)나 화물(LO010300) 등이 아닌 '직접인도' 등일 때는 팝업을 막을 수 있습니다.
            if not tp_cd or tp_cd == 'LO010100': # 직접인도 코드 예시
                 # 직접인도일 때도 열고 싶다면 이 조건문을 제거하세요.
                 return

        # 팝업 실행 로직 (기존 등록 로직 재사용)
        self.open_delivery_popup_for_row(row)

    def open_delivery_popup_for_row(self, row):
        """특정 행의 배송지 관리 팝업을 실행하고 결과를 저장 (sender_info 에러 해결)"""
        # 1. 기존 데이터 및 상품 정보 준비
        existing_data = self.delivery_map.get(row, [])
        item_nm = self.item_table.cellWidget(row, 1).currentText()
        
        # 수량 위젯에서 콤마 제거 후 숫자 변환
        qty_text = self.item_table.cellWidget(row, 5).text().replace(',', '')
        total_qty = float(qty_text or 0)

        # [🚨 추가] 보내는 분(과수원/주문자) 정보 생성
        # self.sender_info 대신 현재 선택된 고객 정보를 조회하여 사용합니다.
        sender_info = {'name': '', 'tel': '', 'addr': ''}
        if self.custm_id:
            try:
                res = self.db.execute_query(
                    "SELECT custm_nm, mobile FROM m_customer WHERE custm_id = ?", 
                    (self.custm_id,)
                )
                if res:
                    sender_info = {
                        'name': res[0]['custm_nm'], 
                        'tel': res[0]['mobile'], 
                        'addr': '' # 주소는 필요시 추가 조회
                    }
            except:
                pass

        # 2. 팝업창 생성 (self.sender_info 대신 위에서 만든 sender_info 전달)
        dlg = DeliveryDetailDialog(item_nm, total_qty, sender_info, self)
        
        # 기존 데이터 복원 (이전 답변에서 만든 함수)
        if existing_data:
            dlg.load_existing_data(existing_data) 

        # 3. 팝업 실행 및 결과 반영
        if dlg.exec():
            self.delivery_map[row] = dlg.delivery_list
            self.update_delivery_ui(row)
            # 하단 안내 라벨도 업데이트
            if hasattr(self, 'lbl_selected_status'):
                self.lbl_selected_status.setText(f"{row + 1}번 행 [{item_nm}] 배송지 {len(dlg.delivery_list)}건 수정됨")

    # ---------------------------------------------------------
    # [기능 1] 엑셀 양식 다운로드
    # ---------------------------------------------------------
    def download_excel_form(self):
        """배송지 일괄 등록을 위한 기본 엑셀 양식 다운로드"""
        try:
            # 1. 저장할 파일 경로 묻기
            fname, _ = QFileDialog.getSaveFileName(
                self, "양식 저장", "배송지등록_양식.xlsx", "Excel Files (*.xlsx)"
            )
            if not fname:
                return

            import pandas as pd  # 지연 로딩: 페이지 초기화 속도 개선
            # 2. 데이터프레임 생성 (8개 컬럼 + 예시 데이터)
            data = {
                '보내는분': ['홍길동'],
                '보내는연락처': ['010-1111-2222'],
                '보내는주소': ['서울시 강남구'],
                '받는분': ['김철수'],
                '받는연락처': ['010-3333-4444'],
                '받는주소': ['경기도 수원시'],
                '수량': [1],
                '배송메시지': ['문 앞에 놔주세요']
            }
            df = pd.DataFrame(data)

            # 3. 엑셀로 저장 (인덱스 제외)
            df.to_excel(fname, index=False)
            
            QMessageBox.information(self, "완료", "양식 파일이 저장되었습니다.\n8가지 항목을 채운 뒤 [엑셀 업로드]를 이용하세요.")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"양식 저장 실패: {e}")

    # ---------------------------------------------------------
    # [기능 2] 택배 주소 엑셀 업로드 로직 (검증 로직 강화: 배송방식 & 수량)
    # ---------------------------------------------------------
    def upload_excel_delivery(self):
        """
        엑셀 파일을 읽어 현재 선택된 품목의 배송지로 일괄 등록
        [개선사항]: 배송메시지 누락 방지 및 중복 저장 버그 완벽 차단
        """
        # 1. 선택된 행 확인
        cur_row = getattr(self, 'active_row', -1)
        if cur_row < 0:
            QMessageBox.warning(self, "알림", "배송지를 등록할 품목의 [선택] 버튼을 먼저 눌러주세요.")
            return

        # [검증 1] 배송 방식 체크
        combo_method = self.item_table.cellWidget(cur_row, 10) 
        if combo_method and isinstance(combo_method, QComboBox):
            method_text = combo_method.currentText()
            if "택배" not in method_text and "화물" not in method_text:
                QMessageBox.warning(self, "업로드 불가", 
                    f"현재 배송 방식은 [{method_text}]입니다.\n엑셀 업로드는 '택배' 또는 '화물' 건만 가능합니다.")
                return

        # 2. 파일 선택
        fname, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", "", "Excel Files (*.xlsx *.xls)")
        if not fname:
            return

        import pandas as pd  # 지연 로딩: 페이지 초기화 속도 개선
        try:
            # 3. 엑셀 데이터 읽기
            df = pd.read_excel(fname)
            df.columns = [str(c).strip() for c in df.columns]

            # 필수 컬럼 검증
            required = ['보내는분', '받는분', '받는연락처', '받는주소']
            if not all(col in df.columns for col in required):
                QMessageBox.critical(self, "형식 오류", f"엑셀 필수 컬럼이 누락되었습니다.\n{required}")
                return

            total_rows = len(df)
            new_list = []

            progress = QProgressDialog("엑셀 데이터 분석 중...", "취소", 0, total_rows, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            
            # 메시지 컬럼명 유연하게 찾기 (배송메시지 or 메시지)
            msg_col = next((c for c in df.columns if '메시지' in c), '배송메시지')

            for i, (_, row) in enumerate(df.iterrows()):
                if progress.wasCanceled(): return 

                def get_val(col):
                    return str(row[col]).strip() if col in df.columns and pd.notna(row[col]) else ""
                
                rcv_nm = get_val('받는분')
                rcv_addr = get_val('받는주소')
                if not rcv_nm or not rcv_addr: continue

                # 수량 변환
                try: 
                    qty = float(row['수량']) if '수량' in df.columns and pd.notna(row['수량']) else 1.0
                except: 
                    qty = 1.0

                # 📍 [핵심] 저장 로직과 동일한 'dlvry_msg' 키값 사용
                new_list.append({
                    'snd_name': get_val('보내는분'), 
                    'snd_tel':  get_val('보내는연락처'), 
                    'snd_addr': get_val('보내는주소'),
                    'rcv_name': rcv_nm, 
                    'rcv_tel':  get_val('받는연락처'), 
                    'rcv_addr': rcv_addr,
                    'delivery_qty': qty, 
                    'dlvry_msg': get_val(msg_col), # 메시지 추출 및 키값 통일
                    'invoice_no': ''
                })
                progress.setValue(i + 1)

            if not new_list: 
                QMessageBox.warning(self, "알림", "업로드할 데이터가 없습니다.")
                return

            # [검증 2] 수량 정합성 체크
            qty_widget = self.item_table.cellWidget(cur_row, 5) 
            item_qty = float(qty_widget.text().replace(',', '').strip() or 0) if qty_widget else 0
            
            # ---------------------------------------------------------
            # 4. 데이터 병합 (중복 방지 및 덮어쓰기 로직)
            # ---------------------------------------------------------
            current_data = self.delivery_map.get(cur_row, [])
            
            if len(current_data) > 0:
                reply = QMessageBox.question(self, "기존 데이터 처리", 
                    f"현재 {len(current_data)}건의 데이터가 있습니다.\n\n"
                    "YES: 기존 데이터 앞에 추가 (병합)\n"
                    "NO: 기존 데이터 삭제 후 새로 업로드\n"
                    "CANCEL: 취소",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                 
                if reply == QMessageBox.StandardButton.No:
                    current_data = [] # 초기화
                elif reply == QMessageBox.StandardButton.Cancel:
                    return

            # 최종 병합: 중복 extend 없이 깔끔하게 대입
            self.delivery_map[cur_row] = new_list + current_data

            # 5. 화면 갱신 및 결과 보고
            self.set_active_row(cur_row) # 화면 UI 새로고침
            
            QMessageBox.information(self, "업로드 완료", 
                f"성공: {len(new_list)}건\n"
                f"전체 배송지: {len(self.delivery_map[cur_row])}건")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 처리 중 치명적 오류 발생: {e}")

    # ---------------------------------------------------------
    # [기능 3] 택배 주소 엑셀 다운로드 로직 (검증 로직 강화: 배송방식 & 수량)
    # ---------------------------------------------------------
    def download_delivery_list(self):
        """현재 선택된 품목의 배송지 목록을 엑셀로 내보내기"""
        cur_row = getattr(self, 'active_row', -1)
        if cur_row < 0:
            QMessageBox.warning(self, "알림", "다운로드할 품목의 [선택] 버튼을 먼저 눌러주세요.")
            return

        d_list = self.delivery_map.get(cur_row, [])
        if not d_list:
            QMessageBox.warning(self, "알림", "등록된 배송지 내역이 없습니다."); return

        try:
            fname, _ = QFileDialog.getSaveFileName(self, "엑셀 다운로드", f"배송지목록_{cur_row+1}번행.xlsx", "Excel Files (*.xlsx)")
            if not fname:
                return

            import pandas as pd  # 지연 로딩: 페이지 초기화 속도 개선
            df = pd.DataFrame(d_list)
            # 한글 헤더 매핑
            rename_map = {
                'snd_name':'보내는분', 'snd_tel':'보내는연락처', 'snd_addr':'보내는주소',
                'rcv_name':'받는분', 'rcv_tel':'받는연락처', 'rcv_addr':'받는주소',
                'delivery_qty':'수량', 'delivery_msg':'배송메시지', 'invoice_no':'송장번호'
            }
            df = df.rename(columns=rename_map)
            export_cols = ['보내는분', '보내는연락처', '보내는주소', '받는분', '받는연락처', '받는주소', '수량', '배송메시지', '송장번호']
            df[[c for c in export_cols if c in df.columns]].to_excel(fname, index=False)
            
            QMessageBox.information(self, "완료", f"{len(df)}건의 배송지가 저장되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"다운로드 중 오류 발생: {e}")

    # ---------------------------------------------------------
    # [기능 4] 배송지 선택 삭제 로직
    # ---------------------------------------------------------
    def delete_delivery_row(self):
        """하단 배송지 목록에서 선택된 행 삭제"""
        cur_item_row = getattr(self, 'active_row', -1)
        if cur_item_row < 0: return

        # 선택된 행 인덱스들 가져오기 (복수 선택 가능)
        sel_rows = sorted(set(index.row() for index in self.dlvry_table.selectedIndexes()), reverse=True)
        
        if not sel_rows:
            QMessageBox.warning(self, "알림", "삭제할 배송지를 선택해주세요.")
            return

        confirm = QMessageBox.question(self, "삭제 확인", f"선택한 {len(sel_rows)}건을 삭제하시겠습니까?")
        if confirm == QMessageBox.StandardButton.Yes:
            # 원본 데이터(List) 가져오기
            data_list = self.delivery_map.get(cur_item_row, [])
            
            # 리스트에서 삭제 (뒤에서부터 지워야 인덱스 안 꼬임)
            for r in sel_rows:
                if 0 <= r < len(data_list):
                    del data_list[r]
            
            # 저장 및 갱신
            self.delivery_map[cur_item_row] = data_list
            self.update_delivery_ui(cur_item_row)
            self.on_dlvry_item_selected()

    # ---------------------------------------------------------
    # [기능 5] 전체 선택 / 해제 토글 (수정됨)
    # ---------------------------------------------------------
    def select_all_delivery_rows(self):
        """배송지 목록의 모든 행을 선택하거나 해제 (토글 방식)"""
        # 현재 버튼에 적힌 글자로 상태를 판단합니다.
        text = self.btn_select_all.text()
        
        if "전체 선택" in text:
            # 1. 선택 모드 -> 전체 선택 실행
            self.dlvry_table.selectAll()
            self.btn_select_all.setText("✔ 전체 해제")
            
            # (선택사항) 버튼 색상을 바꿔서 '눌린 상태'임을 강조
            self.btn_select_all.setStyleSheet(MainStyles.BTN_PRIMARY) 
        else:
            # 2. 해제 모드 -> 선택 초기화 실행
            self.dlvry_table.clearSelection()
            self.btn_select_all.setText("✔ 전체 선택")
            
            # 원래 회색 버튼으로 복귀
            self.btn_select_all.setStyleSheet(MainStyles.BTN_SECONDARY)
            
        self.dlvry_table.setFocus()

    # ------------------------------------------------------------------
    # [이벤트 필터] 콤보박스/날짜 입력창의 '마우스 휠'을 무시하게 만드는 함수
    # ------------------------------------------------------------------
    def eventFilter(self, source, event):
        # 1. 휠 이벤트가 발생했는지 확인
        if event.type() == QEvent.Type.Wheel:
            # 2. 그 대상이 콤보박스, 날짜창, 숫자창 중 하나라면?
            if isinstance(source, (QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox)):
                # 3. 휠 동작을 차단(True 반환) -> 값이 안 바뀝니다!
                # (참고: 값이 안 바뀌는 대신 테이블 스크롤도 여기서 멈춥니다)
                return True 
        
        # 그 외 다른 이벤트(클릭 등)는 원래대로 처리
        return super().eventFilter(source, event)

    def set_active_row(self, row):
        """[선택] 버튼 클릭 시 호출"""
        self.active_row = row
        
        # 스타일 맵 (버튼 제외 모든 입력 필드)
        style_map = {
            1: MainStyles.COMBO, 2: MainStyles.COMBO, 3: MainStyles.COMBO, 
            4: MainStyles.COMBO, 10: MainStyles.COMBO,
            5: MainStyles.INPUT_RIGHT, 6: MainStyles.INPUT_RIGHT, 8: MainStyles.INPUT_RIGHT,
            7: MainStyles.INPUT_READONLY, 9: MainStyles.INPUT_TOTAL
        }

        for r in range(self.item_table.rowCount()):
            bg = "#FFF9C4" if r == row else "white"
            for c in range(self.item_table.columnCount()):
                # 0번(선택), 11번(삭제) 버튼 컬럼은 배경색만 변경
                if c in [0, 11]: continue 
                
                w = self.item_table.cellWidget(r, c)
                if w:
                    base = style_map.get(c, "").strip()
                    if not base.endswith(";"): base += ";"
                    # f-string으로 안전하게 결합
                    w.setStyleSheet(f"{base} background-color: {bg};")
        
        # 안내 라벨 갱신 (이미 13px로 줄임)
        item_nm = ""
        item_widget = self.item_table.cellWidget(row, 1)
        if item_widget: item_nm = item_widget.currentText()
            
        if hasattr(self, 'lbl_selected_status'):
            # 텍스트가 너비를 넘지 않도록 간결하게 유지
            self.lbl_selected_status.setText(f"{row + 1}번 행 [{item_nm}] 선택됨")

        self.update_delivery_ui(row)

    def on_pay_row_selected(self, btn_widget):
        """[최종 해결] 위젯 클래스를 직접 타겟팅하여 스타일 우선순위 문제를 해결한 버전"""
        
        target_row = -1
        # 1. 클릭된 버튼이 있는 행 찾기 (전수조사)
        for r in range(self.pay_table.rowCount()):
            if self.pay_table.cellWidget(r, 0) == btn_widget:
                target_row = r
                break
        
        if target_row == -1: return
        
        # 2. 선택된 행 번호 저장 (삭제 시 참조용)
        self.selected_pay_row = target_row
        
        # 3. 각 컬럼별 표준 스타일 정의
        style_map = {
            1: MainStyles.DATE_EDIT,
            2: MainStyles.COMBO,
            3: MainStyles.INPUT_RIGHT,
            4: MainStyles.INPUT_LEFT
        }

        # 4. 테이블 전체 행을 돌며 배경색 갱신
        for r in range(self.pay_table.rowCount()):
            # 선택된 줄은 연한 노랑(#FFF9C4), 나머지는 흰색(white)
            bg_color = "#FFF9C4" if r == target_row else "white"
            
            # [선택] 버튼(0번)을 제외한 나머지 입력 위젯들 처리
            for c in range(1, 5):
                w = self.pay_table.cellWidget(r, c)
                if w:
                    # 해당 위젯의 클래스명 추출 (QComboBox, QDateEdit, QLineEdit 등)
                    class_name = w.metaObject().className()
                    base_style = style_map.get(c, "").strip()
                    
                    # [핵심] 기존 스타일 뒤에 클래스 선택자를 명시하여 배경색 강제 적용
                    # 이렇게 하면 CSS 우선순위(Specificity)가 높아져서 무조건 바뀝니다.
                    force_bg_style = f"{class_name} {{ background-color: {bg_color}; }}"
                    
                    # 최종 스타일 합성: 기존 스타일 + 새로운 배경색 규칙
                    w.setStyleSheet(f"{base_style} {force_bg_style}")
