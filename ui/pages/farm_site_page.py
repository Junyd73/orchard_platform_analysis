import os
import requests
import qtawesome as qta
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

# 지기님의 통합 디자인 가이드 임포트
from ui.styles import MainStyles

# ---------------------------------------------------------
# 주소 분석 및 기상청 격자 변환 함수 (VWorld API)
# ---------------------------------------------------------
def get_location_info(address, api_key):
    """주소를 받아 경도/위도 좌표 및 기상청 NX/NY 격자로 변환합니다."""
    try:
        url = "https://api.vworld.kr/req/address"
        params = {
            "service": "address", "request": "getcoord", "crs": "epsg:4326",
            "address": address, "format": "json", "type": "road", "key": api_key
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data.get('response', {}).get('status') == 'OK':
            lon = float(data['response']['result']['point']['x'])
            lat = float(data['response']['result']['point']['y'])
            
            # 기상청 격자 변환 로직 (기존 유지)
            import math
            RE = 6371.00877; GRID = 5.0; SLAT1 = 30.0; SLAT2 = 60.0; OLON = 126.0; OLAT = 38.0; XO = 43; YO = 136
            DEGRAD = math.pi / 180.0; re = RE / GRID; slat1 = SLAT1 * DEGRAD; slat2 = SLAT2 * DEGRAD; olon = OLON * DEGRAD; olat = OLAT * DEGRAD
            sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
            sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
            sf = math.tan(math.pi * 0.25 + slat1 * 0.5); sf = math.pow(sf, sn) * math.cos(slat1) / sn
            ro = math.tan(math.pi * 0.25 + olat * 0.5); ro = re * sf / math.pow(ro, sn)
            ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5); ra = re * sf / math.pow(ra, sn)
            theta = lon * DEGRAD - olon
            if theta > math.pi: theta -= 2.0 * math.pi
            if theta < -math.pi: theta += 2.0 * math.pi
            theta *= sn
            nx = int(math.floor(ra * math.sin(theta) + XO + 0.5))
            ny = int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))
            return {'lat': lat, 'lon': lon, 'nx': nx, 'ny': ny}
        return None
    except: return None

