# 09. Production & inventory flow — 생산/재고 (PC 기준)

> **역할:** 실제 농장 업무·기존 PC `StockPage`를 기준으로 한 **생산/재고** SSOT.  
> 주문/판매 상세는 [02_domain_flow.md](./02_domain_flow.md). 데이터 계약은 [03_data_contract.md](./03_data_contract.md).  
> OPEN-PROD-01~03 **CLOSED**. Stage P/5B **구현 완료** (main 미머지). Stage 5C·DDL 운영 적용 **미실행**.

---

## 0. UX 최우선 원칙 (DEC-021)

**농부에게 일을 더 만들지 않는다.**

| 원칙 | 적용 |
|------|------|
| 중복입력 금지 | 생산수량을 판매 화면에서 다시 입력하지 않음 |
| 자동 | 날짜·사용자·채번·시스템이 아는 값 |
| 내부 기록 | Batch·lot·연결키는 사용자가 관리하지 않음 |
| 입력 최소 | 화면 필드는 업무에 꼭 필요한 것만 |
| 선택 단계 강제 금지 | 배정·저장·생산이 선택인데 필수 화면으로 만들지 않음 |

실사용: 농업 현장 · 1인 운영 비중 높음 · 작업 중 짧은 모바일 사용.

---

## 0.1 수확기록 (DEC-022 APPROVED)

**영농일지**의 수확작업으로 관리. 재고관리에서 **조회** 가능(UI 연동은 후속).

| 항목 | 정책 |
|------|------|
| 사용자 입력 | 수확일자 · 품종 · **콘테이너 상자 수** |
| 자동 | 수확년도(일자 기준) · 작업자 · reg_dt |
| 단위 | **콘테이너 상자** — kg 입력 **금지** |
| 금지 | 수확 저장 = `t_stock_master` 자동 입고 |

수확기록 = 통계/생산 **출발점**, 재고 자체 아님.

**통계 목표(추가 입력 없음):** 연도별·품종별·일자별 총수확량, 전년 대비.

**PC 현재와 차이 (`stock_page.register_raw_material`):**

- 별도 “원물 등록” — `CT01` 규격 카드 + **20.0kg 고정** + `t_stock_master` IN
- 영농일지 `t_work_detail`과 **미연동**
- 콘테이너 상자 수·수확 통계 **미지원**

**실제 DB 스키마 (`orchard_platform.db` PRAGMA, 2026-08-19):**

| 컬럼 | 수확기록 용도 |
|------|---------------|
| `work_dt` | 수확일자 ✓ |
| `work_mid_cd` | `WK010300`(수확작업) ✓ |
| `work_loc_id` | **필지** — 품종 **아님** |
| `rmk` | 비고 텍스트 — **상자 수 저장 금지** |
| (없음) | 품종·상자 수 **전용 숫자 필드 없음** |

**저장 코드 (Stage H 구현 완료, 2026-08-19):**

- `core/work_harvest_schema.ensure_work_harvest_schema` — 멱등 ALTER (로컬/테스트)
- Core `normalize_harvest_fields` — 수확 validation SSOT · 비수확 NULL
- 서버 `work_log_service.get_daily` — `variety_nm` JOIN
- PC `work_log_page` · `db_manager.save_work_details` — 수확 컬럼 저장
- 모바일 `WorkLogDailyWorkForm` / `WorkLogDailyView` — 품종·상자 입력

**OPEN-PROD-02 CLOSED — DDL 적용 (로컬/테스트):**

| 컬럼 | 용도 | 필수 |
|------|------|:----:|
| `harvest_container_qty INTEGER` | 콘테이너 상자 수 | ✓ |
| `variety_cd TEXT` | 품종(통계) — 기존 숫자 필드 **재사용 불가** | ✓ |

`man_power` 등 레거시 컬럼은 **현행 스키마에 없음**. `rmk` JSON/파싱 **금지**.

**수확 ↔ 원물입고:** 업무 **분리** 유지. 수확 저장 ≠ `t_stock_master` IN.  
향후 원물등록 화면에서 **같은 날 수확기록 참조** UX — 후속 후보만.

