# SQLite Schema Baseline

읽기 전용 조사 결과입니다. 행 데이터·개인정보는 포함하지 않습니다.

- DB 경로: `C:\orchard_platform\orchard_platform.db`
- 조사 방식: `file:...?mode=ro` + `PRAGMA query_only=ON`

## 전체 테이블 목록

- `m_account_code`
- `m_account_code_old`
- `m_common_code`
- `m_customer`
- `m_farm_crop`
- `m_farm_info`
- `m_farm_site`
- `m_item_unit_price`
- `m_menu_info`
- `m_partner`
- `m_pesticide_info`
- `m_pesticide_item`
- `m_pesticide_pest_map`
- `m_pesticide_supplier`
- `m_user`
- `m_warehouse`
- `market_price_realtime`
- `market_price_settlement`
- `market_price_summary`
- `t_account_code`
- `t_cash_ledger`
- `t_dashboard_card_layout`
- `t_dashboard_card_pref`
- `t_history_log`
- `t_ledger`
- `t_ledger_backup`
- `t_ledger_history`
- `t_observation_ai_analysis`
- `t_observation_ai_candidate`
- `t_observation_ai_photo`
- `t_observation_fruit_measurement`
- `t_observation_master`
- `t_observation_pesticide_snapshot`
- `t_observation_photo`
- `t_order_delivery`
- `t_order_detail`
- `t_order_master`
- `t_pest_ai_recommend_log`
- `t_pesticide_receipt`
- `t_pesticide_receipt_line`
- `t_pesticide_stock_hist`
- `t_pesticide_use`
- `t_pesticide_use_line`
- `t_sales_delivery`
- `t_sales_detail`
- `t_sales_master`
- `t_stock_log`
- `t_stock_master`
- `t_stock_master_backup_final`
- `t_stock_master_old`
- `t_stock_status`
- `t_weather_cache`
- `t_work_detail`
- `t_work_expense`
- `t_work_log`
- `t_work_master`
- `t_work_resource`
- `t_work_resource_old`

## 대상 마스터 테이블 상세

### `m_farm_info`

#### CREATE TABLE

```sql
CREATE TABLE m_farm_info (
                farm_cd TEXT PRIMARY KEY,
                farm_nm TEXT,
                owner_nm TEXT,
                address TEXT,    -- 대표 주소 추가
                lat REAL,        -- 위도 추가
                lon REAL,        -- 경도 추가
                nx INTEGER,      -- 기상청 X 추가
                ny INTEGER,      -- 기상청 Y 추가
                reg_dt TEXT
            )
```

#### 컬럼

| name | type | notnull | default | pk |
|------|------|---------|---------|----|
| `farm_cd` | TEXT |  | `` | 1 |
| `farm_nm` | TEXT |  | `` |  |
| `owner_nm` | TEXT |  | `` |  |
| `address` | TEXT |  | `` |  |
| `lat` | REAL |  | `` |  |
| `lon` | REAL |  | `` |  |
| `nx` | INTEGER |  | `` |  |
| `ny` | INTEGER |  | `` |  |
| `reg_dt` | TEXT |  | `` |  |

#### 외래키

- (없음)

#### 인덱스 / UNIQUE

- `sqlite_autoindex_m_farm_info_1` [UNIQUE] columns=(`farm_cd`) origin=pk

#### 행 수: **1**

### `m_farm_site`

#### CREATE TABLE

```sql
CREATE TABLE m_farm_site (
                site_id TEXT PRIMARY KEY,
                farm_cd TEXT,
                site_nm TEXT,
                use_yn TEXT DEFAULT 'Y',
                reg_id TEXT,
                reg_dt TEXT,
                mod_id TEXT,
                mod_dt TEXT
            )
```

#### 컬럼

| name | type | notnull | default | pk |
|------|------|---------|---------|----|
| `site_id` | TEXT |  | `` | 1 |
| `farm_cd` | TEXT |  | `` |  |
| `site_nm` | TEXT |  | `` |  |
| `use_yn` | TEXT |  | `'Y'` |  |
| `reg_id` | TEXT |  | `` |  |
| `reg_dt` | TEXT |  | `` |  |
| `mod_id` | TEXT |  | `` |  |
| `mod_dt` | TEXT |  | `` |  |

#### 외래키

- (없음)

#### 인덱스 / UNIQUE

- `sqlite_autoindex_m_farm_site_1` [UNIQUE] columns=(`site_id`) origin=pk

#### 행 수: **6**

### `m_common_code`

#### CREATE TABLE

```sql
CREATE TABLE m_common_code (
                farm_cd TEXT,
                code_cd TEXT,
                code_nm TEXT NOT NULL,
                parent_cd TEXT,
                use_yn TEXT DEFAULT 'Y',
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
                PRIMARY KEY (farm_cd, code_cd)
            )
```

#### 컬럼

| name | type | notnull | default | pk |
|------|------|---------|---------|----|
| `farm_cd` | TEXT |  | `` | 1 |
| `code_cd` | TEXT |  | `` | 2 |
| `code_nm` | TEXT | Y | `` |  |
| `parent_cd` | TEXT |  | `` |  |
| `use_yn` | TEXT |  | `'Y'` |  |
| `reg_id` | TEXT |  | `` |  |
| `reg_dt` | TEXT |  | `` |  |
| `mod_id` | TEXT |  | `` |  |
| `mod_dt` | TEXT |  | `` |  |

#### 외래키

- (없음)

#### 인덱스 / UNIQUE

- `sqlite_autoindex_m_common_code_1` [UNIQUE] columns=(`farm_cd`, `code_cd`) origin=pk

#### 행 수: **252**

### `m_user`

#### CREATE TABLE

```sql
CREATE TABLE m_user (
                user_id TEXT PRIMARY KEY,
                user_pw TEXT NOT NULL,
                user_nm TEXT,
                farm_cd TEXT,
                role_cd TEXT,
                use_yn  TEXT DEFAULT 'Y',
                reg_id TEXT, reg_dt TEXT, mod_id TEXT, mod_dt TEXT,
                FOREIGN KEY(farm_cd) REFERENCES m_farm_info(farm_cd)
            )
```

#### 컬럼

| name | type | notnull | default | pk |
|------|------|---------|---------|----|
| `user_id` | TEXT |  | `` | 1 |
| `user_pw` | TEXT | Y | `` |  |
| `user_nm` | TEXT |  | `` |  |
| `farm_cd` | TEXT |  | `` |  |
| `role_cd` | TEXT |  | `` |  |
| `use_yn` | TEXT |  | `'Y'` |  |
| `reg_id` | TEXT |  | `` |  |
| `reg_dt` | TEXT |  | `` |  |
| `mod_id` | TEXT |  | `` |  |
| `mod_dt` | TEXT |  | `` |  |

#### 외래키

- `farm_cd` → `m_farm_info`.`farm_cd` (on_update=NO ACTION, on_delete=NO ACTION)

#### 인덱스 / UNIQUE

- `sqlite_autoindex_m_user_1` [UNIQUE] columns=(`user_id`) origin=pk

#### 행 수: **2**

## 비고

- 구버전 DDL(`orchard_platform_db.py`)과 실제 DB 스키마가 다를 수 있으므로 본 baseline을 기준으로 한다.
- 본 문서는 Step-05 계약 설계용이며, PostgreSQL 이관 DDL이 아니다.
