# 02. Domain flow — 업무 흐름

> 상태: 단계 0 · 설계 수정 / 최종승인 대기.  
> 범례: **현재** = 오늘 PC 코드 · **확정** = 대표 APPROVED · **OPEN** = 미확정.

---

## 1. 세 경로 (확정 운영)

### 1.1 소매 주문

```
주문접수 (재고 0 허용, allocated_qty=0, 판매 없음)
 → 포장대기 / 이행=미배정
 → 재고배정 (부분 가능)
 → 출고대기
 → 배송 또는 방문수령
 → 출고확정 TX: reserved→out + 판매 생성 + 연결
 → 수금/미수 (판매 CONFIRMED 기준 전표)
```

### 1.2 가락시장

```
포장재고 (FR010100)
 → 실시간 경매 (시세 화면)
 → AUCTION_RT + DRAFT 판매 (재고 미차감 — 현재와 동일)
 → 경매결과 확인
 → 확정 TX: CONFIRMED + 재고 출고 (+ 선택 수금)
 → 정산
```

근거: `market_price_page.py` `save_realtime_auction_draft` (마스터·상세만).  
확정 함수는 **현재 없음** → PC/core 보완 (DEC-010).

### 1.3 수출 / 일반도매

```
포장재고
 → 판매 직접 등록 (주문 없음)
 → 출고/판매확정 (재고와 판매가 어긋나지 않게 한 TX 권장)
 → 수금
```

원황 수출은 이 경로. `sales_tp` 문서값 `RETAIL`/`WHOLE` — 주문 경로는 `'NORMAL'`. 운영 코드값은 `m_common_code`와 대조.

---

## 2. 선주문 (DEC-002 APPROVED)

재고 0:

```
주문등록 성공
 → qty = 주문수량
 → allocated_qty = 0
 → 미배정 = qty
 → reserved_qty 변경 없음
 → t_sales_* 없음
```

**현재:** `StockMatrixPopup`은 가용 ≤ 0이어도 담을 수 있다. 저장 시 `reserved_qty += 주문수량` 전량 Hold. 재고 행이 없으면 `INSERT OR IGNORE` 후 Hold.

**문제:** 없는 재고까지 reserved가 올라간다. 줄 단위 100/30/70을 남기지 못한다.

**확정:** 주문 등록은 재고 부족으로 거부하지 않는다. Hold는 배정 시에만.

---

## 3. 부분배정 (DEC-003, DEC-008 APPROVED)

예: 주문 100 · 가용 30

| 필드 | 값 |
|------|----|
| `qty` | 100 |
| `allocated_qty` | 30 |
| 미배정 (계산) | 70 |
| `t_stock_master.reserved_qty` | +30 |

추가 포장 후 `allocated_qty`를 70·100까지 증가시킬 수 있다.  
제약: `0 <= allocated_qty <= qty`. 증분 배정은 **트랜잭션 안에서** 가용재고를 재조회한 뒤만 허용 (초과예약 금지).

**현재:** 컬럼 없음. Hold = 주문수량 전체.

---

## 4. 출고 조건

출고하려는 수량은 **반드시 해당 줄의 미출고 배정수량 이하**.

```
ship_qty <= allocated_qty - already_shipped_qty
already_shipped_qty = SUM(t_sales_detail.qty WHERE order_detail_id = 줄)
```

미배정 수량만 있는 주문/줄은 출고 **거부** (409).

---

## 5. 출고확정 — 소매 단일 트랜잭션 (DEC-014 APPROVED)

한 DB 트랜잭션. 어느 한 단계라도 실패하면 **전체 rollback**.

1. 주문상세 현재 배정수량·미출고분 검증
2. `reserved_qty` 감소 (`ship_qty`)
3. `out_qty` 증가 (`ship_qty`)
4. `t_stock_log` `OUT` (판매출고 remark, 생산 원물소모와 문구 구분)
5. 주문/이행 관련 필드 갱신 (`stock_status`, 필요 시 `status_cd`, `sales_no`)
6. `t_sales_master` 생성 (`sales_source=ORDER`, `sales_status=CONFIRMED`, `order_no` 연결)
7. `t_sales_detail` 생성 (`order_detail_id` 연결)
8. 주문↔판매 연결 (`t_order_master.sales_no`, 상세 키)
9. 배송: `t_order_delivery` → `t_sales_delivery` (택배 분할 규칙은 기존 PC)

금지 상태:

- 재고만 빠지고 판매 없음
- 판매만 생성되고 재고 미차감
- 주문은 완료인데 판매 없음

**출고 후 `allocated_qty`:** 줄의 **배정 누적**으로 유지한다. 출고 시 0으로 되돌리지 않는다.  
이유: 0으로 내리면 미배정으로 오인되고 이중 배정된다.  
재고 Hold 잔량 = `allocated_qty - already_shipped`. 출고 시 stock `reserved_qty`만 줄인다.

