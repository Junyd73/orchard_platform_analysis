# 10. Stage 8 통합회귀 체크리스트

**역할:** Stage 8 실행용 **검증 목록**. 새 정책을 만들지 않는다. 설계 SSOT는 01~05·07~09, 구현상태 SSOT는 [06](./06_development_progress.md). 남은 일만 [11](./11_stage8_remaining_work.md).

**조사 기준 (2026-09-20 ③):** local HEAD **`a60a8ba`** (작성 시점) · 코드 `origin/main` **`63abc6e`**. 코드/DB mutation/배포 **없음**. dirty/stash **미포함**.

## OPS READ ONLY (2026-09-20, 이번 단계)

Lightsail 조회만. INSERT/UPDATE/DELETE 없음.

| 항목 | 결과 |
|------|------|
| backend git SHA | **`63abc6e`** (`style: refine juice stock registration action`) = `origin/main` 코드 |
| orchard-api | **active** |
| mobile/dist/index.html | mtime **2026-09-08 13:01** (서버 TZ). `63abc6e` 커밋(21:58 KST)과 같은 배포 창. **dist 내부 SHA 마커는 없음** |
| juice 신규 DDL | **없음** (`t_stock_master`/`t_stock_log` 재사용) |

**테이블 존재:** `t_order_alloc` · `t_harvest_consumption` · `t_auction_ship_master` · `t_auction_ship_detail` · `t_auction_match_detail` · `t_auction_qty_discrepancy` · `t_auction_return_line`

**컬럼 존재:** `t_order_master.pre_pay_method_cd` · `t_order_detail.allocated_qty` · `t_sales_detail.stock_seq` · `t_stock_log.stock_seq`/`ref_type`/`ref_id`

**OpenAPI 경로 존재:** `auction-shipments` (+ candidates/cancel/finalize/reopen) · `fruit-stock/initial` · `orders/.../allocations` · `sales` · `sales/{id}` · `sales/{id}/payments`

문서 충돌 실측:

| 충돌 | OPS 실측 | 판정 |
|------|----------|------|
| 02 Stage 3A 운영반영 vs 06 allocation DDL 미확인 | `t_order_alloc` + `allocated_qty` **존재** | **DDL은 OPS에 있음**. 06 미확인은 당시 미재확인. 01~09 문구는 DOC_ALIGNMENT |
| 08 DEC-028 DDL 미실행 vs 06 운영 완료 | `pre_pay_method_cd` **존재** | **08 문구 stale**. 컬럼은 OPS에 있음 |

실사용 시나리오 클릭 스모크는 **이번 단계 미수행** → Stage 8 REQUIRED.

## 숫자 요약 (③ 재분류)

| 구분 | 수 |
|------|----|
| **전체 체크항목** | **99** |
| **PASS** | **10** |
| **OPS-VERIFIED** | **70** |
| **IMPLEMENTED** | **2** |
| **IMPLEMENTED / OPS-UNVERIFIED** | **3** |
| **IMPLEMENTATION-INCOMPLETE** | **0** |
| **OPEN** | **7** |
| **DEFERRED** | **6** |
| **NOT-APPLICABLE** | **1** |
| **문서 정합 필요** | **10** (01~09 미수정. DOC-10은 OPS로 **사실 해소**, 문구는 남음) |

10+70+2+3+0+7+6+1 = **99**.

`OPS-UNVERIFIED`를 미완료로 치지 않음. 코드 있는 항목은 **OPS-VERIFIED** 또는 **IMPLEMENTED / OPS-UNVERIFIED**.

## 판정 규칙

| 상태 | 의미 |
|------|------|
| **PASS** | 코드 + **실사용 확인이 06에 남아 있고**, 이번 OPS에서 관련 DDL이 재확인됨 (DEC-035 계열, DEC-028, 선입금 배분) |
| **OPS-VERIFIED** | git 구현 + 이번 OPS에서 **SHA `63abc6e` 및 필요 DDL/OpenAPI**가 확인됨. **실사용 시나리오 PASS는 아님** |
| **IMPLEMENTED** | 코드 존재. 운영 배포 대상이 아니거나(레거시/의도적 PC 공백) |
| **IMPLEMENTED / OPS-UNVERIFIED** | git 구현. **PC 바이너리/실기기 반영은 미확인** (Lightsail과 별개) |
| **IMPLEMENTATION-INCOMPLETE** | 코드 없음/일부만. 이번 목록 **0건** (미착수는 OPEN·DEFERRED) |
| **OPEN** | 07 정책 미닫음 |
| **DEFERRED** | 후순위 (3B, PC UX, 문서) |
| **NOT-APPLICABLE** | 계약상 금지 |

