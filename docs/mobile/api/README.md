# Mobile API Notes

> 문서 버전: **v1.2.8** · SSOT: [`../VERSIONS.md`](../VERSIONS.md)

## 사용 중

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/health` | 서버 상태 |
| GET | `/api/v1/farms/{farm_cd}` | 농장 정보 |
| GET | `/api/v1/farms/{farm_cd}/sites` | 필지 목록 |
| GET | `/api/v1/farms/{farm_cd}/observations/summary` | 요약(서버 전체 집계). **SCR-001 홈 KPI는 목록 7일 집계 사용** |
| GET | `/api/v1/farms/{farm_cd}/observations` | SCR-001 관찰 목록 (+ `ai_pest_nm`) |
| POST | `/api/v1/farms/{farm_cd}/observations` | SCR-002 기본정보 임시 저장 → obs_id 채번 |
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}` | 관찰 단건 |
| PUT | `/api/v1/farms/{farm_cd}/observations/{obs_id}/basic` | 기본정보 수정(중복 생성 방지) |
| POST | `/api/v1/farms/{farm_cd}/observations/{obs_id}/candidates/confirm` | AI 후보 확정 (+ `severity_cd` 필수) |
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos` | 사진 목록 |
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos/representative` | 대표사진(첫 번째) |
| POST | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos` | 사진 업로드 (`multipart/form-data`, field=`files`) |
| PUT | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos/order` | 순서 변경 `{ photo_ids: [] }` |
| DELETE | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos/{photo_id}` | 사진 삭제(soft) |
| GET | `.../photos/{photo_id}/thumbnail` | 썸네일 파일 |
| GET | `.../photos/{photo_id}/original` | 원본 파일 |
| GET | `/api/v1/farms/{farm_cd}/notifications` | SCR-012 알림 목록 |
| GET | `/api/v1/farms/{farm_cd}/notifications/summary` | 미읽음·긴급 건수 (AppBar 배지) |
| PUT | `/api/v1/farms/{farm_cd}/notifications/{noti_id}/read` | 단건 읽음 |
| PUT | `/api/v1/farms/{farm_cd}/notifications/read-all` | 전체 읽음 |

### 알림 (NTF-001 Phase1 마감 · SCR-012 v1.0)

- 스키마: `t_notification` + `t_notification_read` (`core/notification_schema.py`)
- 헤더: `X-User-Id` (없으면 서버 `MOBILE_USER`)
- 응답: `noti_id`, `noti_type_cd/nm`, `priority_cd/nm`, `title`, `body`, `payload`, `event_at`, `read_yn`
- `payload` 권장: `source_org`, `route`, `weather`/`spray`, `market`/`flow`, `agency_lines`, `spray_guide`
- 딥링크(`route` 있을 때만): `observation-detail` | `work-log-daily` (병해충 브리핑은 route 없음)
- Agent: 기상·시세(09/16)·병해충A·내부 미완료 · `observation_severity_notifier`
- Phase1 비범위: Push, dismiss, Chip Filter, NCPMS B·C

### 기본정보 임시 저장 (등록 완료 아님)

- `obs_id`: PC와 동일 `OBS{YYYYMMDD}-{SEQ:03d}`
- 대상: `OB010400`(병해충) / `OB010200`(과실)
- 유형 자동: 병해충→`OY010400`, 과실→`OY010300`
- **위험도 `severity_cd`:** `OS010100`~`OS010400` (선택). 생성 시 미지정→`OS010100`. 수정 시 미지정→**기존값 유지**
- 처리상태 기본 `OP010100`, AI `NONE` (신규 코드 없음)
- 제목·내용: 한쪽만 있으면 다른 쪽에 동일 값 보정 (PC NOT NULL 충족)

### observations 쿼리

- `date_from`, `date_to`, `site_id`, `keyword`, `sort`(`obs_dt_desc`\|`obs_dt_asc`), `limit`
- 응답 항목에 **`ai_pest_nm`**: 최신 AI 분석의 확정명(`confirmed_name`) 또는 후보 `name_ko` (없으면 null). SCR-001 AI 위험 카드 타이틀용

### AI 후보 확정

- Body: `analysis_id`, `candidate_seq`, `confirmed_name?`, **`severity_cd`(필수)** — 사용자가 확인한 OS01
- master `ai_status=CONFIRMED` 와 함께 `severity_cd` 갱신
- 재확정 시에도 severity를 다시 저장 (동일 후보라도 API 호출)

### 사진 규칙

- 최대 **5장** (ODS / Project A)
- **HEIC/HEIF:** 클라이언트에서 업로드 전 JPG 등으로 변환 (ODS v1.1.1)
- 저장 루트: PC와 동일 `%LOCALAPPDATA%\OrchardPlatform\observation_photos` (또는 `OBS_MEDIA_ROOT`)
- 상대경로: `{farm}/{YYYY}/{obs_id}/original|thumbnail/{photo_id}.{ext}`
- `t_observation_photo` 사용, 스키마 변경 없음
- 등록 저장 API와 분리 (기존 `obs_id`에 첨부)
- 헤더 `X-User-Id`: 공통 Auth/User Context (`shared/auth/userContext`)에서 조회
  - development: `VITE_USER_ID` (`.env` / `.env.lan`)
  - production: Session/Auth provider (`setAuthUserProvider`) 의 `user_id`
  - 운영 코드에 user_id 하드코딩 금지. 로그인 연동 시 Auth Context 한 곳만 수정

### 관찰일자

- `obs_dt`는 **오늘 이하만** 허용 (서버·모바일 동일). 미래일이면 400 + 「관찰일자는 오늘까지만 허용됩니다.」

### 과실 · 추적 (ODS v1.2)

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}/track` | 동일 root 타임라인 |
| GET/PUT | `.../fruit` | 열매 측정 조회·저장 |
| PUT | `.../followup` | 재관찰 예정일 |

