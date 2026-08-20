# Stage 6 Ship/Stock UX — Analysis Review Branch

검수 전용 브랜치. **analysis `main`은 변경하지 않았습니다.**

## Private 기준

| 항목 | SHA / 브랜치 |
|------|----------------|
| base | `c6e5edb93fa5234b7314ea9135aa48204138461d` (`main`) |
| feature | `6f74eb5628fedb12759ef1d5954b6d007841154a` |
| branch | `cursor/stage6-ship-stock-ux` |

## Review branch 목적

ChatGPT/대표가 Stage 6 P0~P3 실제 소스를 `orchard_platform_analysis`에서 직접 diff 검증.

- 영구 mirror whitelist 확대 **아님**
- Core 3종 + PC `stock_page.py`는 **이번 review branch 한시 포함**

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
| Python (adjust/ship/alloc/production) | 64 OK |
| 관련 vitest | 56 OK |
| 전체 vitest | 258/260 (AiAnalysisPanel 2건 baseline) |
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