---

## A. 주문

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| A01 | 주문 | 조회 | `OrderService` · `GET …/orders` | `OrderView.vue` | `order_page.py` | `t_order_master/detail` | SHA `63abc6e` | `test_order_api.py` · DEC-007 | **OPS-VERIFIED** | 스모크는 Stage8 |
| A02 | 주문 | 신규등록 | `create` · `POST …/orders` | `OrderNewView.vue` | `save_entire_order` | 주문 3테이블 | 동상 | T-ORD-01 · DEC-005 | **OPS-VERIFIED** | |
| A03 | 주문 | 수정 | `PUT …/orders/{order_no}` | `OrderDetailView.vue` | `order_page` | 상태별 제한 | 동상 | `OrderDetailView.spec.ts` | **OPS-VERIFIED** | |
| A04 | 주문 | 취소 | `POST …/cancel` | `OrderDetailView` | `order_page` | 미출고 배정 해제 | 동상 | `test_order_service.py` | **OPS-VERIFIED** | |
| A05 | 주문 | 주문확정 | `POST …/confirm` | `confirmOrder` | PC 상태 | ST01 | 동상 | DEC-011 | **OPS-VERIFIED** | 판매/OUT 아님 |
| A06 | 주문 | 고객 조회/등록 | `CustomerService` · `GET/POST …/customers` | `OrderNewView` | `m_customer` | `m_customer` | 동상 | `test_customer_service.py` | **OPS-VERIFIED** | |
| A07 | 주문 | 배송지 N건 | 주문 TX | `ParcelDestinationSheet` | `order_page` | `t_order_delivery` | 동상 | spec | **OPS-VERIFIED** | |
| A08 | 주문 | 선입금/결제수단 | `pre_pay_method_cd` · `AS0101` | 주문 폼 | `order_page` | 컬럼 **OPS 존재** | **PASS** + PRAGMA=1 | DEC-028 | **PASS** | 08「DDL 미실행」stale |
| A09 | 주문 | 배/배즙 혼합주문 | 라인 혼재 | `LABEL_PRODUCT_KIND` | 주문 품목 | `item_cd` | SHA `63abc6e` | `27d8dd2` | **OPS-VERIFIED** | 신규 DDL 없음 |
| A10 | 주문 | 배즙 leaf item_cd | FR010201/202 | `ordersConstants.ts` | juice combo | 소분류 | 동상 | spec | **OPS-VERIFIED** | FR010200 신규 제외 |
| A11 | 주문 | 실제재고 포장규격 | fruit-stock 옵션 | `orderJuiceModel.ts` | — | available>0 | 동상 | `44c85e4` | **OPS-VERIFIED** | |
| A12 | 주문 | 재고배정 HOLD | `OrderAllocationService` · `POST …/allocations` | **3B 없음** | Hold 키 | `t_order_alloc` **OPS 존재** | OpenAPI allocations | `test_order_allocation.py` · DEC-018 | **OPS-VERIFIED** | 3B는 A14. DDL 미적용 아님 |
| A13 | 주문 | 배정 RELEASE | `POST …/allocations/release` | 3B 없음 | PC 해제 | reserved | 동상 | 동상 | **OPS-VERIFIED** | |
| A14 | 주문 | 모바일 배정 UI (3B) | API 재사용 가능 | **미착수** | — | — | — | DEC-021 | **DEFERRED** | 코드 공백=후순위 |

---

