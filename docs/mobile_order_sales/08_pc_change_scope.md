# 08. PC 변경 범위

주문/판매 P0 + **재고/생산은 StockPage 유지·확장** (전면 교체 금지).  
생산/재고 SSOT: [09_production_inventory_flow.md](./09_production_inventory_flow.md) · PC: `ui/pages/stock_page.py`.

## 재고/생산 (PC 현재 — 폐기 금지)

| 기능 | StockPage | 비고 |
|------|-----------|------|
| 원물 등록 | `register_raw_material` | FR010300 IN |
| 생산확정 | `save_production_log` | 원물 OUT + FR010100 IN + 수율 |
| 상품 실사 | `audit_product_stock` | AUDIT 로그 |
| 폐기 | `dispose_raw_material` | |
| 작업 완료 | `t_work_detail` DONE | 생산확정 TX |

**확장(후속 P+S):** 생산→바로판매 A안 · 전량 IN 후 판매 OUT (OPEN-PROD-03 **CLOSED**). **이번 작업 DDL 없음.**

---

## P0 반드시 수정 (단계 승인 후)

기능 기준으로 재정리. 상세 표는 아래 A절.

| # | 항목 | 현재 | 확정 설계 |
|---|------|------|-----------|
| 1 | 주문 저장 시 판매 자동생성 제거 | `save_entire_order`가 `t_sales_*` INSERT | 주문 3테이블만 (DEC-005) |
| 2 | `allocated_qty` | 컬럼 없음 | **누적 배정** (DEC-008) |
| 3 | 부분배정 | 전량 Hold | qty와 allocated 분리 |
| 4 | Hold key 정합성 | WHERE에 item/weight/wh 없음 | 생산 UPSERT와 동일 자연키 |
| 5 | Hold 해제 | 수정 시 규격키만, `storage_dt` 없음 | 미출고 lot CANCEL_HOLD |
| 6 | 출고확정 | **없음** (부분출고 미지원) | OrderShip TX (DEC-014) |
| 7 | reserved→out | out 불변 | 출고 시 reserved− out+ |
| 8 | stock_status | Y 세팅 없음 | 전량 출고만 Y. 부분출고 N |
| 9 | 판매생성 | 주문과 동시에 1건 | 출고 시점. **출고 1회 = 판매 1건** (DEC-017) |
| 10 | order_no / order_detail_id 보존 | 재저장 누락 | INSERT에 유지. 전체 조회 SSOT = `t_sales_master.order_no` |
| 11 | DRAFT→CONFIRMED | 버튼 없음 | confirm TX (DEC-010) |
| 12 | 신규 날짜 YYYY-MM-DD | 주문 YYYYMMDD | DEC-012 |
| 13 | 채번 공통화 | `get_next_seq` vs `generate_sales_no` | core만 |
| 14 | 재고행 allocation | MIN(storage_dt) + 로그에 row키 없음 | 가칭 `t_order_alloc` (DEC-018). FIFO 배정/출고, LIFO 해제 |
| 15 | 수금/회계 공용화 | `sales_page.execute_full_save` 안에 `t_cash_ledger` INSERT + slip 매핑이 페이지에 있음 | PC와 모바일이 **같은 AccountManager Core 경로**를 쓴다 (DEC-007 · DEC-029). 페이지별 회계 SQL 복제 금지 |
| 16 | 수금상태 표현 | 미수 표시가 화면 로컬 계산·색상 로직 | `tot_paid_amt`/`tot_unpaid_amt` 기준 계산 규칙 통일 (DEC-029). `sales_status`에 수금 의미 넣지 않음 |
| 17 | 선입금 결제수단 | `t_order_master`에 컬럼 없음 | `pre_pay_method_cd` 제안 (DEC-028). **DDL 미실행** |
| 18 | 출고확정 CONFIRMED read-only | PC `execute_full_save`가 출고 판매도 재저장 | DEC-031: CONFIRMED + 추적키 → read-only · **Stage7A private main · 운영 미배포** |

P1: 판매 삭제 시 `t_ledger` (1차는 삭제 비활성).  
P2: 배송 팝업 키 `delivery_qty` vs `dlvry_qty`, `load_existing_data` 주석화.

