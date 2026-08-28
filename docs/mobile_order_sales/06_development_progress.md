# 06. Development progress

## 문서 역할 / 상태 범례

**역할:** 본 문서(06)는 **구현 진행상태·개발 게이트 SSOT**이다. 과거 개발기록을 보존하며, **설계 정책 SSOT는 아니다.**

**설계 SSOT:** [01 Overview](./01_overview.md) · [02 Domain flow](./02_domain_flow.md) · [03 Data contract](./03_data_contract.md) · [04 Mobile UX](./04_mobile_screen.md) · [05 API contract](./05_api_contract.md) · [07 Decisions / OPEN](./07_decisions.md) · [09 Production / Inventory](./09_production_inventory_flow.md)

**상태 구분:**

| 구분 | 의미 |
|------|------|
| **CURRENT IMPLEMENTATION** | repo·코드에서 확인된 사실 |
| **APPROVED NEXT DESIGN** | 01~05·07·09에서 승인됐으나 **미구현** |
| **HISTORICAL SNAPSHOT** | 과거 당시 merge·테스트·배포 기록 |

**표기 원칙:**

- **Core/API** · **git main** · **ops 배포** · **ops DDL**을 `완료·운영` 한 단어로 **뭉개지 않음**
- `git main 반영` = repo 사실 · `ops 미배포` = 문서·SHA 기준 확인 범위 · `ops 상태 미확인` = 외부 미확인
- ops 상태는 **실제 배포/DB 확인이 있을 때만** 확정. 이번 문서 수정 시 ops SSH/DB **미확인**
- 2026-08-27~28 설계 재정합은 **구현 완료가 아님**

**조사 기준:** git `main` @ `bb8c872` (2026-08-28) · ops backend 기록 SHA `b48ca8b` (Stage5, **과거 이력** — 이번 작업에서 임의 갱신 없음)

---

## CHANGELOG — 설계 재정합 (2026-08-27~28)

| 항목 | 내용 |
|------|------|
| DEC-010 | **SUPERSEDED** — 경매 = 출하→청과→판매확정 흐름으로 대체 |
| DEC-035 | HARVEST N:M / 수확잔량 / 최소 consumption |
| DEC-036 | 경매 출하 / 출하중 / 가용 제외 |
| DEC-037 | 경매 판매확정 / 최종 승인수량 OUT |
| 문서 | 01·02·03·04·05·07·09 재정합 |

**상태:** `APPROVED DESIGN · local documentation updated · uncommitted`