**모바일 판매관리 (2026-08-19):** 하단 **판매관리** · 상단 4탭(포장/생산·재고·주문·판매). 포장/생산 = `PackProdPanel`, 재고 = `StockView` (조회 전용). **강제 workflow 아님.**

---

## 1. 최상위 업무 모델

**판매**가 최종 공통점. 아래는 모두 **선택** 단계.

```
수확
  ↓
(생산/변환)     ← StockPage 생산확정 (PACK / PROCESS)
  ↓
(재고)          ← t_stock_master (원물 FR010300 / 상품 FR010100·FR010200)
  ↓
판매            ← t_sales_* (CONFIRMED 시 회계)
  ↑
(주문)          ← t_order_* (선주문 가능, allocated_qty=0 정상)
```

- 주문은 생산 **앞**(선주문) 또는 **뒤**(생산 후 접수) 모두 가능.
- `주문 → 배정 → 출고 → 판매`는 **저장배 소매 등 일부 경로**이며 전체 판매의 공통 흐름이 **아님**.

### 1.1 혼동하지 않을 5가지 축

| 축 | 예 | 비고 |
|----|-----|------|
| 1. 주문 존재 | 선주문 O/X | 주문 없이도 판매 가능(수출·가락) |
| 2. 생산방식 | PACK(포장) / PROCESS(배즙) | **품종 if 아님** |
| 3. 재고 존재 | 원물·상품·없음 | `t_stock_master` 자연키 |
| 4. 출고방식 | STOCK(배정재고) / DIRECT(즉시) | DEC-020 **한 축**. 판매유형 아님 |
| 5. 판매유형 | 소매·수출·가락·도매 | §2 참조 |

**금지:** `원황=DIRECT`, `신고=STOCK` 같은 품종 코드 분기.

---

## 2. 실제 판매유형별 흐름

운영 예시. 같은 품종도 경로가 달라질 수 있다.

### 2.1 원황 수출

```
수확 → 포장 → 생산수량 확정 → 수출판매
```

- 예약/주문 없음 · 원물 저장 없음 · 포장 후 실제 판매수량 확정

### 2.2 신고 수출

```
수확 → 원물 저장 → 포장 → 생산수량 확정 → 수출판매
```

- 예약/주문 없음 · 저장=원물(`FR010300`) · 상품수량=포장 후 확정

### 2.3 가락시장

```
수확 → 원물 저장 → 포장 → 상품수량 확정 → 가락 출하 → 경매 → 판매확정
```

- 별도 예약 없음 · 저장재고=원물 · DRAFT→확정 TX (DEC-010)

### 2.4 추석/조생 소매

```
(선주문 가능) → 수확 → 포장 → 주문출고 → 판매
```

- 상품재고/HOLD를 **반드시** 거치지 않음 (DEC-020 DIRECT 출고 축)

### 2.5 저장배 소매

```
수확 → 원물 저장 → 포장 → 상품재고 → 주문 → 재고배정 → 출고 → 판매
```

- **Stage 3A** 대상: 이미 있는 상품재고를 주문에 예약

### 2.6 배즙 — 완제품 재고 있음

```
주문 → 배즙 상품재고(FR010200) → 배정/출고 → 판매
```

### 2.7 배즙 — 재고 없음

```
주문 → 원물 → PROCESS → 생산수량(박스) 확정 → 판매 → 잔량 자동재고
```

### 2.6·2.7 공통 — 단위 (DEC-024) · PC 조사

**정책:** 사용자 UI 단위 = **박스**. 포 표기 **금지**. DB qty migration **금지**.

| 위치 | 현재 | DB qty 의미 | 변환 필요? |
|------|------|-------------|:----------:|
| `stock_page` 실사 이력 205–206행 | 「포」 | `t_stock_log.qty` = **낱개 수** | **UI만** |
| `order_page` 465,496,761,785,1300행 | 「포」 | `t_order_detail.qty` = **낱개 수** | **UI만** |
| `order_page` FR010200 | `SZ01` 중 「포」 코드를 size/weight | `weight` = 규격값(예 30), `qty` = **박스(포) 개수** | **UI만** |
| `t_stock_master` FR010200 | 데이터 **없음**(로컬 DB) | `in_qty`/`out_qty` = 개수 | PROCESS 구현 시 동일 패턴 |

