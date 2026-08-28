# 05. API contract — 초안

> **범위:** 주문/판매/재고 조회 API. Stage 3A/5A allocation · Stage P 생산 · Stage 5B fruit-stock **구현 완료** (운영 DDL 미적용).
> Stage 5C Core `OrderShipService.confirm()` **구현**. FastAPI `shipments` **마운트**. Mobile client `confirmShipment`. DEC-020 = **출고방식 축**.
> 수확 N:M (DEC-035): **IMPLEMENTED IN GIT** · **REHEARSAL PASS** · **OPS PENDING**. 경매 출하·청과·판매확정: [DEC-036/037](./07_decisions.md) — **APPROVED LOGICAL (설계. 미구현).**
> 마운트: `server/app/main.py` → `/api/v1` + `router.py`.
> PC와 FastAPI가 SQL을 복제하지 않음. `core.order_service.OrderService` (DEC-007).

**표현 3층 (본 문서 전역):**

| 층 | 의미 |
|----|------|
| **CURRENT API** | 현재 FastAPI/Core에 실제 구현된 endpoint · request/response · TX |
| **IMPLEMENTED API** | git `main` DEC-035 HARVEST N:M 계약 (**ops 배포 전**) |
| **APPROVED LOGICAL API** | DEC-036/037 등 논리 API 책임 (**미구현**) |
| **OPEN API** | endpoint path · payload · DDL · 상태코드 · cardinality · 정책 미확정 |

APPROVED LOGICAL을 **IMPLEMENTED**처럼 쓰지 않는다. DEC-035 HARVEST는 **IMPLEMENTED API** (운영 activation = **OPS PENDING**).

기존 패턴: `/api/v1/farms/{farm_cd}/…`, Header `X-User-Id`.
날짜 요청/응답: **`YYYY-MM-DD`**. 내부 저장 신규도 ISO (DEC-012). 읽기는 YYYYMMDD 호환.
오류: 기존 `BusinessRuleError` / HTTP 4xx · envelope `{detail, error_code}`.

---

## 0. 공통 Core 책임 (논리 · 아키텍처 미확정)

**기존 구현 클래스** (`OrderService`, `OrderAllocationService`, `OrderShipService`, `ProductionService`, `SalesQueryService`, `SalesPaymentService` 등)는 CURRENT 사실로만 기술한다.

**금지:** `AuctionShipService`, `HarvestConsumptionService` 등 **신규 Service 클래스명을 본 문서에서 확정하지 않는다.**
아래는 **논리 책임**만 나열한다. 실제 Core 분리·명칭 = **OPEN** (구현 설계 단계).

| 논리 책임 | 내용 | 관련 API (CURRENT·LOGICAL) |
|-----------|------|---------------------------|
| 주문 CRUD | 주문 3테이블 · 판매 INSERT 금지 | orders (`OrderService`) |
| 재고배정 | reserved + HOLD + allocated_qty | allocations (`OrderAllocationService`) |
| 소매 출고확정 | 주문/DIRECT 판매+OUT **단일 TX** | `POST …/shipments/confirm` (`OrderShipService`) |
| 재고 조회 | fruit-stock read | `GET …/fruit-stock` |
| 생산확정 | PACK/PROCESS · RAW/HARVEST | `POST …/production/confirm` (`ProductionService`) |
| **수확 소진** | N:M · 잔량 SSOT · `harvest_consumptions[]` | harvest-records · confirm (**IMPLEMENTED**) |
| **경매 출하** | 출하중 SSOT · 가용 제외 | **LOGICAL · REST 없음** |
| **청과 확인/매칭** | 확인수량 별도 · 출하수량 불변 | **LOGICAL · REST 없음** |
| **경매 판매확정** | CONFIRMED+OUT+SA 자동 · 원자 TX | **LOGICAL · REST 없음** |
| 판매 조회·수금 | GET sales · payments append | sales (`SalesQueryService`, `SalesPaymentService`) |
| 고객 | 검색·등록 | customers |
| 회계 | `sync_ledger_by_basket` (기존 엔진) | payment / 출고 선입금 |
| 채번 | `generate_sales_no` · `generate_order_no` | `DBManager` |

