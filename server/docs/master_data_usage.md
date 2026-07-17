# 기준정보(Master Data) PyQt 사용처 분석

조사 기준일: Step-05  
DB 원본: `C:\orchard_platform\orchard_platform.db` (읽기 전용)  
최신 실행 경로: `main.py` → `core.db_manager.DBManager` / `ui.pages.*` / `core.code_manager.CodeManager`

구버전(참고만, 실행 경로 아님):
- `orchard_platform_db.py` — 초기 DDL 스크립트. **실제 DB 스키마와 불일치**.

---

## 1. `m_farm_info`

### 조회
| 파일 | 메서드/위치 | 핵심 컬럼 |
|------|-------------|-----------|
| `core/db_manager.py` | `login_check` (JOIN) | `farm_cd`, `farm_nm` |
| `ui/pages/farm_site_page.py` | `load_farm_info` | `farm_nm`, `owner_nm`, `address`, `lat`, `lon`, `nx`, `ny` |
| `ui/pages/user_manage_page.py` | 목록 SELECT | `farm_cd`, `farm_nm`, `owner_nm` 등 |
| `core/weather_manager.py` | `_get_farm_location` | `lat`, `lon`, `nx`, `ny` |
| `ui/pages/work_log_page.py` | 기상 좌표 조회 | `lat`, `lon`, `nx`, `ny` |
| `ui/pages/weather_detail_page.py` | 좌표 조회 | `lat`, `lon`, `nx`, `ny` |

### 저장·수정
| 파일 | 메서드 | 동작 |
|------|--------|------|
| `core/db_manager.py` | `register_new_farm` | INSERT `farm_cd`, `farm_nm`, `owner_nm`, `reg_dt` |
| `ui/pages/farm_site_page.py` | `save_master_info` | UPDATE `address`, `lat`, `lon`, `nx`, `ny` |
| `ui/pages/user_manage_page.py` | 농장 수정 | UPDATE `farm_nm`, `owner_nm` |

### 필터·권한
- 대부분 `WHERE farm_cd = ?` (세션 농장 격리).
- `use_yn` 컬럼 **없음**.

### 핵심 컬럼 (실제 DB)
`farm_cd`(PK), `farm_nm`, `owner_nm`, `address`, `lat`, `lon`, `nx`, `ny`, `reg_dt`

---

## 2. `m_farm_site`

### 조회
| 파일 | 메서드 | 핵심 컬럼 | farm_cd | use_yn |
|------|--------|-----------|---------|--------|
| `core/code_manager.py` | `get_farm_sites` | `site_id`, `site_nm` | Y | **미적용** |
| `ui/pages/farm_site_page.py` | `load_site_list` | `site_id`, `site_nm`, `reg_dt`, `use_yn` | Y | 정렬에 사용(전체 표시) |
| `ui/pages/observation_log_page.py` | 필터 콤보 | `get_farm_sites()` 경유 | Y | CodeManager와 동일(미필터) |
| `ui/pages/cost_detail_page.py` | `_fill_site_combo` | `get_farm_sites()` | Y | 미필터 |

### 저장·수정
| 파일 | 메서드 | 동작 |
|------|--------|------|
| `ui/pages/farm_site_page.py` | `add_site` | INSERT `site_id`(TEXT `SITE##`), `farm_cd`, `site_nm`, `reg_id`, `reg_dt`, `use_yn='Y'` |
| `ui/pages/farm_site_page.py` | `update_site` | UPDATE `site_nm`, `use_yn`, `mod_id`, `mod_dt` + `farm_cd` |
| `ui/pages/farm_site_page.py` | `delete_site` | 논리삭제 `use_yn='N'` |

### 핵심 컬럼 (실제 DB)
`site_id`(TEXT PK), `farm_cd`, `site_nm`, `use_yn`, `reg_id`, `reg_dt`, `mod_id`, `mod_dt`

---

