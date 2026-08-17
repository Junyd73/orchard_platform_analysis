# 07. Decisions

상태: `APPROVED` | `PROPOSED` | `OPEN` | `REJECTED` | `SUPERSEDED`

- **APPROVED**: 대표 확정. 구현 시 이 규칙을 따른다. (DDL·코드는 단계 승인 후)
- **PROPOSED / OPEN**: 미확정. APPROVED와 섞어 확정으로 읽지 말 것.

승인일 표기: 대표 검토 반영일 **2026-08-17**. 단계 0 **최종승인 완료** (2026-08-17 대표). 단계 0은 다시 열지 않음.

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
| 영향 | 단계 2. 재고 검증은 배정 API에서만. |
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
| 결정 | `variety_cd` × `weight` × `grade_cd` × `size_cd` × `qty` × `unit_price` × `harvest_year`. 신규 규격 테이블 없음. |
| 이유 | 기존 PC·재고 키와 동일해야 Hold/출고가 맞는다. |
| 영향 | 주문 줄·재고 매트릭스·판매 상세 |
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

**주문 단계 선입금은 금액만 기록한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 주문접수 시 `pre_pay_amt`만. `t_cash_ledger` / `t_ledger` 생성 금지. 판매확정(CONFIRMED) 시 입금·미수·수금·전표를 판매 기준으로 반영. 선수금 회계는 이번 범위 밖(별도 확장). |
| 이유 | 현재 PC도 주문 경로 전표가 없고, 발생주의 전표는 판매 확정과 맞춘다. |
| 영향 | 단계 2·6. DEC-D |
| 승인 | 2026-08-17 대표 |

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
| 상태 | **OPEN** |
| 결정 | 없음. 추측 코드값 만들지 않음. |
| 확인된 사실 | [02](./02_domain_flow.md) §ST01. 시드 SQL 없음. 저장은 `'10'`. 콤보는 `ST01` 로드. 영농일지가 `ST010300` 등을 폴백 사용. |
| 필요 | 운영 DB `m_common_code WHERE parent_cd='ST01'` read-only 조회. |
| 영향 | 단계 2 저장값. 신규 코드 추가 금지 원칙 유지. |

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
| 상태 | **APPROVED** (논리 분리). 코드값 매핑은 DEC-011 OPEN. |
| 결정 | 주문상태 = 접수/완료/취소(문서 의미). 이행상태 = 미배정/부분배정/배정완료/출고완료(계산). 이행용 **새 컬럼·새 ST01 코드 추가 금지**. 계산식은 [02](./02_domain_flow.md). |
| 이유 | 배정 진행을 주문 취소와 한 코드로 섞으면 선주문을 표현할 수 없다. |
| 영향 | UI 배지 두 개. `status_cd`는 주문상태만. `stock_status`·`allocated_qty`·판매연결은 이행 계산. |
| 승인 | 2026-08-17 대표 (DEC-B) |

---

## DEC-014

**소매 출고확정은 재고 이동과 판매 생성을 하나의 DB 트랜잭션으로 한다.**

| | |
|--|--|
| 상태 | **APPROVED** |
| 결정 | 배정수량 검증 → reserved− → out+ → stock log → 이행/주문상태 → `t_sales_master/detail` → `order_no`/`order_detail_id` 연결 → 배송 연결. 한 단계라도 실패하면 rollback. 금지: 재고만 감소, 판매만 생성, 주문 완료인데 판매 없음. |
| 이유 | 부분 성공 시 장부·재고가 복구 불능에 가깝다. |
| 영향 | 단계 4. 출고 TX에서 판매는 `CONFIRMED`. `pre_pay_amt>0`이면 **같은 TX**에서 판매 수금 바구니 + `sync_ledger_by_basket('SALE', …)`. 선수금 계정 설계는 하지 않음 (DEC-009). **출고 1회 = 판매 1건** (DEC-017). 부분출고 시 선입금 금액 배분은 DEC-019. |
| 승인 | 2026-08-17 대표 (DEC-C) |

---

## DEC-015