class FarmSitePage(QWidget):
    def __init__(self, db_manager, session):
        super().__init__()
        self.db = db_manager
        self.session = session
        # 필지/마스터: 기존과 동일하게 farm_cd 없으면 OR001 (로컬 개발)
        self.farm_cd = session.get('farm_cd', 'OR001')
        # 재배작물(m_farm_crop): 세션에 farm_cd가 있을 때만 해당 농장 데이터로 CRUD
        self._crop_farm_cd = session.get('farm_cd')
        self.service_key = "30C779CF-6D49-3B14-B321-A1CACE6C04D5"
        self.selected_site_id = None
        self.temp_location = None

        self.init_ui()
        self.load_farm_info()
        self.load_site_list()
        self.load_crop_list()

    def init_ui(self):
        self.setStyleSheet(MainStyles.MAIN_BG)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

        # ---------------------------------------------------------
        # [상단] 과수원 마스터 정보 카드
        # ---------------------------------------------------------
        master_card = QFrame(); master_card.setStyleSheet(MainStyles.CARD)
        master_layout = QVBoxLayout(master_card)
        master_layout.setContentsMargins(20, 20, 20, 20)

        # 타이틀 및 저장 버튼 배치 (상단 한 줄)
        title_row = QHBoxLayout()
        title_lbl = QLabel("🌳 과수원 마스터 정보 (기상청 날씨 기준지)")
        title_lbl.setStyleSheet(MainStyles.LBL_TITLE)
        
        btn_save_m = QPushButton(qta.icon('fa5s.save', color='white'), " 정보 저장")
        btn_save_m.setStyleSheet(MainStyles.BTN_PRIMARY); btn_save_m.setFixedWidth(120)
        btn_save_m.clicked.connect(self.save_master_info)

        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(btn_save_m)
        master_layout.addLayout(title_row)

        # 격자 정보 배치 (LineEdit 전환 완료)
        grid_lay = QGridLayout(); grid_lay.setSpacing(15)
        lbl_farm = QLabel("과수원명"); lbl_farm.setStyleSheet(MainStyles.LBL_SUB)
        lbl_owner = QLabel("농장주"); lbl_owner.setStyleSheet(MainStyles.LBL_SUB)
        lbl_addr = QLabel("대표 주소"); lbl_addr.setStyleSheet(MainStyles.LBL_SUB)
        lbl_geo = QLabel("좌표 (위/경)"); lbl_geo.setStyleSheet(MainStyles.LBL_SUB)
        lbl_grid = QLabel("기상청 격자"); lbl_grid.setStyleSheet(MainStyles.LBL_SUB)

        self.edit_farm_nm = QLineEdit(); self.edit_farm_nm.setStyleSheet(MainStyles.INPUT_CENTER); self.edit_farm_nm.setReadOnly(True)
        self.edit_owner = QLineEdit(); self.edit_owner.setStyleSheet(MainStyles.INPUT_CENTER); self.edit_owner.setReadOnly(True)
        self.edit_addr = QLineEdit(); self.edit_addr.setStyleSheet(MainStyles.INPUT_CENTER)
        
        # 좌표/격자 입력창 (읽기 전용)
        self.edit_geo = QLineEdit(); self.edit_geo.setStyleSheet(MainStyles.INPUT_CENTER); self.edit_geo.setReadOnly(True)
        self.edit_grid = QLineEdit(); self.edit_grid.setStyleSheet(MainStyles.INPUT_CENTER); self.edit_grid.setReadOnly(True)

        btn_search = QPushButton(qta.icon('fa5s.search', color='white'), " 위치 찾기")
        btn_search.setStyleSheet(MainStyles.BTN_PRIMARY); btn_search.clicked.connect(self.search_address)

        grid_lay.addWidget(lbl_farm, 0, 0); grid_lay.addWidget(self.edit_farm_nm, 0, 1)
        grid_lay.addWidget(lbl_owner, 0, 2); grid_lay.addWidget(self.edit_owner, 0, 3)
        grid_lay.addWidget(lbl_addr, 1, 0); grid_lay.addWidget(self.edit_addr, 1, 1, 1, 2); grid_lay.addWidget(btn_search, 1, 3)
        grid_lay.addWidget(lbl_geo, 2, 0); grid_lay.addWidget(self.edit_geo, 2, 1)
        grid_lay.addWidget(lbl_grid, 2, 2); grid_lay.addWidget(self.edit_grid, 2, 3)
        
        master_layout.addLayout(grid_lay); main_layout.addWidget(master_card)

        # ---------------------------------------------------------
        # [중단] 세부 필지 정보 관리 (테이블 + 컴팩트 카드)
        # ---------------------------------------------------------
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "필지명", "등록일", "사용여부"])
        self.table.setStyleSheet(MainStyles.TABLE)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemClicked.connect(self.on_table_click)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setMaximumHeight(200)
        bottom_layout.addWidget(self.table, 2)

        control_card = QFrame()
        control_card.setStyleSheet(MainStyles.CARD)
        control_lay = QVBoxLayout(control_card)
        control_lay.setSpacing(8)
        control_lay.setContentsMargins(16, 16, 16, 16)
        side_title = QLabel("📍 필지 정보 관리")
        side_title.setStyleSheet(MainStyles.LBL_TITLE)
        control_lay.addWidget(side_title)

        form_lay = QFormLayout()
        form_lay.setSpacing(6)
        form_lay.setVerticalSpacing(6)
        lbl_id_t = QLabel("필지 ID")
        lbl_id_t.setStyleSheet(MainStyles.LBL_SUB)
        lbl_nm_t = QLabel("필지명")
        lbl_nm_t.setStyleSheet(MainStyles.LBL_SUB)
        lbl_use_t = QLabel("사용여부")
        lbl_use_t.setStyleSheet(MainStyles.LBL_SUB)

        self.edit_site_id = QLineEdit("자동 생성")
        self.edit_site_id.setStyleSheet(MainStyles.INPUT_CENTER)
        self.edit_site_id.setReadOnly(True)
        self.edit_site_nm = QLineEdit()
        self.edit_site_nm.setStyleSheet(MainStyles.INPUT_CENTER)
        self.combo_use_yn = QComboBox()
        self.combo_use_yn.setStyleSheet(MainStyles.COMBO)
        self.combo_use_yn.addItems(["Y", "N"])

        form_lay.addRow(lbl_id_t, self.edit_site_id)
        form_lay.addRow(lbl_nm_t, self.edit_site_nm)
        form_lay.addRow(lbl_use_t, self.combo_use_yn)
        control_lay.addLayout(form_lay)

        site_btn_row = QHBoxLayout()
        site_btn_row.setSpacing(8)
        btn_add = QPushButton("신규 등록")
        btn_add.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_add.clicked.connect(self.add_site)
        btn_edit = QPushButton("정보 수정")
        btn_edit.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_edit.clicked.connect(self.update_site)
        btn_del = QPushButton("필지 삭제")
        btn_del.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_del.clicked.connect(self.delete_site)
        site_btn_row.addWidget(btn_add, 1)
        site_btn_row.addWidget(btn_edit, 1)
        site_btn_row.addWidget(btn_del, 1)
        control_lay.addLayout(site_btn_row)

        bottom_layout.addWidget(control_card, 1)
        main_layout.addLayout(bottom_layout)

        # ---------------------------------------------------------
        # [하단] 재배작물 관리 — 필지 카드 축소로 확보한 세로 여백 우선 할당
        # ---------------------------------------------------------
        self.crop_card = QFrame()
        self.crop_card.setStyleSheet(MainStyles.CARD)
        crop_outer = QVBoxLayout(self.crop_card)
        crop_outer.setContentsMargins(20, 20, 20, 20)

        crop_title_row = QHBoxLayout()
        crop_title = QLabel("🌾 재배작물 관리")
        crop_title.setStyleSheet(MainStyles.LBL_TITLE)
        crop_title_row.addWidget(crop_title)
        crop_title_row.addStretch()
        btn_crop_new = QPushButton("신규")
        btn_crop_new.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_crop_new.clicked.connect(self.crop_append_new_row)
        btn_crop_edit = QPushButton("수정")
        btn_crop_edit.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_crop_edit.clicked.connect(self.crop_start_edit_cell)
        btn_crop_save = QPushButton("저장")
        btn_crop_save.setStyleSheet(MainStyles.BTN_PRIMARY)
        btn_crop_save.clicked.connect(self.save_crop)
        btn_crop_stop = QPushButton("사용중지")
        btn_crop_stop.setStyleSheet(MainStyles.BTN_SECONDARY)
        btn_crop_stop.clicked.connect(self.disable_crop)
        crop_title_row.addWidget(btn_crop_new)
        crop_title_row.addWidget(btn_crop_edit)
        crop_title_row.addWidget(btn_crop_save)
        crop_title_row.addWidget(btn_crop_stop)
        crop_outer.addLayout(crop_title_row)

        self.lbl_crop_hint = QLabel("")
        self.lbl_crop_hint.setStyleSheet(MainStyles.LBL_SUB + " color: #B71C1C;")
        self.lbl_crop_hint.setWordWrap(True)
        crop_outer.addWidget(self.lbl_crop_hint)

        self.crop_table = QTableWidget()
        self.crop_table.setColumnCount(5)
        self.crop_table.setHorizontalHeaderLabels(["ID", "작물명", "정렬순서", "비고", "사용여부"])
        self.crop_table.setColumnHidden(0, True)
        self.crop_table.setStyleSheet(MainStyles.TABLE)
        self.crop_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.crop_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.crop_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.crop_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.crop_table.verticalHeader().setDefaultSectionSize(22)
        self.crop_table.setMinimumHeight(120)
        self.crop_table.setMaximumHeight(280)
        self.crop_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self.crop_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.crop_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.crop_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        crop_outer.addWidget(self.crop_table)
        self.crop_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        main_layout.addWidget(self.crop_card)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._apply_crop_session_guard()

    # --- 농장 마스터 로직 ---
    def load_farm_info(self):
        sql = "SELECT farm_nm, owner_nm, address, lat, lon, nx, ny FROM m_farm_info WHERE farm_cd=?"
        res = self.db.execute_query(sql, (self.farm_cd,))
        if res and len(res) > 0:
            row = res[0]
            self.edit_farm_nm.setText(str(row[0]) if row[0] else "")
            self.edit_owner.setText(str(row[1]) if row[1] else "")
            self.edit_addr.setText(str(row[2]) if row[2] else "")
            if row[3]: self.edit_geo.setText(f"{row[3]}, {row[4]}")
            if row[5]: self.edit_grid.setText(f"NX={row[5]}, NY={row[6]}")

    def search_address(self):
        addr = self.edit_addr.text().strip()
        if not addr: return
        loc = get_location_info(addr, self.service_key)
        if loc:
            self.temp_location = loc
            self.edit_geo.setText(f"{loc['lat']:.5f}, {loc['lon']:.5f}")
            self.edit_grid.setText(f"NX={loc['nx']}, NY={loc['ny']}")
            if hasattr(self.window(), 'show_status'): self.window().show_status("🔍 위치 검색 완료!")

    def save_master_info(self):
        if not self.temp_location:
            QMessageBox.warning(self, "확인", "먼저 '위치 찾기'를 수행해 주세요.")
            return
        sql = "UPDATE m_farm_info SET address=?, lat=?, lon=?, nx=?, ny=? WHERE farm_cd=?"
        self.db.execute_query(sql, (self.edit_addr.text(), self.temp_location['lat'], self.temp_location['lon'], self.temp_location['nx'], self.temp_location['ny'], self.farm_cd))
        if hasattr(self.window(), 'show_status'): self.window().show_status("💾 마스터 정보 저장 완료")

    # --- 필지 관리 로직 (스마트 ID 생성 포함) ---
    def load_site_list(self):
        self.table.setRowCount(0)
        sql = "SELECT site_id, site_nm, reg_dt, use_yn FROM m_farm_site WHERE farm_cd=? ORDER BY use_yn DESC, site_id DESC"
        sites = self.db.execute_query(sql, (self.farm_cd,))
        for i, row in enumerate(sites):
            self.table.insertRow(i)
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val)); item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 3 and val == 'N': item.setForeground(QColor("#999999"))
                self.table.setItem(i, j, item)
        self.clear_form()

    def on_table_click(self, item):
        row = item.row()
        self.selected_site_id = self.table.item(row, 0).text()
        self.edit_site_id.setText(self.selected_site_id)
        self.edit_site_nm.setText(self.table.item(row, 1).text())
        index = self.combo_use_yn.findText(self.table.item(row, 3).text())
        self.combo_use_yn.setCurrentIndex(index)

    def clear_form(self):
        self.selected_site_id = None; self.edit_site_id.setText("자동 생성"); self.edit_site_nm.clear(); self.combo_use_yn.setCurrentIndex(0)

    def add_site(self):
        nm = self.edit_site_nm.text().strip()
        if not nm: return
        # 스마트 ID 생성 (SITE + 순번)
        res = self.db.execute_query("SELECT site_id FROM m_farm_site WHERE farm_cd = ? ORDER BY site_id DESC LIMIT 1", (self.farm_cd,))
        if res and res[0][0]:
            try:
                num = int(res[0][0].replace('SITE', '')) + 1
                new_id = f"SITE{num:02d}"
            except: new_id = "SITE01"
        else: new_id = "SITE01"
        sql = "INSERT INTO m_farm_site (site_id, farm_cd, site_nm, reg_id, reg_dt, use_yn) VALUES (?, ?, ?, ?, datetime('now','localtime'), 'Y')"
        self.db.execute_query(sql, (new_id, self.farm_cd, nm, self.session['user_id']))
        if hasattr(self.window(), 'show_status'): self.window().show_status(f"✨ 필지 [{new_id}] 등록 완료")
        self.load_site_list()

    def update_site(self):
        if not self.selected_site_id: return
        nm = self.edit_site_nm.text().strip()
        use_yn = self.combo_use_yn.currentText()
        if QMessageBox.question(self, "수정", f"[{self.selected_site_id}] 정보를 수정하시겠습니까?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            sql = "UPDATE m_farm_site SET site_nm=?, use_yn=?, mod_id=?, mod_dt=datetime('now','localtime') WHERE site_id=? AND farm_cd=?"
            self.db.execute_query(sql, (nm, use_yn, self.session['user_id'], self.selected_site_id, self.farm_cd))
            self.load_site_list()

    def delete_site(self):
        if not self.selected_site_id: return
        if QMessageBox.question(self, "삭제", "이 필지를 사용 중단(삭제)하시겠습니까?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.db.execute_query("UPDATE m_farm_site SET use_yn='N' WHERE site_id=? AND farm_cd=?", (self.selected_site_id, self.farm_cd))
            self.load_site_list()

    # --- 재배작물 (m_farm_crop) ---

    def _apply_crop_session_guard(self):
        """세션에 farm_cd가 없으면 재배작물 CRUD 비활성화(다른 농장과 혼선 방지)."""
        ok = bool(self._crop_farm_cd)
        self.crop_card.setEnabled(ok)
        if not ok:
            self.lbl_crop_hint.setText(
                "로그인 세션에 농장코드(farm_cd)가 없어 재배작물을 등록할 수 없습니다. 로그인 후 이용해 주세요."
            )
            self.lbl_crop_hint.setVisible(True)
        else:
            self.lbl_crop_hint.clear()
            self.lbl_crop_hint.setVisible(False)

    def _crop_user_id(self):
        return self.session.get("user_id") or ""

    def _crop_row_is_new(self, row: int) -> bool:
        it = self.crop_table.item(row, 0)
        if not it:
            return True
        return it.data(Qt.ItemDataRole.UserRole) == "new"

    def _crop_read_row(self, row: int):
        """테이블 한 행에서 작물명·정렬·비고·사용여부."""

        def cell(c):
            it = self.crop_table.item(row, c)
            return (it.text() if it else "").strip()

        nm = cell(1)
        try:
            so = int(cell(2) or "0")
        except ValueError:
            so = 0
        rmk = cell(3) or None
        uy = (cell(4) or "Y").upper()[:1] or "Y"
        return nm, so, rmk, uy

    def crop_append_new_row(self):
        if not self._crop_farm_cd:
            QMessageBox.warning(self, "확인", "농장코드가 없어 등록할 수 없습니다.")
            return
        r = self.crop_table.rowCount()
        self.crop_table.insertRow(r)
        vals = ["", "", "0", "", "Y"]
        for j, val in enumerate(vals):
            it = QTableWidgetItem(val)
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if j == 0:
                it.setData(Qt.ItemDataRole.UserRole, "new")
            if j in (0, 4):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.crop_table.setItem(r, j, it)
        self.crop_table.selectRow(r)
        self.crop_table.setCurrentCell(r, 1)
        self.crop_table.editItem(self.crop_table.item(r, 1))

    def crop_start_edit_cell(self):
        row = self.crop_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "확인", "수정할 행을 선택해 주세요.")
            return
        self.crop_table.setCurrentCell(row, 1)
        self.crop_table.editItem(self.crop_table.item(row, 1))

    def load_crop_list(self):
        self.crop_table.setRowCount(0)
        if not self._crop_farm_cd:
            return
        rows = self.db.list_farm_crops(self._crop_farm_cd, active_only=False)
        for i, r in enumerate(rows):
            self.crop_table.insertRow(i)
            vals = [
                str(r["crop_id"]),
                r.get("crop_nm") or "",
                str(r.get("sort_ord") if r.get("sort_ord") is not None else 0),
                r.get("rmk") or "",
                r.get("use_yn") or "Y",
            ]
            for j, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j in (0, 4):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 4 and val == "N":
                    it.setForeground(QColor("#999999"))
                self.crop_table.setItem(i, j, it)

    def save_crop(self):
        if not self._crop_farm_cd:
            QMessageBox.warning(self, "확인", "농장코드가 없어 저장할 수 없습니다.")
            return
        row = self.crop_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "확인", "저장할 행을 선택해 주세요.")
            return
        nm, so, rmk, uy = self._crop_read_row(row)
        if not nm:
            QMessageBox.warning(self, "확인", "작물명을 입력해 주세요.")
            return
        uid = self._crop_user_id()

        if self._crop_row_is_new(row):
            new_id = self.db.insert_farm_crop(
                self._crop_farm_cd, nm, so, rmk, uid
            )
            if new_id is None:
                QMessageBox.warning(
                    self, "중복", "동일 농장에 이미 등록된 작물명입니다."
                )
                return
            QMessageBox.information(self, "완료", "재배작물이 등록되었습니다.")
            self.load_crop_list()
            return

        it0 = self.crop_table.item(row, 0)
        try:
            crop_id = int((it0.text() if it0 else "").strip())
        except ValueError:
            QMessageBox.warning(self, "확인", "저장할 수 없는 행입니다.")
            return

        ok = self.db.update_farm_crop(
            crop_id,
            self._crop_farm_cd,
            nm,
            so,
            rmk,
            uy,
            uid,
        )
        if not ok:
            QMessageBox.warning(
                self, "실패",
                "저장에 실패했습니다. 작물명 중복이거나 권한이 없습니다.",
            )
            return
        QMessageBox.information(self, "완료", "저장되었습니다.")
        self.load_crop_list()

    def disable_crop(self):
        if not self._crop_farm_cd:
            QMessageBox.warning(self, "확인", "농장코드가 없어 사용중지할 수 없습니다.")
            return
        row = self.crop_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "확인", "목록에서 사용중지할 작물을 선택해 주세요.")
            return
        if self._crop_row_is_new(row):
            QMessageBox.warning(self, "확인", "저장되지 않은 신규 행은 사용중지할 수 없습니다.")
            return
        it0 = self.crop_table.item(row, 0)
        try:
            crop_id = int((it0.text() if it0 else "").strip())
        except ValueError:
            QMessageBox.warning(self, "확인", "선택한 행을 사용중지할 수 없습니다.")
            return
        if (
            QMessageBox.question(
                self,
                "사용중지",
                "선택한 재배작물을 사용중지 처리하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        ok = self.db.disable_farm_crop(
            crop_id, self._crop_farm_cd, self._crop_user_id()
        )
        if not ok:
            QMessageBox.warning(self, "실패", "사용중지 처리에 실패했습니다.")
            return
        QMessageBox.information(self, "완료", "사용중지되었습니다.")
        self.load_crop_list()