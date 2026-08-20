# Stage 6 Ship/Stock UX ??Analysis Review Branch

ê²€???„ìš© ë¸Œëœì¹? **analysis `main`?€ ë³€ê²½í•˜ì§€ ?Šì•˜?µë‹ˆ??**

## Private ê¸°ì?

| ??ª© | SHA / ë¸Œëœì¹?|
|------|----------------|
| base | `c6e5edb93fa5234b7314ea9135aa48204138461d` (`main`) |
| feature | `de5341735285075d09579e2248c6fc32b7986692` (sales preview 2B list) |
| prior feature | `7e70f51077315271685d970de147843fe6ada2b6` |
| branch | `cursor/stage6-ship-stock-ux` |

## Review branch ëª©ì 

ChatGPT/?€?œê? Stage 6 P0~P3 ?¤ì œ ?ŒìŠ¤ë¥?`orchard_platform_analysis`?ì„œ ì§ì ‘ diff ê²€ì¦?

- ?êµ¬ mirror whitelist ?•ë? **?„ë‹˜**
- Core 3ì¢?+ PC `stock_page.py`??**?´ë²ˆ review branch ?œì‹œ ?¬í•¨**

## A/B ë³´ì™„ (2026-08-20)

### A ??ì£¼ë¬¸?ì„¸ ?”ì—¬?˜ëŸ‰ SSOT

- `core/order_ship_qty.py` ??CONFIRMED ?ë§¤ ?„ê³„ ê³µí†µ helper
- `core/order_service.py` ??`get_order` line??`confirmed_shipped_qty`, `remaining_order_qty`
- `core/order_ship_service.py` ??helper ?„ì„
- `server/schemas/order.py` ??`OrderLineOut` ?„ë“œ ì¶”ê?
- `mobile/src/views/orders/OrderDetailView.vue` ???œë²„ `remaining_order_qty` ?°ì„ 

### B ???¤ê±´ STOCK ?ˆìš©ì¡°ê±´

- `mobile/src/views/sales/shipConfirmModel.ts` ??`canUseStockMode`, confirm ì§ì „ ê²€ì¦?
- `mobile/src/views/sales/ShipConfirmView.vue` ??UI/validation
- `mobile/src/composables/stores/salesPrefill.ts` ??draft ê¸°ë³¸ ship_mode

## P0 ??ë°°ì¦™ ì¶œê³  ?œì‹œ

- `mobile/src/views/orders/ordersConstants.ts` ??`isJuiceItemCd`, `formatOrderLineSpec`
- natural key ë¯¸ë?ê²?

## P1 ???¤ê±´ ?ë§¤/ì¶œê³ 

- `mobile/src/composables/stores/salesPrefill.ts`
- `mobile/src/views/stock/StockView.vue`
- `mobile/src/views/orders/OrderDetailView.vue`
- ?¨ê±´ ? ì?, ??confirm = ??`sales_no`, ship_mode ?¨ì¼

## P2 ??ê²½ë¡œ/?ˆë‚´ ë¬¸êµ¬

- `mobile/src/views/sales/ShipConfirmView.vue`
- `mobile/src/views/sales/shipConfirmModel.ts`
- ?ˆì•½?‘ìˆ˜: ?Œì˜ˆ?½ì ‘???íƒœ?…ë‹ˆ????
- ST010200 ?íƒœë¨¸ì‹  ë¯¸ë?ê²?

## P3 ???¬ê³ ì¡°ì •

### Core (review ?œì‹œ ?¬í•¨)

- `core/stock_adjust_constants.py`
- `core/stock_adjust_service.py`
- `core/order_allocation_service.py` ???´ë ¥ `io_type_nm` ?¬ìœ ëª?

### API (whitelist)

- `server/routers/stock_adjust.py`
- `server/schemas/stock_adjust.py`
- `server/services/stock_adjust_api_service.py`

### Mobile / PC

- `mobile/src/views/stock/stockAdjustConstants.ts`
- `mobile/src/views/stock/StockView.vue`
- `mobile/src/api/stock.ts` (review ?œì‹œ ???µìƒ mirror ?œì™¸)
- `ui/pages/stock_page.py` ??PC ?ê¸° Core ?„ì„

### ?¬ìœ ì½”ë“œ AD01

| code | ëª?| IN/OUT |
|------|-----|--------|
| AD010101 | ?ê¸° | OUT |
| AD010102 | ?Œì† | OUT |
| AD010103 | ì¦ì • | OUT |
| AD010104 | ë°˜í’ˆ | IN |
| AD010105 | ?¤ì‚¬ì°¨ì´ | IN/OUT |
| AD010106 | ê¸°í? | IN/OUT |

## ?ŒìŠ¤??(review branch ?¬í•¨)

- `server/tests/test_stock_adjust_service.py`
- `mobile/src/__tests__/OrderDetailView.spec.ts`
- `mobile/src/__tests__/shipConfirm.spec.ts`
- `mobile/src/__tests__/stockView.spec.ts`
- `mobile/src/__tests__/stockAdjustConstants.spec.ts`

**ë¯¸í¬??** `OrderNewView.spec.ts` ??preflight ?´ë????¨í„´(?ŒìŠ¤??fixture `010-1111-xxxx`) ì°¨ë‹¨. private?ì„œ ë³„ë„ ?•ì¸.

## ê²€ì¦?ê²°ê³¼ (private feature commit ê¸°ì?)

| ?ì—­ | ê²°ê³¼ |
|------|------|
| Python (order ship/service, alloc, adjust, production) | 120 OK |
| ê´€??vitest (OrderDetailView, shipConfirm) | 31 OK |
| ?„ì²´ vitest | 265/267 (AiAnalysisPanel 2ê±?baseline) |
| build | OK |

