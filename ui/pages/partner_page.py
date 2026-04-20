from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt

class PartnerPage(QWidget):
    def __init__(self, db_manager, session_data):
        super().__init__()
        self.db = db_manager
        self.session = session_data
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        header = QLabel("👥 인력 및 거래처 관리")
        header.setStyleSheet("font-weight: bold; margin: 10px;")
        layout.addWidget(header)

        # 상단 입력부와 하단 리스트부 분할
        main_split = QVBoxLayout()

        # 1. 입력 폼 (입력 효율을 위해 가로로 배치)
        input_group = QGroupBox("신규 파트너 등록")
        form_layout = QGridLayout()

        self.pt_type = QComboBox()
        self.pt_type.addItems(["WORKER (인력)", "CLIENT (고객)", "BIZ (도매처)"])
        
        self.pt_nm = QLineEdit()
        self.pt_tel = QLineEdit()
        self.base_price = QSpinBox()
        self.base_price.setRange(0, 1000000)
        self.base_price.setSingleStep(10000)
        self.base_price.setSuffix(" 원")

        form_layout.addWidget(QLabel("구분:"), 0, 0)
        form_layout.addWidget(self.pt_type, 0, 1)
        form_layout.addWidget(QLabel("성명/업체명:"), 0, 2)
        form_layout.addWidget(self.pt_nm, 0, 3)
        form_layout.addWidget(QLabel("연락처:"), 1, 0)
        form_layout.addWidget(self.pt_tel, 1, 1)
        form_layout.addWidget(QLabel("기본단가:"), 1, 2)
        form_layout.addWidget(self.base_price, 1, 3)

        self.save_btn = QPushButton("파트너 저장")
        self.save_btn.setStyleSheet("background-color: #0288D1; color: white; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_partner)
        form_layout.addWidget(self.save_btn, 1, 4)

        input_group.setLayout(form_layout)
        layout.addWidget(input_group)

        # 2. 파트너 리스트 테이블
        self.pt_table = QTableWidget()
        self.pt_table.setColumnCount(5)
        self.pt_table.setHorizontalHeaderLabels(["ID", "구분", "이름", "연락처", "기본단가"])
        self.pt_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.pt_table)

        self.setLayout(layout)
        self.load_partners()

    def load_partners(self):
        """등록된 파트너 목록 로드"""
        query = "SELECT * FROM m_partner WHERE farm_cd = ? ORDER BY pt_id DESC"
        results = self.db.execute_query(query, (self.session['farm_cd'],))
        
        self.pt_table.setRowCount(len(results))
        for i, row in enumerate(results):
            self.pt_table.setItem(i, 0, QTableWidgetItem(str(row['pt_id'])))
            self.pt_table.setItem(i, 1, QTableWidgetItem(row['pt_type_cd']))
            self.pt_table.setItem(i, 2, QTableWidgetItem(row['pt_nm']))
            self.pt_table.setItem(i, 3, QTableWidgetItem(row['pt_tel']))
            self.pt_table.setItem(i, 4, QTableWidgetItem(f"{row['base_price']:,}원"))

    def save_partner(self):
        """DB에 파트너 저장"""
        p_type = self.pt_type.currentText().split(" ")[0]
        p_nm = self.pt_nm.text()
        p_tel = self.pt_tel.text()
        p_price = self.base_price.value()

        if not p_nm:
            QMessageBox.warning(self, "오류", "이름을 입력하세요.")
            return

        query = """
            INSERT INTO m_partner (farm_cd, pt_type_cd, pt_nm, pt_tel, base_price, worker_type_cd, reg_id)
            VALUES (?, ?, ?, ?, ?, 'EMP', ?)
        """
        params = (self.session['farm_cd'], p_type, p_nm, p_tel, p_price, self.session['user_id'])
        
        # 실제 저장 로직 (DBManager의 로직 활용)
        cur = self.db.conn.cursor()
        cur.execute(query, params)
        self.db.conn.commit()
        
        QMessageBox.information(self, "성공", f"{p_nm} 파트너가 등록되었습니다.")
        self.load_partners()
        self.pt_nm.clear()
        self.pt_tel.clear()