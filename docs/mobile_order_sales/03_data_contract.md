# 03. Data contract — 기존 테이블

> 상태: 단계 0 **최종승인 완료**. ALTER/migration은 단계 3 이전 금지.  
> DDL은 저장소에 거의 없음. INSERT/UPDATE, `docs/판매관리테이블 생성.txt`, `server/docs/sqlite_schema_baseline.md` 기준.  
> 문서와 코드가 다르면 **코드 우선**.  
> **이번 작업에서 ALTER/migration 하지 않음.**

운영 DB에 테이블 존재 (baseline):  
`t_order_master/detail/delivery`, `t_sales_master/detail/delivery`, `t_stock_master/log`, `t_cash_ledger`, `t_ledger`, `m_customer`, `m_warehouse`, `m_item_unit_price`, `m_common_code`.

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
| season_type_cd | SS01 | 시즌 | 콤보 | 유지 |
| sales_no | Stage 2 신규는 빈 값 | **legacy/reference.** 출고 전 비움. 이후 최초 출고 판매번호만. **주문 전체 판매 조회는 반드시 `t_sales_master.order_no` 기준.** | | DEC-005 · **017 APPROVED** |
| rmk, reg_id, reg_dt, mod_* | 감사 | `now_ops_str` | 동일 | 유지 |

출고예정일 마스터 컬럼 **추가하지 않음.** `MIN(t_order_delivery.planned_dt)`.

---

## 2. `t_order_detail`

| 컬럼 | 사용 | 의미 | 모바일 | 수정 |
|------|------|------|--------|------|
| order_detail_id | `{order_no}-{NN}` | 줄 PK. 판매 상세 연결키 | 필수 | 유지 |
| item/variety/grade/size_cd, weight, qty, unit_price, item_amt | 규격·**주문수량** | DEC-004 | 필수 | 유지 |
| harvest_year | 있음 | 선주문 시 생산연 | 유지 | |
| wh_cd | 있음 | 기본 WH01 | 유지 | |
| dlvry_tp | LO01 | 행별 배송 | 유지 | |
| **allocated_qty** | **없음 (설계 확정)** | **누적 배정수량** (Hold 잔량 아님) | 목록의 「배정」 | DEC-008. migration은 단계 3 |

**계산값 컬럼을 추가하지 않음.**

```
unallocated_qty        = qty - allocated_qty
shipped_qty            = SUM(t_sales_detail.qty WHERE order_detail_id = 이 줄
                             AND 해당 판매 sales_status = CONFIRMED)
reserved_unshipped_qty = allocated_qty - shipped_qty
0 <= shipped_qty <= allocated_qty <= qty
release_qty            <= allocated_qty - shipped_qty
```

판매 상세에는 `harvest_year`가 **없다.**

### 2.1 `allocated_qty` 설계 (DEC-008 APPROVED, DDL 미실시)

| 항목 | 권장안 |
|------|--------|
| 의미 | 해당 주문상세에 지금까지 확정된 **누적 배정수량** |
| 타입 | `qty`와 동일 계열 → **`REAL NOT NULL DEFAULT 0`** |
| 신규 주문 | 0 |
| 출고 후 | **유지**. 0 리셋 금지 |
| 배정해제 | `allocated_qty − release_qty`. 미출고분 초과 금지 |
| 줄 vs 행 | 총량만 저장. 행 분해는 가칭 `t_order_alloc` (DEC-018 APPROVED, CREATE 금지) |

기존 주문 초기값: **무조건 0 금지** (DEC-015 OPEN). 이미 `reserved_qty` HOLD가 있으면 0이면 이중 배정·미배정 오인.  
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
| sales_tp | RETAIL/WHOLE | 주문 `'NORMAL'` | 정리 제안, 1차 비범위 가능 |
| sales_status / sales_source | 문서 없음 | ALTER 후 사용 | DRAFT/CONFIRMED, ORDER/AUCTION_RT 유지 |
| order_no | 문서 없음 | 주문 INSERT만. **재저장 시 누락**. UNIQUE 없음 | 출고마다 동일 `order_no` 가능 → **주문 1:N 판매 SSOT** (DEC-017). 재저장 보존 |
| slip_no | 문서 있음 | 판매 INSERT 없음 | 전표는 `t_ledger` |

