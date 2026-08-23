# 07. Decisions

상태: `APPROVED` | `PROPOSED` | `OPEN` | `REJECTED` | `SUPERSEDED`

- **APPROVED**: 대표 확정. 구현 시 이 규칙을 따른다. (DDL·코드는 단계 승인 후)
- **PROPOSED / OPEN**: 미확정. APPROVED와 섞어 확정으로 읽지 말 것.

승인일 표기: 대표 검토 반영일 **2026-08-17**. 단계 0 **최종승인 완료** (2026-08-17 대표). 단계 0은 다시 열지 않음.  
**2026-08-21 대표 승인:** DEC-019 **APPROVED** · DEC-028 · DEC-029 **신규 APPROVED**.  
**2026-08-23 대표 승인:** DEC-030 **신규 APPROVED** (6C write validation 전용).

---

## 대표 확정 대응 (2026-08-17)

| 대표 ID | 내용 | DEC |
|---------|------|-----|
| DEC-A | `allocated_qty` 추가 (설계 확정, migration 아직 안 함) | DEC-008 |
| DEC-B | 주문상태와 이행상태 논리 분리 | DEC-013 |
| DEC-C | 출고확정(소매)·가락 확정을 단일 업무 트랜잭션 | DEC-010, DEC-014 |
| DEC-D | 주문 선입금은 금액만. 전표는 판매확정 시 | DEC-009 |
| DEC-E | 신규 `order_dt`/`sales_dt` = `YYYY-MM-DD` | DEC-012 |
| DEC-017 | 출고 1회 = 판매 1건. 주문 1 : 판매 N | DEC-017 |
| DEC-018 | 재고행 allocation 전용 테이블. FIFO 배정/출고, LIFO 해제 | DEC-018 |
| DEC-020 | 출고방식 STOCK/DIRECT (한 축) | DEC-020 |
| DEC-021 | UX: 농부에게 일을 더 만들지 않음 | DEC-021 |
| DEC-022 | 수확: 영농일지·상자·≠자동입고 | DEC-022 |
| DEC-023 | 생산 A안·잔량자동재고 | DEC-023 |
| DEC-024 | 배즙 단위 박스 | DEC-024 |
| DEC-025 | 생산 DB 기존구조 우선 | DEC-025 |
| DEC-026 | harvest_year = 원료 과실 수확연도 · 생산 승계 | DEC-026 |
| DEC-027 | 판매출고 재고 추적 · STOCK/DIRECT consume | DEC-027 |

## 대표 확정 대응 (2026-08-21)

| 대표 ID | 내용 | DEC |
|---------|------|-----|
| DEC-019 | 선입금 부분출고 **순차 배분** 확정 | DEC-019 |
| DEC-028 | 주문 선입금 **결제수단** (금액>0이면 필수) | DEC-028 |
| DEC-029 | **판매상태 ≠ 수금상태** (수금상태는 금액 계산값) | DEC-029 |
| DEC-030 | **신규 수금일** `sales_dt ≤ pay_dt ≤ today` (legacy 조회만) | DEC-030 |
| DEC-031 | **출고확정 CONFIRMED** PC read-only | DEC-031 |
| DEC-032 | **PC 수금 append-only** (구현 Stage7B) | DEC-032 |

---

## DEC-001

**PC를 주문/판매 업무 기준으로 삼되, 미완성 로직은 모바일에 그대로 복제하지 않는다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 공통 규칙을 정의한 뒤 PC를 최소 수정으로 맞춘다. 미연결 버튼·미구현 출고·전표 누락을 모바일에 복제하지 않는다. |
| 이유 | 주문 일괄확정 미연결, 출고 미구현, DRAFT 확정 버튼 없음, 판매 삭제 시 전표 없음 |
| 영향 | 모바일은 본 폴더 권장 흐름. PC는 [08](./08_pc_change_scope.md) P0 |
| 승인 | 2026-08-17 대표 |

---

## DEC-002

**선주문은 재고가 없어도 등록 가능.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | POST 주문은 가용재고 부족으로 거부하지 않는다. 등록 시 `allocated_qty=0`. |
| 이유 | 명절 등 포장 전·중·후에도 주문이 들어온다. |
| 영향 | 단계 2. 재고 검증은 배정 API에서만. `allocated_qty=0`은 정상 (DEC-020). |
| 승인 | 2026-08-17 대표 |

---

## DEC-003

**주문수량과 재고배정수량은 분리.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | `qty` = 주문수량, `allocated_qty` = **누적 배정수량**(출고 후에도 유지). `unallocated_qty = qty - allocated_qty`, `shipped_qty`·`reserved_unshipped_qty`는 계산값(컬럼 없음). |
| 이유 | 주문 100 / 재고 30 → 배정 30, 이후 생산분 추가 배정. |
| 영향 | 단계 3. DEC-008 DDL은 단계 3 착수 시 migration. |
| 승인 | 2026-08-17 대표 |

---

## DEC-004