- 1차(root) soft delete 시 동일 `root_obs_id` 의 2차 이상도 함께 삭제
- 2차 이상 삭제는 해당 `obs_id`만

### 삭제 권한

- 작성자(접속자 `user_id` == `reg_id`) 또는
- `SYS_ADMIN` 또는
- 동일 과수원 `ADMIN` (`m_user.farm_cd` == 대상 `farm_cd`)
- 모바일/PC 채널 구분 없음

### 요약 집계 기준

- 오늘 관찰: `obs_dt = as_of_date`
- 위험(주의·위험): `severity_cd IN (OS010300, OS010400)` ∧ `progress_status_cd NOT IN (OP010400, OP010500)`  
  → PC 목록 요약 카드 `caution_danger`와 동일
- 과실: `target_type_cd = OB010200` (관찰대상 열매, PC `OBS_TARGET_FRUIT_CD`)
- AI 대기: `UPPER(TRIM(COALESCE(ai_status,'NONE'))) IN (NONE, PENDING, FAILED, REVIEW_REQUIRED)`
- **SCR-001 홈 KPI:** summary 대신 **최근 7일 목록**을 클라이언트 집계 (`observationHomeWeek.ts`)

### urgency → OS01 제안 (표시용, 확정은 사용자)

| urgency | 제안 severity |
|---------|----------------|
| HIGH | OS010400 위험 |
| MEDIUM | OS010300 주의 |
| LOW | OS010200 관심 |
| 없음 | OS010100 정상 |

### 영농일지 (SCR-010 / SCR-011) — ODS v1.2.2 · WLS Unify

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/farms/{farm_cd}/work-logs/monthly?year=&month=` | 월간 overview |
| GET | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}` | 일간 마스터+작업 |
| PUT | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/master` | 기상·이슈 UPSERT |
| PUT | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/works` | 작업행 임시 저장(작업-only) |
| PUT | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/integrated` | 통합 저장(장부·농약) |
| DELETE | `/api/v1/farms/{farm_cd}/work-logs/works/{work_id}` | 작업 삭제 |
| POST | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/weather/fetch` | 날씨 조회(캐시·외부 API). 마스터 자동 저장 없음 |

- `work_id` = `YYYYMMDD-NN` (PC와 동일)
- **미래일:** `PUT .../works` 허용 · 상태 `WO010100`(준비중) 강제 · `integrated`/기상 master는 거부
- **월간 `days`:** 캘린더 그리드(앞·뒷달 패딩) 포함 · **`summary`는 해당 월만**
- **월간 집계 (1차):**
  - `resource_count`: 일/월 **고유** `emp_cd` (동일인 다작업=1명)
  - `labor_hour_sum`: `man_hour` 합산
  - `pesticide_count` / `fertilizer_count`: 작업 mid `WK010200` / `WK010800` 건수
  - `work_items[].status_cd`: 준비중 필터용
- 통합 SSOT: [`docs/WORK_LOG_SCHEDULE_UNIFY.md`](../../docs/WORK_LOG_SCHEDULE_UNIFY.md)

### 영농 일정 Schedule — **폐기 (410)**