채번: `generate_sales_no` vs 주문 `get_next_seq` 이중 → P0 공통화.

---

## 5. `t_sales_detail`

문서: `delivery_tp`. 코드: **`dlvry_tp`**.  
주문 INSERT: `order_detail_id`, `wh_cd`.  
판매화면 `execute_full_save`: **`order_detail_id` 없음**. 경매: `crop_nm`. **harvest_year 없음.**

`shipped_qty` = 이 컬럼이 채워진 판매상세 `qty` 합. 재저장이 키를 지우면 계산이 깨짐 → P0 `order_detail_id` 보존.

부분출고: 같은 `order_detail_id`가 **여러 `sales_no`**에 나타날 수 있다 (DEC-017). 기존 판매를 후속 출고 때 수정하여 수량을 증가시키지 않는다.

---

## 6. `t_sales_delivery`

문서명 `t_delivery_detail`. **실제 `t_sales_delivery`.**

| 경로 | dlvry_no |
|------|----------|
| 주문 저장(현재) | `{sale_detail_no}-P..-D{NNN}` |
| 판매 화면 | `{sales_no}-D{NNN}` |
| 규칙 (4.mdc) | `{sale_detail_no}-D{NNN}` |

설계: 출고 TX에서 **해당 출고분만큼만** 생성. 주문 저장 시에는 만들지 않음 (DEC-005). 주문 배송계획 전체 복제 금지 (DEC-017).

---

## 7. `t_stock_master`

키(생산 UPSERT):  
`farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt`

| 컬럼 | 의미 | 설계 |
|------|------|------|
| in_qty | 입고 누적 | 유지 |
| out_qty | 출고/폐기/원물소모. **판매 출고 미사용** | 출고확정 시 + |
| reserved_qty | 현재=주문 전량 Hold | **미출고 배정분** (`reserved_unshipped`의 행 합). 출고 시 − |
| available | SELECT 추정 생성컬럼 | `in-out-reserved` |
| harvest_year | 상품=생산연 | 주문 상세와 매칭 |
| storage_dt | 바구니 | 자동배정 FIFO `storage_dt ASC` (DEC-018). 동일일은 기존 자연키/row 정렬 |
| wh_cd | WH01 하드코딩 | 1차 유지 |

가용: `SUM(in_qty-out_qty) - SUM(reserved_qty)`.

Hold UPDATE WHERE에 `item_cd`/`weight`/`wh_cd` 누락 (2933행) — P0.

원물 입고 UPDATE `variety_cd` 누락 — 이번 비범위(C), 위험만 명시.

배정 API는 **같은 트랜잭션 안에서** 가용수량을 다시 읽고 `request <= available`일 때만 `reserved_qty +=`. 동시 복수 주문 초과예약 방지.

---

## 8. `t_stock_log`

실값: `IN`, `OUT`, `AUDIT`, `HOLD`, `CANCEL_HOLD`.

주문 HOLD/CANCEL_HOLD INSERT 컬럼 (코드):  
`farm_cd, item_cd, variety_cd, harvest_year, grade_cd, size_cd, weight, io_type, qty, (parent_raw_size HOLD만), remark, reg_id, reg_dt`

| 필드 | 주문 로그 | 판정 |
|------|-----------|------|
| wh_cd | 없음 | row 식별 불가 |
| storage_dt | 없음 | row 식별 불가 |
| order_detail_id / ref_id | 없음 | remark `주문예약:{order_no}`만 |
| 판매출고 OUT | 없음 | 생산/폐기 OUT만 |

**`t_stock_log`는 allocation 현재상태 SSOT가 아니다** (DEC-018). 현재상태 복원은 `t_order_alloc`, 감사 이력은 본 로그.