**History — SUPERSEDED:** DEC-010 시절 문서의 `SalesConfirmService` = `AUCTION_RT DRAFT → CONFIRMED + OUT` **단일 TX** 가칭.
현행 목표 SSOT는 **DEC-036(출하)** + **DEC-037(판매확정)**. §9 History 참조.

FastAPI 라우터는 **CURRENT** 구현 Core만 호출. LOGICAL 책임은 구현 단계에서 기존 Core 확장 또는 분리 (**OPEN**).

---

## 1. customers

| method | path | 설명 |
|--------|------|------|
| GET | `/farms/{farm_cd}/customers` | `q`, `use_yn=Y`. Stage 2 (`m_customer`) |
| GET | `/farms/{farm_cd}/customers/{custm_id}` | 상세 — Stage 2 비범위 |
| POST | `/farms/{farm_cd}/customers` | 신규등록 — Stage 2 보완. PC 주문 팝업 SSOT (`C`+`yyMMddHHmmss`, `custm_tp=CT01`). 모바일 전용 테이블 금지 |

Stage 2: 목록 GET + 신규 POST. 고객 테이블은 `m_customer`만.

---

## 2. stock (과일) · production

경로 prefix: 클라이언트가 `/api/v1`을 붙이므로 **`/farms/...`**.

### 2.0 endpoint 목록

| method | path | CURRENT | APPROVED LOGICAL |
|--------|------|---------|------------------|
| GET | `/farms/{farm_cd}/fruit-stock` | Stage 5B · `available=real−reserved` | `available ≈ real − order_reserved − active_auction_transit` |
| GET | `/farms/{farm_cd}/fruit-stock/logs` | Stage 5B read-only | 유지 |
| GET | `/farms/{farm_cd}/production/harvest-records` | + `harvest_year` · `consumed_container_qty` · `remaining_container_qty` | 유지 |
| GET | `/farms/{farm_cd}/production/raw-stock` | 원물 가용 | 유지 |
| POST | `/farms/{farm_cd}/production/confirm` | HARVEST `harvest_consumptions[]` N:M | 유지 |

쓰기(임의 입고/출고) 5B 비범위. 재고 조정: `POST …/fruit-stock/adjust` (§11).

---

### 2.1 `GET …/production/harvest-records` (DEC-035)

**IMPLEMENTED API** (git `main` · ops activation **OPS PENDING**)

- Path: `GET /api/v1/farms/{farm_cd}/production/harvest-records`
- Core: `ProductionService.list_harvest_records` (`core/production_service.py`).
- Query: `variety_cd`, `limit` (기존과 동일).
- 응답 행 (`HarvestRecordOut`):
  - `work_id`, `work_dt`, `variety_cd`, `variety_nm`, `harvest_container_qty`
  - `harvest_year` — `work_dt` 연도
  - `consumed_container_qty` — `t_harvest_consumption` 유효 누적 (`is_valid=1`)
  - `remaining_container_qty` — `harvest_container_qty − consumed_container_qty`
- `t_harvest_consumption` 없으면 consumed=0 · remaining=원수확 (schema preflight 전 호환).

**OPEN API:** 별도 balance endpoint · OPEN-DONE.

---

### 2.2 `POST …/production/confirm` — HARVEST N:M (DEC-035)

**IMPLEMENTED API** (git `main` · ops activation **OPS PENDING**)

- Path: `POST /api/v1/farms/{farm_cd}/production/confirm`
- Core: `ProductionService.confirm` · FastAPI `ProductionApiService`.
- Header: `X-User-Id` (기존).

**HARVEST request (`ProductionConfirmRequest`):**

- `prod_type`: `PACK` | `PROCESS` (HARVEST는 `PACK`만)
- `input_source`: `HARVEST`
- `variety_cd`, `wh_cd`, `pack_weight`, `lines[]` — 기존 PACK 계약
- **`harvest_consumptions[]`** (필수, 1건 이상):
  - `work_id` — `t_work_detail.work_id`
  - `qty` — 사용 상자수 (≥1)