- 과거 Spec: [`docs/WORK_SCHEDULE_PHASE1_SPEC.md`](../../docs/WORK_SCHEDULE_PHASE1_SPEC.md) (Historical)
- `/api/v1/farms/{farm_cd}/work-schedules/*` → **410 Gone**
- 기동 시 `t_work_schedule` PENDING → `t_work_detail`(준비중) 이관

### 구글 캘린더 (WLS-001 Phase4 · work only)

- Spec: [`docs/WORK_SCHEDULE_GOOGLE_PHASE3.md`](../../docs/WORK_SCHEDULE_GOOGLE_PHASE3.md)
- `works/{id}/push` · `import-preview` · `import-confirm` (항상 work · 미래=준비중)
- `schedules/{id}/push` → **410**
- OAuth 콜백: `GET /api/v1/google-calendar/oauth/callback`
- 종일·시간 일정 · 인력/경비 제외
- `.env`: `GOOGLE_OAUTH_CLIENT_ID` · `SECRET` · `REDIRECT_URI` · `SUCCESS_REDIRECT`

### 농약 재고 (SCR-020 · PST-001 · **1차 통과 · 2026-07-22**)

- 설계: [`docs/PESTICIDE_MOBILE_PHASE1.md`](../../docs/PESTICIDE_MOBILE_PHASE1.md)
- 화면: [`screens/SCR-020.md`](../screens/SCR-020.md) **1.2.0**
- Core: `core/pesticide_manager.py` · `core/pesticide_constants.py`
- PC: MN12 재고 · MN13 사용 · 모바일은 조회 + 입고/출고/품목 수정

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/farms/{farm_cd}/pesticide/items` | 재고 목록 + 요약 |
| GET | `/api/v1/farms/{farm_cd}/pesticide/usage/recent` | 농장 최근 사용(일자별 집계) |
| GET | `/api/v1/farms/{farm_cd}/pesticide/items/{item_id}` | 품목 상세 + 최근 사용 이력 |
| GET | `/api/v1/farms/{farm_cd}/pesticide/items/{item_id}/usage` | 사용 이력 페이징 |
| GET | `.../pesticide/stats/yearly` | 연간 사용 통계 |
| GET | `.../pesticide/info` · `/info/{info_id}` | 농약 사전(로컬) |
| GET | `.../pesticide/suppliers` | 공급자 |
| GET/POST/PUT/DELETE | `.../pesticide/receipts*` | 입고 CRUD · `.../apply` 재고 반영 |
| PUT/DELETE | `.../pesticide/items/{item_id}` | 품목 수정·삭제 |
| POST | `.../pesticide/items/{item_id}/stock-out` | **출고(판매)** |
| GET | `.../pesticide/items/{item_id}/stock-hist` | 재고·입고 변동 이력 |

#### `GET .../pesticide/items`

**Query**

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `keyword` | string | — | 품목명·사전명·분류·성분 **또는** 형제 info 대상병해충 부분 일치 |
| `low_only` | bool | false | `is_low=true` 만 |
| `sort` | string | `low_first` | `low_first` \| `name` |

**Response `200`**

```json
{
  "summary": {
    "total_count": 12,
    "low_count": 2,
    "default_warn_piece_below": 1,
    "last_spray_dt": "2026-07-18"
  },
  "items": [
    {
      "item_id": 1,
      "item_nm": "○○살충제",
      "spec_nm": "500ml",
      "pest_category_nm": "살충제",
      "qty_piece": 0,
      "warn_piece_below": null,
      "warn_threshold": 1,
      "warn_source": "default",
      "is_low": true,
      "info_id": 42,
      "info_pesticide_nm": "○○유제",
      "ingredient_nm": "이미다클로프리드 10%",
      "pest_target_nm": "깍지벌레, 진딧물"
    }
  ]
}
```

- `ingredient_nm`: `m_pesticide_info` 성분명
- `pest_target_nm`: 연결 info와 **동일 `pesticide_nm`·`maker_nm`** 형제 행의 `m_pesticide_pest_map` 합집합 (`GROUP_CONCAT` DISTINCT)
- `last_spray_dt`: 확정 사용 중 최신 `use_dt` (없으면 null)
- `warn_threshold`: 실제 판정에 쓴 값 (`warn_piece_below ?? default`)
- `warn_source`: `item` | `default`
- `use_yn != 'Y'` 품목 제외

#### `GET .../pesticide/usage/recent`

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `days` | int | 30 | 조회 기간(1~90) |
| `max_days` | int | 10 | 일자 행 상한(1~30) |

**Response `200`**

```json
{
  "last_spray_dt": "2026-07-18",
  "days": [
    {
      "use_dt": "2026-07-18",
      "lines": [
        { "item_nm": "노블레스", "use_qty": 15, "unit": "개" },
        { "item_nm": "다이센엠45", "use_qty": 10, "unit": "개" }
      ]
    }
  ]
}
```

- 확정(`stock_applied_yn='Y'`) · 미취소 건만
- 동일 일자·품목은 `use_qty` 합산
- `unit`은 현재 고정 `"개"` (낱개)

#### `GET .../pesticide/items/{item_id}`

**Response `200`**

```json
{
  "item": {
    "item_id": 1,
    "item_nm": "○○살충제",
    "spec_nm": "500ml",
    "pest_category_nm": "살충제",
    "qty_piece": 0,
    "warn_piece_below": null,
    "warn_threshold": 1,
    "warn_source": "default",
    "is_low": true,
    "info_id": 42,
    "info_pesticide_nm": "○○유제",
    "ingredient_nm": "이미다클로프리드 10%",
    "pest_target_nm": "깍지벌레, 진딧물",
    "rmk": ""
  },
  "recent_usage": [
    {
      "use_id": 100,
      "use_line_id": 201,
      "use_dt": "2026-07-15",
      "use_qty": 2,
      "purpose_nm": "깍지벌레",
      "work_id": "20260715-02",
      "worker_nm": "홍길동",
      "site_nm": "1번지"
    }
  ]
}
```

- `recent_usage` 기본 **20건**, `cancel_yn='Y'` · 미확정(`stock_applied_yn!='Y'`) 제외
- `404`: 품목 없음 또는 타 농장

#### `GET .../pesticide/items/{item_id}/usage`

**Query**

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `date_from` | string | — | `YYYY-MM-DD` |
| `date_to` | string | — | `YYYY-MM-DD` |
| `offset` | int | 0 | |
| `limit` | int | 20 | max 100 |

**Response `200`**

```json
{
  "item_id": 1,
  "total": 47,
  "offset": 0,
  "limit": 20,
  "rows": [ /* recent_usage 와 동일 항목 */ ]
}
```

#### `POST .../pesticide/items/{item_id}/stock-out`

개인 판매 등 **수동 출고**. 살포(SCR-011)와 분리.

**Body**

```json
{ "qty": 3, "buyer_nm": "A농가", "rmk": "현금" }
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `qty` | Y | 1 이상 · 현재고 이하 |
| `buyer_nm` | 조건부 | 구매처 · `rmk`와 **둘 중 하나 이상** |
| `rmk` | 조건부 | 비고 |

