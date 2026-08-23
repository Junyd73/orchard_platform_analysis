# 05. API contract — 초안

> **범위:** 주문/판매/재고 조회 API. Stage 3A/5A allocation · Stage P 생산 · Stage 5B fruit-stock **구현 완료** (운영 DDL 미적용).  
> Stage 5C Core `OrderShipService.confirm()` **구현**. FastAPI `shipments` **마운트**. Mobile client `confirmShipment`. DEC-020 = **출고방식 축**.  
> 마운트: `server/app/main.py` → `/api/v1` + `router.py`.  
> PC와 FastAPI가 SQL을 복제하지 않음. `core.order_service.OrderService` (DEC-007).

기존 패턴: `/api/v1/farms/{farm_cd}/…`, Header `X-User-Id`.  
날짜 요청/응답: **`YYYY-MM-DD`**. 내부 저장 신규도 ISO (DEC-012). 읽기는 YYYYMMDD 호환.  
오류: 기존 `BusinessRuleError` / HTTP 4xx.

---

## 0. 공통서비스 (가칭 · 아키텍처 미확정)

이름은 기존 `*Service` / `DBManager` / `AccountManager` 관례. 신규 계층을 지금 고정하지 않음.

| 가칭 | 책임 | API |
|------|------|-----|
| OrderService | 주문 3테이블 CRUD·취소 (판매 INSERT 금지) | orders |
| OrderAllocationService | 배정/해제 + reserved + log + allocated_qty | allocations |
| OrderShipService | 소매 출고확정 **단일 TX** | ship |
| StockQueryService | `get_stock_map` | fruit-stock |
| SalesService | 직접판매 저장, 경매 DRAFT, PUT 시 `order_no` 보존 | sales |
| SalesConfirmService | 가락 DRAFT 확정+출고 **단일 TX** | confirm |
| CustomerService | 검색·등록 | customers |
| AccountManager | `sync_ledger_by_basket` (**기존 엔진 그대로**. 모바일 전용 회계 엔진 금지) | payment / 출고 시 선입금 적용 |
| DBManager | `generate_sales_no` + **신설** `generate_order_no` | 채번 |

FastAPI 라우터는 위 함수만 호출.

---

## 1. customers

| method | path | 설명 |
|--------|------|------|
| GET | `/farms/{farm_cd}/customers` | `q`, `use_yn=Y`. Stage 2 (`m_customer`) |
| GET | `/farms/{farm_cd}/customers/{custm_id}` | 상세 — Stage 2 비범위 |
| POST | `/farms/{farm_cd}/customers` | 신규등록 — Stage 2 보완. PC 주문 팝업 SSOT (`C`+`yyMMddHHmmss`, `custm_tp=CT01`). 모바일 전용 테이블 금지 |

Stage 2: 목록 GET + 신규 POST. 고객 테이블은 `m_customer`만.

---

## 2. stock (과일)

| method | path | 설명 |
|--------|------|------|
| GET | `/farms/{farm_cd}/fruit-stock` | Stage 5B. `include_zero` 기본 false(소진 숨김). 응답 `real_qty`/`reserved_qty`/`available_qty` Core 계산 |
| GET | `/farms/{farm_cd}/fruit-stock/logs` | Stage 5B 이력 read-only (`t_stock_log`) |
| GET | `/farms/{farm_cd}/production/harvest-records` | 수확기록 조회 (Stage P) |
| GET | `/farms/{farm_cd}/production/raw-stock` | 원물재고 조회 (Stage P) |
| POST | `/farms/{farm_cd}/production/confirm` | 생산확정 1 TX. `raw_consumptions`는 qty>0만. N건 OUT+IN 전체 rollback |

경로 prefix는 클라이언트가 이미 `/api/v1`을 붙이므로 **`/farms/...`**.  
응답: `real_qty=in-out`, `available_qty=real-reserved`. **클라이언트가 가용재고를 재계산하지 않음.**  
쓰기(임의 입고/출고) 5B 비범위.

---

## 3. orders — 등록은 재고 없어도 성공

| method | path | Stage 2 |
|--------|------|---------|
| GET | `/farms/{farm_cd}/orders` | 구현 |
| GET | `/farms/{farm_cd}/orders/{order_no}` | 구현 |
| POST | `/farms/{farm_cd}/orders` | 구현. 재고 0이어도 200 |
| PUT | `/farms/{farm_cd}/orders/{order_no}` | Stage 2 구현. Stage 3A: allocated 규격 잠금, qty≥allocated |
| POST | `/farms/{farm_cd}/orders/{order_no}/cancel` | Stage 2 구현. Stage 3A: 미출고 배정 동일 TX 해제 |