**결론:** DB는 이미 **개수(정수)** 로 저장. 「포」는 **표기·라벨** 문제. 1포 = 1박스로 **명칭 통일**하면 변환 없음.  
PROCESS 생산: `save_production_log`와 동일 패턴으로 `item_cd=FR010200` IN **가능** (코드 **미구현**).

---

## 3. PC 재고관리 기준 (`ui/pages/stock_page.py`)

기존 PC를 **폐기하지 않고** 확장하는 방향.

| 항목 | PC 현재 | 설계 |
|------|---------|------|
| 품목 | `FR010100` 배 · `FR010200` 배즙 · `FR010300` 원물 | 유지 |
| UI | 원물/상품 모드 토글 · 재고 맵 · 작업대 | 유지 |
| 원물 등록 | `register_raw_material` → `t_stock_master` IN | 유지 |
| 생산확정 | `save_production_log` — 원물 OUT + 상품 IN + `t_stock_log` | 유지·확장 검토 |
| 수율 | `update_gauge` — 투입kg vs 생산kg 자동 | 유지. 감모 상세분류 강제 금지 |
| 상품 실사 | `audit_product_stock` — AUDIT 로그 | 유지 |
| 폐기 | `dispose_raw_material` | 유지 |
| 작업 연동 | 생산확정 시 `t_work_detail` DONE | 유지 |

**현재 PC 한계 (코드 확인, 2026-08-19):**

| 기능 | 파일·함수 | 상태 |
|------|-----------|------|
| 배 PACK 생산 | `save_production_log` | 원물 OUT + **FR010100** IN 전량 |
| 배즙 PROCESS | `save_production_log` + core `ProductionService` | 원물 OUT + FR010200 IN (RAW_STOCK만, HARVEST 차단) |
| 원물 등록 | `register_raw_material` | CT01·20kg·**재고 IN** (≠ 수확기록) |
| 수율 | `update_gauge` | 투입kg(×20) vs 생산kg 자동 |
| 판매 | `sales_page.execute_full_save` | **`t_stock_*` 미참조** — 재고 없이 판매 가능 |
| 가락 DRAFT | `save_realtime_auction_draft` | **`t_stock_*` 미참조** |
| 주문 Hold | `order_page.save_entire_order` | legacy reserved (Stage 2 분리 후) |

---

## 4. 생산/변환 — 재고관리 책임

**판매관리가 아님.** “무엇을 얼마 써서 무엇을 얼마 만들었는가.”

```
재고관리 (StockPage 확장 우선)
├─ 원물재고   FR010300
├─ 상품재고   FR010100 / FR010200
├─ 생산/변환  PACK / PROCESS
└─ 재고이력   t_stock_log (IN/OUT/AUDIT/HOLD…)
```

생산/변환 **대메뉴 신설은 확정 아님.** `StockPage` 생산확정 확장 우선.

### 4.1 작업 유형 (업무 개념만, DB값 미확정)

| 유형 | 의미 | PC 근사 |
|------|------|---------|
| **PACK** | 포장배 생산 | `ProductionService` / `save_production_log` |
| **PROCESS** | 배즙 가공 (박스) | `ProductionService` (RAW_STOCK만) |

**투입 출처:**

| 코드 | 의미 |
|------|------|
| **HARVEST** | 수확 직후 — 저장재고 없이 투입. PACK만. 상품 harvest_year = `work_dt` 연도 |
| **RAW_STOCK** | 저장된 원물 **N건** 투입 (qty>0만). 품종·harvest_year 혼합 금지 |

상세: §16.

---

## 5. 생산확정 UX (DEC-023 정책)

생산 종료 시 **규격별 생산수량만** 입력. 자동: 날짜·사용자·수율·로그·내부 식별.

**선택(단순):**

| 선택 | 동작 |
|------|------|
| **재고로 저장** | 생산확정 TX(이미 전량 IN) **이후** 화면 종료/reset. **추가 stock IN 없음** |
| **바로 판매** | 생산확정 TX 이후 결과 N건 `salesPrefill` · 판매 탭 이동. Stage 5C 전까지 판매 INSERT·상품 OUT **없음** |

