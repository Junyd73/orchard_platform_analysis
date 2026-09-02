# 01. Overview — 주문/판매 통합

> **현재 기준 (2026-08-31):** DEC-035 HARVEST N:M — **APPROVED** · **IMPLEMENTED** · **REHEARSAL PASS** · **OPS APPLIED** · **OPERATIONAL PASS** ([06](./06_development_progress.md) · [07 DEC-035](./07_decisions.md)).
> Stage 6·Order→Ship·compact 목록 **운영 반영** (`fd963e0`) — DEC-035와 별개.
> DEC-036 — **APPROVED LOGICAL** · **APPROVED PHYSICAL DESIGN** · **NOT IMPLEMENTED**. DEC-037 — **APPROVED LOGICAL** · **NOT IMPLEMENTED**.
> **진행·게이트:** [06](./06_development_progress.md).

**표현 4층 (본 문서):**

| 층 | 의미 |
|----|------|
| **CURRENT** | 지금 FastAPI/Core/PC/모바일에 **실제 있는** 기능·코드 |
| **IMPLEMENTED IN GIT** | repo `main`에 merge된 구현 (DEC-035 A~C) |
| **REHEARSAL PASS** | copy DB migration/E2E 검증 완료 (D1/D2) |
| **OPS APPLIED** | PC·Lightsail **운영 DB DDL** + code/deploy **적용 완료** |
| **OPERATIONAL PASS** | 실제 운영환경에서 PC/Mobile HARVEST N:M **실사용 확인** |
| **OPS PENDING** | *(과거 표기)* 운영 미적용 — **DEC-035는 해당 없음 (2026-08-31 종료)** |
| **APPROVED PHYSICAL DESIGN** | DEC-036 `t_auction_ship_*` 물리계약 (**DDL·코드 미적용**) |
| **OPEN** | OPEN-QTY-DIFF · OPEN-DONE · OPEN-AUCTION-MATCH-CARDINALITY · OPEN-SHIP-STATE **(후속)** · 시장/법인 REST path 등 → [07](./07_decisions.md) |

`운영 적용 완료` · `production operational` · `deployed`는 **DEC-035 CURRENT**에 사용 가능.
DEC-036/037 등 **미구현 설계**에는 **APPROVED TARGET** · **OPEN**만 사용.
필요 시 **IMPLEMENTED IN GIT** · **REHEARSAL PASS** · **OPS APPLIED** · **OPERATIONAL PASS**를 **분리** 표기.

---

## 0. UX 최우선 원칙 (DEC-021)

**농부에게 일을 더 만들지 않는다.**

중복입력 금지 · 날짜/채번 자동 · 생산수량 판매 재입력 금지 · 선택 단계 강제 화면 금지.
**보강:** 내부키(`stock_seq`·출하 ID 등) **비노출** · 다중선택·일괄처리 우선 · 시스템이 아는 값은 **자동**.
경매·HARVEST N:M도 **추가 입력·추가 탭**을 만들지 않는 방향 ([04 §0](./04_mobile_screen.md)).

---

## 1. 프로젝트 목적

PC의 **수확·생산·재고·주문·판매·경매**를 모바일과 **공유 규칙**으로 연결하되,
**미완성 PC 로직을 복제하지 않고**, 기존 `StockPage`·`OrderPage`를 **확장**한다. (DEC-001)

**보강:**

- 기존 시스템 **전면 재작성 아님** · 기존 구조로 표현 불가능한 **최소 부분만** 보완 (DEC-025)
- 상세 정책 SSOT: [02](./02_domain_flow.md) · [03](./03_data_contract.md) · [04](./04_mobile_screen.md) · [05](./05_api_contract.md) · [07](./07_decisions.md) · [09](./09_production_inventory_flow.md)

- **재고/생산:** `ui/pages/stock_page.py` (원물·상품·생산확정·수율)
- **주문/판매:** `core/order_service.py`, allocation, Stage 5C 출고·판매

---