- **legacy reject:** `harvest_work_id` only · `work_ids` only · 빈 `harvest_consumptions` → `HARVEST_CONSUMPTIONS`
- RAW_STOCK 전용: `raw_consumptions[]` (HARVEST와 혼합 금지)

**서버 책임 (동일 TX · `BEGIN IMMEDIATE`):**

- schema preflight: `t_harvest_consumption` + production trace (`ref_type`/`ref_id`/`stock_seq`)
- TX 내 최신 `remaining_container_qty` 재검증 · overconsume **reject**
- 동일 `variety_cd` · 동일 `harvest_year` (DEC-026)
- `prod_confirm_id` 채번 (`PRD`+`YYYYMMDD`+`-`+SEQ) · N건 `t_harvest_consumption` INSERT
- 상품 **전량 IN** + `t_stock_log` `ref_type='PRODUCTION'` · `ref_id=prod_confirm_id`
- 실패 시 **전체 rollback**

**Response:** `{ ok, prefill_lines[] }` — 기존과 동일.

**RAW_STOCK:** `raw_consumptions[]` N건 · 사용량>잔여 거부 · 혼합 품종/연도 거부 — **변경 없음**.

**OPEN API:** **OPEN-DONE** — HARVEST `DONE` 최종 의미 ([07 DEC-035](./07_decisions.md)).

**금지:** 사용자에게 `prod_confirm_id` · 내부 `work_id` 입력 요구 · legacy `harvest_work_id` fallback.

---

### 2.3 `GET …/fruit-stock` — 가용수량 (DEC-036)

**CURRENT API**

- Core: `OrderAllocationService.get_available_stock`.
- `real_qty = in_qty − out_qty`
- **`available_qty = real_qty − reserved_qty`**
- `reserved_qty` = 주문 HOLD (`t_order_alloc` 연계).
- **클라이언트가 가용재고를 재계산하지 않음** (CURRENT 계약 유지).

**APPROVED LOGICAL API**

- 서버가 반환하는 **판매가능 가용** (`available_qty`):
  - `현재고 − 주문 HOLD − 유효 경매 출하중`
  - 개념: `available ≈ real − order_reserved − active_auction_transit`
- **반드시 보장할 API 계약 = `available_qty` 정확성.**
- `reserved_qty` 의미 **유지** (주문 HOLD 전용). 경매 출하를 `reserved_qty`에 **넣지 않음**.
- 경매 출하 시 `out_qty` **증가 없음**.
- `active_auction_transit` = **유효 출하 라인 집계** (DEC-036). `transit_qty` 단독 DB 컬럼 SSOT **금지**.

**OPEN API**

- 출하중 수량을 응답에 **별도 필드로 표시**할지 — **필수 계약 아님** (UI 설명용 **선택 후보**).
- 집계 SQL · OPEN-DDL · 별도 필드명.

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

### 6.0 경계 — 경매 출하와 분리 (DEC-036)

**CURRENT · 의미 불변:** 본 endpoint = 주문 STOCK/DIRECT **판매 생성 + 재고 OUT + allocation 소비 + 선입금**.

**경매 “넘기기”는 본 API가 아님:**

| | `shipments/confirm` | 경매 출하 (LOGICAL §9A) |
|--|---------------------|-------------------------|
| 판매 | 생성·CONFIRMED | **아님** |
| `out_qty` | 증가 | **증가 없음** |
| `reserved_qty` | STOCK 시 감소 | **변경 없음** |
| 출하중 SSOT | 해당 없음 | 유효 출하 라인 |

**기각:** `POST …/shipments/confirm`을 경매 출하 생성 API로 **재사용**하는 설계.

**공통 재사용 후보 (Core 내부만 · OPEN):** 가용 검증 helper · FIFO stock 선택 · `{detail, error_code}` envelope.

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