- 설계문서 01~05·07·09 및 본 06은 **working tree 수정 상태** · **commit/push 전**
- **IMPLEMENTED / 운영 / 배포완료 아님**
- 2026-08-17 Stage 0 승인([아래 HISTORICAL](#단계-0-산출물)) 이후 **설계가 확장·재정합**됨 — 「다시 열지 않음」을 **현재 규칙 frozen**으로 읽지 않음

---

## CURRENT IMPLEMENTATION — Stage 표

| Stage | 기능 | Core/API | git main | ops / DDL |
|-------|------|----------|----------|-----------|
| 0 | 주문·판매·재고 설계 / PC 기준 | — | — | HISTORICAL (2026-08-17) |
| 1 | 모바일 진입·메뉴·라우팅 | **구현** | **반영** | ops 반영 (과거 기록) |
| 2 | 주문 조회·등록·수정·취소 | **구현** | **반영** | ops 반영 (과거 기록) |
| 3 (=H) | 수확기록 — 품종·콘테이너 (**단일 HARVEST**) | **구현** | **반영** | harvest DDL **ops 확인 필요** |
| 4 (=P) | 생산/변환 PACK·PROCESS | **구현** | **반영** | core 반영 · ops **미확인** |
| 5A (=3A) | 재고배정 HOLD/RELEASE/allocation | **구현** | **반영** (`OrderAllocationService`) | **ops allocation DDL 별도 게이트** · ops 적용 **미확인** |
| 5B | fruit-stock 조회·이력 | **구현** | **반영** | ops **미확인** |
| 5C (=S) | OrderShip — 판매+OUT (**경매 출하 아님**) | **구현** | **반영** | Stage6 UX ops **`fd963e0` 계열** · trace DDL ops **미확인** |
| 6 | ShipConfirm UX · Order→Ship Step1~3 | **구현** | **반영** | ops **`fd963e0` 계열** (과거 기록) |
| 7* | 경매 출하→청과→판매확정→정산 | — | — | **APPROVED NEXT** ([아래](#approved-next-design)) |
| 8* | 통합 회귀 · 단계적 migration · 배포 | — | — | **예정** |

\*Stage 7·8은 **기존 게이트 번호 유지**. Stage 7 **TARGET 의미만** 갱신. 신규 Stage 번호 **부여 없음**.

**HARVEST N:M (DEC-035):** Stage H **단일 수확 생산 = CURRENT**. 복수 수확·잔량 = **APPROVED NEXT** — H/P를 미완료로 **되돌리지 않음**.

---

## git main 반영 · ops 미배포 (현재 확인 기준)

ops backend 기록: **`b48ca8b`** (Stage5 판매목록 수준, **과거 SHA**). git `main` @ `bb8c872`에는 아래가 **코드상 존재**하나, **ops 배포 완료로 확정하지 않음**.

| 항목 | Core/API | git main | ops (문서 기준) |
|------|----------|----------|-----------------|
| Stage4 선입금·수금 Core·배분 | **구현** | **반영** | ops 반영 (과거 기록 · `fb413a3`/`b48ca8b` 계열) |
| Stage5 판매목록 | **구현** | **반영** | ops **`b48ca8b`** (과거 기록) |
| Stage6-0 수금상태 조회 계약 | **구현** | **반영** | **미배포** |
| Stage6A 판매상세 GET + Mobile | **구현** | **반영** (`e46b9e5` 계열) | **미배포** |
| Stage6B payments GET | **구현** | **반영** (`96d690f` 계열) | **미배포** |
| Stage6C payments POST | **구현** | **반영** (`885144e` 계열) | **미배포** |
| Stage7A PC 출고확정 판매 보호 | **구현** | **반영** (`82dba73` 계열) | **미배포** |
| Stage7B-1/2/7B PC 수금 | **구현** | **반영** | **미배포** |
| S4A | DIRECT 판매 class Core/API | **구현** | **반영** (`bb8c872`) | **미배포** |
| DEC-030~034 | Core validation / PC guards | **IMPLEMENTED** | **반영** | ops **미확인** |

**게이트:** cross-review · ops SHA/DDL 회귀범위 확인 · **배포는 별도 대표 승인** (문서 정합과 분리).

---

## APPROVED NEXT DESIGN

설계 상세는 01~05·07·09 참조. **체크 완료 표기 금지.**

### A. HARVEST N:M — DEC-035

**CURRENT:** 단일 HARVEST 선택 생산.

**TARGET:** 복수 수확 · 부분소진 · 잔량 · 최소 consumption 이력.

**OPEN:** OPEN-DDL · production confirmation persistent identity · OPEN-DONE

### B. 경매 출하 — DEC-036

**TARGET:** 상품재고 다중선택 · 경매 넘기기 · 출하중 · 가용에서 유효 출하분 제외 · reserved/out **선차감 없음**.

**OPEN:** OPEN-DDL · OPEN-SHIP-STATE · stock cardinality · 가용 구현

**경계:** Stage 5C `OrderShipService` / ShipConfirm = **주문·직접판매 OUT**. 경매 출하 **포함 아님**.

### C. 청과 확인/매칭

**TARGET:** 농장 출하수량 유지 · 청과 확인수량 별도 · 가격/경매결과 연결.

**OPEN:** OPEN-AUCTION-MATCH-CARDINALITY · 시장/법인 SSOT/API · 데이터 source · 자동/수동 매칭

### D. 경매 판매확정 — DEC-037

**TARGET:** 최종 승인수량 OUT · CONFIRMED · SALE stock log · 도매/경매판매/경매연동 자동 · 원자 TX.

**OPEN:** OPEN-QTY-DIFF · 차이 시 confirm 정책 · DRAFT 필수 여부 · DEC-016

**20→19 진행계획 (06 수준):** 최종 승인수량 = 판매 OUT · 차이 = OPEN-QTY-DIFF · 차이 **자동가용복귀/자동감모/출하 전체 자동종료 금지** · 차이 confirm 허용/차단 **결정 전 구현 금지**. 세부는 [07](./07_decisions.md) · [05](./05_api_contract.md).

**CURRENT legacy:** PC `AUCTION_RT + DRAFT` 저장 경로는 **존재 가능** — **경매 출하 SSOT 아님**. DEC-010 = [HISTORY](#dec-010--draftconfirmed--history).

---

## 다음 개발 게이트

**후속 개발순서 후보 / 대표 승인 필요** — 신규 Stage 번호 **부여 없음**.

### 문서 게이트

01~05·07·09·06 정합 → 전체 교차검토 → 대표 승인 → commit/merge
(**이번 작업에서 commit/merge 실행 없음**)

### 기존 미배포 기능 게이트

git main 반영 · ops 미배포: 6A~7B · S4A 등 — ops SHA · 필요 DDL · 회귀범위 확인 후 **배포 별도 결정**.

### 신규 구현 순서 후보

1. DEC-035 물리설계
2. HARVEST N:M Core/API/Mobile
3. DEC-036 물리설계
4. 경매 출하 Core/API/Mobile
5. 시장/법인 + 청과결과 read/매칭
6. OPEN-AUCTION-MATCH-CARDINALITY 실데이터 검증
7. OPEN-QTY-DIFF 정책
8. DEC-037 경매 판매확정
9. 통합 회귀 / **승인된** migration / 운영 배포

**Stage 7 (TARGET 의미):** 경매 출하 → 출하중 → 청과 확인/매칭 → 판매확정 → 정산.
설명형 sub-gate(출하/가용 · 청과/매칭 · 판매확정/정산)로만 분리 — **`7a/7b/7c` 식별자 생성 없음**.

**Stage 8:** 통합 회귀 · PC/PWA 정합 · **승인된 migration만** 단계 적용 · 사전점검 · 의존성 · rollback · 단계별 회귀 · 최종 배포 승인. allocation/harvest/auction **일괄 적용 표현 금지**.

**새 경매 TARGET 흐름:**

```
상품재고 → 경매 넘기기 → 출하중 → 청과 확인/매칭 → 판매확정 → 정산
```

---

## 구현 전 정책 BLOCKER

정책을 **실제로 닫지 않음**. 개발순서상 **필요 시점**만 표시.

| 항목 | 분류 | 필요한 시점 |
|------|------|-------------|
| 수확 최소 DDL | **BLOCKER** | HARVEST N:M 구현 전 |
| 생산확정 영속 식별 | **BLOCKER** | HARVEST N:M 구현 전 |
| OPEN-DONE | **CAN-DEFER** | N:M 1차 |
| 경매 출하 최소 DDL | **BLOCKER** | 경매 출하 구현 전 |
| OPEN-SHIP-STATE | **BLOCKER** | 경매 출하 구현 전 |
| 가용 집계 방식 | **BLOCKER** | 경매 출하/fruit-stock |
| stock cardinality | **BLOCKER** | 출하 생성 |
| OPEN-AUCTION-MATCH-CARDINALITY | **BLOCKER** | 매칭 write 확정 전 |
| 시장/법인 SSOT/API | **BLOCKER** | 모바일 경매 UX |
| OPEN-QTY-DIFF | **BLOCKER** | 경매 판매확정 전 |
| 차이 시 confirm 정책 | **BLOCKER** | DEC-037 구현 전 |
| DRAFT 필수 여부 | **CAN-DEFER** | 구체 API 설계까지 |
| DEC-016 | **CAN-DEFER** | 경매 confirm MVP와 분리 가능 |
| 출하 취소/정정 | **CAN-DEFER** | 출하 v1 이후 |
| DEC-015 / DEC-020 저장 | **CAN-DEFER** | 경매와 직교 |

---

## HISTORY 안내

**아래 섹션부터**는 과거 시점의 merge·테스트·배포 기록이다. **CURRENT SSOT가 아님.**

- 과거 SHA · E2E · T-* ID **보존**
- 「private main merge 아님」「merge 대기」 등은 **당시 표현**
- [2026-08-19 권장 후속순서](#권장-후속-개발순서-2026-08-19) · [2026-08-21 순서](#2026-08-21--선입금수금-정책-확정)의 `가락 DRAFT→CONFIRMED` = **HISTORY** (미래 TARGET 아님)

**SHA 스냅샷 (과거):** Stage6C merge `e8b62f9` · Stage7A `82dba73` · feature `6181f69` · review `86af693` · ops backend `b48ca8b`(Stage5)

---

## DEC-010 / DRAFT→CONFIRMED — HISTORY

DEC-010 = **SUPERSEDED**. `DRAFT→CONFIRMED+OUT` 단계 경매 목표는 **폐기**.

- T-AUC-01 등 테스트 ID는 **당시 시나리오**로 보존
- PC `AUCTION_RT` DRAFT 저장 = **legacy CURRENT** 가능 · **경매 출하 SSOT 아님**
- 미래 개발 목표는 [APPROVED NEXT DESIGN](#approved-next-design) 참조

---

## 역사적 개발 기록 (2026-08-19 이전 게이트 표)

> **HISTORICAL — 당시 상태.** **CURRENT SSOT가 아님.** [상단 CURRENT IMPLEMENTATION](#current-implementation--stage-표) 참조.

아래는 **당시 로컬 진행 스냅샷**이다. **현재 운영 상태로 읽지 말 것.**  
「main 미머지」「운영 미적용」「Mobile UI 후속」은 **당시 표현**이며, Stage 6·출고 Core는 이후 ops 반영됨 (과거 기록 `fd963e0` 계열).

### (역사) Stage 표 스냅샷 — 2026-08-19

| 단계 | 목표 | 상태 (당시) |
|------|------|------|
| 0 | 주문·판매·재고 전체 설계 / PC 기준 분석 / 업무규칙 확정 | **완료** |
| 1 | 모바일 주문/판매 진입구조·메뉴·라우팅 | **완료** |
| 2 | 주문관리 — 조회·등록·수정·취소·고객·배송지 | **완료** |
| 3 (=H) | 수확기록 확장 — 영농일지 품종·콘테이너 수량 | **완료** (당시: main 미머지) |
| 4 (=P) | 생산/변환 — PACK·PROCESS·원물 OUT·생산품 IN | **완료** (당시: main 미머지) |
| 5A (=3A) | 재고배정 Core — HOLD / RELEASE / allocation | **완료** (당시: main 미머지) |
| 5B | 재고관리 — 조회·상태·이력·생산/배정 정합성 | **완료** (당시: main 미머지) |
| 5C (=S) | 공통 출고·판매 Core — 실제 판매확정·상품 OUT | **Core+HTTP 완료** (당시: Mobile UI 후속 · main 미머지) |
| 6 | 모바일 출고·배정·판매 UX | **로컬 완료** (당시: main 미머지 · 운영 미적용) |
| 7 | 가락시장 경매→판매확정·정산 | **예정** (당시 표현 · DEC-010 경로) |
| 8 | 통합 회귀·PC/PWA 정합·운영 Migration·배포 | **예정** |

역사적 게이트 번호(3A/H/P/S)는 코드·커밋 메시지에 남아 있다.

## 게이트 (기존 번호 유지 · HISTORICAL)

> **HISTORICAL — 2026-08-19~21 당시 게이트 표.** PC/Core/API/Mobile/Test 열은 **당시 스냅샷**. [상단 CURRENT](#current-implementation--stage-표)와 **불일치 가능**.

```
0 설계 최종승인 (완료)
 → 1 메뉴/라우트
 → 2 주문 조회/등록
 → 3A 저장재고형 선택적 재고배정  (당시: 이후 운영 반영 예정)
 → [권장] 수확기록 → 생산확장 → 판매/출고 OUT TX
 → 3B 모바일 배정 UI  (3A 직후 아님 · 후순위)
 → 5 판매관리 (목록·상세·수금 — 당시 다음 개발순서 5·6)
 → 6 경매/수금/회계 (수금 Core·선입금 배분 — 당시 순서 2~4 · 가락은 8)
 → 7 회귀/운영검증
```

기존 단계 4(출고→판매)는 **권장 후속의 판매/출고 공통 TX**와 같음. 번호만 유지. **이미 ops 반영된 Stage 6 출고 UX를 이 순서에 다시 끼워 넣지 않는다.**

| 단계 | 목표 | 상태 | PC | Core | API | Mobile | Test | 대표 승인 |
|------|------|------|----|------|-----|--------|------|-----------|
| 0. 설계 | 본 폴더 문서 · 규칙 합의 | **완료** | — | — | — | — | 문서 리뷰 | **최종승인 완료** (2026-08-17) |
| 1. 메뉴/라우트 | 하단 주문/판매 · 내정보 이동 | **완료 / 운영** | 없음 | 없음 | 없음 | 셸 | T-NAV-* | **승인** (2026-08-17) |
| 2. 주문 조회/등록 | 선주문 저장 (판매·전표 없음) | **완료 / 운영** | 주문만 저장 | OrderService | GET/POST orders | 목록·등록·수정 | T-ORD-01 | **승인** (2026-08-19) |
| 3A. 재고배정 | 저장재고형 **선택** 배정 · Hold · `t_order_alloc` | **완료** (당시: ops 반영 `fd963e0` 계열) | Hold 키 | Allocation | allocations | 조회만 | 42 passed | 당시 ops 반영 기록 |
| 3B. 배정 UI | 모바일 배정 UX (필수단계처럼 보이지 않게) | **후순위** | — | 3A 재사용 | 3A 재사용 | 미착수 | — | 수확·생산·OUT TX 이후 |
| 4. 출고→판매 | 상품 OUT + 판매 · STOCK/DIRECT | **완료** (당시: ops 반영) | 미위임(PC) | OrderShip | POST shipments/confirm | `/orders/ship` + Step1~3 | T-SHIP-* | Stage 6 ops 기록 |
| 5. 판매관리 | 목록·상세·수금 표시 | **당시 예정** (이후 git main 반영) | 재저장 보존 | SalesService | GET/PUT sales | 판매 탭 | T-SAL-01 | 수금 Core 후 |
| 6. 경매/수금/회계 | 선입금·수금 Core · payments · 가락 | **당시 예정** (수금 Core는 이후 ops/git main) | 확정 버튼 | Confirm+Account | confirm/payments | 수금 UI | T-AUC/PAY | DEC-016 등 · DEC-010 **HISTORY** |
| 7. 회귀/운영 | PC+모바일+관찰/일지/농약 | **당시 예정** | 회귀 | — | health | 스모크 | T-REG-01 | 배포 승인 |

## 단계 0 산출물

> **HISTORICAL — 2026-08-17 당시 Stage 0 승인 기록.** 2026-08-27~28 설계 재정합([CHANGELOG](#changelog--설계-재정합-2026-08-2728)) 이후에도 **과거 산출물로 보존**. 「다시 열지 않음」= **당시 Stage 0** 의미.

- [x] 01–08 초안
- [x] 대표 5항 반영 (allocated_qty, 상태분리, 출고 TX, 선입금, 날짜)
- [x] DEC-017 / DEC-018 설계 확정 (2026-08-17)
- [x] **단계 0 설계 최종승인** (2026-08-17 대표). *(당시: 다시 열지 않음)*
- [x] DEC-019 최초 OPEN 기록 (2026-08-17 · 이후 **2026-08-21 APPROVED**)
- [x] OPEN-PROD-01~03 **CLOSED** (2026-08-19 대표 최종승인. [09 §5·§9](./09_production_inventory_flow.md))
- [x] DEC-026 harvest_year 원료 수확연도 승계 (2026-08-19)
- [x] Stage 5B 재고조회/이력 (**운영 반영됨**. 당시 기록: 로컬 · main 미머지)
- [x] ST01 운영 DB 확인 (DEC-011 **CLOSED** — 2026-08-17)
- [x] **선입금 배분 확정 (DEC-019 APPROVED — 2026-08-21).** 순차 배분, 회차 적용액 = `min(선입금 잔액, 그 판매금액)`
- [x] **주문 선입금 결제수단 (DEC-028 APPROVED — 2026-08-21).** 설계 + 코드 + **운영 ALTER/배포 완료** (`a41b40e`)
- [x] **판매상태 ≠ 수금상태 (DEC-029 APPROVED — 2026-08-21).** 수금상태는 금액 계산값
- [ ] 기존 HOLD 백필 (DEC-015 OPEN — **CLOSED 후보**. 운영 테스트데이터 초기화로 대상 없음. 운영 DB 재확인 SQL: `scripts/ops/check_order_alloc_preflight.sql`. 재확인 전 CLOSED 금지)
- [ ] 가락 확정 시 `t_sales_delivery` (DEC-016 OPEN — 단계 6 전)

## 단계 1 산출물

- [x] 하단 5번째 탭 = 주문/판매 (`nav-orders`, `mainTabNav` 5탭)
- [x] 내정보/환경설정 셸 (`/settings`, AppBar 톱니)
- [x] `/orders` 주문·판매 세그먼트 셸 (목록은 단계 2·5)
- [x] SCR-030
- [x] 대표 수동 확인 승인 (2026-08-17). private main merge.

주문/판매 하단 아이콘 교체는 **후속 UI 보완**이며 이번 승인·merge 범위가 아니다.

## 단계 2

**완료 / 대표 승인** (2026-08-19). 주문 조회/등록/수정/취소만. 판매 생성 · HOLD · 회계 · 배정 DDL 없음.  
private main merge 완료. 단계 3는 별도 브랜치.

- 공통 `core/order_service.py` (`OrderService`)
- PC `save_entire_order` → 주문 3테이블만
- GET `/api/v1/farms/{farm_cd}/orders`(조회조건·서버 페이징), GET detail, POST create, PUT, 취소
- GET/POST customers (`m_customer`)
- 모바일 목록 · 조회조건 Accordion · `/orders/new` · `/orders/:orderNo` · 수정
- 신규 `status_cd=ST010100`, `order_dt=YYYY-MM-DD` (`today_ops`)
- T-ORD-01: 재고 0 저장 성공, sales/HOLD/ledger 0
- 목록 재조회: 하단탭 캐러셀이 `OrderView`를 유지하므로 `/orders` 복귀 시 `route.path` watch로 fetch (저장 후 목록 미표시 수정)
- 주문등록 규격: 중량=`SZ01` kg 콤보, 크기=`FR020100` 과이내 콤보 (`SZ01`을 크기에 쓰지 않음)
- 주문등록 2열 grid · 신규 고객 POST (`m_customer`, PC 채번 SSOT)
- 상품 Accordion · 택배 배송지 N건 · 상태별 수정 제한
- 대표 수동 UI 승인 (2026-08-19). private main merge 완료.

## 단계 3A

**CURRENT (2026-08-28):** Core·API·테스트 **구현 완료** · git `main` **반영** (`OrderAllocationService`, allocations REST). **ops allocation DDL = 별도 게이트** · ops 적용 **미확인**.

> **HISTORICAL (2026-08-19 당시):** 「private main merge 아님 · 운영 DB migration 미실행」 — 당시 기록. git main 반영은 **이후** 완료.

목표 = **이미 있는 상품재고를 주문에 예약** (저장재고형 **선택**).  
모든 주문이 fully allocated일 필요는 없다. `allocated_qty=0`은 정상(즉시출고·생산→바로판매).  
생산→즉시판매에 alloc **강제 없음**. Stage 3A와 확정 생산모델 **충돌 없음**.

- `OrderAllocationService`: FIFO 배정, LIFO 해제, `reserved_qty` + HOLD/CANCEL_HOLD
- GET/POST allocations, POST allocations/release, GET fruit-stock (조회 전용)
- 주문 취소 시 미출고 배정이 있으면 동일 TX 해제. 없으면 상태만 변경
- 배정된 상세 규격 변경 금지, qty < allocated 금지
- T-ORD-02/03/04/05 + FIFO 분할/LIFO/동시성 + 미배정 주문 정상
- 품종 코드로 STOCK/DIRECT 분기하지 않음 (DEC-020)
- `allocated_qty` / `t_order_alloc` DDL: 로컬·테스트 + `core/order_alloc_migrate.py` · **ops = 별도 승인 게이트**

구분: **Core 구현** · **git main** · **ops DDL/배포** — 각각 별도.

### 3B UI — 후순위 (3A 직후 금지)

잘못된 표현: 「미배정 70 → 반드시 처리 필요」  
권장 표시: 주문 100 · 배정 30 · 미배정 70.  
안내: 「저장재고 출고 시 재고를 배정합니다.」  
즉시출고형 주문은 미배정 수량이 있어도 오류 상태로 표시하지 않는다.

영농일지 ST01 폴백은 **Stage 3에서 수정 금지.**

---

## 단계 H (수확기록)

**CURRENT (2026-08-28):** Core·API·PC·모바일·테스트 **구현 완료** · git `main` **반영** · **단일 HARVEST** 생산. **HARVEST N:M (DEC-035) = APPROVED NEXT.**

> **HISTORICAL (2026-08-19 당시):** 「private main merge 아님 · 운영 DB migration 미실행」 — 당시 기록.

- `WK010300` 수확작업: 품종(`FR010100` 공통코드) · 콘테이너 상자 수
- `t_work_detail.variety_cd` · `harvest_container_qty` — `core/work_harvest_schema.py` 멱등 ALTER
- 수확 저장 ≠ `t_stock_master` / `t_stock_log` 변경 (DEC-022)
- PC `work_log_page` · 모바일 `WorkLogDailyWorkForm` · API optional 필드 + Core validation SSOT
- T-HARVEST-01~08 (`server/tests/test_work_harvest.py`) + Stage 3A 회귀

---

## 판매관리 Shell (2026-08-19)

**구현 완료.** 포장/생산(Stage P)·재고(Stage 5B) 실기능. 판매 OUT 없음.

- 하단: **주문/판매** → **판매관리** (5탭 유지, `/orders`·`nav-orders` 유지)
- 상단: **[포장/생산] [재고] [주문] [판매]** — 초기 선택 **주문**
- 포장/생산: `PackProdPanel` · 재고: `StockView` (조회 전용)
- 주문·판매: Stage 2 Shell. 판매 탭은 prefill 수신만 (5C 전)
- PC 대메뉴 **미변경**

---

## 권장 후속 개발순서 (2026-08-19)

> **HISTORICAL — 2026-08-19 당시 권장순서.** `merge 대기` · `API/UI 후속` 등은 **당시 표현**. **현재 다음 개발 게이트는 [상단](#다음-개발-게이트) 참조.**

판단 기준: 기반 의존성 · PC 재사용 · DDL 최소 · 2026 수확철 실사용 · 중복입력 감소 · 독립 테스트 · Stage 3A 무충돌.

```
3A/5A  상품재고 → 주문 배정          [구현 완료 · merge 대기]
 ↓
H/3    수확기록 최소 확장            [구현 완료 · merge 대기]
 ↓
P/4    생산/변환 확장                [구현 완료 · merge 대기]
 ↓
5B     재고관리 조회·이력            [구현 완료 · merge 대기]
 ↓
5C/S   판매/출고 공통 TX             [Core 완료 · API/UI 후속]
 ↓
6      모바일 출고·배정 UX           [저장배 경로만]
 ↓
7      가락 경매확정/정산
 ↓
8      회귀·운영 migration
```

| 순서 | 내용 | 왜 지금 | DDL | 3A 충돌 |
|------|------|---------|-----|:-------:|
| **H 수확** | `variety_cd` · `harvest_container_qty`. PC/모바일 영농일지. 통계 기초 | **구현 완료** (2026-08-19). `core/work_harvest_schema.py` 멱등 ALTER. 운영 자동실행 금지 | `t_work_detail` 2컬럼 | 없음 |
| **P 생산** | 기존 `save_production_log` 유지·확장. HARVEST/RAW_STOCK. PACK/PROCESS. 배즙 **박스**. [재고저장]/[바로판매] prefill. 전량 IN. 원물 N건 투입 | **구현 완료** | 없음 | 없음 (IN≠HOLD) |
| **5B 재고** | GET fruit-stock · logs. 현재/배정/가용 Core 계산. 조회 전용 | **구현 완료** | 없음 | 없음 |
| **5C/S 판매 OUT** | `OrderShipService.confirm()` 단일 TX (로컬) | 출고 추적 | `stock_seq`/`ref_*` | STOCK consume = shipped_qty |
| **6 (구 3B)** | 모바일 출고·배정 UX | 5C 이후. 저장배 경로만 | 없음 | 5A 재사용 |
| **7** | 가락 CONFIRMED + OUT | DRAFT≠확정. 5C의 OUT 시점 규칙 필요 · **DEC-010 경로 (HISTORY)** | DEC-016 | — |
| **8** | 회귀·운영 migration | merge·배포 승인 후 | 운영 ALTER | — |

**3B를 뒤로 미루는 근거:** 배정 UI는 저장배 소매에만 필요. 수확·포장·바로판매가 2026 현장의 최소 흐름. 3B를 먼저 만들면 배정이 **필수 단계처럼 보임** (DEC-021 위반).

### 단계별 DDL · production 적용

| 단계 | 변경 | 적용 시점 |
|------|------|-----------|
| 3A | `t_order_detail.allocated_qty` · `t_order_alloc` | **로컬/테스트만.** 운영 = **main merge + 별도 승인 후** |
| H 수확 | `t_work_detail.variety_cd TEXT` · `harvest_container_qty INTEGER` | **로컬/테스트만** (`ensure_work_harvest_schema`). 운영 = main merge + 별도 승인 후 |
| P 생산 | 신규 테이블 **없음** | — |
| 5C 추적 | `t_sales_detail.stock_seq` · `t_stock_log.stock_seq/ref_type/ref_id` | **로컬/테스트** (`ensure_sales_stock_trace_schema`). **운영 자동실행 금지.** alloc migrate와 분리 |

### 배즙 단위

사용자 단위 = **박스**. PC 「포」는 **P 생산 단계**에서 UI 표기만 수정. qty 변환 migration **없음**.

---

## 업무모델 vs 단계계획

> **HISTORICAL + 일부 CURRENT 혼합.** ops/git 상태는 [상단 CURRENT](#current-implementation--stage-표) 우선.

| 항목 | 상태 |
|------|------|
| OPEN-PROD-01~03 | **CLOSED** (설계). Core·ops 반영 범위는 [상단 CURRENT](#current-implementation--stage-표) |
| Stage 3A/5A allocation | Core **구현** · git main **반영** · ops allocation DDL **별도 게이트** *(역사: 2026-08-19 당시 main 미머지 · ops `fd963e0` 계열 기록)* |
| Stage 5B 재고조회 | Core **구현** · git main **반영** · ops **미확인** |
| Stage 6 (판매/출고 UX) | Core **구현** · `/orders/ship` + Order→Ship Step1~3 · ops **`fd963e0` 계열** (과거 기록). 배정 UI(3B)는 후순위 |
| Stage 5C = S 판매/출고 OUT | Core **구현** · **경매 출하 아님** · DEC-019 선입금 배분 = Stage4 ops 반영 (과거 기록) · DEC-020 저장 필드 OPEN |
| 생산확정→바로판매 A안 | 설계 CLOSED. 코드 = P + 5C |
| **다음 구현 (당시 2026-08-21)** | [아래 2026-08-21 절](#2026-08-21--선입금수금-정책-확정) — **미래 SSOT 아님** · [상단 게이트](#다음-개발-게이트) 참조 |

## 운영 테스트데이터 초기화 (2026-08-17 대표 완료)

기존 주문/판매/재고는 테스트 데이터였음. **운영 DELETE 완료.**  
2026 실제 신규 수확부터 재고 데이터를 신규 구축한다.

| 영역 | 결과 |
|------|------|
| 주문 | `t_order_master` 0 · `t_order_detail` 0 · `t_order_delivery` 0 |
| 판매 | `t_sales_master` 0 · `t_sales_detail` 0 · `t_sales_delivery` 0 |
| 재고 OR001 | `t_stock_master` 0 · `t_stock_log` 0 |
| 회계 | 관련 `t_cash_ledger` 0 · `t_ledger` 0 |
| 백업 | `/var/www/orchard/backups/orchard_20260817.db` |

레거시 테스트 주문(`ORD20260301-*` 등, `status_cd` `'10'`/`'20'`)은 초기화로 제거됨. 신규 저장은 ST01만 사용.

## 테스트 계획 (단계별)

| ID | 시나리오 | 단계 |
|----|----------|------|
| T-NAV-01 | 하단 주문/판매 탭 진입, 세그먼트 주문↔판매 | 1 |
| T-NAV-02 | AppBar 톱니 → 환경설정에서 농장·세션 표시 | 1 |
| T-ORD-01 | 재고 0 주문 저장 성공, 판매행 없음 | 2 |
| T-ORD-02 | 저장재고형: 주문 100 / 가용 30 → 배정 30, 미배정 70 | 3 |
| T-ORD-03 | 추가 생산 후 잔여 70 배정 | 3 |
| T-ORD-04 | 동시 배정이 가용 합을 넘지 않음 | 3 |
| T-ORD-05 | allocated_qty=0 주문 등록/조회 정상. 미배정은 오류 아님 | 3 |
| T-SHP-01 | STOCK 출고 TX: reserved− out+ **새 판매 1건** | 4 |
| T-SHP-04 | 같은 주문 2회 출고 → 판매 2건. 기존 CONFIRMED 수량 불변 | 4 |
| T-SHP-02 | STOCK: 미배정분만 재고출고 요청 시 409. DIRECT는 이 테스트 비대상 | 4 |
| T-SHP-03 | 출고 중 실패 시 전체 rollback | 4 |
| T-SHP-05 | 선입금 순차 배분: 주문 30만·선입금 15만 → 판매1 10만 적용 10만 미수 0 / 판매2 20만 적용 5만 미수 15만 (DEC-019 **APPROVED**) | 4 |
| T-PAY-02 | CONFIRMED 판매 추가수금 → paid/unpaid 갱신 · `sales_status` 불변 (DEC-029) | 6 |
| T-PAY-03 | DRAFT 판매 수금 요청 409 (DEC-029) | 6 |
| T-PAY-04 | 수금액 > 미수금 거부 | 6 |
| T-ORD-06 | `pre_pay_amt=0` + 결제수단 값 전달 → 400 / `pre_pay_amt>0` + 결제수단 누락 → 400. 두 경우 모두 `t_cash_ledger`·`t_ledger` 0 (DEC-028) | 2 |
| T-SHP-06 | DIRECT 즉시출고 (수량추적 OPEN 해소 후) | 4 |
| T-SAL-01 | 판매 PUT 후 order_no 유지 | 5 |
| T-AUC-01 | DRAFT 확정 시 출고+CONFIRMED, 실패 시 DRAFT 유지 (**DEC-010 HISTORY 시나리오**) | 6 |
| T-PAY-01 | CONFIRMED 수금 → cash+ledger. 주문 API는 전표 없음 | 6 |
| T-CAN-01 | 출고 전 취소 Hold 0 | 2–4 |
| T-REG-01 | 관찰·영농일지·농약 회귀 | 7 |
| T-PROD-01~11 | 생산확정 PACK/PROCESS · HARVEST/RAW_STOCK · rollback · prefill | P |
| T-HARVEST-01~08 | 수확기록 (Stage H) | H |

## Stage P — 포장/생산 (2026-08-19 구현 완료 · HISTORICAL 로컬 기록)

> **CURRENT:** Core·API·Mobile **구현** · git main **반영** · **단일 HARVEST**. N:M = APPROVED NEXT.

- Core: `core/production_service.py`, `core/stock_constants.py` (StockPage TX SSOT)
- API: `/production/harvest-records`, `/raw-stock`, `/confirm`
- Mobile: `PackProdPanel.vue` · 판매관리 포장/생산 탭 · `salesPrefill` store
- PC: `stock_page.save_production_log` → Core 위임 · 생산 후 [재고로 저장]=UI reset / [바로 판매]=prefill (판매 OUT은 Stage 5C)
- **금지 준수:** `t_production_*` 없음 · HARVEST kg 환산 없음 · 판매 OUT/allocation consume 없음
- **배즙 2종 (Stage 6 보완):** PROCESS는 그대로 1유형. 완제품 `juice_item_cd` = 일반배즙 `FR010202`(기본) / 도라지배즙 `FR010201`. `item_cd`가 natural key. 중분류 `FR010200`은 레거시 재고만. 도라지 원료·BOM 없음. 기존 판매 row 재분류 없음.

## Stage 5B — 재고관리 (2026-08-19 구현 완료 · HISTORICAL 로컬 기록)

> **CURRENT:** Core·API·Mobile **구현** · git main **반영** · ops **미확인**.

- API: `GET /farms/{farm}/fruit-stock` (`include_zero`) · `GET .../fruit-stock/logs`
- Mobile: `StockView.vue` · 원물/상품/배즙 · 현재/배정/가용 · 이력
- 계산 SSOT: [09 §14](./09_production_inventory_flow.md). DEC-026 harvest_year
- 수기 재고 수정 **없음**

## Stage 5C 1차 — 설계 SSOT + 멱등 DDL (2026-08-19)

- DEC-027 APPROVED. 문서: [03](./03_data_contract.md) · [05](./05_api_contract.md) · [09 §21](./09_production_inventory_flow.md)
- Helper: `core/sales_stock_trace_schema.ensure_sales_stock_trace_schema` — `db_manager.connect()` **미호출**
- alloc preflight/HOLD 정리 **없음**

## Stage 5C 2차 — OrderShipService.confirm() (2026-08-19)

- Core: `core/order_ship_service.py` `confirm()` — `BEGIN IMMEDIATE` 1회. public `allocate()`/`release()` 미호출
- STOCK: alloc `shipped_qty +=` · reserved− · out+ · `allocated_qty` 유지
- DIRECT: available FIFO OUT. alloc 미변경. 무주문+DIRECT 허용. 무주문+STOCK 거부
- 판매: `sales_status=CONFIRMED` · 1 sales_detail = 1 stock_seq · `t_stock_log` SALE
- 주문 SSOT: CONFIRMED sales_detail SUM. `t_order_detail.out_qty` 미사용
- ST01: 부분 `ST010300` · 전량 `ST010400`+`stock_status=Y` · ST010200 강제 없음
- Schema: 실행 중 ALTER 없음. 부족 시 `SCHEMA_PRECONDITION`. STOCK만 alloc 스키마 필수, DIRECT는 alloc 테이블 없이 가능
- FastAPI: `POST /api/v1/farms/{farm_cd}/shipments/confirm` — wrapper만. FIFO/재고 SQL 없음
- PC `sales_page.py` **미위임**. Mobile 판매 UI: Stage 6 `/orders/ship`
- 로컬 개발 DB: **trace DDL 적용 가능**(기존 row NULL 유지). allocation schema는 Stage 6-2 로컬 적용. 운영 DB 미변경
- 테스트: `server/tests/test_order_ship_service.py` · `server/tests/test_order_ship_api.py`

## Stage 5C 3차 — HTTP API (2026-08-19)

- Endpoint: `POST /api/v1/farms/{farm_cd}/shipments/confirm`
- Adapter: `app/services/order_ship_api_service.py` → `OrderShipService.confirm()`
- TX: Core 단독. API는 connection 전달만
- HTTP: 400 검증 · 409 충돌/SCHEMA_PRECONDITION · 404 주문없음
- 주문 전용 `/orders/{order_no}/ship` 미생성

## Stage 6 — 판매/출고 UX (역사적 기록 · 2026-08-19 로컬)

> **현재:** Stage 6 및 Order→Ship Step1~3는 **운영 반영 완료** (`fd963e0`). 아래는 당시 로컬 구현 기록.

- 문서: [04 §9](./04_mobile_screen.md). Vue **1차 구현** `ShipConfirmView` `/orders/ship`
- 한 화면 · 세 진입(생산 바로판매 / 주문출고 / 재고직접판매)
- 잔여 화면 SSOT = `remaining_order[]`
- 연속출고 UI · 로트 수동선택 · STOCK/DIRECT 용어 노출 **1차 제외**
- 생산 1차: 주문검색 없음(무주문 DIRECT)

## Stage 6-1 DIRECT E2E (역사적 기록 · 2026-08-19 로컬)

- **상태:** DIRECT E2E ✅ (로컬 개발 API + 로컬 개발 SQLite DB)
- 판매: `20260819-01` 무주문 DIRECT · `20260819-02` 무주문 DIRECT · `20260819-03` 주문 DIRECT `ORD20260819-001` → `ST010300`
- **Stage 6-2 STOCK/Allocation 전환:** 로컬 A안 적용 (reserved 103 해제 + AUDIT, HOLD 보존, 백필 없음, active reserved-only preflight)

## Stage 6-2 로컬 Allocation + STOCK E2E (역사적 기록 · 2026-08-19)

- 대상 DB: 로컬 개발 `orchard_platform.db` only. 운영/Lightsail 미변경
- A안: stock_seq=156 reserved 103→0 + `t_stock_log` AUDIT 1건. HOLD 9 / CANCEL_HOLD 3 원문 보존. `t_order_alloc` 백필 없음
- DEC-015 preflight: active reserved만 차단. historical HOLD는 보고만
- 로컬 schema: `allocated_qty` + `t_order_alloc`. 기존 주문 allocated=0
- STOCK E2E: `ORD20260819-002` stock_seq=197 신고 15kg 특(GR010200) 1다이 harvest 2026. allocate 5 → ship 3 (`20260819-04` ST010300) → ship 2 (`20260819-05` ST010400+Y). DIRECT 회귀 `20260819-06` seq200. DEC-027 규칙 변경 없음
- **과출고 invariant (로컬 확인):** `real_qty<0` 이고 `reserved=0`이면 다른 로트 배정을 막지 않는다. 음수 로트는 alloc/DIRECT FIFO 후보에서 제외. `reserved > real` 또는 음수+`reserved>0`은 계속 차단
- **OPEN-DATA-NEG-STOCK:** 로컬 2025 음수 3로트(seq 151/169/170, real 합 -273)는 Stage 6과 분리. 운영 이관 전 원인 분석. 아래 절
- 참고: 기존 `ORD20260817-002` 줄 harvest_year=2026 vs 해당 규격 재고 2025 → DIRECT 시 STOCK_UNAVAILABLE 가능. 이번 C는 2026 재고와 맞는 신규 주문으로 검증

## Stage 6 로컬 마감 (역사적 기록 · 2026-08-19)

- **상태 (당시):** 로컬 완료. push는 feature branch만. **당시** main merge / mirror / production 금지  
  → **이후** Stage 6·Step1~3·compact 목록은 운영 반영됨 (`fd963e0`). 당시 금지 문구를 현재로 읽지 말 것.
- DIRECT E2E + STOCK E2E + allocation schema(로컬) + 레거시 reserved 103 정리
- 경계 테스트: `test_stock_ship_e2e.py` (음수 로트 비후보 · 정상 로트 계속 · reserved>real 차단 · 음수+reserved 차단)

## 2026-08-21 — 선입금·수금 정책 확정

> **HISTORICAL — 2026-08-21 당시 문서·정책 확정 기록.** 아래 「다음 개발 순서」의 `8 가락 DRAFT→CONFIRMED`는 **HISTORY** — **미래 TARGET 아님**. [상단 게이트](#다음-개발-게이트)가 현재 기준.

**문서 정합성 작업만 (당시).** 코드·DB·테스트 변경 없음.

확정된 결정:

| DEC | 내용 | 상태 |
|-----|------|------|
| DEC-019 | 부분출고 선입금 **순차 배분**. 회차 적용액 = `min(선입금 잔액, 그 판매금액)`. 초과 적용·기존 CONFIRMED 판매 재작성 금지 | **APPROVED** |
| DEC-028 | 주문 **선입금 결제수단**. `pre_pay_amt=0` → NULL, `>0` → 필수. 컬럼 `t_order_master.pre_pay_method_cd TEXT NULL`. 결제수단 = **현금성 자산 계정**(`AS0101` level4). 채권(`AS02…`) 제외. **운영 ALTER·배포 완료** | **APPROVED** · **완료 · 운영** |
| DEC-029 | **판매상태 ≠ 수금상태.** `sales_status`는 DRAFT/CONFIRMED만. 수금상태는 금액 계산값 | **APPROVED** |

정리된 개념:

- **주문 생성/확정 ≠ 판매.** 판매는 출고확정 시점에 생성 (새 `sales_no`, CONFIRMED, `sales_dt`=그 출고 업무일, 재고 OUT)
- **판매확정** = 그 판매 CONFIRMED · **주문완료** = `ST010400` + `stock_status='Y'` · **수금완료** = 그 판매 미수 0. 세 개념을 섞지 않음
- 수금상태: `tot_paid_amt==0` 미수 · `0 < tot_paid_amt < tot_sales_amt` 부분수금 · `tot_unpaid_amt==0` 수금완료
- 회계는 기존 `t_cash_ledger` · `t_ledger` · `AccountManager.sync_ledger_by_basket('SALE',…)` 재사용. **모바일 전용 회계 엔진 금지**
- UI 용어: **결제수단 · 수금액 · 미수금 · 수금상태** (「수금방법」 금지)

반영 문서: [01](./01_overview.md) · [02 §8·§12](./02_domain_flow.md) · [03 §1.1·§4.1·§9](./03_data_contract.md) · [04 §4.1·§6.1·§6.2](./04_mobile_screen.md) · [05 §3.1·§6.C·§8](./05_api_contract.md) · [07](./07_decisions.md) · [08 A13](./08_pc_change_scope.md)

### 다음 개발 순서 (2026-08-21 당시 · HISTORICAL)

> **현재 SSOT 아님.** `8 가락 DRAFT→CONFIRMED` = **DEC-010 HISTORY**. 미래 경매 TARGET = [상단 APPROVED NEXT](#approved-next-design).

```
1  설계서 정합성 완료
2  선입금 결제수단 기반  ← 완료 · ops (과거 기록)
3  판매 수금 Core        ← 완료 · ops (과거 기록)
4  출고 시 선입금 자동배분  ← 완료 · ops (과거 기록)
5  판매목록  ← 완료 · ops (과거 기록 · b48ca8b)
6-0 수금상태 계약  ← git main 반영 · ops 미배포
6A 판매상세 read-only  ← git main 반영 · ops 미배포
6B 수금내역 read-only  ← git main 반영 · ops 미배포
6C 수금등록 POST  ← git main 반영 · ops 미배포
7A PC 출고확정 판매 보호  ← git main 반영 · ops 미배포
7B-1 PC 수금 immutable  ← git main 반영 · ops 미배포
7B-2 PC 신규수금 append  ← git main 반영 · ops 미배포
7B PC 수금 공용화  ← git main 반영 · ops 미배포
8  가락 DRAFT→CONFIRMED  ← HISTORY (DEC-010 SUPERSEDED)
```

| # | 항목 | 상태 | 내용 | 선행 확인 |
|---|------|------|------|-----------|
| 1 | **설계서 정합성 완료** | **완료** | 본 문서 세트에 DEC-019/028/029 반영 | — |
| 2 | **선입금 결제수단 기반** | **완료 · 운영** | `pre_pay_method_cd` 저장·조회. `0`→NULL, `>0`→현금성 필수. parent `AS0101` / level4 / `use_yn=Y` 검증. legacy prepay>0·method NULL 조회 허용. ST010200/300 NULL→유효 method 최초 1회 보완 · 기존 method 변경 금지. 주문 단계 cash/ledger/sales **변화 없음**. 운영 ALTER `ADD COLUMN pre_pay_method_cd TEXT` + backend/frontend `a41b40e` | — |
| 3 | **판매 수금 Core** | **완료 · 운영** | `SalesPaymentService` append 추가수금. cash SSOT · AccountManager SALE farm scope · DRAFT 금지 · `AS0101` 검증 · `add_payment_in_tx` caller-owned TX. HTTP/UI 없음. 운영 backend `f7d3187` 계열 → Stage4와 함께 `fb413a3` | — |
| 4 | **출고 시 선입금 자동배분** | **완료 · 운영** | Core(DEC-019) + P1 PC `order_no` 보존 + P2 자동 선입금 cash 수정·삭제 가드 + P2b 판매일 우회변경 차단·행별 `pay_dt` INSERT. DDL 0. 운영 backend/PC `fb413a3` | — |
| 5 | **판매목록** | **완료 · 운영** | `SalesQueryService` + `GET /sales` + Mobile 판매탭. P1: 수금 filter 상호배타·malformed date 400. P2: `weight`/`crop_nm` optional schema · `rep_crop_nm`. cash SUM SSOT · DDL 0. 운영 backend `b48ca8b` | Stage4 운영 완료 |
| 6-0 | **수금상태 조회 계약** | **git main · ops 미배포** | `compute_payment_status` 공통화. API `UNPAID/PARTIAL/PAID/null` · UI label 분리. DRAFT=null · 0/0=UNPAID · overpay clamp PAID. AccountManager/ledger/pay_dt **불변** | 5 |
| 6A | **판매상세 read-only** | **git main · ops 미배포** | `GET /sales/{sales_no}` · `SalesDetailView` · cash SUM SSOT · FIFO UI grouping · 배송 제외 · SELECT only | 6-0 |
| 6B | **수금내역 read-only** | **git main · ops 미배포** | `GET /sales/{sales_no}/payments` · cash 행 SSOT · GENERAL/ORDER_PREPAY · method명 · SELECT only | 6A |
| 6C | **수금등록** | **git main · ops 미배포** | `POST /sales/{sales_no}/payments` · `SalesPaymentService.add_payment` · Mobile inline form · DEC-030 Core validation · PUT/수정/삭제 없음 | 6B |
| 7A | **PC 출고확정 판매 보호** | **git main · ops 미배포** | DEC-031: CONFIRMED + (`order_no` \| `order_detail_id` \| `stock_seq`) → PC read-only · UI disable + save/delete backstop + 배송 edit 차단 | 6C |
| 7B-1 | **PC 수금 immutable** | **git main · ops 미배포** | DEC-032/033/034: full-save cash/ledger mutation 제거 · 기존 수금 read-only · DEC-034 감액 backstop · cash 있는 판매 delete 차단 | 7A |
| 7B-2 | **PC 신규수금 append** | **git main · ops 미배포** | `SalesPaymentService.add_payment` · DEC-030 · `list_payment_methods` SSOT · protected CONFIRMED도 unpaid>0 이면 add 허용 · P1 COMMIT/UI 경계 | 7B-1 |
| 7 | **PC 정합성 잔여** | **별도 범위 확정 예정** | `order_detail_id` 재저장 보존 등 — Stage7B-1/7B-2(수금 공용화)와 **별도** | 7B-2 |
| 8 | **가락 DRAFT→CONFIRMED** | **HISTORY (DEC-010 SUPERSEDED)** | 당시: confirm TX + 선택 수금 (DEC-010). **미래 TARGET 아님** — [DEC-036/037](#approved-next-design) | — |

**스키마 확인 결과 (2026-08-21 조사 · Stage4 DDL 0):**

| 항목 | 확인 내용 | 상태 |
|------|-----------|------|
| `t_order_master.pre_pay_method_cd` | 운영 **TEXT NULL 추가 완료** (2026-08-21). 기존 row NULL 유지(backfill 0). helper는 로컬/테스트용 | **완료 · 운영** |
| 현금성 결제수단 범위 | `parent_cd='AS0101'` · level4 · `use_yn=Y` → AS010101/102/103. 채권 AS02 제외. 카드 계정 없음 | **확정** |
| `t_cash_ledger.order_no` | NULL=일반수금 · 주문번호=선입금 자동적용 (DEC-019 provenance CLOSED). 신규 컬럼 없음 | **CLOSED** |
| DEC-016 가락 배송 | 가락 확정 시 `t_sales_delivery` | **OPEN** |

DEC-016(가락 배송행)은 계속 **OPEN**이며 2026-08-21에 승인하지 않았다.

---

## OPEN-DATA-NEG-STOCK (Stage 6 밖 · 운영 이관 전 메모)

**Core 로직 blocker 아님.** **DEC-035/036/037 경매 redesign blocker 아님.** 로컬 PC 테스트 과정에서 생긴 데이터 정합 이슈. **운영 migration 전 별도 확인.**

로컬 `orchard_platform.db` 전용. 운영 미적용. Stage 6 로직 검증과 분리.

| stock_seq | harvest | 규격 | in | out | real | reserved |
|-----------|---------|------|----|-----|------|----------|
| 151 | 2025 | 신고 7.5kg 특 1다이 2025-10-01 | 181 | 226 | -45 | 0 |
| 169 | 2025 | 신고 15kg 등외 1다이 2025-10-01 | 10 | 226 | -216 | 0 |
| 170 | 2025 | 신고 15kg 등외 2다이 2025-10-01 | 8 | 20 | -12 | 0 |

합 real **-273**. sibling 양수 로트 없음. 원인 분석은 운영 이관 전 별도 이슈.

주문 날짜는 `today_ops`. 과거 날짜 일괄변환 테스트 없음.