**상품 규격은 PC의 품종/중량/등급/크기 체계를 재사용.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | `variety_cd` × `weight` × `grade_cd` × `size_cd` × `qty` × `unit_price` × `harvest_year`. 신규 규격 테이블 없음. `harvest_year` 의미는 DEC-026. |
| 이유 | 기존 PC·재고 키와 동일해야 Hold/출고가 맞는다. |
| 영향 | 주문 줄·재고 매트릭스·판매 상세. 관련: DEC-018 · **DEC-026** |
| 승인 | 2026-08-17 대표 |

---

## DEC-005

**주문 저장과 판매 생성을 분리한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 주문 접수는 `t_order_*`만. 소매 판매는 출고확정 트랜잭션에서 생성. 가락·직접판매는 각 확정 경로. |
| 이유 | 현재 `save_entire_order` 동시 INSERT는 선주문·부분배정·회계 시점과 충돌. |
| 영향 | PC P0. 기존 운영 주문은 이미 판매행이 있을 수 있음 → 구현 전 점검. |
| 승인 | 2026-08-17 대표 |

---

## DEC-006

**하단 내정보 위치를 주문/판매로 변경하고, 내정보는 환경설정으로 이동.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 하단 5탭 = 홈·생육관찰·영농일지·농약관리·주문/판매. 내정보 = AppBar 톱니 → 환경설정. |
| 이유 | 확정 메뉴 구조. |
| 영향 | 단계 1. `OdsBottomNav`, `mainTabNav.ts` |
| 승인 | 2026-08-17 대표 |

---

## DEC-007

**PC / FastAPI / mobile이 동일 core 업무로직을 사용한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 주문저장·배정·출고·판매확정의 SQL은 `core` 서비스 1곳. FastAPI는 호출만. 페이지에 SQL을 새로 복제하지 않음. |
| 이유 | 이중 구현 시 규칙이 다시 갈라진다. |
| 영향 | 단계 2 이전 core 추출이 선행. 서비스 이름은 가칭, 아키텍처 확정 아님. |
| 승인 | 2026-08-17 대표 |

---

## DEC-008

**`t_order_detail.allocated_qty` 추가 (설계 확정).**

| | |
|--|--|
| 상태 | **APPROVED** (설계). **migration은 미실시.** |
| 결정 | 컬럼 추가를 권장안으로 확정. 의미는 **누적 배정수량**(현재 Hold 잔량이 아님). 타입은 `qty`와 동일 계열. `NOT NULL DEFAULT 0`. `unallocated_qty`/`shipped_qty` 컬럼은 만들지 않음. |
| 이유 | 줄 단위 부분배정 영속에 기존 컬럼이 없다. |
| 영향 | 단계 3 DDL. 기존 HOLD 데이터와 초기값 충돌 가능 → [03](./03_data_contract.md) migration 계획·운영 점검. |
| 승인 | 2026-08-17 대표 (DEC-A) |

이번 문서 작업에서 ALTER 하지 않는다.

---

## DEC-009

**주문 단계 선입금은 금액(+결제수단)만 기록한다. 전표는 만들지 않는다.**

| | |
|--|--|
| 상태 | **APPROVED** (핵심 유지) |
| 결정 | 주문접수 시 `pre_pay_amt` **금액**과 (DEC-028) **선입금 결제수단**만 저장. `t_cash_ledger` / `t_ledger` 생성 **금지**. 판매확정(CONFIRMED) 시 입금·미수·수금줄·전표를 **판매 기준**으로 반영. 선수금 계정 설계는 이번 범위 밖(별도 확장). |
| 이유 | 현재 PC도 주문 경로 전표가 없고, 발생주의 전표는 판매 확정과 맞춘다. |
| 영향 | 단계 2·6. DEC-D. 배분 규칙 **DEC-019 APPROVED**, 결제수단 **DEC-028** |
| 승인 | 2026-08-17 대표 |

**결제수단을 주문에 저장하는 것은 전표 생성이 아니다.** 주문 단계는 계속 회계 무발생이다 (DEC-028).

---

## DEC-010

**가락 최종 확정은 `AUCTION_RT DRAFT → CONFIRMED` 와 재고 출고를 한 업무 트랜잭션으로 한다.**

| | |
|--|--|
| 상태 | **APPROVED** (방향). 현재 PC는 확정 함수가 없어 **보완 구현 필요**. |
| 결정 | confirm 한 트랜잭션: 상태 CONFIRMED + 가용 재검증 + `out_qty` 증가 + stock log + (선택) 수금/전표. 실패 시 전체 rollback. |
| 이유 | 재고만 빠지거나 판매만 CONFIRMED 되는 상태를 금지. |
| 영향 | 단계 6. 초안 저장 시점에는 재고를 건드리지 않음(현재와 동일). 배송행이 초안에 없으면 확정 TX에서 생성할지 **OPEN**(DEC-016). |
| 승인 | 2026-08-17 대표 (DEC-C) |

---

## DEC-011

**주문 `status_cd`와 운영 `ST01` 실코드 매핑.**

