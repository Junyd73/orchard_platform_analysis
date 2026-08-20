# Stage 6 Ship/Stock UX — Analysis Review Branch

검수 전용 브랜치. **analysis `main`은 변경하지 않았습니다.**

## Private 기준

| 항목 | SHA / 브랜치 |
|------|----------------|
| base | `c6e5edb93fa5234b7314ea9135aa48204138461d` (`main`) |
| feature | `de5341735285075d09579e2248c6fc32b7986692` (sales preview 2B list) |
| prior feature | `7e70f51077315271685d970de147843fe6ada2b6` |
| branch | `cursor/stage6-ship-stock-ux` |

## Review branch 목적

ChatGPT/대표가 Stage 6 P0~P3 실제 소스를 `orchard_platform_analysis`에서 직접 diff 검증.

- 영구 mirror whitelist 확대 **아님**
- Core 3종 + PC `stock_page.py`는 **이번 review branch 한시 포함**

## A/B 보완 (2026-08-20)

### A — 주문상세 잔여수량 SSOT

- `core/order_ship_qty.py` — CONFIRMED 판매 누계 공통 helper
- `core/order_service.py` — `get_order` line에 `confirmed_shipped_qty`, `remaining_order_qty`
- `core/order_ship_service.py` — helper 위임
- `server/schemas/order.py` — `OrderLineOut` 필드 추가
- `mobile/src/views/orders/OrderDetailView.vue` — 서버 `remaining_order_qty` 우선

### B — 다건 STOCK 허용조건

- `mobile/src/views/sales/shipConfirmModel.ts` — `canUseStockMode`, confirm 직전 검증
- `mobile/src/views/sales/ShipConfirmView.vue` — UI/validation
- `mobile/src/composables/stores/salesPrefill.ts` — draft 기본 ship_mode

## P0 — 배즙 출고 표시

- `mobile/src/views/orders/ordersConstants.ts` — `isJuiceItemCd`, `formatOrderLineSpec`
- natural key 미변경

## P1 — 다건 판매/출고

- `mobile/src/composables/stores/salesPrefill.ts`
- `mobile/src/views/stock/StockView.vue`
- `mobile/src/views/orders/OrderDetailView.vue`
- 단건 유지, 한 confirm = 한 `sales_no`, ship_mode 단일

## P2 — 경로/안내 문구

- `mobile/src/views/sales/ShipConfirmView.vue`
- `mobile/src/views/sales/shipConfirmModel.ts`
- 예약접수: 「예약접수 상태입니다.」
- ST010200 상태머신 미변경

## P3 — 재고조정

### Core (review 한시 포함)

- `core/stock_adjust_constants.py`
- `core/stock_adjust_service.py`
- `core/order_allocation_service.py` — 이력 `io_type_nm` 사유명

### API (whitelist)

- `server/routers/stock_adjust.py`
- `server/schemas/stock_adjust.py`
- `server/services/stock_adjust_api_service.py`

### Mobile / PC

- `mobile/src/views/stock/stockAdjustConstants.ts`
- `mobile/src/views/stock/StockView.vue`
- `mobile/src/api/stock.ts` (review 한시 — 통상 mirror 제외)
- `ui/pages/stock_page.py` — PC 폐기 Core 위임

### 사유코드 AD01

| code | 명 | IN/OUT |
|------|-----|--------|
| AD010101 | 폐기 | OUT |
| AD010102 | 파손 | OUT |
| AD010103 | 증정 | OUT |
| AD010104 | 반품 | IN |
| AD010105 | 실사차이 | IN/OUT |
| AD010106 | 기타 | IN/OUT |

## 테스트 (review branch 포함)

- `server/tests/test_stock_adjust_service.py`
- `mobile/src/__tests__/OrderDetailView.spec.ts`
- `mobile/src/__tests__/shipConfirm.spec.ts`
- `mobile/src/__tests__/stockView.spec.ts`
- `mobile/src/__tests__/stockAdjustConstants.spec.ts`

**미포함:** `OrderNewView.spec.ts` — preflight 휴대폰 패턴(테스트 fixture `010-1111-xxxx`) 차단. private에서 별도 확인.

## 검증 결과 (private feature commit 기준)

| 영역 | 결과 |
|------|------|
| Python (order ship/service, alloc, adjust, production) | 120 OK |
| 관련 vitest (OrderDetailView, shipConfirm) | 31 OK |
| 전체 vitest | 265/267 (AiAnalysisPanel 2건 baseline) |
| build | OK |

### AiAnalysisPanel baseline (CASE 1)

main(`c6e5edb`)과 feature(`6f74eb5`) **동일 2건 실패** — Stage 6 무관.