## B. 수확/생산

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| B01 | 수확 | 영농일지 수확기록 | work-harvest | `WorkLogDailyWorkForm` | `work_log_page` | variety/qty 컬럼 | 실사용+SHA | T-HARVEST · DEC-022 | **PASS** | ≠ stock IN |
| B02 | 생산 | HARVEST N:M | `harvest_consumptions[]` | `PackProdPanel` | Core 위임 | `t_harvest_consumption` **존재** | E1/E2 + 재확인 | DEC-035 | **PASS** | |
| B03 | 생산 | 부분소진/잔량 | remaining 계산 | PackProd | 선택 qty | `is_valid=1` | 동상 | OPEN-DONE≠잔량 SSOT | **PASS** | H03 |
| B04 | 생산 | PACK + HARVEST | PACK+HARVEST | 복수 선택 | `save_production_log` | consumption+IN | 동상 | `packProd.spec.ts` | **PASS** | |
| B05 | 생산 | PACK + RAW_STOCK | RAW_STOCK | PackProd 원물 | 원물 투입 | 원물 OUT | SHA `63abc6e` | T-PROD · RAW E2E CAN-DEFER | **OPS-VERIFIED** | 실사용 RAW는 CAN-DEFER |
| B06 | 생산 | PROCESS + RAW_STOCK | juice leaf | `juice_item_cd` | `juice_kind_combo` | 배즙 IN | 동상 | `packProd.spec.ts` | **OPS-VERIFIED** | 09 FR010200 미구현 stale |
| B07 | 생산 | PROCESS + HARVEST | Core **거부** | 비노출 | 동일 | — | — | 가드 | **NOT-APPLICABLE** | |
| B08 | 생산 | 동일 품종/연도 | confirm 검증 | 필터 | 필터 | — | PASS 경로 | tests | **PASS** | |
| B09 | 생산 | 상품 전량 IN | confirm TX | prefill | Core | stock IN | PASS | DEC-023 | **PASS** | |
| B10 | 생산 | production trace | `ref_type=PRODUCTION` | — | Core | `t_stock_log.ref_*` **OPS 존재** | PRAGMA | `e12bf96` | **PASS** | |
| B11 | 생산 | 수확기록 기간 필터 | harvest-records from/to | PackProd | — | SELECT | SHA `63abc6e` | `bcff8a8` | **OPS-VERIFIED** | |

---

## C. 재고

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| C01 | 재고 | 상품/원물/배즙 조회 | `GET …/fruit-stock` | `StockView` 3탭 | `stock_page` | `t_stock_master` | SHA `63abc6e` | `stockView.spec.ts` | **OPS-VERIFIED** | |
| C02 | 재고 | available = in−out−reserved | Core 계산 | 가용 표시 | 가용 | 계산 | 동상 | 즉시 OUT 공식 | **OPS-VERIFIED** | 스모크 REQUIRED |
| C03 | 재고 | include zero | query | 재고(0)포함 | — | — | 동상 | | **OPS-VERIFIED** | |
| C04 | 재고 | 이력 | `GET …/logs` | 이력 | 실사 | `t_stock_log` | 동상 | | **OPS-VERIFIED** | |
| C05 | 재고 | 재고조정 | `POST …/adjust` | StockView | audit/dispose | TX | 동상 | `test_stock_adjust_service.py` | **OPS-VERIFIED** | |
| C06 | 재고 | 배즙 신규재고 | `POST …/fruit-stock/initial` · `StockInitialSheet` | 배즙탭 | — | 기존 master | OpenAPI initial | `09147d9` | **OPS-VERIFIED** | 신규 테이블 없음 |
| C07 | 재고 | initial atomic TX | BEGIN IMMEDIATE master+IN+log | 동일 | — | 기존 테이블 | 동상 | tests | **OPS-VERIFIED** | |
| C08 | 재고 | duplicate spec | `STOCK_SPEC_EXISTS` | 한글 | — | 자연키 | 동상 | | **OPS-VERIFIED** | |
| C09 | 재고 | `품목명 · 포장규격` | — | `juiceLineSummaryText` | — | grade_nm | 동상 | `3d7a21a` | **OPS-VERIFIED** | |
| C10 | 재고 | 직접판매 선택 | — | 담기 → ship | prefill | — | 동상 | `stockSaleList.ts` | **OPS-VERIFIED** | |
| C11 | 재고 | `+ 재고 등록` UX | — | 필터바 | — | — | 동상 | `63abc6e` | **OPS-VERIFIED** | SHA=OPS HEAD |

---