**바로 판매 + 잔량 (A안, DEC-023 업무 확정):**

```
생산 100 → (내부) 상품재고 IN 100 → 판매 화면(100 자동)
→ 사용자 판매 80 확정 → (내부) OUT 80 → 잔량 20은 재고에 자동 잔존
```

- 생산 화면에서 80/20 **재분할 입력 금지**
- 생산수량 **판매 화면 재입력 금지** (DEC-021)
- 판매 화면과 생산 화면 **분리**, UX는 **연속**
- 사용자에게 IN/OUT **노출하지 않음** — 시스템 자동

**PC 현재 (`save_production_log`):** 생산 TX = 원물 OUT + 상품 **전량 IN** (이미 동일). 선택·판매 prefill·판매 시 OUT **없음**.

### 5.1 OPEN-PROD-03 CLOSED — 전량 IN → 판매/출고 OUT

**확정: 전량 IN → 판매/출고 확정 시 OUT.** (partial IN **폐기**)

| 단계 | TX | 비고 |
|------|-----|------|
| 생산확정 | 원물 OUT + 상품 **전량 IN** + `t_stock_log` IN | **현 `save_production_log`와 동일** |
| [재고로 저장] | 위에서 종료 | 추가 TX 없음 |
| [바로 판매] | 생산 TX **완료 후** 판매 화면 prefill (세션) | 생산 rollback **없음** |
| 판매확정 | `t_sales_*` + 상품 **OUT** + `t_stock_log` 판매출고 | Stage **5C Core 구현**. PC/모바일 UI 연결 **후속** |

**partial IN(잔량만 20 IN) vs 전량 IN 비교:**

| | partial IN (**폐기**) | **전량 IN (CLOSED)** |
|--|-------------------|-------------------|
| PC `save_production_log` | 신규 분기 필요 | **그대로** |
| 판매 중단/실패 | pending·rollback 복잡 | **재고 100 유지** — 안전 |
| 잔량 20 | 판매 후 IN | IN−OUT **자동 잔존** |
| partial IN 전용 로직 | 필요 | **불필요** |
| pending 테이블 | 유혹 | **불필요** |

코드 검증 (`save_production_log` 637–642행): 생산 TX는 `execute_transaction` **한 번**에 commit. 이후 판매 화면을 닫아도 **상품재고 소실 없음**.

### 5.2 생산 TX / 판매 TX 분리 (중단·취소)

| 사용자 행동 | 생산 TX | 상품재고 | 판매 |
|-------------|---------|----------|------|
| 바로판매 → 뒤로가기/취소 | **유지** (rollback 금지) | 전량 IN **유지** | 미생성 — **나중에 재등록** |
| 앱 종료 | 동일 | 동일 | 동일 |
| 판매 저장 실패 | 동일 | 동일 | 재시도 |
| 판매 80 확정 | 유지 | OUT 80 → **잔량 20** | 생성 |

생산확정 = **완료된 업무**. 판매는 **별도 TX**. 화면만 연속.

### 5.3 판매확정 시 OUT — 유형별 (Stage 5C 후속, 코드 미구현)

`sales_page.execute_full_save`는 **`t_stock_master` 미참조** (2616행~). 재고 정합 OUT는 Stage 5C에서 추가.

| 유형 | 판매 생성 | 상품 OUT 시점 | 비고 |
|------|-----------|---------------|------|
| **수출** (원황/신고) | `sales_page` CONFIRMED | 판매확정 TX (권장) | 현재 재고 무관 INSERT |
| **소매 즉시** (DIRECT) | 동일 | 판매확정 TX (권장) | Stage 3A alloc **불필요** |
| **저장배·배즙재고** (STOCK) | 주문→출고→판매 | 출고 TX (alloc consume·reserved 해제 포함) | Stage 5A + Stage 5C |
| **가락** | DRAFT (`market_price_page`) | **CONFIRMED 확정 TX** | DRAFT는 OUT **없음** (DEC-010) |
| **배즙 주문생산** | A안 prefill | 생산 전량 IN 후 판매 OUT | PROCESS 선행 |

