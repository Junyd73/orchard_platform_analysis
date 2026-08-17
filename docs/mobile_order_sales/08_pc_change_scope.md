# 08. PC 변경 범위

구현하지 않음. 공통 규칙에 맞추기 위한 **최소 수정 후보**.  
근거: `ui/pages/order_page.py`, `sales_page.py`, `stock_page.py`, `market_price_page.py`, `core/db_manager.py`, `core/account_manager.py`.

서비스 이름은 **가칭**. 기존 `AccountManager`/`DBManager` 관례를 우선하고 새 아키텍처를 지금 확정하지 않음.  
PC와 FastAPI가 **같은 함수**를 호출한다 (DEC-007).

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

P1: 판매 삭제 시 `t_ledger` (1차는 삭제 비활성). 주문 `status_cd` 실코드 (DEC-011).  
P2: 배송 팝업 키 `delivery_qty` vs `dlvry_qty`, `load_existing_data` 주석화.

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

### A11. status_cd 미저장 — P1 / DEC-011 OPEN

UI ST01, INSERT `'10'`. 실코드 확인 전 신규 코드 추가 금지.

### A12. 배송 팝업 키 — P2

모바일 1차와 독립 가능.

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
| 수금/전표 | `execute_full_save` + AccountManager | AccountManager 그대로 |
| 재고 매트릭스 | `StockMatrixPopup.get_stock_map` | StockQueryService |
| 채번 | 이중 | DBManager |
| 고객 | 팝업 | CustomerService |

---

## C. 이번 개발에서 건드리지 않음

- PC 주문/판매 **화면 전면** 재설계
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
