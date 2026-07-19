# Orchard Design System (ODS) v1.2

- 공식 명칭: **Orchard Design System (ODS)**
- 문서: `ODS_v1.md` (Active: **v1.2.2**, 포함: v1.1 · v1.1.1 · v1.2 · v1.2.1 · v1.2.2)
- 상태: **Active**
- 기준일: 2026-07-18
- 버전 SSOT: `mobile/docs/VERSIONS.md`
- 시각·토큰 원본: `ODS_v1.0.pdf` (**PDF는 수정하지 않음**)
- 화면 Addendum:
  - `ODS_v1.0.1_SCR-004_Addendum.md` (상세 승인)
  - `ODS_v1.2_SCR-003_Fruit_Track.md` (과실 추적·Wizard)
- 적용 시작 화면: SCR-004 생육관찰 상세 → SCR-001~003·Home 공통 셸

### 변경 이력

| 버전 | 일자 | 요지 |
|------|------|------|
| v1.1 | 2026-07-17 | Sticky AppBar Glass→Surface · 공통 AppBar · Floating Bottom Action |
| **v1.1.1** | 2026-07-18 | 공통 셸 정렬(AppBar in `.content`) · BottomNav in `MobileLayout` · 관찰일자 오늘 이하 · HEIC 변환 메모 |
| **v1.2** | 2026-07-18 | 과실 추적(1차/2차+) · Wizard 4단계 · N차 사진 · cascade 삭제 · 슬라이드 뷰어 |
| **v1.2.1** | 2026-07-18 | SCR-010 영농일지 월간 시안4 확정 (흰 페이지 · 계절 Hero · KPI 가로) |
| **v1.2.2** | 2026-07-18 | SCR-010 월간 **1차 마감**: 고유 인원+`man_hour` 표시 · 기상 자동조회 · Hero「오늘」KPI(표시 월과 무관) · 농약/비료 건수 |

---

## 1. 목적

디자인 정책은 **Orchard Design System (ODS)** 로 명명·관리한다.

모바일 화면을 "웹 축소판"이 아닌 **Android Native UX** 수준으로 통일한다.  
Samsung One UI, Toss, 증권사 MTS 패턴을 참고하되, **ODS Token·Component를 최우선**으로 재사용한다.

본 문서는 이후 모든 신규 모바일 화면의 공통 디자인 정책이다.

## 2. 정보 계층

1. 공통 AppBar (농장 맥락)
2. Hero / 화면 고유 핵심 정보 (실제 제목 역할)
3. ODS Card 스택 (본문)
4. Bottom Action (필요 시)
5. Bottom Navigation (전역)

화면명(`관찰 상세` 등)을 AppBar 중앙 타이틀로 두지 않는다.  
상세 화면의 제목 역할은 Hero가 담당한다.

## 3. AppBar (공통) — ODS v1.1 + v1.1.1

### 적용 범위 (필수)

모든 모바일 화면 상단에 공통 `OdsAppBar`를 둔다.

| 구분 | 적용 |
|------|------|
| Home / 관찰 목록 / 상세 / 등록·수정 / 사진·열매 / 영농일지 / 주문 | `OdsAppBar` 필수 |
| `MobileLayout` 사용 화면 | 레이아웃에서 AppBar·BottomNav를 포함한다 |
| 관찰 플로우(목록·상세·등록·사진·열매) | 화면별로 `OdsAppBar`를 직접 둔다 |

AppBar는 농장 맥락(Farm Mark · 농장명 · 알림 · 설정)을 유지한다.  
화면명(`관찰 수정` 등)을 AppBar 중앙 타이틀로 두지 않는다.

### 구조

```text
[FarmMark] 농장명                [알림] [설정]
```

- 좌측: 농장명 (Weight 강조, 말줄임 `...`, 향후 ▼ 확장 여지)
- 우측: 알림 · 설정 (아이콘 22px, 터치영역 44px, 간격 8px+)
- 높이: 콘텐츠 영역 약 48px + Safe Area
- **금지:** 햄버거(☰), 화면명, 기본 Back 버튼, Emoji

### 배치 (v1.1.1)

- AppBar는 페이지 `.content`(또는 `MobileLayout`의 `.content`) **안** 첫 자식으로 둔다.
- 가로 full-bleed: `margin-inline: calc(-1 * var(--ods-page-padding-x))` 로 content 패딩을 상쇄한다.
- **아이콘 시각 정렬:** AppBar 좌·우 아이콘(22px)은 카드 좌·우 여백(`--ods-page-padding-x`)과 맞춘다. 터치영역(44px)은 안쪽으로만 확장한다.
- `.page`/`.shell` 직속( content 밖 )에 두면 음수 마진이 어긋나므로 **금지**.
- content 상단 패딩은 상세와 동일하게 `var(--ods-space-12)` 권장(목록·Home·MobileLayout 정합).

### Surface 정책 (v1.1)

| 상태 | 표현 |
|------|------|
| 초기 (Hero 연결) | Glass — white opacity 0.22 + 약한 Blur |
| 스크롤 후 | **동일 투명도(0.22) 유지** · Elevation/Border만 약하게 보강 |

