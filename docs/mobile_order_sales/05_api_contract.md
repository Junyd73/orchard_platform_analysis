# 05. API contract — 초안

> 상태: 단계 0 · 설계 수정 / 최종승인 대기. 구현 금지.  
> 재검색: **과일 orders/sales/stock/customer/delivery/payment API 없음.**  
> 마운트: `server/app/main.py` → `/api/v1` + `router.py`.  
> PC와 FastAPI가 SQL을 복제하지 않음. `core` 서비스 1곳 (DEC-007).

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
| AccountManager | `sync_ledger_by_basket` (기존) | payment / 출고 시 선입금 복사 |
| DBManager | `generate_sales_no` + **신설** `generate_order_no` | 채번 |

FastAPI 라우터는 위 함수만 호출.

---

## 1. customers

| method | path | 설명 |
|--------|------|------|
| GET | `/farms/{farm_cd}/customers` | `q`, `use_yn=Y` |
| GET | `/farms/{farm_cd}/customers/{custm_id}` | 상세 |
| POST | `/farms/{farm_cd}/customers` | nm, mobile 필수. ID `C`+KST |

TX: 단건 INSERT. core: CustomerService.

---

## 2. stock (과일)

| method | path | 설명 |
|--------|------|------|
| GET | `/farms/{farm_cd}/fruit-stock` | 상품 매트릭스 |

농약 경로와 분리. 조회만. 주문 등록을 막지 않음.  
응답: `real_qty=in-out`, `available=real-reserved`.  
쓰기(입고/선별) 1차 비범위.

---

## 3. orders — 등록은 재고 없어도 성공

| method | path |
|--------|------|
| GET | `/farms/{farm_cd}/orders` |
| GET | `/farms/{farm_cd}/orders/{order_no}` |
| POST | `/farms/{farm_cd}/orders` |
| PUT | `/farms/{farm_cd}/orders/{order_no}` |
| POST | `/farms/{farm_cd}/orders/{order_no}/cancel` |

POST 본문 초안: 고객, `order_dt`(ISO), 시즌, `pre_pay_amt`, lines(규격+`qty`), deliveries.

검증: 고객, 줄≥1, 줄 qty=배송 합, 방문 외 주소. **`available < qty`여도 200.** `warnings[]` 선택.

**TX:** `t_order_master` + `detail` + `delivery`만.  
`allocated_qty=0`. `order_dt` ISO.  
**금지:** `t_sales_*`, `reserved_qty` Hold, `t_cash_ledger`, `t_ledger`.

PUT: `stock_status=Y` → 409. 부분출고(`shipped_qty>0`) 후 주문 헤더/줄 수정은 1차 거부 권고.  
cancel: `shipped_qty>0`이면 409 (출고 전만). 배정분 CANCEL_HOLD는 **`t_order_alloc` 행 단위** (DEC-018). 이미 출고된 allocation은 단순 취소 금지.

---

## 4. 재고배정 — allocated + reserved + log 동일 TX

| method | path |
|--------|------|
| POST | `/farms/{farm_cd}/orders/{order_no}/allocations` |
| POST | `/farms/{farm_cd}/orders/{order_no}/allocations/release` |

배정 요청: `{ "order_detail_id", "qty": 30 }` (증분). 내부적으로 FIFO(`storage_dt ASC`) stock row에 분해 (DEC-018).

**동일 트랜잭션:**

1. 줄 잠금/재조회: `allocated_qty + qty <= 주문 qty`
2. 가용재고를 TX 안에서 재조회 (`in-out-reserved`) — 초과 시 rollback
3. FIFO로 stock row 선택
4. `t_order_alloc` 증가/생성
5. `t_order_detail.allocated_qty +=` (누적)
6. 해당 stock row `reserved_qty +=`
7. `t_stock_log` HOLD (이력. 가능한 범위에서 줄·자연키)

배정해제: `release_qty <= allocated_qty - shipped_qty`. 기본 순서 **LIFO**(최근 잡은 행부터). `t_order_alloc` 감소, `allocated_qty −`, `reserved_qty −`, CANCEL_HOLD. 동일 TX.