| | |
|--|--|
| 상태 | **CLOSED** (2026-08-17 대표) |
| 결정 | 신규 ST01 코드 추가 불필요. 주문 `status_cd` SSOT는 운영 `m_common_code.parent_cd='ST01'` 실코드 5종. Stage 2 신규 주문 저장 기본값 = `ST010100`. PC `'10'`/`'20'` 저장은 레거시 테스트 로직으로 폐기 대상. |
| 운영 실코드 | `ST010100` 예약접수 · `ST010200` 주문확정 · `ST010300` 배송준비 · `ST010400` 배송완료 · `ST010500` 취소 |
| 확인된 사실 | 운영 `m_common_code` 컬럼은 `farm_cd, code_cd, code_nm, parent_cd, use_yn, reg_id, reg_dt, mod_id, mod_dt`. `code`/`sort_order` 없음. 테스트 주문 4건(`10`/`20`)은 **2026-08-17 운영 초기화로 제거 완료**. |
| 별도 정리 | 영농일지 `classify_work_log_status`의 `ST010300`/`ST010400`/`ST010500` 폴백은 주문 의미(배송준비/배송완료/취소)와 충돌. **주문 Stage 2와 분리. Stage 2에서 수정 금지.** |
| 영향 | Stage 2 신규 저장값 = `ST010100`. 이행 4종은 ST01에 넣지 않음 (DEC-013). PC `'10'`/`'20'` 저장 폐기. |

---

## DEC-012

**신규 `order_dt` / `sales_dt` 저장 형식은 `YYYY-MM-DD`.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 신규 INSERT/UPDATE는 ISO 날짜. 과거 데이터 일괄 변환 안 함. 조회 시 YYYYMMDD와 ISO를 모두 파싱. 업무일은 `today_ops` / `now_ops_str` (KST). |
| 이유 | PC 주문 경로는 `YYYYMMDD`, 판매화면·경매는 ISO로 혼재. |
| 영향 | PC P0 신규 저장. API 요청/응답은 ISO만. |
| 승인 | 2026-08-17 대표 (DEC-E) |

---

## DEC-013

**주문상태와 이행상태(배정/출고)를 같은 개념으로 쓰지 않는다.**

| | |
|--|--|
| 상태 | **APPROVED** (논리 분리). 주문 `status_cd` 실코드는 DEC-011 CLOSED. |
| 결정 | 주문상태 = 접수/완료/취소(문서 의미). 이행상태 = 미배정/부분배정/배정완료/출고완료(계산). 이행용 **새 컬럼·새 ST01 코드 추가 금지**. 계산식은 [02](./02_domain_flow.md). |
| 이유 | 배정 진행을 주문 취소와 한 코드로 섞으면 선주문을 표현할 수 없다. |
| 영향 | UI 배지 두 개. `status_cd`는 주문상태만. `stock_status`·`allocated_qty`·판매연결은 이행 계산. **DEC-027:** ST010300은 부분배정이 아니라 **첫 CONFIRMED 출고 후 잔량 있는 주문의 배송준비**. 배정 이행(미배정/부분배정/배정완료)은 ST01에 넣지 않음. |
| 승인 | 2026-08-17 대표 (DEC-B) |

---

## DEC-014

**소매 출고확정은 재고 이동과 판매 생성을 하나의 DB 트랜잭션으로 한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 배정수량 검증 → reserved− → out+ → stock log → 이행/주문상태 → `t_sales_master/detail` → `order_no`/`order_detail_id` 연결 → 배송 연결. 한 단계라도 실패하면 rollback. 금지: 재고만 감소, 판매만 생성, 주문 완료인데 판매 없음. |
| 이유 | 부분 성공 시 장부·재고가 복구 불능에 가깝다. |
| 영향 | 단계 4. 출고 TX에서 판매는 `CONFIRMED`. `pre_pay_amt>0`이면 **같은 TX**에서 그 회차 적용액을 판매 수금 바구니에 담고 `sync_ledger_by_basket('SALE', …)`. 선수금 계정 설계는 하지 않음 (DEC-009). **출고 1회 = 판매 1건** (DEC-017). 부분출고 시 선입금 배분은 **DEC-019 APPROVED**(순차 배분, 회차 적용액 = `min(선입금 잔액, 그 판매금액)`). 사용 결제수단은 주문의 선입금 결제수단 (DEC-028). |
| 승인 | 2026-08-17 대표 (DEC-C) |

---

## DEC-015

**기존 HOLD → `allocated_qty` / `t_order_alloc` 백필.**

