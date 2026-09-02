# 03. Data contract — 기존 테이블 · 승인 논리계약

> **범위:** 주문/판매/재고 **기존** 테이블 + 수확 소진·경매 출하의 **승인된 논리 계약**.
> 업무 흐름: [09](./09_production_inventory_flow.md) · [02](./02_domain_flow.md). 정책: [07](./07_decisions.md).
> Stage 3A migration: `core/order_alloc_migrate.py` (로컬·테스트). 운영 자동 실행 금지.
> **`t_production_master`/`detail` 풀세트 생성 안 함** ([DEC-025](./07_decisions.md) · OPEN-PROD-01 **CLOSED**).

**문서 층 (혼동 금지):**

| 층 | 의미 |
|----|------|
| **CURRENT PHYSICAL** | 현재 실제 존재하는 테이블/컬럼/코드 계약 |
| **IMPLEMENTED PHYSICAL CONTRACT** | git `main`에 구현·문서화된 물리 계약 (DEC-035) — **OPS APPLIED** |
| **APPROVED LOGICAL** | DEC-036/037 등 승인 논리 요구 (**미구현일 수 있음**) |
| **APPROVED PHYSICAL DESIGN** | DEC-036 경매 출하 header/line **물리계약 확정** (**DDL·코드 미적용**) |
| **OPEN PHYSICAL** | 경매 출하 등 신규 테이블·상태코드 — **미확정** |
| **OPS APPLIED** | PC·Lightsail **운영 DB DDL** + code/deploy **적용 완료** |
| **OPERATIONAL PASS** | 실제 운영환경 PC/Mobile HARVEST N:M **실사용 확인** |
| **OPS PENDING** | *(과거)* 운영 미적용 — **DEC-035는 2026-08-31 종료** |

DEC-035 `t_harvest_consumption` · `prod_confirm_id` · production trace = **OPS APPLIED** · **OPERATIONAL PASS**.
경매 출하중 물리 DDL = **OPEN**. APPROVED LOGICAL을 운영 DB에 이미 있다고 쓰지 않는다.

운영 DB baseline (CURRENT):
`t_order_*`, `t_sales_*`, `t_stock_master/log`, `t_cash_ledger`, `t_ledger`, `m_customer`, `m_warehouse`, `m_common_code`.

### 품목 코드 (PC `StockPage` SSOT)

| item_cd | 의미 | 재고 역할 |
|---------|------|-----------|
| FR010300 | 원물 | 저장·생산 투입 |
| FR010100 | 배 상품 | 포장(PACK) 결과·주문 배정 대상 |
| FR010200 | 배즙(중분류) | 레거시 PROCESS 재고. 신규 생산은 소분류 사용 |
| FR010202 | 일반배즙 | PROCESS 결과 |
| FR010201 | 도라지배즙 | PROCESS 결과 |

생산확정(PC): 원물 OUT + 상품 IN + `t_stock_log`. 판매 테이블은 **생산 시점에 만들지 않음** (DEC-005).
수확 저장 ≠ stock 자동 IN ([DEC-022](./07_decisions.md) · [DEC-035](./07_decisions.md)).

---

## 1. `t_order_master`

| 항목 | 내용 |
|------|------|
| 목적 | 소매(및 일부 도매) 주문 헤더 |
| PK | 코드상 `order_no` 단일 조건. `farm_cd` 저장 |
| 채번 | `ORD`+`YYYYMMDD`+`-`+3자리. **core `generate_order_no`** (farm 스코프, TX 안 MAX). UUID 금지 |

| 컬럼 | 코드 사용 | 주문/판매 의미 | 모바일 | 수정 |
|------|-----------|----------------|--------|------|
| order_no | INSERT | PK | 필수 | 유지 |
| farm_cd | INSERT | 농장 | 세션 | 유지 |
| order_dt | 현재 `YYYYMMDD` | 주문일 | 신규 **YYYY-MM-DD** (DEC-012). 조회 시 혼재 파싱 | PC P0 |
| custm_id | INSERT | 고객 | 필수 | 유지 |
| status_cd | Stage 2 신규 `ST010100` | **주문상태만** (DEC-013). 운영 ST01 SSOT (DEC-011 CLOSED) | 표시 | PC `'10'`/`'20'` 폐기 |
| stock_status | `'N'` | 출고완료 플래그. `'Y'` 전환 없음 | 이행 계산에 사용 | 출고 TX에서 Y |
| tot_order_amt / tot_ship_fee / tot_pay_amt / pre_pay_amt | 금액 | 선입금은 전표 없음 (DEC-009) | 표시 | 유지 |
| **pre_pay_method_cd** | **TEXT NULL (운영 반영)** | 선입금 결제수단. `pre_pay_amt=0`이면 NULL, `>0`이면 필수 (DEC-028) | 선입금>0일 때만 입력 | **완료 · 운영** |
| season_type_cd | SS01 | 시즌 | 콤보 | 유지 |
| sales_no | Stage 2 신규는 빈 값 | **legacy/reference.** 출고 전 비움. 이후 최초 출고 판매번호만. **주문 전체 판매 조회는 반드시 `t_sales_master.order_no` 기준.** | | DEC-005 · **017 APPROVED** |
| rmk, reg_id, reg_dt, mod_* | 감사 | `now_ops_str` | 동일 | 유지 |

출고예정일 마스터 컬럼 **추가하지 않음.** `MIN(t_order_delivery.planned_dt)`.

### 1.1 선입금 결제수단 (DEC-028 APPROVED · **완료 · 운영**)

| 항목 | 내용 |
|------|------|
| 컬럼 | `t_order_master.pre_pay_method_cd TEXT NULL` |
| 값 도메인 | **현금성** `parent_cd='AS0101'` · level4 · `use_yn='Y'`. 운영: AS010101/102/103. 채권 제외 |
| 규칙 | `pre_pay_amt = 0` → NULL · `> 0` → 필수 |
| 회계 | 주문 저장 시 전표 **없음** (DEC-009) |

`prepay_balance` 같은 잔액 컬럼은 **만들지 않는다** (DEC-019, §9.1 계산식).

---

## 2. `t_order_detail`

| 컬럼 | 사용 | 의미 | 모바일 | 수정 |
|------|------|------|--------|------|
| order_detail_id | `{order_no}-{NN}` | 줄 PK. 판매 상세 연결키 | 필수 | 유지 |
| item/variety/grade/size_cd, weight, qty, unit_price, item_amt | 규격·**주문수량** | DEC-004 | 필수 | 유지 |
| harvest_year | 있음 | **원료 과실 수확연도** (DEC-026). 생산연도 아님. allocation 탐색 키 | 유지 | |
| wh_cd | 있음 | 기본 WH01 | 유지 | |
| dlvry_tp | LO01 | 행별 배송 | 유지 | |
| **allocated_qty** | **Stage 3A DDL** | **누적 배정수량** (Hold 잔량 아님) | 목록의 「배정」 | DEC-008. 운영 ALTER는 별도 승인 |

**계산값 컬럼을 추가하지 않음.** `allocated_qty=0`은 주문 오류가 아니다 (DEC-020).

```
unallocated_qty        = qty - allocated_qty
shipped_qty            = SUM(t_sales_detail.qty WHERE order_detail_id = 이 줄
                             AND 해당 판매 sales_status = CONFIRMED)
reserved_unshipped_qty = allocated_qty - shipped_qty   -- STOCK Hold 잔량
0 <= allocated_qty <= qty
0 <= shipped_qty <= qty
release_qty            <= allocated_qty - shipped_qty  -- STOCK 배정해제
```

