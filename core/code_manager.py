import sqlite3
from PyQt6.QtCore import QDate, Qt, QTimer, QTime

class CodeManager:
    def __init__(self, db_manager, farm_cd):
        self.db = db_manager
        self.farm_cd = farm_cd

    def get_common_codes(self, parent_cd):
        sql = """
            SELECT code_cd, code_nm FROM m_common_code
            WHERE farm_cd = ? AND parent_cd = ? AND use_yn = 'Y'
            ORDER BY code_cd
        """
        res = self.db.execute_query(sql, (self.farm_cd, parent_cd))
        return res if res else []

    def get_code_nm(self, code_cd):
        if not code_cd:
            return ""
        sql = "SELECT code_nm FROM m_common_code WHERE farm_cd = ? AND code_cd = ?"
        try:
            res = self.db.execute_query(sql, (self.farm_cd, code_cd))
            if res:
                return dict(res[0]).get('code_nm', code_cd)
            return code_cd
        except Exception as e:
            print(f"[CodeManager Error] 명칭 조회 실패: {str(e)}")
            return code_cd

    def get_main_work_codes(self):
        sql = """
            SELECT code_cd, code_nm FROM m_common_code
            WHERE farm_cd = ? AND parent_cd = 'WK01' AND use_yn = 'Y'
        """
        return self.db.execute_query(sql, (self.farm_cd,))

    def get_sub_work_codes(self, p_code_cd):
        return self.get_common_codes(p_code_cd)

    def get_weather_codes(self):
        return self.get_common_codes('WT01')

    def get_worker_list(self):
        sql = "SELECT pt_id, pt_nm, base_price FROM m_partner WHERE farm_cd = ? AND use_yn = 'Y'"
        return self.db.execute_query(sql, (self.farm_cd,)) or []

    def get_farm_sites(self):
        sql = "SELECT site_id, site_nm FROM m_farm_site WHERE farm_cd = ? ORDER BY site_nm ASC"
        res = self.db.fetch_all(sql, (self.farm_cd,))
        return res if res else []

    def get_partners(self):
        sql = """
            SELECT pt_id, pt_nm, base_price FROM m_partner
            WHERE farm_cd = ? AND use_yn = 'Y' ORDER BY pt_nm ASC
        """
        res = self.db.execute_query(sql, (self.farm_cd,))
        return res if res else []
