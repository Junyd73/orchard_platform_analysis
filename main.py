import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDate, Qt, QTimer
from core.db_manager import DBManager
from ui.styles import make_app_font
from ui.pages.login_page import LoginPage
from app.main_app import MainApp

class StartupController:
    def __init__(self):
        self.db = DBManager()
        self.show_login()

    def show_login(self):
        # 1. 로그인 화면 생성5
        self.login_win = LoginPage(self.db)
        
        # 2. 로그인창 중앙 정렬 및 크기 설정
        self.login_win.resize(600   , 750)
        screen = QApplication.primaryScreen().availableGeometry()
        qr = self.login_win.frameGeometry()
        qr.moveCenter(screen.center())
        self.login_win.move(qr.topLeft())
        # 3. 로그인 성공 시 메인 화면으로 전환 신호 연결
        self.login_win.login_success.connect(self.start_main_app)
        self.login_win.show()

    def start_main_app(self, session_data):
        # 4. 메인 앱 생성 및 실행
        self.main_app = MainApp(self.db, session_data)
        self.main_app.show() # 이 부분이 있어야 메인 화면이 뜹니다!
        self.login_win.close() # 로그인창 닫기

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(make_app_font(18))  # 돋보기 방지 (유효 point size 보장)
    controller = StartupController()
    sys.exit(app.exec())