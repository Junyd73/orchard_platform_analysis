# NTF-001 알림 시스템 설계

> **문서 번호:** NTF-001  
> **상태:** Approved · Phase 1 마감  
> **기준일:** 2026-07-20  
> **관련 화면:** [SCR-012](../mobile/docs/screens/SCR-012.md) (문서 v1.0)  
> **SSOT:** `mobile/docs/VERSIONS.md`

---

## 1. 목적

과수원 관리자·현장 사용자에게 **작업·관찰·외부 정보**를 한곳에서 전달한다.

| 구분 | 예시 |
|------|------|
| **내부(업무)** | 영농 작업 예정·미완료, 관찰 위험/주의, AI 미확정, 재관찰 예정일 |
| **외부(에이전트)** | 기상 특보·농업기상, 농촌진흥청·기술센터·농민신문 등 RSS/API |

원칙:

- 알림 **생성·외부 API 호출은 서버(또는 Agent 프로세스)** 에서만 수행한다.
- 모바일은 **조회·읽음 처리·딥링크 이동**만 담당한다.
- `farm_cd` 격리, PC·모바일 공통 DB(`orchard_platform.db`)를 따른다.
- 공통코드는 **4·8·8 규칙** (`m_common_code`).

---

## 2. 문서·화면 번호

| 번호 | 문서 | 역할 |
|------|------|------|
| **NTF-001** | 본 문서 | DB·Agent·API·정책 SSOT |
| **SCR-012** | `mobile/docs/screens/SCR-012.md` | 알림 목록·상세 UI |
| (후속) | `mobile/docs/api/README.md` §알림 | REST 계약 메모 |

기존 SCR-001~004(관찰), SCR-010~011(영농일지)과 **번호 충돌 없음**.

---

## 3. 알림 유형 (공통코드 NT01)

대분류 `NT01` — 알림유형

| 코드 | 명칭 | 발생원 | 비고 |
|------|------|--------|------|
| NT010100 | 작업 알림 | 내부 | 오늘 **미완료** 작업(필지·작업명 요약) |
| NT010200 | **생육관찰** | 내부 | `severity_cd` OS010300(주의)/OS010400(위험) + 방제 가이드 |
| NT010300 | 관찰 AI 미확정 | 내부 | `ai_status` REVIEW_REQUIRED 등 (Phase1 선택) |
| NT010400 | 재관찰 예정 | 내부 | `followup_dt` 도래·경과 (Phase1 선택) |
| NT010500 | 기상 | 외부 Agent | 일별 기상요약 + **방제작업여건**(좋음/주의/나쁨) |
| NT010600 | 농촌진흥청 | 외부 Agent | 병해충 브리핑(기관 라벨) · A단계 RSS |
| NT010700 | 기술센터 | 외부 Agent | 병해충 브리핑(기관 라벨) · A단계 RSS |
| NT010800 | 농업 뉴스 | 외부 Agent | 농민신문 등 (후속) |
| NT010900 | 시스템 | 내부 | 점검·연동 실패(관리자) |
| NT011000 | 가락 시세 | 외부 Agent | 일 2회(09·16) 출하요약 + 시그널(여건·가격·추세·5영업일 흐름) |

우선순위 `NP01`:

| 코드 | 명칭 | 적용 |
|------|------|------|
| NP010100 | 긴급 | 위험 관찰, 기상 특보, 재관찰 경과 |
| NP010200 | 보통 | 주의 관찰, 작업 알림, 일반 뉴스 |
| NP010300 | 낮음 | 참고 뉴스·정보 |

외부 피드 소스 `EF01`:

| 코드 | 명칭 |
|------|------|
| EF010100 | 기상청·농업기상 |
| EF010200 | 농촌진흥청 |
| EF010300 | 지역 기술센터 |
| EF010400 | 농민신문 |
| EF010500 | 기타 RSS |

Agent 작업 `AG01`:

| 코드 | 명칭 | 기본 주기 |
|------|------|-----------|
| AG010100 | 내부 알림 생성 | 15분 |
| AG010200 | 기상 수집·알림 | 1시간 |
| AG010300 | RDA 수집 | 6시간 |
| AG010400 | 기술센터 수집 | 6시간 |
| AG010500 | 농업 뉴스 수집 | 12시간 |

---

## 4. DB 설계

스키마 추가는 `core/notification_schema.py` → `ensure_notification_schema(db)` 로 PC·서버 공통 멱등 적용.

### 4.1 `t_notification` — 알림 마스터

농장 단위 피드. 사용자별 읽음은 별도 테이블.

