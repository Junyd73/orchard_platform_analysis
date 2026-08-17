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

PUT: `stock_status=Y` → 409.  
cancel: 출고 전만. 배정분 CANCEL_HOLD + allocated 0 + 주문상태 취소. 판매 있으면 409.

---

## 4. 재고배정 — allocated + reserved + log 동일 TX

| method | path |
|--------|------|
| POST | `/farms/{farm_cd}/orders/{order_no}/allocations` |
| POST | `/farms/{farm_cd}/orders/{order_no}/allocations/release` |

배정 요청: `{ "order_detail_id", "qty": 30 }` (증분).

**동일 트랜잭션:**

1. 줄 잠금/재조회: `allocated_qty + qty <= 주문 qty`
2. **가용재고 재조회** (`in-out-reserved`) — 요청 > 가용이면 rollback 400/409
3. `allocated_qty +=`
4. `reserved_qty +=` (Hold 키 = 생산과 동일 자연키, item/weight/wh 포함)
5. `t_stock_log` HOLD

배정해제: `allocated_qty −`, `reserved_qty −`, log CANCEL_HOLD. 미출고분 초과 해제 금지. 동일 TX.

단계 3 전 DDL 없으면 이 API를 **구현하지 않음**.

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

**한 트랜잭션 (실패 시 전부 rollback):**

1. 배정·미출고분 검증 (`ship_qty <= allocated - shipped`)
2. `reserved_qty −`
3. `out_qty +`
4. stock log OUT
5. `stock_status` (전량이면 Y), 주문상태(DEC-011 후)
6. `t_sales_master` (`ORDER`+`CONFIRMED`, `order_no`, `sales_dt` ISO)
7. `t_sales_detail` (`order_detail_id`)
8. 주문 `sales_no` 연결
9. `t_sales_delivery`
10. `pre_pay_amt>0`이면 같은 TX에서 수금 바구니 + `sync_ledger_by_basket` (DEC-009). 선수금 계정 아님.

금지 결과: 재고만 감소 / 판매만 생성 / 주문 완료·판매 없음.

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
| 배정 | allocated + reserved + HOLD log + 가용 재검증 |
| 배정해제 | allocated − + reserved − + CANCEL_HOLD |
| 소매 출고 | reserved/out/log + 판매 생성 + 연결 + 배송 + (선입금 시 전표) |
| 가락 확정 | status + out/log + 선택 전표 |
| 수금만 | cash + ledger + totals |
| 주문 취소(출고 전) | 상태 + 잔여 Hold 해제 |

---

## 11. FastAPI 현황 (재확인)

`router.py`: health, farms, observations*, pesticide, smart_spray, work_logs, weather, work_photos, work_schedules(410), google_calendar, notifications, common_codes.

**orders/sales/customers/fruit-stock 없음.**
