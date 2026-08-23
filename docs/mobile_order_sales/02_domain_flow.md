# 02. Domain flow — 주문·배정·출고·판매

> **범위:** 주문/판매 도메인. 생산/재고 전체·판매유형 7종: [09_production_inventory_flow.md](./09_production_inventory_flow.md)  
> 범례: **현재** = PC 코드 · **확정** = APPROVED · **OPEN** = 미확정

## 0. 전체 맥락

최상위: `수확 → (생산) → (재고) → 판매 ← (주문)`.  
본 문서는 **주문·배정·출고·판매** 구간. 생산확정·원물/상품 재고는 **StockPage** (09 §3).

**Stage 3A:** 상품재고가 **이미 있을 때** 주문에 예약. 필수 단계 아님. **운영 반영 완료** (`fd963e0` 계열). *(역사: 로컬 구현 당시 main 미머지)*

---

## 1. 수량 용어

| 이름 | 정의 | 저장 |
|------|------|------|
| `qty` | 주문상세 주문수량 | `t_order_detail.qty` |
| `allocated_qty` | 해당 줄에 지금까지 확정된 **누적 배정수량**. 출고 후 0으로 내리지 않음 | `t_order_detail.allocated_qty` (Stage 3A · **운영 반영**) |
| `shipped_qty` | 해당 `order_detail_id`로 생성된 모든 **CONFIRMED** 판매상세 수량 합계 | 계산. 컬럼 없음 |
| `reserved_unshipped_qty` | 아직 재고 Hold 중인 배정분 | 계산. `allocated_qty - shipped_qty` |
| `unallocated_qty` | 아직 배정하지 않은 주문분 | 계산. `qty - allocated_qty` |

정합성: `0 <= allocated_qty <= qty`, `0 <= shipped_qty <= qty`.  
STOCK 배정해제: `release_qty <= allocated_qty - shipped_qty`.  
STOCK 출고: `ship_qty <= reserved_unshipped_qty`. 출고 시 `allocated_qty`는 감소하지 않음.  
DIRECT 출고: allocation/HOLD 없이 가능 (DEC-020). `allocated_qty=0`은 정상.

---

## 2. 판매 경로 요약 (09와 정합)

| 경로 | 주문 | 배정(3A) | 비고 |
|------|------|----------|------|
| 저장배 소매 | O | O | 09 §2.5 |
| 배즙(재고) | O | O | 09 §2.6 |
| 추석/조생 소매 | O | X | DIRECT 출고, 09 §2.4 |
| 원황/신고 수출 | X | X | 생산→판매, 09 §2.1·2.2 |
| 가락 | X | X | DRAFT→확정, 09 §2.3 |
| 배즙(주문생산) | O | X | PROCESS 후 판매, 09 §2.7 |

아래 §3~는 **주문이 있고 저장재고 출고(STOCK)를 쓰는** 경로 중심.

---

## 3. 세 경로 (주문/판매 관점)

### 3.1 소매 주문 (STOCK 가능)

```
주문접수 (재고 0 허용, allocated_qty=0, 판매 없음)
 → 포장대기 / 이행=미배정
 → 재고배정 (부분 가능)
 → 출고대기
 → 배송 또는 방문수령
 → 출고확정 TX: reserved→out + 새 판매(CONFIRMED) 생성 + 연결
 → 선입금 순차 적용 → 미수 확정 (판매 CONFIRMED 기준 전표)
 → 추가수금 → 수금완료
```