### AiAnalysisPanel baseline (CASE 1)

main(`c6e5edb`)ê³?feature(`6f74eb5`) **?™ì¼ 2ê±??¤íŒ¨** ??Stage 6 ë¬´ê?.

1. `AI ?¤ë¥˜ ì½”ë“œ ë©”ì‹œì§€` ??`?”ê¸ˆ ?œí•œ` ë¯¸í‘œ??
2. `?•ì • ?¤íŒ¨ ???¤ë¥˜ ?œì‹œÂ·ê°€?´ë“œ ë¯¸í˜¸ì¶? ??`?•ì •???„ë³´ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤` ë¯¸í‘œ??

## Secret scan

- `scripts/mirror/preflight.py` ?µê³¼ (review ?¬í•¨ ?Œì¼)
- API key / password / env / DB ê²½ë¡œ ë¯¸í¬??

## Private commit ë³€ê²??Œì¼ (27)

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

??analysis mirror ê²½ë¡œ ë§¤í•‘: `features`??views`, `shared/stores`??composables/stores`, `server/app/*`??server/*`

## ë³´ì™„ 2?¨ê³„ ???ë§¤ ë¯¸ë¦¬ë³´ê¸° (2026-08-20)

| ??ª© | ê°?|
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `7bc54293df34e1bcbfdc5f6f7de4bb4089610ffa` |
| ë²”ìœ„ | ?¬ê³  ?¤ê±´? íƒ ???ë§¤ë¯¸ë¦¬ë³´ê¸° ??DIRECT ?•ì • (1ê³ ê°Â·1ë°°ì†¡Â·N?ˆëª©) |
| ?œì™¸ | ?¤ë°°?¡ì? / ë¶€ë¶„ë°°??/ Stage 7 / main merge |

### ?µì‹¬ ?Œì¼

- `mobile/src/views/stock/StockView.vue` ??ê°œë³„ ?ë§¤ ?œê±°, sticky ?ë§¤ë¯¸ë¦¬ë³´ê¸°, ?ë§¤?ˆì • ?œì‹œ
- `mobile/src/views/sales/SalesPreviewView.vue` ??? ê·œ ë¯¸ë¦¬ë³´ê¸° ?”ë©´
- `mobile/src/composables/stores/salesPrefill.ts` ??draft ë³‘í•©Â·? ì?Â·?? œ
- `core/order_ship_service.py` ??`tot_ship_fee` / `dlvry_tp` / `t_sales_delivery` ?€??
- `server/schemas/shipment.py`, `server/services/order_ship_api_service.py` ??ë°°ì†¡ ?„ë“œ ?„ë‹¬

## ë³´ì™„ 2?¨ê³„ ë³´ì™„?˜ì • (2026-08-20)

| ??ª© | ê°?|
|------|-----|
| private SHA | `f6e35c65fcfb62c1e06ed60c28cf0879d37c747d` |
| ?´ìš© | fixed ?ë§¤ë¯¸ë¦¬ë³´ê¸° ë°?Â· draft?’íŒë§¤ì˜ˆ??Â· STOCK ?¤ë” ì´ˆê¸°??? ì? Â· ë°°ì†¡ schema ê²€ì¦??ŒìŠ¤??|

## ?¬ê³  ëª©ë¡ UX ??ì¡°íšŒì¡°ê±´ ì¹´ë“œ (2026-08-20)

| ??ª© | ê°?|
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `c6a6a0926f387af3dd1269ace306a94dd9096a16` |
| ?´ìš© | ?¬ì¥?˜ëŸ‰?’íŒë§¤ìˆ˜??Â· ?ˆì¢…/ì¤‘ëŸ‰/?¬ê¸°/?±ê¸‰ ì¡°íšŒ Â· ?‹ë³´ê¸??ˆë¡œê³ ì¹¨ Â· ì¡°íšŒì¡°ê±´??OdsCardë¡??í’ˆ ë¦¬ìŠ¤?¸ì? êµ¬ë¶„ |

### ?µì‹¬ ?Œì¼

- `mobile/src/views/stock/StockView.vue`
- `mobile/src/__tests__/stockView.spec.ts`

## ë³´ì™„ 2A ìµœì¢… ???¬ì¥/?€?¥ì¼ ?¬ìš©???¸ì¶œ ?œê±° (2026-08-20)

| ??ª© | ê°?|
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `7e70f51077315271685d970de147843fe6ada2b6` |
| ?´ìš© | LOT ? íƒ Sheet ?œê±° Â· ?í’ˆ ì¡°ì •?€ `adjust_by_sale_spec` Â· OUT FIFO ë¶„í•  Â· IN ê¸°ì¡´ ìµœì‹  source |

### ?µì‹¬ ?Œì¼

- `mobile/src/views/stock/StockView.vue`
- `mobile/src/api/stock.ts`
- `core/stock_adjust_service.py`
- `server/routers|schemas|services/stock_adjust*`
- `server/tests/test_stock_adjust_service.py`

## ë³´ì™„ 2B ???ë§¤ ë¯¸ë¦¬ë³´ê¸° ë¦¬ìŠ¤?¸í˜• (2026-08-20)

| ??ª© | ê°?|
|------|-----|
| private branch | `cursor/stage6-ship-stock-ux` |
| private SHA | `0f2e14a264b7d2867d827d2e3b111e2e80c30fbd` |
| ?´ìš© | ì¹´ë“œ???ˆëª© UI ?œê±° Â· divider ë¦¬ìŠ¤??Â· ?ë§¤ì¤€ë¹„ì·¨??Â· compact footer Â· 2A STOCK SSOT ? ì? |

### ?µì‹¬ ?Œì¼

- `mobile/src/views/sales/SalesPreviewView.vue`
- `mobile/src/__tests__/salesPreview.spec.ts`
