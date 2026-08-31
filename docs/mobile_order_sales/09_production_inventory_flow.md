# 09. Production & inventory flow — 생산/재고 (PC 기준)

> **역할:** 실제 농장 업무·기존 PC `StockPage`를 기준으로 한 **생산/재고** SSOT.
> 주문/판매 상세는 [02_domain_flow.md](./02_domain_flow.md). 데이터 계약은 [03_data_contract.md](./03_data_contract.md).
> OPEN-PROD-01~03 **CLOSED**. Stage P/5B/5C·출고 UX **운영 반영** (`fd963e0` 계열). *(역사 스냅샷의「main 미머지」는 [06](./06_development_progress.md) 역사 절 참고)*.
>
> **개정 (2026-08-31):** DEC-035 HARVEST N:M — **OPS APPLIED** · **OPERATIONAL PASS** ([06](./06_development_progress.md)). 경매(DEC-036/037)는 설계·미구현. DEC-035 물리 스키마 = [03 §8A](./03_data_contract.md).

---

## 0. UX 최우선 원칙 (DEC-021)

**농부에게 일을 더 만들지 않는다.**

| 원칙 | 적용 |
|------|------|
| 중복입력 금지 | 생산수량을 판매 화면에서 다시 입력하지 않음 · 출하수량/확인수량 이중 입력 최소화 |
| 자동 | 날짜·사용자·채번·시스템이 아는 값 · 경매 확정 시 판매분류 자동(§2.3.1) |
| 내부 기록 | Batch·lot·`stock_seq`·`work_id`·생산/출하 내부키는 사용자가 관리·입력하지 **않음** |
| 입력 최소 | 화면 필드는 업무에 꼭 필요한 것만 · 경매 상품 **복수 선택·일괄** [경매 넘기기] |
| 선택 단계 강제 금지 | 배정·저장·생산이 선택인데 필수 화면으로 만들지 않음 |
| 수확 선택 표시 | 수확량 / 사용량 / **남음**이 사용자 언어로 보이게 |

실사용: 농업 현장 · 1인 운영 비중 높음 · 작업 중 짧은 모바일 사용.
최근 시장/법인 값은 가능하면 자동·최근값 활용(구현 세부 OPEN).

---

## 0.1 수확기록 (DEC-022 APPROVED)

**영농일지**의 수확작업(`t_work_detail`)으로 관리. 재고관리에서 **조회** 가능(UI 연동은 후속).

| 항목 | 정책 |
|------|------|
| 사용자 입력 | 수확일자 · 품종 · **콘테이너 상자 수** |
| 자동 | 수확년도(일자 기준) · 작업자 · reg_dt |
| 단위 | **콘테이너 상자** — kg 입력 **금지** |
| 금지 | 수확 저장 = `t_stock_master` 자동 입고 |

