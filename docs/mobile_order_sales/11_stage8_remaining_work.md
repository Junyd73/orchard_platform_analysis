# 11. Stage 8 남은 일

**역할:** ③ 추출. **아직 남은 일만.** 완료 기능 반복 금지. 입력: [10](./10_stage8_integration_checklist.md) 재분류 + OPS READ ONLY (2026-09-20).

**조사 기준:** local 문서 작업 중 · 코드 `origin/main` **`63abc6e`** = **OPS backend SHA**. 코드/DDL/deploy 변경 없음.

## OPS 실측 (남은 일에서 제외하는 것)

아래는 **이미 OPS에 있음**. 11에 “DDL 적용/백엔드 배포”로 넣지 않음.

- backend **`63abc6e`**, orchard-api **active**
- `t_order_alloc` · `allocated_qty` · `pre_pay_method_cd`
- `t_sales_detail.stock_seq` · `t_stock_log.stock_seq/ref_type/ref_id`
- `t_harvest_consumption`
- `t_auction_ship_*` · match/discrepancy/return
- OpenAPI: auction (candidates/cancel/finalize/reopen) · `fruit-stock/initial` · allocations · sales/payments
- juice **신규 DDL 없음**

미수행: OPS 화면 클릭 스모크. PC exe는 **현재 운영 범위 아님** (`DEFERRED — PC NOT IN USE`). ④ 통합회귀(2026-09-20)는 아래 R01~R06.

## Remaining 표

