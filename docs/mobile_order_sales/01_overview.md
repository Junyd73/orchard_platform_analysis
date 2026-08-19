# 01. Overview — 주문/판매 통합

> 상태: 단계 0 **최종승인** → 단계 1·2 **완료** → **3A/H/P/5B 구현 완료** (main 미머지)  
> **2026-08-19:** Stage 5C 1차 DEC-027 · 추적 DDL. Core 출고 **없음**. 상세: [09](./09_production_inventory_flow.md) · [06](./06_development_progress.md)  
> Stage 5C Core · Stage 3B UI · 운영 migration **없음** (이번 작업).

## 0. UX 최우선 원칙 (DEC-021)

**농부에게 일을 더 만들지 않는다.**

중복입력 금지 · 자동(날짜/채번) · 생산수량 판매 재입력 금지 · 선택 단계 강제 화면 금지.  
상세: [09 §0](./09_production_inventory_flow.md).

## 1. 프로젝트 목적

PC의 **수확·생산·재고·주문·판매·경매**를 모바일과 공유 규칙으로 연결하되,  
**미완성 PC 로직을 복제하지 않고**, 기존 `StockPage`·`OrderPage`를 **확장**한다. (DEC-001)

- **재고/생산:** `ui/pages/stock_page.py` (원물·상품·생산확정·수율)
- **주문/판매:** `core/order_service.py`, Stage 5A allocation, Stage 5C 출고·판매

## 2. 최상위 업무 모델

**판매**가 공통 종착. 괄호 단계는 모두 **선택**.

```
수확 → (생산/변환) → (재고) → 판매
                              ↑
                           (주문)
```

`주문→배정→출고→판매`는 **저장배 소매 등 일부 경로**만. 전체 공통 흐름 아님.  
판매유형 7종·PC 근거: [09 §2·§3](./09_production_inventory_flow.md).

## 3. 확정된 통합 원칙

| 원칙 | DEC | 상태 |
|------|-----|------|
| UX: 일을 더 만들지 않음 | 021 | APPROVED |
| 주문 저장 ≠ 판매 생성 | 005 | APPROVED |
| 선주문 (재고 0 OK) | 002 | APPROVED |
| 부분배정, 배정은 **선택** | 003, 008 | APPROVED |
| 출고방식 STOCK/DIRECT (한 축) | 020 | APPROVED. 저장·DIRECT TX OPEN |
| 출고 1회 = 판매 1건 | 014, 017 | APPROVED |
| PC/core/API/mobile 동일 규칙 | 007 | APPROVED |
| 날짜 ISO | 012 | APPROVED |
| Stage 3A DDL | 008, 018 | 로컬. 운영 별도 |
| 주문상태 ≠ 이행상태 | 013 | APPROVED |
| 선입금 금액만 | 009 | APPROVED |
| 규격 4요소 | 004 | APPROVED |
| harvest_year = 원료 수확연도 | 026 | APPROVED |

**금지:** 품종으로 STOCK/DIRECT·판매유형 자동 분기.

## 4. Stage 3A (구현 완료 · merge 대기)

**이미 있는 상품재고**를 주문에 예약 — 저장배·배즙재고 등.

- `allocated_qty`, `t_order_alloc`, FIFO/LIFO, HOLD — **유지**
- `allocated_qty=0` **정상**. 생산→바로판매에 alloc **강제 없음**
- 운영 DDL **미적용**. main merge **미승인**
- [02 §3·§4](./02_domain_flow.md) 배정·STOCK 출고

## 5. 개발 범위·비범위

**범위:** 모바일 **판매관리** (하단) · 상단 4탭 Shell · 공통 Order/Allocation 서비스 · PC P0(판매 분리·출고 TX 등)  
**비범위:** StockPage 전면 교체 · `t_production_*` DDL · Stage 3B UI · Stage 5C 판매 OUT

## 5.1 모바일 판매관리 Shell (2026-08-19)

- 하단 5탭 5번째: **판매관리** (`/orders`, 아이콘 `nav-orders` 유지)
- 상단 4탭: **포장/생산 · 재고 · 주문 · 판매** — 업무영역 분류(강제 workflow 아님)
- 초기 선택 탭: **주문** (기존 사용성 유지)
- 포장/생산·재고: Stage P/5B **실기능**. 주문·판매 기존 Shell 유지

## 6. 기존 시스템 재사용

| 자산 | 재사용 |
|------|--------|
| 재고/생산 | `stock_page.py` — FR010300/100/200, 생산확정, 수율, 실사 |
| 주문 | `order_service.py`, `order_allocation_service.py` |
| 판매/경매 | `sales_page.py`, `market_price_page.py` |
| 회계 | `account_manager.py` — CONFIRMED만 |
| 업무일 | `today_ops` / `now_ops_str` |

## 7. 단계 계획

역사적 번호(3A/H/P/S)는 유지하고, 운영 표기는 아래와 같이 읽는다. 게이트: [06](./06_development_progress.md).

| 단계 | 목표 | 상태 |
|------|------|------|
| 0 | 주문·판매·재고 전체 설계 / PC 기준 분석 / 업무규칙 | **완료** |
| 1 | 모바일 주문/판매 진입구조·메뉴·라우팅 | **완료** |
| 2 | 주문관리 — 조회·등록·수정·취소·고객·배송지 | **완료** |
| 3 (=H) | 수확기록 확장 — 영농일지 품종·콘테이너 수량 | **완료** (main 미머지) |
| 4 (=P) | 생산/변환 — PACK·PROCESS·원물 OUT·생산품 IN | **완료** (main 미머지) |
| 5A (=3A) | 재고배정 Core — HOLD / RELEASE / allocation | **완료** (main 미머지) |
| 5B | 재고관리 — 조회·상태·이력·생산/배정 정합성 | **완료** (main 미머지) |
| 5C (=S) | 공통 출고·판매 Core — 판매확정·상품 OUT | **예정** |
| 6 | 모바일 출고·배정·판매 UX (구 3B 포함) | **예정** |
| 7 | 가락시장 경매→판매확정·정산 | **예정** |
| 8 | 통합 회귀·PC/PWA 정합·운영 Migration·배포 | **예정** |

## 8. OPEN

| ID | 내용 |
|----|------|
| DEC-015 | HOLD 백필 **금지**. active reserved만 DDL 차단. CLOSED 후보, 운영 재확인 전 CLOSED 금지 |
| DEC-019 | 선입금 부분출고 배분 |
| DEC-020 저장 | 출고방식 저장·DIRECT TX |
| DEC-016 | 가락 `t_sales_delivery` |

## 9. 코드 근거

- `ui/pages/stock_page.py` — 원물 IN, 생산확정, 수율, 실사, 폐기
- `core/order_service.py`, `core/order_allocation_service.py`
- `docs/mobile_order_sales/09_production_inventory_flow.md` — 생산/재고 SSOT
