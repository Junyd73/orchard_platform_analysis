# 모바일 폼·카드 가독성 — Project A 적용 규칙

> ODS PDF(`mobile/docs/ODS/ODS_v1.0.pdf`) **원본은 수정하지 않는다.**  
> 본 문서는 대표님 실기·논의로 확정한 **현장 적용 보완 기준**이다.  
> 버전: **1.4** · 2026-07-26

---

## 1. 폼 규칙 (등록형)

| 항목 | 기준 |
|------|------|
| 입력 라벨 | **15px**, Bold(**700**), `#2D3748` (`--ods-font-form-label`) |
| 라벨–입력 간격 | **8px** (`--ods-form-label-gap`) |
| 필드 세로 간격 | **18px** (`--ods-form-field-gap`) |
| 입력값 | **14px**, Medium(500) (`--ods-font-form-value`) |
| Placeholder | **14px**, Regular |
| 도움말·검증 | **13px** (`--ods-font-form-help`) |
| 입력·선택·비활성 필드 높이 | **35px** (`--ods-control-height`) |
| 하단 Floating 버튼 | **48px** (`--ods-button-height`) |

레퍼런스: `ObservationNewView` · `ObservationFruitMeasureView`

---

## 2. 카드 내부 규칙 (조회형 · v1.3)

카드 **바깥**(페이지·카드 헤더)과 **안쪽** 계층을 한 단 작게 둔다.

| 역할 | 예시 | 토큰 | 기준 |
|------|------|------|------|
| 카드 제목(바깥) | 과실 추적, 관찰 내용 | `--ods-font-form-label` | **15px Bold** |
| 섹션 제목(안) | 추적 요약, 타임라인 | `--ods-font-card-section` | **13px Bold** |
| 본문 강조(안) | 타임라인 일자 | `--ods-font-card-body` | **13px Bold** |
| 메타·치수(안) | 뒷밭, 30×30, Δ | `--ods-font-card-meta` | **11px** |
| 강조 보조(안) | 요약 치수, 항목 제목 | `--ods-font-card-emphasis` | **11px SemiBold** |
| 설명·힌트(안) | 사진 → 크게 보기… | `--ods-font-card-help` | **11px** |
| 카드 안 버튼 | 추적관찰, 촬영/갤러리 | `--ods-button-height-in-card` | **40px** |
| 하단 Floating | 수정·삭제 | `--ods-button-height` | **48px** |

레퍼런스: 관찰상세 **과실 추적** 카드 (`FruitTrackPanel`)

구현: `OdsCard` 내부 `.ods-btn`에 in-card 높이 자동 적용.

---

## 3. 카드 내부 표 (v1.4)

흰 카드·아코디언 본문 안의 `<table>`.  
**열 제목(th)이 본문 리스트보다 한 단 더 돋보여야 한다.** (본문 항목명이 th보다 커지거나 더 진하면 안 됨)

클래스 관례: `.tbl-wrap` > `.tbl` · 항목명 `.tbl__nm` · 수량 `.tbl__qty`

### 3.1 공통

| 항목 | 기준 |
|------|------|
| 카드 셸 | 흰 배경 · `1px --ods-color-border` · `--ods-radius-card` · `--ods-shadow-card` |
| 표 | `width: 100%` · `border-collapse: collapse` · 기본 폰트 `--ods-font-card-meta` |
| 셀 패딩 | `--ods-space-8` (**8px**) |
| 구분선 | `1px solid --ods-color-border` · **마지막 행** border 없음 |
| 열 제목(th) | `--ods-font-card-section` (**13px Bold**) · `--ods-color-text` · 배경 `--ods-color-gray-100` · `white-space: nowrap` |
| 본문 셀(td) | `--ods-color-text` · `word-break: keep-all` · 세로 정렬은 화면 성격에 맞게 |
| 본문 항목명 | `--ods-font-card-emphasis` 또는 meta + **Bold 700** (**11px**) — **th보다 작거나 같은 시각 무게, th를 넘지 않음** |
| 보조·예시 문구 | `--ods-font-card-help` / meta · `--ods-color-text-secondary` (**11px**) |
| 숫자 강조 | `font-variant-numeric: tabular-nums` · 필요 시 Bold 800 · 우측 정렬 |
| 가로 폭 | **가능하면 스크롤 없이** 열 구성. 조회·다열만 `overflow-x: auto` + `min-width` 허용 |

### 3.2 조회형

읽기 전용 목록(탭 → 상세).

| 항목 | 기준 |
|------|------|
| 행 | 탭 가능 시 cursor · `:active` 배경 `--ods-color-bg-muted` |
| 경고 수량/명 | `--ods-color-danger` |
| 래퍼 | `.tbl-wrap` · 필요 시 `overflow-x: auto` |

레퍼런스: `PesticideHoldingsAccordion` (보유현황)

### 3.3 편집형

표 안에 입력·선택. 열 제목·항목명 계층은 **3.1 공통**과 동일.  
컨트롤만 폼 규칙을 쓴다.

| 항목 | 기준 |
|------|------|
| 비교·기준값 등 컨트롤 | `--ods-font-form-value` (**14px**) · 높이 `--ods-control-height` (**35px**) · `--ods-radius-button` |
| 비활성 비교(`—` / `해당`) | `--ods-font-card-help` · secondary · 가운데 |
| 등록예시 | 별도 열 대신 **항목명 아래** 보조 문구 권장 (좁은 폭·가로 스크롤 방지) |
| 래퍼 | `overflow-x: hidden` · `table-layout: fixed` 권장 |

레퍼런스: `PesticideOutbreakSettingsView` (발병여건 설정)

---

## 구현 위치

- 토큰: `src/design-system/tokens.css`
- 카드: `OdsCard.vue`
- 폼: `OdsFormField`, `OdsInput`/`OdsSelect` `variant="form"`, `OdsButton`
- 카드 내 표: `PesticideHoldingsAccordion` · `PesticideOutbreakSettingsView`