**기존 HOLD → `allocated_qty` / `t_order_alloc` 백필.**

| | |
|--|--|
| 상태 | **OPEN** |
| 결정 | 무조건 0 금지. 운영 HOLD/`reserved_qty` 점검 후 migration에서 `allocated_qty` 및 `t_order_alloc` 백필 여부 결정. 현재 로그로는 행 복원이 어려울 수 있음. |
| 이유 | 이미 전량 Hold된 주문에 0을 넣으면 미배정으로 보이며 이중 Hold 가능. |
| 영향 | 단계 3 직전 운영 점검 체크리스트. |

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

전량 출고: 모든 주문상세 `shipped_qty == qty` → `stock_status='Y'`, 이행상태=출고완료. 주문상태 완료 매핑은 DEC-011 `ST01` 확인 후.

---

## DEC-018

**재고행 allocation은 전용 `t_order_alloc`(가칭). `t_stock_log`는 이력이며 현재상태 SSOT가 아니다.**

| | |
|--|--|
| 상태 | **APPROVED** (설계). **CREATE TABLE 금지.** 실제 테이블명은 구현 시 네이밍 대조. |
| 결정 | 줄↔stock 자연키 배정은 `t_order_alloc`. 자동배정 **FIFO**(`storage_dt ASC`). 배정해제 **LIFO**(최근 잡은 행부터). 출고 소비 **FIFO**. 로그에 allocation SSOT용 컬럼을 억지로 넣지 않음. 향후 HOLD/CANCEL_HOLD/OUT에는 가능한 범위에서 `order_no`/`order_detail_id`/`sales_no`/stock 자연키를 이력으로 남길 수 있음. 현재상태 복원은 `t_order_alloc`, 감사 이력은 `t_stock_log`. |
| 근거 | 현재 로그에 `wh_cd`/`storage_dt`/`order_detail_id` 없음 → 행 복원 불가. |
| 영향 | 단계 3 DDL. DEC-008 줄 총량과 병행. |
| 승인 | 2026-08-17 대표 |

**하위 운영규칙:** 배정해제 기본 순서는 FIFO의 역순인 LIFO. 먼저 잡은 오래된 재고를 유지해 FIFO 출고 원칙을 깨지 않기 위함. 동일 `storage_dt` 정렬은 기존 stock 자연키/row 규칙을 쓰며, 임의 규칙은 이번 단계에서 만들지 않음. 1차 모바일은 자동 FIFO. 향후 수동 재고행 선택은 열어 둠.

최소 추적: `order_no`, `order_detail_id`, stock 자연키(`farm_cd, wh_cd, item_cd, variety_cd, grade_cd, size_cd, weight, harvest_year, storage_dt`), `allocated_qty`, `shipped_qty`, 생성/수정 감사정보. PK/UNIQUE는 구현 전 schema 대조.

---

## DEC-019

**선입금의 부분출고별 배분.**

| | |
|--|--|
| 상태 | **OPEN** |
| 결정 | 없음. 단계 4 출고 TX 구현 전 확정. |
| 문제 | 현재 초안은 선입금 전표를 첫 출고에만 넣는다고 적혀 있었다. 선입금 30만 · 첫 출고 판매금액 10만이면 첫 판매에 30만 전액을 붙일 수 없다. |
| 권장 원칙 (미확정) | 각 출고 판매에 적용하는 선입금 ≤ 해당 판매금액. 남은 선입금은 다음 출고 판매에 순차 적용. |
| 유지 | DEC-009: 주문 단계는 `pre_pay_amt` 금액만. 전표는 판매 CONFIRMED 기준. 선수금 계정 설계는 비범위. |
| 영향 | 단계 4. 단계 1을 막지 않음. 단계 0을 다시 열지 않음. |

---

## 상태 요약

| ID | 상태 |
|----|------|
| DEC-001 ~ 010, 012 ~ 014, **017, 018** | APPROVED |
| DEC-011, 015, 016, **019** | OPEN (단계 1을 막지 않음. 011→단계2 전, 015→단계3 전, 019→단계4 전, 016→단계6 전) |