단계 3 전 `allocated_qty` DDL 및 `t_order_alloc`이 없으면 이 API를 **구현하지 않음**. 이번 문서 작업에서 CREATE/ALTER 금지.

동시성: SQLite 트랜잭션 안에서 재검증 (위험 9·10).

---

## 5. delivery

주문 생성에 포함. 단독 수정:

| method | path |
|--------|------|
| PUT | `/farms/{farm_cd}/orders/{order_no}/deliveries` |

`t_sales_delivery`는 출고/확정 TX에서만.

---

## 6. 출고확정 — 재고 이동 + 판매생성 단일 TX (DEC-014)

| method | path |
|--------|------|
| POST | `/farms/{farm_cd}/orders/{order_no}/ship` |

요청: 줄별 `ship_qty` 또는 “미출고 배정 전량”.  
`ship_qty <= allocated_qty - shipped_qty`.

**한 트랜잭션 (실패 시 전부 rollback):**

1. 출고 가능한 미출고 `t_order_alloc` 조회
2. FIFO(`storage_dt ASC`) 순서대로 `ship_qty` 배분
3. 각 `t_order_alloc.shipped_qty` 증가
4. 각 stock row `reserved_qty −`
5. 각 stock row `out_qty +`
6. stock log OUT
7. **항상 새** `t_sales_master` (`order_no` 연결, `sales_source=ORDER`, `sales_status=CONFIRMED`, `sales_dt`=출고 업무일). 기존 CONFIRMED 판매·전표 수정 금지
8. `t_sales_detail` (`order_detail_id` 필수, 이번 `ship_qty`만)
9. `t_order_master.sales_no`는 비어 있을 때만 최초 판매번호 기록 (legacy/reference). 전체 조회는 `t_sales_master.order_no`
10. `t_sales_delivery` — 그 출고분만큼만. 주문 배송계획 전체 복사 금지
11. 선입금 전표는 **첫 출고**에만 (DEC-009)
12. 전 줄 `shipped_qty == qty`이면 `stock_status='Y'`

금지 결과: 재고만 감소 / 판매만 생성 / 전량 완료인데 판매 없음 / 기존 판매 수량 증가.

부분출고를 여러 번 호출할 수 있다. 매번 DEC-014 TX + 새 판매 1건 (DEC-017).

---

## 7. sales

| method | path |
|--------|------|
| GET | `/farms/{farm_cd}/sales` |
| GET | `/farms/{farm_cd}/sales/{sales_no}` |
| POST | `/farms/{farm_cd}/sales` |
| PUT | `/farms/{farm_cd}/sales/{sales_no}` |

PUT: 자식 재INSERT 시 **`order_no` / `sales_status` / `sales_source` 보존**. 재고는 ship/confirm만.  
DELETE 1차 비공개 (전표 역분개 전).

직접판매 POST: 출고 포함 플래그 시 재고+판매 한 TX (수출/도매).

---

## 8. payment — 판매확정 기준 수금/회계

| method | path |
|--------|------|
| GET | `/farms/{farm_cd}/sales/{sales_no}/payments` |
| PUT | `/farms/{farm_cd}/sales/{sales_no}/payments` |

검증: `CONFIRMED`만. DRAFT 409.  
TX: cash + ledger + 마스터 tot_paid/unpaid.  
주문 API에서 전표 생성 금지.

출고 TX에 선입금을 이미 넣었으면 이중 전표 주의 — 수금 서비스가 기존 줄을 바구니로 동기화.

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
| 소매 출고 (1회) | alloc shipped+ / reserved− / out+ / OUT log + **새 판매 1건** + `order_no`/`order_detail_id` + 출고분 배송 + (첫 출고 선입금 전표) |
| 가락 확정 | status + out/log + 선택 전표 |
| 수금만 | cash + ledger + totals |
| 주문 취소(출고 전) | 상태 + 모든 미출고 `t_order_alloc` 행별 reserved 복구 |

---

## 11. FastAPI 현황 (재확인)

`router.py`: health, farms, observations*, pesticide, smart_spray, work_logs, weather, work_photos, work_schedules(410), google_calendar, notifications, common_codes.

**orders/sales/customers/fruit-stock 없음.**