**Response `200`**

```json
{
  "item_id": 2,
  "qty": 3,
  "qty_after": 2,
  "message": "출고 3개 반영 (잔량 2)"
}
```

- 재고 차감 + `t_pesticide_stock_hist` `trans_type=OUT` · `ref_table=manual_out`
- 재고 부족·필수값 누락 → `400`

#### `GET .../pesticide/items/{item_id}/stock-hist`

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `limit` | int | 100 | max 300 |

- `trans_type`: `IN` · `USE` · `OUT` · `ADJ` · `CANCEL`
- 입고 조인: `receipt_dt` · `supplier_nm`
- hist 없는 입고 명세도 표시(가상 행) · `qty_after` 누락 시 현재고로 역추적 보강

#### 기존 영농일지 농약 API (유지 · SCR-011)

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/farms/{farm_cd}/work-logs/masters/pesticide-items` | 일지 입력 피커 (경량, `is_low` 없음) |
| POST | `.../work-logs/daily/{work_dt}/pesticide/cancel` | 사용 취소 |
| POST | `.../pesticide/cancel-all` | 작업 연결 전건 취소 |
| POST | `.../pesticide/replace` | 확정 수정 |

- SCR-020 전용 API와 **역할 분리** (피커 vs 재고·이력·입고·출고)

#### 후속 비범위

- 발주 추천 · 푸시
- PSIS 사전 실호출 (SCR-021)
- 방제 예정일 스케줄 소스

## 향후 (미구현)

GPS 고도화·영농일지 Phase 2(일간 인력/경비 CRUD·전표·시간별 예보) 등은 후속. 모바일 번들에 API 키 금지.  
관찰 완료·AI·PSIS·과실 추적 API는 Project A에서 사용 중(위 표·절 참고).  
날씨 자동조회(`weather/fetch`)는 SCR-010/011에서 **구현됨**.  
농약 재고(SCR-020) **1차 통과** (2026-07-22) — 조회·입고·출고·통계·사전 포함.
