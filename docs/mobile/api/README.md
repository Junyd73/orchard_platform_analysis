# Mobile API Notes

## 사용 중

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/api/v1/health` | 서버 상태 |
| GET | `/api/v1/farms/{farm_cd}` | 농장 정보 |
| GET | `/api/v1/farms/{farm_cd}/sites` | 필지 목록 |
| GET | `/api/v1/farms/{farm_cd}/observations/summary` | SCR-001 요약 카드 |
| GET | `/api/v1/farms/{farm_cd}/observations` | SCR-001 관찰 목록 |
| POST | `/api/v1/farms/{farm_cd}/observations` | SCR-002 기본정보 임시 저장 → obs_id 채번 |
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}` | 관찰 단건 |
| PUT | `/api/v1/farms/{farm_cd}/observations/{obs_id}/basic` | 기본정보 수정(중복 생성 방지) |
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos` | 사진 목록 |
| GET | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos/representative` | 대표사진(첫 번째) |
| POST | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos` | 사진 업로드 (`multipart/form-data`, field=`files`) |
| PUT | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos/order` | 순서 변경 `{ photo_ids: [] }` |
| DELETE | `/api/v1/farms/{farm_cd}/observations/{obs_id}/photos/{photo_id}` | 사진 삭제(soft) |
| GET | `.../photos/{photo_id}/thumbnail` | 썸네일 파일 |
| GET | `.../photos/{photo_id}/original` | 원본 파일 |

### 기본정보 임시 저장 (등록 완료 아님)

- `obs_id`: PC와 동일 `OBS{YYYYMMDD}-{SEQ:03d}`
- 대상: `OB010400`(병해충) / `OB010200`(과실)
- 유형 자동: 병해충→`OY010400`, 과실→`OY010300`
- 기본값: 심각도 `OS010100`, 처리상태 `OP010100`, AI `NONE` (신규 코드 없음)
- 제목·내용: 한쪽만 있으면 다른 쪽에 동일 값 보정 (PC NOT NULL 충족)

### observations 쿼리

- `date_from`, `date_to`, `site_id`, `keyword`, `sort`(`obs_dt_desc`\|`obs_dt_asc`), `limit`

### 사진 규칙

- 최대 **5장** (ODS / Project A)
- 저장 루트: PC와 동일 `%LOCALAPPDATA%\OrchardPlatform\observation_photos` (또는 `OBS_MEDIA_ROOT`)
- 상대경로: `{farm}/{YYYY}/{obs_id}/original|thumbnail/{photo_id}.{ext}`
- `t_observation_photo` 사용, 스키마 변경 없음
- 등록 저장 API와 분리 (기존 `obs_id`에 첨부)
- 헤더 `X-User-Id`: 공통 Auth/User Context (`shared/auth/userContext`)에서 조회
  - development: `VITE_USER_ID` (`.env` / `.env.lan`)
  - production: Session/Auth provider (`setAuthUserProvider`) 의 `user_id`
  - 운영 코드에 user_id 하드코딩 금지. 로그인 연동 시 Auth Context 한 곳만 수정

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

## 향후 (미구현)

관찰 등록 완료·GPS·AI·PSIS는 SCR-002 이후 단계. 모바일 번들에 API 키 금지.