STOCK 출고만: `ship_qty <= allocated_qty - shipped_qty`  
DIRECT 출고: allocation/HOLD 없이 `shipped_qty` 증가 가능. 생산수량 추적은 Stage 4 전 OPEN.  
`ship_mode` / stock·direct 플래그 컬럼은 이번 단계 추가 금지.

판매 상세에는 `harvest_year`가 **없다.**

### 2.1 `allocated_qty` 설계 (DEC-008 APPROVED, Stage 3A 로컬 DDL)

| 항목 | 권장안 |
|------|--------|
| 의미 | 저장재고 출고를 선택한 줄의 **누적 배정수량**. 모든 주문의 필수값이 아님 |
| 타입 | `qty`와 동일 계열 → **`REAL NOT NULL DEFAULT 0`** |
| 신규 주문 | 0 |
| 출고 후 | **유지**. 0 리셋 금지 |
| 배정해제 | `allocated_qty − release_qty`. 미출고분 초과 금지 |
| 줄 vs 행 | 총량만 저장. 행 분해는 `t_order_alloc` (DEC-018. **운영 반영됨** — 당시 문서: 로컬 CREATE) |

기존 주문 초기값: **백필 없음** (DEC-015). schema DEFAULT 0. active reserved가 있으면 DDL 중단.  
migration 직전 운영 점검 필수 → §15.

---

## 3. `t_order_delivery`

코드 INSERT:  
`order_dlvry_id, order_no, farm_cd, order_detail_id, snd_*, rcv_*, dlvry_qty, dlvry_msg, delivery_tp_cd, planned_dt, reg_dt`

- 채번 실제: `{order_detail_id}-P{NN}`
- 워크스페이스 규칙과 불일치. 코드 우선.
- `test_page.py` DDL은 운영 INSERT와 불일치 → 무시.

출고 TX에서 `t_sales_delivery`로 **그 출고분만큼만** 생성. 주문 배송계획 전체를 매번 복사하지 않음 (DEC-017). 상세 분할 알고리즘은 단계 4 전 재검토.

---

## 4. `t_sales_master`

문서 PK `(sales_no, farm_cd)`.

| 컬럼 | 문서 | 코드 | 설계 |
|------|------|------|------|
| sales_dt | YYYY-MM-DD | 판매화면 ISO / **주문경로 YYYYMMDD** | 신규 ISO (DEC-012). 과거 변환 없음 |
| sales_tp | RETAIL/WHOLE | 주문 `'NORMAL'` | 정리 제안, 1차 비범위 가능. **임의 폐기 금지** |
| sales_status / sales_source | 문서 없음 | ALTER 후 사용 | **`DRAFT`/`CONFIRMED` 두 값만** (DEC-029). ORDER/AUCTION_RT **호환 유지** |
| sales_type_cd / sales_category_cd / sales_route_cd | — | S4A canonical (**CURRENT PHYSICAL**) | 아래 §4.2. 경매 확정 자동값은 [DEC-037](./07_decisions.md) |
| tot_sales_amt / tot_paid_amt / tot_unpaid_amt | 있음 | 판매금액 / 수금액 / 미수금 | **수금 SSOT는 `t_cash_ledger` SUM.** master `tot_paid_amt`/`tot_unpaid_amt`는 동기화·조회용 (개발순서 3 `SalesPaymentService`) |
| order_no | 문서 없음 | 주문 INSERT만. **재저장 시 누락**. UNIQUE 없음 | 출고마다 동일 `order_no` 가능 → **주문 1:N 판매 SSOT** (DEC-017). 재저장 보존 |
| slip_no / pay_method_cd | 문서 있음 | 판매 INSERT 일부 | **N회·복수 결제수단 수금의 SSOT 아님.** Core는 이 두 필드를 수금으로 갱신하지 않음 |

채번: `generate_sales_no` vs 주문 `get_next_seq` 이중 → P0 공통화.

**경매·판매상태 경계:**
- **출하중은 `sales_status`가 아님** ([DEC-036](./07_decisions.md) · [02 §8.2](./02_domain_flow.md)).
- `SHIPPED` / `TRANSIT` 등 **신규 `sales_status` 금지**.
- **CURRENT:** `AUCTION_RT`+`DRAFT` 존재 가능. **출하중 SSOT가 아님**.
- 경매 **판매확정** = [DEC-037](./07_decisions.md) (`CONFIRMED` + OUT 원자 TX).

### 4.1 수금상태는 계산값 (DEC-029 APPROVED · Stage6-0 통일)

**수금상태 컬럼을 만들지 않는다.** `sales_status`에 수금 의미를 넣지 않는다.

**API/Core 코드 (`payment_status`):** `UNPAID` · `PARTIAL` · `PAID` · `null`
**UI label:** 미수 · 부분수금 · 수금완료 · 수금대기(DRAFT/`null`)

| API 코드 | 조건 (조회 시 **cash SUM 기준** `paid` / `unpaid`) | UI label |
|----------|------|----------|
| `null` | `sales_status != CONFIRMED` (DRAFT 등) | 수금대기 |
| `UNPAID` | CONFIRMED · `paid <= 0` (0원 판매 0/0 포함) | 미수 |
| `PARTIAL` | CONFIRMED · `0 < paid < tot_sales_amt` | 부분수금 |
| `PAID` | CONFIRMED · `unpaid <= 0` (`unpaid = MAX(0, total − paid)`) | 수금완료 |

`paid = SUM(t_cash_ledger.pay_amt WHERE farm_cd·sales_no)`. master `tot_paid_amt`/`tot_unpaid_amt`는 동기화 값.

**OPS 현재 회계 불변규칙 (Stage6-0):** 수금·지급 발생 여부가 전표 생성 조건이며, 전표 기준일(`t_ledger.trans_dt`)은 해당 업무의 업무일(`sales_dt`/`work_dt`)을 사용한다. `t_cash_ledger.pay_dt`는 실제 수금일 기록.

완료 개념 3종은 서로 다른 값에서 나온다.

| 용어 | 근거 |
|------|------|
| 판매확정 | `t_sales_master.sales_status = 'CONFIRMED'` |
| 주문완료 | `t_order_master.status_cd='ST010400'` AND `stock_status='Y'` |
| 수금완료 | CONFIRMED · `payment_status = PAID` (조회 시 cash SUM + clamp) |

경매 **출하중/청과확인**은 위 3종과 **별도 물류 상태**이며 판매확정이 아니다 ([02 §8.4](./02_domain_flow.md)).

**현재 구현:** 출고 TX에서 판매 INSERT 후 `SalesPaymentService.add_payment_in_tx`로 선입금 적용. `tot_paid_amt`/`tot_unpaid_amt`는 cash SUM 동기화 (DEC-019). **Stage4 · Stage3 Core 완료 · 운영.**
**Stage6-0:** `SalesQueryService` · `SalesPaymentService.get_payment_summary`가 동일 `compute_payment_status` helper 사용.
**Stage6B:** 수금내역 SSOT = `t_cash_ledger` 행. `payment_source` = `cash.order_no`만으로 `GENERAL`/`ORDER_PREPAY` 파생 (DB 컬럼 추가 없음). rmk/slip/id 패턴 추론 금지.
**DEC-030 (6C write · private main):** 신규 일반 수금 `pay_dt`는 Core `add_payment`에서 `sales_dt ≤ pay_dt ≤ today` 검증 · blank/future/before-sales reject. legacy cash는 조회만 · 자동보정 없음. `t_cash_ledger.pay_dt` = 실제 수금일 · `t_ledger.trans_dt` = `sales_dt` (불변).
**적용액:** `min(remaining_prepay, 이번 판매 tot_sales_amt)`. 기존 CONFIRMED 판매는 수정하지 않는다.