POST 본문 초안: 고객, `order_dt`(ISO), 시즌, `pre_pay_amt`, **`pre_pay_method_cd`**, lines(규격+`qty`), deliveries.

검증: 고객, 줄≥1, 줄 qty=배송 합, 방문 외 주소. **`available < qty`여도 200.** `warnings[]` 선택.

**TX:** `t_order_master` + `detail` + `delivery`만.  
`allocated_qty=0`. `order_dt` ISO.  
**금지:** `t_sales_*`, `reserved_qty` Hold, `t_cash_ledger`, `t_ledger`.

PUT: `stock_status=Y` → 409. 부분출고(`shipped_qty>0`) 후 주문 헤더/줄 수정은 1차 거부 권고.  
cancel: `shipped_qty>0`이면 409 (출고 전만). 배정분 CANCEL_HOLD는 **`t_order_alloc` 행 단위** (DEC-018). 이미 출고된 allocation은 단순 취소 금지.

### 3.1 선입금 결제수단 (DEC-028 APPROVED · **완료·운영**)

POST / PUT 공통 필드. `t_order_master.pre_pay_method_cd` 운영 반영됨.

| 필드 | 타입 | 규칙 |
|------|------|------|
| `pre_pay_amt` | number | 기본 0. 음수 거부 |
| `pre_pay_method_cd` | string \| null | `pre_pay_amt = 0` → **null 강제**(값이 오면 400). `pre_pay_amt > 0` → **필수**(누락/공백이면 400) |

값 도메인: **현금성** `parent_cd=AS0101` · level4 · `use_yn=Y`. 채권(`AS02…`) 금지. 하드코딩 목록 금지.

**주문 API는 회계를 만들지 않는다** (DEC-009). 검증 SSOT = `core/order_service.py`.

---

## 4. 재고배정 — 저장재고형 주문의 선택 경로 (DEC-020)

allocation은 필수 단계가 아니다. `allocated_qty=0`인 주문은 정상이다.  
저장재고 출고를 선택한 주문만 이 API를 쓴다. 품종 if로 강제하지 않는다.

| method | path |
|--------|------|
| GET | `/farms/{farm_cd}/orders/{order_no}/allocations` |
| POST | `/farms/{farm_cd}/orders/{order_no}/allocations` |
| POST | `/farms/{farm_cd}/orders/{order_no}/allocations/release` |

배정 요청:

| 필드 | 의미 |
|------|------|
| `order_detail_id` | 필수 |
| `qty` | 생략 시 자동(가능한 만큼). 명시+`auto=false`면 **전량 가능해야 성공**(부족 시 409) |
| `auto` | `true`이면 `min(요청, 미배정, 가용)` 부분배정. T-ORD-02 (100/30→30) |

**동일 트랜잭션 (`BEGIN IMMEDIATE`):**

1. 줄 잠금/재조회: `allocated_qty + qty <= 주문 qty`
2. 가용재고를 TX 안에서 재조회 (`in-out-reserved`) — 초과 시 rollback
3. FIFO로 stock row 선택
4. `t_order_alloc` 증가/생성
5. `t_order_detail.allocated_qty +=` (누적)
6. 해당 stock row `reserved_qty +=`
7. `t_stock_log` HOLD (이력. 가능한 범위에서 줄·자연키)

배정해제: `release_qty <= allocated_qty - shipped_qty`. 기본 순서 **LIFO**(최근 잡은 행부터). `t_order_alloc` 감소, `allocated_qty −`, `reserved_qty −`, CANCEL_HOLD. 동일 TX.

단계 3A: `allocated_qty` + `t_order_alloc` migration (`core/order_alloc_migrate.py`). 운영 자동 실행 금지. **active reserved_qty>0 이면 중단**. historical HOLD 로그만으로는 중단하지 않음. 백필 없음 (DEC-015).

동시성: SQLite 트랜잭션 안에서 재검증 (위험 9·10).

---

## 5. delivery

주문 생성에 포함. 단독 수정:

| method | path |
|--------|------|
| PUT | `/farms/{farm_cd}/orders/{order_no}/deliveries` |

`t_sales_delivery`는 출고/확정 TX에서만.

---