| | |
|--|--|
| 상태 | **OPEN** (**CLOSED 후보**) |
| 결정 | **백필 금지 유지.** 초기 migration은 HOLD/`reserved_qty` 보호가 목적이다. `ensure_order_alloc_schema` preflight는 **현재 active `reserved_qty>0`만 차단**. historical HOLD/CANCEL_HOLD 로그만 있고 현재 reserved=0이면 schema(DDL)는 허용한다. 로그는 Audit 대상이지 DDL 영구 차단 사유가 아니다. 레거시 HOLD를 `t_order_alloc`로 자동 복원하지 않는다. 기존 주문 `allocated_qty` DEFAULT 0. |
| 이유 | 이미 전량 Hold된 주문에 0을 넣으면 미배정으로 보이며 이중 Hold 가능. 유령 reserved는 잠금만 해제하고 백필하지 않는다 (Stage 6-2 A안). |
| 영향 | 단계 3 직전 점검. 로컬 A안: stock_seq=156 reserved 103 해제 + AUDIT, HOLD 이력 보존. 운영 DDL은 별도 승인. |
| 3A 메모 | 운영 DB 재확인 SQL: `scripts/ops/check_order_alloc_preflight.sql`. **운영 재확인 전 CLOSED 하지 않음.** DEC-027(출고 규칙)과 충돌 없음 — 현재상태 SSOT는 계속 `t_order_alloc`. |

---

## DEC-016

**가락 초안에 `t_sales_delivery`가 없는 경우, 확정 TX에서 배송행을 만들지.**

| | |
|--|--|
| 상태 | **OPEN** |
| 현재 | `save_realtime_auction_draft`는 마스터·상세만. `dlvry_tp=LO010300`. |
| 영향 | DEC-010 보완. 없으면 출고 후 송장 연결이 비어 있음. |

---

## DEC-017

**부분출고와 판매: 출고 1회 = 판매 1건 (주문 1 : 판매 N).**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 출고 이벤트마다 새 `sales_no`. 기존 CONFIRMED 판매·전표를 후속 출고로 수정하지 않음. SSOT = `t_sales_master.order_no` + `t_sales_detail.order_detail_id`. `t_order_master.sales_no`는 **legacy/reference**(최초 출고 번호 또는 대표 참조). 주문 전체 판매 조회는 반드시 `t_sales_master.order_no` 기준. 새 컬럼 없음. |
| 이유 | 실제 출고일과 판매일·재고 출고·배송·수금·회계를 일치시킨다. |
| 현재 PC | 부분출고 없음. 주문 저장 시 판매 1건. |
| 영향 | 단계 4. DEC-014와 함께: 출고 1회 TX 안에 판매 1건 생성. |
| 승인 | 2026-08-17 대표 |

판매마스터: `order_no` 저장, `sales_source=ORDER`, `sales_status=CONFIRMED`, `sales_dt` = 실제 출고 업무일 `YYYY-MM-DD`.  
판매상세: `order_detail_id` 필수, 해당 출고분 `ship_qty`만 저장.  
배송: 그 출고분에 해당하는 판매배송만 연결. 주문 배송계획 전체를 매번 복사하지 않음. 한 계획이 여러 출고로 나뉘면 실제 출고수량만큼 판매배송행 생성. 상세 알고리즘은 단계 4 전 `t_order_delivery` 기준으로 재검토하되 1:N 원칙은 변경하지 않음.

전량 출고: 모든 주문상세 `shipped_qty == qty` → `stock_status='Y'`, 이행상태=출고완료. 주문상태 배송완료 매핑은 `ST010400` (DEC-011 CLOSED).

---

## DEC-018

**재고행 allocation은 전용 `t_order_alloc`(가칭). `t_stock_log`는 이력이며 현재상태 SSOT가 아니다.**

| | |
|--|--|
| 상태 | **APPROVED.** Stage 3A 로컬 테이블명 `t_order_alloc`. 운영 CREATE 금지. |
| 결정 | 줄↔stock 자연키 배정은 `t_order_alloc`. 자동배정 **FIFO**(`storage_dt ASC`). 배정해제 **LIFO**(최근 잡은 행부터). 출고 소비 **FIFO**. 로그에 allocation SSOT용 컬럼을 억지로 넣지 않음. 향후 HOLD/CANCEL_HOLD/OUT에는 가능한 범위에서 `order_no`/`order_detail_id`/`sales_no`/stock 자연키를 이력으로 남길 수 있음. 현재상태 복원은 `t_order_alloc`, 감사 이력은 `t_stock_log`. |
| 근거 | 로그에 `wh_cd`/`storage_dt`가 없어 행 복원 불가했음. DEC-027은 이력에 `stock_seq`를 추가하되 **allocation 현재상태 SSOT는 `t_order_alloc` 유지**. |
| 영향 | 단계 3 DDL. DEC-008 줄 총량과 병행. HOLD ≠ OUT. `available_qty = real_qty - reserved_qty` ([09 §14](./09_production_inventory_flow.md)). Stage 5C 로그 추적은 `stock_seq`+`ref_type`+`ref_id` (DEC-027). 현재상태 SSOT는 계속 `t_order_alloc`. |
| 승인 | 2026-08-17 대표 |

**하위 운영규칙:** 배정해제 기본 순서는 FIFO의 역순인 LIFO. 먼저 잡은 오래된 재고를 유지해 FIFO 출고 원칙을 깨지 않기 위함. 동일 `storage_dt` 정렬은 기존 stock 자연키/row 규칙을 쓰며, 임의 규칙은 이번 단계에서 만들지 않음. 1차 모바일은 자동 FIFO. 향후 수동 재고행 선택은 열어 둠.

