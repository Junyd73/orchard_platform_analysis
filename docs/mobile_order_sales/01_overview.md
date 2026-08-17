# 01. Overview — 주문/판매 통합

> 상태: 단계 0 **최종승인 완료** (2026-08-17 대표) → **단계 1 착수**  
> 단계 0은 다시 열지 않는다. DEC-019는 OPEN이며 단계 4 전 확정.

## 1. 프로젝트 목적

PC에만 있는 과일 **주문 · 재고배정 · 출고 · 판매 · 배송 · 수금 · 가락 경매 DRAFT** 를  
모바일에서도 같은 규칙으로 다루되, **미완성 PC 로직을 그대로 복제하지 않는다.** (DEC-001 APPROVED)

공통 업무규칙을 문서화하고, PC는 그 규칙에 맞추기 위한 **최소 수정**만 설계한다.

## 2. 확정된 통합 원칙

| 원칙 | DEC | 상태 |
|------|-----|------|
| 주문 저장과 판매 생성 분리 | DEC-005 | APPROVED |
| 선주문 허용 (재고 0이어도 등록) | DEC-002 | APPROVED |
| 부분배정 (`qty` ≠ 누적 `allocated_qty`) | DEC-003, DEC-008 | APPROVED |
| 소매 출고확정이 주문→판매 경계 (단일 TX). 출고 1회 = 판매 1건 | DEC-014, 017 | APPROVED |
| PC / core / FastAPI / mobile 동일 업무로직 | DEC-007 | APPROVED |
| 신규 `order_dt`/`sales_dt` = `YYYY-MM-DD` | DEC-012 | APPROVED |
| DB 변경 최소화. 1차 DDL = `allocated_qty` + 가칭 `t_order_alloc` | DEC-008, 018 | 둘 다 설계 APPROVED. 이번엔 CREATE/ALTER 금지 |
| 주문상태 ≠ 이행상태 | DEC-013 | APPROVED (ST01 실코드는 OPEN) |
| 주문 선입금은 금액만. 전표는 판매 기준 | DEC-009 | APPROVED |
| 규격 = 품종×중량×등급×크기 | DEC-004 | APPROVED |

기타: ODS / FastAPI `/api/v1` / Vue3 / PyQt6 / SQLite 유지. 농약 재고 API와 과일 재고 혼용 금지.

## 3. 개발 범위 (목표)

- 소매 선주문 · 부분 재고배정 · 배송/방문 · **출고확정 TX에서 판매 생성** → 수금
- 가락: 포장재고 → 실시간 경매 → `AUCTION_RT` DRAFT → **확정+출고 단일 TX** → 정산
- 수출/일반도매: 포장재고 → 판매 직접 등록 → 출고/확정 → 수금
- 모바일 하단 5번째 탭 **주문/판매** (DEC-006)
- PC P0: 동시생성 제거, Hold 키, 출고, 날짜, 채번 공통화

## 4. 비범위

- PC 주문/판매 UI 전면 재설계
- 저장관리(`StockPage`) 구조 전면 교체
- 과거 주문/판매 **일괄** 날짜·상태 migration
- 선수금 회계 신규 설계
- `t_dlvry_detail` 등 미사용 명칭 정리
- 농약 입고/출고, 관찰·영농일지·시세수집 로직 변경
- OS timezone / backup cron
- 단계 0 최종승인 전 구현

## 5. 품종별 업무흐름 (운영 확정)

코드에 품종별 if 분기는 **없다.** `item_cd` + 원물(`FR010300`) 존재 여부로 운영한다.

| 품종 | 흐름 | 주문 | 저장 |
|------|------|------|------|
| 원황 | 수확 → (저장 없음) → 포장 → **수출 판매** | 드묾 | 원물 입고 생략 가능 |
| 조생 (수황·황금·화산 등) | 수확 → (저장 없음) → 포장 → 도매 또는 소매 | 소매 있음 | 원물 입고 생략 가능 |
| 신고 | 수확 → **저장** → 포장 → 주로 가락 도매 | 소매 일부 | `FR010300` 입고 후 선별 |

포장 완료 상품은 모두 `t_stock_master.item_cd = FR010100` (배).  
원황/조생과 신고 **상품 행만으로는 구분 불가** — 원물 입고 이력으로만 구분.

## 6. 도메인 관계