## 6. 출고확정 — 재고 이동 + 판매생성 단일 TX (DEC-014 · DEC-020)

| method | path |
|--------|------|
| POST | `/farms/{farm_cd}/shipments/confirm` |

**Core:** `core/order_ship_service.py` `OrderShipService.confirm()` (DEC-027).  
**FastAPI:** `POST /api/v1/farms/{farm_cd}/shipments/confirm` (`app/routers/shipments.py`). 주문 전용 `/orders/{order_no}/ship` **없음** (무주문 DIRECT).  
요청에 출고방식 `STOCK` / `DIRECT`. **`stock_seq`는 클라이언트가 고르지 않음** — Core FIFO. 요청 extra 필드(`stock_seq` 포함)는 422.

### 6.A STOCK / 재고출고

저장재고 배정분에서 출고. `t_order_alloc` 필수. 주문 없음+STOCK **거부**.

`ship_qty <= allocated_qty - shipped_qty` (alloc 잔여).  
주문 잔여: `qty - SUM(CONFIRMED sales_detail)`. 과출고 거부 (`confirmed + request <= qty`). 완료는 `==`.

FIFO가 stock Nrow면 **`t_sales_detail` N행** (`stock_seq`마다 1행). 연결 테이블 없음.

**동일 트랜잭션 (`BEGIN IMMEDIATE`) — `confirm()` 소유:**

1. 미출고 `t_order_alloc` FIFO
2. 각 행 `shipped_qty +=` (`allocated_qty` 유지)
3. `reserved_qty −` · `out_qty +`
4. `t_stock_log` OUT (`stock_seq`, `ref_type=SALE`, `ref_id=sale_detail_no`)
5. 새 `t_sales_master` + 분할된 `t_sales_detail`
6. 잔량 있으면 `ST010300`, 전량이면 `ST010400` + `stock_status='Y'`

### 6.B DIRECT / 즉시출고

allocation/`shipped_qty` **미갱신**. 가용 FIFO로 stock row 선택. 결과 Nrow면 판매상세 N행. `stock_seq` 기록은 STOCK과 동일.  
주문 있으면 주문 잔여만 검증. 주문 없으면 직접판매. STOCK의 `ship_qty <= alloc 잔여`를 DIRECT에 적용하지 않음.

### 6.C 선입금 순차 배분 (DEC-019 APPROVED · 확정 설계)

confirm이 판매를 CONFIRMED로 만든 **같은 TX 안에서** 처리한다.

1. 그 주문의 남은 선입금 계산 = `t_order_master.pre_pay_amt − 그 주문 CONFIRMED 판매에 적용된 선입금 합`
2. 이번 회차 적용액 = `min(남은 선입금, 이번 판매금액)` — **판매금액 초과 금지**
3. 적용액 > 0이면 주문의 `pre_pay_method_cd`로 `t_cash_ledger` 기록 → `AccountManager.sync_ledger_by_basket('SALE', …)` → `t_ledger`
4. `tot_paid_amt` = 적용액, `tot_unpaid_amt` = 판매금액 − 적용액
5. 남은 선입금은 **다음 출고 confirm**에 순차 적용

**금지:** 이미 CONFIRMED 된 판매·전표를 이번 confirm에서 수정 · 첫 판매에 선입금 전액 부착 · `sales_status`를 수금 의미로 변경 (DEC-029).

예: 주문 30만 · 선입금 15만 → confirm①(판매 10만) 적용 10만·미수 0 → confirm②(판매 20만) 적용 5만·미수 15만.

**현재 구현 (Stage4 feature):** `OrderShipService.confirm()`이 동일 TX에서 순차 배분·`SalesPaymentService.add_payment_in_tx`(source_order_no)·cash SUM 동기화를 수행한다. main/운영 미반영. HTTP 응답 필드(적용액·잔액)는 미추가.

부분출고를 여러 번 호출할 수 있다. 매번 DEC-014 TX + 새 판매 1건 (DEC-017). Core·HTTP confirm **구현**. Mobile UI **후속**.

요청 요약: `ship_mode`, `sales_dt`, `order_no`(nullable), `custm_id`(nullable), `lines[]` (`order_detail_id` nullable, 규격, `qty>0`, `unit_price`).  
응답 요약: `ok`, `sales_no`, `sales_status=CONFIRMED`, `ship_mode`, `order_no`, `details[]`, `order_status`, `remaining_order[]`, `remaining_order_qty`.