최소 추적: `alloc_id` PK, UNIQUE(상세+stock 자연키), `allocated_qty`, `shipped_qty`, 감사컬럼. 같은 키는 한 행 누적.

---

## DEC-019

**선입금의 부분출고별 순차 배분.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 부분출고 시 주문 선입금 잔액을 **판매일 빠른 순(먼저 확정된 판매부터)** 순차 적용한다. 회차별 적용액 = `min(남은 주문 선입금, 그 판매의 판매금액)`. 판매금액 초과 적용 **금지**. 이미 CONFIRMED된 판매·전표를 후속 출고 때문에 다시 쓰지 **않는다**. |
| 폐기된 초안 | 「선입금 전액을 첫 출고 판매에 적용」 — 선입금 30만 · 첫 출고 판매금액 10만이면 성립하지 않는다. |
| 예시 | 주문 30만 · 선입금 15만 → 판매1 10만: 적용 10만, 미수 0, 선입금 잔액 5만 → 판매2 20만: 적용 5만, 미수 15만 |
| 유지 | DEC-009: 주문 단계는 금액(+결제수단, DEC-028)만. 전표는 판매 CONFIRMED 기준. 선수금 계정 설계는 비범위. |
| 선입금 잔액 | `prepay_balance` 컬럼 **신설하지 않음**. 잔액 = `pre_pay_amt − applied_prepay` (`t_cash_ledger.order_no`=주문번호 · CONFIRMED 판매 JOIN). |
| provenance | **CLOSED.** `t_cash_ledger.order_no` NULL=일반수금, 주문번호=출고 선입금 자동적용. 신규 DDL 없음. |
| 영향 | 단계 4 출고 TX (feature 구현 · main 미반영). 관련: DEC-014 · DEC-017 · **DEC-028** · **DEC-029** |
| 승인 | **2026-08-21 대표** |

---

## DEC-020

**출고방식: 저장재고(STOCK) vs 즉시(DIRECT) — 판매유형·전체 업무모델과 구분.**

| | |
|--|--|
| 상태 | **APPROVED** (출고방식 축). 저장 필드·DIRECT TX·전체 5축 모델은 **09·OPEN** |
| 결정 | STOCK: `t_order_alloc`/HOLD 필수, `ship_qty <= allocated - shipped`. DIRECT: allocation 없이 출고·판매 가능. `allocated_qty=0` 정상. **품종으로 분기 금지.** |
| 한계 | STOCK/DIRECT만으로 **전체 판매를 분류하지 않음.** 주문·생산·재고·판매유형은 별도 축 → [09 §1.1](./09_production_inventory_flow.md) |
| 영향 | Stage 3A = STOCK용 배정. Stage 5C = 출고 TX 분기 (DEC-027). 주문 없음+STOCK **거부**. |
| 금지 | DIRECT를 판매유형명으로 사용 · 주문이 있다고 STOCK 강제 |
| OPEN | 출고방식 저장 컬럼·ship payload 필드명 |
| 승인 | 2026-08-19. 2026-08-19 업무모델 재정렬로 범위 명확화 |
| 승인 | 2026-08-19. 2026-08-19 업무모델 재정렬로 범위 명확화 |

---

## DEC-021

**UX: 농부에게 일을 더 만들지 않는다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 중복입력 금지. 생산수량 판매 재입력 금지(A안). 자동(날짜·채번). 선택 단계 강제 화면 금지. Batch 사용자 관리 금지. |
| 영향 | 모바일·PC·생산→판매 연동 설계. [09 §0](./09_production_inventory_flow.md). Stage 6 판매화면 4정책: [04 §9](./04_mobile_screen.md) |
| 승인 | 2026-08-19 대표 논의 반영 |

---

## DEC-022

**수확기록 — 영농일지, 콘테이너 상자, 재고 자동생성 금지.**

| | |
|--|--|
| 상태 | **APPROVED.** OPEN-PROD-02 **CLOSED** |
| 결정 | `t_work_detail` 수확작업. 입력: 일자·품종·**콘테이너 상자 수**. 년도=일자 자동. kg **금지**. 수확 저장 ≠ `t_stock_master` IN. 통계(연/품종/일/전년대비) 목적. |
| DDL 설계 | `variety_cd TEXT` · `harvest_container_qty INTEGER` (convention 준수). **`core/work_harvest_schema.py` 멱등 ALTER** — 로컬/테스트만. 운영 자동실행 금지 |
| PC | `work_log_page` 수확 입력 · `register_raw_material`과 **미연동** |
| 구현 | PC/모바일 영농일지 필드 — **Stage H 완료** (2026-08-19). 통계 화면은 후속 |
| 승인 | 2026-08-19 대표 |

---

## DEC-023

**생산확정 A안 — 바로 판매, 미판매 잔량 자동재고.**

