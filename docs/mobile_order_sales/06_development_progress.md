# 06. Development progress

> 추적 문서. **단계 0 = 최종승인 완료** (2026-08-17 대표). 다시 열지 않음.  
> **단계 1 = 완료 / 대표 승인** (2026-08-17). **단계 2 = 완료 / 대표 승인** (2026-08-19). 단계 3 미착수.

범례: `—` · `예정` · `진행` · `완료` · `차단` · `대기`

## 게이트

```
0 설계 최종승인 (완료)
 → 1 메뉴/라우트
 → 2 주문 조회/등록
 → 3 재고배정  (allocated_qty + t_order_alloc + 운영 HOLD 점검)
 → 4 출고→판매  (DEC-019 선입금 배분 확정 후)
 → 5 판매관리
 → 6 경매/수금/회계
 → 7 회귀/운영검증
```

| 단계 | 목표 | 상태 | PC | Core | API | Mobile | Test | 대표 승인 |
|------|------|------|----|------|-----|--------|------|-----------|
| 0. 설계 | 본 폴더 문서 · 규칙 합의 | **완료** | — | — | — | — | 문서 리뷰 | **최종승인 완료** (2026-08-17) |
| 1. 메뉴/라우트 | 하단 주문/판매 · 내정보 이동 | **완료 / 대표 승인** | 없음 | 없음 | 없음 | 셸 | T-NAV-* | **승인** (2026-08-17) |
| 2. 주문 조회/등록 | 선주문 저장 (판매·전표 없음) | **완료 / 대표 승인** | 주문만 저장 | OrderService | GET/POST orders | 목록·등록·수정 | T-ORD-01 | **승인** (2026-08-19) |
| 3. 재고배정 | 부분배정 · Hold · `t_order_alloc` | 예정 | Hold 키 · allocated · alloc | Allocation | allocations | 상세 배정 | 100/30/70 · 동시성 | 단계2 + DDL + 운영점검 |
| 4. 출고→판매 | 단일 TX · 출고 1회=판매 1건 | 예정 | ship | OrderShip | POST ship | 출고 CTA | T-SHP-* | 단계3 + DEC-019 |
| 5. 판매관리 | 목록·직접판매·order_no | 예정 | 재저장 보존 | SalesService | GET/PUT sales | 판매 탭 | T-SAL-01 | 단계4 승인 후 |
| 6. 경매/수금/회계 | confirm TX · payments | 예정 | 확정 버튼 | Confirm+Account | confirm/payments | DRAFT CTA | T-AUC/PAY | 단계5 승인 후 |
| 7. 회귀/운영 | PC+모바일+관찰/일지/농약 | 예정 | 회귀 | — | health | 스모크 | T-REG-01 | 배포 승인 |

## 단계 0 산출물

- [x] 01–08 초안
- [x] 대표 5항 반영 (allocated_qty, 상태분리, 출고 TX, 선입금, 날짜)
- [x] DEC-017 / DEC-018 설계 확정 (2026-08-17)
- [x] **단계 0 설계 최종승인** (2026-08-17 대표). 다시 열지 않음
- [x] DEC-019 OPEN 기록 (선입금 부분출고 배분 · 단계 4 전)
- [x] ST01 운영 DB 확인 (DEC-011 **CLOSED** — 2026-08-17)
- [ ] 기존 HOLD 백필 (DEC-015 OPEN — 단계 3 전)
- [ ] 선입금 배분 확정 (DEC-019 OPEN — 단계 4 전)
- [ ] 가락 확정 시 `t_sales_delivery` (DEC-016 OPEN — 단계 6 전)

## 단계 1 산출물

- [x] 하단 5번째 탭 = 주문/판매 (`nav-orders`, `mainTabNav` 5탭)
- [x] 내정보/환경설정 셸 (`/settings`, AppBar 톱니)
- [x] `/orders` 주문·판매 세그먼트 셸 (목록은 단계 2·5)
- [x] SCR-030
- [x] 대표 수동 확인 승인 (2026-08-17). private main merge.

주문/판매 하단 아이콘 교체는 **후속 UI 보완**이며 이번 승인·merge 범위가 아니다.

## 단계 2

**완료 / 대표 승인** (2026-08-19). 주문 조회/등록/수정/취소만. 판매 생성 · HOLD · 회계 · 배정 DDL 없음.  
private main merge 완료. 단계 3 착수 금지.