S4A: 무주문 DIRECT만 `sales_type_cd` / `sales_category_cd` 요청. **`SA020400`(경매판매) 클라이언트 선택 거부** (CURRENT). 경매 자동분류 = DEC-037 §9C.

### 6.C 선입금 순차 배분 (DEC-019 APPROVED · 확정 설계)

confirm이 판매를 CONFIRMED로 만든 **같은 TX 안에서** 처리한다.

1. 그 주문의 남은 선입금 계산 = `t_order_master.pre_pay_amt − 그 주문 CONFIRMED 판매에 적용된 선입금 합`
2. 이번 회차 적용액 = `min(남은 선입금, 이번 판매금액)` — **판매금액 초과 금지**
3. 적용액 > 0이면 주문의 `pre_pay_method_cd`로 `t_cash_ledger` 기록 → `AccountManager.sync_ledger_by_basket('SALE', …)` → `t_ledger`
4. `tot_paid_amt` = 적용액, `tot_unpaid_amt` = 판매금액 − 적용액
5. 남은 선입금은 **다음 출고 confirm**에 순차 적용

**금지:** 이미 CONFIRMED 된 판매·전표를 이번 confirm에서 수정 · 첫 판매에 선입금 전액 부착 · `sales_status`를 수금 의미로 변경 (DEC-029).

**현재 구현 (Stage4):** `OrderShipService.confirm()`이 동일 TX에서 순차 배분·`SalesPaymentService.add_payment_in_tx`(source_order_no)·cash SUM 동기화를 수행한다. **완료 · 운영** (backend/PC `fb413a3`). HTTP 응답 필드(적용액·잔액)는 미추가.

부분출고를 여러 번 호출할 수 있다. 매번 DEC-014 TX + 새 판매 1건 (DEC-017). Core·HTTP confirm **구현**. Mobile UI **후속**.

요청 요약: `ship_mode`, `sales_dt`, `order_no`(nullable), `custm_id`(nullable), `lines[]` (`order_detail_id` nullable, 규격, `qty>0`, `unit_price`).
응답 요약: `ok`, `sales_no`, `sales_status=CONFIRMED`, `ship_mode`, `order_no`, `details[]`, `order_status`, `remaining_order[]`, `remaining_order_qty`.

HTTP: 검증 400 · 충돌/부족/SCHEMA_PRECONDITION 409 · 주문 없음 404 · envelope `{detail, error_code}`.

---

## 7. sales

| method | path | CURRENT |
|--------|------|---------|
| GET | `/farms/{farm_cd}/sales` | **구현** (목록) |
| GET | `/farms/{farm_cd}/sales/{sales_no}` | **구현** (상세 · private main) |
| GET/POST | `…/sales/{sales_no}/payments` | **구현** (Stage6B/C · private main) |
| POST | `/farms/{farm_cd}/sales` | **미구현** |
| PUT | `/farms/{farm_cd}/sales/{sales_no}` | **미구현** |

### 7.1 GET 목록 (Stage 5 · 완료 · 운영)

**Core:** `SalesQueryService.list_sales` (`core/sales_query_service.py`) — read-only.

**Query:** `from_date`, `to_date`, `sales_status` (`CONFIRMED` \| `DRAFT`), `payment_status` (`UNPAID` \| `PARTIAL` \| `PAID`), `keyword`, `page`(default 1), `page_size`(default 20, max 100).

**수금 SSOT:** `paid_amt = SUM(t_cash_ledger.pay_amt)`. master `tot_paid_amt`/`tot_unpaid_amt`는 목록 계산에 사용하지 않음.

**응답 item:** `sales_no`, `sales_dt`, `custm_id`, `customer`, `order_no`, `sales_status`, `sales_source`, `tot_sales_amt`, `paid_amt`, `unpaid_amt`, `payment_status`, `rep_*`.

**CURRENT:** `sales_source=AUCTION_RT` + `sales_status=DRAFT` 건이 목록에 **나타날 수 있음** (PC `save_realtime_auction_draft`).
**DRAFT ≠ 경매 출하중 SSOT** (DEC-036).