| ID | 분류 | 항목 | 코드 상태 | OPS 상태 | 필요한 조치 | 선행조건 | 위험도 | Stage8 |
|----|------|------|-----------|----------|-------------|----------|--------|--------|
| R01 | OPS_DEPLOY_OR_VERIFY | 주문→출고→판매→수금 스모크 | git `63abc6e` 구현 | **PASS** · isolated unittest(주문·배정·출고·판매·수금·stock OUT). OPS write 없음 | 운영 클릭 스모크는 별도 | backup | **HIGH** | **REQUIRED** |
| R02 | OPS_DEPLOY_OR_VERIFY | 경매 핵심 스모크 | 동상 | **PASS** · AUCTION `rep_weight`=shipment/match spec(`WEIGHT`). stale 0.0 assertion 정합. extra OUT 없음. 정산 실조회 없음 | 운영 클릭 스모크는 별도 | 정산/realtime 소스 · backup | **HIGH** | **REQUIRED** |
| R03 | OPS_DEPLOY_OR_VERIFY | 배즙 주문·initial 스모크 | 동상 · DDL 없음 | **PASS** · leaf initial/중복차단/FR010200 거부 + 주문·생산 unittest. OPS write 없음 | 운영 클릭 스모크는 별도 | 배즙 재고/QT01 | **MEDIUM** | **REQUIRED** |
| R04 | OPS_DEPLOY_OR_VERIFY | 재고 available 정합 | in−out−reserved | **PASS** · stock/ship unittest. copy 스냅샷 FR010201/202 각 available 50. OPS 클릭 교차 없음 | 운영 수치 스모크는 별도 | R01/R02 데이터 | **HIGH** | **REQUIRED** |
| R05 | OPS_DEPLOY_OR_VERIFY | backup / rollback | deploy 스크립트 존재 | **PASS** · `backups/orchard_20260920.db` 6094848 · 로컬 copy+restore rehearsal integrity/schema/count 일치. 운영 DB rollback 없음 | 운영 복원 금지 유지 | SSH | **HIGH** | **REQUIRED** |
| R06 | OPS_DEPLOY_OR_VERIFY | mobile dist SHA 마커 | `build-info.json` · deploy.log | **PASS / DEPLOY-VERIFIED** · runtime `8db4b99` · `/build-info.json` source_sha 일치 · dist.bak_20260920100733 | 종료. docs-only 재배포 없음 | — | **LOW** | **REQUIRED** |
| R07 | POLICY_OPEN | F-4 반품/수금 reverse | **미구현** (reopen은 reject) | — | 정책 결정 전 코딩 금지 | 대표 결정 | **MEDIUM** | **CAN-DEFER** |
| R08 | POLICY_OPEN | DEC-016 경매 `t_sales_delivery` | finalize에 INSERT **없음** | — | 생성 여부 결정 | 대표 결정 | **LOW** | **CAN-DEFER** |
| R09 | POLICY_OPEN | OPEN-DONE | DONE≠잔량만 확정 | — | 최종 의미 필요 시에만 | 대표 결정 | **LOW** | **CAN-DEFER** |
| R10 | POLICY_OPEN | DEC-015 HOLD 백필 | 백필 코드 없음 · DDL은 이미 OPS | alloc 테이블 **존재** | 백필 여부. **재ALTER 아님** | preflight SQL | **LOW** | **CAN-DEFER** |
| R11 | POLICY_OPEN | DEC-020 저장 필드 | STOCK/DIRECT 동작 · 컬럼 OPEN | — | 필드명 필요 시에만 | 대표 결정 | **LOW** | **CAN-DEFER** |
| R12 | POLICY_OPEN | 경매 수수료/운송 차감 | finalize gross | — | 차감 0 유지 vs 정책 | 대표 결정 | **LOW** | **CAN-DEFER** |
| R13 | POLICY_OPEN | OPEN-DATA-NEG-STOCK | 음수 로트 비후보 | 운영 이관 전 | 운영 음수 로트 여부 조회만 | READ ONLY SQL | **LOW** | **CAN-DEFER** |
| R14 | DOC_ALIGNMENT | 05 경매 REST 없음 등 | 코드/OpenAPI와 불일치 | 라우트 존재 | 05 CURRENT API 갱신 | 문서 게이트 | **MEDIUM** | **CAN-DEFER** |
| R15 | DOC_ALIGNMENT | 09 PROCESS/경매출하 미구현 | leaf·경매 구현 | 테이블 존재 | 09 CURRENT | 문서 게이트 | **MEDIUM** | **CAN-DEFER** |
| R16 | DOC_ALIGNMENT | 01/03 경매 미적용 | git+OPS 테이블 | DDL 존재 | 01/03 층 분리 | 문서 게이트 | **MEDIUM** | **CAN-DEFER** |
| R17 | DOC_ALIGNMENT | 04 경매 화면 없음 | Auction*Sheet | dist 동 배포창 | 04 CURRENT 화면 | 문서 게이트 | **LOW** | **CAN-DEFER** |
| R18 | DOC_ALIGNMENT | 02 vs 06 alloc · 08 DEC-028 DDL | — | **alloc·pre_pay OPS 존재** | 08 stale · 06 미확인 해소 반영 | 문서 게이트 | **MEDIUM** | **CAN-DEFER** |
| R19 | PC_FOLLOWUP | HARVEST N:M PC 화면 보완 | Core 위임됨 | **DEFERRED — PC NOT IN USE**. Stage 8 remaining/blocker **제외** | 현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류 | PC 재사용 게이트 | **LOW** | **CAN-DEFER** |
| R20 | PC_FOLLOWUP | PC CONFIRMED read-only 운영 PC | git 구현 (7A) | **DEFERRED — PC NOT IN USE**. Stage 8 remaining/blocker **제외** | 현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류 | PC 재사용 게이트 | **MEDIUM** | **CAN-DEFER** |
| R21 | PC_FOLLOWUP | PC 수금 append-only 운영 PC | git 구현 (7B) | **DEFERRED — PC NOT IN USE**. Stage 8 remaining/blocker **제외** | 현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류 | PC 재사용 게이트 | **MEDIUM** | **CAN-DEFER** |
| R22 | PC_FOLLOWUP | PC SalesPaymentService 공용화 확인 | sales_page 호출 코드 | **DEFERRED — PC NOT IN USE**. Stage 8 remaining/blocker **제외** | 현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류 | PC 재사용 게이트 | **LOW** | **CAN-DEFER** |
| R23 | PC_FOLLOWUP | legacy AUCTION_RT 정리 | 경로 **존재** | **DEFERRED — PC NOT IN USE**. Stage 8 remaining/blocker **제외** | 현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류 · 삭제 금지 | PC 재사용 게이트 | **LOW** | **CAN-DEFER** |
| R24 | PC_FOLLOWUP | PC 경매 UI | 없음 · Mobile SSOT | **DEFERRED — PC NOT IN USE**. Stage 8 remaining/blocker **제외** | 현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류 | PC 재사용 게이트 | **LOW** | **CAN-DEFER** |
| R25 | PC_FOLLOWUP | 3B 모바일 배정 UI | API만 | — | DEC-021 후순위. **PC 보류 결정에 포함하지 않음** (모바일 독립) | A12 API | **LOW** | **CAN-DEFER** |
| R26 | USER_FEATURE | 경매조회 | **DESIGN APPROVED** · [12](./12_today_auction_design.md) | — | 판매관리 5탭 `경매` · `/orders?tab=auction` · `GET /api/v1/market-auctions`. 우선순위 **P1**. **Stage 8 blocker 아님** | 대표 최종 승인 (2026-09-20) | **MEDIUM** | **NOT-STAGE8** |

**IMPLEMENTATION_INCOMPLETE (코딩 게이트):** 없음. F-4/DEC-016/3B는 정책·후순위.

중복 없음. 완료 기능(주문 CRUD, HARVEST N:M DDL, auction 테이블, juice initial 라우트 등)은 표에 넣지 않음.

**PC (2026-09-20):** R19~R24는 **CAN-DEFER 유지**. 사유=현재 PC 미사용 · 대표 결정으로 재사용 시점까지 개발 보류. **Stage 8 remaining/blocker에서 제외.** PC 프로그램은 폐기하지 않는다. 현재 사용하지 않으므로 후속 개발을 보류하며, 향후 사용 필요 시 당시 최신 Core·DB·업무정책을 기준으로 재조사 후 별도 승인 절차로 개발을 재개한다. PC 후속 개발 보류는 Mobile/PWA 및 Server 운영·개발의 blocker가 아니다.

**R25**는 3B 모바일 배정 UI(DEC-021). PC 기능이 아니며 이번 PC 보류에 **포함하지 않음**. 기존 독립 CAN-DEFER 유지.