**화면 SSOT (Stage 6):** 줄 잔여·다음 출고 = `remaining_order[]`. `remaining_order_qty`는 합 요약만. 완료 = `order_status`. 무주문이면 잔여 필드 비움.

HTTP: 검증 400 · 충돌/부족/SCHEMA_PRECONDITION 409 · 주문 없음 404 · envelope `{detail, error_code}`.

---

## 7. sales

| method | path |
|--------|------|
| GET | `/farms/{farm_cd}/sales` |
| GET | `/farms/{farm_cd}/sales/{sales_no}` |
| POST | `/farms/{farm_cd}/sales` |
| PUT | `/farms/{farm_cd}/sales/{sales_no}` |

### 7.1 GET 목록 (Stage 5 · feature · main/운영 미반영)

**Core:** `SalesQueryService.list_sales` (`core/sales_query_service.py`) — read-only.

**Query:** `from_date`, `to_date`, `sales_status` (`CONFIRMED` \| `DRAFT`), `payment_status` (`UNPAID` \| `PARTIAL` \| `PAID`), `keyword`, `page`(default 1), `page_size`(default 20, max 100).

**날짜:** `t_sales_master.sales_dt` · ISO·`YYYYMMDD` 혼재 조회(주문 목록과 동일 compact 비교). 일괄 변환 없음.

**수금 SSOT:** `paid_amt = SUM(t_cash_ledger.pay_amt)` (`farm_cd`+`sales_no`). `unpaid_amt = MAX(0, tot_sales_amt - paid_amt)`. master `tot_paid_amt`/`tot_unpaid_amt`는 목록 계산에 사용하지 않음.

**payment_status (응답 계산):** CONFIRMED만 — `UNPAID` / `PARTIAL` / `PAID`. DRAFT는 `null`(화면: 수금대기). 수금상태 필터 시 DRAFT 제외.

**payment_status filter (Core·SQL 동일 · 상호배타):** `UNPAID`=`paid<=0` · `PARTIAL`=`paid>0 AND paid<total` · `PAID`=`paid>0 AND (total-paid)<=0`. `total=0,paid=0`는 `UNPAID`만(0원 판매 PAID 승격 없음).

**날짜 validation:** malformed `from_date`/`to_date` → `SalesQueryValidationError` → HTTP 400. ISO·legacy `YYYYMMDD` 호환 유지. `from>to` swap 기존 동작 유지.

**대표상품:** 판매 1행. `t_sales_detail` 다건이어도 `sale_detail_no ASC` 첫 행. cash는 선 aggregate 후 join(cash×detail 곱집계 방지).

**응답:** `{ items[], total, page, page_size }` · item: `sales_no`, `sales_dt`, `custm_id`, `customer`, `order_no`, `sales_status`, `sales_source`, `tot_sales_amt`, `paid_amt`, `unpaid_amt`, `payment_status`, `rep_*`.

**미구현(Stage 5 범위 외):** GET/POST/PUT 상세·저장 · §8 payments HTTP.

PUT: 자식 재INSERT 시 **`order_no` / `sales_status` / `sales_source` 보존**. 재고는 ship/confirm만.  
DELETE 1차 비공개 (전표 역분개 전).

직접판매 POST: 출고 포함 플래그 시 재고+판매 한 TX (수출/도매).

---

## 8. payment — 판매확정 기준 수금/회계

> **Core (개발순서 3):** `SalesPaymentService` — CONFIRMED 추가수금 append · cash SSOT · AccountManager SALE 재사용. **feature 구현.** main/운영 반영은 별도 승인.  
> **HTTP GET/PUT:** 아직 **미구현** (개발순서 6 판매상세/수금등록).

| method | path | 용도 | 상태 |
|--------|------|------|------|
| GET | `/farms/{farm_cd}/sales/{sales_no}/payments` | 수금 내역 + 판매금액/수금액/미수금/수금상태 | **미구현** |
| PUT | `/farms/{farm_cd}/sales/{sales_no}/payments` | 수금 등록/갱신 | **미구현** |

**검증 (DEC-029 · Core 반영):**

| 항목 | 규칙 |
|------|------|
| 판매상태 | `sales_status = 'CONFIRMED'`만. **DRAFT 거부** |
| 수금액 | `> 0`. 미수 = `tot_sales_amt − SUM(cash)`. 초과 금지 |
| 결제수단 | **필수**. `parent_cd=AS0101` · level4 · `use_yn=Y`. 채권 금지 |
| 수금상태 | 응답 계산값 — `미수` / `부분수금` / `수금완료` ([03 §4.1](./03_data_contract.md)) |