**APPROVED LOGICAL:** 경매 **출하중** 목록을 sales GET에 **합치지 않음** (04 §6 · 별도 호출 §9A).
경매 **판매확정** 후 CONFIRMED 건은 기존 sales GET/상세/수금 **재사용 가능**.

**S4A 3분류 (`sales_type_cd` / `sales_category_cd` / `sales_route_cd`):**

| | CURRENT HTTP | TARGET |
|--|--------------|--------|
| 목록/상세 응답 | master 컬럼 **미포함** (rep_* 위주) | 경매 CONFIRMED 후 DB에 SA 자동 저장 (DEC-037) · 목록 노출 필요성 **OPEN** |
| 직접판매 출고 | `ShipConfirmRequest`로 입력 (경매구분 제외) | 경매확정 시 **서버 자동** · 사용자 선택 금지 |

### 7.2 GET 상세 (Stage6A · read-only · private main · 운영 미배포)

**Core:** `SalesQueryService.get_sale_detail` — SELECT only.

**Master:** `sales_no`, `sales_dt`, `custm_id`, `customer`, `order_no`, `sales_status`, `sales_source`, `tot_sales_amt`, `paid_amt`, `unpaid_amt`, `payment_status`.

**Lines:** `t_sales_detail` 원본 행 · `sale_detail_no ASC`. optional schema 방어 유지.

**미구현(6A 범위 외):** POST/PUT 저장 · payments PUT.

---

## 8. payment — 판매확정 기준 수금/회계

> **Core:** `SalesPaymentService` — CONFIRMED append · cash SSOT · AccountManager SALE 재사용. **완료 · 운영** (Stage4).
> **Stage6B/6C:** GET/POST payments · **private main · 운영 미배포**.

| method | path | 용도 | 상태 |
|--------|------|------|------|
| GET | `/farms/{farm_cd}/sales/{sales_no}/payments` | 수금 내역 + 요약 | Stage6B |
| POST | `/farms/{farm_cd}/sales/{sales_no}/payments` | 신규 일반수금 append | Stage6C |

**검증:** `sales_status = CONFIRMED`만 write · DRAFT 거부 (DEC-029).
**단일 TX:** ledger sync → cash append → master paid/unpaid. 실패 시 rollback.

`sales_status`는 수금으로 **변경되지 않는다** (DEC-029).

### 8.1 GET 수금내역 · 8.2 POST 수금등록

§8 상세 규칙(DEC-029 · DEC-030) 유지. Request: `{ pay_dt, pay_amt, pay_method_cd }`.
**금지:** PUT · 수금 수정/삭제 HTTP.

---

## 9. History — 경매확정 DEC-010 SUPERSEDED

> **과거 설계 (현행 정책 아님)**

| | |
|--|--|
| DEC | **DEC-010 SUPERSEDED** ([07](./07_decisions.md)) |
| 당시 논리 | `AUCTION_RT` DRAFT → `CONFIRMED` + 재고 OUT **단일 TX** |
| 문서상 endpoint | `POST /farms/{farm_cd}/sales/{sales_no}/confirm` |
| **CURRENT 사실** | 위 HTTP **미구현**. FastAPI `sales.py`에 `/confirm` **없음**. Core confirm 서비스 **없음**. |
| PC CURRENT | `MarketPricePage.save_realtime_auction_draft` → DRAFT INSERT only · **재고 미접촉** |

**승계:** DEC-010 **원자성**(확정+OUT 실패 시 rollback) → **DEC-037**.
**후계:** DEC-036 경매 출하 · DEC-037 판매확정 (§9A~C).

---

## 9A. 경매 출하 API 논리 (DEC-036)

**APPROVED LOGICAL · endpoint path 미확정 (OPEN).**

흐름: `상품 가용 → 경매 넘기기 → 출하중 → 청과 확인/매칭 → 판매확정`.

### 9A.1 출하 생성

**사용자 입력(개념):** 출하일 · 시장 · 법인 · 상품별 출하수량(규격집합).

