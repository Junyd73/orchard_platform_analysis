import sys
from pathlib import Path
for _d in Path(__file__).resolve().parents:
    if (_d / "path_setup.py").is_file():
        sys.path.insert(0, str(_d))
        break
import path_setup  # noqa: E402
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
import datetime

class ConfigPage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        
        self.my_farm_cd = self.session.get('farm_cd', 'OR001')
        self.my_user_id = self.session.get('user_id', 'ADMIN')
        
        self.init_ui()
        QTimer.singleShot(50, self.refresh_data)

    def init_ui(self):
        self.setStyleSheet("background-color: #FDFBF7;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(25)

        header = QLabel("시스템 기초 정보 설정")
        header.setStyleSheet("font-weight: 900; color: #2D5A27; letter-spacing: -1.2px;")
        main_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(0)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; }")

        self.table_main = self.create_modern_table()
        self.group_main = self.create_card_section("대분류 관리", self.table_main, self.on_add_main, self.on_mod_main, self.on_del_main)
        splitter.addWidget(self.group_main)

        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 20, 0, 0)
        bottom_layout.setSpacing(25)

        self.table_mid = self.create_modern_table()
        self.table_sub = self.create_modern_table()
        
        bottom_layout.addWidget(self.create_card_section("중분류 그룹", self.table_mid, self.on_add_mid, self.on_mod_mid, self.on_del_mid))
        bottom_layout.addWidget(self.create_card_section("상세 소분류", self.table_sub, self.on_add_sub, self.on_mod_sub, self.on_del_sub))
        
        splitter.addWidget(bottom_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        self.table_main.itemClicked.connect(self.on_main_selected)
        self.table_mid.itemClicked.connect(self.on_mid_selected)

    def create_modern_table(self):
        """[디자인 표준] 테이블 폰트 상세 설정"""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["CODE", "명칭", "사용여부"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFrameShape(QFrame.Shape.NoFrame)
        
        # [지기님 요청 반영] 
        # 1. 헤더: 사이즈 2 크게 (11px -> 13px) 및 Bold(진하게) 적용
        # 2. 내용: 사이즈 1 작게 (14px -> 13px) 적용
        table.setStyleSheet("""
            QTableWidget { 
                background-color: white; 
                color: #333;
                alternate-background-color: #FBFBFA;
            }
            QTableWidget::item { padding: 12px; }
            QTableWidget::item:selected { background-color: #F1F4F1; color: #2D5A27; font-weight: bold; }
            QHeaderView::section { 
                background-color: transparent; 
                color: #5D4037; 
                font-weight: bold;            /* [요청] 헤더 진하게(Bold) */
                height: 40px; 
                border: none; 
                border-bottom: 2px solid #E0DED9;
                padding-left: 10px;
                text-align: left;
            }
        """)
        return table

    def create_card_section(self, title, table, add_f, mod_f, del_f):
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: white; border: 1px solid #EEE; border-radius: 20px; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 25)

        toolbar = QHBoxLayout()
        t_label = QLabel(title)
        t_label.setStyleSheet("font-weight: 800; color: #2D5A27; border: none;")
        toolbar.addWidget(t_label)
        toolbar.addStretch()

        btn_data = [
            ("신규", add_f, "#4A7C59"),
            ("저장", mod_f, "#F1F4F1"),
            ("삭제", del_f, "#FFF0F0")
        ]
        
        for txt, func, color in btn_data:
            btn = QPushButton(txt)
            btn.setFixedWidth(60) # 폰트가 커짐에 따라 가로폭 소폭 확장
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(func)
            
            text_color = "white" if txt == "신규" else ("#2D5A27" if txt == "저장" else "#CD6155")
            
            # [지기님 요청 반영] 버튼 내 폰트 사이즈 1 크게 (12px -> 13px)
            btn.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: {color}; 
                    color: {text_color}; 
                    border-radius: 16px; 
                    font-weight: bold; 
                    border: none;
                }}
                QPushButton:hover {{ background-color: #E0E0E0; }}
            """)
            toolbar.addWidget(btn)

        layout.addLayout(toolbar)
        layout.addWidget(table)
        return card

    # (데이터 로드 및 이벤트 로직은 동일...)
    def refresh_data(self):
        self.my_farm_cd = self.session.get('farm_cd', 'OR001')
        for table in [self.table_main, self.table_mid, self.table_sub]:
            table.setRowCount(0)
        self.load_main_codes()

    def load_main_codes(self):
        sql = "SELECT code_cd, code_nm, use_yn FROM m_common_code WHERE farm_cd = ? AND parent_cd is null ORDER BY code_cd"
        rows = self.db.execute_query(sql, (self.my_farm_cd,))
        for r in rows: self.add_row_to_table(self.table_main, *r)

    def on_main_selected(self, item):
        self.current_main_cd = self.table_main.item(item.row(), 0).text()
        self.table_mid.setRowCount(0); self.table_sub.setRowCount(0)
        sql = "SELECT code_cd, code_nm, use_yn FROM m_common_code WHERE farm_cd = ? AND parent_cd = ? ORDER BY code_cd"
        for r in self.db.execute_query(sql, (self.my_farm_cd, self.current_main_cd)):
            self.add_row_to_table(self.table_mid, *r)

    def on_mid_selected(self, item):
        self.current_mid_cd = self.table_mid.item(item.row(), 0).text()
        self.table_sub.setRowCount(0)
        sql = "SELECT code_cd, code_nm, use_yn FROM m_common_code WHERE farm_cd = ? AND parent_cd = ? ORDER BY code_cd"
        for r in self.db.execute_query(sql, (self.my_farm_cd, self.current_mid_cd)):
            self.add_row_to_table(self.table_sub, *r)

    def add_row_to_table(self, table, code, name, use_yn):
        row = table.rowCount(); table.insertRow(row)
        it_code = QTableWidgetItem(str(code))
        it_code.setForeground(QColor("#999"))
        # [핵심] ItemIsEditable 플래그를 제외하여 수정 불가 옵션 적용
        it_code.setFlags(it_code.flags() ^ Qt.ItemFlag.ItemIsEditable)
        it_name = QTableWidgetItem(str(name))
        table.setItem(row, 0, it_code)
        table.setItem(row, 1, it_name)
        combo = QComboBox(); combo.addItems(["Y", "N"]); combo.setCurrentText(use_yn)
        combo.setStyleSheet("border: 1px solid #EEE; border-radius: 10px; padding-left: 5px;")
        table.setCellWidget(row, 2, combo)

    def on_add_main(self):
        """[최종] 대분류 코드 생성 및 저장 후 즉시 선택 상태로 전환"""
        prefix, ok = QInputDialog.getText(self, "신규 분류", "식별자 2자(예: WT):")
        if ok and prefix:
            prefix = prefix.strip().upper()[:2]
            sql = "SELECT MAX(code_cd) FROM m_common_code WHERE farm_cd = ? AND code_cd LIKE ?"
            res = self.db.execute_query(sql, (self.my_farm_cd, f"{prefix}%"))
            
            if res and res[0][0]:
                max_v = res[0][0]
                try:
                    num_part = int(max_v[2:]) 
                    new_code = f"{prefix}{num_part + 1:02d}"
                except ValueError:
                    new_code = f"{prefix}01"
            else:
                new_code = f"{prefix}01"

            # 1. DB 저장 및 테이블 리프레시
            self.save_code_to_db(new_code, "새 분류", None)
            
            # 2. [중요] 저장 후 생성된 최하단 행을 자동으로 선택 (Focus 부여)
            last_row = self.table_main.rowCount() - 1
            if last_row >= 0:
                self.table_main.selectRow(last_row) # 행 하이라이트
                self.table_main.setCurrentCell(last_row, 0) # 시스템 포커스 부여
                
                # 3. 중분류 추가에 필요한 기준 변수(current_main_cd) 즉시 갱신
                self.current_main_cd = new_code 
                
            self.window().show_status(f"대분류 {new_code}가 저장되었습니다. 이제 바로 중분류를 추가할 수 있습니다.")

    def save_code_to_db(self, code, name, parent):
        """[수정] DB 저장 시 NULL값 처리 보완"""
        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # parent가 None이면 DB에 NULL로 들어감
        sql = """INSERT INTO m_common_code (farm_cd, code_cd, code_nm, parent_cd, use_yn, reg_id, reg_dt, mod_id, mod_dt) 
                 VALUES (?, ?, ?, ?, 'Y', ?, ?, ?, ?)"""
        
        try:
            self.db.execute_query(sql, (self.my_farm_cd, code, name, parent, self.my_user_id, dt, self.my_user_id, dt))
            # [변경] 무조건 refresh_data()를 호출하지 않고 수동 업데이트
            if parent is None:
                # 대분류 추가 시에만 전체 리프레시
                self.refresh_data()
            elif len(parent) == 4:
                # 중분류 추가 시: 대분류 선택 상태를 유지하며 중분류 테이블만 갱신
                self.load_mid_codes(parent)
            elif len(parent) == 8:
                # 소분류 추가 시: 중분류 선택 상태를 유지하며 소분류 테이블만 갱신
                self.load_sub_codes(parent)

            self.window().show_status(f"코드 {code}가 생성되었습니다.")
        except Exception as e:
            self.window().show_status(f"저장 중 오류: {str(e)}", is_error=True)
    
    def load_mid_codes(self, main_cd):
        """중분류 테이블만 새로고침"""
        self.table_mid.setRowCount(0)
        self.table_sub.setRowCount(0)
        sql = "SELECT code_cd, code_nm, use_yn FROM m_common_code WHERE farm_cd = ? AND parent_cd = ? ORDER BY code_cd"
        for r in self.db.execute_query(sql, (self.my_farm_cd, main_cd)):
            self.add_row_to_table(self.table_mid, *r)

    def load_sub_codes(self, mid_cd):
        """소분류 테이블만 새로고침"""
        self.table_sub.setRowCount(0)
        sql = "SELECT code_cd, code_nm, use_yn FROM m_common_code WHERE farm_cd = ? AND parent_cd = ? ORDER BY code_cd"
        for r in self.db.execute_query(sql, (self.my_farm_cd, mid_cd)):
            self.add_row_to_table(self.table_sub, *r)

    # 기존 이벤트 함수는 추출한 함수를 호출하도록 변경
    def on_main_selected(self, item):
        self.current_main_cd = self.table_main.item(item.row(), 0).text()
        self.load_mid_codes(self.current_main_cd)

    def on_mid_selected(self, item):
        self.current_mid_cd = self.table_mid.item(item.row(), 0).text()
        self.load_sub_codes(self.current_mid_cd)

    def on_add_mid(self):
        # 1. 현재 선택된 대분류 행 확인
        row = self.table_main.currentRow()
        if row < 0:
            self.window().show_status("중분류를 추가할 대분류를 선택해주세요.", is_error=True)
            return

        # 2. 선택된 행에서 대분류 코드 직접 추출 (변수 미갱신 대비)
        main_cd = self.table_main.item(row, 0).text()
        
        # 3. 신규 코드 생성 로직 (지기님의 규칙 반영)
        sql = "SELECT MAX(code_cd) FROM m_common_code WHERE farm_cd = ? AND parent_cd = ?"
        res = self.db.execute_query(sql, (self.my_farm_cd, main_cd))
        
        if res and res[0][0]:
            last_v = res[0][0]
            # 예: WT010100 -> '01' 추출 후 +1
            new_num = int(last_v[len(main_cd):len(main_cd)+2]) + 1
            new_code = f"{main_cd}{new_num:02d}00"
        else:
            new_code = f"{main_cd}0100"

        # 4. DB 저장
        self.save_code_to_db(new_code, "새 그룹", main_cd)
        self.window().show_status(f"대분류 [{main_cd}] 하위에 중분류가 추가되었습니다.")

    def on_add_sub(self):
        if not self.current_mid_cd: return
        p_prefix = self.current_mid_cd[:6]
        sql = "SELECT MAX(code_cd) FROM m_common_code WHERE farm_cd = ? AND parent_cd = ?"
        res = self.db.execute_query(sql, (self.my_farm_cd, self.current_mid_cd))
        last_v = res[0][0] if res and res[0][0] else f"{p_prefix}00"
        new_code = f"{p_prefix}{int(last_v[6:8]) + 1:02d}"
        self.save_code_to_db(new_code, "새 상세항목", self.current_mid_cd)

    def on_mod_main(self): self.generic_modify(self.table_main)
    def on_mod_mid(self): self.generic_modify(self.table_mid)
    def on_mod_sub(self): self.generic_modify(self.table_sub)

    def generic_modify(self, table):
        row = table.currentRow()
        if row < 0: 
            self.window().show_status("수정할 항목을 선택해주세요.", is_error=True)
            return
            
        code, name = table.item(row, 0).text(), table.item(row, 1).text()
        use_yn = table.cellWidget(row, 2).currentText()
        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            sql = "UPDATE m_common_code SET code_nm = ?, use_yn = ?, mod_id = ?, mod_dt = ? WHERE farm_cd = ? AND code_cd = ?"
            self.db.execute_query(sql, (name, use_yn, self.my_user_id, dt, self.my_farm_cd, code))
            
            # [수정] 메인 앱 하단바에 성공 메시지 전송
            self.window().show_status(f"'{name}' 설정이 성공적으로 저장되었습니다.")
        except Exception as e:
            # [수정] 에러 발생 시 상태바에 빨간색 경고 출력
            self.window().show_status(f"저장 중 오류: {str(e)}", is_error=True)
        
    def on_del_main(self): self.generic_delete(self.table_main)
    def on_del_mid(self): self.generic_delete(self.table_mid)
    def on_del_sub(self): self.generic_delete(self.table_sub)

    def generic_delete(self, table):
        row = table.currentRow()
        if row < 0: 
            self.window().show_status("삭제할 항목을 선택해주세요.", is_error=True)
            return
            
        code = table.item(row, 0).text()
        
        try:
            check = self.db.execute_query("SELECT COUNT(*) FROM m_common_code WHERE farm_cd = ? AND parent_cd = ?", (self.my_farm_cd, code))
            if check[0][0] > 0:
                self.window().show_status("하위 항목이 존재하여 삭제할 수 없습니다.", is_error=True)
                return
                
            if QMessageBox.question(self, "확인", "정말 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
                self.db.execute_query("DELETE FROM m_common_code WHERE farm_cd = ? AND code_cd = ?", (self.my_farm_cd, code))
                table.removeRow(row)
                self.window().show_status("항목이 삭제되었습니다.")
        except Exception as e:
            self.window().show_status(f"삭제 중 오류: {str(e)}", is_error=True)