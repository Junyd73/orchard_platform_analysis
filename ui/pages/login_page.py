from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from ui.styles import make_app_font

class LoginPage(QWidget):
    login_success = pyqtSignal(dict)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("과수원관리플랫폼v1.0 - 로그인")
        self.setStyleSheet("background-color: #FDFBF7;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(500)
        card.setStyleSheet("""
            QFrame { background-color: white; border-radius: 20px; border: 1px solid #E0DED9; }
            QLabel { font-weight: bold; color: #444444; border: none; }
            QLineEdit { padding: 15px; border: 2px solid #E0E0E0; border-radius: 10px; }
            QPushButton { font-weight: bold; padding: 22px; background-color: #4A7C59; color: white; border-radius: 12px; }
        """)
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(40, 50, 40, 50)
        c_lay.setSpacing(20)

        title = QLabel("🌿 과수원 로그인")
        title.setStyleSheet("font-weight: 900; color: #2D5A27; border: none;")
        title.setFont(make_app_font(36, bold=True))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.addWidget(title)

        lbl_id = QLabel("아이디")
        lbl_id.setFont(make_app_font(22, bold=True))
        c_lay.addWidget(lbl_id)
        self.id_input = QLineEdit()
        self.id_input.setFont(make_app_font(26))
        self.id_input.returnPressed.connect(lambda: self.pw_input.setFocus())
        c_lay.addWidget(self.id_input)

        lbl_pw = QLabel("비밀번호")
        lbl_pw.setFont(make_app_font(22, bold=True))
        c_lay.addWidget(lbl_pw)
        self.pw_input = QLineEdit()
        self.pw_input.setFont(make_app_font(26))
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.returnPressed.connect(self.auth_check)
        c_lay.addWidget(self.pw_input)

        self.btn_login = QPushButton("로 그 인")
        self.btn_login.setFont(make_app_font(28, bold=True))
        self.btn_login.clicked.connect(self.auth_check)
        c_lay.addWidget(self.btn_login)

        layout.addWidget(card)
    
    def auth_check(self):
        uid = self.id_input.text().strip()
        upw = self.pw_input.text().strip()

        # [수정 전] 직접 쿼리를 날리면 암호화 비교가 안 됩니다.
        # [수정 후] db_manager에 만들어둔 login_check를 사용해야 합니다.
        session = self.db.login_check(uid, upw)

        if session:
            # 성공 시 터미널에 데이터를 찍어보세요 (farm_nm이 들어있어야 함)
            # print(f"DEBUG: 로그인 성공 세션 -> {session}")
            self.login_success.emit(session)
        else:
            # 여기서 None이 나온다면 아이디/비번이 틀렸거나 
            # DB에 암호화된 비번이 안 들어있는 것입니다.
            QMessageBox.warning(self, "알림", "아이디 또는 비밀번호가 틀립니다.")