- Sticky 고정 (`position: sticky; top: 0`)
- Glass **투명도는 스크롤 전·후 동일** (white opacity 0.22)
- 스크롤 시 Elevation · Border 만 progress(0~1)로 보간
- Blur는 읽기성 우선, 과도한 효과 금지
- 스크롤 전: AppBar와 Hero가 분리 카드처럼 보이지 않도록 연결감 유지
- 스크롤 후: 투명도는 유지하되 Elevation으로 Navigation 영역 인식

### 컴포넌트

- `mobile/src/components/ods/OdsAppBar.vue`

### 뒤로가기 정책

| 구분 | 정책 |
|------|------|
| 기본 화면 (Home·목록·영농일지·주문 등) | AppBar에 Back 없음. Android 시스템 Back / 제스처 |
| 상세·등록(Wizard)·사진·열매 단계 | AppBar Back 허용. **대상 화면을 명시적으로 `router.push({ name })`로 이동** (단순 `router.back()` 지양) |
| Camera / Viewer / Modal / 슬라이드 뷰어 | 각 오버레이 헤더 Back 유지 |

상세 AppBar Back → 관찰 목록(`observation`).  
등록·수정 AppBar Back → 취소와 동일(수정 중이면 상세, 아니면 목록).

## 4. Bottom Navigation (공통) — v1.1.1

- 컴포넌트: `OdsBottomNav.vue`
- 활성: Filled Icon + Primary Green + SemiBold
- 비활성: Outline/Gray Icon + Gray 텍스트
- Safe Area(`env(safe-area-inset-bottom)`) 필수
- 현재 위치를 아이콘·색·굵기로 즉시 구분 가능하게 유지
- **`MobileLayout`**: AppBar와 함께 BottomNav를 포함한다 (Home · 영농일지 · 주문)
- 관찰 플로우: 각 화면에서 BottomNav를 직접 둔다

## 5. Hero

- 상세 화면의 실제 제목 계층
- 제목: 기존 대비 약 10~15% 축소, SemiBold(600), 최대 2줄
- 우측 기능 연결 일러스트 유지
- 관찰번호를 주 제목으로 사용 금지
- AppBar Glass 전환과 시각적으로 이어지되, **Hero 자체 디자인은 변경하지 않음**

### 5.1 SCR-010 영농일지 월간 Hero (예외 · 시안4 · v1.2.2)

상세 Hero와 역할이 다르다. 화면 명세: `docs/screens/SCR-010.md` (1차 마감)

| 항목 | 규칙 |
|------|------|
| 페이지 바탕 | **흰색** (`ods-color-bg`). AppBar+Hero 공유 Green Layer **금지** |
| Hero 형태 | 둥근 카드 · 계절 과수원 webp · 하단만 진녹 반투명 밴드 |
| 계절 | 봄 3–5 · 여름 6–8 · 가을 9–11 · 겨울 12–2 |
| KPI | `[원형 아이콘] 라벨/숫자` 가로 3열 · 구분선 · **서브 문구 없음** |
| 투입 인력 | `N명 · Nh` (동일인 다작업=1명, `man_hour` 합). **오늘** 기준 · 표시 월과 무관 |
| 금액 | 전체 숫자(`1,250,000원`) · `만원` 축약 금지 · 세 KPI 숫자 동일 크기 |
| 인사 | 시간대별 2줄 (`workLogConstants` `heroGreetingForHour`) |
| Weather | Hero와 **겹침 없음** (간격 유지) · DB 없으면 자동 조회(버튼 없음) |
| 시안 | `docs/ODS/assets/영농일지-월간시안4.png` |

### 5.2 SCR-001 생육관찰 메인 Hero 일러스트 다양화 (확정 · 2026-07-19)

레이아웃은 영농일지와 동일 골격을 유지하고, **사진·AI 포인트·계절 톤·날씨 사진만** 바꾼다.  
상세: `docs/ODS/ODS_v1.3_SCR-001_Hero_Illustration.md`

| 항목 | 규칙 |
|------|------|
| 레이아웃 | **고정** (날짜 · 카피 · AI 안내 · 우측 이미지 · 하단 KPI) |
| 계절 | 4종 (연두/진녹/골드/블루그레이) |
| AI 테마 | 6종 (잎·과실·병해충·새순·꽃·봉지) — **우측 이미지만** |
| 날씨 | 4종 (맑음·흐림·비·안개) — **사진만** |
| KPI | **5칸** 고정 · 영농일지와 동일 높이 |
| 조합 | \(4 \times 6 \times 4 = 96\) |

## 6. Card / Token

반드시 ODS 재사용:

- Color, Typography, Spacing, Radius, Shadow
- `OdsCard`, `OdsButton`, `OdsBadge`, `OdsBottomNav`, `OdsAppBar`

화면 전용 CSS는 **배치·일러스트·상태 톤**에만 제한한다.  
Card의 radius/border/shadow/padding 토큰을 우회하는 임의 카드 스타일 금지.

## 7. 사진 — v1.1 + v1.1.1