### 4.2 판매분류 (S4A · CURRENT PHYSICAL) · 경매 자동값 (DEC-037)

**CURRENT PHYSICAL:** `t_sales_master`에 canonical 분류 3컬럼이 있다 (`core/sales_class_schema` · 공통코드 SA01/SA02/SA03).

| 컬럼 | 축 |
|------|-----|
| `sales_type_cd` | 판매유형 (SA01…) |
| `sales_category_cd` | 판매구분 (SA02…) |
| `sales_route_cd` | 판매경로 (SA03…) |

**APPROVED LOGICAL (경매 판매확정, DEC-037):** 사용자 선택 없이 자동:

| 컬럼 | 값 | 명칭 |
|------|-----|------|
| `sales_type_cd` | `SA010200` | 도매 |
| `sales_category_cd` | `SA020400` | 경매판매 |
| `sales_route_cd` | `SA030300` | 경매연동 |

legacy `sales_tp` / `sales_source`는 **임의 폐기하지 않음**.

---

## 5. `t_sales_detail`

문서: `delivery_tp`. 코드: **`dlvry_tp`**.
주문 INSERT: `order_detail_id`, `wh_cd`.
판매화면 `execute_full_save`: **`order_detail_id` 없음**. 경매: `crop_nm`. **harvest_year 없음.**

**Stage 5C (DEC-027) — CURRENT / 주문·DIRECT OUT:** `stock_seq INTEGER NULL` — CONFIRMED 재고출고가 가리키는 `t_stock_master` row.
1행 = 1 `stock_seq`. FIFO N로트면 N행. DRAFT·레거시는 NULL. 물리 FK·NOT NULL 없음.

`shipped_qty`(주문 출고 누적) = **컬럼 아님.** `SUM(t_sales_detail.qty)` WHERE 같은 `order_detail_id` AND 마스터 `sales_status='CONFIRMED'`. DRAFT 제외. `t_order_detail.out_qty` 사용 금지.

부분출고: 같은 `order_detail_id`가 **여러 `sales_no`** 및 **같은 판매의 여러 상세**에 나타날 수 있다 (DEC-017 · FIFO 분할). 기존 CONFIRMED 판매를 후속 출고로 수정하여 수량을 증가시키지 않는다.

**Stage6A 상세 조회:** API는 FIFO 분할 **raw 행 그대로** 반환 (`sale_detail_no ASC`). Mobile 상세는 `order_detail_id`+`item_cd`+규격+`unit_price`가 같을 때만 qty·item_amt 합산 표시(첫 등장 위치 유지). `order_detail_id` NULL(직접판매·경매)은 임의 spec grouping 금지.