| | |
|--|--|
| 상태 | **APPROVED.** OPEN-PROD-03 **CLOSED** |
| 결정 | 선택: [재고로 저장] / [바로 판매]. **재고로 저장 = 확정 TX 이후 UI reset** (추가 IN 아님). 바로 판매: 생산수량→판매 화면 자동·재입력 금지. 판매 80/생산 100 → **20 자동 상품재고**. 생산 화면에서 80/20 분할 입력 금지. |
| 기술 | **전량 IN**(현 PC) → 판매/출고 확정 시 **OUT** (Stage 5C). partial IN **폐기**. 생산 TX와 판매 TX **분리**. 판매 중단해도 생산재고 유지. rollback 금지. IN/OUT은 내부 처리. 원물 N건·harvest_year 승계는 **DEC-026**. |
| PC | `save_production_log` 전량 IN = 확정안과 **동일**. 바로판매 prefill·OUT **미구현** (후속) |
| 승인 | 2026-08-19 대표 |

---

## DEC-024

**배즙 완제품 재고 단위 = 박스.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 사용자 재고/주문/판매 단위 = **박스**. PC `「포」` 표기는 **생산/재고 확장 단계**에서 UI만 수정. qty 변환 migration **금지** (개수=박스). |
| PC | FR010200 조회○ · PROCESS **미구현** · 표기 「포」 |
| 승인 | 2026-08-19 대표 |

---

## DEC-025

**생산/변환 DB — 기존 구조 최대 활용, 신규 테이블 선행 금지.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | `t_stock_master` · `t_stock_log` · `t_work_*` · 판매/주문 우선. `t_production_master`/`t_production_detail` **생성 안 함**. Batch 사용자 UI·번호 입력 **금지**. 명백한 부족이 구현에서 확인되기 전 신규 생산테이블 **제안 금지**. |
| DDL | 수확만: `variety_cd` + `harvest_container_qty` (DEC-022). 생산/판매는 기존 구조. |
| 승인 | 2026-08-19 대표 |

---

## DEC-026

**재고 harvest_year 의미 및 생산 승계 규칙.**

| | |
|--|--|
| 상태 | **APPROVED** (Accepted) |
| 관련 Stage | 4 (P) · 5A (3A) · 5B · 5C |
| 결정 | `harvest_year`는 **생산(포장)연도가 아니라 원료 과실의 수확연도**. RAW_STOCK: 상품/배즙 = 투입 원물 `harvest_year` 승계. HARVEST: 수확기록 `work_dt` 연도. PROCESS: 원물 승계. 한 생산에서 **다른 harvest_year 혼합 금지**, **다른 품종 원물 혼합 금지** (Core `MIXED_YEAR` / `MIXED_VARIETY`). |
| 이유 | 생산일과 원료 연도는 다를 수 있음. 저장배는 다음 해 포장 가능. 주문 allocation이 `harvest_year`로 재고 탐색 (DEC-018). 상품 traceability 유지. |
| 운영 제약 | 배 재고는 1년 이상 장기보관을 일반 전제로 하지 않음. 다년도 rollover UI **도입하지 않음**. `harvest_year` 필드는 유지. |
| 관련 | DEC-004 (규격에 harvest_year 포함) · DEC-018 (FIFO 키에 harvest_year) · DEC-023 (전량 IN, TX 분리 — 충돌 없음) · DEC-025 (신규 테이블 없음) |
| 승인 | 2026-08-19 대표 (Stage 5B 구현 확정) |

---

## DEC-027

**판매출고 재고 추적 및 STOCK/DIRECT consume 규칙.**

| | |
|--|--|
| 상태 | **APPROVED** (Accepted) |
| 관련 Stage | 5C (규칙 불변). Core+HTTP·Mobile 출고 UX **운영 반영** (`fd963e0`). 선입금·수금은 다음 개발순서 |
| 결정 | 아래 11항. |

1. `t_stock_master.stock_seq`는 **추적키**. 업무 natural key(9필드)를 대체하지 않음. 생산·조회·Allocation은 9필드 유지. UPSERT 후 `stock_seq`는 natural key로 SELECT (lastrowid 금지).
2. CONFIRMED 상품 OUT: **1 `t_sales_detail` = 1 `stock_seq`**. FIFO가 N row면 판매상세 N행. 연결 테이블 없음.
3. STOCK·DIRECT **동일 분할**. 차이는 allocation consume 여부뿐.
4. DRAFT·레거시 `stock_seq` **NULL 허용**. DB NOT NULL/물리 FK 없음. CONFIRMED OUT은 Core가 논리 강제.
5. `t_stock_log`: `stock_seq` + `ref_type` + `ref_id` (NULL 허용). SALE 시 `ref_id` = `sale_detail_no`. remark만으로 이벤트 구분하지 않음.
6. STOCK consume = `t_order_alloc.shipped_qty +=`. `allocated_qty`는 출고로 줄이지 않음. 같은 TX에 `reserved_qty −`, `out_qty +`.
7. 주문 출고 SSOT = `SUM(CONFIRMED t_sales_detail.qty)` by `order_detail_id`. `t_order_detail.out_qty` 사용 금지. DEC-017 1:N 유지.
8. ST01에 **배정상태 금지** (DEC-013). ST010300 = 첫 CONFIRMED 출고 후 **잔량 있는 배송준비**. ST010200 강제 경유 없음.
9. 전량: 모든 줄 `confirmed_shipped == order_qty` → `ST010400` + `stock_status='Y'`. 완료는 `==`(ε). `>=` 금지.
10. 과출고: `confirmed + request <= order_qty` 아니면 거부.
11. 허용: 주문+STOCK / 주문+DIRECT / 주문없음+DIRECT. **거부: 주문없음+STOCK.**