가락: DRAFT ≠ CONFIRMED. OUT은 **경매 확정** 시점에만.

---

## 7. Stage 5A (구 3A) 위치

Stage 5A = **이미 존재하는 상품재고**를 주문에 예약. **실제 OUT이 아님.**

```
상품재고 → 주문 → t_order_alloc → HOLD → (Stage 5C STOCK 출고) → 판매
```

- 전체 판매 필수단계 **아님**. `allocated_qty=0` 정상.
- FIFO/LIFO/reserved/HOLD/CANCEL_HOLD/allocation API — **유지** (저장배·배즙재고 등).

---

## 8. DEC-020 (출고방식 축)

STOCK/DIRECT **폐기 아님**. 다만 **전체 판매모델 설명에는 부족** — §1.1 5축과 함께 본다.

- **STOCK:** `ship_qty <= allocated_qty - shipped_qty`, alloc·reserved·out
- **DIRECT:** allocation/HOLD 없이 출고·판매 (추석/조생 소매 등)
- DIRECT는 **판매유형 이름이 아님**.

---

## 9. OPEN-PROD CLOSED (DEC-025)

**신규 `t_production_*` 생성 안 함.** 기존 `t_stock_master` · `t_stock_log` · `t_work_*` · 판매/주문 최대 활용.

| ID | 상태 | 확정 |
|----|------|------|
| **OPEN-PROD-01** | **CLOSED** | 추적 = `work_id` + `t_stock_log`. Batch UI/번호 **없음**. 구현에서 명백한 부족 확인 전 신규 생산테이블 **제안 금지** |
| **OPEN-PROD-02** | **CLOSED** | 영농일지. DDL 설계 `variety_cd TEXT` + `harvest_container_qty INTEGER`. ALTER는 **후속 수확 단계** |
| **OPEN-PROD-03** | **CLOSED** | §5.1 **전량 IN → 판매/출고 OUT**. 생산/판매 TX **분리**. 세션 prefill·공통 OUT은 **후속 구현** |

### 9.1 생산확정 DB — 전량 IN (CLOSED)

**현재 PC (`save_production_log`):** 원물 OUT + 생산상품 **전량 IN** — 확정안과 **동일**.

**목표 (DEC-023):**

| 경로 | 생산 TX | 판매 TX |
|------|---------|---------|
| 재고로 저장 100 | IN 100 | — |
| 바로판매 100→80 | IN 100 (**완료**) | 판매 80 + OUT 80 → **잔량 20 자동** |

**검증 요약:**

1. `save_production_log` — 이미 전량 IN ✓  
2. 생산 후 판매 화면 이탈 — 재고 **유지** ✓ (별도 pending 불필요)  
3. `sales_page.execute_full_save` — stock **미검사** → 판매 INSERT만 가능; **OUT은 Stage 4**  
4. partial IN 전용 로직 — **폐기**  
5. `t_stock_master` / `t_stock_log` — **그대로**  
6. `t_production_*` — **안 함** (OPEN-PROD-01 CLOSED)

---

## 10. 갭 분석 요약 (DEC-025)

| 영역 | 기존 PC/DB | 그대로 사용 | 최소 보완 | 신규 DDL |
|------|------------|-------------|-----------|----------|
| 수확기록 | `t_work_detail` 텍스트 필드만 | 작업일·상태 | **품종+상자 수** | **승인됨** 2컬럼 (미실행) |
| 원물재고 | `register_raw_material` | CT01·IN/OUT | 수확기록과 **분리** UX | 불필요 |
| PACK(배) | `save_production_log` | 원물 OUT·상품 IN·수율 | A안·선택 UI | 불필요 |
| PROCESS(배즙) | `save_production_log` 확장 + core `ProductionService` | 원물 OUT + 배즙 IN(박스) | 저장 원물만 허용(P) | 불필요 |
| 생산→재고 | 전량 IN | **현행과 동일** | “재고로 저장” = 추가 TX 없음 | 불필요 |
| 생산→바로판매 | 생산 TX 후 prefill | 전량 IN | UI 세션·Stage 5C OUT | 불필요 |
| 잔량 자동재고 | IN−OUT 잔존 | **전량 IN 방식** | 판매확정 OUT만 추가 | 불필요 |
| 주문배정 | Stage 3A Core | **유지** | — | Stage 3A 로컬만 |
| 수출 직접판매 | `sales_page` | **재고 무관** 판매 | 출고 OUT(Stage 5C) | 불필요 |
| 가락 | DRAFT만 | `t_sales_*` | 확정+OUT TX | 불필요 |