```
고객(m_customer)
    ↓
주문(t_order_*)     ←── 선주문: 재고 없어도 접수, allocated_qty=0
    ↓ 재고배정 (부분 허용, FIFO, t_order_alloc)
상품재고(t_stock_master FR010100)  ← 선별생산 ← 원물(FR010300, 신고)
    ↓ 출고확정 TX (reserved → out + 새 판매 1건, 주문 1:N)
판매(t_sales_*)     ←── 경매 DRAFT(AUCTION_RT) 도 확정 TX에서 합류
    │   SSOT: t_sales_master.order_no + t_sales_detail.order_detail_id
    ↓ CONFIRMED
수금(t_cash_ledger) + 전표(t_ledger)   ←── 주문 시점 전표 없음
배송(t_order_delivery / t_sales_delivery)  ←── 출고분만큼만 판매배송
```

**현재 PC:** 주문 저장 시 판매 행을 **즉시 INSERT** (`save_entire_order`).  
**확정 설계:** 주문 접수와 판매 생성을 분리한다. (DEC-005 APPROVED)

## 7. 기존 시스템 재사용

| 자산 | 재사용 |
|------|--------|
| 규격 | `variety_cd` × `weight` × `grade_cd` × `size_cd` × `qty` × `unit_price` × `harvest_year` |
| 채번 | 주문 `ORDYYYYMMDD-NNN` · 판매 `YYYYMMDD-NN` (`generate_sales_no`로 공통화) |
| 배송유형 | `LO010100` 방문 · `LO010200` 택배 · `LO010300` 화물/경매 |
| 시즌 | `SS01` → `season_type_cd` |
| 판매상태 | `sales_status` `DRAFT`/`CONFIRMED`, `sales_source` `ORDER`/`AUCTION_RT` |
| 회계 | `AccountManager.sync_ledger_by_basket('SALE', …)` — CONFIRMED 판매만 |
| 경매 | `MarketPricePage.save_realtime_auction_draft` + **신설 confirm** |
| 업무일 | `today_ops` / `now_ops_str` (KST) |

## 8. 신규 구조 최소화

수량 용어:

- `allocated_qty` = **누적 배정수량** (출고 후 유지)
- `shipped_qty` / `reserved_unshipped_qty` / `unallocated_qty` = 계산값, 컬럼 없음

- 새 상태코드 임의 추가 없음.
- 1차 DDL 후보: **`t_order_detail.allocated_qty`** (DEC-008) + 가칭 **`t_order_alloc`** (DEC-018, 현재상태 SSOT). 실제 ALTER/CREATE는 단계 3. 이번 문서 작업에서 DDL 금지.
- `t_stock_log`는 HOLD/CANCEL_HOLD/OUT **이력**. allocation 현재상태 SSOT로 쓰지 않음.

## 9. 단계별 개발계획

상세·게이트: [06_development_progress.md](./06_development_progress.md)

| 단계 | 목표 | 진입 조건 |
|------|------|-----------|
| 0 | 설계 · **최종승인** | 본 문서 대표 승인 |
| 1 | 하단탭·라우트 셸 | 단계 0 최종승인 |
| 2 | 주문 조회/등록 (판매 미생성) | 단계 1 승인. ST01은 OPEN이어도 접수는 `'10'` 유지 가능 |
| 3 | 재고배정 | 단계 2 승인 + `allocated_qty`/`t_order_alloc` migration + 운영 HOLD 점검 (DEC-015) |
| 4 | 출고 → 판매 (단일 TX, 1출고=1판매) | 단계 3 승인 + DEC-019 |
| 5 | 판매 목록/직접판매 | 단계 4 승인 |
| 6 | 경매 확정 · 수금 · 회계 | 단계 5 승인 |
| 7 | 회귀 · 운영 검증 | 단계 6 승인 |

현재: **단계 0 최종승인 완료. 단계 1 착수.**

## 10. 남은 승인·점검

단계 0은 닫혔다. 아래 OPEN은 **단계 1을 막지 않는다.** 각 단계 진입 전에 해결한다.

| ID | 내용 | 해결 시점 |
|----|------|-----------|
| DEC-011 | 운영 `ST01` 실코드 | 단계 2 전 |
| DEC-015 | 기존 HOLD → allocated / `t_order_alloc` 백필 | 단계 3 migration 전 |
| DEC-019 | 선입금의 부분출고별 배분 | 단계 4 전 |
| DEC-016 | 가락 확정 시 `t_sales_delivery` | 단계 6 전 |

출고 후 판매취소 정책은 기존대로 단계 6 OPEN.
