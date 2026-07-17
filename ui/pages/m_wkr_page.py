import sys
import os
import sqlite3
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QLabel, QPushButton, QLineEdit, 
                             QHeaderView, QMessageBox, QFrame, QApplication)
from PyQt6.QtCore import Qt

class WorkerPage(QWidget):
    def __init__(self):
        super().__init__()
        # DB 경로 설정 (근본 구조 반영)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(base_dir, "orchard_platform_v10.db")
        
        # 농장 ID (현재는 기본값 1번 농장으로 설정, 추후 확장 가능)
        self.current_farm_id = 1
        
        self.init_ui()
        self.load_worker_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        # 1. 제목 영역
        header = QLabel("👤 인력 마스터 관리")
        header.setStyleSheet("font-weight: bold; color: #2c3e50; margin-bottom: 20px;")
        layout.addWidget(header)

        # 2. 입력 폼 영역 (카드 스타일)
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 10px; padding: 15px;")
        form_layout = QHBoxLayout(form_frame)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("인부 성명")
        self.edit_name.setFixedWidth(150)

        self.edit_pay = QLineEdit()
        self.edit_pay.setPlaceholderText("기본 일당 (숫자만)")
        self.edit_pay.setFixedWidth(150)

        btn_add = QPushButton("➕ 인력 등록")
        btn_add.setStyleSheet("background-color: #1abc9c; color: white; padding: 8px 15px; font-weight: bold;")
        btn_add.clicked.connect(self.add_worker)

        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self.load_worker_data)

        form_layout.addWidget(QLabel("성명:"))
        form_layout.addWidget(self.edit_name)
        form_layout.addWidget(QLabel("일당:"))
        form_layout.addWidget(self.edit_pay)
        form_layout.addSpacing(20)
        form_layout.addWidget(btn_add)
        form_layout.addWidget(btn_refresh)
        form_layout.addStretch()

        layout.addWidget(form_frame)

        # 3. 인력 목록 (TableWidget)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["인력 ID", "성명", "기본 일당", "비고"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("QTableWidget { gridline-color: #dcdde1; }")
        layout.addWidget(self.table)

        # 하단 버튼 (삭제 등)
        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("🗑️ 선택 삭제")
        btn_delete.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")
        btn_delete.clicked.connect(self.delete_worker)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_delete)
        layout.addLayout(btn_layout)

    def load_worker_data(self):
        """DB에서 인력 목록을 불러와 테이블에 표시"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 근본 구조 m_wkr 테이블 조회
                cursor.execute("SELECT wkr_id, wkr_nm, wkr_pay FROM m_wkr WHERE farm_id = ?", (self.current_farm_id,))
                rows = cursor.fetchall()
                
                self.table.setRowCount(len(rows))
                for i, row in enumerate(rows):
                    for j, val in enumerate(row):
                        item = QTableWidgetItem(str(val))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.table.setItem(i, j, item)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"데이터 로드 실패: {e}")

    def add_worker(self):
        """인력 신규 등록"""
        name = self.edit_name.text().strip()
        pay = self.edit_pay.text().strip()

        if not name or not pay:
            QMessageBox.warning(self, "경고", "성명과 일당을 모두 입력하세요.")
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO m_wkr (farm_id, wkr_nm, wkr_pay) 
                    VALUES (?, ?, ?)
                """, (self.current_farm_id, name, int(pay)))
                conn.commit()
                
                self.edit_name.clear()
                self.edit_pay.clear()
                self.load_worker_data()
                QMessageBox.information(self, "완료", f"{name} 님이 등록되었습니다.")
        except ValueError:
            QMessageBox.warning(self, "경고", "일당은 숫자만 입력 가능합니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"등록 실패: {e}")

    def delete_worker(self):
        """선택된 인력 삭제"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "경고", "삭제할 항목을 선택하세요.")
            return

        wkr_id = self.table.item(current_row, 0).text()
        wkr_nm = self.table.item(current_row, 1).text()

        reply = QMessageBox.question(self, "삭제 확인", f"[{wkr_nm}] 인력을 삭제하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM m_wkr WHERE wkr_id = ?", (wkr_id,))
                    conn.commit()
                    self.load_worker_data()
            except Exception as e:
                QMessageBox.critical(self, "오류", f"삭제 실패: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WorkerPage()
    window.show()
    sys.exit(app.exec())