PROCESS+HARVEST 조합은 Stage P에서 미지원이며, UI 차단 및 Core 검증으로 안전하게 처리됩니다.

**DDL (설계 승인, 이번 작업 미실행):**

1. `t_work_detail.variety_cd TEXT` + `harvest_container_qty INTEGER` (OPEN-PROD-02 CLOSED). `rmk` **금지**.
2. 생산-판매 DB 연결키 — **UI 세션 prefill**. 테이블 신설 **금지**.

---

## 11. 판매유형 7개 — DB·PC 갭

| # | 유형 | 수확기록 | 원물재고 | PACK/PROC | 상품 IN | 주문 | alloc | 판매 | PC 지원 | 부족 |
|---|------|:--------:|:--------:|:---------:|:-------:|:----:|:-----:|------|---------|------|
| 1 | 원황 수출 | ○ | — | PACK | △ | — | — | 직접 | 판매○ 생산△ | A안·통계 |
| 2 | 신고 수출 | ○ | ○ | PACK | ○ | — | — | 직접 | 원물등록○ | 수확≠등록 |
| 3 | 가락 | ○ | ○ | PACK | ○ | — | — | DRAFT→확정 | DRAFT○ | 확정·OUT |
| 4 | 추석/조생 | △ | — | PACK | △ | ○ | — | DIRECT | 주문○ | alloc·출고 |
| 5 | 저장배 | ○ | ○ | PACK | ○ | ○ | ○ | STOCK | 3A○ PC legacy Hold | 출고 TX |
| 6 | 배즙 재고 | — | — | — | ○ | ○ | ○ | STOCK | 재고조회○ | PROCESS·단위 |
| 7 | 배즙 주문생산 | — | ○ | PROC | △ | ○ | — | A안 | — | PROCESS 전부 |

○=설계 필요/가능 △=부분 —=불필요

---

## 12. 판매 vs 생산 예시

**생산/재고 (StockPage):**

```
원물 1,000kg → PACK → 15kg 25과 20박스 + 15kg 30과 30박스
```

**판매 (Sales):**

```
수출처 A — 25과 20 · 30과 30 · 단가 …
```

주문·배정·출고는 **저장배 소매 등** 경로에서만 개입.

---

## 13. 개발단계와의 관계

운영 표기: [01 §7](./01_overview.md) · [06](./06_development_progress.md).

- **5A (=3A) 배정 Core** · **3 (=H) 수확** · **4 (=P) 생산** · **5B 재고조회** = **구현 완료** (로컬). **main merge 미승인.**
- 생산모델(전량 IN, alloc 비강제)과 5A **충돌 없음**.
- 후속: **5C (=S)** 판매/출고 공통 OUT TX · `salesPrefill` → 실제 판매. 그다음 **6**(구 3B 포함).

---

## 14. Stage 5B 재고 계산 SSOT

Mobile/PC는 수량을 **재계산하지 않는다.** Core/Server가 내려준 값을 동일 기준으로 표시한다.

```
real_qty      = in_qty - out_qty          # 현재고
reserved_qty  = t_stock_master.reserved_qty  # 배정 (HOLD 누적)
available_qty = real_qty - reserved_qty   # 가용재고
```

| 용어 | 필드 | 의미 |
|------|------|------|
| 현재고 | `real_qty` | 실제 남은 수량. HOLD해도 변하지 않음 |
| 배정 | `reserved_qty` | 주문 예약. **실제 OUT이 아님** |
| 가용재고 | `available_qty` | 새로 배정·판매에 쓸 수 있는 수량 |

