import datetime
import hashlib

class AccountManager:
    """
    [스키마 완벽 일치판] 과수원 통합 회계 매니저
    - trans_type_cd, farm_cd, parent_slip_no 등 필수 컬럼 적용
    - [현금 중심] 수익/비용은 현금 수령·지급 시점에만 전표 생성 (pay_status='Y'만 처리)
    """
    _shared_seq_cache = {}

    def __init__(self, db_manager, farm_cd):
        self.db = db_manager
        self.farm_cd = farm_cd

    def sync_ledger_by_basket(self, ref_type, main_id, work_date, basket, user_id):
        all_queries = []
        group_slip_map = {}
        current_groups = {}
        dirty_keys = set()
        prefix = f"{ref_type}-{main_id}-"
        db_fingerprints = self._get_db_fingerprints(ref_type, main_id, work_date)
        ui_group_signatures = {}
        for item in basket:
            if item.get('status') == 'DEL' or item.get('pay_status', 'N') == 'N':
                continue
            key = f"{item['acct_cd']}_{item['method']}"
            if key not in ui_group_signatures: ui_group_signatures[key] = []
            orig = item.get('orig_data', {})
            d_id = str(orig.get('res_id') or orig.get('exp_id') or orig.get('paid_detail_no') or 'NEW')
            amt_str = str(int(float(str(item['amt']).replace(',', ''))))
            sig = f"{d_id}|{amt_str}|{item['method']}|{work_date[:10]}"
            ui_group_signatures[key].append(sig)
            if key not in current_groups:
                current_groups[key] = {
                    'amt': 0, 'items': [], 'acct_cd': item['acct_cd'], 'method': item['method'],
                    'existing_slip': orig.get('slip_no')
                }
            current_groups[key]['amt'] += float(str(item['amt']).replace(',', ''))
            current_groups[key]['items'].append(item.get('rmk_nm') or item.get('rmk', ''))
        for key, sig_list in ui_group_signatures.items():
            ui_hash = hashlib.md5("".join(sorted(sig_list)).encode()).hexdigest()
            if ui_hash != db_fingerprints.get(key):
                dirty_keys.add(key)
        for db_key in db_fingerprints:
            if db_key not in ui_group_signatures: dirty_keys.add(db_key)
        sql_ref = "SELECT ref_id FROM t_ledger WHERE ref_id LIKE ? AND trans_st = '10' GROUP BY ref_id"
        refs = self.db.fetch_all(sql_ref, (f"{prefix}%",))
        existing_ref_keys = {r[0][len(prefix):] for r in refs}
        for key, info in current_groups.items():
            ref_id = f"{prefix}{key}"
            if key in dirty_keys:
                all_queries.extend(self.get_reversal_queries(ref_id, user_id))
                summary = f"{info['items'][0]} 외 {len(info['items'])-1}건" if len(info['items']) > 1 else info['items'][0]
                trans_type_cd = 'REVENUE' if ref_type == 'SALE' else 'SPEND'
                amt_val = abs(info['amt']) if trans_type_cd == 'REVENUE' else -abs(info['amt'])
                rmk_text = f"[{ref_type}] {summary} ({info['method']})"
                new_q, slip_no = self.get_simple_ledger_queries(ref_id, work_date, amt_val, info['acct_cd'], rmk_text, trans_type_cd, user_id)
                all_queries.extend(new_q)
                group_slip_map[key] = slip_no
            else:
                group_slip_map[key] = info.get('existing_slip')
            if key in existing_ref_keys: existing_ref_keys.remove(key)
        for old_key in existing_ref_keys:
            all_queries.extend(self.get_reversal_queries(f"{prefix}{old_key}", user_id))
        return all_queries, group_slip_map

    def _get_db_fingerprints(self, ref_type, main_id, work_date):
        fingerprints = {}
        group_data = {}
        if ref_type == 'SALE':
            sql = "SELECT pay_method_cd, pay_method_cd, paid_detail_no, pay_amt FROM t_cash_ledger WHERE sales_no = ?"
        elif ref_type == 'RES':
            sql = "SELECT 'EX020101', pay_method_cd, res_id, daily_wage FROM t_work_resource WHERE work_id = ? AND pay_status = 'Y'"
        else:
            sql = "SELECT acct_cd, pay_method_cd, exp_id, total_amt FROM t_work_expense WHERE work_id = ? AND pay_status = 'Y'"
        rows = self.db.fetch_all(sql, (main_id,))
        for r in rows:
            key = f"{r[0]}_{r[1]}"
            if key not in group_data: group_data[key] = []
            amt_str = str(int(float(r[3])))
            sig = f"{r[2]}|{amt_str}|{r[1]}|{work_date[:10]}"
            group_data[key].append(sig)
        for key, sig_list in group_data.items():
            fingerprints[key] = hashlib.md5("".join(sorted(sig_list)).encode()).hexdigest()
        return fingerprints

    def get_reversal_queries(self, ref_id, user_id):
        queries = []
        sql = "SELECT slip_no, trans_dt, trans_amt, acct_cd, rmk, trans_type_cd FROM t_ledger WHERE ref_id = ? AND trans_st = '10'"
        for row in self.db.fetch_all(sql, (ref_id,)):
            slip, dt, amt, acct, rmk, t_type = row
            queries.append(("UPDATE t_ledger SET trans_st = '90', mod_id = ?, mod_dt = datetime('now','localtime') WHERE slip_no = ?", (user_id, slip)))
            new_slip = self._generate_slip_no(dt)
            queries.append(("""
                INSERT INTO t_ledger (
                    slip_no, farm_cd, trans_dt, trans_type_cd, acct_cd, trans_amt,
                    rmk, ref_id, parent_slip_no, trans_st, reg_id, reg_dt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '80', ?, datetime('now','localtime'))
            """, (new_slip, self.farm_cd, dt, t_type, acct, -amt, f"보정(원본:{slip})", slip, slip, user_id)))
        return queries

    def get_simple_ledger_queries(self, ref_id, trans_dt, amt, acct_cd, rmk, trans_type_cd, user_id):
        slip_no = self._generate_slip_no(trans_dt)
        query = ("""
            INSERT INTO t_ledger (
                slip_no, farm_cd, trans_dt, trans_type_cd, acct_cd, trans_amt,
                rmk, ref_id, trans_st, reg_id, reg_dt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '10', ?, datetime('now','localtime'))
        """, (slip_no, self.farm_cd, trans_dt, trans_type_cd, acct_cd, amt, rmk, ref_id, user_id))
        return [query], slip_no

    def _generate_slip_no(self, dt):
        date_str = dt.replace('-', '')[:8]
        if date_str not in self._shared_seq_cache:
            res = self.db.fetch_all("SELECT MAX(CAST(SUBSTR(slip_no, 10) AS INTEGER)) FROM t_ledger WHERE SUBSTR(slip_no, 1, 8) = ?", (date_str,))
            self._shared_seq_cache[date_str] = res[0][0] if res and res[0][0] else 0
        self._shared_seq_cache[date_str] += 1
        return f"{date_str}-{self._shared_seq_cache[date_str]:03d}"

    def get_account_codes(self, parent_code, target_level=None):
        sql = "SELECT acct_cd, acct_nm, acct_level as level FROM m_account_code WHERE acct_cd LIKE ? AND use_yn = 'Y'"
        params = [f"{parent_code}%"]
        if target_level:
            sql += " AND CAST(acct_level AS TEXT) = ?"
            params.append(str(target_level))
        sql += " ORDER BY acct_cd ASC"
        return self.db.fetch_all(sql, tuple(params))
