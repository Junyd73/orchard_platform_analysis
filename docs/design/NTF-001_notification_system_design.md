# NTF-001 알림 시스템 설계

> **문서 번호:** NTF-001  
> **상태:** Draft · 설계 (구현 전)  
> **기준일:** 2026-07-20  
> **관련 화면:** [SCR-012](../mobile/docs/screens/SCR-012.md)  
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
| NT010100 | 작업 알림 | 내부 | 영농일지·예정 작업·미기록 |
| NT010200 | 관찰 위험·주의 | 내부 | `severity_cd` OS010300/OS010400 |
| NT010300 | 관찰 AI 미확정 | 내부 | `ai_status` REVIEW_REQUIRED 등 |
| NT010400 | 재관찰 예정 | 내부 | `followup_dt` 도래·경과 |
| NT010500 | 기상 | 외부 Agent | 강수·한파·바람 등 임계 |
| NT010600 | 농촌진흥청 | 외부 Agent | 병해충·재해·기술정보 |
| NT010700 | 기술센터 | 외부 Agent | 지역 기술센터 RSS/API |
| NT010800 | 농업 뉴스 | 외부 Agent | 농민신문 등 주요 헤드라인 |
| NT010900 | 시스템 | 내부 | 점검·연동 실패(관리자) |
| NT011000 | 가락 시세 | 외부 Agent | 출하 타이밍 시그널(±10%) |

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

### 5.1 관찰 — 위험·주의 (NT010200)

| 조건 | priority | dedupe |
|------|----------|--------|
| `severity_cd IN (OS010300, OS010400)` AND `use_yn='Y'` AND 미완료(`progress_status_cd` NOT IN OP010400, OP010500) | OS010400→긴급, OS010300→보통 | obs_id + severity |

- **트리거:** 관찰 저장·수정·AI 확정 시 `NotificationService.emit_observation_severity`.
- 제목: `{severity_nm} 관찰` / 본문: `{ai_pest_nm 또는 obs_title}` · `{site_nm}` · `{obs_dt}`.

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
| `work_dt = 오늘` AND 작업 행 존재 AND 미저장(Phase2) | 보통 |
| 농약(`WK010200`) 작업 예정 + 최근 위험 관찰 동일 필지 | 긴급(연계) |

Phase 1: 영농일지 **일간 마스터만 있는 날** 「오늘 영농일지 미작성」 (선택).

---

## 6. 외부 Agent 구성

### 6.1 아키텍처

```text
Windows Task Scheduler / cron
    ↓
server/agents/notification_runner.py   ← 진입점(CLI)
    ↓
NotificationAgentService
    ├── InternalScanAgent      (AG010100)
    ├── WeatherAlertAgent      (AG010200) → core/weather_manager.py 재사용
    ├── RdaFeedAgent           (AG010300)
    ├── TechCenterFeedAgent    (AG010400)
    └── AgNewsFeedAgent        (AG010500)
    ↓
t_external_feed_item (upsert)
    ↓
t_notification (farm별 fan-out, dedupe)
    ↓
t_notification_agent_run (이력)
```

- **API 키:** `server/.env` · `core/api_config.py` — Agent 프로세스만 로드.
- **FastAPI와 분리:** uvicorn 재시작과 무관하게 스케줄 실행.
- 개발: `server/run_notification_agent.ps1 -Job AG010200`

### 6.2 기상 Agent (NT010500)

- 기존 `WeatherManager` · `m_farm_info.lat/lon/nx/ny` 활용.
- 임계 예: 강수확률 ≥ 70%, 최저기온 ≤ 0°C, 풍속 주의.
- 농장별 1건 dedupe / 일·특보 유형별.

### 6.3 RSS Agent (RDA·기술센터·농민신문)

- `feedparser` 또는 `requests` + XML 파싱.
- `external_id` = GUID 또는 `sha256(link_url)`.
- **전국 동일 기사** → 농장별 알림은 `m_farm_crop`·지역코드 매칭 시에만 생성 (Phase 2).
- Phase 1: `farm_cd` NULL 글로벌 피드 + 모든 농장에 「참고」 알림 (priority 낮음).

### 6.4 Agent 실패 정책

- 네트워크 오류: `status_cd=PARTIAL`, 다음 주기 재시도.
- 3회 연속 FAIL: `NT010900` 시스템 알림(ADMIN/SYS_ADMIN).

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

**권한:** `m_user.farm_cd` 일치 USER 이상. SYS_ADMIN 전 농장.

---

## 8. 모바일 연동 (SCR-012)

- AppBar 종 아이콘 → `/notifications` (SCR-012).
- 미읽음 배지: `GET .../summary`.
- 탭 시 `payload.route` 로 관찰 상세·영농일지 등 이동.
- ODS: `OdsCard` 리스트 · `OdsBadge` 유형·우선순위 톤.

---

## 9. 구현 Phase

| Phase | 범위 |
|-------|------|
| **1** | DB 스키마 · 공통코드 · REST(목록/요약/읽음) · SCR-012 골격 · AppBar 연결 (**2026-07-20 구현**) |
| **2** | Agent runner · 기상 · 필터 Chip · AppBar 배지 고도화 |
| **3** | RSS 3종 · 농장별 필터 · 읽음/숨김 UX |
| **4** | Push(Web Push) · 사용자 알림 설정(유형 on/off) |

Project A 범위 밖: Push, SMS — Phase 4·별도 승인.

---

## 10. PC·회계와의 경계

- 알림은 **t_ledger·전표와 무연결** (정보성).
- 삭제는 soft(`use_yn`) 또는 사용자 dismiss만. 회계 이력 삭제 금지.

---

## 11. 변경 이력

| 버전 | 일자 | 요지 |
|------|------|------|
| 0.1 | 2026-07-20 | 초안 — NTF-001 · SCR-012 · DB·Agent·API |
| 0.2 | 2026-07-20 | Phase1 구현 반영 (스키마·REST·SCR-012·AppBar) |