## 2. 최상위 업무 모델

**판매**가 공통 종착. 경로마다 중간 절차는 **다름**. TX·테이블·API 상세는 01에 **넣지 않음**.

### 생산·재고 축

```
영농일지 수확 → 포장/생산 → 상품재고
```

| 대표 원칙 | |
|-----------|--|
| 수확 **N건** → 포장/생산 **1회** · **부분사용** · **잔량** | **OPERATIONAL PASS** (DEC-035) |
| 수확 **저장** ≠ `t_stock_master` IN | CURRENT + DEC-022 |
| 생산확정 후 상품 **전량 IN** | CURRENT + DEC-023 |

상세: [09 §0·§16](./09_production_inventory_flow.md) · [03 §8A](./03_data_contract.md).

### 상품재고 이후 — 판매 3경로

```
                    ┌─ ① 직접판매 ──→ 판매확정 + OUT
상품재고 ──────────┼─ ② 주문 ──→ (선택 배정) ──→ 출고확정 ──→ 판매 + OUT
                    └─ ③ 경매 ──→ 넘기기 ──→ 출하중 ──→ 청과 확인/매칭 ──→ 판매확정 + OUT ──→ 정산
```

| | 직접/주문 | 경매 (TARGET) |
|--|-----------|----------------|
| 중간 | 배정 **선택** · 주문 **필수 아님** | 출하중 ≠ 판매 · ≠ DRAFT |
| OUT | 출고/판매확정 시 | **출하 시 OUT 없음** · 판매확정 시 최종 승인수량 OUT |
| reserved | 주문 HOLD만 | **사용 금지** |

경매 UI: **신규 최상위 탭 없음** — 판매 탭 내 **경매출하** 구역 ([04 §6.3](./04_mobile_screen.md)).
판매유형 7종·PC 근거: [09 §2·§3](./09_production_inventory_flow.md).

---

## 3. 확정된 통합 원칙

| 원칙 | DEC | 상태 |
|------|-----|------|
| UX: 일을 더 만들지 않음 | 021 | APPROVED |
| 주문 저장 ≠ 판매 생성 | 005 | APPROVED |
| 선주문 (재고 0 OK) | 002 | APPROVED |
| 부분배정, 배정은 **선택** | 003, 008 | APPROVED |
| 출고방식 STOCK/DIRECT (한 축) | 020 | APPROVED. 저장·DIRECT TX OPEN |
| 출고 1회 = 판매 1건 | 014, 017 | APPROVED |
| PC/core/API/mobile 동일 규칙 | 007 | APPROVED |
| 날짜 ISO | 012 | APPROVED |
| Stage 3A DDL | 008, 018 | **Core 구현 완료 · 운영 DDL 별도 게이트** |
| 주문상태 ≠ 이행상태 | 013 | APPROVED |
| 주문 단계 전표 없음 (금액+결제수단만) | 009, 028 | APPROVED |
| 선입금 **순차 배분** | 019 | APPROVED (2026-08-21) |
| 주문 선입금 **결제수단** | 028 | APPROVED · **운영 ALTER 반영** (`pre_pay_method_cd`) |
| **판매상태 ≠ 수금상태** | 029 | APPROVED |
| 규격 4요소 | 004 | APPROVED |
| 수확 ≠ stock IN | 022 | APPROVED |
| 생산확정 → 상품 **전량 IN** | 023 | APPROVED |
| **full-set production 금지 · 최소 보완 우선** | 025 | APPROVED |
| harvest_year = 원료 수확연도 | 026 | APPROVED |
| **수확잔량 · HARVEST N:M 소진** | **035** | **OPERATIONAL PASS** |
| **`reserved_qty` = 주문 HOLD 전용** | **018, 036** | APPROVED |
| **경매 출하 ≠ 판매 · ≠ DRAFT · 출하 시 OUT 없음** | **036** | **APPROVED (설계)** |
| **경매 판매확정 = 최종 승인수량 OUT · 원자 TX** | **037** | **APPROVED (설계)** |
| **판매 canonical 3분류 (S4A)** | S4A · **037** | CURRENT(컬럼) · TARGET(경매 자동) |
| ~~가락 DRAFT→CONFIRMED+OUT~~ | **010** | **SUPERSEDED → 036/037** |