단계 2에서 반영: A1 판매 분리, A8 신규 날짜 ISO, A9 `generate_order_no`, A11 신규 `ST010100`.  
Hold 키·allocated·출고 TX는 단계 3–4.

---

## A. 상세 (현재동작 / 문제 / 권장 / 영향)

### A1. 주문 저장 시 판매 자동생성 — P0

| | |
|--|--|
| 현재 | 같은 TX에 `t_sales_master/detail/delivery` INSERT |
| 문제 | 선주문·부분배정·회계 시점과 충돌. 운영에 이미 판매 연결된 주문 존재 가능 |
| 권장 | 주문만 저장 |
| 모바일 | 복제 금지 |
| DB | 신설 없음. `sales_no` NULL 허용 |
| 회귀 | **높음** |

### A2–A3. 부분배정 · allocated_qty · Hold/출고 — P0

| | |
|--|--|
| 현재 | 전량 reserved +=. allocated 없음. out 불변 |
| 문제 | 100/30/70 불가. 가용 왜곡 |
| 권장 | 배정 TX / 출고 TX. `allocated_qty`는 누적 유지. 행 추적은 `t_order_alloc` (DEC-018) |
| DB | allocated_qty는 단계 3 ALTER만 |
| 회귀 | 기존 HOLD와 초기값 충돌 (DEC-015) |

### A4. Hold key — P0

UPDATE WHERE에 `item_cd`, `weight`, `wh_cd` 추가. 타 품목 오염 방지.

### A5. stock_status — P0

출고완료 시 `'Y'`. 부분 출고는 `'N'` + 이행상태 계산.

### A6. DRAFT 확정 — P0

PC·API 공통 confirm. 재고+CONFIRMED 한 TX. 운영 DRAFT 건수 점검 후 일괄 확정 금지.

### A7. order_no 유실 — P0

`execute_full_save` INSERT에 `order_no` 포함.

### A8. 날짜 — P0

신규 `order_dt`/`sales_dt` ISO. 읽기 파서. 일괄 UPDATE 금지.

### A9. 채번 — P0

`generate_order_no` 신설. 판매는 `generate_sales_no`만. 페이지 로컬 SEQ 폐기.

### A10. 삭제 시 전표 — P1

현재 delivery/cash/detail/master만 DELETE. 1차 삭제 버튼 비활성.

### A11. status_cd 미저장 — P1 / DEC-011 CLOSED

UI ST01, 신규 INSERT `ST010100` (`OrderService`). `'10'`/`'20'` 저장 폐기. 확정 워크플로 버튼은 Stage 2 비범위.

### A12. 배송 팝업 키 — P2

모바일 1차와 독립 가능.

### A13. PC SalesPage 수금/회계 공용화 — P1 (DEC-019 · 028 · 029)

| | |
|--|--|
| 현재 | `ui/pages/sales_page.py`가 수금 바구니 구성 · `t_cash_ledger` INSERT SQL · `slip_map` 매핑 · 미수 표시 로직을 **페이지 안에** 갖고 있다. 확인된 INSERT 컬럼: `paid_detail_no, sales_no, farm_cd, pay_dt, pay_method_cd, pay_amt, slip_no, rmk, reg_id` |
| 문제 | 모바일 수금이 생기면 같은 회계 로직이 두 벌이 된다. 규칙이 다시 갈라진다 (DEC-001 · DEC-007) |
| 확정 설계 | PC와 모바일이 **동일한 AccountManager Core 경로**를 공유한다. 수금 저장은 Core 한 곳: 수금액+결제수단 → `t_cash_ledger` → `AccountManager.sync_ledger_by_basket('SALE', …)` → `t_ledger` → `tot_paid_amt`/`tot_unpaid_amt`. 한 TX |
| 금지 | 화면·라우터별 회계 SQL 복제 · **모바일 전용 회계 엔진** · 모바일 전용 결제수단 코드 하드코딩 · DRAFT 판매 수금 (DEC-029) |
| 계정코드 | 결제수단 = **현금성 자산 계정**(실제 운영 코드 재확인 후 범위 확정). 채권(`AS02…`)은 결제수단 아님. 신규 코드 정의·모바일 하드코딩 없음 |
| 수금상태 | 컬럼 신설 없음. `tot_paid_amt`/`tot_unpaid_amt`에서 미수/부분수금/수금완료 계산 (DEC-029) |
| 선입금 | 출고확정 TX에서 `min(선입금 잔액, 판매금액)` 순차 적용 (DEC-019). PC 출고 경로도 동일 규칙 |
| 비범위 | **PC SalesPage 전면 재작성**. 화면 레이아웃·기존 판매 저장 UX는 유지하고 회계 호출부만 Core로 위임 |