배정 예: 현재 30 · HOLD 10 → 현재 30 · 배정 10 · 가용 20. RELEASE 후 배정 0 · 가용 30.  
Stage 5C 판매확정 전까지 **상품 `real_qty`는 변하지 않는다.**

---

## 15. 재고 종류 · natural key

`t_stock_master` 자연키 (생산 IN · 재고조회 · allocation 동일):

`farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt`

| 유형 | `item_cd` | 사용자 식별 개념 | 표시 예 |
|------|-----------|------------------|---------|
| 원물 | `FR010300` | farm + 창고 + item + 품종 + 원물구분(`size_cd`) + harvest_year + storage_dt | 신고 · 중과 · 2025-10-01 · 가용 240통 |
| 상품 | `FR010100` | farm + 창고 + item + 품종 + 포장중량 + 과수(`size_cd`) + 등급 + harvest_year + storage_dt | 신고 · 15kg · 25과 · 특 · 가용 20박스 (현재 30 · 배정 10) |
| 배즙 | `FR010200` | 동일 키. 사용 단위 **박스** (DEC-024) | 배즙 · 현재/배정/가용 |

필드 의미:

| 키 | 상품 | 원물 |
|----|------|------|
| `weight` | 포장중량. 비교는 `ABS(weight-?)<1e-9` (생산 OUT · allocation 동일) | 원물 중량 |
| `size_cd` | 과수 공통코드 (`FR02…`, 주문과 동일) | 원물구분(대/중/소/혼합 등) |
| `grade_cd` | 공통 등급코드 | 원물 등급(해당 시) |
| `harvest_year` | **원료 과실 수확연도** (DEC-026). 포장/생산연도 아님 | 원물 수확연도 |
| `storage_dt` | 상품은 생산/입고일 | 원물 입고일 |

Production IN · GET fruit-stock · allocation FIFO는 위 키를 **같은 의미**로 쓴다.

---

## 16. 생산 ↔ 재고 · 복수 원물 (Stage 4/5B)

동일 Production TX (`ProductionService.confirm`, `BEGIN IMMEDIATE` 1회).

| 조합 | 원물 OUT | 결과 IN |
|------|:--------:|:-------:|
| PACK + RAW_STOCK | 원물 **N건** OUT | 상품 결과 N건 IN |
| PACK + HARVEST | **없음** (수확상자는 재고가 아님) | 상품 결과 N건 IN |
| PROCESS + RAW_STOCK | 원물 OUT | 배즙 IN (박스) |
| PROCESS + HARVEST | **미지원** (Core `HARVEST_PROCESS`) | — |

### 16.1 RAW_STOCK 복수 투입

한 생산에서 원물 N건 사용 가능. 행 사용수량 빈값 또는 0 = **이번 생산 미사용**. `qty > 0`만 실제 투입.

Mobile payload: `raw_consumptions`에 `qty > 0`인 row만 포함.  
예: 대과 30 · 중과 0 · 소과 60 · 혼합 빈값 → 대과30 + 소과60 두 건만 전송.

### 16.2 TX / rollback

N건 OUT + N건 IN을 **한 TX**. 하나라도 실패하면 모든 OUT·IN **전체 rollback**. 부분 성공 금지.

### 16.3 정합 (Core 검증, Mobile만 의존 금지)

한 생산확정에서 투입 원물의 `variety_cd` · `harvest_year`가 **모두 동일**해야 한다.

허용: 신고 중과/2026 + 신고 소과/2026.  
차단: 신고/2026 + 원황/2026 (`MIXED_VARIETY`).  
차단: 신고/2025 + 신고/2026 (`MIXED_YEAR`).

---

## 17. harvest_year (DEC-026)

**의미:** 이 상품이 **몇 년산 과실에서 생산되었는가**. 생산(포장)연도가 아니다.

| 경로 | 상품/결과 `harvest_year` |
|------|--------------------------|
| RAW_STOCK | 투입 원물 `harvest_year` **승계** |
| HARVEST | 선택 수확기록 `t_work_detail.work_dt`의 **연도** |
| PROCESS | 원물 `harvest_year` 승계 |

주문 `t_order_detail.harvest_year`도 같은 의미 — allocation이 이 연도로 stock을 탐색한다 (DEC-018).