**서버 자동(개념):** farm · 내부 출하 묶음 식별 · 실제 stock row 추적 · 상태 · 감사.

**금지:**

- `stock_seq` 클라이언트 직접 지정 **강제**
- 사용자 선택 상품 1행 = `stock_seq` 1행 **cardinality 확정**
- `reserved_qty` / `out_qty` 변경
- 판매 DRAFT 선행

**TX (원자 · 한 업무 경계):**

1. 최신 가용 재조회 (`§2.3` LOGICAL `available`)
2. 요청수량 검증
3. Core FIFO 등으로 **실제 stock row** 결정
4. 출하 묶음/라인 생성
5. **유효 출하중** 집계 반영
6. `reserved_qty` / `out_qty` **변경 없음**
7. 실패 시 **전체 rollback**

주문 HOLD와 경매 출하가 동일 재고를 동시에 소비하지 못하도록 **가용 재검증 + 출하 반영은 동일 TX**.

### 9A.2 출하 목록

**논리 응답(개념):** 내부 출하 묶음 식별 · 출하일 · 시장/법인명 · 품목 수 · 농장 출하 총수량 · 상태 · 청과 확인 여부.

내부 ID = routing용 가능 · **화면 기본 노출 대상 아님** (DEC-021).

**OPEN:** path · paging · OPEN-SHIP-STATE.

### 9A.3 출하 상세

**논리 표시(개념):** 규격 · 농장 출하수량 · 청과 확인수량 · 차이 · 경매 결과 · 매칭상태.

농장 출하수량 **원본 불변** · 확인수량 **별도**.

**OPEN:** §9B · **OPEN-AUCTION-MATCH-CARDINALITY** · stock row cardinality.

### 9A.4 출하 취소/정정

**OPEN:** endpoint · TX · OPEN-SHIP-STATE 연동. 본 문서에서 확정하지 않음.

---

## 9B. 청과 확인/매칭 API 논리 (DEC-036)

**CURRENT**

- PC: 실시간 경매 (`MarketPriceManager.fetch_real_time_data`) · `market_price_settlement` (스케줄러 적재).
- PC: `save_realtime_auction_draft` (수동 매핑 → DRAFT).
- **모바일 경매 매칭 REST 없음.**

**APPROVED LOGICAL — 필요 책임**

1. 해당 출하와 **매칭 가능한** 경매결과 조회
2. **농장 출하수량** 보존 (UPDATE 덮어쓰기 **금지**)
3. **청과 확인수량** 별도 보존
4. 가격/금액 연결
5. 매칭상태 관리

**자동매칭 API를 근거 없이 확정하지 않는다.**

**OPEN API**

- 조회 endpoint · 데이터 소스(PSIS/정산/실시간) · 자동 vs 수동 · write 방식 · 가격 SSOT
- **OPEN-AUCTION-MATCH-CARDINALITY** (아래)

### OPEN-AUCTION-MATCH-CARDINALITY

출하 라인 1건 ↔ 청과 경매결과 관계가 **1:1 · 1:N · N:M** 중 무엇인지 **실데이터 확인 전 확정하지 않는다.**

**금지:**

- 출하 라인에 **단가 1개만** 존재한다고 확정
- 출하 라인 1건 = 청과 결과 1건으로 API shape **고정**
- `confirmation_qty` · 단가 · 금액을 **단일 필드**로 물리 확정

UI에서 상품별 **합산 표시**는 가능. API/DB cardinality = **OPEN**.

---

## 9C. 경매 판매확정 API (DEC-037)

**APPROVED LOGICAL · endpoint path = OPEN.**

`POST …/sales/{sales_no}/confirm` (DEC-010)을 새 SSOT로 **당연시하지 않는다.**

### 9C.1 논리 TX (실패 시 전체 rollback)