- 대표사진, Thumbnail, 최대 5장, 수량 표시, Viewer, 대표 지정, 삭제, 추가
- 별도 상단 사진관리 버튼 금지
- 사진 삭제 컨트롤: **White Circle + Gray X** (강한 Danger Red 금지)
- 삭제 컨트롤은 사진보다 시각적으로 앞서지 않도록 작은 오버레이로 유지
- **HEIC/HEIF (v1.1.1):** 업로드 전 JPG 등으로 변환한다. ODS 토큰·카드 구조는 변경하지 않는다.

## 8. AI / PSIS 일러스트

- 문서형(클립보드/서류) 일러스트 금지
- AI: Leaf + Camera + Scan + Disease Detection
- PSIS: Spray + Shield + Leaf + Recommendation
- 자산 위치: `mobile/src/assets/ods/scr004/`
- **과실 관찰(v1.2):** 상세에서 AI·스마트 방제 카드를 **표시하지 않는다** (SCR-003)

## 9. Bottom Action (Floating)

- 본문 스크롤과 무관하게 **항상 보이도록** Bottom Nav 위에 fixed(floating) 배치한다.
- 기준 화면: SCR-004 상세(수정·삭제), SCR-002/003 등록/수정(취소·다음·사진·열매), 사진·열매 단계
- Safe Area + Bottom Nav 높이(`64px + safe-area`) 위에 올린다.
- 페이지 `padding-bottom`으로 본문이 버튼에 가리지 않게 한다.
- 수정: Document + Pencil 계열 아이콘
- 삭제: Outline Trash 계열 아이콘
- ODS Button variant 유지

## 10. 관찰일자 (v1.1.1)

- 관찰일자(`obs_dt`)는 **오늘(로컬 달력) 이하만** 허용한다.
- UI: `type="date"` 에 `max=오늘`, 미래 선택 시 안내 후 오늘로 보정.
- 서버: 미래일이면 BusinessRule `"관찰일자는 오늘까지만 허용됩니다."`
- PC 관찰일지와 동일 문구·정책.

## 11. 과실 추적 (v1.2) — 요약

상세 규칙은 `ODS_v1.2_SCR-003_Fruit_Track.md` · SCR-003 · SCR-004 를 따른다.

| 항목 | 정책 |
|------|------|
| 차수 | **1차** = 최초 관찰. **2차부터** = 추적 관찰 |
| 제목 | 추적 생성 시 `{기본제목} N차` (구형 `N차추적` 접미는 표시·생성 시 정규화) |
| 타임라인 | 각 항목에 `1차`·`2차`… 뱃지. 사진→슬라이드 뷰어, 본문→해당 차수 상세 |
| 추적관찰 CTA | **1차 상세·완료 후만** 표시. 2차 이상은 **invisible** (disabled 아님) |
| 사진 | **N차 상세 모두** `PhotoPanel`로 해당 차수 사진 표시 |
| 삭제 | 1차 삭제 시 2차 이상 일괄 삭제 가능 → **경고 후 확인**. 2차+ 삭제는 해당 건만 |
| Wizard | 과실: 기본 → 사진 → **열매** → 완료 (4단계) |
| 추적 폼 | 2차+: 관찰일자·관찰 내용만 편집. 제목 읽기 전용 |

## 12. 금지사항

- Emoji 사용
- 햄버거 메뉴
- 임의 Color / 임의 Component 남발
- 승인 시안 정보 계층 훼손
- 기능·API·DB·라우팅을 디자인 이유로 변경
- AppBar를 content 밖에 두어 full-bleed 음수 마진을 깨뜨리는 배치

## 13. 적용 대상

| 단계 | 화면 |
|------|------|
| ODS v1.1 ~ v1.1.1 | Home, 관찰 목록·상세·등록/수정·사진, 영농일지·주문 (공통 셸) |
| ODS v1.2 | 과실 생육관찰(SCR-003) · 상세 과실 분기(SCR-004) · 열매 측정 · 추적 |
| ODS v1.2.1 | SCR-010 영농일지 월간 (시안4 Hero 예외) |
| **ODS v1.2.2** | **SCR-010 월간 1차 마감** (인원·시간·기상 자동·집계 freeze) |
| 영농일지 | SCR-010 월간(Approved · 1차) · SCR-011 일간 (**UI 확정** · 기능 구현 중) |

등록·사진·열매 Wizard도 공통 AppBar + Floating Bottom Action을 따른다.

## 14. 관련 자산

| 구분 | 경로 |
|------|------|
| 공통 아이콘 | `mobile/src/assets/ods/common/` |
| SCR-004 자산 | `mobile/src/assets/ods/scr004/` |
| SCR-010 Hero | `mobile/src/assets/images/work-log/hero-*.png` |
| SCR-010 시안 | `mobile/docs/ODS/assets/영농일지-월간시안4.png` |
| ODS Token | `mobile/src/design-system/tokens.css` |
| ODS Components | `mobile/src/components/ods/` |
| 시각 원본 PDF | `mobile/docs/ODS/ODS_v1.0.pdf` |
| 과실 추적 Addendum | `mobile/docs/ODS/ODS_v1.2_SCR-003_Fruit_Track.md` |