선입금 전표: 주문 시점 없음 (DEC-009). 출고로 판매가 CONFIRMED가 되면, `pre_pay_amt>0`인 경우 **같은 TX**에서 판매 수금 바구니 + `sync_ledger_by_basket('SALE', …)` 로 입금·미수를 맞춘다. 선수금 전용 계정 설계는 하지 않음.

**현재:** 주문은 reserved만 증감. `out_qty` 불변. `stock_status='Y'` 세팅 코드 없음. 판매 저장은 `t_stock_master` 미갱신.

---

## 6. 가락 확정 트랜잭션 (DEC-010 APPROVED)

방향: `DRAFT → CONFIRMED` + 재고 출고를 **한 트랜잭션**.

권장 순서:

1. 대상이 `AUCTION_RT` + `DRAFT`인지 검증
2. 줄 수량만큼 **트랜잭션 안**에서 가용(`in-out-reserved`) 재조회
3. 부족 시 전체 rollback (409)
4. `out_qty +=`, log `OUT`
5. `sales_status=CONFIRMED`
6. 선택 수금 → ledger
7. 배송행: 초안에 없음 → DEC-016 OPEN. 없으면 확정 후 송장이 비어 운영 공백.

현재 구조상 바로 묶기 어려운 점:

| 갭 | 영향 | 보완 |
|----|------|------|
| confirm 함수 없음 | DRAFT 재저장해도 전표 스킵 | core `SalesConfirmService` 신설, PC 버튼 연결 |
| 초안이 reserved를 안 씀 | 확정 순간 재고가 다른 소매 배정과 경합 | TX 내 가용 재검증 필수 |
| 초안 무배송 | 출고와 송장 분리 | DEC-016 |
| 주문/`allocated_qty` 없음 | 해당 없음 | 가락은 판매 경로만 |

---

## 7. 주문상태와 이행상태 (DEC-013 APPROVED, DEC-011 OPEN)

동일 개념으로 취급하지 않는다. **새 상태코드·새 컬럼을 임의로 추가하지 않는다.**

### 7.1 논리 상태 (문서 의미)

**주문상태:** 접수 · 완료 · 취소  
**이행상태:** 미배정 · 부분배정 · 배정완료 · 출고완료

UI 예: `주문상태: 접수` / `재고상태: 부분배정`

### 7.2 현재 ST01 사용 상태 (소스 확인분)

| 항목 | 확인 결과 |
|------|-----------|
| 코드 정의 시드/DDL | 저장소에 **없음** |
| 코드관리 | `CodeManager.get_common_codes('ST01')` → `m_common_code` |
| 주문화면 콤보 | 필터·상세 모두 ST01 (`order_page.py` 1067, 1194–1195행). 주석: 예약접수, 예약확정, 취소 등 — **주석일 뿐 실코드 아님** |
| 실제 저장 | 신규 INSERT `status_cd='10'` 고정. 수정 UPDATE에 `status_cd` 없음. 콤보 무시 |
| 일괄확정/취소 | 버튼 있음, **미연결** |
| 영농일지 폴백 | `ST010300` 배송준비(진행), `ST010400` 완료, `ST010500` 취소 — **일지 구데이터**. 주문과 코드 공간 혼재 위험 |
| 운영 DB 목록 | **이 환경에서 미확인** |

**운영 DB 확인 필요.** 추측해서 ST01 값을 만들지 않는다.

### 7.3 이행상태를 기존 구조로 표현

새 컬럼 없이 계산 (주문 헤더 집계):

| 이행상태 | 계산 (확정 설계) |
|----------|------------------|
| 미배정 | `SUM(allocated_qty)=0` 이고 출고 없음 |
| 부분배정 | `0 < SUM(allocated_qty) < SUM(qty)` 또는 줄 간 불균등. 일부 출고여도 전량 출고 전이면 여기 |
| 배정완료 | 전 줄 `allocated_qty = qty` 이고 전량 출고 전 |
| 출고완료 | 전량 출고 (`stock_status='Y'` 또는 출고수량 = `SUM(qty)`) |

보조 필드:

- `t_order_master.stock_status` 현재 `'N'`/`'Y'`. `'Y'` 전환 코드 없음 → 출고완료 플래그로 **재사용** (DEC 이행 컬럼 신설 안 함).
- `t_stock_status` 테이블은 baseline에만 있고 **Python 미사용**. 이번 설계에서 쓰지 않음.

### 7.4 기존 코드 매핑 가능 여부

| 논리 | 매핑 |
|------|------|
| 주문 접수/완료/취소 | ST01 실코드 **운영 DB 확인 필요**. 확인 전 신규 저장은 당분간 `'10'` 유지 가능하나 필터는 깨진 상태 |
| 이행 4종 | ST01에 넣지 **않음**. `allocated_qty` + `stock_status` + 판매상세 수량으로 계산 |
| `'10'` | 공통코드와 불일치 가능성. ST01에 `'10'`이 없으면 폐기 후보 (PC A) |

