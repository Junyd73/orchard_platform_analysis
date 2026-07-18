# Orchard Design System (ODS) v1.1

- 공식 명칭: **Orchard Design System (ODS)**
- 문서: `ODS_v1.md` (ODS v1.1)
- 상태: **Active**
- 기준일: 2026-07-17
- 시각·토큰 원본: `ODS_v1.0.pdf`
- 화면 Addendum: `ODS_v1.0.1_SCR-004_Addendum.md`
- 적용 시작 화면: SCR-004 생육관찰 상세
- v1.1 추가: Sticky AppBar Glass → Surface 스크롤 전환
- v1.1 보완(2026-07-18): **모든 화면 공통 AppBar 필수** · Bottom Action Floating 표준화

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

## 3. AppBar (공통) — ODS v1.1

### 적용 범위 (필수)

모든 모바일 화면 상단에 공통 `OdsAppBar`를 둔다.

| 구분 | 적용 |
|------|------|
| Home / 관찰 목록 / 상세 / 등록·수정 / 사진 / 영농일지 / 주문 | `OdsAppBar` 필수 |
| `MobileLayout` 사용 화면 | 레이아웃에서 AppBar를 포함한다 |
| 관찰 플로우(목록·상세·등록·사진) | 화면별로 `OdsAppBar`를 직접 둔다 |

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
| 상세·등록(Wizard)·사진 단계 | AppBar Back 허용. **대상 화면을 명시적으로 `router.push({ name })`로 이동** (단순 `router.back()` 지양) |
| Camera / Viewer / Modal | 각 오버레이 헤더 Back 유지 |

상세 AppBar Back → 관찰 목록(`observation`).  
등록·수정 AppBar Back → 취소와 동일(수정 중이면 상세, 아니면 목록).

## 4. Bottom Navigation (공통)

- 컴포넌트: `OdsBottomNav.vue`
- 활성: Filled Icon + Primary Green + SemiBold
- 비활성: Outline/Gray Icon + Gray 텍스트
- Safe Area(`env(safe-area-inset-bottom)`) 필수
- 현재 위치를 아이콘·색·굵기로 즉시 구분 가능하게 유지

## 5. Hero

- 상세 화면의 실제 제목 계층
- 제목: 기존 대비 약 10~15% 축소, SemiBold(600), 최대 2줄
- 우측 기능 연결 일러스트 유지
- 관찰번호를 주 제목으로 사용 금지
- AppBar Glass 전환과 시각적으로 이어지되, **Hero 자체 디자인은 변경하지 않음**

## 6. Card / Token

반드시 ODS 재사용:

- Color, Typography, Spacing, Radius, Shadow
- `OdsCard`, `OdsButton`, `OdsBadge`, `OdsBottomNav`, `OdsAppBar`

화면 전용 CSS는 **배치·일러스트·상태 톤**에만 제한한다.  
Card의 radius/border/shadow/padding 토큰을 우회하는 임의 카드 스타일 금지.

## 7. 사진

- 대표사진, Thumbnail, 최대 5장, 수량 표시, Viewer, 대표 지정, 삭제, 추가
- 별도 상단 사진관리 버튼 금지
- 사진 삭제 컨트롤: **White Circle + Gray X** (강한 Danger Red 금지)
- 삭제 컨트롤은 사진보다 시각적으로 앞서지 않도록 작은 오버레이로 유지

## 8. AI / PSIS 일러스트

- 문서형(클립보드/서류) 일러스트 금지
- AI: Leaf + Camera + Scan + Disease Detection
- PSIS: Spray + Shield + Leaf + Recommendation
- 자산 위치: `mobile/src/assets/ods/scr004/`

## 9. Bottom Action (Floating)

- 본문 스크롤과 무관하게 **항상 보이도록** Bottom Nav 위에 fixed(floating) 배치한다.
- 기준 화면: SCR-004 상세(수정·삭제), SCR-002 등록/수정(취소·다음·사진), 사진 단계(완료)
- Safe Area + Bottom Nav 높이(`64px + safe-area`) 위에 올린다.
- 페이지 `padding-bottom`으로 본문이 버튼에 가리지 않게 한다.
- 수정: Document + Pencil 계열 아이콘
- 삭제: Outline Trash 계열 아이콘
- ODS Button variant 유지

## 10. 금지사항

- Emoji 사용
- 햄버거 메뉴
- 임의 Color / 임의 Component 남발
- 승인 시안 정보 계층 훼손
- 기능·API·DB·라우팅을 디자인 이유로 변경

## 11. 적용 대상

| 단계 | 화면 |
|------|------|
| ODS v1.1 적용 | Home, 관찰 목록·상세·등록/수정·사진, 영농일지·주문 (`OdsAppBar` 공통) |
| 후속 고도화 | SCR-002/003 승인 시안 세부 필드·AI 플로우 |

등록·사진 Wizard도 공통 AppBar + Floating Bottom Action을 따른다.

## 12. 관련 자산

| 구분 | 경로 |
|------|------|
| 공통 아이콘 | `mobile/src/assets/ods/common/` |
| SCR-004 자산 | `mobile/src/assets/ods/scr004/` |
| ODS Token | `mobile/src/design-system/tokens.css` |
| ODS Components | `mobile/src/components/ods/` |
| 시각 원본 PDF | `mobile/docs/ODS/ODS_v1.0.pdf` |