1. 출하 묶음/라인 **유효성** 검증
2. 청과 확인/매칭 검증
3. **최종 승인 판매수량** 결정
4. 판매 **생성** 또는 기존 DRAFT → `CONFIRMED` (**DRAFT 필수 여부 = OPEN**)
5. `t_sales_detail` ↔ 실제 stock 추적 (cardinality OPEN-DDL)
6. 최종 승인수량 기준 **`out_qty` 증가**
7. `t_stock_log` SALE OUT (`ref_type=SALE`)
8. **S4A 자동** (사용자 SA 선택 **금지**):

| 축 | 코드 |
|----|------|
| 판매유형 | `SA010200` (도매) |
| 판매구분 | `SA020400` (경매판매) |
| 판매경로 | `SA030300` (경매연동) |

9. **최종 승인수량에 해당하는 출하중 정산** (아래 §9C.2)
10. (DEC-016 OPEN) `t_sales_delivery` 생성 여부 — **본 DEC에서 확정하지 않음**

### 9C.2 20 출하 / 19 확인 — OPEN-QTY-DIFF

**예:** 농장 출하 20 · 청과 확인 19 · 최종 승인 판매 19.

**확정된 논리:**

- 최종 승인 **19** → 판매 OUT **19** 가능
- 농장 출하 **20** 원본 유지 · 청과 확인 **19** 별도 유지

**OPEN-QTY-DIFF:** 남은 차이 1을 자동으로 가용복귀 · OUT · 감모 · 반입 · 재고조정 **하지 않는다**.

**표현 (필수):**

> 판매확정 시 **최종 승인수량에 해당하는 출하중 수량을 정산**한다.
> 출하수량과 최종 승인수량의 **미해결 차이분**이 이후 가용·출하중·조정 중 어디에 귀속되는지는 **OPEN-QTY-DIFF**이며 **임의 처리하지 않는다**.

**금지:** 「판매확정 시 출하중 **전체** 종료」 · 19 OUT = 출하 20 **자동 종료**.

**OPEN:** 차이가 있는 출하의 판매확정 API **허용/거부** · HTTP 거부 여부.

---

## 9D. 시장/법인 API (OPEN)

**CURRENT**

- 모바일 **전용 시장 REST 없음**.
- `GET …/customers` — `m_customer` (법인/고객 후보 **가능** · 시장 FK **없음**).
- `GET /common-codes?farm_cd&parent_cd` — 품목/규격 등 · **시장 목록 SSOT 아님**.
- PC: 시장명은 실시간 API distinct · 일부 **하드코드 맵** (`ANALYSIS_MARKET_CODE_BY_NAME` 등). **신규 API 계약으로 승격 금지**.

**APPROVED LOGICAL (04 UX)**

- 최근 **유효** 시장+법인 조합 자동
- 시장 변경 시 법인 **유효성 재검증** · 무효 시 법인 초기화

**OPEN API**

- 시장 목록 endpoint
- 법인 조회/filter · 시장↔법인 **유효조합** 검증
- 최근 조합 **저장/조회** 위치

---

## 10. 트랜잭션 경계

| 유스케이스 | 층 | 한 트랜잭션 |
|------------|-----|-------------|
| 주문 접수 | CURRENT | order 3테이블. 재고·판매·전표 없음 |
| 배정 | CURRENT | 줄 allocated + `t_order_alloc` + reserved + HOLD + 가용 재검증 |
| 배정해제 | CURRENT | LIFO release + reserved − + CANCEL_HOLD |
| 소매 출고 STOCK | CURRENT | alloc shipped+ / reserved− / out+ / OUT log + 판매 1건 + 배송 + 선입금 + cash/ledger |
| 소매 출고 DIRECT | CURRENT | 가용 FIFO + 판매 + OUT (DEC-027) |
| 주문 취소(출고 전) | CURRENT | 상태 + 미출고 alloc reserved 복구 |
| 수금만 | CURRENT | cash + ledger + paid/unpaid. DRAFT 금지 |
| ~~가락 확정 (DEC-010)~~ | **SUPERSEDED** | ~~DRAFT + OUT~~ → §9 History |
| **HARVEST 생산확정** | LOGICAL | 잔량 재검증 → N건 소진 → 상품 전량 IN → 결과 → rollback |
| **경매 출하** | LOGICAL | 가용 재검증 → 출하 묶음/라인 → active 출하중 → **reserved/out 불변** → rollback |
| **경매 판매확정** | LOGICAL | 출하/매칭 검증 → 최종 승인수량 → CONFIRMED + OUT + SALE log + SA 자동 + **승인분 출하중 정산** → rollback |