### A14. 출고확정 CONFIRMED read-only — P0 (DEC-031 · Stage7A)

| | |
|--|--|
| 현재 | 출고 생성 CONFIRMED 판매도 PC `execute_full_save` DELETE→INSERT 재저장 가능 |
| 문제 | `order_detail_id`/`stock_seq`/`order_no` 정합성 훼손 · 재고·주문 추적 불일치 |
| 확정 | CONFIRMED + (`order_no` \| `order_detail_id` \| `stock_seq`) → read-only. UI disable + save/delete DB backstop |
| helper | `core/pc_sales_provenance.py` — `is_shipment_confirmed_sale_locked` · `assert_sale_mutable` |
| Stage7A | **완료 · private main · 운영 미배포** — protected 판매 수금 버튼 disable + 배송 edit 차단. DEC-032 본구현은 Stage7B |
| 금지 | `order_detail_id` 재INSERT 우회 · protected 판매 partial edit |

---

## B. 공용화 권장 (가칭)

페이지 SQL을 `core/`로 이전. UI·FastAPI는 호출만. **이전이 끝나기 전에 FastAPI에 SQL을 새로 짜지 않는다.**

| 기능 | 현재 위치 | 가칭 |
|------|-----------|------|
| 주문저장 | `save_entire_order` 중 주문만 | OrderService |
| 재고배정 | 없음 (전량 Hold 루프) | OrderAllocationService |
| 배정해제 | 수정 시 reserved 복구 | 동일 |
| 출고확정 | 없음 | OrderShipService |
| 판매생성 | 주문 루프 / `execute_full_save` | SalesService / OrderShip |
| DRAFT 저장 | `save_realtime_auction_draft` | SalesService |
| DRAFT 확정 | 없음 | SalesConfirmService |
| 수금/전표 | `execute_full_save` + AccountManager | **AccountManager 그대로.** PC·모바일 공용 Core 경로 1곳 (A13) |
| 재고 매트릭스 | `StockMatrixPopup.get_stock_map` | StockQueryService |
| 채번 | 이중 | DBManager |
| 고객 | 팝업 | CustomerService |

---

## C. 이번 개발에서 건드리지 않음

- PC 주문/판매 **화면 전면** 재설계 (**PC `SalesPage` 전면 재작성 포함**. A13은 회계 호출부 위임만)
- `t_order_master.pre_pay_method_cd` ALTER (DEC-028 설계만. 운영 PRAGMA 확인 후 별도 승인)
- `t_stock_master_old` / backup 정리, `t_stock_status` 활용
- 과거 주문·판매·날짜 **일괄** 변환
- 저장관리 UX 전면 교체 (원물 UPDATE variety 누락은 후속 티켓)
- `m_warehouse` 실사용 전환
- `t_dlvry_detail` 명칭, AccountManager 80/90 재구현, finance 구스키마
- 관찰·영농일지·농약·시세 수집, 운영 TZ/cron
- 선수금 회계
- 이번 문서 작업에서 `t_order_alloc` CREATE / `t_stock_log` ALTER / `allocated_qty` ALTER

단계 4 출고는 **부분출고 + 출고 1회 = 판매 1건**이 확정 범위다 (DEC-017). 전량 출고만으로 범위를 좁히지 않는다.

---

## 권장 착수 순서 (최종승인 후)

1. core 골격 — 동작 동일 복제 + 테스트 (단계 2 전)
2. A4 Hold 키, A7 order_no, A8 날짜, A9 채번
3. A1 판매 분리 (단계 2)
4. allocated DDL + `t_order_alloc` + 운영 점검 후 배정 (단계 3, DEC-015)
5. 출고 TX (단계 4)
6. 경매 confirm (단계 6)
7. A10 삭제는 막거나 역분개
