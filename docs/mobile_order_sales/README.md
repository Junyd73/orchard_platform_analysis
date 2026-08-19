# 주문/판매관리 통합 설계 (ORD-001)

> **상태:** Stage 5C Core+HTTP **구현 완료**. Stage 6 UX **1차 구현** (`/orders/ship`). main 미머지.  
> **갱신:** 2026-08-19 — Stage 6 판매/출고 화면 · [04 §9](./04_mobile_screen.md)

PC · core · FastAPI · Vue PWA **공통 업무규칙**. 기존 PC `StockPage`·`OrderPage` **확장** (폐기 금지).

## 목차

| 파일 | 내용 |
|------|------|
| [01_overview.md](./01_overview.md) | 목적·원칙·단계 |
| [09_production_inventory_flow.md](./09_production_inventory_flow.md) | **생산/재고·판매유형·PC StockPage·A안** |
| [02_domain_flow.md](./02_domain_flow.md) | 주문·배정·출고·판매 |
| [03_data_contract.md](./03_data_contract.md) | 테이블 · FR010300/100/200 |
| [04_mobile_screen.md](./04_mobile_screen.md) | 모바일 UX (DEC-021) |
| [05_api_contract.md](./05_api_contract.md) | API |
| [06_development_progress.md](./06_development_progress.md) | 게이트 |
| [07_decisions.md](./07_decisions.md) | DEC · OPEN-PROD **CLOSED** |
| [08_pc_change_scope.md](./08_pc_change_scope.md) | PC P0 · StockPage |

## 핵심 (한눈에)

```
수확 → (생산) → (재고) → 판매 ← (주문)
```

- **판매**가 공통. 주문·생산·재고·배정은 **선택**.
- **Stage 3A (=5A):** 이미 있는 **상품재고**를 주문에 예약 (`allocated_qty=0` OK). **구현 완료 · main 미머지.**
- **Stage H (=3):** 수확기록 **구현 완료** (main 미머지).
- **Stage P (=4):** 포장/생산 **구현 완료** (로컬 · main 미머지). Core `ProductionService` · 모바일 `PackProdPanel`.
- **Stage 5B:** 재고관리 조회·상태·이력 **구현 완료** (로컬 · main 미머지).
- **모바일:** 하단 **판매관리** · 상단 **포장/생산 | 재고 | 주문 | 판매** (포장/생산·재고 실기능).
- **다음:** Stage 6 1차 승인. **3B 배정 UI는 후순위.**
- **UX (DEC-021):** 일을 더 만들지 않음 · 생산수량 재입력 금지 · 재고 수기 입력 금지.
- **harvest_year (DEC-026):** 생산연도가 아니라 **원료 과실의 수확연도**.

## OPEN

DEC-015 · DEC-019 · DEC-020(저장) · DEC-016

## 코드 근거

- `ui/pages/stock_page.py` — 원물·생산확정·수율·실사
- `core/order_service.py` · `core/order_allocation_service.py`
- `ui/pages/order_page.py` · `ui/pages/sales_page.py`