DDL: `core/sales_stock_trace_schema.ensure_sales_stock_trace_schema`. 운영 자동실행 금지. `ensure_order_alloc_schema`와 분리.

| 관련 | DEC-013 · **017** · **018** (HOLD≠OUT, alloc SSOT) · **020** · **026** |
| 승인 | 2026-08-19 대표 |

---

## DEC-028

**주문 선입금 결제수단.**

| | |
|--|--|
| 상태 | **APPROVED** (설계). **이번 작업 DDL 없음** |
| 결정 | 선입금에는 **결제수단**을 함께 받는다. `pre_pay_amt = 0` → 결제수단 **NULL**(입력 UI 노출 안 함). `pre_pay_amt > 0` → 결제수단 **필수**. |
| 전표 | 주문 저장 시 전표·수금줄 **생성 없음** (DEC-009 유지). 판매확정(CONFIRMED) 시 그 결제수단으로 선입금 적용분을 회계 반영. |
| 계정코드 | 선입금은 **실제 받은 돈**이다. 결제수단은 **현금성 자산 계정**만. 판정: `m_account_code.parent_cd='AS0101'` AND `acct_level=4` AND `use_yn='Y'` (운영: AS010101/102/103). **외상매출금·미수금 등 채권계정(`AS02…`)은 선입금 결제수단이 아니다.** `get_account_codes('AS', target_level=4)` 전체를 모바일 결제수단 목록 SSOT로 **확정하지 않는다**. 목록 API는 `prefix=AS0101&level=4` 재사용. 모바일 전용 결제수단 코드 **하드코딩 금지**. |
| 제안 컬럼 | `t_order_master.pre_pay_method_cd TEXT NULL` (권장안. 신규 테이블 없음) |
| 구현 전 확인 (2단계 착수 직전) | ① 운영 `PRAGMA table_info(t_order_master)`로 동일 목적 컬럼 유무 ② 운영 `m_account_code` ③ PC 실제 수금계정 사용분포 → **현금성 계정 범위 확정** 후 ALTER 여부 결정. **이번 문서 작업에서 ALTER·범위 확정하지 않는다.** |
| UI 용어 | 「**결제수단**」 (「수금방법」 금지) |
| 관련 | DEC-009 · DEC-014 · **DEC-019** · DEC-029 |
| 승인 | **2026-08-21 대표** |

---

## DEC-029

**판매상태와 수금상태를 분리한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | `sales_status`는 **`DRAFT` / `CONFIRMED` 두 값만**. `PAID` / `UNPAID` 같은 수금 의미를 `sales_status`에 넣지 **않는다**. |
| 수금상태 | **금액에서 계산**한다. 신규 상태 컬럼 **없음**. API `payment_status`: `UNPAID`/`PARTIAL`/`PAID`/`null`. UI label: 미수/부분수금/수금완료/수금대기. CONFIRMED · `paid<=0` → **UNPAID**(0원 0/0 포함) · `0<paid<total` → **PARTIAL** · `MAX(0,total−paid)<=0` → **PAID**. DRAFT → **null**. (Stage6-0: `core/sales_payment_constants.compute_payment_status`) |
| 완료 개념 3종 | **판매확정** = 그 판매가 CONFIRMED · **주문완료** = `ST010400` + `stock_status='Y'`(전량 출고) · **수금완료** = 그 판매의 미수 0. 세 개념을 하나로 합치지 않는다. |
| 추가수금 | **CONFIRMED 판매만** 가능. DRAFT 판매에 수금·전표를 붙이지 않는다. |
| 이유 | 「판매완료 = 수금완료」로 섞으면 부분수금·미수 관리가 불가능하고 전표 시점이 흐려진다. |
| 영향 | 단계 4·5·6. [02 §8·§12](./02_domain_flow.md) · [03 §4](./03_data_contract.md) · [05 §8](./05_api_contract.md) |
| 승인 | **2026-08-21 대표** |

---

## DEC-030