```sql
CREATE TABLE IF NOT EXISTS t_notification (
    noti_id       TEXT NOT NULL,           -- NTF{YYYYMMDD}-{SEQ:03d}
    farm_cd       TEXT NOT NULL,
    noti_type_cd  TEXT NOT NULL,           -- NT01
    priority_cd   TEXT NOT NULL DEFAULT 'NP010200',
    title         TEXT NOT NULL,
    body          TEXT,                    -- 요약 본문(plain)
    payload_json  TEXT,                    -- 딥링크·메타(JSON)
    source_cd     TEXT NOT NULL,           -- INTERNAL | EF01
    ref_type      TEXT,                    -- OBSERVATION | WORK_LOG | EXTERNAL_FEED | ...
    ref_id        TEXT,                    -- obs_id, work_dt, feed_id 등
    event_at      TEXT NOT NULL,           -- 사건 발생 시각(로컬)
    expires_at    TEXT,                    -- NULL=무기한
    dedupe_key    TEXT NOT NULL,           -- 중복 방지 키(유니크)
    use_yn        TEXT NOT NULL DEFAULT 'Y',
    reg_id        TEXT NOT NULL DEFAULT 'SYSTEM',
    reg_dt        TEXT NOT NULL,
    mod_id        TEXT,
    mod_dt        TEXT,
    PRIMARY KEY (farm_cd, noti_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_noti_dedupe
    ON t_notification (farm_cd, dedupe_key) WHERE use_yn = 'Y';

CREATE INDEX IF NOT EXISTS idx_noti_farm_event
    ON t_notification (farm_cd, event_at DESC);

CREATE INDEX IF NOT EXISTS idx_noti_farm_type
    ON t_notification (farm_cd, noti_type_cd, event_at DESC);
```

**채번:** `noti_id` = `NTF` + `YYYYMMDD` + `-` + SEQ(3자리) — 전표·관찰과 독립 채번.

**`dedupe_key` 예:**

| 유형 | dedupe_key |
|------|------------|
| 관찰 위험 | `OBS:{obs_id}:SEV:{severity_cd}` |
| 재관찰 당일 | `OBS:{obs_id}:FOLLOWUP:{followup_dt}` |
| 외부 기사 | `FEED:{source_cd}:{external_id}` |
| 기상 | `WX:{farm_cd}:{alert_dt}:{alert_type}` |

**`payload_json` 예 (관찰):**

```json
{
  "route": "observation-detail",
  "obs_id": "OBS20260720-001",
  "severity_cd": "OS010400",
  "ai_pest_nm": "검은별무늬병"
}
```

### 4.2 `t_notification_read` — 사용자 읽음·숨김

```sql
CREATE TABLE IF NOT EXISTS t_notification_read (
    farm_cd    TEXT NOT NULL,
    noti_id    TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    read_yn    TEXT NOT NULL DEFAULT 'N',
    read_dt    TEXT,
    dismiss_yn TEXT NOT NULL DEFAULT 'N',
    dismiss_dt TEXT,
    reg_dt     TEXT NOT NULL,
    mod_dt     TEXT,
    PRIMARY KEY (farm_cd, noti_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_noti_read_user
    ON t_notification_read (user_id, read_yn, farm_cd);
```

- **읽음:** 목록 진입·상세 조회 시 `read_yn='Y'`.
- **숨김:** 사용자가 스와이프 삭제 시 `dismiss_yn='Y'` (마스터는 유지).

### 4.3 `t_external_feed_item` — 외부 원문 캐시

Agent가 수집한 RSS/API 항목. 알림 생성 전 **중복·TTL** 관리.

```sql
CREATE TABLE IF NOT EXISTS t_external_feed_item (
    feed_id       TEXT NOT NULL,           -- FED{YYYYMMDD}-{SEQ:03d}
    source_cd     TEXT NOT NULL,           -- EF01
    external_id   TEXT NOT NULL,           -- URL hash / GUID / article id
    title         TEXT NOT NULL,
    summary       TEXT,
    link_url      TEXT,
    published_at  TEXT,
    raw_json      TEXT,
    fetched_at    TEXT NOT NULL,
    use_yn        TEXT NOT NULL DEFAULT 'Y',
    PRIMARY KEY (source_cd, external_id)
);

CREATE INDEX IF NOT EXISTS idx_feed_fetched
    ON t_external_feed_item (source_cd, fetched_at DESC);
```

농장별 알림으로 펼칠 때: `m_farm_info`의 지역·작물·관심 키워드로 **필터링** 후 `t_notification` INSERT.

### 4.4 `t_notification_agent_job` — Agent 작업 정의