미해결 출하/확인 **차이분** 처리 TX = **OPEN-QTY-DIFF** (본 표에 포함하지 않음).

### 10.1 오류 계약 후보

**패턴 유지:** 400 / 404 / 409 / 422 · `{detail, error_code}`.

**논리 오류 후보 (error_code 문자열 미확정):**

| 후보 | HTTP 후보 | 관련 |
|------|-----------|------|
| 수확 사용량 > 잔량 | 409 | §2.2 |
| 품종/연도 혼합 | 422 | §2.2 |
| 경매 출하 가용 부족 | 409 | §9A |
| 시장/법인 조합 오류 | 422 | §9D |
| 출하 상태 충돌 | 409 | OPEN-SHIP-STATE |
| 매칭 미완료 | 409 | §9B |
| 출하/확인 **차이** 존재 시 확정 시도 | 409 또는 422 | **OPEN-QTY-DIFF** |

---

## 11. FastAPI CURRENT 스냅샷

`router.py`: health, farms, observations*, work_logs, weather, common_codes, **orders, sales, customers, fruit-stock, fruit-stock/adjust, production, shipments**, …

| 영역 | CURRENT (사실) | LOGICAL | REST |
|------|------------------|---------|------|
| harvest-records | **구현** · 원수확만 | 잔량 개념 | 확장 **미구현** |
| production/confirm | **구현** · HARVEST **단일** | N:M | **미구현** |
| fruit-stock | **구현** · `real−reserved` | transit 반영 | **미구현** |
| shipments/confirm | **구현** · 판매+OUT | — | 유지 |
| sales GET/상세/payments | **구현** (payments private main) | 경매확정 후 재사용 | — |
| sales POST/PUT/confirm | **미구현** | DEC-037 | **미구현** |
| PC AUCTION_RT DRAFT | `save_realtime_auction_draft` | 출하 SSOT **아님** | PC only |
| 경매 출하 | — | DEC-036 | **없음** |
| 청과 매칭 | PC/DB only | DEC-036 | **없음** |
| 경매 판매확정 | — | DEC-037 | **없음** |

**Stage P (로컬):** harvest-records, raw-stock, production/confirm. PROCESS `juice_item_cd`: `FR010202`/`FR010201`.

**Stage 5C:** `OrderShipService.confirm()` · Mobile `confirmShipment`.

**금지:** 위 LOGICAL 행을 **IMPLEMENTED**로 표기.

판매목록 `rep_*` · Stage6B/C payments · 주문 `pre_pay_method_cd` (DEC-028) · Stage4 선입금 — 기존 §7·§8 상세 유지.

---

## 12. CURRENT / TARGET / OPEN 요약

| | |
|--|--|
| **CURRENT** | HARVEST 단일 · harvest balance 없음 · `available=real−reserved` · `/shipments/confirm`=판매+OUT · PC `AUCTION_RT`+DRAFT · 경매 confirm FastAPI/Core **없음** · 모바일 경매 출하/매칭 REST **없음** |
| **TARGET (LOGICAL)** | HARVEST N:M · 서버 잔량 · 정확한 `available_qty` · 경매 출하 생성/목록/상세 · 청과 확인/매칭 · DEC-037 판매확정 |
| **OPEN** | OPEN-DDL · OPEN-SHIP-STATE · OPEN-QTY-DIFF · OPEN-DONE · **OPEN-AUCTION-MATCH-CARDINALITY** · DEC-016 · DRAFT 필수 · endpoint path · payload 필드명 · 출하 취소/정정 · 차이 시 confirm 허용 · 시장/법인/최근값 API · 자동매칭 · stock/가격 cardinality · **실제 Core 클래스 구조** |
