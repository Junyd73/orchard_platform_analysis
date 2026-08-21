# 주문/판매관리 통합 설계 (ORD-001)

> **현재 운영 기준 (2026-08-21):** Stage 6 출고/판매 · Order→Ship Step1~3 · 주문목록 compact **운영 반영** (`fd963e0`). analysis main `2e7b3fc`.  
> **문서 feature** (선입금·수금 DEC-019/028/029)는 main **미반영**. 상세·다음 순서: [06](./06_development_progress.md).  
> **갱신:** 2026-08-21 — 선입금·수금 설계 정합 · 현금성 결제수단 범위.

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
| [06_development_progress.md](./06_development_progress.md) | 게이트 · **현재 운영 기준** |
| [07_decisions.md](./07_decisions.md) | DEC · OPEN-PROD **CLOSED** |
| [08_pc_change_scope.md](./08_pc_change_scope.md) | PC P0 · StockPage |

## 핵심 (한눈에)

```
수확 → (생산) → (재고) → 판매 ← (주문)
```

- **판매**가 공통. 주문·생산·재고·배정은 **선택**.
- **Stage 3A~6 / Order→Ship:** **운영 반영 완료** (`fd963e0`). 배정 UI(3B)는 후순위.
- **모바일:** 하단 **판매관리** · 상단 **포장/생산 | 재고 | 주문 | 판매**.
- **다음:** [06 개발순서 1~8](./06_development_progress.md) — 선입금 결제수단 · 수금 Core · 출고 선입금 배분 · 판매목록/상세 · PC 정합 · 가락.
- **UX (DEC-021):** 일을 더 만들지 않음 · 생산수량 재입력 금지 · 재고 수기 입력 금지.
- **harvest_year (DEC-026):** 생산연도가 아니라 **원료 과실의 수확연도**.

## 선입금 · 수금 (2026-08-21 확정)

- **DEC-019 APPROVED** — 부분출고 선입금 **순차 배분**. 회차 적용액 = `min(선입금 잔액, 그 판매금액)`
- **DEC-028 APPROVED** — 주문 **선입금 결제수단** (`pre_pay_amt>0`이면 필수). **현금성 자산 계정**. 채권(`AS02…`) 제외. **완료 · 운영** (`pre_pay_method_cd`)
- **DEC-019 provenance CLOSED** — `t_cash_ledger.order_no` NULL=일반수금, 주문번호=출고 선입금 자동적용. Stage4 feature · main 미반영 · DDL 0
- **DEC-029 APPROVED** — **판매상태 ≠ 수금상태**. `sales_status`는 DRAFT/CONFIRMED만, 수금상태는 금액 계산값
- 주문 단계는 계속 **전표 없음**. 회계는 판매확정에서만 (DEC-009)
- UI 용어: **결제수단 · 수금액 · 미수금 · 수금상태**

## OPEN

DEC-015 · DEC-020(저장) · DEC-016  
(DEC-019는 2026-08-21 APPROVED로 제외)  
스키마 확인 대기: `pre_pay_method_cd` · `t_cash_ledger` 선입금 구분키 · **현금성 결제계정 범위** · DEC-016

상세 현황·역사 기록 분리: [06](./06_development_progress.md).