## D. 주문출고 / 직접판매

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| D01 | 출고 | STOCK | `POST …/shipments/confirm` | `ShipConfirmView` | 미위임 | alloc shipped | SHA `63abc6e` | T-SHP-01 · DEC-027 | **OPS-VERIFIED** | |
| D02 | 출고 | DIRECT | FIFO OUT | ShipConfirm | — | alloc 불변 | 동상 | DEC-020 | **OPS-VERIFIED** | 저장필드 H05 |
| D03 | 출고 | FIFO | Core FIFO | — | — | storage_dt | 동상 | | **OPS-VERIFIED** | |
| D04 | 출고 | reserved 해제 | reserved− | — | — | reserved_qty | 동상 | | **OPS-VERIFIED** | |
| D05 | 출고 | OUT | SALE log | — | — | `t_stock_log` | 동상 | | **OPS-VERIFIED** | |
| D06 | 출고 | sales 생성 | 출고1=판매1 | 판매탭 | — | `t_sales_*` | 동상 | DEC-017 | **OPS-VERIFIED** | |
| D07 | 출고 | stock_seq trace | 1 detail=1 seq | — | — | stock_seq/ref_* **OPS 존재** | PRAGMA | DEC-027 | **OPS-VERIFIED** | DDL 미적용 아님 |
| D08 | 출고 | 부분/전량 | ST010300/400 | remaining_order | — | 계산 | 동상 | T-SHP-04 | **OPS-VERIFIED** | |
| D09 | 출고 | 배송정보 | delivery link | Step3 | — | `t_sales_delivery` | 동상 | step3 tests | **OPS-VERIFIED** | ≠ DEC-016 |
| D10 | 출고 | 선입금 자동배분 | DEC-019 | 출고 TX | order_no 보존 | cash.order_no | **PASS** `fb413a3` | T-SHP-05 | **PASS** | |
| D11 | 출고 | DIRECT 판매분류 | SA 축 | Select | — | class 컬럼 | SHA `63abc6e` | S4A | **OPS-VERIFIED** | 06「미배포」는 SHA상 stale |

---

## E. 판매

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| E01 | 판매 | 목록 | `GET …/sales` | `SalesLookupPanel` | `sales_page` | master | OpenAPI + SHA | `salesList.spec.ts` | **OPS-VERIFIED** | 이후 UX도 63abc6e |
| E02 | 판매 | 상세 | `GET …/sales/{id}` | `SalesDetailView` | `sales_page` | SELECT | OpenAPI | 6A · spec | **OPS-VERIFIED** | 06「6A 미배포」stale |
| E03 | 판매 | 고객/판매경로 | sales_source | party | PC | join | 동상 | `3cfc8d0` | **OPS-VERIFIED** | |
| E04 | 판매 | 판매박스수 | qty 합 | 상품/경매 중량 | — | detail.qty | 동상 | `3b097f3` | **OPS-VERIFIED** | |
| E05 | 판매 | 판매/수금/미수 | cash SUM | 목록·상세 | summary | cash | 동상 | DEC-029 | **OPS-VERIFIED** | |
| E06 | 판매 | payment_status | compute_* | 라벨 | — | 계산 | SHA | 6-0 tests | **OPS-VERIFIED** | |
| E07 | 판매 | 수금조회 | `GET …/payments` | 이력 | read-only | cash 행 | OpenAPI | 6B | **OPS-VERIFIED** | |
| E08 | 판매 | 수금등록 | `POST …/payments` | inline | 7B-2 UI | cash+ledger | OpenAPI | 6C · DEC-030 | **OPS-VERIFIED** | Mobile 경로. PC는 G04 |
| E09 | 판매 | append-only | add만 | PUT 없음 | 7B-1 | — | SHA | DEC-032~034 | **OPS-VERIFIED** | Mobile 계약 |
| E10 | 판매 | CANCELLED 제외 | not_cancelled SQL | 목록 | 집계 | sales_status | SHA | DEC-037 F | **OPS-VERIFIED** | |
| E11 | 판매 | 수금>미수 거부 | DEC-030 | 한글 | backstop | — | SHA | T-PAY-04 | **OPS-VERIFIED** | |

---

## F. 경매 (DEC-036/037)

