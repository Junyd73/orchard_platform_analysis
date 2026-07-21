# Mobile API Notes

> 문서 버전: **v1.2.4** · SSOT: [`../VERSIONS.md`](../VERSIONS.md)

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

### 영농일지 (SCR-010 / SCR-011) — ODS v1.2.2

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/farms/{farm_cd}/work-logs/monthly?year=&month=` | 월간 overview |
| GET | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}` | 일간 마스터+작업 |
| PUT | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/master` | 기상·이슈 UPSERT |
| PUT | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/works` | 작업행 일괄 저장 |
| DELETE | `/api/v1/farms/{farm_cd}/work-logs/works/{work_id}` | 작업 삭제 |
| POST | `/api/v1/farms/{farm_cd}/work-logs/daily/{work_dt}/weather/fetch` | 날씨 조회(캐시·외부 API). 마스터 자동 저장 없음 |

- `work_dt` · 미래일 저장 불가 (오늘 이하)
- `work_id` = `YYYYMMDD-NN` (PC와 동일)
- **월간 집계 (1차):**
  - `resource_count`: 일/월 **고유** `emp_cd` (동일인 다작업=1명)
  - `labor_hour_sum`: `man_hour` 합산
  - `pesticide_count` / `fertilizer_count`: 작업 mid `WK010200` / `WK010800` 건수
- **일간 MVP:** 인력·경비·전표 CRUD 미포함. 자식 행이 있으면 작업 삭제 거부

### 영농 일정 Schedule (WLS-001 Phase1)

- Spec: [`docs/WORK_SCHEDULE_PHASE1_SPEC.md`](../../docs/WORK_SCHEDULE_PHASE1_SPEC.md)
- 스키마: `t_work_schedule` + `WS01` (`core/work_schedule_schema.py`)
- Base: `/api/v1/farms/{farm_cd}/work-schedules` — CRUD + `convert-to-draft`
- 일정은 미래일 가능 · **실적 전환은 당일/과거만** · `integrated`/Google 동기화는 비범위

## 향후 (미구현)

GPS 고도화·영농일지 Phase 2(일간 인력/경비 CRUD·전표·시간별 예보) 등은 후속. 모바일 번들에 API 키 금지.  
관찰 완료·AI·PSIS·과실 추적 API는 Project A에서 사용 중(위 표·절 참고).  
날씨 자동조회(`weather/fetch`)는 SCR-010/011에서 **구현됨**.