**신규 일반 수금등록의 pay_dt 유효범위를 확정한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 신규 일반 수금등록(6C write)의 `pay_dt`는 **`sales_dt ≤ pay_dt ≤ today`** 만 허용한다. |
| 거부 | `pay_dt < sales_dt` (판매 이전 수금) · `pay_dt > today` (미래 수금일) |
| 허용 | `pay_dt = sales_dt` · `sales_dt < pay_dt ≤ today` |
| 선입금 자동적용 | Stage4 기존 정책 유지 — cash `pay_dt` = 판매 생성 시점 `sales_dt` |
| legacy | 기존 DB row는 **수정/삭제/자동보정하지 않음**. 조회만 허용 |
| 회계 날짜 | `t_cash_ledger.pay_dt` = 실제 수금일 · `t_ledger.trans_dt` = `sales_dt`. DEC-030 때문에 `trans_dt`를 `pay_dt`로 바꾸지 않음 |
| 적용 범위 | **6C POST write validation** · Core `add_payment` / `source_order_no=None` · **APPROVED · IMPLEMENTED** |
| 이유 | 미래 수금일은 미발생 데이터 · 판매 이전 일반수금은 판매 수금 흐름과 불일치 · 주문 선입금은 별도 경로 |
| 영향 | [02 §8.7](./02_domain_flow.md) · [03 §4](./03_data_contract.md) · [05 §8](./05_api_contract.md) · Stage6C |
| 승인 | **2026-08-23 대표** |

---

## DEC-031

**출고로 생성된 CONFIRMED 판매는 PC에서 read-only로 취급한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | `sales_status='CONFIRMED'` AND (`t_sales_master.order_no` OR `t_sales_detail.order_detail_id` OR `t_sales_detail.stock_seq` 실값) → PC `SalesPage` full-save·삭제·수금 mutation **금지** |
| 판정 | UI flag만 신뢰 금지. `load_sales_data` + `execute_full_save`/`delete_sales_data` 직전 DB 재확인 |
| 제외 | DRAFT · 일반 PC 직접판매(CONFIRMED·추적키 없음) |
| 정정 | 별도 취소/정정 절차만 (이번 범위 아님) |
| 구현 | **APPROVED · IMPLEMENTED** · Stage7A private main merge(`82dba73`) · `core/pc_sales_provenance.py` |
| 영향 | [03 §4](./03_data_contract.md) · [08 A13+](./08_pc_change_scope.md) · PC `SalesPage` |
| 승인 | **2026-08-23 대표** |

---

## DEC-032

**PC 수금은 append-only로 통일한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 기존 수금 **수정/삭제 금지** · 신규 일반수금만 append · Core = `SalesPaymentService` · DEC-030 동일 |
| Stage7A | protected 판매 수금 등록/수정/삭제 버튼 disable (full-save 경유 차단) |
| 구현 | **Stage7B 예정** (PC 수금 UI → `SalesPaymentService` append) |
| 영향 | [08 A13](./08_pc_change_scope.md) · PC `SalesPage` 수금 탭 |
| 승인 | **2026-08-23 대표** |

---

## OPEN-PROD (CLOSED — 2026-08-19 대표 최종승인)

설계 확정. Stage H/P/5B/5C·출고 UX **운영 반영** (`fd963e0` 계열). 잔여 OPEN은 [06](./06_development_progress.md).

| ID | 상태 | 확정 내용 | 후속 구현 |
|----|------|-----------|-----------|
| OPEN-PROD-01 | **CLOSED** | 추적 = `work_id` + `t_stock_log`. `t_production_*` 없음 | 구현 중 부족 확인 전 테이블 제안 금지 |
| OPEN-PROD-02 | **CLOSED** | 영농일지. DDL `variety_cd TEXT` + `harvest_container_qty INTEGER` | **Stage H 구현 완료** — 운영 ALTER는 별도 승인 |
| OPEN-PROD-03 | **CLOSED** | 전량 IN → 판매/출고 OUT. TX 분리. partial IN 폐기 | StockPage 바로판매 prefill · 공통 OUT TX |

상세: [09 §5·§9](./09_production_inventory_flow.md).

---

## 상태 요약

| ID | 상태 |
|----|------|
| DEC-001 ~ 014, **017, 018, 019, 020 ~ 027, 028, 029, 030, 031, 032** | APPROVED 또는 CLOSED. 020 **저장 필드**만 OPEN |
| DEC-015, 016 | **OPEN** |
| **OPEN-PROD-01~03** | **CLOSED** (설계·Core 반영됨. 상세 현황은 [06 현재 운영 기준](./06_development_progress.md)) |

2026-08-21 갱신: **DEC-019 APPROVED**(선입금 순차 배분) · **DEC-028 신규 APPROVED**(주문 선입금 결제수단) · **DEC-029 신규 APPROVED**(판매상태 ≠ 수금상태). DEC-016은 계속 OPEN이며 이번에 승인하지 않았다.  
2026-08-23 갱신: **Stage7A private main merge**(`82dba73`) · **DEC-031 IMPLEMENTED** · DEC-032 **Stage7B 예정**.

### 스키마 확인 (2026-08-22)

| 항목 | 확인 내용 |
|------|-----------|
| `t_order_master.pre_pay_method_cd` | **완료 · 운영** (DEC-028) |
| `t_cash_ledger.order_no` provenance | **CLOSED** — NULL=일반수금, 주문번호=선입금 자동적용. Stage4 DDL 0 (DEC-019) |
| 선입금 결제수단 계정 범위 | `parent_cd=AS0101` · level4 · `use_yn=Y`. 채권(`AS02…`) 제외 (DEC-028) |