코드·DDL·OpenAPI **OPS-VERIFIED**. **실사용 PASS 아님.**

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| F01 | 경매 | 상품 다중선택 | FIFO seq | `AuctionShipConfirmSheet` | 비SSOT | detail 1=1 seq | SHA+테이블 | `auctionShipFlow.spec.ts` | **OPS-VERIFIED** | |
| F02 | 경매 | 경매보내기 | `POST …/auction-shipments` | 확인 시트 | — | master/detail **존재** | OpenAPI | `3ec2032`/`af5d817` | **OPS-VERIFIED** | |
| F03 | 경매 | 즉시 OUT | AUCTION_SHIP OUT | — | — | out_qty | SHA | `28044dc` | **OPS-VERIFIED** | |
| F04 | 경매 | IN_TRANSIT | status | 출하중 목록 | — | status | SHA | `04b8a5c` | **OPS-VERIFIED** | |
| F05 | 경매 | 시장/법인 | `auction-markets/corporations` | 출하 시트 | 별경로 | snapshot | SHA | `a5cd835` | **OPS-VERIFIED** | OpenAPI 이번 필터 외, SHA 포함 |
| F06 | 경매 | 후보조회 | `GET …/auction-candidates` | `AuctionMatchSheet` | — | 저장 없음 | OpenAPI | `f806d07` | **OPS-VERIFIED** | |
| F07 | 경매 | settlement/realtime | 정산 우선 fallback | 라벨 | — | settlement read | SHA | Stage B | **OPS-VERIFIED** | |
| F08 | 경매 | kg→box | `settlement_box_qty` | 비교표 | — | DDL 없음 | SHA | `6c650d0` | **OPS-VERIFIED** | |
| F09 | 경매 | fruit_count_bucket | Core SSOT | 비교 키 | — | DDL 없음 | SHA | `8377f9d` | **OPS-VERIFIED** | |
| F10 | 경매 | 수량 비교 | diff_qty | 비교표 | — | — | SHA | `38f5e1f` | **OPS-VERIFIED** | dirty 시트 비근거 |
| F11 | 경매 | discrepancy | 유형 필수 | 선택 | — | discrepancy **존재** | 테이블 | finalize tests | **OPS-VERIFIED** | |
| F12 | 경매 | RETURN IN | 역FIFO IN | 반품 확인 | — | return_line **존재** | 테이블 | DEC-037 C | **OPS-VERIFIED** | ≠ F-4 |
| F13 | 경매 | finalize | `POST …/finalize` | 최종확인 | — | match+sales | OpenAPI | `7649fa9`/`ddc79a5` | **OPS-VERIFIED** | |
| F14 | 경매 | AUCTION sales | sales_source=AUCTION | provenance | — | t_sales_* | SHA | | **OPS-VERIFIED** | |
| F15 | 경매 | 추가 OUT 없음 | finalize OUT 0 | — | — | 재고 불변 | SHA | | **OPS-VERIFIED** | |
| F16 | 경매 | COMPLETED | status+sales_no | 필터 | — | status | SHA | | **OPS-VERIFIED** | |
| F17 | 경매 | cancel guard | `POST …/cancel` | cancel_allowed | — | CANCELLED | OpenAPI | | **OPS-VERIFIED** | |
| F18 | 경매 | reopen/correction | `POST …/reopen` | `AuctionReopenConfirmSheet` | — | is_valid=0 | OpenAPI | F-1~F-3 | **OPS-VERIFIED** | |
| F19 | 경매 | sale CANCELLED | soft cancel | 액션 없음 | 제외 | sales_status | SHA | | **OPS-VERIFIED** | |
| F20 | 경매 | 재매칭 | IN_TRANSIT 복귀 | Stage E 재사용 | — | — | SHA | | **OPS-VERIFIED** | |
| F21 | 경매 | source_key UNIQUE | 활성 UNIQUE | stale UX | — | index | SHA | `2fc49c9` | **OPS-VERIFIED** | |
| F22 | 경매 | match DDL | ensure_* | — | — | match 3테이블 **존재** | 테이블 목록 | 자동 ALTER 아님(이미 있음) | **OPS-VERIFIED** | |

---

## G. PC 정합

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| G01 | PC | HARVEST N:M 위임 | ProductionService | Mobile SSOT | `save_production_log` | consumption **존재** | E1 + 재확인 | client tests | **PASS** | |
| G02 | PC | HARVEST N:M 화면 UI 보완 | — | — | 06 별도 단계 | — | — | CAN-DEFER | **DEFERRED** | |
| G03 | PC | protected CONFIRMED | `is_shipment_confirmed_sale_locked` | — | `sales_page` | — | **PC 바이너리 미확인** | 7A tests · DEC-031 | **IMPLEMENTED / OPS-UNVERIFIED** | Lightsail≠PC exe |
| G04 | PC | 수금 append-only | 동일 Core | Mobile은 E08 | 7B-2 UI | cash | **PC 미확인** | 7B tests | **IMPLEMENTED / OPS-UNVERIFIED** | |
| G05 | PC | SalesPaymentService 공용화 | 동일 클래스 | POST payments | sales_page 호출 | — | **PC 미확인** | 08 A13 | **IMPLEMENTED / OPS-UNVERIFIED** | |
| G06 | PC | legacy AUCTION_RT | — | 비SSOT | `save_realtime_auction_draft` | DRAFT | 레거시 | DEC-010 SUPERSEDED | **IMPLEMENTED** | 정리 여부는 정책 |
| G07 | PC | 경매 출하/매칭 UI | REST 있음 | Mobile SSOT | **없음** | — | — | | **DEFERRED** | |
| G08 | PC | 출고 confirm 미위임 | FastAPI | `/orders/ship` | 비위임 | — | — | 5C | **IMPLEMENTED** | 의도적 |
| G09 | PC | 배즙 PROCESS leaf | ProductionService | PackProd | `juice_kind_combo` | leaf item | SHA `63abc6e` (API) | stock_page | **OPS-VERIFIED** | PC 콤보=동일 커밋 |