**경매 (APPROVED LOGICAL · DEC-036/037):**
- 경매 **출하 라인을 `t_sales_detail`로 선행 생성하지 않는다**.
- 농장 출하수량·청과 확인수량을 `qty` **하나로 덮어쓰지 않는다** — 원본은 출하 원장(DEC-036).
- 판매확정 시 `t_sales_detail.qty` = **최종 승인 판매수량** 축 (DEC-037).
- 출하 원천 상품재고는 **`stock_seq` 단위 line**으로 추적한다. Mobile은 **규격 집계 row** 선택 · Server는 **FIFO 분할** ([§8B](#8b-경매-출하-물리계약-dec-036)).

---

## 6. `t_sales_delivery`

문서명 `t_delivery_detail`. **실제 `t_sales_delivery`.**

| 경로 | dlvry_no |
|------|----------|
| 주문 저장(현재) | `{sale_detail_no}-P..-D{NNN}` |
| 판매 화면 | `{sales_no}-D{NNN}` |
| 규칙 (4.mdc) | `{sale_detail_no}-D{NNN}` |

설계: 출고 TX에서 **해당 출고분만큼만** 생성. 주문 저장 시에는 만들지 않음 (DEC-005). 주문 배송계획 전체 복제 금지 (DEC-017).

**고객배송 ≠ 경매출하:** `t_sales_delivery`는 **경매 출하중 SSOT가 아님**. 청과시장 출하는 고객배송과 **다른 업무** ([DEC-036](./07_decisions.md) · [02 §10](./02_domain_flow.md)).
경매 판매확정 시 delivery 생성 여부 = [DEC-016](./07_decisions.md) **OPEN** (임의 확정 금지).

---

## 7. `t_stock_master` (재고관리 · PC StockPage)

키(생산 UPSERT · 배정 FIFO):
`farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt`

surrogate PK `stock_seq` — **추적키만** (DEC-027). 업무키를 대체하지 않음. UPSERT 후 natural key로 `SELECT stock_seq`.

| 컬럼 | 의미 | PC / 설계 |
|------|------|-----------|
| in_qty | 입고 누적 | 원물등록·**생산확정 상품 IN** |
| out_qty | 출고·폐기·**생산 원물 OUT** | `save_production_log` 원물 차감. **경매 출하 시 증가 금지** (DEC-036) |
| reserved_qty | Hold | Stage 5A **주문 배정만**. **OUT 아님** · **경매 출하중 아님** |
| real_qty | 계산 (컬럼 아님) | `in_qty - out_qty` **현재고**. Mobile 재계산 금지 |
| available_qty | 계산 (컬럼 아님) | 아래 CURRENT / APPROVED LOGICAL |

**PC 현재 = 확정안:** 생산 100 → 상품 IN 100. 바로판매는 이후 OUT (OPEN-PROD-03 **CLOSED**, 코드 후속).

**Stage 5A:** `reserved_qty`는 `t_order_alloc` 미출고분과 일치 (상품재고 FR010100/200). HOLD는 real_qty를 바꾸지 않음.

Hold UPDATE WHERE에 `item_cd`/`weight`/`wh_cd` 누락 (2933행) — P0.

원물 입고 UPDATE `variety_cd` 누락 — 이번 비범위(C), 위험만 명시.

배정 API는 **같은 트랜잭션 안에서** 가용수량을 다시 읽고 `request <= available`일 때만 `reserved_qty +=`. 동시 복수 주문 초과예약 방지.

### 7.1 가용과 경매 출하중

**CURRENT PHYSICAL:**

```
real_qty      = in_qty - out_qty
available_qty = real_qty - reserved_qty
```

Core/API가 위 식으로 표시·배정 검증.

**APPROVED PHYSICAL DESIGN ([DEC-036](./07_decisions.md) · [09 §14.1](./09_production_inventory_flow.md) · [02 §14](./02_domain_flow.md) · **2026-08-31 대표 승인**):**

```
real_qty                   = in_qty - out_qty
active_auction_transit_qty = SUM(farm_shipped_qty)   -- status=IN_TRANSIT shipment line only
available_qty              = real_qty - reserved_qty - active_auction_transit_qty
```

- `reserved_qty` = **주문 HOLD 전용** (의미·컬럼 **변경 없음**).
- `active_auction_transit_qty` = `t_auction_ship_detail` ↔ `t_auction_ship_master` **집계** ([§8B](#8b-경매-출하-물리계약-dec-036)). `t_stock_master.transit_qty` **추가 금지**.
- 경매 출하 시 `out_qty` **증가 금지** · `t_sales_*` **생성 금지**.

**SSOT 적용 범위 (구현 시 일관 필수 — 화면표시만 수정 금지):**

- `GET …/fruit-stock` 조회
- 주문 allocation/HOLD 가용검증 (`OrderAllocationService`)
- DIRECT 판매/출고 가용검증 (`OrderShipService`)
- 경매 출하 생성 가용검증
- 기타 **실제 상품재고 소비** 경로

한 경로에서 transit 집계를 **무시**하면 동일 재고 **이중사용** 가능 → **금지**. 구현 시 공통 helper 또는 **동등한 단일 책임** 지점 우선 (helper **이름은 구현 단계에서 확정**).

**동시성 (APPROVED PHYSICAL):** 경매 출하 생성 = `BEGIN IMMEDIATE` → 가용 재검증 → header/line INSERT → COMMIT. 실패 시 **전체 rollback**. `reserved_qty` / `out_qty` / `t_sales_*` / SALE `t_stock_log` **변경 없음**.

**데이터 품질 (CURRENT 관찰 · DEC-036 범위 밖):** 일부 row에서 `out_qty > in_qty`로 **음수 가용** 가능. **자동 보정·clamp·DB 수정 금지**. 구현 시 `available_qty <= 0` → 경매 선택 불가 · 서버 출하 **reject**. 정리는 **별도 작업**.

---

## 8. `t_stock_log`

실값: `IN`, `OUT`, `AUDIT`, `HOLD`, `CANCEL_HOLD`.

**Stage 5C DDL (DEC-027, 멱등):** `stock_seq INTEGER NULL`, `ref_type TEXT NULL`, `ref_id TEXT NULL`.
물리 FK·NOT NULL 없음. 기존 행 NULL 유지. SALE 출고 시 `ref_type='SALE'`, `ref_id=sale_detail_no`.

주문 HOLD/CANCEL_HOLD INSERT 컬럼 (현재 코드, 5C Core 전):
`farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, (parent_raw_size HOLD만), remark, reg_id, reg_dt`

| 필드 | 주문 로그(현) | 5C 이후 |
|------|---------------|---------|
| stock_seq | 없음(컬럼 준비) | 해당 stock row |
| ref_type / ref_id | 없음(컬럼 준비) | SALE + sale_detail_no |
| wh_cd / storage_dt | 없음 | stock_seq로 row 추적 |
| 판매출고 OUT | 미구현 | io_type=OUT + ref |

**`t_stock_log`는 allocation 현재상태 SSOT가 아니다** (DEC-018). 현재상태 복원은 `t_order_alloc`. 5C부터 이력은 remark만이 아니라 `stock_seq`/`ref_*`.

| 이벤트 | io_type |
|--------|---------|
| 배정 | HOLD |
| 배정해제 | CANCEL_HOLD |
| 출고확정 | OUT (가능한 범위에서 판매번호·줄·자연키) — **신설 계약** |

신규 io_type 문자열 남발 금지.

**역할 경계 (APPROVED LOGICAL):**
- [DEC-035](./07_decisions.md) 수확 N:M **소진 SSOT로 사용 금지**.
- [DEC-036](./07_decisions.md) 경매 출하 묶음/라인 **SSOT로 사용 금지**.
- 출하중 표현용 **신규 io_type 임의 확정 금지**.
- [DEC-037](./07_decisions.md) 최종 판매 OUT은 기존 **`OUT` + `ref_type='SALE'`** 계약과 정합.
- `t_stock_log` = **감사/이력**. 출하 **현재상태 원장이 아님**.

---

## 8A. 수확 소진 물리계약 (DEC-035)

상세 업무: [09 §0.2·§16.4](./09_production_inventory_flow.md). **OPS APPLIED** · **OPERATIONAL PASS**.

### CURRENT PHYSICAL (수확 원장)

`t_work_detail` (수확): `work_id` · `farm_cd` · `work_dt` · `variety_cd` · `harvest_container_qty` 등.
- 수확 저장 ≠ `t_stock_master` 자동 IN. 단위 = 콘테이너 상자.

### IMPLEMENTED PHYSICAL CONTRACT (git `main`)

**테이블 `t_harvest_consumption`** (`core/harvest_consumption_schema.py` — 멱등 CREATE, 운영 자동 실행 금지):

| 컬럼 | 타입 | 의미 |
|------|------|------|
| `consumption_seq` | INTEGER PK AUTOINCREMENT | 소진 행 식별 |
| `farm_cd` | TEXT NOT NULL | 농장 |
| `prod_confirm_id` | TEXT NOT NULL | 생산확정 1회 event (`PRD`+`YYYYMMDD`+`-`+SEQ) |
| `harvest_work_id` | TEXT NOT NULL | `t_work_detail.work_id` |
| `consumed_container_qty` | INTEGER NOT NULL CHECK > 0 | 이번 생산 사용 상자수 |
| `is_valid` | INTEGER NOT NULL DEFAULT 1 CHECK IN (0,1) | 유효 소진 (cancel/reversal용) |
| `reg_id` | TEXT | 등록자 |
| `reg_dt` | TEXT NOT NULL | 등록 시각 |

**Index (2개):**
- `idx_harvest_consumption_work_valid` — (`farm_cd`, `harvest_work_id`, `is_valid`)
- `idx_harvest_consumption_confirm` — (`farm_cd`, `prod_confirm_id`)

**잔량 SSOT:** `harvest_container_qty − SUM(consumed_container_qty WHERE is_valid=1)` (행별 집계는 harvest-records API).

**상품 추적 (production trace):** HARVEST 생산 IN 시 `t_stock_log.ref_type='PRODUCTION'` · `ref_id=prod_confirm_id` (`core/stock_constants.py` · Stage 5C trace DDL).

**OPS APPLIED (2026-08-31):** PC·Lightsail **운영 DB**에 `t_harvest_consumption` **적용 완료** · integrity **ok** · D1/D2 rehearsal 후 E1/E2 운영 DDL PASS.

### OPEN (DEC-035)

- **OPEN-DONE** — HARVEST `DONE` 최종 의미 (잔량 SSOT와 분리는 확정)
- idempotency / cancel-reversal 물리 — **구현 유지** · 운영 적용 후에도 동일

**기각:** `t_stock_log` 단독 · `used_qty` 누적만 · CT01/20kg 자동변환 · `t_production_*` 풀세트 · legacy `harvest_work_id` only.

---

## 8B. 경매 출하 물리계약 (DEC-036)

상세: [09 §2.3.1·§2.3.2](./09_production_inventory_flow.md) · [02 §6.1](./02_domain_flow.md) · [05 §9A](./05_api_contract.md).

**상태:** **APPROVED LOGICAL** · **APPROVED PHYSICAL DESIGN** · **NOT IMPLEMENTED** (**2026-08-31 대표 승인**).

흐름: `상품 가용 → 경매 넘기기 → 출하중 → 청과 확인/매칭 → DEC-037 판매확정`.

### CURRENT PHYSICAL

전용 출하 테이블 **없음**. `AUCTION_RT`+`DRAFT` 판매만 (`save_realtime_auction_draft`) · 재고 미접촉 · **출하중 SSOT 아님** ([§8B.4](#8b4-legacy-auction_rt-draft)).

### APPROVED PHYSICAL DESIGN — 테이블

프로젝트 **master/detail** 네이밍(`t_sales_master` / `t_sales_detail` 등)에 맞춘 물리명:

| 논리 | 물리 테이블 |
|------|-------------|
| Auction Shipment Header | **`t_auction_ship_master`** |
| Auction Shipment Line | **`t_auction_ship_detail`** |

**DDL·migration·운영 ALTER는 본 문서 승인만으로 실행하지 않는다** (로컬/테스트용은 별도 구현 지시).

#### `t_auction_ship_master` (Header)

| 컬럼 | 타입 | 의미 |
|------|------|------|
| `shipment_id` | TEXT **PK** | 서버 생성 **내부키**. 사용자 입력·화면 노출 **금지** |
| `farm_cd` | TEXT NOT NULL | 농장 |
| `ship_dt` | TEXT NOT NULL | 출하일 (YYYY-MM-DD) |
| `market_cd` | TEXT NOT NULL | 시장 코드 — [§8B.5](#8b5-시장청과회사-ssot) |
| `market_name` | TEXT NOT NULL | 출하 시점 **시장 표시 snapshot** |
| `corporation_name` | TEXT NOT NULL | 출하 시점 **청과회사(법인) 표시 snapshot** |
| `custm_id` | TEXT NULL | `m_customer` 매핑 있을 때만. **nullable** |
| `status` | TEXT NOT NULL | v1 생성값 **`IN_TRANSIT`** ([§8B.3](#8b3-v1-상태)) |
| `reg_id` | TEXT | 등록자 |
| `reg_dt` | TEXT NOT NULL | 등록 시각 |
| `mod_id` | TEXT NULL | (선택) 감사 — 기존 테이블 패턴 |
| `mod_dt` | TEXT NULL | (선택) 감사 |

#### `t_auction_ship_detail` (Line)

| 컬럼 | 타입 | 의미 |
|------|------|------|
| `line_seq` | INTEGER **PK** AUTOINCREMENT | 라인 내부 식별 |
| `shipment_id` | TEXT NOT NULL | → `t_auction_ship_master.shipment_id` |
| `stock_seq` | INTEGER NOT NULL | → `t_stock_master.stock_seq`. **1 line = 1 stock row** |
| `farm_shipped_qty` | REAL NOT NULL CHECK > 0 | 농장 출하수량 **원본** (UPDATE 덮어쓰기 **금지**) |
| `company_confirmed_qty` | REAL NULL | 청과 확인수량 (nullable). 존재 여부로 확인 진행 표현 가능 |
| `reg_dt` | TEXT NOT NULL | 등록 시각 |

**v1에서 넣지 않음 (OPEN 후속):** `match_ref` · `sale_ref` · line `status` · settlement FK · qty diff 자동처리 필드 · `transit_qty` 누적.

규격/품종/등급/중량 등은 **`stock_seq` → `t_stock_master` join**으로 복원 (중복 최소화).

**권장 index (구현 시):** master (`farm_cd`, `status`); detail (`shipment_id`); detail (`stock_seq`) — active transit 집계용.

### 8B.1 Stock cardinality (CLOSED)

| 계층 | 계약 |
|------|------|
| **Mobile / 사용자** | **규격 단위 집계 row** 선택 · `stock_seq` **비노출** · 출하수량만 입력 |
| **Server / Core** | 동일 규격에 stock row **여러 개**면 **`storage_dt ASC, rowid ASC` FIFO** 분할 ([`OrderAllocationService._fifo_stock_rows`](../../core/order_allocation_service.py) · [`OrderShipService`](../../core/order_ship_service.py)와 **동일 ordering**) |
| **물리 line** | **1 shipment line = 1 `stock_seq`** |
| **분할** | 사용자 규격 선택 1건 → shipment line **N건** 가능 |

```
Mobile spec row 1  →  Server FIFO  →  t_auction_ship_detail × N (각 stock_seq 1)
```

### 8B.2 Active transit 집계 (CLOSED)

```
active_auction_transit_qty(stock_seq) =
  SUM(d.farm_shipped_qty)
  FROM t_auction_ship_detail d
  JOIN t_auction_ship_master m ON d.shipment_id = m.shipment_id
  WHERE m.farm_cd = :farm
    AND m.status = 'IN_TRANSIT'
    AND d.stock_seq = :stock_seq
```

- v1 **active** = master `status = 'IN_TRANSIT'` line만.
- `reserved_qty` / `out_qty` **미사용**.

### 8B.3 v1 상태 (CLOSED — 생성)

| 코드 | v1 | 의미 |
|------|:--:|------|
| **`IN_TRANSIT`** | **생성 시 설정** | 농장→시장 출하중 · active transit · 가용 제외 · 판매 아님 · reserved/out **불변** |

**v1 비필수 / 금지:**

- `CHECKED` 등 **별도 상태 전이 필수 아님** — `company_confirmed_qty` 입력만으로 확인 진행 표현 가능
- `COMPLETED` · **`CANCELLED`** — v1 **구현 금지** (출하 취소/정정 = **CAN-DEFER**)

**OPEN (후속):** 판매확정 후 잔여 transit 해소 · 취소/정정 · 확인/매칭 완료 상태 — [OPEN-SHIP-STATE](./07_decisions.md) **후속 OPEN**.

### 8B.4 Legacy `AUCTION_RT` DRAFT

`save_realtime_auction_draft` ([PC `market_price_page.py`](../../ui/pages/market_price_page.py)):

- **CURRENT legacy** · 판매 DRAFT 저장 · 재고 **미접촉**
- DEC-036 출하 SSOT **아님** · DEC-036에서 **재사용 금지**
- **삭제하지 않음** · DEC-010 = **SUPERSEDED HISTORY**

### 8B.5 시장·청과회사 SSOT (MVP CLOSED)

| 항목 | SSOT | 비고 |
|------|------|------|
| 시장 코드 | `core/market_price_manager.py` **`MARKET_CODE_BY_NAME`** | 신규 market master **금지** |
| Header 저장 | `market_cd` + `market_name` **snapshot** | |
| 청과회사 표시 | `corporation_name` **필수 snapshot** | 전용 corporation master **금지** |
| 거래처 연결 | `m_customer.custm_id` **nullable** | PC 법인→custm_id 매핑 패턴 재사용 |
| 후보 목록 | `market_price_settlement.corporation` · `m_customer` | |
| Mobile REST | **미구현** — 기존 map **read-only 노출** 우선 (path = 구현 단계) |

매핑 없이 출하를 **막을지**는 API 구현 단계에서 조사.

### 8B.6 DEC-037 경계 — 20 출하 / 19 확인

DEC-037에서 **19**를 판매확정해도 DEC-036 shipment **전체 자동 종료 금지**.

**금지:** 남은 **1** 자동 가용복귀 · 자동 폐기 · 자동 OUT · 자동 재고조정 · 「확정 = 출하 20 전체 종료」.

잔여 transit 해소 = **OPEN-QTY-DIFF** + **DEC-037** 별도 확정. DEC-036 v1은 **판매확정 이전 active transit**까지 책임.

### APPROVED LOGICAL (유지)

- 출하 ≠ 판매 DRAFT · 출하중 ≠ `sales_status`.
- `reserved_qty` 재사용 금지 · 출하 시 `out_qty` 선차감 금지 · `t_sales_master/detail` 생성 **금지**.
- 단순 `transit_qty` 단독 SSOT **금지**.
- 출하 시 `t_stock_log` **임의 추가 금지** (감사 필요성 확인 전).

---

## 8C. 경매 판매확정 연결계약 (DEC-037)

상세: [09 §5.3](./09_production_inventory_flow.md) · [02 §6.2](./02_domain_flow.md). **설계 APPROVED · 구현·DDL 아님.** DEC-010 **SUPERSEDED** 원자성 승계.

개념 TX (실패 시 **전체 rollback**):

1. 출하/매칭 원장 확인
2. **최종 승인 판매수량** 확인
3. **판매 생성 또는 기존 DRAFT 확정** → `CONFIRMED` *(목표에서 DRAFT 필수 여부 = OPEN)*
4. `t_sales_detail` ↔ stock 추적 (`stock_seq` — DEC-036 line과 **별도** DEC-037 OUT 대상)
5. `t_stock_master.out_qty` 증가 (최종 승인 수량)
6. `t_stock_log` SALE OUT (`OUT` + `ref_type='SALE'`)
7. S4A 자동분류 (`SA010200` / `SA020400` / `SA030300`)
8. rollback on failure

- 출하 시 OUT **없음** → **이중 OUT 금지**.
- `t_sales_detail.qty` = **최종 승인 판매수량** 축. 출하/확인 **원본은 출하 원장에 유지**.

**예 (20 출하 / 19 확인):** 판매확정 19 → OUT 19.
남은 차이 1을 자동 가용복귀·자동 OUT·감모·반입·재고조정 중 무엇으로 할지는 **OPEN-QTY-DIFF**.
「판매확정 시 출하라인 전체가 자동 종료된다」고 **단정하지 않는다**.

문구: **최종 승인수량은 판매 OUT 처리한다. 출하수량과 최종 승인수량의 미해결 차이분이 이후 가용·출하중·조정 중 어디에 귀속되는지는 OPEN-QTY-DIFF이며 임의 처리하지 않는다.**

[DEC-016](./07_decisions.md) delivery 생성 여부 **OPEN**.

---

## 9. `t_cash_ledger` / `t_ledger` — 수금·회계 SSOT

판매 **CONFIRMED** 수금만. 문서명 `t_sales_pay_detail`과 다름. **코드 테이블명 우선.**

**수금 SSOT = `t_cash_ledger`.** master `tot_paid_amt`/`tot_unpaid_amt`는 Core가 cash SUM으로 동기화한다.  
master `pay_method_cd` / `slip_no`는 N회 수금 SSOT가 아니다.

**주문 단계에는 아무 행도 넣지 않는다** (DEC-009). 주문에 선입금 금액·결제수단을 저장해도 전표는 생기지 않는다 (DEC-028).

회계 엔진은 **기존 것을 그대로 재사용**한다. 모바일 전용 회계 엔진을 만들지 않는다.

| 대상 | 사용 |
|------|------|
| 수금 상세 (SSOT) | `t_cash_ledger` |
| 전표 | `t_ledger` (+ `t_ledger_history`) |
| 전표 생성 | `AccountManager.sync_ledger_by_basket('SALE', sales_no, work_date, basket, user_id)` |
| 공용 Core | `core/sales_payment_service.py` `SalesPaymentService` (개발순서 3 · append 추가수금). HTTP는 6단계 |
| 계정코드 | 결제수단 = **현금성** `parent_cd=AS0101` · level4 · `use_yn=Y`. 채권(`AS02…`) 금지 |

**확인된 `t_cash_ledger` 컬럼** (운영 PRAGMA 2026-08-21):

```
paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt,
rmk, reg_id, reg_dt, slip_no, order_no
```

PC `sales_page.py` INSERT·일반 추가수금 Core는 `order_no`를 **넣지 않는다**(NULL).

**DEC-019 provenance (CLOSED):** `t_cash_ledger.order_no`가 구분 SSOT이다.
- `NULL` = 일반 추가수금 (Stage3 · PC 신규 수금)
- 주문번호 = 출고 시 선입금 자동적용 (Stage4)
- 신규 `payment_type`/`prepay_yn` 컬럼·DDL **없음**. `rmk`/`paid_detail_no` 패턴을 SSOT로 쓰지 않는다.

**PC 재저장 보존 (Stage4-P1):** `execute_full_save` DELETE→INSERT 시
- `t_sales_master.order_no` = DELETE 전 DB값 보존 (UI/역산 금지)
- 기존 cash 행(ORG/MOD) = 행별 `orig_data.order_no` 보존 (master 상속 금지)
- 신규 PC 수금(INS) = 항상 `NULL`
- `t_sales_detail.order_detail_id` 재저장 유실은 **별도 OPEN P1** (이번 범위 아님)

**PC 선입금 행 불변 (Stage4-P2):** `orig_data.order_no IS NOT NULL`인 자동 선입금 cash는
판매관리에서 금액·결제수단·날짜 수정 및 삭제 **금지**. 일반수금(`order_no` NULL)은 기존 수정/삭제 유지.
AccountManager sync·DB TX 이전에 검증한다.

**PC 판매일 우회차단 (Stage4-P2b):** 자동 선입금 cash가 하나라도 있으면 기존 `sales_dt` 변경 **금지**
(cash.pay_dt / ledger.trans_dt 불변). PC cash 재INSERT 시 `pay_dt`는 **각 수금행 `pay_dt`**를 사용한다

**출고확정 CONFIRMED read-only (Stage7A · private main · DEC-031):** `sales_status='CONFIRMED'` 이고
(`t_sales_master.order_no` OR `t_sales_detail.order_detail_id` OR `t_sales_detail.stock_seq` 실값)이면
PC `SalesPage`에서 full-save·삭제·수금 mutation **금지**. UI disable + write/delete DB backstop.
일반 PC 직접판매(CONFIRMED·추적키 없음)는 기존 편집 유지. DRAFT는 대상 아님.

**PC 수금 append-only (DEC-032 · IMPLEMENTED · Stage7B-1+7B-2):** 기존 수금 수정/삭제 금지 · `execute_full_save` cash/ledger mutation **제거** · 신규 일반수금은 `SalesPaymentService.add_payment`만 · `source_order_no=None` → `cash.order_no` NULL. **`slip_no`는 내부 파생 회계 linkage** — 동일 결제수단 append 시 AccountManager 누적 그룹 정책으로 기존 cash의 slip이 재연결될 수 있으나, 사용자 수금값(날짜·수단·금액·order_no) 수정으로 취급하지 않는다. **P1:** COMMIT 성공 후 UI 갱신 실패는 수금 write 실패로 표시하지 않음.

**신규 판매 수금 (DEC-033 · IMPLEMENTED):** 판매 저장 전 수금등록 금지 · CONFIRMED + unpaid>0 만 수금등록 · 미저장 판매금액/판매일 변경 시 차단.

**판매금액 감액 (DEC-034 · IMPLEMENTED):** 일반 직접판매 수정 시 `new tot_sales_amt >= actual paid(cash SSOT)` — Stage7B-1 backstop 유지.

### 9.1 선입금 잔액 (컬럼 없음 · DEC-019)

```
applied_prepay = SUM(c.pay_amt)
  FROM t_cash_ledger c
  JOIN t_sales_master s ON s.farm_cd=c.farm_cd AND s.sales_no=c.sales_no
 WHERE c.farm_cd=? AND c.order_no=?
   AND s.sales_status='CONFIRMED' AND s.order_no=c.order_no

remaining_prepay = MAX(0, t_order_master.pre_pay_amt − applied_prepay)
apply_amt = MIN(remaining_prepay, 이번 판매 tot_sales_amt)
```

`prepay_balance` 컬럼은 **만들지 않는다.** master `tot_paid_amt` 합으로 역산하지 않는다.

### 9.2 트랜잭션 순서 (확정 설계)

출고확정: 판매 생성 → 선입금 적용액 계산 → `t_cash_ledger` → `AccountManager` → `t_ledger` → `tot_paid_amt`/`tot_unpaid_amt`. 전부 **한 TX**.  
추가수금: **CONFIRMED 판매만** → 수금액+결제수단 → `t_cash_ledger` → `AccountManager` → `t_ledger` → paid/unpaid. **DRAFT 판매에는 수금 금지** (DEC-029).

판매 삭제 시 `t_ledger` 미처리 — P1, 1차 DELETE 비활성.

`ref_id` ≈ `SALE-{sales_no}-{acct_cd}_{method}`, `trans_type_cd='REVENUE'`. 회계 엔진 개편은 C.

---

## 10. `m_customer` · `m_warehouse` · 코드

- 고객 INSERT: `custm_id=C`+`yyMMddHHmmss`, `custm_tp='CT01'`(고객유형). 원물 규격 부모 `CT01`과 **코드 공간 충돌** — parent 혼용 금지.
- `m_warehouse`: Python 미사용. `WH01` 고정.
- `m_common_code`: FR01, GR01, SZ01, LO01, SS01, ST01(목록 미확인).
- `m_item_unit_price`: 주문 단가.
- `t_stock_status`: baseline만, 코드 미사용. 이행상태에 쓰지 않음.

---

## 11. 핵심 키 관계

```
t_order_master.order_no
    ├─ t_order_detail.order_no
    │     qty, allocated_qty (누적)
    │     shipped_qty = SUM(CONFIRMED sales_detail.qty) by order_detail_id
    │     order_detail_id ──→ t_sales_detail.order_detail_id  (출고마다 N건 · FIFO면 stock_seq마다 N건)
    │     t_sales_detail.stock_seq ──→ t_stock_master.stock_seq
    ├─ t_order_delivery
    ├─ t_order_alloc (가칭) ── 줄 ↔ stock 자연키 현재상태
    └─ t_order_master.sales_no ──→ legacy/reference (최초 출고 또는 대표 참조)
         전체 판매 조회: t_sales_master.order_no = 주문번호 (1:N SSOT)

t_stock_master.reserved_qty  ↔  t_order_alloc 미출고분 합 (행 단위)  -- 주문 HOLD만
t_stock_log                  =  HOLD / CANCEL_HOLD / OUT 이력 (현재상태 SSOT 아님)
t_order_master.stock_status  =  전량 출고 시만 Y
```

**APPROVED PHYSICAL (DEC-036 — [§8B](#8b-경매-출하-물리계약-dec-036)):**

```
[수확 DEC-035]
t_work_detail (harvest)
    → 최소 소진이력 (3축)
    → 생산확정 1회 내부식별
    → 상품 IN (기존 t_stock_master)   -- DEC-023

[경매 DEC-036/037]
t_stock_master
    → 경매 출하 라인 → 경매 출하 묶음
    → (판매확정) t_sales_detail ← stock 추적
    → out_qty + · t_stock_log SALE OUT
```

| 필드 | 현재 | 확정 설계 |
|------|------|-----------|
| reserved_qty | 주문 전량 Hold | 미출고 배정분. 출고 시 −. **경매 출하중 아님** |
| out_qty | 판매출고 없음 | 출고 TX / 경매 **판매확정**에서 +. **경매 출하 시 + 금지** |
| stock_status | N만. Y 세팅 없음 | 전량 출고 시 Y. 부분출고 N |
| allocated_qty | 없음 | **누적 배정**. 출고 후 유지 |
| shipped_qty | 없음 | CONFIRMED 판매상세 합. 컬럼 없음 |
| sales_no (주문) | 저장 즉시 1개 | **legacy/reference.** 최초 출고만. SSOT 아님 |
| order_no (판매) | 주문 생성 시만, 재저장 유실 | **1:N 추적 SSOT.** 재저장 보존 |
| order_detail_id | 주문 경로만 | 모든 출고 상세에 유지 |

---

## 12. 컬럼 제안 상태

| 제안 | 상태 |
|------|------|
| **`t_order_master.pre_pay_method_cd TEXT NULL`** | **완료 · 운영** (DEC-028) |
| `t_order_master.prepay_balance` | **하지 않음** (계산. §9.1) |
| 수금상태 컬럼 (`payment_status` 등) | **하지 않음** (금액 계산. DEC-029) |
| `sales_status`에 PAID/UNPAID 추가 | **하지 않음** (DEC-029) |
| `t_cash_ledger.order_no` provenance | **CLOSED.** NULL=일반수금, 주문번호=선입금 자동적용. 신규 컬럼 없음 (§9) |
| `t_order_detail.allocated_qty` | **Stage 3A 로컬 DDL.** 운영 ALTER는 별도 승인 |
| `unallocated_qty` / `shipped_qty` 컬럼 | **하지 않음** (계산) |
| `t_sales_detail.stock_seq` | **Stage 5C 멱등 ALTER** (NULL). 운영 자동실행 금지 |
| `t_stock_log.stock_seq` / `ref_type` / `ref_id` | **Stage 5C 멱등 ALTER** (NULL). SALE 시 ref_id=`sale_detail_no` |
| `t_stock_log` 컬럼 추가 | **하지 않음** (allocation SSOT 목적). 향후 이력 식별정보만 설계 가능 |
| `t_order_master.plan_ship_dt` | 하지 않음 (`planned_dt` 계산) |
| `t_sales_detail.harvest_year` | 하지 않음 (주문 조인) |
| 이행상태 컬럼 | 하지 않음 (계산) |
| 주문↔판매 연결 새 컬럼 | **하지 않음.** SSOT는 기존 `t_sales_master.order_no` + `t_sales_detail.order_detail_id` |
| S4A `sales_type_cd` / `sales_category_cd` / `sales_route_cd` | **CURRENT PHYSICAL** (기존). 경매 자동값 = DEC-037 |

### APPROVED LOGICAL / OPEN PHYSICAL (물리명·ALTER 예정 표현 금지)

| 항목 | 근거 | 상태 |
|------|------|------|
| 수확 소진 `t_harvest_consumption` | DEC-035 | **OPS APPLIED** · **OPERATIONAL PASS** |
| 생산확정 `prod_confirm_id` + PRODUCTION trace | DEC-035 | **OPS APPLIED** · `ref_type='PRODUCTION'` · `ref_id=prod_confirm_id` |
| 경매 출하 `t_auction_ship_master` / `t_auction_ship_detail` | DEC-036 | **APPROVED PHYSICAL DESIGN** · **NOT IMPLEMENTED** |
| 출하/확인 수량 두 축 | DEC-036 | **APPROVED** (`farm_shipped_qty` / `company_confirmed_qty`) |
| v1 출하 생성 상태 `IN_TRANSIT` | DEC-036 | **CLOSED** |
| 출하 후속 상태(완료/취소/차이 종료) | OPEN-SHIP-STATE | **OPEN** (v1 생성 상태만 CLOSED) |
| stock cardinality Mobile→FIFO→line | DEC-036 | **CLOSED** |
| 가용에서 출하중 제외 집계 | DEC-036 · §7.1 | **APPROVED PHYSICAL** · 코드 **미적용** |

### 하지 않음

| 항목 | 이유 |
|------|------|
| `sales_status`에 `SHIPPED`/`TRANSIT` | 출하중 ≠ sales_status |
| `transit_qty` 단독 SSOT | DEC-036 |
| `t_production_master`/`detail` 풀세트 | DEC-025 |
| `t_stock_log`를 출하/소진 SSOT로 재사용 | DEC-035/036 |
| 경매용 `reserved_qty`/`out_qty` 선차감 | DEC-036 |

### 12.1 `t_order_alloc` (Stage 3A)

```
alloc_id TEXT PK          -- {order_detail_id}-A{NNN}
farm_cd, order_no, order_detail_id
wh_cd, item_cd, variety_cd, grade_cd, size_cd,
weight, harvest_year, storage_dt   -- t_stock_master 자연키
allocated_qty REAL NOT NULL DEFAULT 0
shipped_qty REAL NOT NULL DEFAULT 0
reg_id, reg_dt, mod_id, mod_dt
UNIQUE (farm_cd, order_detail_id, wh_cd, item_cd, variety_cd,
        grade_cd, size_cd, weight, harvest_year, storage_dt)
```

같은 주문상세 + 같은 stock 행은 한 행에 누적.  
미출고분이 0이면 행 DELETE. `t_stock_log`는 ALTER하지 않음.

---

## 13. `allocated_qty` / `t_order_alloc` migration

로컬·테스트: `core/order_alloc_migrate.py` (`ensure_order_alloc_schema`). 멱등.  
운영: **자동 실행 금지.** **active reserved_qty>0**이면 중단. historical HOLD만으로는 중단하지 않음. 점검 SQL: `scripts/ops/check_order_alloc_preflight.sql`.

1. `qty` 타입 운영 PRAGMA로 재확인 후 동일 계열.
2. `ALTER TABLE t_order_detail ADD COLUMN allocated_qty REAL NOT NULL DEFAULT 0;`
3. **기존 행은 DEFAULT 0으로 생기지만, HOLD가 있으면 정합성 깨짐.**
4. 백필은 DEC-015: 운영 점검 후.
   - 후보: 아직 미출고이고 주문별 Hold가 줄 `qty`와 일치하면 `allocated_qty=qty`.
   - 불일치·복수 줄·재고 행 병합 실패 → 수동 목록, 0 유지 금지 vs 운영 판단.
5. Rollback: SQLite는 컬럼 드롭이 표준 아님. 배포 전 스테이징에서만 ALTER. 실패 시 앱 플래그로 배정 API 비활성.
6. 호환: 컬럼 없는 구PC는 배정 화면을 열지 않음. 주문 조회는 DEFAULT 0으로 읽히면 미배정으로 보임 → **구PC와 신규칙 동시 운영 기간을 짧게**.

---

## 14. 설계 위험 (반드시 구현 전 인지)

1. 기존 주문이 이미 `t_sales_*`를 갖고 있음 (`save_entire_order`).
2. 기존 `reserved_qty` / HOLD 로그와 `allocated_qty=0` 충돌.
3. 판매 재저장 시 `order_no` 유실.
4. 판매 삭제 시 `t_ledger` 미처리.
5. `sales_dt` YYYYMMDD / ISO 혼재.
6. `order_dt` 동일 혼재.
7. 운영에 DRAFT 판매가 있을 수 있음 (확정 버튼 없음).
8. 주문/판매 채번 이중 경로 충돌 가능.
9. 부분배정 동시성: 두 요청이 같은 가용 30을 각각 30으로 배정.
10. 동일 규격 복수 주문 초과예약.
11. 수확 소진이력 없으면 부분포장 잔량/원복 불가 (DEC-035).
12. 생산확정 내부식별 없으면 N:M 추적 불가 (DEC-035).
13. DRAFT를 출하 SSOT로 사용하면 판매/물류 의미 오염 (DEC-036).
14. 경매 출하중을 `reserved`로 처리하면 주문 HOLD 충돌.
15. 출하 시 `out` 처리하면 판매확정에서 이중 OUT 위험 (DEC-037).
16. 출하/확인 단일 qty 사용 시 원본 유실.
17. 가용계산에 유효 출하중 미반영 시 과대계상.
18. 주문 HOLD와 경매 출하 동시 요청 시 가용 중복 소비 위험 (§7.1).
19. OPEN-QTY-DIFF 확정 전 차이수량 임의 재고조정 위험.
20. ~~사용자 상품행과 `stock_seq` cardinality 조기 고정~~ → **CLOSED** Mobile spec / Server FIFO / line=`stock_seq` ([§8B.1](#8b1-stock-cardinality-closed)).

**원칙:** 배정·출고·(목표) 경매 출하 서비스는 BEGIN(가능하면 IMMEDIATE) 후 가용/배정수량을 **다시 SELECT** 하고 조건 불일치 시 rollback.

---

## 15. 구현/migration 직전 운영 DB 점검 (read-only)

이번 문서 작업에서는 운영 DB에 **접근하지 않음.** 실행은 단계 3·4 직전.

**향후 DDL 직전 점검 후보 (문장 · 이번 범위에서 SQL 실행 금지):**
- `t_work_detail` harvest 컬럼 (`variety_cd` · `harvest_container_qty`)
- 생산확정 식별로 **재사용 가능한 기존 영속키** 존재 여부
- 동일 목적 **소진** 구조 존재 여부
- 동일 목적 **경매출하** 구조 존재 여부
- `stock_seq` 실사용
- S4A 3컬럼·SA01/02/03 코드
- 기존 `AUCTION_RT`+`DRAFT` 데이터

```sql
-- ST01 실코드
SELECT code_cd, code_nm, use_yn FROM m_common_code
 WHERE parent_cd = 'ST01' ORDER BY code_cd;

-- 미완료 주문 (status/stock 실값 분포)
SELECT status_cd, stock_status, COUNT(*) FROM t_order_master GROUP BY 1, 2;

-- sales_no 연결된 주문
SELECT COUNT(*) FROM t_order_master WHERE sales_no IS NOT NULL AND TRIM(sales_no) != '';

-- reserved > 0
SELECT COUNT(*), SUM(reserved_qty) FROM t_stock_master WHERE reserved_qty > 0;

-- HOLD 로그
SELECT COUNT(*) FROM t_stock_log WHERE io_type = 'HOLD';

-- DRAFT 판매
SELECT COUNT(*) FROM t_sales_master WHERE sales_status = 'DRAFT';

-- 선입금 결제수단 ALTER 전 (DEC-028)
PRAGMA table_info(t_order_master);

-- 선입금 적용분 vs 추가수금 구분키 확인 (§9 OPEN)
PRAGMA table_info(t_cash_ledger);

-- 실사용 결제수단 코드
SELECT pay_method_cd, COUNT(*) FROM t_cash_ledger GROUP BY 1 ORDER BY 2 DESC;

-- 수금상태 분포 (계산값 검증용)
SELECT
  SUM(CASE WHEN COALESCE(tot_paid_amt,0) = 0 THEN 1 ELSE 0 END) AS 미수,
  SUM(CASE WHEN COALESCE(tot_paid_amt,0) > 0
            AND COALESCE(tot_unpaid_amt,0) > 0 THEN 1 ELSE 0 END) AS 부분수금,
  SUM(CASE WHEN COALESCE(tot_unpaid_amt,0) = 0 THEN 1 ELSE 0 END) AS 수금완료
FROM t_sales_master;

-- 날짜 형식
SELECT
  SUM(CASE WHEN order_dt LIKE '____-__-__' THEN 1 ELSE 0 END) AS iso_n,
  SUM(CASE WHEN order_dt GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 1 ELSE 0 END) AS ymd_n,
  COUNT(*) AS tot
FROM t_order_master;

SELECT
  SUM(CASE WHEN sales_dt LIKE '____-__-__' THEN 1 ELSE 0 END) AS iso_n,
  SUM(CASE WHEN sales_dt GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 1 ELSE 0 END) AS ymd_n,
  COUNT(*) AS tot
FROM t_sales_master;
```

ST01 운영 실코드는 DEC-011 CLOSED (`ST010100`~`ST010500`).

## 16. 운영 테스트데이터 초기화 (2026-08-17 대표 완료)

기존 주문/판매/재고는 테스트 데이터였으며 **운영 DB 초기화 완료**.  
2026년 실제 신규 수확부터 재고관리를 시작한다. Stage 3 DDL을 당겨오지 않음.

| 영역 | 결과 |
|------|------|
| 주문 | `t_order_master` 0 · `t_order_detail` 0 · `t_order_delivery` 0 |
| 판매 | `t_sales_master` 0 · `t_sales_detail` 0 · `t_sales_delivery` 0 |
| 재고 OR001 | `t_stock_master` 0 · `t_stock_log` 0 |
| 회계 | 관련 `t_cash_ledger` 0 · `t_ledger` 0 |
| 백업 | `/var/www/orchard/backups/orchard_20260817.db` |
