"""
페이지명 : work_log_page.py
개발일자 : 2026-01-16
개발자 : 전영두 & 지니
화면명 : 영농일지
"""
import sys
from pathlib import Path
for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402
import datetime
import re
from PyQt6.QtCore import QDate, Qt, QTimer, QTime
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from ui.styles import MainStyles, make_app_font
from core.code_manager import CodeManager
from core.account_manager import AccountManager
from core.weather_manager import WeatherManager, convert_to_grid

class EmployeeRegistrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("신규 직원 등록")
        self.setFixedWidth(400)
        self.setStyleSheet(MainStyles.MAIN_BG)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_lbl = QLabel("👨‍🌾 신규 인력 정보 등록")
        title_lbl.setStyleSheet(MainStyles.LBL_TITLE)
        layout.addWidget(title_lbl)

        form_card = QFrame()
        form_card.setStyleSheet(MainStyles.CARD)
        form_layout = QFormLayout(form_card)
        form_layout.setContentsMargins(15, 20, 15, 20)
        form_layout.setVerticalSpacing(12)

        # 1. 성함 입력
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("성함 입력 (필수)")
        self.name_edit.setStyleSheet(MainStyles.INPUT_CENTER)

        # 2. 일당 입력 (화폐 형식 적용)
        self.wage_edit = QLineEdit("0")
        self.wage_edit.setStyleSheet(MainStyles.INPUT_CENTER)
        self.wage_edit.textChanged.connect(self.format_wage)

        # 3. 연락처 입력 (하이픈 자동 생성)
        self.tel_edit = QLineEdit()
        self.tel_edit.setPlaceholderText("010-0000-0000")
        self.tel_edit.setStyleSheet(MainStyles.INPUT_CENTER)
        self.tel_edit.textChanged.connect(self.format_phone)

        # 4. 은행 및 계좌
        self.bank_combo = QComboBox()
        self.bank_combo.addItems(["선택 안 함", "농협", "신한", "국민", "우리", "카카오"])
        self.bank_combo.setStyleSheet(MainStyles.COMBO)

        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("계좌번호 입력")
        self.account_edit.setStyleSheet(MainStyles.INPUT_CENTER)

        labels = ["직원 성함 *", "기본 일당 *", "연락처", "급여 은행", "계좌 번호"]
        widgets = [self.name_edit, self.wage_edit, self.tel_edit, self.bank_combo, self.account_edit]

        for text, widget in zip(labels, widgets):
            lbl = QLabel(text)
            lbl.setStyleSheet(MainStyles.LBL_SUB)
            form_layout.addRow(lbl, widget)
        
        layout.addWidget(form_card)

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setStyleSheet(MainStyles.BTN_SECONDARY)
        self.btn_save = QPushButton("직원 등록")
        self.btn_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.btn_save.clicked.connect(self.validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

    # --- [신규 로직] 실시간 포맷팅 함수들 ---

    def format_wage(self, text):
        """일당 입력 시 천 단위 콤마(#,###) 자동 적용"""
        clean_text = text.replace(",", "")
        if clean_text.isdigit():
            formatted = "{:,}".format(int(clean_text))
            self.wage_edit.blockSignals(True)
            self.wage_edit.setText(formatted)
            self.wage_edit.blockSignals(False)

    def format_phone(self, text):
        """휴대폰 번호 하이픈(-) 자동 삽입 로직"""
        nums = re.sub(r'[^0-9]', '', text) # 숫자만 추출
        if len(nums) > 11: nums = nums[:11] # 11자리 제한
        
        formatted = ""
        if len(nums) <= 3:
            formatted = nums
        elif len(nums) <= 7:
            formatted = f"{nums[:3]}-{nums[3:]}"
        else:
            formatted = f"{nums[:3]}-{nums[3:7]}-{nums[7:]}"
        
        self.tel_edit.blockSignals(True)
        self.tel_edit.setText(formatted)
        self.tel_edit.blockSignals(False)

    def validate_and_accept(self):
        """필수값 검증 로직"""
        name = self.name_edit.text().strip()
        wage = self.wage_edit.text().replace(",", "").strip()
        if not name or not wage or int(wage) <= 0:
            QMessageBox.warning(self, "입력 오류", "성함과 일당을 정확히 입력해주세요.")
            return
        self.accept()

    def get_data(self):
        """최종 데이터 반환 (DB 저장용)"""
        return {
            "pt_nm": self.name_edit.text().strip(),
            "base_price": float(self.wage_edit.text().replace(",", "") or 0),
            "pt_tel": self.tel_edit.text().strip(),
            "bank_cd": self.bank_combo.currentText() if self.bank_combo.currentIndex() > 0 else None,
            "account_no": self.account_edit.text().strip()
        }
    
class WorkLogPage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        self.farm_cd = session.get('farm_cd')
        
        self.user_role = self.session.get('role_cd', 'USER')
        self.current_farm_cd = self.session.get('farm_cd', 'OR001')
        self.my_user_id = self.session.get('user_id', 'ADMIN')

        self.acct_mgr = AccountManager(db_manager, self.farm_cd)
        self.code_mgr = CodeManager(self.db, self.current_farm_cd)

        self.weather_widgets = {} 
        self.selected_work_id = None 

        self.init_ui()
        self.load_initial_codes()
        QTimer.singleShot(500, self.load_master_data)
        self.removed_res_ids = []
        self.removed_exp_ids = []

        # 인건비/경비를 변경을 확인하기 위한 빈 바구니
        self.removed_res_ids = []  # 삭제된 인력 ID 바구니
        self.removed_exp_ids = []  # 삭제된 경비 ID 바구니
                
    def init_ui(self):
        """[수정] 상단 고정 제어 바 도입 및 경비 탭 7컬럼 정비"""
        self.setStyleSheet(MainStyles.MAIN_BG)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- [신규] 상단 고정 제어 바 (스크롤 되지 않음) ---
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: white; border-bottom: 1px solid #EAE7E2;")
        top_bar.setFixedHeight(60)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)

        # 제목 영역
        title_area = QLabel("📝 영농일지 작성")
        title_area.setStyleSheet(MainStyles.LBL_TITLE + "font-size: 16px;")
        top_layout.addWidget(title_area)
        top_layout.addStretch()

        # [위치 이동] 최종 승인 버튼 (상단 고정)
        self.btn_final = QPushButton("💾 최종 승인 및 장부 동기화")
        self.btn_final.setFixedSize(240, 40)
        self.btn_final.setStyleSheet(MainStyles.BTN_PRIMARY + "font-size: 13px;")
        self.btn_final.clicked.connect(self.save_all_integrated_data)
        top_layout.addWidget(self.btn_final)

        main_layout.addWidget(top_bar)

        # --- 전체 스크롤 영역 (기존 content 유지) ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet(MainStyles.MAIN_BG)
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)
        scroll.setWidget(container)

        # --- [1단] 상세 기상 정보 바 ---
        weather_card = QFrame(); weather_card.setStyleSheet(MainStyles.CARD); weather_card.setFixedHeight(120)
        w_layout = QVBoxLayout(weather_card)
        w_head = QHBoxLayout()
        w_head.addWidget(QLabel("⚙️ 상세 기상 정보", styleSheet=MainStyles.LBL_TITLE))
        #날짜선택
        self.date_edit = QDateEdit(QDate.currentDate()); 
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setStyleSheet(MainStyles.COMBO); 
        self.date_edit.dateChanged.connect(self.load_master_data)
        self.date_edit.dateChanged.connect(self.update_day_of_week)
        w_head.addWidget(self.date_edit); 
        w_head.addStretch()
        
        #조회버튼/ 날씨 가져오기 버튼
        btn_w_load = QPushButton("날씨조회"); btn_w_load.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_w_load.clicked.connect(self.load_master_data)
        btn_w_fetch = QPushButton("날씨 가져오기"); btn_w_fetch.setStyleSheet(MainStyles.BTN_FETCH)
        btn_w_fetch.clicked.connect(self.fetch_weather_api)
        w_head.addWidget(btn_w_load); w_head.addWidget(btn_w_fetch)
        w_layout.addLayout(w_head)

        w_grid = QGridLayout()
        self.combo_day = QComboBox(); #요일
        self.combo_day.setStyleSheet(MainStyles.COMBO); #요일
        self.combo_weather = QComboBox()   #날씨
        self.combo_weather.setStyleSheet(MainStyles.COMBO)
        fields = [
            ("요일", "day_of_week"), ("날씨", "weather_cd"), ("최고온도(℃)", "temp_max"), 
            ("최저온도(℃)", "temp_min"), ("강수량(mm)", "precip"), ("습도(%)", "humidity"), 
            ("일출시간", "sun_rise"), ("일몰시간", "sun_set"), ("일조량(시간)", "sunshine_hr"), 
            ("최고풍속(m/s)", "wind_max"), ("최저풍속(m/s)", "wind_min")
        ]
        for i, (name, key) in enumerate(fields):
            vbox = QVBoxLayout(); vbox.setSpacing(1); vbox.addWidget(QLabel(name, styleSheet=MainStyles.LBL_SUB))
            if name == "요일": edit = self.combo_day
            elif name == "날씨": edit = self.combo_weather
            else: edit = QLineEdit(); edit.setStyleSheet(MainStyles.INPUT_CENTER)
            edit.setFixedHeight(28); vbox.addWidget(edit); w_grid.addLayout(vbox, 0, i)
            self.weather_widgets[name] = edit 
        w_layout.addLayout(w_grid)
        content_layout.addWidget(weather_card)

        # --- [2단] 오늘의 이슈 및 장비 고장 기록 ---
        issue_card = QFrame(); 
        issue_card.setStyleSheet(MainStyles.CARD); 
        issue_card.setMinimumHeight(140)
        i_layout = QVBoxLayout(issue_card); 
        i_layout.addWidget(QLabel("📝 오늘의 이슈 및 장비 고장 기록", styleSheet=MainStyles.LBL_TITLE))
        self.txt_issue = QTextEdit(); 
        self.txt_issue.setStyleSheet(MainStyles.TEXT_EDIT)
        self.txt_issue.setPlaceholderText("고장 내역 등을 자유롭게 기록하세요...")
        i_layout.addWidget(self.txt_issue); content_layout.addWidget(issue_card)

        # --- [3단] 작업 목록 ---
        work_card = QFrame(); work_card.setStyleSheet(MainStyles.CARD); work_v_layout = QVBoxLayout(work_card)
        work_head = QHBoxLayout(); work_head.addWidget(QLabel("📋 작업 목록", styleSheet=MainStyles.LBL_TITLE)); work_head.addStretch()
        btn_add_work = QPushButton("+ 작업추가"); btn_add_work.setStyleSheet(MainStyles.BTN_PRIMARY); btn_add_work.clicked.connect(self.add_work_row)
        work_head.addWidget(btn_add_work); work_v_layout.addLayout(work_head)
        self.table_work = QTableWidget(0, 7); 
        #self.table_work.setFixedHeight(160);
        self.table_work.setMinimumHeight(160); 
        self.table_work.setHorizontalHeaderLabels(["조회", "작업내용", "작업장소", "시작", "종료", "상태", "삭제"])
        self.table_work.setStyleSheet(MainStyles.TABLE)
        header_w = self.table_work.horizontalHeader(); 
        header_w.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_work.setColumnWidth(0, 70); 
        work_v_layout.addWidget(self.table_work); 
        content_layout.addWidget(work_card)

        # --- [4단] 상세 리소스 탭 (경비 탭 정비 포함) ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(MainStyles.STYLE_TABS) 
        self.tabs.setMinimumHeight(300)
        
        # 1. [탭] 인력 관리 탭
        self.tab_res = QWidget() 
        res_layout = QVBoxLayout(self.tab_res)

        res_head = QHBoxLayout() 
        res_head.addWidget(QLabel("👨‍🌾 투입 인력 관리", styleSheet=MainStyles.LBL_TITLE))
        
        # [신규] 인력 탭용 작업 안내 레이블
        self.lbl_selected_work_res = QLabel("(작업 목록에서 🔍 조회를 먼저 클릭해주세요)")
        self.lbl_selected_work_res.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
        res_head.addWidget(self.lbl_selected_work_res)
        res_head.addStretch()

        self.lbl_total_sum = QLabel("총계: 0원")
        self.lbl_total_sum.setStyleSheet("font-weight: bold; color: #2D5A27; font-size: 13px;")
        res_head.addWidget(self.lbl_total_sum)

        # 인력추가 버튼
        self.btn_add_res = QPushButton("+ 인력추가")
        self.btn_add_res.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_add_res.clicked.connect(self.add_res_row)
        self.btn_add_res.setEnabled(False) # 초기 비활성화
        res_head.addWidget(self.btn_add_res)

        res_layout.addLayout(res_head)

        # 🚨 [중요] table_res 객체를 먼저 생성해야 에러가 나지 않습니다!
        self.table_res = QTableWidget(0, 8) 
        self.table_res.setHorizontalHeaderLabels(["상태", "직원명", "추가", "시간", "일당", "지급방식", "지급여부", "삭제"])
        self.table_res.setColumnHidden(0, True) # 0번(상태) 숨김
        self.table_res.setColumnWidth(1, 120)  # 직원명 너비
        self.table_res.setStyleSheet(MainStyles.TABLE)
        
        # 인력 테이블 헤더 정책
        header_r = self.table_res.horizontalHeader()
        header_r.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # 직원명 칸 늘리기
        
        res_layout.addWidget(self.table_res)
        self.tabs.addTab(self.tab_res, "인력 관리")

        # 2. [탭] 경비/자재 관리 탭
        self.tab_exp = QWidget()
        exp_layout = QVBoxLayout(self.tab_exp)
        
        exp_head = QHBoxLayout()
        exp_head.addWidget(QLabel("💰 투입 리소스(경비/자재) 상세", styleSheet=MainStyles.LBL_TITLE))

        self.lbl_selected_work_exp = QLabel("(작업 목록에서 🔍 조회를 먼저 클릭해주세요)")
        self.lbl_selected_work_exp.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
        exp_head.addWidget(self.lbl_selected_work_exp)
        exp_head.addStretch()
        
        self.lbl_exp_total = QLabel("경비 총계: 0원")
        self.lbl_exp_total.setStyleSheet("font-weight: bold; color: #2D5A27; font-size: 13px;")
        exp_head.addWidget(self.lbl_exp_total)
        
        self.btn_add_exp = QPushButton("+ 경비추가")
        self.btn_add_exp.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_add_exp.clicked.connect(self.add_exp_row)
        self.btn_add_exp.setEnabled(False) # 초기 비활성화
        exp_head.addWidget(self.btn_add_exp)
        
        exp_layout.addLayout(exp_head)

        # 경비 테이블 설정 (총 10개 컬럼)
        self.table_exp = QTableWidget(0, 10) 
        self.table_exp.setHorizontalHeaderLabels([
            "상태", "발생일자", "지출내용", "상세내역(15자)", "사용금액(총액)", 
            "단가", "수량(인원)", "지불방식", "지불여부", "삭제"
        ])
        self.table_exp.setColumnHidden(0, True) # 0번 '상태' 컬럼 숨기기
        self.table_exp.setStyleSheet(MainStyles.TABLE)
        
        header_e = self.table_exp.horizontalHeader()
        # 지출내용(2)과 상세내역(3) 자동 확장
        header_e.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) 
        header_e.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) 
        
        # 나머지 컬럼 너비 설정
        col_widths = {1: 100, 4: 110, 5: 100, 6: 80, 7: 100, 8: 90, 9: 50}
        for col, width in col_widths.items():
            self.table_exp.setColumnWidth(col, width)

        exp_layout.addWidget(self.table_exp)
        self.tabs.addTab(self.tab_exp, "경비/자재 관리")

        # 탭 위젯을 메인 레이아웃에 추가
        content_layout.addWidget(self.tabs)

    def update_exp_total_label(self):
        """
        [포인트] 경비 탭의 '사용금액(3번 컬럼)'을 실시간 합산하여 레이블에 표시합니다.
        """
        total_sum = 0
        
        # 1. 테이블의 모든 행을 돌면서 금액을 추출합니다.
        for row in range(self.table_exp.rowCount()):
            # 3번 컬럼(사용금액)의 위젯(QLineEdit)을 가져옵니다.
            amt_widget = self.table_exp.cellWidget(row, 4)
            
            if amt_widget and isinstance(amt_widget, QLineEdit):
                # 콤마(,)를 제거하고 숫자로 변환합니다.
                raw_text = amt_widget.text().replace(',', '').strip()
                if raw_text:
                    try:
                        total_sum += int(raw_text)
                    except ValueError:
                        # 숫자가 아닌 값이 들어올 경우 무시합니다.
                        pass

        # 2. 합산 결과를 세 자릿수 콤마 포맷팅하여 레이블에 반영합니다.
        self.lbl_exp_total.setText(f"경비 총계: {total_sum:,}원")
        
        # [참고] 나중에 장부 통합 시 이 값을 참조할 수 있도록 스타일을 유지합니다.
        self.lbl_exp_total.setStyleSheet("font-weight: bold; color: #2D5A27; font-size: 14px;")
    
    # ---------------------------------------------------------
    # 로직 및 편의 기능 메서드
    # ---------------------------------------------------------
    def load_initial_codes(self):
        """[수정] 위젯이 생성된 후 공통 코드를 채웁니다."""
        try:
            weathers = self.code_mgr.get_common_codes('WT01')
            self.combo_weather.clear()
            self.combo_weather.addItem("선택", "")
            for w in weathers:
                self.combo_weather.addItem(w['code_nm'], w['code_cd'])
            # 요일 자동 설정
            # 요일 코드 초기화
            days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
            self.combo_day.clear()
            self.combo_day.addItems(days)
            self.combo_day.setCurrentIndex(QDate.currentDate().toPyDate().weekday())
        except Exception as e:
            print(f"코드 로딩 중 오류 발생: {e}")

    # ---------------------------------------------------------
    # 정비된 경비/자재 행 추가 로직
    # ---------------------------------------------------------
    def add_exp_row(self, data=None):
        """
        [지기님 전용] 바구니 원칙 적용 - 경비 행 추가 및 센서 연결
        1. 0번 컬럼: 상태 표시 (신규는 INS, 로드는 ORG)
        2. 모든 입력 위젯에 변경 감지(check_exp_modified) 연결
        """
        # 1. 작업 선택 여부 확인 (기존 변수명 selected_work_id 권장)
        target_work_id = getattr(self, 'selected_work_id', None) or getattr(self, 'current_work_id', None)
        if not target_work_id:
            QMessageBox.warning(self, "알림", "상단의 '작업 목록'에서 작업을 먼저 선택해주세요.")
            return

        row = self.table_exp.rowCount()
        self.table_exp.insertRow(row)

        # ---------------------------------------------------------
        # 2. [Col 0] 상태 표시줄 (바구니 원칙의 핵심!)
        # ---------------------------------------------------------
        # 데이터가 없이 버튼으로 추가되면 'INS', DB에서 로드되면 'ORG'
        status_text = "ORG" if data else "INS"
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 신규 행이면 UserRole에 'NEW'라고 표시해둡니다.
        if not data:
            status_item.setData(Qt.ItemDataRole.UserRole, "NEW")
        
        self.table_exp.setItem(row, 0, status_item)

        # ---------------------------------------------------------
        # 3. 위젯 생성 및 실시간 센서(check_exp_modified) 연결
        # ---------------------------------------------------------
        # [Col 1] 지출계정 콤보
        acct_combo = QComboBox()
        acct_combo.setStyleSheet(MainStyles.COMBO)
        
        # 0번: 상태 (Hidden)
        status_text = "ORG" if data else "INS"
        status_item = QTableWidgetItem(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, data.get('exp_id') if data else "NEW")
        if data: status_item.setData(Qt.ItemDataRole.UserRole + 1, dict(data))
        self.table_exp.setItem(row, 0, status_item)
        
        # 1번: 발생일자 (추가된 컬럼)
        dt_edit = QDateEdit()
        dt_edit.setCalendarPopup(True)
        dt_edit.setDate(QDate.fromString(data.get('trans_dt'), "yyyy-MM-dd") if data else self.date_edit.date())
        dt_edit.setStyleSheet(MainStyles.DATE_EDIT)
        # 📍 센서 연결
        dt_edit.dateChanged.connect(lambda _, r=row: self.check_exp_modified(r)) # 센서 연결
        self.table_exp.setCellWidget(row, 1, dt_edit)
        
        # 2번: 지출내용 (기존 1번)
        acct_combo = QComboBox()
        if hasattr(self, 'expense_accounts'):
            for acct in self.expense_accounts:
                acct_combo.addItem(acct['acct_nm'], acct['acct_cd'])
        # 📍 센서 연결
        acct_combo.currentIndexChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 2, acct_combo)

        # 3번: 상세내역 (기존 2번)
        item_edit = QLineEdit()
        item_edit.textChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 3, item_edit)

        # [Col 4] 사용금액 (합계 계산 + 콤마 포맷팅 + 센서)
        le_amt = QLineEdit("0")
        le_amt.setStyleSheet(MainStyles.INPUT_CENTER + "font-weight: bold; color: blue;")
        le_amt.textChanged.connect(lambda t, w=le_amt: self.format_comma_and_calculate(w))
        le_amt.textChanged.connect(self.update_exp_total_label)
        # 📍 센서 연결
        le_amt.textChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 4, le_amt)

        # [Col 5] 단가
        le_unit = QLineEdit("0")
        le_unit.setStyleSheet(MainStyles.INPUT_CENTER)
        le_unit.textChanged.connect(lambda t, w=le_unit: self.format_comma_and_calculate(w))
        # 📍 센서 연결
        le_unit.textChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 5, le_unit)

        # [Col 6] 수량
        le_qty = QLineEdit("1")
        le_qty.setStyleSheet(MainStyles.INPUT_CENTER)
        # 📍 센서 연결
        le_qty.textChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 6, le_qty)

        # [Col 7] 지불방식
        pay_method_cb = QComboBox()
        pay_method_cb.setStyleSheet(MainStyles.COMBO)
        if hasattr(self, 'asset_accounts'):
            for acct in self.asset_accounts:
                pay_method_cb.addItem(acct['acct_nm'], acct['acct_cd'])
        # 📍 센서 연결
        pay_method_cb.currentIndexChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 7, pay_method_cb)

        # [Col 8] 지불여부
        status_combo = QComboBox()
        status_combo.setStyleSheet(MainStyles.COMBO)
        status_combo.addItem("NO", "N")
        status_combo.addItem("YES", "Y")
        # 📍 센서 연결
        status_combo.currentIndexChanged.connect(lambda _, r=row: self.check_exp_modified(r))
        self.table_exp.setCellWidget(row, 8, status_combo)

        # [Col 9] 삭제 버튼
        btn_del = QPushButton("❌")
        btn_del.setStyleSheet("border:none; color:red;")
        btn_del.clicked.connect(self.remove_exp_row)
        btn_del.clicked.connect(self.update_exp_total_label)
        self.table_exp.setCellWidget(row, 9, btn_del)

    def remove_exp_row(self):
        """[지기님 전용] 경비 행 삭제 및 DB 삭제 바구니 등록"""
        button = self.sender()
        if not button: return
        
        # 클릭된 버튼이 있는 행 번호 계산
        index = self.table_exp.indexAt(button.pos())
        row = index.row()
        if row < 0: return

        # 0번 컬럼에서 exp_id(PK) 추출
        id_item = self.table_exp.item(row, 0)
        exp_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None

        print(f"🗑️ [삭제 수사] 행 번호: {row}, 추출된 ID: {exp_id}")

        # DB에 저장된 적이 있는 데이터(ID 존재)라면 바구니에 담기
        if exp_id:
            if not hasattr(self, 'removed_exp_ids'):
                self.removed_exp_ids = []
            if exp_id not in self.removed_exp_ids:
                self.removed_exp_ids.append(exp_id)
                print(f"✅ 바구니 등록 완료: {exp_id}")

        # UI에서 행 제거
        self.table_exp.removeRow(row)
        self.update_exp_total_label() # 합계 갱신

    # 화면Load시 오늘의 날씨, 작업목록 가져오기
    def load_master_data(self):
        """
        [최종 교정] 날짜 변경 시 모든 테이블 초기화 및 데이터 로드
        - 신호 차단 후 반드시 해제하여 날짜 변경 기능이 유지되도록 수정
        """
        try:
            # 1. [핵심] 신호 차단 (데이터 로딩 중 발생하는 중복 호출 방지)
            self.date_edit.blockSignals(True)

            if not hasattr(self, 'table_work') or self.table_work is None:
                return
            
            # 2. 날짜 변경 시 UI 상태 완전 초기화
            self.current_work_id = None 
            self.selected_work_id = None
            
            # 테이블 내용 리셋
            self.table_work.setRowCount(0) 
            self.table_res.setRowCount(0)  
            self.table_exp.setRowCount(0)  
            
            # 안내 레이블 및 버튼 상태 리셋
            reset_msg = "(작업 목록에서 🔍 조회를 먼저 클릭해주세요)"
            self.lbl_selected_work_res.setText(reset_msg)
            self.lbl_selected_work_res.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
            self.lbl_selected_work_exp.setText(reset_msg)
            self.lbl_selected_work_exp.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
            
            self.btn_add_res.setEnabled(False)
            self.btn_add_exp.setEnabled(False)
            
            self.lbl_total_sum.setText("총계: 0원")
            self.lbl_exp_total.setText("경비 총계: 0원")

            # 3. 데이터 조회 및 표시
            work_dt = self.date_edit.date().toString("yyyy-MM-dd")
            
            # 날씨 정보 로드
            weather_res = self.db.get_weather_info(self.current_farm_cd, work_dt)
            self.display_weather(weather_res) 

            # 작업 목록 로드
            work_res = self.db.get_work_details(self.current_farm_cd, work_dt)
            
            if work_res:
                for row_data in work_res:
                    data = dict(row_data)
                    self.add_work_row()
                    curr_row = self.table_work.rowCount() - 1
                    
                    # 위젯 데이터 매핑 및 인덱스 조정 (조회 버튼 고려)
                    self.table_work.cellWidget(curr_row, 1).setCurrentIndex(
                        self.table_work.cellWidget(curr_row, 1).findData(data.get('work_mid_cd'))
                    )
                    self.table_work.cellWidget(curr_row, 2).setCurrentIndex(
                        self.table_work.cellWidget(curr_row, 2).findData(data.get('work_loc_id'))
                    )
                    self.table_work.cellWidget(curr_row, 3).setTime(QTime.fromString(data.get('start_tm'), "HH:mm"))
                    self.table_work.cellWidget(curr_row, 4).setTime(QTime.fromString(data.get('end_tm'), "HH:mm"))
                    
                    status_widget = self.table_work.cellWidget(curr_row, 5)
                    if status_widget:
                        status_widget.setCurrentIndex(status_widget.findData(data.get('status_cd')))

                self.window().show_status(f"✅ [{work_dt}] 정보 조회 완료 (작업 {len(work_res)}건)")
            else:
                self.window().show_status(f"ℹ️ [{work_dt}] 저장된 정보가 없습니다.")

            if hasattr(self, 'acct_mgr'):
                # 1. 지불방식 (자산 AS0101: 현금/예금) - Level 4
                self.asset_accounts = self.acct_mgr.get_account_codes('AS0101', target_level=4)
                # 2. 경비내용 (비용 EX) - Level 4
                self.expense_accounts = self.acct_mgr.get_account_codes('EX', target_level=4)

                # [참고] 판매 페이지에서는 target_level 없이 호출하므로 기존대로 다 가져갑니다.
            else:
                self.asset_accounts = []
                self.expense_accounts = []

        except (RuntimeError, AttributeError) as e:
            print(f"⚠️ 데이터 로드 중 오류 발생: {e}")
            QTimer.singleShot(200, self.load_master_data)
            
        finally:
            # 4. [🚨 핵심 수정] 작업 완료 후 반드시 신호 차단 해제
            # 이 코드가 있어야 다음 번 날짜 변경 시에도 이 함수가 다시 호출됩니다.
            self.date_edit.blockSignals(False)

    #화면 로딩시 조회된 날씨데이터를 가져와서 보여줌
    def display_weather(self, weather_res):
        """조회된 날씨/이슈 데이터를 모든 위젯에 정확히 배치합니다."""
        now_time = datetime.datetime.now().strftime("%H:%M")

        # 요일 업데이트
        self.update_day_of_week(self.date_edit.date())
        
        if weather_res:
            row = dict(weather_res[0])
            
            # 1. 요일 및 날씨 설정
            self.combo_day.setCurrentText(row.get('day_of_week', ''))
            w_code = row.get('weather_cd')
            weather_idx = self.combo_weather.findData(w_code)
            if weather_idx >= 0: 
                self.combo_weather.setCurrentIndex(weather_idx)

            # 2. [핵심] 상세 필드 매핑 - UI 생성 시 이름과 100% 일치시킴
            mapping = {
                'temp_max': "최고온도(℃)", 
                'temp_min': "최저온도(℃)",
                'precip': "강수량(mm)", 
                'humidity': "습도(%)",
                'sun_rise': "일출시간", 
                'sun_set': "일몰시간",
                'sunshine_hr': "일조량(시간)",  # sunshine_hr 데이터를 "일조량(시간)" 위젯에 표시
                'wind_max': "최고풍속(m/s)",    # wind_max 데이터를 "최고풍속(m/s)" 위젯에 표시
                'wind_min': "최저풍속(m/s)"     # wind_min 데이터를 "최저풍속(m/s)" 위젯에 표시
            }

            for db_key, widget_key in mapping.items():
                if widget_key in self.weather_widgets:
                    val = row.get(db_key)
                    # 데이터가 0.0인 경우에도 표시되도록 str()로 변환
                    self.weather_widgets[widget_key].setText(str(val) if val is not None else "")
            
            # 3. 이슈 항목 (work_rmk) 복원
            issue_val = row.get('work_rmk', '')
            self.txt_issue.setPlainText(str(issue_val) if issue_val else "")

            self.window().show_status(f"🌤️ [{row.get('work_dt')}] 날씨와 이슈를 불러왔습니다.")
        else:
            # 데이터가 없는 날짜 초기화
            for name, w in self.weather_widgets.items():
                if isinstance(w, QLineEdit):
                    w.setText(now_time if "시간" in name else "")
            self.combo_weather.setCurrentIndex(0)
            self.txt_issue.clear()
    
    # =========================================================
    # 기능 구현부
    # =========================================================
    # 날씨 가져오기
    def fetch_weather_api(self):
        """DB에서 현재 농장의 모든 위치 정보(lat, lon, nx, ny)를 가져옵니다."""
        # 🚨 lat, lon까지 포함하여 조회하도록 쿼리 확장
        sql_loc = "SELECT lat, lon, nx, ny FROM m_farm_info WHERE farm_cd = ?"
        loc_res = self.db.execute_query(sql_loc, (self.current_farm_cd,))
        
        # 🚨 [안전장치] 위치 정보가 하나라도 없으면 즉시 차단합니다.
        if not loc_res or not all([loc_res[0][0], loc_res[0][1], loc_res[0][2], loc_res[0][3]]):
            QMessageBox.warning(
                self, "위치 정보 누락", 
                "현재 농장의 위도, 경도, 혹은 격자 정보가 등록되지 않았습니다.\n\n"
                "'과수원 관리' 페이지에서 위치를 먼저 저장해 주세요."
            )
            return

        # DB에서 꺼낸 실제 값들
        lat, lon, nx, ny = loc_res[0]
        work_dt = self.date_edit.date().toString("yyyy-MM-dd")

        try:
            wm = WeatherManager()
            # 🚨 get_weather 함수에 lat, lon을 함께 전달하여 계산하게 함
            w_data = wm.get_weather(nx, ny, work_dt, lat, lon)

            if w_data:
                # 🚨 지기님의 UI 위젯 이름과 100% 일치하도록 매핑
                mapping = {
                    "최고온도(℃)": w_data.get('temp_max'),
                    "최저온도(℃)": w_data.get('temp_min'),
                    "강수량(mm)": w_data.get('precip'),
                    "습도(%)": w_data.get('humidity'),
                    "일출시간": w_data.get('sun_rise'),
                    "일몰시간": w_data.get('sun_set'),
                    "일조량(시간)": w_data.get('sunshine_hr'),
                    "최고풍속(m/s)": w_data.get('wind_max'),
                    "최저풍속(m/s)": w_data.get('wind_min')
                }

                for label, val in mapping.items():
                    if label in self.weather_widgets:
                        self.weather_widgets[label].setText(str(val))
                
                # 날씨 코드 처리 (WT019900 대응 포함)
                weather_cd = w_data.get('weather_cd')
                idx = self.combo_weather.findData(weather_cd)
                if idx >= 0:
                    self.combo_weather.setCurrentIndex(idx)
                else:
                    other_idx = self.combo_weather.findData('WT019900')
                    if other_idx >= 0: self.combo_weather.setCurrentIndex(other_idx)
                
                if hasattr(self.window(), 'show_status'):
                    self.window().show_status("✅ 모든 기상 데이터 동기화 완료!")

        except Exception as e:
            QMessageBox.critical(self, "통신 에러", f"날씨 연동 중 오류 발생: {e}")

    def update_day_of_week(self, qdate):
        weekday = qdate.toPyDate().weekday()
        self.combo_day.setCurrentIndex(weekday)
   
    def save_master_data(self):
        """기상 정보 및 이슈 메모 저장 로직"""
        work_dt = self.date_edit.date().toString("yyyy-MM-dd")
        w_code = self.combo_weather.currentData()
        
        if not w_code or w_code == "":
            QMessageBox.warning(self, "알림", "날씨 정보를 선택해주세요.")
            return False # 실패 반환
            
        weather_data = {
            'day_of_week': self.combo_day.currentText(),
            'weather_cd': w_code,
            'work_rmk': self.txt_issue.toPlainText().strip(),
            'temp_min': self.weather_widgets["최저온도(℃)"].text(),
            'temp_max': self.weather_widgets["최고온도(℃)"].text(),
            'precip': self.weather_widgets["강수량(mm)"].text(),
            'humidity': self.weather_widgets["습도(%)"].text(),
            'sun_rise': self.weather_widgets["일출시간"].text(),
            'sun_set': self.weather_widgets["일몰시간"].text(),
            'sunshine_hr': self.weather_widgets["일조량(시간)"].text(),
            'wind_max': self.weather_widgets["최고풍속(m/s)"].text(),
            'wind_min': self.weather_widgets["최저풍속(m/s)"].text()
        }
        
        try:
            if self.db.save_weather_data(self.current_farm_cd, work_dt, weather_data, self.my_user_id):
                self.window().show_status(f"☀️ [{work_dt}] 기상 정보가 저장되었습니다.")
                return True # 성공 반환
            else:
                return False
        except Exception as e:
            QMessageBox.critical(self, "오류", f"기상 저장 실패: {e}")
            return False

    def add_work_row(self):
        
        row = self.table_work.rowCount()
        self.table_work.insertRow(row)
        c_font = make_app_font(10)

        # 0번: 조회 버튼 (신규 추가)
        btn_view = QPushButton("🔍")
        btn_view.setStyleSheet(MainStyles.BTN_PRIMARY + "padding:0px;")
        # 클릭 시 해당 행의 인덱스를 들고 load_linked_resource로 이동
        btn_view.clicked.connect(lambda _, r=row: self.load_linked_resource(r))
        self.table_work.setCellWidget(row, 0, btn_view)
        self.table_work.setCellWidget(row, 0, btn_view)
        
        # 1번: 작업내용 (중분류 콤보박스 - WK01 고정 로드)
        work_combo = QComboBox()
        work_combo.setStyleSheet(MainStyles.COMBO)
        work_combo.setFont(c_font)
        work_combo.addItem("작업 선택", "")
        for s in self.code_mgr.get_sub_work_codes('WK01'): # 영농작업 하위 코드
            work_combo.addItem(s['code_nm'], s['code_cd'])
        self.table_work.setCellWidget(row, 1, work_combo)

        # 2번: 작업장소 (m_farm_site 콤보박스)
        loc_combo = QComboBox()
        loc_combo.setStyleSheet(MainStyles.COMBO)
        loc_combo.setFont(c_font)
        loc_combo.addItem("장소 선택", "")

        sites = self.code_mgr.get_farm_sites()

        if sites: # 데이터가 있을 때만 루프 실행
            for loc in sites:
                loc_combo.addItem(loc['site_nm'], loc['site_id'])
        self.table_work.setCellWidget(row, 2, loc_combo)

        # 3번: 시작 / 4번: 종료 (QTimeEdit - 스타일 및 폰트 보정)
        for col in [3, 4]:
            te = QTimeEdit(QTime.currentTime())
            te.setDisplayFormat("HH:mm")
            te.setStyleSheet(MainStyles.COMBO)
            te.setFont(c_font)
            te.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_work.setCellWidget(row, col, te)
        # 5. 상태 (콤보박스 - 공통코드 'ST01' 로드)
        status_combo = QComboBox()
        status_combo.setStyleSheet(MainStyles.COMBO)
        status_combo.setFont(c_font)
        status_combo.addItem("상태 선택", "") # 기본 문구
        
        # [수정] DB에서 상태 코드 리스트 가져오기
        try:
            status_list = self.code_mgr.get_common_codes('ST01') 
            if status_list:
                for s in status_list:
                    # s['code_nm'] 형식이 맞는지 확인하며 추가
                    status_combo.addItem(str(s['code_nm']), str(s['code_cd']))
            else:
                # 데이터가 없을 경우를 대비한 하드코딩 (보험)
                status_combo.addItems(["진행", "완료", "지연"])
        except Exception as e:
            print(f"상태 코드 로드 실패: {e}")

        self.table_work.setCellWidget(row, 5, status_combo)

        # 6번: 삭제 버튼
        btn_del = QPushButton("❌")
        btn_del.setStyleSheet("border:none; color:red; font-weight:bold;")
        btn_del.clicked.connect(lambda: self.table_work.removeRow(self.table_work.currentRow()))
        self.table_work.setCellWidget(row, 6, btn_del)
    
    def load_linked_resource(self, row):
        """
        [교정본] 이벤트 신호를 일시 차단하여 화면 멈춤을 방지하고 
        데이터를 안전하게 로드합니다.
        """
        # [방어 로직] 비정상적인 행 번호 차단
        if row < 0 or row >= self.table_work.rowCount():
            return

        # [핵심] 모든 위젯 신호를 잠시 차단하여 무한 루프를 방지합니다.
        self.blockSignals(True)
        
        try:
            # 1. 해당 행에서 작업 정보 추출 (기존 로직 유지)
            work_combo = self.table_work.cellWidget(row, 1)
            work_nm = work_combo.currentText() if work_combo else "미지정 작업"
            
            work_dt_str = self.date_edit.date().toString("yyyyMMdd")
            work_id = f"{work_dt_str}-{row + 1:02d}"

            # 2. 클래스 전역 변수 저장
            self.current_work_id = work_id
            self.selected_work_id = work_id 
            
            # 3. 시각적 피드백 업데이트
            display_text = f"▶ 현재 선택된 작업: [{work_id}] {work_nm}"
            self.lbl_selected_work_res.setText(display_text)
            self.lbl_selected_work_res.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
            self.lbl_selected_work_exp.setText(display_text)
            self.lbl_selected_work_exp.setStyleSheet(MainStyles.LbL_HIGHTLIGHT)
            
            # 4. 버튼 활성화
            self.btn_add_res.setEnabled(True)
            self.btn_add_exp.setEnabled(True)
            
            # 5. DB 데이터 로드 (멈춤 발생 위험 구간을 try-finally로 보호)
            self.load_res_data(work_id)       
            self.load_work_expenses(work_id)  
            
            self.window().show_status(f"📂 작업 [{work_id}] 편집 모드로 전환되었습니다.")
            
        except Exception as e:
            print(f"❌ 상세 리소스 로드 중 오류 발생: {e}")
        
        finally:
            # [핵심] 작업이 끝나면 반드시 신호를 다시 복구합니다.
            self.blockSignals(False)
            # 수동으로 합계 계산을 한 번 호출하여 UI를 최신화합니다.
            self.calculate_total_sum()

    def update_sub_categories(self, main_combo, sub_combo):
        """대분류 콤보박스의 선택값에 따라 중분류 콤보박스의 아이템을 변경합니다."""
        # 1. 현재 대분류에서 선택된 코드값(예: WK0101)을 가져옵니다.
        parent_cd = main_combo.currentData()
        
        # 2. 중분류 콤보박스를 일단 깨끗하게 비웁니다.
        sub_combo.clear()
        
        if parent_cd:
            # 3. CodeManager에게 해당 대분류에 속한 중분류 리스트를 요청합니다.
            sub_codes = self.code_mgr.get_sub_work_codes(parent_cd)
            
            # 4. 가져온 데이터를 중분류 콤보박스에 하나씩 담습니다.
            for s in sub_codes:
                sub_combo.addItem(s['code_nm'], s['code_cd'])
        else:
            sub_combo.addItem("대분류 선택", "")

    # 인건비 table변경 flag
    def check_res_modified(self, row):
        """인력 행 변경 감지: 일당, 지불방식, 지불상태가 바뀌면 MOD로 인식"""
        status_item = self.table_res.item(row, 0)
        if not status_item or status_item.text() == "INS": return 

        orig = status_item.data(Qt.ItemDataRole.UserRole + 1)
        if not orig: return

        # 현재 화면 값 추출
        wage_edit = self.table_res.cellWidget(row, 4)     # 일당(Col 4)
        method_combo = self.table_res.cellWidget(row, 5)  # 방식(Col 5)
        status_combo = self.table_res.cellWidget(row, 6)  # 여부(Col 6)
        
        if not all([wage_edit, method_combo, status_combo]): return
        
        curr_amt = int(wage_edit.text().replace(',', '').strip() or 0)
        curr_method = str(method_combo.currentData())
        curr_status = str(status_combo.currentData())

        # 📍 하나라도 다르면 MOD
        is_changed = (
            curr_amt != int(orig.get('amt') or orig.get('daily_wage') or 0) or
            curr_method != str(orig.get('pay_method_cd')) or
            curr_status != str(orig.get('pay_status'))
        )

        if is_changed:
            status_item.setText("MOD")
            status_item.setBackground(QColor("#FFF9C4")) 
        else:
            status_item.setText("ORG")
            status_item.setBackground(QColor("white"))

    # 비용 table변경 flag
    def check_exp_modified(self, row):
        """
        [지기님 요청 수정] 경비 행 변경 감지 센서 (5대 핵심 필드)
        감지 대상: 발생일자(1), 지출내용/계정(2), 금액(4), 지불방식(7), 지불여부(8)
        """
        status_item = self.table_exp.item(row, 0)
        if not status_item or status_item.text() == "INS": return 

        orig = status_item.data(Qt.ItemDataRole.UserRole + 1) 
        if not orig: return

        # 1. 화면의 현재 값들 추출
        dt_widget = self.table_exp.cellWidget(row, 1)      # 발생일자
        acct_widget = self.table_exp.cellWidget(row, 2)    # 지출내용(계정) 👈 추가
        amt_widget = self.table_exp.cellWidget(row, 4)     # 사용금액
        method_widget = self.table_exp.cellWidget(row, 7)  # 지불방식
        status_widget = self.table_exp.cellWidget(row, 8)  # 지불여부

        if not all([dt_widget, acct_widget, amt_widget, method_widget, status_widget]): return

        curr_dt = dt_widget.date().toString("yyyy-MM-dd")
        curr_acct = str(acct_widget.currentData())         # 👈 현재 계정코드
        curr_amt = int(amt_widget.text().replace(',', '').strip() or 0)
        curr_method = str(method_widget.currentData())
        curr_status = str(status_widget.currentData())

        # 2. 원본 데이터와 비교
        is_changed = (
            curr_dt != str(orig.get('trans_dt')) or
            curr_acct != str(orig.get('acct_cd')) or       # 👈 계정코드 비교 추가
            curr_amt != int(orig.get('total_amt') or orig.get('amt') or 0) or
            curr_method != str(orig.get('pay_method_cd')) or
            curr_status != str(orig.get('pay_status'))
        )

        # 3. 결과 반영
        if is_changed:
            status_item.setText("MOD")
            status_item.setBackground(QColor("#FFF9C4")) # 연노랑색
        else:
            status_item.setText("ORG")
            status_item.setBackground(QColor("white"))

    # work_log_page.py 의 save_work_data 함수 수정
    def save_work_data(self):
        """테이블 위젯의 데이터를 리스트로 변환하여 DBManager에 전달"""
        work_dt = self.date_edit.date().toString("yyyy-MM-dd")        
        # 1. DBManager에게 전달할 순수 데이터 리스트 만들기 (바구니 담기)
        work_data_list = []
        for r in range(self.table_work.rowCount()):
            # [인덱스 수정] 1:작업내용, 2:장소, 3:시작, 4:종료, 5:상태
            mid_combo = self.table_work.cellWidget(r, 1)
            mid_cd = mid_combo.currentData() if mid_combo else None
            
            if not mid_cd: continue # 작업내용이 선택 안 된 행은 제외
            
            work_data_list.append({
                'mid_cd': mid_cd,
                'loc_id': self.table_work.cellWidget(r, 2).currentData(),
                'start_tm': self.table_work.cellWidget(r, 3).time().toString("HH:mm"),
                'end_tm': self.table_work.cellWidget(r, 4).time().toString("HH:mm"),
                'status': self.table_work.cellWidget(r, 5).currentData()
            })

        # 2. DBManager의 전용 메서드 호출
        try:
            if self.db.save_work_details(work_dt, self.current_farm_cd, work_data_list, self.my_user_id):
                self.window().show_status(f"✅ [{work_dt}] 작업 저장 완료")
                return True # [핵심] 성공 리턴 추가
        except Exception as e:
            print(f"저장 오류: {e}")
            return False # 실패 리턴
        return False

    def load_res_data(self, work_id):
        self.table_res.setUpdatesEnabled(False)
        self.blockSignals(True)

        try:
            self.table_res.setRowCount(0)
            self.removed_res_ids = [] 
            res_list = self.db.get_work_resources(work_id)

            if not res_list:
                self.lbl_total_sum.setText("총계: 0원")
                return

            for r, data in enumerate(res_list):
                row_data = dict(data)
                # 📍 행 추가 (이미 8컬럼으로 생성됨)
                self.add_res_row(row_data) 
                curr_row = self.table_res.rowCount() - 1

                # 📍 [교정] 0번 컬럼: 상태(ORG) 및 ID 보관
                status_item = self.table_res.item(curr_row, 0)
                if status_item:
                    status_item.setText("ORG")
                    status_item.setData(Qt.ItemDataRole.UserRole, row_data.get('res_id'))
                    status_item.setData(Qt.ItemDataRole.UserRole + 1, row_data)

                # 📍 [교정] 위젯별 데이터 매핑 (1:직원, 3:시간, 4:일당, 5:방식, 6:여부)
                widgets_info = {
                    1: (row_data.get('emp_cd'), 'combo'),
                    3: (str(row_data.get('man_hour', '0')), 'edit'),
                    4: (f"{int(row_data.get('daily_wage', 0)):,}", 'edit'),
                    5: (row_data.get('pay_method_cd'), 'combo'),
                    6: (row_data.get('pay_status', 'N'), 'combo')
                }

                for col, (val, w_type) in widgets_info.items():
                    w = self.table_res.cellWidget(curr_row, col)
                    if w:
                        w.blockSignals(True)
                        if w_type == 'combo':
                            w.setCurrentIndex(w.findData(val))
                        else:
                            w.setText(val)
                        w.blockSignals(False)

        except Exception as e:
            print(f"❌ [인력 로드 에러] {e}")
        finally:
            self.blockSignals(False)
            self.table_res.setUpdatesEnabled(True)
            self.calculate_total_sum()

    def load_work_expenses(self, work_id):
        self.table_exp.setUpdatesEnabled(False)
        self.blockSignals(True)
        
        try:
            self.table_exp.setRowCount(0)
            self.removed_exp_ids = [] 
            exp_list = self.db.get_work_expenses(work_id)
            if not exp_list: return

            for r, data in enumerate(exp_list):
                row_data = dict(data)
                self.add_exp_row(row_data) 
                curr_row = self.table_exp.rowCount() - 1

                # 📍 [교정] 0번 컬럼 상태 설정
                status_item = self.table_exp.item(curr_row, 0)
                if status_item:
                    status_item.setText("ORG")
                    status_item.setData(Qt.ItemDataRole.UserRole, row_data.get('exp_id'))
                    status_item.setData(Qt.ItemDataRole.UserRole + 1, row_data)

                # 📍 [교정] 10컬럼 체계 매핑 (1:날짜, 2:계정, 3:내역, 4:금액, 5:단가, 6:수량, 7:방식, 8:여부)
                mapping = {
                    1: (row_data.get('trans_dt'), 'date'),
                    2: (row_data.get('acct_cd'), 'combo'),
                    3: (row_data.get('item_nm') or "", 'edit'),
                    4: (f"{int(row_data.get('total_amt') or 0):,}", 'edit'),
                    5: (f"{int(row_data.get('unit_price') or 0):,}", 'edit'),
                    6: (str(row_data.get('qty') or 1), 'edit'),
                    7: (row_data.get('pay_method_cd'), 'combo'),
                    8: (row_data.get('pay_status', 'N'), 'combo')
                }

                for col, (val, w_type) in mapping.items():
                    w = self.table_exp.cellWidget(curr_row, col)
                    if w:
                        w.blockSignals(True)
                        if w_type == 'combo':
                            w.setCurrentIndex(w.findData(val))
                        elif w_type == 'date':
                            w.setDate(QDate.fromString(val, "yyyy-MM-dd"))
                        else:
                            w.setText(str(val))
                        w.blockSignals(False)

        except Exception as e:
            print(f"❌ [경비 로드 에러] {e}")
        finally:
            self.blockSignals(False)
            self.table_exp.setUpdatesEnabled(True)
            self.update_exp_total_label()

    def remove_res_row(self):
        """[최종 검정판] 버튼의 위치를 계산하여 정확한 행의 ID를 바구니에 담습니다."""
        button = self.sender()
        if not button:
            row = self.table_res.currentRow()
        else:
            index = self.table_res.indexAt(button.pos())
            row = index.row()

        if row < 0: 
            print("⚠️ 삭제할 행을 찾을 수 없습니다.")
            return

        # [교정] 0번 열의 아이템을 가져옵니다. 
        # load_res_data에서 item을 생성해주었으므로 이제 None이 아닐 것입니다.
        item = self.table_res.item(row, 0)
        res_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        
        # [추가 디버그] 아이템 존재 여부까지 확인하면 더 완벽합니다.
        if not item:
            print(f"⚠️ 경고: {row}행 0번 열에 Item 객체가 없습니다. 위젯만 있고 Item이 생성되지 않았을 수 있습니다.")

        print(f"DEBUG: ❌ 삭제 시도 - 행 번호: {row}, 수집된 ID: {res_id}")

        # 3. DB 기록인 경우만 바구니 등록
        # ID가 존재하고, "NEW"가 아닐 때만 삭제 바구니에 넣습니다. 
        if res_id and res_id != "NEW":
            if res_id not in self.removed_res_ids: # 중복 담기 방지
                self.removed_res_ids.append(res_id)
                print(f"🗑️ [회계 이력] 기존 데이터 '{res_id}' 삭제 바구니 등록 완료")
        else:
            print("ℹ️ 신규 행이거나 ID가 없는 행이므로 화면에서만 즉시 삭제합니다.")
        
        # 4. 화면 행 제거 및 합계 갱신 
        self.table_res.removeRow(row)
        self.calculate_total_sum()

    # 인력 투입 UI 초기화
    def init_res_section(self, res_card):
        """인력 투입 영역 초기화 (컬럼 너비 최적화 버전)"""
        res_v_layout = QVBoxLayout(res_card)
        
        # 1. 헤더 영역 구성 (제목 + 총계 + 버튼)
        res_head = QHBoxLayout()
        res_head.addWidget(QLabel("👷 인력투입", styleSheet=MainStyles.LBL_TITLE))
        
        self.lbl_total_sum = QLabel("총계: 0원")
        self.lbl_total_sum.setStyleSheet("font-weight: bold; color: #2E7D32; font-size: 13px; margin-right: 10px;")
        res_head.addStretch()
        res_head.addWidget(self.lbl_total_sum)

        self.btn_add_res = QPushButton("인력추가")
        self.btn_add_res.setStyleSheet(MainStyles.BTN_PRIMARY)
        self.btn_add_res.clicked.connect(self.add_res_row) 

        res_head.addWidget(self.btn_add_res)
        res_head.addWidget(self.btn_save_res)
        res_v_layout.addLayout(res_head)

        # 2. 테이블 객체 생성 (반드시 헤더 설정보다 먼저 와야 함)
        self.table_res = QTableWidget(0, 7)
        self.table_res.setHorizontalHeaderLabels([
            "직원명", "직원추가", "근무시간", "일당", "지불방식", "지불여부", "삭제"
        ])
        self.table_res.setStyleSheet(MainStyles.TABLE)
        res_v_layout.addWidget(self.table_res)

        # 3. [핵심 수정] 컬럼 너비 및 리사이즈 모드 설정
        header = self.table_res.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive) 
        
        # 직원명(0번)은 남는 공간을 다 채우도록 설정
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) 
        
        # 나머지 컬럼들의 고정 너비 지정
        column_widths = {
            1: 50,  #직원추가버튼
            2: 100,  # 근무시간
            3: 100, # 일당
            4: 120,  # 지불방식
            5: 100,  # 지불여부
            6: 100, # 삭제
        }
        
        for col, width in column_widths.items():
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table_res.setColumnWidth(col, width)

        self.table_res.setMinimumWidth(650)

    # 인력 투입 행 추가 및 로직
    def add_res_row(self, data=None):
        """
        [지기님 전용] 바구니 원칙 적용 - 인력 행 추가 및 센서 연결
        0번 컬럼: 상태(INS/ORG/MOD) 고정
        1번~7번 컬럼: 입력 위젯 배치 및 센서 연결
        """
        # 1. 방어 로직 (작업 선택 여부 확인)
        target_work_id = getattr(self, 'selected_work_id', None) or getattr(self, 'current_work_id', None)
        if not target_work_id:
            QMessageBox.warning(self, "알림", "상단의 '작업 목록'에서 작업을 먼저 선택해주세요.")
            return False

        # 2. 행 추가
        row = self.table_res.rowCount()
        self.table_res.insertRow(row)

        # ---------------------------------------------------------
        # 🚨 [Col 0] 상태 표시줄 (바구니 원칙의 핵심!)
        # ---------------------------------------------------------
        status_text = "ORG" if data else "INS"
        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 신규면 "NEW", 기존이면 PK(res_id)를 숨겨둡니다.
        res_id = data.get('res_id') if data else "NEW"
        status_item.setData(Qt.ItemDataRole.UserRole, res_id)
        if data:
            status_item.setData(Qt.ItemDataRole.UserRole + 1, dict(data)) # 원본 백업
        
        self.table_res.setItem(row, 0, status_item)

        # ---------------------------------------------------------
        # 3. 위젯 배치 (1번 컬럼부터 시작!)
        # ---------------------------------------------------------
        
        # [Col 1] 직원명 (콤보박스)
        emp_combo = QComboBox()
        emp_combo.setStyleSheet(MainStyles.COMBO)
        self.refresh_emp_combo(emp_combo) 
        # 📍 센서 연결
        emp_combo.currentIndexChanged.connect(lambda _, r=row: self.check_res_modified(r))
        self.table_res.setCellWidget(row, 1, emp_combo)
        
        # [Col 2] 등록 버튼 (+)
        btn_new_emp = QPushButton("+")
        btn_new_emp.setFixedSize(30, 25)
        btn_new_emp.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 3px;")
        btn_new_emp.clicked.connect(self.open_new_employee_modal) 
        self.table_res.setCellWidget(row, 2, btn_new_emp) 

        # [Col 3] 근무시간
        hour_edit = QLineEdit("0")
        hour_edit.setStyleSheet(MainStyles.INPUT_CENTER)
        hour_edit.textChanged.connect(self.calculate_total_sum)
        # 📍 센서 연결
        hour_edit.textChanged.connect(lambda _, r=row: self.check_res_modified(r))
        self.table_res.setCellWidget(row, 3, hour_edit)

        # [Col 4] 일당 (포맷팅 + 합계계산 + 센서)
        wage_edit = QLineEdit("0")
        wage_edit.setStyleSheet(MainStyles.INPUT_CENTER + "font-weight: bold; color: blue;")
        wage_edit.textChanged.connect(lambda t, e=wage_edit: self.format_comma_and_calculate(e))
        # 📍 센서 연결
        wage_edit.textChanged.connect(lambda _, r=row: self.check_res_modified(r))
        self.table_res.setCellWidget(row, 4, wage_edit)

        # [Col 5] 지불방식
        pay_method_combo = QComboBox()
        pay_method_combo.setStyleSheet(MainStyles.COMBO)
        if hasattr(self, 'asset_accounts') and self.asset_accounts:
            for acct in self.asset_accounts:
                pay_method_combo.addItem(acct['acct_nm'], acct['acct_cd'])
        # 📍 센서 연결
        pay_method_combo.currentIndexChanged.connect(lambda _, r=row: self.check_res_modified(r))
        self.table_res.setCellWidget(row, 5, pay_method_combo)

        # [Col 6] 지불여부 (YES/NO)
        pay_status_combo = QComboBox()
        pay_status_combo.setStyleSheet(MainStyles.COMBO)
        pay_status_combo.addItem("NO", "N")
        pay_status_combo.addItem("YES", "Y")
        # 📍 센서 연결
        pay_status_combo.currentIndexChanged.connect(lambda _, r=row: self.check_res_modified(r))
        self.table_res.setCellWidget(row, 6, pay_status_combo)

        # [Col 7] 삭제 버튼
        btn_del = QPushButton("❌")
        btn_del.setStyleSheet("border:none; color:red;")
        btn_del.clicked.connect(self.remove_res_row)
        btn_del.clicked.connect(self.calculate_total_sum)
        self.table_res.setCellWidget(row, 7, btn_del)

        return True
    
    def get_table_value(self, row, col):
        try:
            widget = self.table_res.cellWidget(row, col)
            if isinstance(widget, QLineEdit):
                txt = widget.text().replace(',', '').strip() # 콤마 제거
                return float(txt) if txt else 0.0
            return 0.0
        except:
            return 0.0   

    def format_comma_and_calculate(self, edit_widget):
        """숫자 입력 시 천 단위 콤마를 적용하고 전체 합계를 계산합니다."""
        text = edit_widget.text().replace(",", "")
        if text.isdigit():
            formatted = "{:,}".format(int(text))
            edit_widget.blockSignals(True)
            edit_widget.setText(formatted)
            edit_widget.blockSignals(False)
        self.calculate_total_sum()

    def calculate_total_sum(self):
        """모든 행의 일당 + 식사비 + 비용을 합산하여 표시합니다."""
        total = 0
        for r in range(self.table_res.rowCount()):
            try:
                # 콤마 제거 후 합산
                wage = int(self.table_res.cellWidget(r,4).text().replace(",", "") or 0)
                #meal = int(self.table_res.cellWidget(r, 3).text().replace(",", "") or 0)
                #other = int(self.table_res.cellWidget(r, 4).text().replace(",", "") or 0)
                total += wage
            except: continue
        self.lbl_total_sum.setText(f"총계: {total:,}원")

    def open_new_employee_modal(self):
        """인력추가 버튼 클릭 시 호출"""
        dialog = EmployeeRegistrationDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            
            # 필수값 검증
            if not data['pt_nm'] or data['base_price'] <= 0:
                QMessageBox.warning(self, "알림", "직원 성함과 기본 일당을 입력해주세요.")
                return

            # DB 저장 시도
            if self.db.add_new_partner_extended(self.current_farm_cd, data, self.my_user_id):
                QMessageBox.information(self, "성공", f"{data['pt_nm']} 직원이 등록되었습니다.")
                self.refresh_all_emp_combos() # 화면 내 모든 콤보박스 갱신
            else:
                QMessageBox.critical(self, "오류", "데이터베이스 저장에 실패했습니다.")

    def refresh_all_emp_combos(self):
        """모든 행의 직원 선택 드롭박스 목록을 최신화합니다."""
        for r in range(self.table_res.rowCount()):
            widget = self.table_res.cellWidget(r, 1)
            if widget:
                combo = widget.findChild(QComboBox)
                if combo: self.refresh_emp_combo(combo)

    def refresh_emp_combo(self, combo):
        """DB에서 직원 목록(m_partner)을 가져와 콤보박스에 채웁니다."""
        current_data = combo.currentData()
        combo.clear()
        partners = self.code_mgr.get_partners() # m_partner 조회
        for p in partners:
            combo.addItem(p['pt_nm'], p['pt_id'])
        if current_data: 
            combo.setCurrentIndex(combo.findData(current_data))
    
    def highlight_current_work_row(self, target_id):
        """저장 후 작업 목록에서 해당 ID의 행을 찾아 다시 선택해줍니다."""
        for r in range(self.table_work.rowCount()):
            item = self.table_work.item(r, 0)
            if item and item.text() == target_id:
                self.table_work.selectRow(r)
                break

    def on_work_selection_changed(self):
        """작업 목록에서 행을 선택하면 해당 작업의 인력 정보를 로드합니다."""
        curr_row = self.table_work.currentRow()
        if curr_row < 0:
            return

        # [수정] 작업 ID 생성 규칙: YYYYMMDD-NN (저장 로직과 동일하게)
        work_dt = self.date_edit.date().toString("yyyyMMdd")
        self.selected_work_id = f"{work_dt}-{curr_row + 1:02d}" 
        
        # 하단 상태바에 현재 선택된 작업 표시 (디버깅용)
        self.window().show_status(f"🔍 작업 ID 선택됨: {self.selected_work_id}")
        self.load_res_data(self.selected_work_id)

    # 통합 데이터 저장
    def save_all_integrated_data(self):
        """
        [최종 완성] 통합 저장 (비고/이슈 저장 버그 수정 완료)
        - 수정사항: work_rmk 가져오는 위젯을 self.txt_issue.toPlainText()로 변경
        - 기상 데이터, 인력, 경비 등 모든 데이터 완벽 저장
        """
        try:
            # 0. 안전장치: 선택된 작업 ID가 없으면 중단
            if not self.selected_work_id:
                QMessageBox.warning(self, "알림", "작업 목록에서 작업을 먼저 선택해주세요.")
                return
            
            all_queries = []
            
            # 1. 날짜(PK) 설정
            work_date = self.date_edit.date().toString("yyyy-MM-dd")
            
            # 요일 구하기
            day_list = ["월", "화", "수", "목", "금", "토", "일"]
            day_idx = self.date_edit.date().dayOfWeek() - 1
            day_of_week = day_list[day_idx]

            # 2. 화면 데이터 수집
            weather_cd = "" 
            if hasattr(self, 'combo_weather'): 
                weather_cd = self.combo_weather.currentData()
            
            # ---------------------------------------------------------
            # [핵심 수정] 비고(work_rmk) 저장 로직 수정
            # ---------------------------------------------------------
            work_rmk = "" 
            # 1순위: self.txt_issue (QTextEdit) 확인
            if hasattr(self, 'txt_issue'):
                work_rmk = self.txt_issue.toPlainText() # .text() 아님!
            # 2순위: 혹시 모를 input_work_content (QLineEdit) 확인
            elif hasattr(self, 'input_work_content'): 
                work_rmk = self.input_work_content.text()

            # 3. 기상 데이터 UI에서 가져오기
            def get_float(key):
                if hasattr(self, 'weather_widgets') and key in self.weather_widgets:
                    text = self.weather_widgets[key].text().strip()
                    if text and text != '-':
                        try:
                            return float(text)
                        except ValueError:
                            return 0.0
                return 0.0

            def get_text(key):
                if hasattr(self, 'weather_widgets') and key in self.weather_widgets:
                    return self.weather_widgets[key].text().strip()
                return ""

            temp_max = get_float("최고온도(℃)")
            temp_min = get_float("최저온도(℃)")
            precip = get_float("강수량(mm)")
            humidity = get_float("습도(%)")
            wind_max = get_float("최고풍속(m/s)")
            wind_min = get_float("최저풍속(m/s)")
            sunshine_hr = get_float("일조량(시간)")
            
            sun_rise = get_text("일출시간")
            sun_set = get_text("일몰시간")
            
            # 4. 마스터 데이터 매핑
            master_data = {
                "work_dt": work_date,          
                "day_of_week": day_of_week,
                "weather_cd": weather_cd,
                "temp_max": temp_max,
                "temp_min": temp_min,
                "precip": precip,
                "humidity": humidity,
                "sun_rise": sun_rise,
                "sun_set": sun_set,
                "sunshine_hr": sunshine_hr,
                "wind_max": wind_max,
                "wind_min": wind_min,
                "work_rmk": work_rmk,          # [수정됨] 정확한 비고 값
                "farm_cd": self.farm_cd,       
                "reg_id": self.my_user_id,     
                "mod_id": self.my_user_id      
            }
            
            # 5. 마스터 저장 쿼리 (UPSERT)
            sql_master = """
                INSERT INTO t_work_master (
                    work_dt, day_of_week, weather_cd, 
                    temp_max, temp_min, precip, humidity, 
                    sun_rise, sun_set, sunshine_hr, wind_max, wind_min, 
                    work_rmk, farm_cd, reg_id, reg_dt
                ) VALUES (
                    :work_dt, :day_of_week, :weather_cd, 
                    :temp_max, :temp_min, :precip, :humidity, 
                    :sun_rise, :sun_set, :sunshine_hr, :wind_max, :wind_min, 
                    :work_rmk, :farm_cd, :reg_id, datetime('now','localtime')
                )
                ON CONFLICT(work_dt) DO UPDATE SET
                    day_of_week = excluded.day_of_week,
                    weather_cd = excluded.weather_cd,
                    temp_max = excluded.temp_max,
                    temp_min = excluded.temp_min,
                    precip = excluded.precip,
                    humidity = excluded.humidity,
                    sun_rise = excluded.sun_rise,
                    sun_set = excluded.sun_set,
                    sunshine_hr = excluded.sunshine_hr,
                    wind_max = excluded.wind_max,
                    wind_min = excluded.wind_min,
                    work_rmk = excluded.work_rmk,
                    mod_id = :mod_id,
                    mod_dt = datetime('now','localtime')
            """
            all_queries.append((sql_master, master_data))

            # 6. 인건비 쿼리 담기
            res_queries = self.save_res_data(self.selected_work_id)
            all_queries.extend(res_queries)

            # 7. 경비 쿼리 담기
            exp_queries = self.save_exp_data(self.selected_work_id)
            all_queries.extend(exp_queries)
            
            # 8. [수정] 작업 목록(Table 3) 저장 - 트랜잭션에 포함
            # 기존 데이터를 지우고 다시 넣는 쿼리를 바구니에 담습니다.
            current_ui_work_ids = [] # 화면에 있는 ID들을 모아서 나중에 없는 놈만 지울 겁니다.

            for r in range(self.table_work.rowCount()):
                mid_cd = self.table_work.cellWidget(r, 1).currentData()
                if not mid_cd: continue

                work_dt_str = self.date_edit.date().toString("yyyyMMdd")
                gen_work_id = f"{work_dt_str}-{r + 1:02d}"
                current_ui_work_ids.append(gen_work_id)
                
                sql_detail = """
                INSERT INTO t_work_detail (
                    work_id, work_dt, farm_cd, work_main_cd, work_mid_cd, 
                    work_loc_id, start_tm, end_tm, status_cd, reg_id, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(work_id) DO UPDATE SET
                    work_mid_cd = excluded.work_mid_cd,
                    work_loc_id = excluded.work_loc_id,
                    start_tm = excluded.start_tm,
                    end_tm = excluded.end_tm,
                    status_cd = excluded.status_cd,
                    mod_id = ?, 
                    mod_dt = datetime('now','localtime')
                """
                params_detail = (
                    gen_work_id, work_date, self.farm_cd, 'WK01', mid_cd,
                    self.table_work.cellWidget(r, 2).currentData(),
                    self.table_work.cellWidget(r, 3).time().toString("HH:mm"),
                    self.table_work.cellWidget(r, 4).time().toString("HH:mm"),
                    self.table_work.cellWidget(r, 5).currentData(),
                    self.my_user_id,
                    self.my_user_id # DO UPDATE SET의 mod_id용
                )
                all_queries.append((sql_detail, params_detail))
            
            # 3. [중요] 화면에서 삭제된 행 처리
            # DB에는 있는데 화면(current_ui_work_ids)에는 없는 녀석들만 골라서 삭제
            if current_ui_work_ids:
                placeholders = ','.join(['?'] * len(current_ui_work_ids))
                sql_cleanup = f"""
                    DELETE FROM t_work_detail 
                    WHERE work_dt = ? AND farm_cd = ? 
                    AND work_id NOT IN ({placeholders})
                """
                all_queries.append((sql_cleanup, [work_date, self.farm_cd] + current_ui_work_ids))

            # 9. 일괄실행
            if all_queries:
                if self.db.execute_transaction(all_queries):
                    # 10. 화면 갱신 (반드시 selected_work_id 사용!)
                    self.load_res_data(self.selected_work_id)
                    if hasattr(self, 'load_work_expenses'):
                        self.load_work_expenses(self.selected_work_id)
                    
                    QMessageBox.information(self, "저장 완료", "영농일지와 장부가 성공적으로 동기화되었습니다! ✅")
                else:
                    raise Exception("트랜잭션 실행 중 오류가 발생했습니다.")
            
        except Exception as e:
            print(f"❌ 저장 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "저장 실패", f"데이터 저장 중 오류가 발생했습니다.\n원인: {str(e)}")

    def save_res_data(self, work_log_id):
        """[혁신 모델] 인건비 저장: 지문(Fingerprint) 엔진 최적화 버전"""
        queries = []
        basket = [] 
        work_date = self.date_edit.date().toString("yyyy-MM-dd")

        # ---------------------------------------------------------------------
        # 1. 삭제된 항목 처리 (삭제 바구니 구성)
        # ---------------------------------------------------------------------
        if hasattr(self, 'removed_res_ids') and self.removed_res_ids:
            for rid in self.removed_res_ids:
                if rid and str(rid).upper() != 'NEW':
                    # 지문 재료: 수단, 상태, 전표번호, 금액, 직원코드(rmk 대용)
                    sql = "SELECT pay_method_cd, pay_status, slip_no, daily_wage, emp_cd FROM t_work_resource WHERE res_id=?"
                    res_list = self.db.fetch_all(sql, (rid,))
                    
                    if res_list:
                        old = res_list[0]
                        orig = {
                            'detail_no': rid,           # 엔진이 식별자로 사용
                            'pay_method_cd': old[0],
                            'pay_status': old[1],
                            'slip_no': old[2],
                            'daily_wage': old[3],
                            'emp_cd': old[4],
                            'acct_cd': 'EX020101'
                        }
                        
                        # 엔진 전달용 DEL 마크 (지문 대조에서 제외되지만 명시적 증거가 됨)
                        basket.append({
                            'status': 'DEL',
                            'orig_data': orig,
                            'acct_cd': 'EX020101',
                            'method': old[0],
                            'amt': 0, 
                            'pay_status': 'N',
                            'rmk': old[4] # 직원코드를 rmk 재료로 사용
                        })
                    
                    queries.append(("DELETE FROM t_work_resource WHERE res_id = ?", (rid,)))

        # ---------------------------------------------------------------------
        # 2. 화면 데이터 처리 (현재 바구니 구성)
        # ---------------------------------------------------------------------
        rows_to_save = []
        for row in range(self.table_res.rowCount()):
            status_item = self.table_res.item(row, 0)
            if not status_item: continue
            
            status = status_item.text()
            res_id = status_item.data(Qt.ItemDataRole.UserRole)
            orig_data = status_item.data(Qt.ItemDataRole.UserRole + 1) or {} 
            if str(res_id).upper() == 'NEW': res_id = None

            # 위젯 추출
            emp_w = self.table_res.cellWidget(row, 1)
            hour_w = self.table_res.cellWidget(row, 3)
            amt_w = self.table_res.cellWidget(row, 4)
            method_w = self.table_res.cellWidget(row, 5)
            pay_st_w = self.table_res.cellWidget(row, 6)
            
            if not emp_w or not amt_w: continue

            # 지문 엔진이 요구하는 표준 키값으로 구성
            item_data = {
                'status': status,
                'id': res_id,
                'orig_data': orig_data,
                'acct_cd': 'EX020101', 
                'method': method_w.currentData(),
                'amt': int(amt_w.text().replace(',', '') or 0),
                'pay_status': pay_st_w.currentData(),
                'rmk': emp_w.currentData(),      # 지문용은 코드값
                'rmk_nm': emp_w.currentText(),   # 📍 전표 표시용은 이름!
                'work_time': float(hour_w.text() or 0),
                'emp_cd': emp_w.currentData()
            }
            basket.append(item_data)
            
            # DB에 실제로 저장(Insert/Update)할 목록
            if status in ['INS', 'MOD']: 
                rows_to_save.append(item_data)

        # ---------------------------------------------------------------------
        # 3. 회계 엔진 호출 (지문 대조)
        # ---------------------------------------------------------------------
        ledger_queries, slip_map = self.acct_mgr.sync_ledger_by_basket(
            'RES', work_log_id, work_date, basket, self.my_user_id
        )
        queries.extend(ledger_queries)

        # ---------------------------------------------------------------------
        # 4. 상세 데이터 DB 저장 (t_work_resource)
        # ---------------------------------------------------------------------
        sql_upsert = """
            INSERT INTO t_work_resource (
                res_id, work_id, farm_cd, trans_dt, emp_cd, man_hour, daily_wage, meal_cost, other_cost,
                pay_method_cd, pay_status, reg_id, slip_no, reg_dt
            ) VALUES (
                :id, :work_id, :farm_cd, :trans_dt, :emp_cd, :work_time, :amt, 0, 0,
                :method, :pay_status, :reg_id, :slip_no, datetime('now','localtime')
            )
            ON CONFLICT(res_id) DO UPDATE SET
                emp_cd=excluded.emp_cd, man_hour=excluded.man_hour, daily_wage=excluded.daily_wage,
                pay_method_cd=excluded.pay_method_cd, pay_status=excluded.pay_status,
                slip_no=excluded.slip_no, mod_id=:reg_id, mod_dt=datetime('now','localtime')
        """
        for item in rows_to_save:
            key = f"{item['acct_cd']}_{item['method']}"
            # 지급 완료된 경우만 엔진에서 받은 전표번호 부여
            item['slip_no'] = slip_map.get(key) if item['pay_status'] == 'Y' else None
            
            item.update({
                'work_id': work_log_id, 
                'farm_cd': self.farm_cd, 
                'trans_dt': work_date, 
                'reg_id': self.my_user_id
            })
            queries.append((sql_upsert, item))

        self.removed_res_ids = [] # 삭제 바구니 비우기
        return queries

    def save_exp_data(self, work_log_id):
        """[혁신 모델] 경비 저장: 지문(Fingerprint) 엔진 최적화 및 에러 방지 버전"""
        queries = []
        basket = [] 
        work_date = self.date_edit.date().toString("yyyy-MM-dd")

        # ---------------------------------------------------------------------
        # 1. 삭제된 경비 처리 (DB 조회 후 지문 재료 구성)
        # ---------------------------------------------------------------------
        # 변수명 주의: removed_res_ids가 아닌 removed_exp_ids를 사용해야 합니다.
        removed_ids = getattr(self, 'removed_exp_ids', [])
        if removed_ids:
            for eid in removed_ids:
                if eid and str(eid).upper() != 'NEW':
                    # 지문 재료 확보: acct_cd, pay_method_cd, pay_status, total_amt, slip_no, item_nm(rmk)
                    sql = "SELECT acct_cd, pay_method_cd, pay_status, total_amt, slip_no, item_nm FROM t_work_expense WHERE exp_id=?"
                    exp_list = self.db.fetch_all(sql, (eid,))
                    
                    if exp_list:
                        old = exp_list[0]
                        orig = {
                            'detail_no': eid,           # 엔진이 식별자로 사용
                            'acct_cd': old[0],
                            'pay_method_cd': old[1],
                            'pay_status': old[2],
                            'slip_no': old[3],
                            'total_amt': old[4],
                            'item_nm': old[5] or ''
                        }
                        
                        # 엔진 전달용 DEL 바구니 (지문 엔진이 '삭제됨'을 인식하게 함)
                        basket.append({
                            'status': 'DEL',
                            'orig_data': orig,
                            'acct_cd': old[0],
                            'method': old[1],
                            'amt': 0, 
                            'pay_status': 'N',
                            'rmk': old[5] or '' # 품목명을 rmk 재료로 사용
                        })
                    
                    queries.append(("DELETE FROM t_work_expense WHERE exp_id = ?", (eid,)))

        # ---------------------------------------------------------------------
        # 2. 화면 경비 데이터 처리 (현재 스냅샷 구성)
        # ---------------------------------------------------------------------
        rows_to_save = []
        for row in range(self.table_exp.rowCount()):
            status_item = self.table_exp.item(row, 0)
            if not status_item: continue
            
            status = status_item.text()
            exp_id = status_item.data(Qt.ItemDataRole.UserRole)
            orig_data = status_item.data(Qt.ItemDataRole.UserRole + 1) or {} 
            if str(exp_id).upper() == 'NEW': exp_id = None

            # 테이블 위젯 안전하게 추출 (인덱스: 2:계정, 3:품목/적요, 4:금액, 7:수단, 8:상태)
            acct_w = self.table_exp.cellWidget(row, 2)
            item_w = self.table_exp.cellWidget(row, 3)
            amt_w = self.table_exp.cellWidget(row, 4)
            method_w = self.table_exp.cellWidget(row, 7)
            pay_st_w = self.table_exp.cellWidget(row, 8)
            
            if not acct_w or not amt_w: continue

            # 지문 엔진 표준 인터페이스에 맞춤
            item_data = {
                'status': status,
                'id': exp_id,
                'orig_data': orig_data,
                'acct_cd': acct_w.currentData(),         # 📍 지문 재료 1
                'method': method_w.currentData(),        # 📍 지문 재료 2
                'amt': int(amt_w.text().replace(',', '') or 0), # 📍 지문 재료 3
                'pay_status': pay_st_w.currentData(),
                'rmk': item_w.text() if hasattr(item_w, 'text') else '', # 📍 지문 재료 4 (품목명)
                'item_nm': item_w.text() if hasattr(item_w, 'text') else ''
            }
            basket.append(item_data)
            
            if status in ['INS', 'MOD']: 
                rows_to_save.append(item_data)

        # ---------------------------------------------------------------------
        # 3. 회계 엔진 호출 (지문 대조)
        # ---------------------------------------------------------------------
        ledger_queries, slip_map = self.acct_mgr.sync_ledger_by_basket(
            'EXP', work_log_id, work_date, basket, self.my_user_id
        )
        queries.extend(ledger_queries)

        # ---------------------------------------------------------------------
        # 4. 상세 데이터 DB 저장 (t_work_expense)
        # ---------------------------------------------------------------------
        sql_upsert = """
            INSERT INTO t_work_expense (
                exp_id, work_id, farm_cd, trans_dt, acct_cd, item_nm, qty, unit_price, total_amt, 
                pay_method_cd, pay_status, reg_id, slip_no, reg_dt
            ) VALUES (
                :id, :work_id, :farm_cd, :trans_dt, :acct_cd, :item_nm, 1, :amt, :amt, 
                :method, :pay_status, :reg_id, :slip_no, datetime('now','localtime')
            )
            ON CONFLICT(exp_id) DO UPDATE SET
                acct_cd=excluded.acct_cd, item_nm=excluded.item_nm, total_amt=excluded.total_amt,
                pay_method_cd=excluded.pay_method_cd, pay_status=excluded.pay_status,
                slip_no=excluded.slip_no, mod_id=:reg_id, mod_dt=datetime('now','localtime')
        """
        for item in rows_to_save:
            key = f"{item['acct_cd']}_{item['method']}"
            # 지급 완료('Y')인 경우에만 전표 매칭
            item['slip_no'] = slip_map.get(key) if item['pay_status'] == 'Y' else None
            
            item.update({
                'work_id': work_log_id, 
                'farm_cd': self.farm_cd, 
                'trans_dt': work_date, 
                'reg_id': self.my_user_id
            })
            queries.append((sql_upsert, item))

        self.removed_exp_ids = [] # 삭제 바구니 초기화
        return queries