```sql
CREATE TABLE IF NOT EXISTS t_notification_agent_job (
    job_cd        TEXT NOT NULL PRIMARY KEY,  -- AG01
    job_nm        TEXT NOT NULL,
    cron_expr     TEXT NOT NULL,              -- e.g. "0 * * * *"
    enabled_yn    TEXT NOT NULL DEFAULT 'Y',
    last_run_at   TEXT,
    next_run_at   TEXT,
    config_json   TEXT,                       -- URL, 키 참조명, 임계값
    reg_dt        TEXT NOT NULL,
    mod_dt        TEXT
);
```

초기 시드:

| job_cd | cron_expr | config_json 요지 |
|--------|-----------|------------------|
| AG010100 | `*/15 * * * *` | 내부 스캔(관찰·작업) |
| AG010200 | `0 * * * *` | 기상 임계(강수·저온) |
| AG010300 | `0 */6 * * *` | RDA RSS URL |
| AG010400 | `0 */6 * * *` | 기술센터 RSS(농장 지역) |
| AG010500 | `0 7,19 * * *` | 농민신문 RSS |

### 4.5 `t_notification_agent_run` — 실행 이력

```sql
CREATE TABLE IF NOT EXISTS t_notification_agent_run (
    run_id        TEXT NOT NULL PRIMARY KEY,  -- RUN{YYYYMMDD}-{SEQ:03d}
    job_cd        TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status_cd     TEXT NOT NULL,              -- OK | PARTIAL | FAIL
    fetched_cnt   INTEGER DEFAULT 0,
    created_cnt   INTEGER DEFAULT 0,
    skipped_cnt   INTEGER DEFAULT 0,
    error_msg     TEXT,
    detail_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_run_job
    ON t_notification_agent_run (job_cd, started_at DESC);
```

---

## 5. 내부 알림 발생 규칙

### 5.1 생육관찰 — 주의·위험 (NT010200)

| 조건 | priority | dedupe |
|------|----------|--------|
| `severity_cd IN (OS010300, OS010400)` AND `use_yn='Y'` | OS010400→긴급, OS010300→보통 | `OBS:{farm}:{obs_id}:severity` |

- **트리거:** 관찰 생성·수정·AI 후보 확정 시 `observation_severity_notifier`.
- **본문:** 관찰 요약 + **추천 방제 및 대응 가이드**(`payload.spray_guide`).
- **딥링크:** `route=observation-detail`.
- **출처:** `source_org` = 내부 관찰·방제 가이드.

### 5.2 관찰 — AI 미확정 (NT010300)

| 조건 | priority |
|------|----------|
| `ai_status IN (REVIEW_REQUIRED, ANALYZED)` AND 후보 존재 AND 미확정 | 보통 |

### 5.3 재관찰 (NT010400)

| 조건 | priority | dedupe |
|------|----------|--------|
| `followup_dt = 오늘` | 보통 | FOLLOWUP:date |
| `followup_dt < 오늘` AND 미완료 | 긴급 | FOLLOWUP:overdue |

- Agent `AG010100`이 매 15분 스캔 (이벤트 누락 보완).

### 5.4 작업 (NT010100)

| 조건 | priority |
|------|----------|
| `work_dt = 오늘` AND **미완료** 작업 행 존재 | 보통 |

- 본문: 필지·작업명 요약(여러 건 시 N건·대표 2~3개).
- 딥링크: `work-log-daily`.
- Phase1: 「오늘 영농일지 미작성」만의 단순 알림은 사용하지 않음.

---

## 6. 외부 Agent 구성

### 6.1 아키텍처 (Phase1 구현)

```text
APScheduler (server/app/scheduler.py)  /  CLI once
    ↓
server/app/agents/*
    ├── internal_agent      — 미완료 작업
    ├── weather_agent       — 기상 + 방제작업여건 (PC evaluate_period_condition)
    ├── market_agent        — 가락 일요약(09·16) + 시그널
    ├── pest_agent          — A단계 RSS 브리핑(기관 라벨)
    └── observation_severity_notifier — 이벤트 트리거
    ↓
notification_writer (source_org 자동 부착 · dedupe_key)
    ↓
t_notification
```

- 개발 1회 실행: `server/scripts/run_notification_agents_once.py`
- **공통 payload:** 모든 Agent는 `source_org`(공식 출처)를 기록한다. Agent가 명시하면 덮어쓰지 않음.

### 6.2 기상 Agent (NT010500)