수확기록 = 통계/생산 **출발점**이며 **재고 row가 아님**.
동시에 **수확잔량 SSOT의 원천**이다 ([§0.2](#02-수확잔량--소진이력)).

**통계 목표(추가 입력 없음):** 연도별·품종별·일자별 총수확량, 전년 대비.

**PC 현재와 차이 (`stock_page.register_raw_material`):**

- 별도 “원물 등록” — `CT01` 규격 카드 + **20.0kg 고정** + `t_stock_master` IN
- 영농일지 `t_work_detail`과 **미연동**
- 콘테이너 상자 ≠ 원물 20kg 통 — **동일시·자동 변환 금지**

**실제 DB 스키마 (`orchard_platform.db` PRAGMA, 2026-08-19):**

| 컬럼 | 수확기록 용도 |
|------|---------------|
| `work_dt` | 수확일자 ✓ |
| `work_mid_cd` | `WK010300`(수확작업) ✓ |
| `work_loc_id` | **필지** — 품종 **아님** |
| `rmk` | 비고 텍스트 — **상자 수 저장 금지** |
| `harvest_container_qty` / `variety_cd` | Stage H DDL (로컬/테스트) ✓ |

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

**금지:** 수확 `DONE`만으로 **잔량 0·전량소진**을 판단하지 않는다 ([OPEN-DONE](#23-open-정책)).

---

## 0.2 수확잔량 · 소진이력

### 잔량 SSOT

```
수확잔량 = harvest_container_qty − SUM(유효한 소진 상자수)
```

- 단위: **콘테이너 상자** (원물 CT01/20kg와 혼동 금지).
- 잔량 > 0 인 수확은 **이후 포장에서 재사용** 가능.
- 사용자 표시: 수확량 / 사용량 / **남음** (내부키 비노출).

### 최소 소진이력 (개념)

한 행(또는 동등 최소 기록)이 보존해야 할 **3축**:

| 축 | 의미 |
|----|------|
| harvest work | 어느 수확기록에서 |
| 생산확정 1회 | 어느 생산확정 이벤트에서 (시스템 내부 식별 · **사용자 비노출**) |
| 사용 상자수 | 이번 생산에서 쓴 상자 수 |

그래서 예:

```
8/27 수확 30
 ├─ 생산 A : 20
 └─ 생산 B :  5
남음 5
```

생산 A만 취소·정정 시 **A분 20만** 원복할 수 있어야 한다.

### 기각

| 방식 | 이유 |
|------|------|
| `t_stock_log` **단독** | 수확은 stock row가 아님. 상품 IN 축과 상자 소진 축이 다름. 생산확정 1회 id·정정 복원 불가 |
| `used_qty` **누적 컬럼만** | 잔량 숫자는 되나 포장별 기여·부분 원복·감사 추적 불가 |
| `t_production_master` / `detail` **풀세트** | DEC-025 — **만들지 않음** |

### DEC-025와의 관계

DEC-025 **유지** (`t_production_*` 풀세트 금지). DEC-035 **최소 소진이력** = `t_harvest_consumption` — **OPS APPLIED** · **OPERATIONAL PASS** ([03 §8A](./03_data_contract.md) · [07 DEC-035](./07_decisions.md)).

생산확정 TX에서는 **consumption INSERT + 상품 전량 IN(DEC-023)** 을 `BEGIN IMMEDIATE` 한 TX에서 처리 ([§16.4](#164-harvest-복수--부분소진)).

---

## 1. 최상위 업무 모델

**판매**가 최종 공통점. 아래는 경로에 따라 **선택** 단계.

```
수확 (영농일지 · 상자)
  ↓
수확잔량 (소진이력으로 추적)
  ↓
(생산/포장)     ← PACK / PROCESS · 복수 수확 또는 원물 N건
  ↓
상품재고        ← t_stock_master (전량 IN)
  ↓
(경로 분기)
  ├─ 주문/직접판매 등 → 기존 출고·판매 (DEC-020 · DEC-027)
  └─ 경매
        → 경매출하 (출하중 · 가용 제외 · 판매 아님)
        → 청과 확인 / 차이
        → 판매확정 (+ 판매 OUT · 분류 자동)
```

- 주문은 생산 **앞**(선주문) 또는 **뒤**(생산 후 접수) 모두 가능.
- `주문 → 배정 → 출고 → 판매`는 **저장배 소매 등 일부 경로**이며 전체 판매의 공통 흐름이 **아님**.
- 경매 경로의 **출하중**은 판매 DRAFT가 아니다 ([§2.3.1](#231-경매출하--출하중)).

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

### 2.3 가락시장 / 경매

```
수확 → (원물 저장 선택) → 포장 → 상품재고
  → 경매 넘기기 (출하중 · 가용 제외)
  → 청과 확인 / 차이 / 매칭
  → 판매확정 (분류 자동 + 판매 OUT)
```

- 별도 예약 없음 · 저장재고=원물(선택) · **출하 ≠ 판매 DRAFT**.
- ~~SUPERSEDED: `DRAFT → CONFIRMED → OUT`만으로 출하를 설명하던 서술~~ — 역사는 [부록](#부록-superseded--현행-코드-스냅샷).
- **DEC-010 — SUPERSEDED** (2026-08-27). 후계: **[DEC-036](./07_decisions.md)** 경매 출하 · **[DEC-037](./07_decisions.md)** 경매 판매확정. 상태 SSOT = [07](./07_decisions.md).

#### 2.3.1 경매출하 · 출하중

```
상품 가용
  → 복수 선택 [경매 넘기기]
  → 출하중 (판매 아님 · 가용에서 제외)
  → 청과 확인 / 차이
  → 판매확정
```

| 규칙 | 내용 |
|------|------|
| 출하 ≠ DRAFT | `t_sales_*` DRAFT는 **판매초안** 의미. **출하 SSOT로 쓰지 않음** |
| `reserved_qty` | **주문 HOLD 전용**. 경매 출하중 **재사용 금지** |
| 출하 시 `out_qty` | **선차감 금지**. 아직 판매 OUT 아님 |
| 출하중 SSOT | 최소 **출하 묶음 + 라인** 개념. 단순 `transit_qty` 컬럼 하나 = SSOT **금지** |
| 출하중 수량 | **유효한 출하 라인 집계**로 계산 (물리 컬럼명 미정) |
| 묶음(개념) | 출하일 · 시장 · 법인 · 상태 |
| 라인(개념) | 상품재고 연결 · 농장 출하수량 · 청과 확인수량 · (이후) 판매 연결 |
| UX | 내부 출하번호·`stock_seq` **비노출** · 다선택 일괄 |

**판매확정 시 자동 분류 (사용자 선택 없음):**

| 축 | 코드 | 명칭 |
|----|------|------|
| 판매유형 | `SA010200` | 도매 |
| 판매구분 | `SA020400` | 경매판매 |
| 판매경로 | `SA030300` | 경매연동 |

**재고 처리 원칙:**

| 시점 | 재고 | 판매 |
|------|------|------|
| 출하(경매 넘기기) | 가용에서 **출하중 수량 제외** | 판매 생성 **아님** |
| 판매확정 | 출하중 **종료** · 승인된 **최종 판매수량** 기준 **판매 OUT** | CONFIRMED + 분류 자동 |

출하 시 OUT하지 않으므로 **이중 OUT 없음** (DEC-027 판매 OUT 원칙과 정합).

기존 `save_realtime_auction_draft`는 **판매 DRAFT 저장**일 뿐이며, 본 절의 **출하중 SSOT가 아니다**.

#### 2.3.2 출하수량 / 청과확인수량

| 수량 | 정책 |
|------|------|
| **농장 출하수량** | 출하 시점 원본. **이후 UPDATE로 덮어쓰기 금지** |
| **청과 확인수량** | **별도** 보존 |
| **차이** | `확인수량 − 출하수량` (예: 19 − 20 = −1). UI에 표시 |

차이(감모·반입·정정·회계) 처리 정책은 **확정하지 않음** → [OPEN-QTY-DIFF](#23-open-정책).
구조상 **두 원수량은 반드시 보존**한다.

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
| 원물 등록 | `register_raw_material` → `t_stock_master` IN | 유지 (≠ 수확) |
| 생산확정 | `save_production_log` — 원물 OUT + 상품 IN + `t_stock_log` | 유지·**HARVEST 복수/소진** 확장 |
| 수율 | `update_gauge` — 투입kg vs 생산kg 자동 | 유지. 감모 상세분류 강제 금지 |
| 상품 실사 | `audit_product_stock` — AUDIT 로그 | 유지 |
| 폐기 | `dispose_raw_material` | 유지 |
| 작업 연동 | 생산확정 시 `t_work_detail` DONE | **DONE≠잔량 SSOT** ([OPEN-DONE](#23-open-정책)) |

**현재 PC 한계 (코드 확인, 2026-08-19 · 현행 구현 스냅샷):**

| 기능 | 파일·함수 | 상태 |
|------|-----------|------|
| 배 PACK 생산 | `save_production_log` / `ProductionService` | 원물 OUT + **FR010100** IN 전량 |
| HARVEST 투입 | Mobile/PC | **사실상 수확 1건** · 소진이력 없음 (목표: §16.4) |
| 배즙 PROCESS | `ProductionService` | 원물 OUT + 배즙 IN (RAW_STOCK만, HARVEST 차단) |
| 원물 등록 | `register_raw_material` | CT01·20kg·**재고 IN** (≠ 수확기록) |
| 가락 DRAFT | `save_realtime_auction_draft` | 판매 DRAFT만 · **출하중·재고 미접촉** |
| 경매 출하중 | — | **미구현** (본 문서 설계) |

---

## 4. 생산/변환 — 재고관리 책임

**판매관리가 아님.** “무엇을 얼마 써서 무엇을 얼마 만들었는가.”

```
재고관리 (StockPage 확장 우선)
├─ 원물재고   FR010300
├─ 상품재고   FR010100 / FR010200
├─ 생산/변환  PACK / PROCESS
├─ 수확잔량   (소진이력 · work 기준)
└─ 재고이력   t_stock_log (IN/OUT/AUDIT/HOLD…)  ※ 수확 상자 소진 SSOT 아님
```

생산/변환 **대메뉴 신설은 확정 아님.** `StockPage` 생산확정 확장 우선.

### 4.1 작업 유형 (업무 개념만, DB값 미확정)

| 유형 | 의미 | PC 근사 |
|------|------|---------|
| **PACK** | 포장배 생산 | `ProductionService` / `save_production_log` |
| **PROCESS** | 배즙 가공 (박스). 완제품 선택: 일반배즙 `FR010202` / 도라지배즙 `FR010201`. PROCESS 유형은 1개. 도라지 원료·BOM 없음. 출고 **표시**는 제품명만(내부 weight/size/grade placeholder는 숨김) | `ProductionService` (RAW_STOCK만) |

**투입 출처:**

| 코드 | 의미 |
|------|------|
| **HARVEST** | 수확 상자 투입 (재고 OUT 아님). PACK만. **복수 수확 + 부분소진** ([§16.4](#164-harvest-복수--부분소진)). 상품 harvest_year = 투입 수확의 연도(동일 연도) |
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
| 생산확정 | (HARVEST: 소진이력) + (RAW: 원물 OUT) + 상품 **전량 IN** + `t_stock_log` IN | DEC-023 |
| [재고로 저장] | 위에서 종료 | 추가 TX 없음 |
| [바로 판매] | 생산 TX **완료 후** 판매 화면 prefill (세션) | 생산 rollback **없음** |
| 판매확정 | `t_sales_*` + 상품 **OUT** + `t_stock_log` 판매출고 | Stage **5C** · 경매는 §2.3.1 |

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
HARVEST 소진의 **생산 단위 취소·원복**은 소진이력 3축을 전제로 한다 ([§0.2](#02-수확잔량--소진이력)).

### 5.3 판매확정 시 OUT — 유형별

`sales_page.execute_full_save`는 **`t_stock_master` 미참조** (레거시). 주문/DIRECT OUT는 Stage 5C `OrderShipService`.

| 유형 | 판매 생성 | 상품 OUT 시점 | 비고 |
|------|-----------|---------------|------|
| **수출** (원황/신고) | CONFIRMED | 판매확정 TX | |
| **소매 즉시** (DIRECT) | 동일 | 판매확정 TX | Stage 3A alloc **불필요** |
| **저장배·배즙재고** (STOCK) | 주문→출고→판매 | 출고 TX (alloc consume·reserved 해제) | Stage 5A + 5C |
| **가락/경매** | 판매확정 (출하중 **이후**) | **판매확정 TX의 판매 OUT** | 출하 시 OUT **없음**. DRAFT≠출하 SSOT |
| **배즙 주문생산** | A안 prefill | 생산 전량 IN 후 판매 OUT | PROCESS 선행 |

경매: **출하중 → 확인 → 확정+OUT**. 확정 시 SA010200 / SA020400 / SA030300 자동.

---

## 7. Stage 5A (구 3A) 위치

Stage 5A = **이미 존재하는 상품재고**를 주문에 예약. **실제 OUT이 아님.**

```
상품재고 → 주문 → t_order_alloc → HOLD → (Stage 5C STOCK 출고) → 판매
```

- 전체 판매 필수단계 **아님**. `allocated_qty=0` 정상.
- FIFO/LIFO/reserved/HOLD/CANCEL_HOLD/allocation API — **유지** (저장배·배즙재고 등).
- `reserved_qty`는 **주문 HOLD 전용** — 경매 출하중과 **섞지 않음**.

---

## 8. DEC-020 (출고방식 축)

STOCK/DIRECT **폐기 아님**. 다만 **전체 판매모델 설명에는 부족** — §1.1 5축과 함께 본다.

- **STOCK:** `ship_qty <= allocated_qty - shipped_qty`, alloc·reserved·out
- **DIRECT:** allocation/HOLD 없이 출고·판매 (추석/조생 소매 등)
- DIRECT는 **판매유형 이름이 아님**.
- 경매 출하중은 STOCK/DIRECT와 **별 축** ([§2.3.1](#231-경매출하--출하중)).

---

## 9. OPEN-PROD CLOSED (DEC-025)

**신규 `t_production_master` / `t_production_detail` 풀세트는 생성하지 않는다.**
기존 `t_stock_master` · `t_stock_log` · `t_work_*` · 판매/주문 최대 활용.

| ID | 상태 | 확정 |
|----|------|------|
| **OPEN-PROD-01** | **CLOSED** | Batch UI/번호 **없음**. `t_production_*` 풀세트 **안 함** |
| **OPEN-PROD-02** | **CLOSED** | `variety_cd` + `harvest_container_qty` |
| **OPEN-PROD-03** | **CLOSED** | §5.1 **전량 IN → 판매/출고 OUT**. 생산/판매 TX **분리** |

**보완 (2026-08-31):** DEC-035 `t_harvest_consumption` · `prod_confirm_id` · production trace — **OPS APPLIED** · PC·Lightsail **OPERATIONAL PASS**.

### 9.1 생산확정 DB — 전량 IN (CLOSED)

**현재 PC (`save_production_log`):** 원물 OUT + 생산상품 **전량 IN** — 확정안과 **동일**.

**목표 (DEC-023):**

| 경로 | 생산 TX | 판매 TX |
|------|---------|---------|
| 재고로 저장 100 | IN 100 | — |
| 바로판매 100→80 | IN 100 (**완료**) | 판매 80 + OUT 80 → **잔량 20 자동** |

**검증 요약:**

1. `save_production_log` — 이미 전량 IN ✓
2. 생산 후 판매 화면 이탈 — 재고 **유지** ✓
3. partial IN 전용 로직 — **폐기**
4. `t_production_*` 풀세트 — **안 함**
5. HARVEST 상자 소진 — **최소 소진이력** (상품 natural key 중복 저장 지양)

---

## 10. 갭 분석 요약 (DEC-025)

| 영역 | 기존 PC/DB | 그대로 사용 | 최소 보완 | 비고 |
|------|------------|-------------|-----------|------|
| 수확기록 | `t_work_detail` | 작업일·품종·상자 | 잔량 표시 | DEC-022 |
| 수확 소진 | `t_harvest_consumption` | consumption 3축 | **OPERATIONAL PASS** | **OPS APPLIED** |
| 원물재고 | `register_raw_material` | CT01·IN/OUT | 수확과 **분리** | |
| PACK HARVEST | N:M · partial · overconsume reject | 상품 전량 IN | **OPERATIONAL PASS** | PC·Mobile·Lightsail |
| PACK RAW_STOCK | N건 | 유지 | — | §16.1 |
| 경매 출하중 | (없음) · DRAFT만 | — | **출하 묶음+라인** | ≠ DRAFT |
| 가락 판매 | DRAFT (legacy) | 판매초안 경로 · **출하 SSOT 아님** | **DEC-037** 확정+OUT · 분류 자동 | **DEC-010 SUPERSEDED** |
| 주문배정 | Stage 3A | **유지** | reserved≠출하중 | |

PROCESS+HARVEST 조합은 Stage P에서 미지원이며, UI 차단 및 Core 검증으로 안전하게 처리됩니다.

---

## 11. 판매유형 7개 — DB·PC 갭

| # | 유형 | 수확기록 | 원물재고 | PACK/PROC | 상품 IN | 주문 | alloc | 판매 | PC 지원 | 부족 |
|---|------|:--------:|:--------:|:---------:|:-------:|:----:|:-----:|------|---------|------|
| 1 | 원황 수출 | ○ | — | PACK | ○ | — | — | 직접 | 판매○ 생산△ | 수확 N:M |
| 2 | 신고 수출 | ○ | ○ | PACK | ○ | — | — | 직접 | 원물등록○ | 수확≠등록 |
| 3 | 가락 | ○ | ○ | PACK | ○ | — | — | 출하중→확정 | DRAFT○ | **출하중·확인수량·확정** |
| 4 | 추석/조생 | △ | — | PACK | △ | ○ | — | DIRECT | 주문○ | |
| 5 | 저장배 | ○ | ○ | PACK | ○ | ○ | ○ | STOCK | 3A○ | |
| 6 | 배즙 재고 | — | — | — | ○ | ○ | ○ | STOCK | 재고조회○ | |
| 7 | 배즙 주문생산 | — | ○ | PROC | △ | ○ | — | A안 | — | PROCESS |

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
경매는 **출하 묶음**으로 여러 상품행을 한 번에 보낸 뒤 확인·확정한다.

---

## 13. 개발단계와의 관계

운영 표기: [01 §7](./01_overview.md) · [06](./06_development_progress.md).

- **5A (=3A) 배정 Core** · **3 (=H) 수확** · **4 (=P) 생산** · **5B 재고조회** · **5C 출고** = 구현·운영 반영 이력은 [06](./06_development_progress.md).
- 생산모델(전량 IN, alloc 비강제)과 5A **충돌 없음**.
- **후속 설계·구현 후보:** 수확잔량·HARVEST N:M 소진이력 · 경매 출하중·청과확인·확정(**DEC-036/037**) · OPEN 정책(§23).
- 본 문서 개정만으로는 코드/DDL을 실행하지 않는다.

---

## 14. Stage 5B 재고 계산 SSOT

Mobile/PC는 수량을 **재계산하지 않는다.** Core/Server가 내려준 값을 동일 기준으로 표시한다.

```
real_qty      = in_qty - out_qty                    # 현재고
reserved_qty  = t_stock_master.reserved_qty         # 주문 배정 (HOLD) — 경매 출하중 아님
```

**가용재고(개념):** 새로 배정·판매·경매 넘기기에 쓸 수 있는 수량.
주문 HOLD(`reserved`)뿐 아니라 **유효한 경매 출하중 수량도 제외**한다.

```
available_qty = real_qty - reserved_qty - (유효 출하중 집계)   # 개념식 · 물리 컬럼/SQL 미확정
```

| 용어 | 의미 |
|------|------|
| 현재고 | `real_qty` — HOLD·출하중과 별개로 “창고에 잡힌” 수량 축 |
| 배정 | `reserved_qty` — **주문** 예약만. **실제 OUT 아님** · **경매 출하중 아님** |
| 출하중 | 경매 넘기기 후·판매확정 전. **출하 라인 집계** ([§14.1](#141-가용과-출하중)) |
| 가용재고 | 배정·판매·경매 출하에 새로 쓸 수 있는 수량 |

배정 예: 현재 30 · HOLD 10 → 배정 10 · (출하중 0이면) 가용 20.
~~SUPERSEDED: `available = real − reserved`만으로 충분하다는 기존 암시~~ — [부록](#부록-superseded--현행-코드-스냅샷).

### 14.1 가용과 출하중

| 규칙 | 내용 |
|------|------|
| 출하중 SSOT | **출하 묶음 + 라인** (개념). `transit_qty` 단독 SSOT **금지** |
| 출하중 수량 | **유효한 출하 라인**의 출하(또는 정책상 집계 기준) 수량 **합** |
| `reserved_qty` | 주문 HOLD만. 출하중과 **분리** |
| 출하 시 `out_qty` | **증가시키지 않음** |
| 판매확정 | 출하중 종료 + **판매 OUT** (`out_qty+`, DEC-027) |

물리 스키마·상태값은 [OPEN-DDL](#23-open-정책) · [OPEN-SHIP-STATE](#23-open-정책).

---

## 15. 재고 종류 · natural key

`t_stock_master` 자연키 (생산 IN · 재고조회 · allocation 동일):

`farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt`

| 유형 | `item_cd` | 사용자 식별 개념 | 표시 예 |
|------|-----------|------------------|---------|
| 원물 | `FR010300` | farm + 창고 + item + 품종 + 원물구분(`size_cd`) + harvest_year + storage_dt | 신고 · 중과 · 2025-10-01 · 가용 240통 |
| 상품 | `FR010100` | farm + 창고 + item + 품종 + 포장중량 + 과수(`size_cd`) + 등급 + harvest_year + storage_dt | 신고 · 15kg · 25과 · 특 · 가용 20박스 (현재 30 · 배정 10) |
| 배즙 | `FR010201`/`FR010202` (+레거시 `FR010200`) | 동일 키. 사용 단위 **박스** (DEC-024). 완제품별로 재고 분리 | 배즙 탭 · 현재/배정/가용 |

필드 의미:

| 키 | 상품 | 원물 |
|----|------|------|
| `weight` | 포장중량. 비교는 `ABS(weight-?)<1e-9` | 원물 중량(CT01 경로 20kg 등) |
| `size_cd` | 과수 공통코드 (`FR02…`) | 원물구분(대/중/소/혼합 등) |
| `grade_cd` | 공통 등급코드 | 원물 등급(해당 시) |
| `harvest_year` | **원료 과실 수확연도** (DEC-026) | 원물 수확연도 |
| `storage_dt` | 상품은 생산/입고일 | 원물 입고일 |

Production IN · GET fruit-stock · allocation FIFO는 위 키를 **같은 의미**로 쓴다.
수확 상자 소진이력에 상품 natural key를 **중복 저장하지 않는** 방향을 권한다.

---

## 16. 생산 ↔ 재고 · 복수 원물 / 복수 수확 (Stage 4/5B+) — **IMPLEMENTED IN GIT**

동일 Production TX (`ProductionService.confirm`, `BEGIN IMMEDIATE` 1회) — **OPERATIONAL PASS** (PC·Lightsail).

| 조합 | 원물/수확 소진 | 결과 IN |
|------|:--------------:|:-------:|
| PACK + RAW_STOCK | 원물 **N건** OUT | 상품 결과 N건 IN |
| PACK + HARVEST | **수확 상자 소진이력** (stock OUT 아님) | 상품 결과 N건 IN |
| PROCESS + RAW_STOCK | 원물 OUT | 배즙 IN (박스) |
| PROCESS + HARVEST | **미지원** (Core `HARVEST_PROCESS`) | — |

### 16.1 RAW_STOCK 복수 투입

한 생산에서 원물 N건 사용 가능. 행 사용수량 빈값 또는 0 = **이번 생산 미사용**. `qty > 0`만 실제 투입.

Mobile payload: `raw_consumptions`에 `qty > 0`인 row만 포함.
예: 대과 30 · 중과 0 · 소과 60 · 혼합 빈값 → 대과30 + 소과60 두 건만 전송.

**주의:** RAW_STOCK N건 = **원물 lot**. HARVEST 복수 = **수확 work** — 축이 다르다.

### 16.2 TX / rollback

투입 소진(원물 OUT 또는 수확 소진이력) + 상품 IN을 **한 TX**. 하나라도 실패하면 **전체 rollback**. 부분 성공 금지.

### 16.3 정합 (Core 검증, Mobile만 의존 금지)

한 생산확정에서 투입의 `variety_cd` · `harvest_year`가 **모두 동일**해야 한다 (DEC-026).

허용: 신고 중과/2026 + 신고 소과/2026.
차단: 신고/2026 + 원황/2026 (`MIXED_VARIETY`).
차단: 신고/2025 + 신고/2026 (`MIXED_YEAR`).
HARVEST 복수 선택 시에도 **동일 품종·동일 수확연도**만 허용.

### 16.4 HARVEST 복수 · 부분소진 — **OPERATIONAL PASS**

**현재 운영 흐름 (CURRENT):**

```
수확기록 N건 선택
→ 행별 부분사용 (harvest_consumptions[])
→ t_harvest_consumption N행 INSERT
→ 상품재고 전량 IN (DEC-023)
→ t_stock_log ref_type=PRODUCTION · ref_id=prod_confirm_id
→ valid consumption SUM(is_valid=1)으로 remaining 재계산
```

**유지:** N:M · partial consumption · same variety · same harvest_year · overconsume reject · `BEGIN IMMEDIATE` · **DONE ≠ remaining 0**.

**업무 흐름 (git `main`):**

```
8/27 수확 30 · 8/28 수확 40
8/29 생산 A: 27→20, 28→15
8/30 생산 B: 27→5,  28→10
→ 잔량 27=5, 28=15
```

| 항목 | 정책 |
|------|------|
| 선택 | **복수** 수확기록 (체크) |
| 입력 | 각 수확별 **사용 상자수**만. lot/`work_id` 사용자 입력 금지 |
| 표시 | 수확량 / 사용량 / **남음** |
| 잔량 | §0.2 공식. 남음 > 0 → 다음 포장 재사용 |
| TX | 소진이력(3축) + 상품 **전량 IN** 동일 TX |
| stock | 수확 상자 → `t_stock_master` OUT **없음** (DEC-022) |
| TX | `BEGIN IMMEDIATE` · consumption + 상품 **전량 IN** + `ref_type=PRODUCTION` 동일 TX |
| overconsume | TX 내 잔량 재검증 · **reject** |
| production trace | `t_stock_log.ref_type='PRODUCTION'` · `ref_id=prod_confirm_id` |
| DONE | **잔량 SSOT로 쓰지 않음** · `DONE ≠ remaining 0` ([OPEN-DONE](#23-open-정책)) |
| OPS | PC·Lightsail 운영 DB DDL **APPLIED** · **OPERATIONAL PASS** |

**Client:** Mobile `PackProdPanel` · PC `stock_page` — 복수 선택 + 행별 `harvest_consumptions[]`. legacy `harvest_work_id` only **reject**. Lightsail PWA **`4daae03`** **OPERATIONAL PASS**.

**SUPERSEDED:** 단일 HARVEST · 소진이력 없음 · `work_ids: []` only — [부록](#부록-superseded--현행-코드-스냅샷).

---

## 17. harvest_year (DEC-026)

**의미:** 이 상품이 **몇 년산 과실에서 생산되었는가**. 생산(포장)연도가 아니다.

| 경로 | 상품/결과 `harvest_year` |
|------|--------------------------|
| RAW_STOCK | 투입 원물 `harvest_year` **승계** |
| HARVEST | 선택 수확기록(들)의 `work_dt` 연도 — **동일 연도만** (§16.3) |
| PROCESS | 원물 `harvest_year` 승계 |

주문 `t_order_detail.harvest_year`도 같은 의미 — allocation이 이 연도로 stock을 탐색한다 (DEC-018).

**업무 전제:** 배 재고는 일반적으로 1년 이상 장기보관하지 않는다. 다년도 rollover · 연도 혼합 생산 UI는 **설계하지 않는다.**

---

## 18. 생산확정 이후

```
(소진이력 / RAW OUT) / PRODUCT IN  →  COMMIT   ← 이 시점에 생산·재고(상품) 처리 완료
```

| 버튼 | 의미 |
|------|------|
| [재고로 저장] | 별도 DB 저장 **없음**. 화면 종료/reset |
| [바로 판매] | 생산결과 N건 `salesPrefill` + 판매 탭 이동 |

경매로 보내는 경우: 상품재고에서 **[경매 넘기기]** ([§2.3.1](#231-경매출하--출하중)).

---

## 19. 재고관리 UX (Stage 5B)

재고는 사용자가 다시 기록하는 기능이 **아니다.** OPS가 기존 업무 TX 결과를 자동 집계해 보여준다.

금지: 수동 재고 수정 · 임의 IN/OUT · 재고 삭제 · 재고수량 수기 입력.

제공: 현재고 · 배정 · **가용** · (후속) **출하중** · 원물/상품/배즙 · 수확잔량 조회(후속) · 소진 포함 필터 · 재고 이력.

화면: 판매관리 상단 **포장/생산 | 재고 | 주문 | 판매**. 재고 내부 **원물 | 상품 | 배즙**.
기본: 소진재고 숨김 (`include_zero=false`). 옵션: 소진 포함.
재고 탭 진입 시 최신 fruit-stock 재조회.

---

## 20. 재고 이력 (`t_stock_log`)

read-only. 현재 유형: IN · OUT · HOLD · CANCEL_HOLD / RELEASE 계열.

| io_type | 사용자 표현 (5B) | 주의 |
|---------|------------------|------|
| IN | 생산입고 | |
| OUT + remark 원물 사용 | 원물사용 | |
| 기타 OUT | 출고 | **OUT = 항상 원물사용이 아님** · **경매 출하중 아님** |
| HOLD | 주문배정 | 실제 출고 아님 · 경매 출하중 아님 |
| CANCEL_HOLD | 배정해제 | |

Stage 5C 이후 상품 OUT = **판매출고**.
**수확 상자 소진 SSOT로 `t_stock_log`만 쓰지 않는다** ([§0.2](#02-수확잔량--소진이력)).

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

`OrderShipService.confirm()` **구현**. HTTP `POST /api/v1/farms/{farm_cd}/shipments/confirm`. `stock_seq`는 Client가 고르지 않음.

**경매와의 분리:**
DEC-027의 **판매 OUT**은 **판매확정** 시점. 경매 **출하중**은 OUT/`reserved`가 아니다 ([§2.3.1](#231-경매출하--출하중)). 경매 판매확정 TX = **[DEC-037](./07_decisions.md)** (DEC-010 SUPERSEDED · 원자성 승계).

---

## 22. DEC 영향 맵 (이번 개정)

본 절은 **문서상 영향 표시**만 한다. DEC **상태·`07_decisions.md`는 변경하지 않는다.**

| DEC | 본 문서에서의 취급 |
|-----|-------------------|
| **DEC-021** | **유지** — UX 최우선 · 내부키 비노출 · 일괄 선택 |
| **DEC-022** | **유지** + **확장** — 자동 IN 금지 · 상자 단위 · **수확잔량/소진 추적** |
| **DEC-023** | **유지** — 상품 **전량 IN** |
| **DEC-026** | **유지** — 동일 품종 / harvest_year |
| **DEC-025** | **보완 DEC 검토 후보** — `t_production_*` 풀세트 금지는 유지. **최소 소진이력·최소 출하 묶음/라인** |
| **DEC-010** | **SUPERSEDED** — DRAFT→CONFIRMED+OUT 단일 TX. 후계 **DEC-036**(출하) / **DEC-037**(판매확정+OUT 원자성) |
| **DEC-027** | **유지 + 분리** — 판매확정 OUT. 출하중≠out/reserved |

---

## 23. OPEN 정책

확정 사항과 **섞지 말 것**.

| ID | 내용 |
|----|------|
| **OPEN-QTY-DIFF** | 출하수량 ≠ 청과확인수량일 때 감모·반입·정정·회계 처리 |
| **OPEN-DONE** | HARVEST `DONE`의 최종 의미 (잔량 SSOT로 쓰지 않음은 확정) |
| **OPEN-SHIP-STATE** | 출하중 / 확인 / 매칭 / 확정 등 **상태값** 목록 |
| **OPEN-DDL** | **경매** 출하 헤더/라인 **물리 스키마**. DEC-035 consumption = design **CLOSED** · **OPS APPLIED** |
| **DEC-016** | 경매 확정 시 `t_sales_delivery` 생성 여부 (기존 OPEN 유지 · [07](./07_decisions.md)) |

> **HISTORY — SUPERSEDED (OPEN 아님):** **DEC-010** — `AUCTION_RT DRAFT→CONFIRMED+OUT` 단일 TX. **2026-08-27** 후계 **DEC-036/037**로 전환 완료.

---

## 부록. SUPERSEDED / 현행 코드 스냅샷

추적 가능성을 위해 **삭제하지 않고** 표시한다.

| 구분 | 내용 |
|------|------|
| SUPERSEDED | 「생산/재고 범위 재설계 없음」(구 머리말) |
| SUPERSEDED | HARVEST = **단일** + 소진이력 없음 + legacy `harvest_work_id` (pre-DEC-035-C) |
| **OPERATIONAL PASS** | HARVEST N:M · `harvest_consumptions[]` · `t_harvest_consumption` · PC/Mobile · Lightsail **`4daae03`** |
| 현행 코드 | `save_realtime_auction_draft`: `t_sales_*` DRAFT+AUCTION_RT · 재고 미접촉 · `stock_seq` 없음 |
| 참고 | DEC-025 **상태**는 SUPERSEDED로 바꾸지 않음 — §9·§22의 「보완 검토」표현만 사용 |