### 판매 3분류 (업무 축)

| 축 | 의미 |
|----|------|
| 판매유형 | 소매 / 도매 / 수출 |
| 판매구분 | 일반 / 명절 / **경매판매** 등 |
| 판매경로 | 직접판매 / 주문출고 / **경매연동** |

**경매 판매확정 (TARGET):** 사용자 선택 없이 **도매 · 경매판매 · 경매연동** 자동 (코드값 → [03 §4.2](./03_data_contract.md) · [05 §9C](./05_api_contract.md)).

**legacy:** `sales_tp` · `sales_source`(`AUCTION_RT` DRAFT 등) **CURRENT 유지** · 폐기 표현 금지.

### 경매 판매확정 — 차이 (OPEN-QTY-DIFF)

판매확정은 **최종 승인수량**을 OUT한다. 출하수량과 확정수량의 **차이 처리**는 **OPEN-QTY-DIFF**.
**금지:** 판매확정 시 출하 **전체** 자동종료 · 차이수량 자동 가용복귀 · 자동 감모/OUT.

**금지 (추가):** 품종 if로 STOCK/DIRECT·판매유형 자동 분기 · 경매를 **DRAFT/OUT/reserved**로 표현 · **ShipConfirm**에 경매 출하 합치기.

---

## 4. 현재 구현 기준

### Stage 3A (5A) — §7과 동일 층

**Stage 3A(5A): allocation Core/API 구현 완료.**
**운영 DB DDL 적용 · main merge/배포** = **별도 게이트** ([06 §3A](./06_development_progress.md) · [AGENTS.md](../../AGENTS.md)).

- `allocated_qty`, `t_order_alloc`, FIFO/LIFO, HOLD — **유지**
- `allocated_qty=0` **정상**. 생산→바로판매에 alloc **강제 없음**
- [02 §3·§4](./02_domain_flow.md) 배정·STOCK 출고

### CURRENT / APPROVED TARGET / OPEN (요약)