- `WeatherManager` · 농장 좌표.
- **방제작업여건:** PC와 동일 규칙 → 라벨 `좋음` / `주의` / `나쁨`.
- 본문: 방제작업여건 · 방제안내 · 풍속 · 24시간 강수 · 오늘/내일 요약.
- dedupe: `WX:{farm}:{YYYYMMDD}:daily` (일 1건).

### 6.3 가락 시세 Agent (NT011000)

- 스케줄: **매일 09:00 · 16:00** (슬롯별 dedupe `MKT:{farm}:{YYYYMMDD}:{09|16}`).
- 일요약: 법인별 출하량·최고가 표(`payload.market.corps`).
- 시그널: 여건·가격·추세 soft body + 최고가/평균가 **5영업일 흐름표**(당일 금액·증감%).
- 시그널 dedupe: `…:signal`.

### 6.4 병해충 Agent (NT010600/700) — A단계

- 소스: 환경설정 RSS/피드(화성·정남·경기 + 배·병해충 키워드 필터). **NCPMS 3단 API·감염예측은 B·C단계.**
- **스케줄** (`Asia/Seoul` 07:00, `season_label`과 동일 월 경계):
  - **봄·여름(3~8월):** 주 3회 — 월·수·금
  - **가을·겨울(9~2월):** 주 1회 — 월요일
- 일 1건 브리핑: `PEST:{farm}:{YYYYMMDD}:briefing`.
- 본문/모달: `농촌진흥청 : …` / `기술지원센터 : …` (`agency_lines`).
- **딥링크 없음** (정보성). `source_org` = 농촌진흥청·기술지원센터 등.

### 6.5 Agent 실패 정책

- 네트워크 오류: 다음 주기 재시도.
- 연속 실패 시 `NT010900` 시스템 알림(후속).

---

## 7. REST API (초안)

Prefix: `/api/v1/farms/{farm_cd}/notifications`

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/` | 목록 (`unread_only`, `noti_type_cd`, `limit`, `cursor`) |
| GET | `/summary` | 미읽음 건수 (AppBar 배지) |
| GET | `/{noti_id}` | 상세 |
| PUT | `/{noti_id}/read` | 읽음 처리 |
| PUT | `/read-all` | 전체 읽음 |
| PUT | `/{noti_id}/dismiss` | 숨김 |

응답 필드: `noti_id`, `noti_type_cd`, `noti_type_nm`, `priority_cd`, `title`, `body`, `event_at`, `read_yn`, `payload`.

`payload` 권장 키: `source_org`, `route`, `weather`/`spray`, `market`/`flow`, `agency_lines`, `spray_guide`.

**권한:** `m_user.farm_cd` 일치 USER 이상. SYS_ADMIN 전 농장.

---

## 8. 모바일 연동 (SCR-012)

- AppBar 종 아이콘 → `/notifications`.
- 미읽음 배지: `GET .../summary` ↔ `notificationBadge` 스토어.
- 탭 → 읽음 + 바텀시트. **이동은 `payload.route` 있을 때만**.
- ODS: 그룹 좌측 보더 · SVG 아이콘 웰 · 2×N 유형 뱃지. 상세는 SCR-012 v1.0.

---

## 9. 구현 Phase

| Phase | 범위 | 상태 |
|-------|------|------|
| **1** | DB·공통코드·REST · SCR-012 · Agent(기상/시세/병해충A/내부) · source_org · 그룹 UI | **마감 (2026-07-20)** |
| **2** | 필터 Chip · dismiss · 유형 on/off 설정 | 예정 |
| **3** | NCPMS·기상연동 감염위험(B·C) · 농장별 피드 정밀화 | 예정 |
| **4** | Push(Web Push) · SMS(별도 승인) | 예정 |

---

## 10. PC·회계와의 경계

- 알림은 **t_ledger·전표와 무연결** (정보성).
- 삭제는 soft(`use_yn`) 또는 사용자 dismiss만. 회계 이력 삭제 금지.

---

## 11. 변경 이력

| 버전 | 일자 | 요지 |
|------|------|------|
| 0.1 | 2026-07-20 | 초안 — NTF-001 · SCR-012 · DB·Agent·API |
| 0.2 | 2026-07-20 | Phase1 골격 (스키마·REST·SCR-012·AppBar) |
| **1.0** | **2026-07-20** | **Phase1 마감** — 시세 09/16·시그널 흐름표 · 기상 방제여건 · 병해충 기관별 브리핑(딥링크 없음) · 생육관찰 방제가이드 · source_org · ODS 그룹 시각화 |
| 1.1 | 2026-07-21 | 병해충 스케줄: 봄·여름 월수금 / 가을·겨울 월요일 |
