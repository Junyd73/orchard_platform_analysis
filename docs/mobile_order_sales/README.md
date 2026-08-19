# 주문/판매관리 통합 설계 (ORD-001)

> **상태:** 단계 0 **최종승인 완료** → 단계 1 **완료 / 대표 승인** → 단계 2 **완료 / 대표 승인** (2026-08-19)  
> **갱신:** 2026-08-19 (단계 2 대표 승인 · private main merge. DEC-011 CLOSED. 단계 3 미착수)

PC(PyQt) · core · FastAPI · Vue PWA가 **동일 업무 규칙**을 쓰기 위한 설계다.

## 문서 위치

`docs/mobile_order_sales/`

| 대안 | 사용하지 않은 이유 |
|------|-------------------|
| `mobile/docs/screens/` | 승인된 ODS/SCR SSOT. 아직 SCR ID 없음 |
| 관찰/농약 단일 md | 주문/판매는 PC 변경·migration 조건까지 포함해 분할 |

단계 1–2 화면 명세: `mobile/docs/screens/SCR-030.md` (주문/판매 셸 · 목록/등록).

## 목차

| 파일 | 내용 |
|------|------|
| [01_overview.md](./01_overview.md) | 목적·확정 원칙·범위·단계 |
| [02_domain_flow.md](./02_domain_flow.md) | 선주문·배정·출고 TX·상태 분리·취소 |
| [03_data_contract.md](./03_data_contract.md) | 테이블 계약 · allocated_qty · 운영 점검 SQL |
| [04_mobile_screen.md](./04_mobile_screen.md) | 하단탭·주문/판매·배정 표시 |
| [05_api_contract.md](./05_api_contract.md) | API · 트랜잭션 경계 |
| [06_development_progress.md](./06_development_progress.md) | 단계 게이트 |
| [07_decisions.md](./07_decisions.md) | DEC 로그 |
| [08_pc_change_scope.md](./08_pc_change_scope.md) | PC P0 / 공용 서비스 / 비범위 |

## 대표 확정 (APPROVED) — 2026-08-17

구현 허가와 다름. **설계 규칙**만 확정.

| 대표 | DEC | 요지 |
|------|-----|------|
| DEC-A | 008 | `allocated_qty` 설계 확정. 이번엔 ALTER 안 함 |
| DEC-B | 013 | 주문상태 ≠ 이행상태. 새 코드/컬럼 임의 추가 없음 |
| DEC-C | 010, 014 | 소매 출고·가락 확정은 재고+판매 단일 TX |
| DEC-017 | 017 | 출고 1회 = 판매 1건. 주문 1 : 판매 N |
| DEC-018 | 018 | `t_order_alloc` 행 배정. FIFO 배정/출고, LIFO 해제 |
| DEC-D | 009 | 주문 선입금은 금액만. 전표는 판매 기준 |
| DEC-E | 012 | 신규 `order_dt`/`sales_dt` = `YYYY-MM-DD`. 과거 일괄변환 없음 |
| (기존) | 001–007 | 복제 금지, 선주문, 수량 분리, 규격, 주문/판매 분리, 하단탭, core 공용 |

## 아직 OPEN (단계 1을 막지 않음)

| ID | 내용 | 해결 시점 |
|----|------|-----------|
| DEC-015 | 기존 HOLD → allocated / `t_order_alloc` 백필 | **단계 3 migration 전** |
| DEC-019 | 선입금의 부분출고별 배분 | **단계 4 전** |
| DEC-016 | 가락 확정 시 `t_sales_delivery` | **단계 6 전** |

## 단계 0 상태

단계 0 설계 **최종승인 완료** (2026-08-17 대표). 단계 0을 다시 열지 않는다.  
단계 1(메뉴/라우트 셸) **완료 / 대표 승인**. 단계 2(주문 조회/등록) **완료 / 대표 승인**. 단계 3 미착수.  
배정 DDL(`allocated_qty` / `t_order_alloc`)·출고 TX는 단계 3 이후.

## 코드 근거 (재검증)

- `ui/pages/order_page.py` — `save_entire_order`
- `ui/pages/sales_page.py` — `execute_full_save`, `delete_sales_data`
- `ui/pages/stock_page.py` — 원물 IN / 선별생산
- `ui/pages/market_price_page.py` — `save_realtime_auction_draft`
- `core/db_manager.py` — `generate_sales_no`, `generate_order_no`, `classify_work_log_status` (ST01 폴백 · **Stage 2에서 수정 금지**)
- `core/order_service.py` — 주문 3테이블 CRUD (판매·HOLD·전표 금지)
- `core/account_manager.py` — `sync_ledger_by_basket`
- `server/app/api/v1/router.py` — Stage 2: orders + customers GET. sales 없음
- `mobile/src/features/orders/OrderView.vue` — 주문 목록 · FAB → `/orders/new`
- `docs/판매관리테이블 생성.txt` — `qty REAL`
- `server/docs/sqlite_schema_baseline.md` — 테이블 목록. ST01 시드 없음