**업무 전제:** 배 재고는 일반적으로 1년 이상 장기보관하지 않는다. 다년도 rollover · 2년 이상 carry-over · 연도 혼합 생산 · 복잡한 다년도 재고 UI는 **설계하지 않는다.** `harvest_year`는 식별·allocation 정확성을 위해 **유지**.

---

## 18. 생산확정 이후

```
RAW OUT / PRODUCT IN  →  COMMIT   ← 이 시점에 재고 처리 완료
```

| 버튼 | 의미 |
|------|------|
| [재고로 저장] | 별도 DB 저장 **없음**. 화면 종료/reset |
| [바로 판매] | 생산결과 N건 `salesPrefill` + 판매 탭 이동 |

현재 Stage: 판매 INSERT 없음 · 상품 OUT 없음 · allocation consume 없음 → **Stage 5C**.

---

## 19. 재고관리 UX (Stage 5B)

재고는 사용자가 다시 기록하는 기능이 **아니다.** OPS가 기존 업무 TX 결과를 자동 집계해 보여준다.

금지: 수동 재고 수정 · 임의 IN/OUT · 재고 삭제 · 재고수량 수기 입력.

제공: 현재고 · 배정 · 가용 · 원물/상품/배즙 구분 · 소진 포함 필터 · 재고 이력.

화면: 판매관리 상단 **포장/생산 | 재고 | 주문 | 판매**. 재고 내부 **원물 | 상품 | 배즙**.  
기본: 소진재고 숨김 (`include_zero=false`). 옵션: 소진 포함.  
재고 탭 진입 시 최신 `GET /farms/{farm}/fruit-stock` 재조회 (생산확정 후 이동 시 새 DB 상태 확인).

---

## 20. 재고 이력 (`t_stock_log`)

read-only. 현재 유형: IN · OUT · HOLD · CANCEL_HOLD / RELEASE 계열.

| io_type | 사용자 표현 (5B) | 주의 |
|---------|------------------|------|
| IN | 생산입고 | |
| OUT + remark 원물 사용 | 원물사용 | |
| 기타 OUT | 출고 | **OUT = 항상 원물사용이 아님** |
| HOLD | 주문배정 | 실제 출고 아님 |
| CANCEL_HOLD | 배정해제 | |

Stage 5C 이후 상품 OUT = **판매출고**. 표시명은 재고 종류 / remark / ref / source 등 **발생 원인**으로 구분한다.

### 20.1 추적 컬럼 (DEC-027, 멱등 DDL)

`t_stock_log.stock_seq` / `ref_type` / `ref_id` 추가. 기존 행 NULL. 물리 FK 없음.  
SALE: `ref_id=sale_detail_no`. remark만으로 OUT 원인 구분하지 않음.

---

## 21. Stage 5C 출고 규칙 (DEC-027)

**1 sales_detail = 1 stock_seq.** FIFO N로트 → N행. STOCK·DIRECT 동일. 연결 테이블 없음.

```
주문 OD001 / 10
stock_seq 101 → 6    →  sales_detail A  stock_seq=101 qty=6
stock_seq 105 → 4    →  sales_detail B  stock_seq=105 qty=4
```

DIRECT 8: 가용 FIFO 201→5, 204→3 → 판매상세 2행. alloc `shipped_qty` 미갱신.

두 수량축:

- 주문 잔여 = `qty - SUM(CONFIRMED sales_detail)`
- STOCK 잔여 = `allocated_qty - shipped_qty`

consume: `shipped_qty +=` (allocated 유지) + `reserved −` + `out +` 동일 TX.

과출고: `confirmed + request <= qty`. 완료: 전 줄 `==`. ST010300 = 첫 출고·잔량. ST010400+`stock_status=Y` = 전량. 배정은 ST01에 넣지 않음.

허용: 주문+STOCK / 주문+DIRECT / 무주문+DIRECT. 거부: 무주문+STOCK.

`OrderShipService.confirm()` **구현**. HTTP `POST /api/v1/farms/{farm_cd}/shipments/confirm`. `stock_seq`는 Client가 고르지 않음. Mobile UI 연결은 Stage 6.