| | 대표 |
|--|------|
| **CURRENT** | 주문 CRUD · allocation Core/API · Stage H/P 생산·수확 **HARVEST N:M** · fruit-stock · **ShipConfirm** 주문/DIRECT 판매+OUT · sales GET/수금(git main 반영 · ops 미배포 — [06](./06_development_progress.md)) · PC **`AUCTION_RT`+DRAFT** · 경매 출하 REST **없음** |
| **APPROVED TARGET** | DEC-036 **`t_auction_ship_*`** · transit 가용 공식 · DEC-037 판매확정 |
| **OPEN** | OPEN-QTY-DIFF · OPEN-DONE · OPEN-AUCTION-MATCH-CARDINALITY · OPEN-SHIP-STATE **(후속)** · 시장/법인 REST path · 출하 취소/정정 → [§8](#8-주요-open) · [07](./07_decisions.md) |

---

## 5. 개발 범위·설계 경계

**범위:** 모바일 **판매관리** Shell · 공통 Order/Allocation/Ship · PC P0(판매 분리·출고 TX 등)

### 여전히 금지 / 비범위

- StockPage **전면 교체**
- **full-set** `t_production_master/detail` **신규 시스템** (DEC-025)
- 사용자 **batch/stock/work 내부키** 관리
- Stage **3B** 배정 UI (후순위)
- 경매 출하를 **`POST …/shipments/confirm`** 의미에 **합치기**

### 승인된 후속설계 (범위에 가까움 · **미구현**)

- DEC-036 **`t_auction_ship_master`/`detail`** ([03 §8B](./03_data_contract.md))

**DEC-035:** **OPERATIONAL PASS** — PC·Lightsail OPS DDL **APPLIED** · Mobile/PWA N:M **실사용 PASS** ([06](./06_development_progress.md) · [07 DEC-035](./07_decisions.md)).

**정확한 표현:** DEC-035 최소 보완구조는 **git 구현 + 운영 적용 완료**. DEC-036 물리설계 **APPROVED (2026-08-31)** · **구현·DDL 미적용**. PC 생산확정 HARVEST N:M **화면 UI 보완** = 모바일 마무리 후 **별도 PC 단계** (기능 장애/blocker **아님**).

### OPEN (01에서는 링크만)

실제 테이블 · 컬럼 · 상태코드 · endpoint/payload → [07](./07_decisions.md) · [03 §12](./03_data_contract.md) · [05](./05_api_contract.md)

**삭제됨 (과거 오류):** ~~Stage 5C 판매 OUT 비범위~~ — 5C ShipConfirm **CURRENT 구현**.

---

## 5.1 모바일 판매관리 Shell (2026-08-19)

- 하단 5탭 5번째: **판매관리** (`/orders`, `nav-orders` 유지)
- 상단 4탭: **포장/생산 · 재고 · 주문 · 판매** — 업무 분류 (**강제 workflow 아님**)
- 초기 선택: **주문**
- 포장/생산·재고: Stage P/5B **실기능**. 경매 **신규 최상위 탭 없음** — 판매 탭 **경매출하** 구역 ([04 §6.3](./04_mobile_screen.md))

---

## 6. 기존 시스템 재사용

| 자산 | 재사용 | 비고 |
|------|--------|------|
| 재고/생산 | `stock_page.py` · `ProductionService` | HARVEST N:M = **최소 보완** (클래스명 OPEN) |
| 주문/배정 | `order_service` · `order_allocation_service` | `reserved` = **주문 HOLD 전용** |
| 판매/출고 | `order_ship_service` · `sales_query` · `sales_payment` | 경매 출하 = **별도 논리 TX** (ShipConfirm **아님**) |
| 경매/시세 | `market_price_page.py` · `market_price_settlement` | **CURRENT:** `AUCTION_RT` DRAFT ≠ 출하 SSOT · 매칭 read **가능성**만 |
| 회계 | `account_manager.py` | CONFIRMED · 기존 엔진 **재사용** |
| 업무일 | `today_ops` / `now_ops_str` | |

**금지:** `save_realtime_auction_draft`를 **새 출하 SSOT**처럼 기술 · 신규 Service **클래스명 확정**.

---

## 7. 단계 계획

역사적 번호(3A/H/P/S) 유지. **flat `완료·운영` 단독 표기 금지** — [§4](#4-현재-구현-기준)와 **일치**.

| 단계 | 목표 | 상태 (CURRENT 요약) |
|------|------|---------------------|
| 0 | 설계 / PC 분석 / 업무규칙 | **완료** (설계 이력) |
| 1 | 모바일 진입·라우팅 | **Core 구현 · git main · ops 과거 반영** — [06](./06_development_progress.md) |
| 2 | 주문 CRUD·고객·배송 | **Core 구현 · git main · ops 과거 반영** — [06](./06_development_progress.md) |
| 3 (=H) | 수확기록 (품종·상자) · **HARVEST N:M** | **OPERATIONAL PASS** · ops DDL **APPLIED** — [06](./06_development_progress.md) |
| 4 (=P) | PACK/PROCESS · IN/OUT | **Core 구현 · git main** · HARVEST N:M confirm **OPERATIONAL** · ops [06](./06_development_progress.md) |
| 5A (=3A) | allocation HOLD/RELEASE | **Core/API 구현 · git main · ops allocation DDL 별도 게이트** — [06](./06_development_progress.md) |
| 5B | fruit-stock 조회·이력 | **Core 구현 · git main** · ops [06](./06_development_progress.md) |
| 5C (=S) | ShipConfirm 판매+OUT | **Core+HTTP 구현 · git main** · ops `fd963e0` 계열(과거 기록) — [06](./06_development_progress.md) |
| 6 | 모바일 출고 UX + Order→Ship | **Core 구현 · git main** · ops `fd963e0` 계열(과거 기록) — [06](./06_development_progress.md) |
| — | 판매상세·수금·PC 잔여 · S4A | **git main 반영 · ops 미배포** — [06](./06_development_progress.md) |
| 7 | **경매 출하 → 출하중 → 청과 확인/매칭 → 판매확정 → 정산** | **예정** (DEC-016 OPEN · **DEC-010 SUPERSEDED**) |
| 8 | 통합 회귀·PC/PWA 정합 | **예정** |

**개발 순서 SSOT:** 06 **다음 갱신**에서 확정. 01에서 **신규 Stage 번호 추가 금지**.

### 후속 보완설계 — 승인 · 미구현 (2026-08-27)

| DEC | 내용 |
|-----|------|
| **035** | HARVEST N:M · 수확잔량 · 소진이력 |
| **036** | 경매 출하 · 출하중 · 가용 제외 |
| **037** | 경매 판매확정 · SA 자동 · 최종 승인 OUT |

Stage H/P를 **미완료로 되돌리지 않음** — 위는 **기존 기능 위 후속 보완**.

---

## 8. 주요 OPEN

01 = **대표 묶음**만. 세부 → [07](./07_decisions.md) · [03 §12](./03_data_contract.md) · [05 §12](./05_api_contract.md).

| 묶음 | 대표 OPEN |
|------|-----------|
| **수확·생산** | OPEN-DONE · ~~OPS DDL PENDING(DEC-035)~~ → **DEC-035 OPS APPLIED** |
| **경매 출하** | ~~OPEN-DDL~~ **CLOSED** (physical) · OPEN-SHIP-STATE **(후속)** · 출하 취소/정정 · REST path |
| **청과·매칭** | OPEN-AUCTION-MATCH-CARDINALITY · 시장/법인 유효조합·API |
| **판매확정** | OPEN-QTY-DIFF · 차이 시 confirm 허용 · DRAFT 필수 · **DEC-016** (가락 배송) |

**유지 (세부 07):** DEC-015 (HOLD 백필) · DEC-020 (출고방식 저장) — **임의 CLOSED 금지**.

DEC-019 · DEC-028(운영 ALTER) · provenance CLOSED 등 **완료 항목**은 OPEN 목록에서 **제외**.

---

## 9. 상세문서 · 코드 근거

### 설계 SSOT (우선)

| 문서 | 역할 |
|------|------|
| [02](./02_domain_flow.md) | domain flow · TX 개요 |
| [03](./03_data_contract.md) | data contract |
| [04](./04_mobile_screen.md) | mobile UX |
| [05](./05_api_contract.md) | API contract |
| [07](./07_decisions.md) | decisions · OPEN |
| [09](./09_production_inventory_flow.md) | production · inventory |
| [06](./06_development_progress.md) | **진행·게이트 참고** (재설계 반영 **전**일 수 있음) |

### 코드 (확인된 대표 경로)

| 영역 | 위치 |
|------|------|
| 생산·수확 | `core/production_service.py` · `core/work_harvest_schema.py` |
| 재고·배정 | `core/order_allocation_service.py` |
| 소매 출고 | `core/order_ship_service.py` · `POST …/shipments/confirm` |
| 판매·수금 | `core/sales_query_service.py` · `core/sales_payment_service.py` |
| PC 경매 legacy | `ui/pages/market_price_page.py` (`save_realtime_auction_draft`) |
| 모바일 | `PackProdPanel.vue` · `StockView.vue` · `ShipConfirmView` |

**01에서 장문 복제 금지:** HARVEST 3축 → 03 · 경매 헤더/라인 → 03 · API → 05 · 화면 → 04 · TX → 02/05 · OPEN 전체 → 07 · 생산 상세 → 09.
