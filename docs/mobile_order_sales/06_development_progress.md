# 06. Development progress

> **현재 기준 (2026-08-22):** private main **`6bc7b4f`**. 운영 backend **`f7d3187`**.  
> **Stage4 (출고 선입금 자동배분):** Core + PC provenance safety patch · feature 완료 · **main/운영 미반영**.  
> **다음 개발 순서 SSOT:** [2026-08-21 절](#2026-08-21--선입금수금-정책-확정) 5~8.  
> OPEN-PROD-01~03 **CLOSED**. DEC-019 provenance **CLOSED** (`t_cash_ledger.order_no`). DEC-028/029 **APPROVED**.  
> 생산/재고 SSOT: [09](./09_production_inventory_flow.md).

범례: `—` · `예정` · `진행` · `완료` · `차단` · `대기`

## 현재 운영 기준 — Stage 표 (2026-08-21)

| 단계 | 목표 | 상태 |
|------|------|------|
| 0 | 주문·판매·재고 전체 설계 / PC 기준 분석 / 업무규칙 확정 | **완료** |
| 1 | 모바일 주문/판매 진입구조·메뉴·라우팅 | **완료 · 운영** |
| 2 | 주문관리 — 조회·등록·수정·취소·고객·배송지 | **완료 · 운영** (compact 2줄 목록 포함) |
| 3 (=H) | 수확기록 확장 — 영농일지 품종·콘테이너 수량 | **완료 · 운영** |
| 4 (=P) | 생산/변환 — PACK·PROCESS·원물 OUT·생산품 IN | **완료 · 운영** |
| 5A (=3A) | 재고배정 Core — HOLD / RELEASE / allocation | **완료 · 운영** |
| 5B | 재고관리 — 조회·상태·이력·생산/배정 정합성 | **완료 · 운영** |
| 5C (=S) | 공통 출고·판매 Core — 실제 판매확정·상품 OUT | **완료 · 운영** |
| 6 | 모바일 출고·배정·판매 UX + Order→Ship Step1~3 | **완료 · 운영** |
| — | **다음:** 5 판매목록 → 판매상세/수금 → PC 정합 → 가락 | [§ 2026-08-21](#2026-08-21--선입금수금-정책-확정) |
| 7* | 가락시장 경매→판매확정·정산 | **예정** (DEC-016 OPEN · 개발순서 8) |
| 8* | 통합 회귀·PC/PWA 정합 | **예정** (개발순서 7과 연계) |

\*표의 7·8은 과거 게이트 번호. **앞으로의 구현 순서는 아래 1~8이 SSOT**이며, 이미 끝난 Stage 6을 그 안에 다시 넣지 않는다.

```
1 설계서 정합성 완료
2 선입금 결제수단 기반  ← 완료 · 운영
3 판매 수금 Core        ← 완료 · 운영
4 출고 시 선입금 자동배분  ← Core + PC provenance patch · feature 완료 · main/운영 미반영
→ 5 판매목록  →  6 판매상세/수금등록
→ 7 PC 정합성  →  8 가락 DRAFT→CONFIRMED
```

SHA 스냅샷: private main = `6bc7b4f` · 운영 backend = `f7d3187` · Stage4 feature = `cursor/order-ship-prepay-stage4`.

---

## 역사적 개발 기록 (2026-08-19 이전 게이트 표)

아래는 **당시 로컬 진행 스냅샷**이다. **현재 운영 상태로 읽지 말 것.**  
「main 미머지」「운영 미적용」「Mobile UI 후속」은 **당시 표현**이며, Stage 6·출고 Core는 이후 운영 반영됨 ([위 현재 운영 기준](#현재-운영-기준--stage-표-2026-08-21)).

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
| 7 | 가락시장 경매→판매확정·정산 | **예정** |
| 8 | 통합 회귀·PC/PWA 정합·운영 Migration·배포 | **예정** |

역사적 게이트 번호(3A/H/P/S)는 코드·커밋 메시지에 남아 있다.

## 게이트 (기존 번호 유지 · 역사+현황 혼용 주의)

```
0 설계 최종승인 (완료)
 → 1 메뉴/라우트
 → 2 주문 조회/등록
 → 3A 저장재고형 선택적 재고배정  (이후 운영 반영)
 → [권장] 수확기록 → 생산확장 → 판매/출고 OUT TX
 → 3B 모바일 배정 UI  (3A 직후 아님 · 후순위)
 → 5 판매관리 (목록·상세·수금 — 다음 개발순서 5·6)
 → 6 경매/수금/회계 (수금 Core·선입금 배분 — 다음 개발순서 2~4 · 가락은 8)
 → 7 회귀/운영검증
```

기존 단계 4(출고→판매)는 **권장 후속의 판매/출고 공통 TX**와 같음. 번호만 유지. **이미 운영 반영된 Stage 6 출고 UX를 이 순서에 다시 끼워 넣지 않는다.**

| 단계 | 목표 | 상태 | PC | Core | API | Mobile | Test | 대표 승인 |
|------|------|------|----|------|-----|--------|------|-----------|
| 0. 설계 | 본 폴더 문서 · 규칙 합의 | **완료** | — | — | — | — | 문서 리뷰 | **최종승인 완료** (2026-08-17) |
| 1. 메뉴/라우트 | 하단 주문/판매 · 내정보 이동 | **완료 / 운영** | 없음 | 없음 | 없음 | 셸 | T-NAV-* | **승인** (2026-08-17) |
| 2. 주문 조회/등록 | 선주문 저장 (판매·전표 없음) | **완료 / 운영** | 주문만 저장 | OrderService | GET/POST orders | 목록·등록·수정 | T-ORD-01 | **승인** (2026-08-19) |
| 3A. 재고배정 | 저장재고형 **선택** 배정 · Hold · `t_order_alloc` | **완료 / 운영** | Hold 키 | Allocation | allocations | 조회만 | 42 passed | 운영 반영 (`fd963e0` 계열) |
| 3B. 배정 UI | 모바일 배정 UX (필수단계처럼 보이지 않게) | **후순위** | — | 3A 재사용 | 3A 재사용 | 미착수 | — | 수확·생산·OUT TX 이후 |
| 4. 출고→판매 | 상품 OUT + 판매 · STOCK/DIRECT | **완료 / 운영** | 미위임(PC) | OrderShip | POST shipments/confirm | `/orders/ship` + Step1~3 | T-SHIP-* | Stage 6 운영 |
| 5. 판매관리 | 목록·상세·수금 표시 | **예정** (개발순서 5·6) | 재저장 보존 | SalesService | GET/PUT sales | 판매 탭 | T-SAL-01 | 수금 Core 후 |
| 6. 경매/수금/회계 | 선입금·수금 Core · payments · 가락 | **예정** (개발순서 2~4·8) | 확정 버튼 | Confirm+Account | confirm/payments | 수금 UI | T-AUC/PAY | DEC-016 등 |
| 7. 회귀/운영 | PC+모바일+관찰/일지/농약 | 예정 | 회귀 | — | health | 스모크 | T-REG-01 | 배포 승인 |

## 단계 0 산출물

- [x] 01–08 초안
- [x] 대표 5항 반영 (allocated_qty, 상태분리, 출고 TX, 선입금, 날짜)
- [x] DEC-017 / DEC-018 설계 확정 (2026-08-17)
- [x] **단계 0 설계 최종승인** (2026-08-17 대표). 다시 열지 않음
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

**구현 완료** (Core·API·테스트). **private main merge 아님.** 운영 DB migration **미실행.**

목표 = **이미 있는 상품재고를 주문에 예약** (저장재고형 **선택**).  
모든 주문이 fully allocated일 필요는 없다. `allocated_qty=0`은 정상(즉시출고·생산→바로판매).  
생산→즉시판매에 alloc **강제 없음**. Stage 3A와 확정 생산모델 **충돌 없음**.

- `OrderAllocationService`: FIFO 배정, LIFO 해제, `reserved_qty` + HOLD/CANCEL_HOLD
- GET/POST allocations, POST allocations/release, GET fruit-stock (조회 전용)
- 주문 취소 시 미출고 배정이 있으면 동일 TX 해제. 없으면 상태만 변경
- 배정된 상세 규격 변경 금지, qty < allocated 금지
- T-ORD-02/03/04/05 + FIFO 분할/LIFO/동시성 + 미배정 주문 정상
- 품종 코드로 STOCK/DIRECT 분기하지 않음 (DEC-020)
- `allocated_qty` / `t_order_alloc` DDL은 로컬·테스트만 (`core/order_alloc_migrate.py`)

구분: **구현 완료** ≠ **main merge 승인**.

### 3B UI — 후순위 (3A 직후 금지)

잘못된 표현: 「미배정 70 → 반드시 처리 필요」  
권장 표시: 주문 100 · 배정 30 · 미배정 70.  
안내: 「저장재고 출고 시 재고를 배정합니다.」  
즉시출고형 주문은 미배정 수량이 있어도 오류 상태로 표시하지 않는다.

영농일지 ST01 폴백은 **Stage 3에서 수정 금지.**

---

## 단계 H (수확기록)

**구현 완료** (Core·API·PC·모바일·테스트). **private main merge 아님.** 운영 DB migration **미실행.**

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
| **7** | 가락 CONFIRMED + OUT | DRAFT≠확정. 5C의 OUT 시점 규칙 필요 | DEC-016 | — |
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

| 항목 | 상태 |
|------|------|
| OPEN-PROD-01~03 | **CLOSED** (설계). Core·운영 반영 범위는 [현재 운영 기준](#현재-운영-기준--stage-표-2026-08-21) |
| Stage 3A/5A allocation | **운영 반영 완료** (`fd963e0` 계열). *(역사: 2026-08-19 당시 main 미머지)* |
| Stage 5B 재고조회 | **운영 반영 완료** |
| Stage 6 (판매/출고 UX) | **운영 반영 완료** (`/orders/ship` + Order→Ship Step1~3 · `fd963e0`). 배정 UI(3B)는 후순위 |
| Stage 5C = S 판매/출고 OUT | **운영 반영 완료**. **DEC-019** 선입금 배분 = Stage4 feature 완료 · main 미반영 · DEC-020 저장 필드 OPEN |
| 생산확정→바로판매 A안 | 설계 CLOSED. 코드 = P + 5C |
| **다음 구현** | [2026-08-21 절](#2026-08-21--선입금수금-정책-확정) 1~8 (Stage 6 재포함 금지) |

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
| T-AUC-01 | DRAFT 확정 시 출고+CONFIRMED, 실패 시 DRAFT 유지 | 6 |
| T-PAY-01 | CONFIRMED 수금 → cash+ledger. 주문 API는 전표 없음 | 6 |
| T-CAN-01 | 출고 전 취소 Hold 0 | 2–4 |
| T-REG-01 | 관찰·영농일지·농약 회귀 | 7 |
| T-PROD-01~11 | 생산확정 PACK/PROCESS · HARVEST/RAW_STOCK · rollback · prefill | P |
| T-HARVEST-01~08 | 수확기록 (Stage H) | H |

## Stage P — 포장/생산 (2026-08-19 구현 완료 · 로컬)

- Core: `core/production_service.py`, `core/stock_constants.py` (StockPage TX SSOT)
- API: `/production/harvest-records`, `/raw-stock`, `/confirm`
- Mobile: `PackProdPanel.vue` · 판매관리 포장/생산 탭 · `salesPrefill` store
- PC: `stock_page.save_production_log` → Core 위임 · 생산 후 [재고로 저장]=UI reset / [바로 판매]=prefill (판매 OUT은 Stage 5C)
- **금지 준수:** `t_production_*` 없음 · HARVEST kg 환산 없음 · 판매 OUT/allocation consume 없음
- **배즙 2종 (Stage 6 보완):** PROCESS는 그대로 1유형. 완제품 `juice_item_cd` = 일반배즙 `FR010202`(기본) / 도라지배즙 `FR010201`. `item_cd`가 natural key. 중분류 `FR010200`은 레거시 재고만. 도라지 원료·BOM 없음. 기존 판매 row 재분류 없음.

## Stage 5B — 재고관리 (2026-08-19 구현 완료 · 로컬)

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

**문서 정합성 작업만.** 코드·DB·테스트 변경 없음.

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

### 다음 개발 순서 (2026-08-21 확정 · 순서 자체 변경 없음)

```
1  설계서 정합성 완료
2  선입금 결제수단 기반  ← 완료 · 운영
3  판매 수금 Core        ← 완료 · 운영
4  출고 시 선입금 자동배분  ← Core + PC provenance patch · feature 완료 · main/운영 미반영
5  판매목록
6  판매상세/수금등록
7  PC 정합성
8  가락 DRAFT→CONFIRMED
```

| # | 항목 | 상태 | 내용 | 선행 확인 |
|---|------|------|------|-----------|
| 1 | **설계서 정합성 완료** | **완료** | 본 문서 세트에 DEC-019/028/029 반영 | — |
| 2 | **선입금 결제수단 기반** | **완료 · 운영** | `pre_pay_method_cd` 저장·조회. `0`→NULL, `>0`→현금성 필수. parent `AS0101` / level4 / `use_yn=Y` 검증. legacy prepay>0·method NULL 조회 허용. ST010200/300 NULL→유효 method 최초 1회 보완 · 기존 method 변경 금지. 주문 단계 cash/ledger/sales **변화 없음**. 운영 ALTER `ADD COLUMN pre_pay_method_cd TEXT` + backend/frontend `a41b40e` | — |
| 3 | **판매 수금 Core** | **완료 · 운영** | `SalesPaymentService` append 추가수금. cash SSOT · AccountManager SALE farm scope · DRAFT 금지 · `AS0101` 검증 · `add_payment_in_tx` caller-owned TX. HTTP/UI 없음. 운영 backend `f7d3187` (DDL 없음) | — |
| 4 | **출고 시 선입금 자동배분** | **feature 구현 완료 · main/운영 미반영** | Core(DEC-019) + **PC `execute_full_save` order_no 보존 패치**(master·cash 행별). DDL/HTTP/Mobile 0. Stage7 전체 PC 정합 아님 | — |
| 5 | **판매목록** | **예정** | 판매금액·수금액·미수금·수금상태 배지. 판매상태 배지와 분리 | 3·4 |
| 6 | **판매상세/수금등록** | **예정** | 수금 내역 + 수금등록(수금액 ≤ 미수금, 결제수단 필수) | 3 |
| 7 | **PC 정합성** | **예정** | PC `SalesPage` 회계 호출부를 공용 Core로 위임 ([08 A13](./08_pc_change_scope.md)). 전면 재작성 아님. **OPEN P1:** `t_sales_detail.order_detail_id` 재저장 유실 | 3·4 |
| 8 | **가락 DRAFT→CONFIRMED** | **예정** | confirm TX + 선택 수금 (DEC-010). DEC-016 OPEN 선결 | 3·7 |

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

**Core 로직 blocker 아님.** 로컬 PC 테스트 과정에서 생긴 데이터 정합 이슈. 운영 적용 전 정리 대상.

로컬 `orchard_platform.db` 전용. 운영 미적용. Stage 6 로직 검증과 분리.

| stock_seq | harvest | 규격 | in | out | real | reserved |
|-----------|---------|------|----|-----|------|----------|
| 151 | 2025 | 신고 7.5kg 특 1다이 2025-10-01 | 181 | 226 | -45 | 0 |
| 169 | 2025 | 신고 15kg 등외 1다이 2025-10-01 | 10 | 226 | -216 | 0 |
| 170 | 2025 | 신고 15kg 등외 2다이 2025-10-01 | 8 | 20 | -12 | 0 |

합 real **-273**. sibling 양수 로트 없음. 원인 분석은 운영 이관 전 별도 이슈.

주문 날짜는 `today_ops`. 과거 날짜 일괄변환 테스트 없음.