주문 등록·확정은 판매가 아니다. 판매는 **출고확정 시점**에 생성된다 ([§8.1](#81-주문-생성확정은-판매가-아니다)).

### 3.2 가락시장

```
포장재고 (FR010100)
 → 실시간 경매 (시세 화면)
 → AUCTION_RT + DRAFT 판매 (재고 미차감 — 현재와 동일)
 → 경매결과 확인
 → 확정 TX: CONFIRMED + 재고 출고 (+ 선택 수금)
 → 정산
```

근거: `market_price_page.py` `save_realtime_auction_draft` (마스터·상세만).  
확정 함수는 **현재 없음** → PC/core 보완 (DEC-010).

### 3.3 수출 / 일반도매

```
포장재고
 → 판매 직접 등록 (주문 없음)
 → 출고/판매확정 (재고와 판매가 어긋나지 않게 한 TX 권장)
 → 수금
```

원황 수출은 이 경로. `sales_tp` 문서값 `RETAIL`/`WHOLE` — 주문 경로는 `'NORMAL'`. 운영 코드값은 `m_common_code`와 대조.

---

## 4. 선주문 (DEC-002)

재고 0:

```
주문등록 성공
 → qty = 주문수량
 → allocated_qty = 0
 → 미배정 = qty
 → reserved_qty 변경 없음
 → t_sales_* 없음
```

**현재:** `StockMatrixPopup`은 가용 ≤ 0이어도 담을 수 있다. 저장 시 `reserved_qty += 주문수량` 전량 Hold. 재고 행이 없으면 `INSERT OR IGNORE` 후 Hold.

**문제:** 없는 재고까지 reserved가 올라간다. 줄 단위 100/30/70을 남기지 못한다.

**확정:** 주문 등록은 재고 부족으로 거부하지 않는다. Hold는 배정 시에만.

---

## 5. 부분배정 (DEC-003, DEC-008) — 저장재고형만

예: 주문 100 · 가용 30

| 필드 | 값 |
|------|----|
| `qty` | 100 |
| `allocated_qty` (누적 배정) | 30 |
| `unallocated_qty` | 70 |
| `shipped_qty` | 0 |
| `reserved_unshipped_qty` | 30 |
| `t_stock_master.reserved_qty` | +30 |

추가 포장 후 `allocated_qty`를 70·100까지 **증가**시킬 수 있다.  
제약: `0 <= allocated_qty <= qty`. 증분 배정은 **트랜잭션 안에서** 해당 stock row 가용재고를 재조회한 뒤만 허용.

**현재:** 컬럼 없음. Hold = 주문수량 전체. `StockMatrixPopup.get_stock_map`은 규격 GROUP BY라 `storage_dt`를 숨긴다.

---

## 6. 출고 조건 (DEC-020 — 출고방식 축)

**STOCK / 재고출고**

```
ship_qty <= allocated_qty - shipped_qty     -- reserved_unshipped_qty
```

미배정분만으로 STOCK 출고는 거부 (409).

**DIRECT / 즉시출고**

allocation 불필요. 위 STOCK 식을 적용하지 않음.  
수확/포장 실출고 수량으로 판매 생성. 재고/생산 수량 추적은 Stage 4 전 OPEN.

`shipped_qty` = CONFIRMED 판매상세 합 (컬럼 없음).  
**현재 PC는 부분출고 API/버튼이 없다.** 주문 저장 시 전량 판매 생성.

---

## 4.1 부분출고와 판매 건 (DEC-017 APPROVED)

**규칙: 출고 1회 = 판매 1건. 주문 1 : 판매 N.**

예: 주문 30박스

- 8/20 10박스 출고 → 판매 A 생성 (`sales_dt` = 그 출고 업무일)
- 8/21 20박스 출고 → 판매 B 생성 (판매 A를 수정하여 수량을 올리지 않음)

실제 출고일과 판매일·재고 출고·배송·수금·회계를 일치시키기 위한 것이다. 이미 CONFIRMED 된 판매/전표를 다음 출고 때문에 수정하지 않는다.

**현재 PC:** 지원하지 않음. `save_entire_order()`가 주문과 판매를 같은 TX에서 한 번에 만들고, `t_order_master.sales_no` 1개 + 판매 상세 전량. `stock_status='Y'` 세팅 없음.

연결 SSOT:

- `t_sales_master.order_no`
- `t_sales_detail.order_detail_id`

`t_order_master.sales_no`는 **legacy/reference 성격**이며, 주문 전체 판매 조회는 반드시 `t_sales_master.order_no` 기준으로 한다. 기존 호환을 위해 최초 출고 판매번호 또는 대표 참조값으로만 유지한다. 새 컬럼은 추가하지 않는다.

- `shipped_qty` = 해당 `order_detail_id`로 생성된 모든 CONFIRMED 판매상세 수량 합계.
- 출고 후에도 `allocated_qty`는 감소하지 않는다.
- `stock_status`: 부분출고면 `'N'`. 모든 주문상세 `shipped_qty == qty`일 때만 `'Y'`.
- 이행: 출고완료는 전 줄 `shipped_qty == qty`. 주문상태 배송완료는 `ST010400` (DEC-011 CLOSED).
- 화면에는 주문/배정/미배정/출고를 숫자로 보여 준다.

부분출고 **취소** (해당 판매 1건만) — 정책은 단계 6 OPEN. 방향만:

| | 재고 | 판매 | 회계 | 주문 |
|--|------|------|------|------|
| 방향 | `out_qty −`, `reserved_qty +` (`allocated_qty` 유지 → reserved_unshipped 복구) | 그 판매만 취소/역분개. 다른 출고 판매는 유지 | 그 `sales_no` 전표만 | `stock_status` N, 주문 완료 해제 |

1차 구현은 출고 후 취소 비활성 권고. 출고 후 판매취소는 단계 6 OPEN.

---

## 5. 출고확정 — 소매 단일 트랜잭션 (DEC-014 · DEC-017 APPROVED)

한 출고 **이벤트**의 DB 트랜잭션. 실패 시 전체 rollback. **항상 새 `sales_no`.** 기존 CONFIRMED 판매를 수정하지 않는다.

1. 출고 가능한 미출고 `t_order_alloc` 조회
2. FIFO(`storage_dt ASC`) 순서대로 `ship_qty` 배분
3. 각 `t_order_alloc.shipped_qty` 증가
4. 각 stock row `reserved_qty` 감소
5. 각 stock row `out_qty` 증가
6. `t_stock_log` OUT
7. **새 판매** 생성: `order_no`, `sales_source=ORDER`, `sales_status=CONFIRMED`, `sales_dt` = 실제 출고 업무일 `YYYY-MM-DD`
8. 판매상세: `order_detail_id` 필수, 해당 출고분 `ship_qty`만
9. 그 출고분에 해당하는 판매배송만 연결
10. **선입금 배분** (DEC-019 APPROVED): 남은 주문 선입금에서 `min(잔액, 그 판매금액)`을 이 판매에 적용. 초과 적용 금지. 결제수단은 주문의 선입금 결제수단 (DEC-028)
11. **회계**: 적용액 > 0이면 같은 TX에서 `t_cash_ledger` → `AccountManager.sync_ledger_by_basket('SALE', …)` → `t_ledger`
12. 판매마스터 `tot_paid_amt` = 적용액, `tot_unpaid_amt` = 판매금액 − 적용액. `sales_status`는 `CONFIRMED` 그대로 (DEC-029)
13. 모든 주문상세 `shipped_qty == qty`이면 `stock_status='Y'`, 이행=출고완료 (주문상태 `ST010400`)

금지: 재고만 감소 / 판매만 생성 / 전량 완료인데 판매 없음 / 기존 CONFIRMED 판매·전표 수정 / 선입금을 판매금액보다 많이 적용.

**현재 구현 (Stage4 feature):** `OrderShipService.confirm()`이 판매 master/detail/delivery 직후·order status 전에 동일 TX에서 선입금 순차 배분·cash/ledger를 수행한다. main/운영 미반영. 위 10~12는 구현됨.

출고 시 `allocated_qty` **유지**. stock `reserved_qty -= ship_qty`, `out_qty += ship_qty`.

**현재:** reserved만 증감. out 불변. `stock_status='Y'` 세팅 없음. 판매 저장은 재고 미갱신.

---

## 6. 가락 확정 트랜잭션 (DEC-010 APPROVED)

방향: `DRAFT → CONFIRMED` + 재고 출고를 **한 트랜잭션**.

권장 순서:

1. 대상이 `AUCTION_RT` + `DRAFT`인지 검증
2. 줄 수량만큼 **트랜잭션 안**에서 가용(`in-out-reserved`) 재조회
3. 부족 시 전체 rollback (409)
4. `out_qty +=`, log `OUT`
5. `sales_status=CONFIRMED`
6. 선택 수금 → ledger
7. 배송행: 초안에 없음 → DEC-016 OPEN. 없으면 확정 후 송장이 비어 운영 공백.

현재 구조상 바로 묶기 어려운 점:

| 갭 | 영향 | 보완 |
|----|------|------|
| confirm 함수 없음 | DRAFT 재저장해도 전표 스킵 | core `SalesConfirmService` 신설, PC 버튼 연결 |
| 초안이 reserved를 안 씀 | 확정 순간 재고가 다른 소매 배정과 경합 | TX 내 가용 재검증 필수 |
| 초안 무배송 | 출고와 송장 분리 | DEC-016 |
| 주문/`allocated_qty` 없음 | 해당 없음 | 가락은 판매 경로만 |

---

## 7. 주문상태와 이행상태 (DEC-013 APPROVED, DEC-011 CLOSED)

동일 개념으로 취급하지 않는다. **새 상태코드·새 컬럼을 임의로 추가하지 않는다.**

### 7.1 논리 상태 (문서 의미)

**주문상태:** 접수 · 완료 · 취소 (문서 논리)  
**운영 `status_cd` SSOT (DEC-011):** 예약접수 `ST010100` · 주문확정 `ST010200` · 배송준비 `ST010300` · 배송완료 `ST010400` · 취소 `ST010500`  
**이행상태:** 미배정 · 부분배정 · 배정완료 · 출고완료 (계산. ST01에 넣지 않음)

UI 예: `주문상태: 예약접수` / `재고상태: 부분배정`

### 7.2 현재 ST01 사용 상태

| 항목 | 확인 결과 |
|------|-----------|
| 운영 실코드 | `ST010100` 예약접수 · `ST010200` 주문확정 · `ST010300` 배송준비 · `ST010400` 배송완료 · `ST010500` 취소 (DEC-011 CLOSED) |
| 코드관리 | `CodeManager.get_common_codes('ST01')` → `m_common_code` (`code_cd`/`code_nm`) |
| 주문화면 콤보 | 필터·상세 모두 ST01 |
| 실제 저장 | Stage 2 신규 = `ST010100` (`OrderService`). PC `'10'`/`'20'` 저장 **폐기**. 확정/배송 워크플로 버튼은 Stage 3+ |
| 일괄확정/취소 | 버튼 있음, **미연결** (Stage 2에서 확장하지 않음) |
| 영농일지 폴백 | `ST010300`/`ST010400`/`ST010500`을 진행/완료/취소로 해석. 주문 의미와 충돌. **별도 이슈. Stage 2에서 수정 금지** |
| Stage 2 기본값 | `ST010100` |

### 7.3 이행상태를 기존 구조로 표현

새 컬럼 없이 계산 (주문 헤더 집계):

| 이행상태 | 계산 (확정 설계) |
|----------|------------------|
| 미배정 | `SUM(allocated_qty)=0` 이고 `SUM(shipped_qty)=0`. **오류 아님.** DIRECT 즉시출고 가능 |
| 부분배정 | `0 < SUM(allocated_qty) < SUM(qty)` (출고 일부가 있어도 미배정이 남으면 여기) |
| 배정완료 | 전 줄 `allocated_qty = qty` 이고 `SUM(shipped_qty) < SUM(qty)` |
| 출고완료 | `SUM(shipped_qty) = SUM(qty)` 이며 이때 `stock_status='Y'` |

화면 숫자는 주문 / 배정(`allocated_qty`) / 미배정 / 출고(`shipped_qty`) 네 칸. 내부에서만 누적 배정임을 구분한다.

보조 필드:

- `t_order_master.stock_status` 현재 `'N'`/`'Y'`. `'Y'` 전환 코드 없음 → 출고완료 플래그로 **재사용** (DEC 이행 컬럼 신설 안 함).
- `t_stock_status` 테이블은 baseline에만 있고 **Python 미사용**. 이번 설계에서 쓰지 않음.

### 7.4 기존 코드 매핑 (DEC-011 CLOSED)

| 논리 | 매핑 |
|------|------|
| 신규 주문 접수 | `ST010100` 예약접수 (Stage 2 기본값) |
| 주문확정 / 배송준비 / 배송완료 | `ST010200` / `ST010300` / `ST010400` (운영 ST01. 이행 4종과 별개) |
| 주문 취소 | `ST010500` |
| 이행 4종 | ST01에 넣지 **않음**. `allocated_qty` + `stock_status` + 판매상세 수량으로 계산 |
| `'10'` / `'20'` | ST01에 없음. PC 테스트 저장값. 폐기 대상 |

PC `'10'` 리터럴은 Stage 2 `OrderService` 신규 저장에서 제거. 과거 행 일괄변환은 하지 않음(운영 테스트데이터는 2026-08-17 초기화 완료).

---

## 8. 판매 상태 · 수금 상태 (DEC-029 APPROVED)

### 8.1 주문 생성/확정은 판매가 아니다

주문을 등록하거나 주문상태를 확정으로 바꾸는 것은 **판매가 아니다**. 판매는 **출고확정 시점**에 생성된다.

```
주문 등록/확정  ─(판매 아님)─→  출고확정  ──→  새 sales_no · CONFIRMED
                                            sales_dt = 그 출고 업무일 (ops)
                                            재고 OUT
```

출고 1회 = 판매 1건. 주문 1 : 판매 N (DEC-017).

### 8.2 판매상태 (`sales_status`)

**현재:** `sales_status` `DRAFT` \| `CONFIRMED`, `sales_source` `ORDER` \| `AUCTION_RT`.

- 신규 판매화면 기본 CONFIRMED. 경매 초안 DRAFT.
- DRAFT→CONFIRMED 버튼 없음.
- 주문 경로 INSERT는 두 컬럼을 안 넣음 → DEFAULT `CONFIRMED`/`ORDER` 추정. 전표는 안 남김.

**확정 설계:** `sales_status`는 **`DRAFT` / `CONFIRMED` 두 값만**.

| 경로 | 생성 시 | 확정 |
|------|---------|------|
| 소매 출고 | 출고 TX에서 CONFIRMED + (선입금 적용분이 있으면) 전표 | 출고와 동일 TX |
| 가락 | 기존 DRAFT+AUCTION_RT | confirm TX (DEC-010) |
| 수출/도매 | CONFIRMED (또는 임시 DRAFT — 추가 OPEN 없음, 1차는 CONFIRMED) | 출고 포함 TX |

**금지:** 새 status 문자열(`SHIPPED` 등) 추가. `PAID` / `UNPAID` 등 **수금 의미를 `sales_status`에 넣기**.

### 8.3 수금상태 — 금액 계산값 (컬럼 없음 · Stage6-0)

수금상태 전용 DB 컬럼을 만들지 않는다. **cash SUM** 기준으로 계산한다.

| API `payment_status` | UI label | 조건 |
|----------|----------|------|
| `null` | 수금대기 | `sales_status != CONFIRMED` |
| `UNPAID` | 미수 | CONFIRMED · `paid <= 0` |
| `PARTIAL` | 부분수금 | CONFIRMED · `0 < paid < tot_sales_amt` |
| `PAID` | 수금완료 | CONFIRMED · `MAX(0, tot_sales_amt − paid) <= 0` |

공통 helper: `core/sales_payment_constants.compute_payment_status`.

### 8.4 완료 개념 3종 — 섞지 않는다

| 용어 | 정의 | 근거 |
|------|------|------|
| **판매확정** | 그 판매의 `sales_status = CONFIRMED` | `t_sales_master` |
| **주문완료** | 주문상태 `ST010400` **AND** `stock_status='Y'` (전 줄 전량 출고) | DEC-011 · DEC-027 |
| **수금완료** | 그 판매의 `tot_unpaid_amt == 0` | 금액 계산 |

**금지:** 「판매완료 = 수금완료」로 취급 · 판매상태로 미수/수금완료를 표현 · 주문완료를 수금완료로 읽기.  
한 주문이 **주문완료**여도 판매별로 미수가 남을 수 있고, 반대로 **수금완료** 판매가 있어도 주문은 잔량 때문에 미완료일 수 있다.

### 8.5 판매 → 수금 흐름 (요약)

```
출고확정 → 새 판매 CONFIRMED
        → 선입금 순차 적용 (min(잔액, 판매금액))     [DEC-019]
        → t_cash_ledger → AccountManager → t_ledger
        → tot_paid_amt / tot_unpaid_amt
        → 미수 남으면 추가수금 (CONFIRMED 판매만)     [DEC-029]
        → tot_unpaid_amt = 0 → 수금완료
```

상세: [§12](#12-선입금--수금-dec-009--dec-019--dec-028--dec-029-approved).

### 8.6 판매상세 read-only (Stage6A)

판매목록 행 → `GET /farms/{farm_cd}/sales/{sales_no}` → Mobile `/orders/sales/:salesNo`. **SELECT only** — 수금등록·수정·취소·ledger/cash write 없음.

뒤로가기는 `/orders?tab=sales`로 복귀 (`router.replace`). 배송(`t_sales_delivery`) read-only 표시는 schema 가변성으로 **6A 제외**.

### 8.7 수금내역 read-only (Stage6B)

`GET /farms/{farm_cd}/sales/{sales_no}/payments` · Core `SalesPaymentService.get_payment_summary`.

**SSOT = `t_cash_ledger` 실제 행** (동일 method/slip 합산 금지 · `t_ledger`를 내역으로 표시 금지).

| `payment_source` | 조건 (`cash.order_no`만) | UI |
|------------------|--------------------------|-----|
| `GENERAL` | NULL/blank | 일반수금 |
| `ORDER_PREPAY` | 실값 존재 | 선입금 자동적용 (+ `source_order_no`) |

DRAFT도 GET 허용 · `payment_status=null` · legacy cash 숨기지 않음.

### 8.8 수금등록 (Stage6C · private main · 운영 미배포)

`POST /farms/{farm_cd}/sales/{sales_no}/payments` · Core `SalesPaymentService.add_payment` · **append only**. PUT/수정/삭제 **미구현**.

| 조건 | UX |
|------|-----|
| `sales_status=CONFIRMED` AND `unpaid_amt>0` | Mobile 수금내역 section **[수금 등록]** |
| DRAFT / 수금완료 | 버튼 없음 |

**provenance:** API adapter `source_order_no=None` → `cash.order_no NULL` → `GENERAL`.

**DEC-030:** Core general-payment write 경계에서 `sales_dt ≤ pay_dt ≤ today`. 선입금 자동적용(`source_order_no` 실값)은 Stage4 기존 정책 · DEC-030 대상 아님.

**DEC-030 (6C write 전용 · APPROVED · IMPLEMENTED):** 신규 일반 수금등록 `pay_dt`는 `sales_dt ≤ pay_dt ≤ today`만 허용 · blank → `PAY_DT_INVALID`. 판매 이전·미래 수금일 거부. 선입금 자동적용은 기존대로 `sales_dt`를 cash `pay_dt`로 사용 · DEC-030 대상 아님. legacy DB 자동보정 없음 · 조회만. `t_ledger.trans_dt = sales_dt` 불변.

---

## 9. 취소

| 경우 | 재고 | 판매 | 회계 | 주문 |
|------|------|------|------|------|
| 미배정 주문 취소 | 변경 없음 | 없음 | 없음 | 주문상태=취소 |
| 일부배정 · 출고 전 | 모든 미출고 `t_order_alloc`의 stock row `reserved_qty` 복구. CANCEL_HOLD. allocation 정리. `allocated_qty` 감소/0 | 없음 | 없음 | 취소 |
| 배정완료 · 출고 전 | 잔여 Hold = `reserved_unshipped` 전량 해제 (alloc row 기준) | 없음 | 없음 | 취소 |
| 부분출고 후 · 해당 판매만 취소 | 그 회차 `out−` `reserved+`. `allocated_qty` 유지 | 그 `sales_no`만 | 그 전표만 역분개 | `stock_status` N. **단계 6 OPEN** |
| 전량 출고 후 판매취소 | 전량 `out` 복구. 단순 DELETE 금지 | 연결된 판매 전부 | `t_ledger` 역분개. 현재 `delete_sales_data`는 전표·재고 없음 | 별도 정책. **단계 6 OPEN** |

출고 전 취소: 모든 미출고 `t_order_alloc`을 조회하여 각 stock row별 `reserved_qty`를 정확히 복구. 이미 출고된 allocation은 단순 취소 금지.

1차 권고: 출고 후 전량 취소는 **비활성**. 출고 후 판매취소 정책은 단계 6 OPEN.

**현재 주문 삭제 함수 없음.** 수정 시 CANCEL_HOLD는 주문 `qty` 전량·규격 키만 (`storage_dt` 없음).

---

## 10. 배송

| 코드 | 의미 (코드 주석) | 동작 |
|------|------------------|------|
| `LO010100` | 방문/직접인도 | 주소 비필수 |
| `LO010200` | 택배 | 박스 1개씩 `t_sales_delivery` 분할 |
| `LO010300` | 화물 · 경매 초안 기본 | |
| `LO010400` | 직배 | 주소 레이어 |

주문: `t_order_delivery`. 주석 `t_dlvry_detail`은 **실제 테이블 아님**.  
출고예정일: 배송 `planned_dt` 집계. 마스터 전용 컬럼 추가하지 않음.

부분출고 배송 (DEC-017): 각 출고 이벤트 판매에는 그 출고분에 해당하는 배송 데이터만 연결한다. 주문 배송계획 전체를 매번 복사하지 않는다. 한 주문배송 계획이 여러 출고로 나뉠 경우, 실제 출고수량만큼 판매배송행을 생성한다. 상세 알고리즘은 단계 4 구현 전 현재 `t_order_delivery` 구조를 기준으로 재검토하되, 1:N 판매 원칙은 변경하지 않는다.

채번: 주문 배송 실제 `{order_detail_id}-P{NN}` vs 워크스페이스 규칙 `{detail}-{3자리}` — 코드 우선.

---

## 11. 날짜 (DEC-012 APPROVED)

- **신규 저장:** `order_dt`, `sales_dt` = `YYYY-MM-DD`. 값은 `today_ops` (KST 업무일).
- **기존 데이터:** 일괄 변환하지 않음. 주문 경로는 `YYYYMMDD` 혼재.
- **조회:** 8자리면 하이픈 삽입, 이미 ISO면 그대로. API 응답은 ISO만.
- 시각 감사필드: `now_ops_str`.

---

## 12. 선입금 · 수금 (DEC-009 · DEC-019 · DEC-028 · DEC-029 APPROVED)

### 12.1 주문 단계 — 금액 + 결제수단, 회계 없음

주문접수에 저장하는 것은 **선입금 금액**과 **선입금 결제수단** 뿐이다 (DEC-009 · DEC-028).

| 조건 | 결제수단 |
|------|----------|
| `pre_pay_amt = 0` | **NULL**. 화면에 결제수단 입력을 노출하지 않음 |
| `pre_pay_amt > 0` | **필수**. 미입력 시 저장 거부 |

주문 단계 금지: `t_cash_ledger` INSERT · `t_ledger` INSERT · 전표번호 채번.  
**결제수단 저장은 전표 생성이 아니다.** 회계는 판매확정에서만 발생한다.  
선입금 결제수단 = **현금성 자산 계정**(실제 운영 코드 재확인 후 범위 확정). 채권(외상·미수)은 선입금 결제수단이 아니다 (DEC-028).

UI 용어는 **결제수단 · 수금액 · 미수금 · 수금상태**. 「수금방법」은 쓰지 않는다.

### 12.2 판매확정 시 선입금 순차 배분 (DEC-019 APPROVED)

출고확정으로 판매가 CONFIRMED 될 때, 그 주문의 **남은 선입금**을 그 판매에 적용한다.

```
회차 적용액 = min(남은 주문 선입금, 그 판매의 판매금액)
```

- 판매금액을 **초과 적용 금지**
- 남은 선입금은 **다음 출고 판매에 순차 적용** (판매확정이 빠른 순)
- 이미 CONFIRMED 된 판매·전표를 후속 출고 때문에 **다시 쓰지 않는다**
- 사용 결제수단 = 주문의 선입금 결제수단 (DEC-028)

예: 주문 30만 · 선입금 15만

| 회차 | 판매금액 | 선입금 적용 | 미수 | 남은 선입금 |
|------|----------|-------------|------|-------------|
| 판매1 | 10만 | 10만 | 0 | 5만 |
| 판매2 | 20만 | 5만 | 15만 | 0 |

폐기된 초안: 「선입금 전액을 첫 출고 판매에 적용」. 선입금 30만 · 첫 판매 10만에서 성립하지 않는다.

### 12.3 선입금 잔액 (컬럼 없음)

`prepay_balance` 컬럼을 **신설하지 않는다**.

```
남은 선입금 = t_order_master.pre_pay_amt
            − 그 주문의 CONFIRMED 판매에 적용된 선입금 합
```

**구현 (Stage4 feature):** `t_cash_ledger.order_no`로 구분한다. NULL=일반수금, 주문번호=선입금 자동적용. 신규 DDL 없음.

선수금(선수금 계정) 회계 설계는 계속 비범위.

### 12.4 추가수금 (DEC-029 APPROVED)

- **CONFIRMED 판매만** 수금 등록 가능. DRAFT 판매에는 수금·전표를 붙이지 않는다
- 등록 항목: **수금액 + 결제수단**
- 수금액 ≤ 그 판매의 미수금
- 한 트랜잭션: `t_cash_ledger` → `AccountManager.sync_ledger_by_basket('SALE', …)` → `t_ledger` → 판매마스터 `tot_paid_amt` / `tot_unpaid_amt` 갱신

---

## 13. 재고행별 allocation (DEC-018 APPROVED)

### 13.1 역할 분리

`t_stock_log`를 allocation **현재상태**의 SSOT로 사용하지 않는다.

| 대상 | 역할 |
|------|------|
| 가칭 `t_order_alloc` | 현재 주문상세 ↔ 실제 재고행 배정 관계 |
| `t_stock_log` | HOLD / CANCEL_HOLD / OUT **이력** |

실제 테이블명: `t_order_alloc` (Stage 3A 로컬). 운영 CREATE는 단계 3 전체 승인 후.

현재 로그에 부족한 `wh_cd` / `storage_dt` / `order_detail_id`를 allocation SSOT 목적으로 억지로 추가하지 않는다. 앞으로 생성되는 HOLD / CANCEL_HOLD / OUT 로그에는 가능한 범위에서 `order_no`, `order_detail_id`, `sales_no`, stock 자연키 식별정보를 남기는 방향을 설계할 수 있다. **현재 상태 복원은 `t_order_alloc`, 감사 이력은 `t_stock_log`.**

기존 HOLD → `t_order_alloc` 백필은 DEC-015 **금지 유지**. historical HOLD만으로는 DDL 차단하지 않음.

### 13.2 현재 `t_stock_log` (코드 INSERT — 이력 SSOT로 쓰기 부족)

`t_stock_master` 자연키:  
`farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt`

주문 HOLD (`order_page.py` 2941행):  
`farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, parent_raw_size, remark, reg_id, reg_dt`  
remark = `주문예약:{order_no}`

주문 CANCEL_HOLD (2818행): 동일 규격 키 + remark `주문수정전 복구:{order_no}`  
reserved UPDATE는 `storage_dt`/`wh_cd` **없음** (규격+연도만, 복수 row 오염 가능).

저장/생산 로그: `wh_cd`/`storage_dt`/`order_detail_id`/`stock_id` **없음**. Stage 5C 사전검토: [09 §20.1](./09_production_inventory_flow.md).

| 필요 정보 | HOLD 로그 |
|-----------|-----------|
| farm/item/variety/grade/size/weight/year | 있음 |
| qty, io_type HOLD/CANCEL_HOLD | 있음 |
| OUT (판매출고) | **현재 없음** (생산·폐기 OUT만) |
| wh_cd | 없음 |
| storage_dt | 없음 |
| order_detail_id / ref_id | 없음 (`order_no`만 remark) |

Hold 대상 row는 `MIN(storage_dt)` 1개만 고르는 **단일 바구니**에 가깝다. 이 때문에 로그 replay로는 줄×row 현재상태를 복원할 수 없다 → 전용 `t_order_alloc`.

### 13.3 `t_order_alloc` 최소 책임

과도한 구조를 만들지 않는다. 최소 추적 대상:

- `order_no`
- `order_detail_id`
- 실제 stock row 자연키 (`t_stock_master` 기준): `farm_cd`, `wh_cd`, `item_cd`, `variety_cd`, `grade_cd`, `size_cd`, `weight`, `harvest_year`, `storage_dt`
- `allocated_qty`
- `shipped_qty`
- 생성/수정 감사정보

PK/UNIQUE는 구현 전 실제 schema와 대조하여 확정.

의미 예:

- 주문상세 신고 15kg 특 25과 20박스
- stock A `storage_dt=2026-09-01` 8박스, stock B `storage_dt=2026-09-03` 12박스
- `t_order_alloc`: A allocated 8, B allocated 12
- `t_order_detail.allocated_qty` = 20

이 구조로 출고·배정해제·주문취소 시 정확한 stock row의 `reserved_qty`를 조정한다.

### 13.4 FIFO / LIFO (DEC-018 하위 운영규칙)

| 동작 | 기본 순서 | 비고 |
|------|-----------|------|
| 자동 재고배정 | FIFO `storage_dt ASC` | 동일 `storage_dt`는 기존 stock 자연키/row 정렬. 임의 규칙은 이번 단계에서 만들지 않음. 1차 모바일은 자동 FIFO. 향후 수동 재고행 선택 가능 |
| 배정해제 | LIFO (최근 잡은 stock row부터) | 먼저 잡은 오래된 재고를 유지해 FIFO 출고 원칙을 깨지 않기 위함 |
| 출고 소비 | FIFO `storage_dt ASC` | allocation row 기준 |

### 13.5 배정 TX

모두 한 트랜잭션. 실패 시 전체 rollback.

1. 주문상세 `qty` / allocated 검증
2. 가용재고를 TX 안에서 재조회
3. FIFO로 stock row 선택
4. `t_order_alloc` 증가/생성
5. `t_order_detail.allocated_qty` 증가
6. 해당 stock row `reserved_qty` 증가
7. `t_stock_log` HOLD 기록

### 13.6 배정해제 TX

미출고 allocation만 가능. `release_qty <= allocated_qty - shipped_qty`.

- `t_order_alloc` 감소
- `t_order_detail.allocated_qty` 감소
- 해당 stock `reserved_qty` 감소
- CANCEL_HOLD log

기본 해제 순서는 LIFO.

### 13.7 출고 TX

§5와 동일. allocation row 기준 FIFO 소비 → 새 판매 1건 → 단일 TX (DEC-014).

동시성: 같은 stock row를 여러 주문이 배정할 때 TX 안에서 그 row 가용(`in-out-reserved`) 재검증.

---

## 14. 재고가 생기는 시점 (참고)

| 이벤트 | 테이블 | 수량 |
|--------|--------|------|
| 원물 입고 (신고 저장) | `FR010300` `in_qty` | 20kg 단위 |
| 선별 생산 | 상품 `FR010100` `in_qty` +, 원물 `out_qty` + | 박스 |
| 폐기/실사 | `out_qty` / in·out 재기록 | — |
| 배정 | 행 `reserved_qty` +, 줄 `allocated_qty` + | 박스 |
| 배정 해제 | reserved −, allocated − (미출고분) | 박스 |
| 출고확정 | reserved −, out + | 박스 (`allocated_qty` 유지, `shipped_qty` 증가) |

원황/조생은 원물 입고 없이 상품 `in_qty`만 실사/생산으로 올릴 수 있음 (운영).
