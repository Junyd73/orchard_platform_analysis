# Mobile Architecture Overview

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
    │   ├── observation/     # 생육관찰 (SCR-001~003)
    │   ├── work-log/
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

## Project A 포커스

단기 확장은 `features/observation` + 관련 API 가 중심이다.