- 공통 `core/order_service.py` (`OrderService`)
- PC `save_entire_order` → 주문 3테이블만
- GET `/api/v1/farms/{farm_cd}/orders`(조회조건·서버 페이징), GET detail, POST create, PUT, 취소
- GET/POST customers (`m_customer`)
- 모바일 목록 · 조회조건 Accordion · `/orders/new` · `/orders/:orderNo` · 수정
- 신규 `status_cd=ST010100`, `order_dt=YYYY-MM-DD` (`today_ops`)
- T-ORD-01: 재고 0 저장 성공, sales/HOLD/ledger 0
- 목록 재조회: 하단탭 캐러셀이 `OrderView`를 유지하므로 `/orders` 복귀 시 `route.path` watch로 fetch (저장 후 목록 미표시 수정)
- 주문등록 규격: 중량=`SZ01` kg 콤보, 크기=`FR020100` 과이내 콤보 (`SZ01`을 크기에 쓰지 않음)
- 주문등록 2열 grid · 신규 고객 POST (`m_customer`, PC 채번 SSOT)
- 상품 Accordion · 택배 배송지 N건 · 상태별 수정 제한
- 대표 수동 UI 승인 (2026-08-19). private main merge 완료.

## 단계 3

예정 / **미착수**. `allocated_qty` / `t_order_alloc` DDL 및 배정 API는 당기지 않음.

영농일지 `classify_work_log_status`의 ST010300/400/500 폴백은 **별도 이슈. Stage 2에서 수정 금지.**

## 운영 테스트데이터 초기화 (2026-08-17 대표 완료)

기존 주문/판매/재고는 테스트 데이터였음. **운영 DELETE 완료.**  
2026 실제 신규 수확부터 재고 데이터를 신규 구축한다.

| 영역 | 결과 |
|------|------|
| 주문 | `t_order_master` 0 · `t_order_detail` 0 · `t_order_delivery` 0 |
| 판매 | `t_sales_master` 0 · `t_sales_detail` 0 · `t_sales_delivery` 0 |
| 재고 OR001 | `t_stock_master` 0 · `t_stock_log` 0 |
| 회계 | 관련 `t_cash_ledger` 0 · `t_ledger` 0 |
| 백업 | `/var/www/orchard/backups/orchard_20260817.db` |

레거시 테스트 주문(`ORD20260301-*` 등, `status_cd` `'10'`/`'20'`)은 초기화로 제거됨. 신규 저장은 ST01만 사용.

## 테스트 계획 (단계별)

| ID | 시나리오 | 단계 |
|----|----------|------|
| T-NAV-01 | 하단 주문/판매 탭 진입, 세그먼트 주문↔판매 | 1 |
| T-NAV-02 | AppBar 톱니 → 환경설정에서 농장·세션 표시 | 1 |
| T-ORD-01 | 재고 0 주문 저장 성공, 판매행 없음 | 2 |
| T-ORD-02 | 주문 100 / 가용 30 → 배정 30, 미배정 70 | 3 |
| T-ORD-03 | 추가 생산 후 잔여 70 배정 | 3 |
| T-ORD-04 | 동시 배정이 가용 합을 넘지 않음 | 3 |
| T-SHP-01 | 출고 TX: reserved− out+ **새 판매 1건** 연결 (`order_no`) | 4 |
| T-SHP-04 | 같은 주문 2회 출고 → 판매 2건. 기존 CONFIRMED 수량 불변 | 4 |
| T-SHP-02 | 미배정만 출고 409, 재고·판매 불변 | 4 |
| T-SHP-03 | 출고 중 실패 시 전체 rollback | 4 |
| T-SHP-05 | 선입금 배분 (DEC-019 확정 후) | 4 |
| T-SAL-01 | 판매 PUT 후 order_no 유지 | 5 |
| T-AUC-01 | DRAFT 확정 시 출고+CONFIRMED, 실패 시 DRAFT 유지 | 6 |
| T-PAY-01 | CONFIRMED 수금 → cash+ledger. 주문 API는 전표 없음 | 6 |
| T-CAN-01 | 출고 전 취소 Hold 0 | 2–4 |
| T-REG-01 | 관찰·영농일지·농약 회귀 | 7 |

주문 날짜는 `today_ops`. 과거 날짜 일괄변환 테스트 없음.
