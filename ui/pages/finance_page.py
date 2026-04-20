import sys
from pathlib import Path
for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt

class FinancePage(QWidget):
    def __init__(self, db_manager, session_data):
        super().__init__()
        self.db = db_manager
        self.session = session_data
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        header = QLabel("💰 미수금 및 미지급금 정산 관리")
        header.setStyleSheet("font-weight: bold; margin: 10px;")
        layout.addWidget(header)

        # 1. 상단 필터
        filter_layout = QHBoxLayout()
        self.type_filter = QComboBox()
        self.type_filter.addItems(["전체 보기", "매출 미수금 (받을 돈)", "인건비 미지급 (줄 돈)"])
        self.search_btn = QPushButton("내역 조회")
        self.search_btn.clicked.connect(self.load_unsettled_data)
        
        filter_layout.addWidget(self.type_filter)
        filter_layout.addWidget(self.search_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 2. 메인 콘텐츠 (좌: 리스트, 우: 정산 입력)
        content_layout = QHBoxLayout()

        # 미정산 내역 테이블
        self.ledger_table = QTableWidget(0, 5)
        self.ledger_table.setHorizontalHeaderLabels(["번호", "날짜", "항목", "발생금액", "현재잔액"])
        self.ledger_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ledger_table.itemClicked.connect(self.prepare_settlement)
        content_layout.addWidget(self.ledger_table, 7) # 비중 7

        # 정산 입력 폼
        settle_group = QGroupBox("정산 실행")
        settle_layout = QFormLayout()
        
        self.sel_id = QLineEdit(); self.sel_id.setReadOnly(True)
        self.target_amt = QLineEdit(); self.target_amt.setReadOnly(True)
        self.pay_amt = QSpinBox(); self.pay_amt.setRange(0, 10000000); self.pay_amt.setSingleStep(1000)
        self.pay_method = QComboBox(); self.pay_method.addItems(["계좌이체", "현금", "카드"])
        
        settle_layout.addRow("전표번호:", self.sel_id)
        settle_layout.addRow("남은금액:", self.target_amt)
        settle_layout.addRow("실제정산액:", self.pay_amt)
        settle_layout.addRow("결제수단:", self.pay_method)
        
        self.execute_btn = QPushButton("정산 처리 (장부 반영)")
        self.execute_btn.setStyleSheet("height: 40px; background-color: #1976D2; color: white; font-weight: bold;")
        self.execute_btn.clicked.connect(self.execute_settlement)
        settle_layout.addRow(self.execute_btn)
        
        settle_group.setLayout(settle_layout)
        content_layout.addWidget(settle_group, 3) # 비중 3

        layout.addLayout(content_layout)
        self.setLayout(layout)
        self.load_unsettled_data()

    def load_unsettled_data(self):
        """t_ledger에서 아직 잔액(rem_amt)이 남은 내역 조회"""
        query = f"SELECT * FROM t_ledger WHERE farm_cd = '{self.session['farm_cd']}' AND rem_amt != 0"
        
        # 필터링 로직 (생략 가능)
        results = self.db.execute_query(query)
        self.ledger_table.setRowCount(len(results))
        for i, row in enumerate(results):
            self.ledger_table.setItem(i, 0, QTableWidgetItem(str(row['ledger_id'])))
            self.ledger_table.setItem(i, 1, QTableWidgetItem(row['trans_dt']))
            self.ledger_table.setItem(i, 2, QTableWidgetItem(row['trans_type_cd']))
            self.ledger_table.setItem(i, 3, QTableWidgetItem(f"{row['acc_amt']:,}"))
            self.ledger_table.setItem(i, 4, QTableWidgetItem(f"{row['rem_amt']:,}"))

    def prepare_settlement(self, item):
        row = item.row()
        self.sel_id.setText(self.ledger_table.item(row, 0).text())
        self.target_amt.setText(self.ledger_table.item(row, 4).text().replace(",", ""))
        self.pay_amt.setValue(abs(int(self.target_amt.text())))

    def execute_settlement(self):
        """실제 정산 처리: t_ledger의 cash_amt 업데이트 및 rem_amt 계산"""
        lid = self.sel_id.text()
        amt = self.pay_amt.value()
        
        if not lid: return

        # 실제로는 UPDATE 쿼리로 rem_amt를 줄여주는 로직이 들어갑니다.
        # 예시: UPDATE t_ledger SET cash_amt = cash_amt + ?, rem_amt = rem_amt - ? WHERE ledger_id = ?
        try:
            cur = self.db.conn.cursor()
            cur.execute("UPDATE t_ledger SET cash_amt = cash_amt + ?, rem_amt = rem_amt - ? WHERE ledger_id = ?", (amt, amt, lid))
            self.db.conn.commit()
            QMessageBox.information(self, "완료", "정산 처리가 완료되었습니다.")
            self.load_unsettled_data()
        except Exception as e:
            print(f"정산 오류: {e}")