1. `AI 오류 코드 메시지` — `요금 제한` 미표시
2. `확정 실패 시 오류 표시·가이드 미호출` — `확정할 후보를 찾을 수 없습니다` 미표시

## Secret scan

- `scripts/mirror/preflight.py` 통과 (review 포함 파일)
- API key / password / env / DB 경로 미포함

## Private commit 변경 파일 (27)

```
core/order_allocation_service.py
core/stock_adjust_constants.py
core/stock_adjust_service.py
docs/mobile_order_sales/04_mobile_screen.md
docs/mobile_order_sales/05_api_contract.md
docs/mobile_order_sales/06_development_progress.md
docs/mobile_order_sales/09_production_inventory_flow.md
mobile/src/__tests__/OrderDetailView.spec.ts
mobile/src/__tests__/OrderNewView.spec.ts
mobile/src/__tests__/shipConfirm.spec.ts
mobile/src/__tests__/stockAdjustConstants.spec.ts
mobile/src/__tests__/stockView.spec.ts
mobile/src/api/stock.ts
mobile/src/features/orders/OrderDetailView.vue
mobile/src/features/orders/ordersConstants.ts
mobile/src/features/sales/ShipConfirmView.vue
mobile/src/features/sales/shipConfirmModel.ts
mobile/src/features/stock/StockView.vue
mobile/src/features/stock/stockAdjustConstants.ts
mobile/src/shared/stores/salesPrefill.ts
server/app/api/dependencies.py
server/app/api/v1/router.py
server/app/routers/stock_adjust.py
server/app/schemas/stock_adjust.py
server/app/services/stock_adjust_api_service.py
server/tests/test_stock_adjust_service.py
ui/pages/stock_page.py
```

※ analysis mirror 경로 매핑: `features`→`views`, `shared/stores`→`composables/stores`, `server/app/*`→`server/*`

## 보완 2단계 — 판매 미리보기 (2026-08-20)

| 항목 | 값 |
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `7bc54293df34e1bcbfdc5f6f7de4bb4089610ffa` |
| 범위 | 재고 다건선택 → 판매미리보기 → DIRECT 확정 (1고객·1배송·N품목) |
| 제외 | 다배송지 / 부분배송 / Stage 7 / main merge |

### 핵심 파일

- `mobile/src/views/stock/StockView.vue` — 개별 판매 제거, sticky 판매미리보기, 판매예정 표시
- `mobile/src/views/sales/SalesPreviewView.vue` — 신규 미리보기 화면
- `mobile/src/composables/stores/salesPrefill.ts` — draft 병합·유지·삭제
- `core/order_ship_service.py` — `tot_ship_fee` / `dlvry_tp` / `t_sales_delivery` 저장
- `server/schemas/shipment.py`, `server/services/order_ship_api_service.py` — 배송 필드 전달

## 보완 2단계 보완수정 (2026-08-20)

| 항목 | 값 |
|------|-----|
| private SHA | `f6e35c65fcfb62c1e06ed60c28cf0879d37c747d` |
| 내용 | fixed 판매미리보기 바 · draft→판매예정 · STOCK 헤더 초기화/유지 · 배송 schema 검증 테스트 |

## 재고 목록 UX — 조회조건 카드 (2026-08-20)

| 항목 | 값 |
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `c6a6a0926f387af3dd1269ace306a94dd9096a16` |
| 내용 | 포장수량→판매수량 · 품종/중량/크기/등급 조회 · 돋보기/새로고침 · 조회조건을 OdsCard로 상품 리스트와 구분 |

### 핵심 파일

- `mobile/src/views/stock/StockView.vue`
- `mobile/src/__tests__/stockView.spec.ts`

## 보완 2A 최종 — 포장/저장일 사용자 노출 제거 (2026-08-20)

| 항목 | 값 |
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `7e70f51077315271685d970de147843fe6ada2b6` |
| 내용 | LOT 선택 Sheet 제거 · 상품 조정은 `adjust_by_sale_spec` · OUT FIFO 분할 · IN 기존 최신 source |

### 핵심 파일

- `mobile/src/views/stock/StockView.vue`
- `mobile/src/api/stock.ts`
- `core/stock_adjust_service.py`
- `server/routers|schemas|services/stock_adjust*`
- `server/tests/test_stock_adjust_service.py`

## 보완 2B — 판매 미리보기 리스트형 (2026-08-20)

| 항목 | 값 |
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `de5341735285075d09579e2248c6fc32b7986692` |
| 내용 | 카드형 품목 UI 제거 · divider 리스트 · 판매준비취소 · compact footer · 2A STOCK SSOT 유지 |

### 핵심 파일

- `mobile/src/views/sales/SalesPreviewView.vue`
- `mobile/src/__tests__/salesPreview.spec.ts`