현재 로그에 부족한 `wh_cd`/`storage_dt`/`order_detail_id`를 allocation SSOT 목적으로 억지로 추가하지 않는다. 앞으로 생성되는 HOLD / CANCEL_HOLD / OUT에는 가능한 범위에서 `order_no`, `order_detail_id`, `sales_no`, stock 자연키를 남기는 방향을 설계할 수 있다.

| 이벤트 | io_type |
|--------|---------|
| 배정 | HOLD |
| 배정해제 | CANCEL_HOLD |
| 출고확정 | OUT (가능한 범위에서 판매번호·줄·자연키) — **신설 계약** |

신규 io_type 문자열 남발 금지.

---

## 9. `t_cash_ledger` / `t_ledger`

판매 CONFIRMED 수금만. 문서명 `t_sales_pay_detail`과 다름. **코드 테이블명 우선.**

주문 선입금은 **안 넣음** (DEC-009).  
판매 삭제 시 `t_ledger` 미처리 — P1, 1차 DELETE 비활성.

`ref_id` ≈ `SALE-{sales_no}-…`, `trans_type_cd='REVENUE'`. 회계 엔진 개편은 C.

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
    │     order_detail_id ──→ t_sales_detail.order_detail_id  (출고마다 N건 가능)
    ├─ t_order_delivery
    ├─ t_order_alloc (가칭) ── 줄 ↔ stock 자연키 현재상태
    └─ t_order_master.sales_no ──→ legacy/reference (최초 출고 또는 대표 참조)
         전체 판매 조회: t_sales_master.order_no = 주문번호 (1:N SSOT)

t_stock_master.reserved_qty  ↔  t_order_alloc 미출고분 합 (행 단위)
t_stock_log                  =  HOLD / CANCEL_HOLD / OUT 이력 (현재상태 SSOT 아님)
t_order_master.stock_status  =  전량 출고 시만 Y
```

| 필드 | 현재 | 확정 설계 |
|------|------|-----------|
| reserved_qty | 주문 전량 Hold | 미출고 배정분. 출고 시 − |
| out_qty | 판매출고 없음 | 출고 TX에서 + |
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
| `t_order_detail.allocated_qty` | **설계 확정.** migration은 단계 3 |
| `unallocated_qty` / `shipped_qty` 컬럼 | **하지 않음** (계산) |
| `t_order_alloc` (가칭) | **설계 확정** (DEC-018). **CREATE TABLE 금지.** 실제 테이블명·PK/UNIQUE는 구현 전 schema 대조 |
| `t_stock_log` 컬럼 추가 | **하지 않음** (allocation SSOT 목적). 향후 이력 식별정보만 설계 가능 |
| `t_order_master.plan_ship_dt` | 하지 않음 (`planned_dt` 계산) |
| `t_sales_detail.harvest_year` | 하지 않음 (주문 조인) |
| 이행상태 컬럼 | 하지 않음 (계산) |
| 주문↔판매 연결 새 컬럼 | **하지 않음.** SSOT는 기존 `t_sales_master.order_no` + `t_sales_detail.order_detail_id` |

### 12.1 `t_order_alloc` 최소 데이터 계약 (CREATE 금지)

```
order_no
order_detail_id
farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd,
weight, harvest_year, storage_dt   -- t_stock_master 자연키
allocated_qty
shipped_qty
생성/수정 감사정보
```

`allocated_qty - shipped_qty` = 그 행 Hold 잔량.  
PK/UNIQUE는 구현 전 실제 schema와 대조하여 확정. 이번 작업에서 CREATE TABLE 금지.

---

## 13. `allocated_qty` migration 계획 (실행 금지 · 문서만)

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

**원칙:** 배정·출고 서비스는 BEGIN(가능하면 IMMEDIATE) 후 가용/배정수량을 **다시 SELECT** 하고 조건 불일치 시 rollback.

---

## 15. 구현/migration 직전 운영 DB 점검 (read-only)

이번 문서 작업에서는 운영 DB에 **접근하지 않음.** 실행은 단계 3·4 직전.

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
