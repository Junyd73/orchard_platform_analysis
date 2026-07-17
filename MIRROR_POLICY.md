# Orchard Platform — Analysis 미러 정책

> **공식 미러:** [Junyd73/orchard_platform_analysis](https://github.com/Junyd73/orchard_platform_analysis)  
> **원본(Private):** `orchard_platform` (본 저장소)

## 1. 공개 목적

`orchard_platform_analysis`는 Project A의 **공식 공개 분석 저장소**이다.

- 모바일 UI·ODS·화면 설계(SCR)·API 계약·공개 가능한 서버 구조를 외부·협업자가 **동일한 기준**으로 확인할 수 있게 한다.
- Private 저장소의 **전체 복사본이 아니다.** Whitelist로 선별한 영역만 동기화한다.
- PC(PyQt) 분석 코드(`ui/`)와 모바일(Vue) 분석 코드가 **한 저장소**에서 이어지도록 유지한다.

## 2. 동기화 원칙

```text
Private (orchard_platform)
        ↓  Whitelist만
Analysis (orchard_platform_analysis)
```

| 원칙 | 설명 |
|------|------|
| Whitelist | `scripts/mirror/manifest.yaml`에 정의된 경로만 복사 |
| 선별 복사 | `.env`, DB, 실데이터, LAN·운영 URL은 절대 포함하지 않음 |
| 기능 완료 후 | Private에서 기능 완료 → 공개 가능 범위만 Analysis에 **별도 커밋** |
| ODS 동일 | Color·Typography·Spacing·Token·컴포넌트 구조는 Analysis에서도 동일하게 확인 가능해야 함 |
| 모바일 지속 반영 | 생육관찰·사진·AI·PSIS·Timeline·GPS 등 **공개 가능한** UI/설계는 지속 동기화 |

## 3. 공개 대상 (Whitelist)

### 3.1 Mobile (`mobile/`)

| Analysis 경로 | Private 원본 | 비고 |
|---------------|--------------|------|
| `mobile/src/components/` | `mobile/src/components/` | ODS 포함 |
| `mobile/src/views/` | `mobile/src/features/` | 화면 단위 (명칭 매핑) |
| `mobile/src/layouts/` | `mobile/src/shared/layouts/` | |
| `mobile/src/router/` | `mobile/src/router/` | |
| `mobile/src/composables/` | `mobile/src/shared/stores/`, `shared/constants/`, `shared/obsDraft.ts` | 상태·상수 |
| `mobile/src/types/` | `mobile/src/types/` | |
| `mobile/src/styles/` | `mobile/src/styles.css` | 단일 파일 → `styles/global.css` |
| `mobile/src/design-system/` | `mobile/src/design-system/` | Design Token |
| `mobile/src/utils/` | `mobile/src/shared/mediaUrl.ts`, `photoCardLabel.ts`, `fileInput.ts` | 순수 유틸 |
| `mobile/src/assets/` | `mobile/src/assets/**/.gitkeep`, `public/icons/`, `public/favicon.svg` | **실사진·히어로 원본 제외** |
| `mobile/docs/` | `mobile/docs/` | ODS·SCR·Architecture·API |
| `mobile/design-system/` | `mobile/design-system/README.md` | 문서만 |

**ODS 필수 포함 항목:** Color, Typography, Spacing, Radius, Shadow, Badge, Button, Card, Page/Detail/List 레이아웃 가이드, Design Token, 컴포넌트 구조 (`docs/ODS/`, `tokens.css`, `components/ods/`).

### 3.2 Server (`server/`)

| Analysis 경로 | Private 원본 | 비고 |
|---------------|--------------|------|
| `server/schemas/` | `server/app/schemas/` | Pydantic 계약 |
| `server/services/` | `server/app/services/` | 비즈니스 로직 (키·경로 하드코딩 없음) |
| `server/routers/` | `server/app/routers/` | HTTP 라우터 |
| `server/models/` | `server/app/core/observation_*.py`, `observation_constants.py` | 상태·상수 (DB 모델 아님) |
| `server/tests/` | `server/tests/` | 공개 가능 테스트만 |
| `server/docs/` | `server/docs/api_master_data.md`, `master_data_usage.md`, `sqlite_schema_baseline.md` | **LAN 접속 문서 제외** |

**제외:** `app/core/config.py`, `app/db/`, `app/api/dependencies.py`, `.env`, 실제 SQLite 경로, 미디어 루트.

### 3.3 Docs (`docs/`)

| Analysis 경로 | Private 원본 |
|---------------|--------------|
| `docs/ODS/` | `mobile/docs/ODS/` |
| `docs/mobile/` | `mobile/docs/screens/`, `architecture/`, `api/` |
| `docs/design/` | `docs/mobile_observation_design.md`, `docs/ODS_LOCATION.md` |
| `docs/architecture/` | `mobile/docs/architecture/`, `server/docs/` (화이트리스트) |

### 3.4 Scripts (`scripts/`)

| 포함 | 제외 |
|------|------|
| `scripts/mirror/` (본 정책·점검·동기화) | `start_project_dev.ps1`, `*lan*`, `show_network_info.py` |
| 문서화된 공개 유틸 (승인 후 manifest 추가) | QR·LAN IP 자동 생성 스크립트 |

## 4. 공개 제외 (Blacklist)

다음은 **절대** Analysis에 포함하지 않는다.

- `.env`, `.env.*` (`.env.example` 형태의 플레이스홀더만 예외 검토)
- `secret`, `token`, `api key`, `password`, 인증서, `keystore`
- 운영 DB, SQLite 파일 (`*.db`, `*.sqlite`)
- 실제 사진·첨부·캐시·로그
- `dist/`, `node_modules/`, `.venv/`
- 실제 농장·사용자·거래 데이터
- 내부 서버 주소, VPN, **LAN IP·QR 개발 URL**
- `mobile/src/api/` (런타임 API 클라이언트·`VITE_*` 의존 — 설계는 `docs/api`로 공개)
- **예외:** `mobile/src/api-mirror/` → Analysis `mobile/src/api/` (스텁·타입 시그니처만, HTTP 미구현)
- `mobile/src/__tests__/` (선택: 계약 테스트만 manifest 확장 시 포함)

## 5. 동기화 절차

### 5.1 일반 흐름

```text
1. Private에서 기능 완료 + 테스트
2. 공개 가능 범위 식별 (본 문서 §3)
3. scripts/mirror/preflight.py 실행 → 통과 필수
4. scripts/mirror/sync_to_analysis.py --target <analysis_repo_path>
5. Analysis 저장소에서 diff 검토
6. Analysis에 별도 커밋·푸시 (Private와 커밋 해시 일치 불필요)
```

### 5.2 명령 예시

```powershell
# 사전 점검 (실패 시 exit 1 → Push 중단)
python scripts/mirror/preflight.py

# 동기화 (Analysis 클론 경로 지정)
python scripts/mirror/sync_to_analysis.py --target ..\orchard_platform_analysis

# Analysis 쪽에서
cd ..\orchard_platform_analysis
git status
git add -A
git commit -m "feat(mobile): 생육관찰 목록 카드 ODS 동기화"
git push
```

### 5.3 환경 변수

| 변수 | 설명 |
|------|------|
| `MIRROR_TARGET` | Analysis 저장소 루트 (기본: 형제 디렉터리 `orchard_platform_analysis`) |

## 6. Push 전 자동 점검

`scripts/mirror/preflight.py`가 다음을 검사한다. **하나라도 발견 시 종료 코드 1 (Push 중단).**

| # | 검사 항목 |
|---|-----------|
| □ | `.env` / `.env.*` 파일 |
| □ | `token`, `secret`, `password`, `api_key` 패턴 |
| □ | `*.db`, `*.sqlite` |
| □ | 대용량 `jpg`/`png` (관찰 실사진 의심) |
| □ | 개인정보 패턴 (휴대폰·주민번호 형식) |
| □ | 운영 URL·내부 IP (`192.168.x`, `10.x`, `172.16–31.x`) |

동기화 스크립트는 **preflight 통과 후에만** 파일을 복사한다.

## 7. Analysis 커밋 규칙

Private 커밋과 **분리**한다. Analysis 커밋 메시지 접두사:

| 접두사 | 용도 |
|--------|------|
| `docs:` | ODS·SCR·설계 문서 |
| `feat:` | 공개 UI·API 계약 추가 |
| `refactor:` | 구조 정리 (동작 동일) |
| `test:` | 공개 테스트 |
| `style:` | ODS·토큰·포맷 |

예: `feat(mobile): SCR-003 상세 화면 카드 레이아웃 미러`

## 8. PR 작성 기준 (Analysis)

- Whitelist 밖 파일이 없는지 확인
- `preflight.py` 통과 로그 첨부
- 스크린샷·실데이터 미포함
- ODS 변경 시 PDF·토큰·컴포넌트 경로를 PR 설명에 명시
- LAN·API 키·DB 경로 언급 금지

## 9. 보안 정책

- Analysis는 **공개** 저장소로 간주한다. 민감 정보는 Private에만 둔다.
- 동기화는 자동 CI가 아닌 **개발자 승인 후** 수동 실행을 기본으로 한다 (필요 시 CI에 preflight만 연동 가능).
- manifest 변경은 대표님 승인 후 반영한다.

## 10. 관련 파일

| 파일 | 역할 |
|------|------|
| `MIRROR_POLICY.md` | 본 정책 (최상위) |
| `scripts/mirror/manifest.yaml` | Whitelist·경로 매핑 |
| `scripts/mirror/preflight.py` | Push 전 보안 점검 |
| `scripts/mirror/sync_to_analysis.py` | 선별 복사 |
| `scripts/mirror/README.md` | 실행 안내 |

## 11. 향후 모바일 기능 동기화

새 기능 개발 시 아래를 Analysis에도 반영한다 (공개 가능 범위).

| 영역 | Private | Analysis |
|------|---------|----------|
| 생육관찰 UI | `features/observation/` | `views/observation/` |
| 사진 UI | `PhotoPanel`, `PhotoViewer` | 동일 구조 |
| AI·PSIS | UI·설계 문서 | `docs/mobile/`, SCR |
| Timeline·GPS | 구현·SCR 확정 후 | manifest에 경로 추가 후 동기화 |

**미구현·비공개 기능**은 manifest에 추가하지 않는다.

## 12. Analysis 모바일 import·빌드

| 항목 | 정책 |
|------|------|
| import 치환 | `sync_to_analysis.py`가 `@/features`→`@/views`, `@/shared`→`@/composables` 등 자동 치환 |
| API | `api-mirror/` 스텁만 `mobile/src/api/`로 복사 (LAN·`.env` 없음) |
| 단독 빌드 | 타입·import 정합성 목적. 런타임 API 호출은 `ApiClientError` |
| 전체 `mobile/src/api/` | Private 런타임 구현은 미러 제외 (Whitelist 임의 확대 금지) |

---

*최종 수정: SCR-004 보완 점검 — api-mirror·import 치환*
