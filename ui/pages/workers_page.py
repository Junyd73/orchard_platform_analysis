import sqlite3
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QLineEdit, 
                             QFormLayout, QFrame, QMessageBox, QHeaderView)

class WorkersPage(QWidget):
    def __init__(self):
        super().__init__()
        self.db_name = "orchard_platform_v10.db" # 1일차에 만든 DB 파일명
        self.init_ui()
        self.load_data() # 화면이 열릴 때 기존 인력 데이터를 불러옴

    def init_ui(self):
        layout = QHBoxLayout()

        # --- 좌측: 등록된 인력 리스트 ---
        list_layout = QVBoxLayout()
        list_layout.addWidget(QLabel("📋 등록된 인력 명단 (마스터)"))
        
        self.worker_table = QTableWidget(0, 3)
        self.worker_table.setHorizontalHeaderLabels(["이름", "연락처", "기본 일당"])
        self.worker_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        list_layout.addWidget(self.worker_table)
        
        layout.addLayout(list_layout, 2)

        # --- 우측: 신규 등록 및 수정 폼 ---
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        form_layout = QFormLayout()
        
        form_layout.addRow(QLabel("<h3>👤 인력 마스터 등록</h3>"))
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.rate_input = QLineEdit()
        self.rate_input.setPlaceholderText("예: 150000")
        self.bank_input = QLineEdit()
        self.account_input = QLineEdit()
        self.remark_input = QLineEdit()

        form_layout.addRow("성명 (필수):", self.name_input)
        form_layout.addRow("연락처:", self.phone_input)
        form_layout.addRow("기본 일당:", self.rate_input)
        form_layout.addRow("은행명:", self.bank_input)
        form_layout.addRow("계좌번호:", self.account_input)
        form_layout.addRow("비고:", self.remark_input)

        # 저장 버튼 및 이벤트 연결
        self.save_worker_btn = QPushButton("💾 인력 정보 DB 저장")
        self.save_worker_btn.setFixedHeight(40)
        self.save_worker_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        self.save_worker_btn.clicked.connect(self.save_worker) # 클릭 시 저장 함수 실행
        
        form_layout.addRow(self.save_worker_btn)

        form_frame.setLayout(form_layout)
        layout.addWidget(form_frame, 1)

        self.setLayout(layout)

    def load_data(self):
        """DB에서 인력 명단을 가져와 그리드(Table)에 표시 (SELECT)"""
        try:
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            cur.execute("SELECT name, contact, daily_rate FROM workers ORDER BY name")
            rows = cur.fetchall()
            
            self.worker_table.setRowCount(0) # 기존 리스트 초기화
            for row_data in rows:
                row = self.worker_table.rowCount()
                self.worker_table.insertRow(row)
                for column, data in enumerate(row_data):
                    self.worker_table.setItem(row, column, QTableWidgetItem(str(data)))
            
            conn.close()
        except Exception as e:
            print(f"데이터 로드 오류: {e}")

    def save_worker(self):
        """입력한 내용을 DB에 저장 (INSERT)"""
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        rate = self.rate_input.text().strip() or "0"
        bank = self.bank_input.text().strip()
        account = self.account_input.text().strip()
        remark = self.remark_input.text().strip()

        # 필수 입력 체크
        if not name:
            QMessageBox.warning(self, "입력 오류", "인부 성명은 필수입니다.")
            return

        try:
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            
            # SQL 실행 (1일차에 만든 테이블 구조 기준)
            sql = """
                INSERT INTO workers (name, contact, daily_rate, bank_name, account_number, remarks)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cur.execute(sql, (name, phone, int(rate), bank, account, remark))
            
            conn.commit() # 파워빌더의 COMMIT과 동일
            conn.close()

            QMessageBox.information(self, "완료", f"{name} 님이 등록되었습니다.")
            
            # 입력창 초기화 및 리스트 새로고침
            self.clear_inputs()
            self.load_data()
            
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "오류", "이미 등록된 이름입니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 중 오류 발생: {e}")

    def clear_inputs(self):
        """입력 필드 초기화"""
        self.name_input.clear()
        self.phone_input.clear()
        self.rate_input.clear()
        self.bank_input.clear()
        self.account_input.clear()
        self.remark_input.clear()