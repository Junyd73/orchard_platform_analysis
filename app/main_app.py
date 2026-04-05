import sys
import datetime
import importlib
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from ui.styles import make_app_font

# DB에 module_nm/class_nm이 없을 때 메뉴코드→페이지 매핑 (fallback). 경로는 ui.pages.*
MENU_PAGE_MAP = {
    'MN01': ('ui.pages.dashboard_page', 'DashboardPage'),
    'MN02': ('ui.pages.work_log_page', 'WorkLogPage'),
    'MN03': ('ui.pages.config_page', 'ConfigPage'),
    'MN04': ('ui.pages.user_manage_page', 'UserManagePage'),
    'MN12': ('ui.pages.pesticide_page', 'PesticidePage'),
    'MN13': ('ui.pages.pesticide_use_page', 'PesticideUsePage'),
    'MN14': ('ui.pages.pesticide_stats_page', 'PesticideStatsPage'),
    'MN15': ('ui.pages.pesticide_info_page', 'PesticideInfoPage'),
}

class MainApp(QMainWindow):
    def __init__(self, db_manager, session):
        super().__init__(None)
        self.db = db_manager
        self.session = session

        self.menu_buttons = {}
        self.pages = {}

        self.init_ui()
        self.start_clock()
        self.load_dynamic_menu()
        # UI 구성 후 전체화면 (작업 표시줄까지 덮음)
        self.showFullScreen()

    def init_ui(self):
        self.setWindowTitle(f"과수원 통합 관리 플랫폼 - {self.session.get('farm_nm', '')}")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("background-color: #2E7D32; color: white; border: none;")
        header_lay = QHBoxLayout(self.header)
        title_lbl = QLabel(f"🌳 {self.session.get('farm_nm')} 관리 시스템")
        title_lbl.setStyleSheet("font-weight: bold; margin-left: 20px;")
        title_lbl.setFont(make_app_font(20, bold=True))
        user_info = QLabel(f"👤 {self.session.get('user_nm')} ({self.session.get('role_cd')})님")
        user_info.setStyleSheet("margin-right: 20px;")
        user_info.setFont(make_app_font(14))
        header_lay.addWidget(title_lbl)
        header_lay.addStretch()
        header_lay.addWidget(user_info)
        self.main_layout.addWidget(self.header)

        self.body_layout = QHBoxLayout()
        self.body_layout.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("background-color: #333333; border: none;")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 20, 10, 20)
        self.menu_container_layout = QVBoxLayout()
        self.sidebar_layout.addLayout(self.menu_container_layout)
        self.sidebar_layout.addStretch()
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #FAF9F6;")
        self.body_layout.addWidget(self.sidebar)
        self.body_layout.addWidget(self.stack)
        self.main_layout.addLayout(self.body_layout)

        self.footer = QFrame()
        self.footer.setFixedHeight(35)
        self.footer.setStyleSheet("background-color: #F0F0F0; border-top: 1px solid #D1D1D1;")
        footer_lay = QHBoxLayout(self.footer)
        footer_lay.setContentsMargins(15, 0, 15, 0)
        self.lbl_status = QLabel("🌿 시스템 준비 완료")
        self.lbl_status.setStyleSheet("color: #555555; font-weight: bold;")
        self.lbl_status.setFont(make_app_font(12, bold=True))
        self.lbl_clock = QLabel()
        self.lbl_clock.setStyleSheet("color: #333333; font-weight: bold;")
        self.lbl_clock.setFont(make_app_font(12, bold=True))
        footer_lay.addWidget(self.lbl_status)
        footer_lay.addStretch()
        footer_lay.addWidget(self.lbl_clock)
        self.main_layout.addWidget(self.footer)

    def start_clock(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_time)
        self.clock_timer.start(1000)
        self.update_time()

    def update_time(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_clock.setText(now)

    def _reset_status_to_idle(self):
        self.lbl_status.setText("🌿 시스템 대기 중")

    def show_status(self, message, timeout=3000, **_kwargs):
        """timeout=None이면 자동 클리어 없음(다음 show_status 호출까지 문구 유지)."""
        self.lbl_status.setText(message)
        if not hasattr(self, "_status_idle_timer"):
            self._status_idle_timer = QTimer(self)
            self._status_idle_timer.setSingleShot(True)
            self._status_idle_timer.timeout.connect(self._reset_status_to_idle)
        self._status_idle_timer.stop()
        if timeout is not None:
            self._status_idle_timer.start(timeout)

    def load_dynamic_menu(self):
        self.menu_info_list = []
        self.pages = {}
        sql = "SELECT * FROM m_menu_info WHERE use_yn='Y' ORDER BY sort_ord"
        menus = self.db.execute_query(sql)
        role_hierarchy = {'USER': 1, 'ADMIN': 2, 'SYS_ADMIN': 3}
        user_role = self.session.get('role_cd', 'USER')
        user_level = role_hierarchy.get(user_role, 1)
        actual_idx = 0
        for m in menus:
            m = dict(m)
            limit_level = role_hierarchy.get(m.get('role_limit'), 1)
            if user_level < limit_level:
                continue
            self.menu_info_list.append(m)
            placeholder = QWidget()
            self.stack.addWidget(placeholder)
            btn = self.create_menu_button(m, actual_idx)
            self.menu_container_layout.addWidget(btn)
            self.menu_buttons[m['menu_cd']] = btn
            actual_idx += 1
        if self.menu_buttons:
            first_btn = list(self.menu_buttons.values())[0]
            self.switch_page(0, first_btn)

    def create_page_instance(self, module_nm, class_nm):
        try:
            module = importlib.import_module(module_nm)
            page_class = getattr(module, class_nm)
            return page_class(self.db, self.session)
        except Exception as e:
            print(f"[App] Page load failed {module_nm}: {e}")
            return None

    def create_menu_button(self, m_data, index):
        btn = QPushButton(f"{m_data['icon_str']}  {m_data['menu_nm']}")
        btn.setCheckable(True)
        btn.setFixedHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #BBBBBB; border: none;
                text-align: left; padding-left: 20px; border-radius: 5px;
            }
            QPushButton:hover { background-color: #444444; color: white; }
            QPushButton:checked { background-color: #2E7D32; color: white; font-weight: bold; }
        """)
        btn.setFont(make_app_font(15))
        btn.clicked.connect(lambda checked, idx=index, b=btn: self.switch_page(idx, b))
        return btn

    def switch_page(self, index, active_btn):
        for btn in self.menu_buttons.values():
            btn.setChecked(False)
        active_btn.setChecked(True)
        # 클릭 반응을 즉시 그리기 (로딩 전 인터벌이 버튼만 바뀐 것처럼 보이지 않도록)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        current_widget = self.stack.widget(index)
        if not hasattr(current_widget, 'is_loaded'):
            m_data = self.menu_info_list[index]
            menu_cd = m_data.get('menu_cd', '')
            module_nm = m_data.get('module_nm') or (MENU_PAGE_MAP.get(menu_cd, (None, None))[0])
            class_nm = m_data.get('class_nm') or (MENU_PAGE_MAP.get(menu_cd, (None, None))[1])
            if not module_nm or not class_nm:
                print(f"[App] No page mapping for menu {menu_cd}.")
                return
            # 상태바에 로딩 안내 (선택)
            self.lbl_status.setText(f"  ... {m_data.get('menu_nm', '')} 로딩 중")
            QApplication.processEvents()
            real_page = self.create_page_instance(module_nm, class_nm)
            if real_page:
                real_page.is_loaded = True
                self.stack.removeWidget(current_widget)
                self.stack.insertWidget(index, real_page)
                current_widget = real_page
            self.lbl_status.setText("시스템 대기 중")
        self.stack.setCurrentIndex(index)
        if hasattr(current_widget, 'refresh_data'):
            current_widget.refresh_data()

    def keyPressEvent(self, event):
        """전체화면 해제: Esc → 최대화 창(작업 표시줄 표시)"""
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showMaximized()
            return
        super().keyPressEvent(event)