**R26** 경매조회: 분류 `USER_FEATURE` · 우선순위 **P1** · 상태 **DESIGN APPROVED**. Stage 8 remaining/blocker **아님**. Stage 8 **FINAL PASS 불변**. R25·PC DEFERRED 미변경.

## ④ 통합회귀 (2026-09-20)

지시서 번호 ↔ 본 표: ④R01=표R01+R04 · ④R02=표R03 · ④R03 HARVEST(표 외, unittest) · ④R04=표R02 · ④R05=표R05 · ④R06=표R06.

| 지시서 | 표 | 상태 |
|--------|----|------|
| ④ R01 주문→출고→판매→재고 | R01+R04 | PASS |
| ④ R02 배즙 | R03 | PASS |
| ④ R03 HARVEST→생산 | (표 ID 없음) | PASS |
| ④ R04 경매 | R02 | PASS |
| ④ R05 backup/rollback | R05 | PASS |
| ④ R06 dist | R06 | PASS / DEPLOY-VERIFIED |

Preflight: OPS backend `63abc6e` · api active · integrity ok · 대상 테이블/컬럼 존재. 운영 mutation/DDL/deploy/push 없음.

Copy: `C:\Users\junyd\AppData\Local\Temp\orchard_stage8_ro\orchard_20260920.db` size 6094848 · integrity ok. restore `restored_rehearsal.db` 동 size · schema_equal · counts `t_order_master` 30 / `t_sales_master` 1 / `t_stock_master` 14 / `t_auction_ship_master` 2 / `t_harvest_consumption` 4 / `t_order_alloc` 0. copy 스냅샷 juice FR010201/202 available 50, FR010200 stock 0.

Server: order/alloc/ship/stock/sales 470 OK. ④R04 재실행(2026-09-20): `rep_weight` 계약=finalize `t_sales_detail.weight`=spec + `COALESCE(detail.weight, match.spec_weight)`. stale expect 0.0만 `WEIGHT`(7.5)로 정합. production code 미변경. 단일 test OK · `test_auction_complete_api` 22 OK · auction 184 OK · `test_sales_query_service` 38 OK · 생산/HARVEST/경매 unittest OK. `test_non_return_no_extra_out_or_sale_log` · RETURN only IN 유지.

Mobile vitest 599 중 2 FAIL 모두 `AiAnalysisPanel.spec.ts`(관찰 AI). Stage8 무관. vue-tsc + `build:staging` OK.

R06 close (2026-09-20): runtime deploy SHA **`8db4b997fd4e2108fe8eb88a8d1ddc00d90d7244`**. `GET /build-info.json` `{app:orchard-mobile, source_sha:8db4b99…, build_mode:staging}`. OPS backend git SHA 동일. `backups/deploy.log` append-only. dist.bak **`/var/www/orchard/mobile/dist.bak_20260920100733`**. GET smoke: orders/fruit-stock/sales/auction-shipments 200. 화면: 홈·주문·재고(상품/배즙)·경매출하 UI·판매 조회. 업무 write 없음. DDL 없음. docs-only commit은 재배포하지 않음.

Stage 8 **기능 통합회귀: PASS** (R01~R05). **배포 추적성: PASS / DEPLOY-VERIFIED** (R06). **Stage 8 FINAL PASS.** PC DEFERRED·R26 DESIGN APPROVED는 FINAL PASS·Mobile 운영을 바꾸지 않음.

## 실행순서

| 순 | 단계 | blocker |
|----|------|---------|
| 1 | OPS READ ONLY preflight | **본 단계에서 SHA/DDL/라우트 완료.** 재실행은 스모크 직전 재확인만 |
| 2 | 누락 DDL/배포 항목 확정 | **신규 ALTER/백엔드 배포 blocker 아님** (`63abc6e`·테이블 존재). 남음=R06 선택 |
| 3 | 문서 정합 (01~09) | **Stage8 스모크 blocker 아님** (R14–R18 CAN-DEFER). 테스터 혼선만 MEDIUM |
| 4 | Stage8 통합회귀 | **blocker: R05 backup.** 그다음 R01–R04 |
| 5 | 운영 smoke | R01–R04. 정산 API 장애 시 R02만 부분 HOLD |
| 6 | PC 후속 R19–R24 | **Stage 8 remaining/blocker 아님.** `DEFERRED — PC NOT IN USE`. 재사용 시 별도 게이트 |
| 7 | 3B 모바일 배정 UI (R25) | PC와 무관. DEC-021 후순위 CAN-DEFER 유지 |
| 8 | 경매조회 (R26) | **Stage 8 blocker 아님.** DESIGN APPROVED. 구현은 별도 게이트 |

```
preflight(완료) → backup 확인(R05) → 통합회귀 스모크(R01–R04)
 → (병렬 가능) 문서 정합(R14–R18) · 정책(R07–R13) · R25 3B(모바일, PC 아님) · R26 DESIGN APPROVED
 → PC R19–R24는 Stage 8 remaining/blocker 제외 (재사용 시 별도 게이트)
```
