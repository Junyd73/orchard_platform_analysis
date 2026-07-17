# Orchard Platform Mobile — Development Rule

> 공식 개발 기준 문서.  
> **새 작업 전:** `mobile/PROJECT_MASTER.md` 를 먼저 읽고, 이어서 본 문서를 확인한다.  
> 버전: 1.1 · Project A · 2026-07

---

## 1. 개발 원칙

Orchard Platform 모바일은 **새로운 프로그램이 아니다.**

기존 **Python + PyQt6 PC 프로그램**을 모바일(PWA)로 확장하는 프로젝트이다.

| 구분 | 기준 |
|------|------|
| 업무 로직 | PC 프로그램 (분석 저장소 포함) |
| UI/UX | **Orchard Design System (ODS) v1.1** (`docs/ODS/ODS_v1.md`) |
| 데이터 | 기존 DB 구조 유지·확장 |
| API | FastAPI (`server/`), 응답 스키마 임의 변경 금지 |

### 작업 우선순위 (필수)

1. **Orchard Design System (ODS)**
2. **PC 프로그램** ([Junyd73/orchard_platform_analysis](https://github.com/Junyd73/orchard_platform_analysis) 및 본 저장소 `ui/`, `core/`)
3. **DB 구조**
4. **API**
5. **모바일 구현**

이 순서를 건너뛰고 UI를 먼저 그리지 않는다.

---

## 2. ODS 우선 원칙

- ODS는 공식 디자인 기준이다. 원본: `mobile/docs/ODS/ODS_v1.0.pdf`
- **SCR-001, SCR-002, SCR-003** 승인 화면은 **절대 임의 변경하지 않는다.**
- Color / Typography / Spacing / Radius / Button / Card / Badge / Input / Navigation 은 ODS 토큰·공통 컴포넌트를 사용한다.
- **새로운 디자인을 만들지 않는다.** 변경이 필요하면 먼저 제안하고 대표님 승인을 받는다.
- 구현 토큰: `src/design-system/tokens.css`  
- 공통 컴포넌트: `src/components/ods/*`
- **모바일 폼 가독성(현장 적용):** `docs/ODS/MOBILE_FORM_READABILITY.md`  
  - 입력 라벨 16px+ / SemiBold+ / 진한 본문색, 컨트롤과 8~10px 간격  
  - 필수·선택 명시, 도움말 13px+  
  - ODS PDF 원본은 수정하지 않고, 본 문서는 **적용 보완 규칙**으로만 관리한다.  
  - `OdsInput`/`OdsSelect`의 `variant="form"` · `OdsFormField` 사용. 기본 `variant`는 기존 화면 영향 없음.

---

## 3. PC 프로그램 기준 원칙

기능 구현 전에 반드시 PC 코드를 분석한다.

분석 경로:
- GitHub mirror: `Junyd73/orchard_platform_analysis` (`ui/pages`, `ui/widgets`, `ui/styles.py` + **Project A 모바일 미러**)
- 미러 정책: 저장소 루트 `MIRROR_POLICY.md`, 동기화 `scripts/mirror/`
- 본 저장소: `ui/`, `core/` (업무·DB·AI 로직)

업무 흐름을 PC와 동일하게 유지한다.

```text
입력 → 조회 → 저장 → 검증 → AI 처리(선택)
```

관찰(생육관찰) 예외 규칙 (ODS):
- AI는 **자동 실행하지 않는다.** 저장 후 사용자 요청 시에만 실행한다.
- GPS 실패해도 관찰 저장은 가능해야 한다.
- GPT는 약제 추천 금지 → **PSIS 공식정보** + 보유농약 표시.

---

## 4. 업무 로직 계승 원칙

- PC에서 검증된 상태값·채번·공통코드(`m_common_code`)·`farm_cd` 격리를 계승한다.
- 모바일만의 독자 업무 규칙을 만들지 않는다.
- AI / PSIS / 사진 정책은 `docs/mobile_observation_design.md`(저장소 루트)와 ODS를 함께 따른다.
- 사진: 관찰당 **최대 5장** (ODS Project A). AI 분석 동시 전송은 **최대 3장**.

---

## 5. 공통 컴포넌트 재사용 원칙

- 버튼·카드·배지·입력·하단 네비는 `src/components/ods` 를 재사용한다.
- Feature 화면에서 동일 UI를 복제·하드코딩하지 않는다.
- Feature 전용 위젯은 `src/features/<name>/components` 에만 둔다.

---

## 6. Project A 범위

### 구현 대상

- 생육관찰 메인 (SCR-001)
- 병해충 생육관찰 (SCR-002)
- 과실 생육관찰 (SCR-003)
- GPS 저장
- 사진 최대 5장 (촬영·갤러리)
- AI 분석 (사용자 요청 시, 병해충)
- PSIS 연동
- 보유농약 표시

### 구현 금지 (대표 승인 전)

- Tree Passport / 독립 `tree_id`
- QR · NFC
- IoT · 센서 · 드론
- 음성메모
- 과실 AI 예측 고도화

---

## 7. 개발 절차

새 기능/화면 작업 시:

1. **PROJECT_MASTER** (`mobile/PROJECT_MASTER.md`) 확인
2. **이 Development Rule** 확인
3. **ODS PDF** + 해당 **SCR 문서** (`docs/screens/`) 확인
4. **PC 프로그램** 해당 화면·위젯·core 로직 분석
5. **DB** 테이블·공통코드 확인 (쓰기 전 대표 확인)
6. **API** 계약 정의/확인 (`docs/api/`, `server/`)
7. **모바일** `features/` 에 ODS 컴포넌트로 구현
8. 테스트 (`npm run test:unit`, 필요 시 `npm run build` / `lint`)
9. 아래 보고 형식으로 결과 보고

금지 (기본):
- Git commit/push (요청 시에만)
- ODS 승인 화면 임의 변경
- Project A 범위 밖 기능
- API 키를 모바일 번들에 포함

---

## 8. 보고 형식

작업 완료 시 **원페이지·복사 가능한 평문**으로 보고한다.  
긴 표·다단 레이아웃·불필요한 서론은 쓰지 않는다.

```text
[작업명]
(한 줄)

[요약]
(2~4줄)

[변경]
- 경로/파일 …

[참조]
- ODS / SCR / PC …

[범위]
- 구현: …
- 미구현·제외: …

[검증]
- test / build / lint / pytest …

[영향]
- PC / DB / API …

[다음]
- …
```

---

## 9. Cursor 참조 순서

```text
1. mobile/PROJECT_MASTER.md
2. mobile/docs/DEVELOPMENT_RULE.md          ← 본 문서
3. mobile/docs/ODS/ODS_v1.0.pdf
4. mobile/docs/screens/SCR-00x.md
5. mobile/docs/architecture/overview.md
6. GitHub Junyd73/orchard_platform_analysis 또는 ui/, core/
7. DB / server API
8. mobile/src 구현
```

프로젝트 Cursor Rule: `.cursor/rules/mobile-project-a.mdc`
