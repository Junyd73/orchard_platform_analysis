# Mobile Architecture Overview

> 문서 버전: **v1.2.2** · 기준일: 2026-07-18 · SSOT: [`../VERSIONS.md`](../VERSIONS.md)

## 목적

PC(PyQt) 업무 로직을 FastAPI로 노출하고, 모바일 PWA는 ODS UI로 소비한다.

```text
[PC PyQt]  ←── 동일 도메인 ──→  [SQLite / 향후 PG]
                ↑
           [FastAPI server]
                ↑
        [mobile PWA · ODS]
```

## 폴더 구조

```text
mobile/
├── docs/                    # Documentation · Development Rule · SCR · API 메모
│   ├── VERSIONS.md          # 버전 SSOT
│   ├── DEVELOPMENT_RULE.md
│   ├── ODS/
│   ├── architecture/
│   ├── screens/
│   └── api/
├── design-system/           # ODS 문서·토큰 설명 (런타임 아님)
├── public/                  # PWA 정적 자산
└── src/
    ├── api/                 # HTTP 클라이언트 · 엔드포인트
    ├── assets/              # 이미지·아이콘
    ├── components/
    │   └── ods/             # ODS 공통 컴포넌트 (Button/Card/Badge/Input/Nav)
    ├── design-system/       # tokens.css (런타임)
    ├── features/            # 화면·기능 단위
    │   ├── home/
    │   ├── observation/     # 생육관찰 (SCR-001~004)
    │   ├── work-log/        # 영농일지 (SCR-010 1차 · SCR-011 UI 확정)
    │   └── orders/
    ├── shared/              # layouts · stores · constants · lib
    ├── router/
    ├── types/
    ├── App.vue
    ├── main.ts
    └── styles.css
```

## 레이어 규칙

| 레이어 | 책임 | 금지 |
|--------|------|------|
| `features/*` | 화면·유스케이스 | ODS 토큰 하드코딩 복제 |
| `components/ods` | 재사용 UI | 업무 API 직접 호출 |
| `api/` | 서버 통신 | UI 마크업 |
| `shared/` | 공통 상태·레이아웃·상수 | Feature 전용 로직 |
| `design-system/` | ODS 토큰 | 임의 색상 추가 |

## Project 포커스

| 영역 | 상태 |
|------|------|
| `features/observation` | Project A 완료 (SCR-001~004 · ODS v1.2) |
| `features/work-log` | **SCR-010 월간 1차 마감** (ODS v1.2.2) · SCR-011 **UI 확정** · 기능 구현 중 |