**단일 트랜잭션:** ledger sync → cash append(+동일 method slip 갱신) → master paid/unpaid. 실패 시 전체 rollback.  
`add_payment_in_tx`는 caller-owned TX (4단계 OrderShip 재사용 예정).

`sales_status`는 수금으로 **변경되지 않는다** (DEC-029).  
일반 추가수금 `t_cash_ledger.order_no = NULL`. 선입금 자동적용 `order_no = 원 주문번호` (Stage4 feature · main 미반영).

---

## 9. 경매확정 — DRAFT→CONFIRMED + 재고출고 단일 TX (DEC-010)

| method | path |
|--------|------|
| POST | `/farms/{farm_cd}/sales/{sales_no}/confirm` |

TX: DRAFT 검증 → 가용 재조회 → out+log → CONFIRMED → 선택 수금/전표 → (DEC-016) 배송.  
부족 시 전체 rollback.  
초안 INSERT API는 단계 6에서 결정. 당분간 PC 시세 화면 유지 가능.

---

## 10. 트랜잭션 경계

| 유스케이스 | 한 트랜잭션 |
|------------|-------------|
| 주문 접수 | order 3테이블. 재고·판매·전표 없음 |
| 배정 | 줄 allocated + `t_order_alloc` + 지정 stock row reserved + HOLD + 그 row 가용 재검증 |
| 배정해제 | release ≤ reserved_unshipped. LIFO alloc 감소 + reserved − + allocated − + CANCEL_HOLD |
| 소매 출고 STOCK | alloc shipped+ / reserved− / out+ / OUT log + **새 판매 1건** + 출고분 배송 + 선입금 순차 적용 + cash/ledger + paid·unpaid (DEC-019 · 설계) |
| 소매 출고 DIRECT | allocation 없이 가용 FIFO + 판매상세 stock_seq 분할 (DEC-027). Core 후속 |
| 주문 취소(출고 전) | 상태. 미출고 `t_order_alloc`이 있으면 reserved 복구. 없으면 상태만 |
| 가락 확정 | status + out/log + 선택 전표 |
| 수금만 (CONFIRMED 판매) | cash + `AccountManager` + ledger + `tot_paid_amt`/`tot_unpaid_amt`. DRAFT 금지 (DEC-029) |

---

## 11. FastAPI 현황 (재확인)

`router.py`: health, farms, observations*, pesticide, smart_spray, work_logs, weather, work_photos, work_schedules(410), google_calendar, notifications, common_codes, **orders, sales(GET 목록), customers, fruit-stock, fruit-stock/adjust, production, shipments**.

**Stage 5 (feature · main/운영 미반영):** `GET /farms/{farm_cd}/sales` · `SalesQueryService` · Mobile 판매탭 목록.

**Stage 3A (구현 완료):** GET/POST/PUT orders, allocations, GET fruit-stock.

**Stage P (구현 완료 · 로컬):** GET harvest-records, GET raw-stock, POST production/confirm.  
PROCESS 요청 `juice_item_cd`: `FR010202` 일반배즙(기본) · `FR010201` 도라지배즙. 중분류 `FR010200` 거부. PACK은 해당 필드 무시. 응답 `prefill_lines[].item_nm`. 도라지 원료/BOM 없음.

재고 조정: `POST /farms/{farm_cd}/fruit-stock/adjust` — `io_type` IN/OUT, `reason_cd`(중분류 `AD010100` 하위: 폐기·파손·증정·반품·실사차이·기타). 폐기/파손/증정은 OUT만, 반품은 IN만, 실사차이·기타는 IN/OUT. `t_ledger` 없음. 감액은 가용재고(`in-out-reserved`) 이하.

**Stage 5C Core+HTTP · Stage 6 1차 Mobile:** `OrderShipService.confirm()` · `POST /farms/{farm_cd}/shipments/confirm` · Vue `confirmShipment`. 운영 DDL 미적용.

**미구현:** `sales/{sales_no}/payments` GET/PUT HTTP (§8 · Core는 개발순서 3 완료) · 출고 confirm 선입금 배분은 Core feature 완료 · main/운영·HTTP 응답 확장 미반영.  
**완료·운영:** 주문 `pre_pay_method_cd` (§3.1 · DEC-028).