---

## H. 정책 OPEN / DEFERRED

| ID | 영역 | 기능 | Core/API | Mobile | PC | DB/DDL | OPS | 테스트/검증 | 상태 | 비고 |
|----|------|------|----------|--------|----|--------|-----|-------------|------|------|
| H01 | 정책 | F-4 reverse | reopen은 reject | 한글 409 | — | reverse **없음** | — | DEC-037 | **OPEN** | 미구현≠이번 INCOMPLETE 게이트 |
| H02 | 정책 | DEC-016 | finalize 배송행 미닫음 | — | AUCTION_RT도 없음 | delivery | — | 07 OPEN | **OPEN** | |
| H03 | 정책 | OPEN-DONE | DONE≠잔량 SSOT만 | — | work DONE | work_detail | — | 07 OPEN | **OPEN** | |
| H04 | 정책 | DEC-015 백필 | 백필 안 함 | — | — | alloc **이미 존재** | DDL 있음 · 백필 OPEN | preflight SQL | **OPEN** | 적용≠백필 |
| H05 | 정책 | DEC-020 저장 필드 | 축 APPROVED · 컬럼 OPEN | 비노출 | — | 미확정 | — | 07 | **OPEN** | |
| H06 | 정책 | DRAFT 필수 | 경매 v1 없음 | — | AUCTION_RT | — | — | CAN-DEFER | **DEFERRED** | |
| H07 | 정책 | OPEN-DATA-NEG-STOCK | 음수 비후보 | — | 로컬 | 로컬 | 운영 이관 전 | 06 | **OPEN** | |
| H08 | 배정 | 3B UX | =A14 | 미착수 | — | — | — | DEC-021 | **DEFERRED** | |
| H09 | 회계 | 경매 수수료/운송 | gross | — | — | — | — | | **OPEN** | |
| H10 | 문서 | 01~09 stale | — | — | — | — | OPS로 일부 사실 해소 | 아래 | **DEFERRED** | 01~09 수정 금지(본 단계) |

---

## 문서 정합 필요

01~09 **미수정**. 사실 해소와 문구 수정은 별개.

| # | 문서 | 지점 | 이번 OPS/코드 | 권장 |
|---|------|------|---------------|------|
| DOC-01 | 05 | 경매 **REST 없음** | OpenAPI에 auction 전 경로 | CURRENT API |
| DOC-02 | 05 | HARVEST N:M **미구현** | DDL+실사용 PASS | IMPLEMENTED |
| DOC-03 | 05 | transit 반영 미구현 | 즉시 OUT 공식 | 공식 수정 |
| DOC-04 | 05 | sales confirm/DEC-037 미구현 | 소매 POST/PUT 없음 · 경매 finalize 있음 | 분리 |
| DOC-05 | 09 | PROCESS FR010200 미구현 | leaf 201/202 | leaf 정합 |
| DOC-06 | 09 | 경매출하 미구현 | 테이블+REST OPS | CURRENT |
| DOC-07 | 01 | 경매 DDL·코드 미적용 | SHA `63abc6e` + 테이블 | 층 분리 |
| DOC-08 | 03 | 출하 DDL OPEN | 테이블 존재 | PHYSICAL vs 과거 OPEN |
| DOC-09 | 04 | 경매 화면 없음 | Auction*Sheet | CURRENT 화면 |
| DOC-10 | 02 / 08 | 3A 운영 vs alloc 미확인 · 08 DDL 미실행 | **alloc 테이블+allocated_qty+pre_pay 컬럼 OPS 존재** | 02에 가깝고 08 stale. 06 미확인은 해소 |

---

## Stage 8 실행 시 주의

- **DDL 일괄 적용은 남은 일이 아님** (필요 테이블/컬럼 OPS 존재).
- 남은 핵심은 **기능 스모크 · backup/rollback · PC 후속 · 정책 OPEN · 01~09 문구**.
- 상세: [11](./11_stage8_remaining_work.md).
