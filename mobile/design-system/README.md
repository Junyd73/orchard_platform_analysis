# Design System (ODS) — Mobile

런타임 토큰: `../src/design-system/tokens.css`  
원본 PDF: `mobile/docs/ODS/ODS_v1.0.pdf` (공식 위치 유일)

## Color

| Token | Hex | 이름 |
|-------|-----|------|
| `--ods-color-primary` | `#2E7D32` | Orchard Green |
| `--ods-color-secondary` | `#66BB6A` | Fresh Leaf |
| `--ods-color-accent` | `#FFC107` | Pear Gold |
| `--ods-color-caution` | `#FF8A65` | Harvest Orange |
| `--ods-color-danger` | `#E85C4A` | Orchard Crimson |
| `--ods-color-ai` | `#4F7FB8` | Morning Sky |

Gray 900/700/500/300/100 · White — `tokens.css` 참고

## Typography

Pretendard 계열 또는 시스템 고딕  
Title1 22 Bold · Title2 18 Bold · Headline 16 SemiBold · Body1 14 Medium · Body2 13 Regular · Caption 11

## Spacing / Layout

4px 그리드: 4–64  
페이지 좌우 16 · 카드 패딩 16 · 입력/버튼 높이 52 · 카드 Radius 16

## Components

`src/components/ods`: `OdsButton`, `OdsCard`, `OdsBadge`, `OdsInput`, `OdsBottomNav`

새 컴포넌트가 필요하면 ODS 확장으로 제안 후 승인한다. 화면마다 스타일을 새로 만들지 않는다.
