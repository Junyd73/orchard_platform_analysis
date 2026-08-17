# 주문/판매관리 통합 설계 (ORD-001)

> **상태:** 단계 0 · **설계 수정 / 최종승인 대기**  
> **갱신:** 2026-08-17 (대표 확정 5항 반영)  
> **구현:** 금지. DDL/API/UI/migration/테스트코드 금지.  
> **단계 1:** 단계 0 **최종승인** 전에는 착수하지 않는다.

PC(PyQt) · core · FastAPI · Vue PWA가 **동일 업무 규칙**을 쓰기 위한 설계다.

## 문서 위치

`docs/mobile_order_sales/`

| 대안 | 사용하지 않은 이유 |
|------|-------------------|
| `mobile/docs/screens/` | 승인된 ODS/SCR SSOT. 아직 SCR ID 없음 |
| 관찰/농약 단일 md | 주문/판매는 PC 변경·migration 조건까지 포함해 분할 |

구현 착수 후 화면 명세는 `mobile/docs/screens/SCR-0xx.md` 로 옮긴다.

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
| DEC-D | 009 | 주문 선입금은 금액만. 전표는 판매 기준 |
| DEC-E | 012 | 신규 `order_dt`/`sales_dt` = `YYYY-MM-DD`. 과거 일괄변환 없음 |
| (기존) | 001–007 | 복제 금지, 선주문, 수량 분리, 규격, 주문/판매 분리, 하단탭, core 공용 |

## 아직 OPEN

| ID | 내용 | 막힘 |
|----|------|------|
| DEC-011 | 운영 `ST01` 실코드 매핑 | 주문상태 저장값. **운영 DB 확인 필요** |
| DEC-015 | 기존 주문 allocated 백필 | 단계 3 migration |
| DEC-016 | 가락 확정 시 배송행 생성 | 단계 6 |

## 단계 0 최종승인 시 남는 조건

1. 본 수정본 승인
2. 단계 1 착수 허가
3. ST01·HOLD·DRAFT·날짜 혼재는 **구현/migration 직전** read-only 점검 ([03](./03_data_contract.md) §15)

## 코드 근거 (재검증)

- `ui/pages/order_page.py` — `save_entire_order`
- `ui/pages/sales_page.py` — `execute_full_save`, `delete_sales_data`
- `ui/pages/stock_page.py` — 원물 IN / 선별생산
- `ui/pages/market_price_page.py` — `save_realtime_auction_draft`
- `core/db_manager.py` — `generate_sales_no`, `ensure_sales_workflow_schema`, `classify_work_log_status` (ST01 폴백)
- `core/account_manager.py` — `sync_ledger_by_basket`
- `server/app/api/v1/router.py` — 과일 orders/sales 없음
- `mobile/src/features/orders/OrderView.vue` — placeholder
- `docs/판매관리테이블 생성.txt` — `qty REAL`
- `server/docs/sqlite_schema_baseline.md` — 테이블 목록. ST01 시드 없음