부족할 경우 **최소 변경 제안** (승인 전 구현 금지):

1. 이행은 계산값 유지 (컬럼 추가 없음) — **1차 권고**
2. 주문상태만 ST01 기존 3~4개 코드에 매핑. 없으면 대표와 코드관리 화면으로 **기존 체계 안에서** 추가 (임의 하드코딩 금지)
3. `status_cd='10'` 리터럴 제거

---

## 8. 판매 상태

**현재:** `sales_status` `DRAFT` \| `CONFIRMED`, `sales_source` `ORDER` \| `AUCTION_RT`.

- 신규 판매화면 기본 CONFIRMED. 경매 초안 DRAFT.
- DRAFT→CONFIRMED 버튼 없음.
- 주문 경로 INSERT는 두 컬럼을 안 넣음 → DEFAULT `CONFIRMED`/`ORDER` 추정. 전표는 안 남김.

**확정:**

| 경로 | 생성 시 | 확정 |
|------|---------|------|
| 소매 출고 | 출고 TX에서 CONFIRMED + 전표(선입금 복사 시) | 출고와 동일 TX |
| 가락 | 기존 DRAFT+AUCTION_RT | confirm TX (DEC-010) |
| 수출/도매 | CONFIRMED (또는 임시 DRAFT — 추가 OPEN 없음, 1차는 CONFIRMED) | 출고 포함 TX |

새 status 문자열(`SHIPPED` 등) 추가 금지.

---

## 9. 취소

| 경우 | 재고 | 판매 | 회계 | 주문 |
|------|------|------|------|------|
| 미배정 주문 취소 | 변경 없음 (`allocated_qty=0`) | 없음 | 없음 | 주문상태=취소 |
| 일부배정 · 출고 전 | `CANCEL_HOLD`로 해당 reserved 해제, `allocated_qty→0` | 없음 | 없음 | 취소 |
| 배정완료 · 출고 전 | 잔여 Hold 전량 해제 | 없음 | 없음 | 취소 |
| 출고 후 판매취소 | `out_qty` 복구 필요. 단순 DELETE 금지 | 취소/역분개 | `t_ledger` 역분개 필요. 현재 `delete_sales_data`는 전표·재고 미처리 | 주문 완료 유지 또는 별도 정책 |

1차 권고: 출고 후 취소는 **비활성**. 운영 정책은 단계 6 승인 사항.

**현재 주문 삭제 함수 없음.**

---

## 10. 배송

| 코드 | 의미 (코드 주석) | 동작 |
|------|------------------|------|
| `LO010100` | 방문/직접인도 | 주소 비필수 |
| `LO010200` | 택배 | 박스 1개씩 `t_sales_delivery` 분할 |
| `LO010300` | 화물 · 경매 초안 기본 | |
| `LO010400` | 직배 | 주소 레이어 |

주문: `t_order_delivery`. 주석 `t_dlvry_detail`은 **실제 테이블 아님**.  
출고예정일: 배송 `planned_dt` 집계. 마스터 전용 컬럼 추가하지 않음.

채번: 주문 배송 실제 `{order_detail_id}-P{NN}` vs 워크스페이스 규칙 `{detail}-{3자리}` — 코드 우선.

---

## 11. 날짜 (DEC-012 APPROVED)

- **신규 저장:** `order_dt`, `sales_dt` = `YYYY-MM-DD`. 값은 `today_ops` (KST 업무일).
- **기존 데이터:** 일괄 변환하지 않음. 주문 경로는 `YYYYMMDD` 혼재.
- **조회:** 8자리면 하이픈 삽입, 이미 ISO면 그대로. API 응답은 ISO만.
- 시각 감사필드: `now_ops_str`.

---

## 12. 선입금 (DEC-009 APPROVED)

주문접수: `pre_pay_amt`만. `t_cash_ledger`/`t_ledger` 없음.  
판매확정: 입금액·미수·수금줄·전표는 판매 기준.  
선수금 회계는 비범위.

---

## 13. 재고가 생기는 시점 (참고)

| 이벤트 | 테이블 | 수량 |
|--------|--------|------|
| 원물 입고 (신고 저장) | `FR010300` `in_qty` | 20kg 단위 |
| 선별 생산 | 상품 `FR010100` `in_qty` +, 원물 `out_qty` + | 박스 |
| 폐기/실사 | `out_qty` / in·out 재기록 | — |
| 배정 | `reserved_qty` +, `allocated_qty` + | 박스 |
| 배정 해제 | reserved −, allocated − | 박스 |
| 출고확정 | reserved −, out + | 박스 (`allocated_qty` 유지) |

원황/조생은 원물 입고 없이 상품 `in_qty`만 실사/생산으로 올릴 수 있음 (운영).