## 3. `m_common_code`

### 조회
| 파일 | 메서드 | farm_cd | use_yn |
|------|--------|---------|--------|
| `core/code_manager.py` | `get_common_codes`, `get_code_nm`, `get_main_work_codes` | **필수** | `use_yn='Y'` (명칭 단건 조회는 use_yn 미적용) |
| `ui/pages/config_page.py` | 대/중/소 분류 로드 | **필수** | 표시용으로 `use_yn` 조회 |
| `ui/pages/observation_log_page.py` | CodeManager 경유 | Y | Y |
| `ui/pages/sales_page.py` / `order_page.py` 등 | CodeManager 또는 직접 SQL | 대부분 Y | 대부분 Y |
| `ui/pages/stock_page.py` | 직접 SQL | **일부 farm_cd 누락** | 미적용 |

### 저장·수정
| 파일 | 메서드 | 동작 |
|------|--------|------|
| `ui/pages/config_page.py` | 등록/수정/삭제 | INSERT/UPDATE/DELETE, PK `(farm_cd, code_cd)` |
| `core/db_manager.py` / `observation_stage2.py` / `observation_stage3.py` | 시드 INSERT | 관찰·공통코드 보장용 |

### 핵심 컬럼 (실제 DB)
PK `(farm_cd, code_cd)`, `code_nm` NOT NULL, `parent_cd`, `use_yn`, 감사 컬럼(`reg_*`, `mod_*`)

---

## 4. `m_user`

### 조회·인증
| 파일 | 메서드 | 비고 |
|------|--------|------|
| `core/db_manager.py` | `login_check` | `use_yn='Y'`, 비밀번호 검증 후 **응답에서 `user_pw` 제거** |
| `ui/pages/login_page.py` | 로그인 버튼 → `login_check` | 최신 진입점 |

### 저장·수정
| 파일 | 메서드 |
|------|--------|
| `core/db_manager.py` | `register_new_farm` (ADMIN 사용자 INSERT), 레거시 해시 승격 UPDATE |
| `ui/pages/user_manage_page.py` | 사용자/농장 등록·수정 |

### API 계약 주의
- `user_pw` 및 해시 값은 **외부 스키마에 포함하지 않음** (이번 Step 스키마 미생성).

---

## 5. 스키마·코드 불일치

| 항목 | 구버전 `orchard_platform_db.py` | 실제 SQLite + 최신 소스 |
|------|----------------------------------|-------------------------|
| 농장 소유자 | `owner_id` | `owner_nm` |
| 농장 주소 | `farm_addr` | `address` |
| 기상 좌표 | 없음 | `lat`, `lon`, `nx`, `ny` |
| 필지 PK | `INTEGER AUTOINCREMENT` | **`TEXT`** (`SITE01` 형식) |
| 필지 면적 등 | `area_size`, `tree_count` | **실제 테이블에 없음** |
| 공통코드 PK | `code_id` + `group_cd` | **`(farm_cd, code_cd)`** + `parent_cd` |
| 공통코드 계층 | `parent_id` | `parent_cd` (코드 문자열) |
| `CodeManager.get_farm_sites` | — | `use_yn` 미필터 (비활성 필지도 콤보에 노출 가능) |
| `stock_page` 공통코드 | — | 일부 쿼리에 `farm_cd` 조건 누락 |

---

## 6. 최신 vs 구버전 경로

| 구분 | 경로 | 비고 |
|------|------|------|
| 최신(사용) | `main.py`, `core/db_manager.py`, `core/code_manager.py`, `ui/pages/login_page.py`, `ui/pages/farm_site_page.py`, `ui/pages/config_page.py` | 앱 실행 경로 |
| 구버전(참고) | `orchard_platform_db.py` | 초기 DDL, 실제 DB와 불일치 |
| 서버(계약) | `server/app/schemas/*`, `server/app/repository/interfaces/*` | Step-05 계약만 |
