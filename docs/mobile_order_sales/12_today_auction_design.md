# 12. 경매조회 — UX · READ API 설계

**상태:** **DESIGN APPROVED** (2026-09-20 대표 최종 승인). **미구현.**  
**기능명/탭명:** `경매`  
**성격:** 판매관리 5번째 탭에서 지정 날짜의 **경매 결과**를 조회한다. 출고·수금 업무와 섞지 않는다.

**금지:** DDL/settlement 스키마 변경 승인 아님. 후보매칭 API 재사용 금지. 등급·과수 추정 금지. 사용자가 source(실시간/정산)를 구분하게 하지 않음.

Stage 8 **FINAL PASS**와 무관. 구현은 **R26** ([11](./11_stage8_remaining_work.md)).

### SUPERSEDED (같은 날 초안)

아래는 **폐기**. 구현에 쓰지 않는다.

- 기능명 `오늘의 경매`
- 판매관리 4탭 + 헤더 아래 진입 카드
- 독립 route `/orders/auction-today`
- 전용 뷰 `features/market/AuctionTodayView.vue`
- 화면의 당일 경매 / 정산완료 / 진행중 badge
- 카드형 결과 리스트
- PC식 이전/다음 페이지

---

## 확정

### 사용자 목적

지정한 날짜의 가락(기본) **배** 경매 결과를 빠르게 본다. 기본 진입 = **오늘**.

### private 경로 (CURRENT)

analysis mirror `views/orders`를 private에 강제하지 않는다.

| 역할 | 경로 |
|------|------|
| 하단 5메뉴 | `mobile/src/components/ods/OdsBottomNav.vue` — **변경 없음** |
| 판매관리 탭 SSOT | `mobile/src/features/orders/ordersConstants.ts` (`ORDER_SALES_SEGMENT_OPTIONS`) |
| 경매 탭 화면 | **`mobile/src/features/orders/OrderView.vue`** (같은 파일, `?tab=auction`) |
| 탭 query | 기존 `applyTabQuery` (`pack_prod`/`stock`/`order`/`sales`)에 `auction` 추가 |
| 라우터 | `mobile/src/router/index.ts` — `/orders` 유지. **신규 path 없음** |
| 시장/청과 lookup | `GET /api/v1/auction-markets`, `GET /api/v1/auction-corporations` |
| 실시간 | `core/market_price_manager.py` `MarketPriceManager` |
| 과거 원본 | `MarketSettlementManager.fetch_sale_data` (1차 katSale) |
| 후보매칭 (재사용 금지) | `…/auction-shipments/{id}/auction-candidates` |

신규(미구현) 후보: `mobile/src/api/marketAuctions.ts`, `server/app/routers/market_auctions.py`.

---

## 1. 탭 / 화면 구조

하단 5메뉴 유지.

판매관리 탭 **5개:**

`포장/생산` · `재고` · `주문` · `판매` · **`경매`**

- `경매` 클릭 → **같은 OrderView**에서 경매조회 표시
- URL: **`/orders?tab=auction`**
- 탭 값 후보: `TAB_AUCTION = 'auction'`
- 별도 진입카드 · 경매 홈 · 독립 route **없음**
- 1차 **상세 화면 없음**

한 화면 구성 (위→아래):

1. **조회조건** — 항상 펼침
2. **요약** 3지표
3. **경매조회 결과** compact list
4. **더보기** (있을 때만)

제목: `경매결과 {total_count}건` (천단위 콤마). 예: `경매결과 1,135건`

---

## 2. 조회조건

From–To **없음**. 단일 **조회일자**.

| 필드 | 기본 | 규칙 |
|------|------|------|
| 조회일자 | 오늘 (KST) | 미래일 선택 금지 |
| 시장 | 가락 `110001` | lookup 목록 |
| 청과법인 | 전체 | |
| 산지 | 전체 | |
| 품종 | 전체 | |

품목 **배** (`06-02`) 고정 — **UI 비노출**.

버튼: **조회하기** · **초기화**  
초기화 = 오늘 / 가락 / 전체 / 전체 / 전체.

편의:

- 경매 탭 진입 시 **오늘 조건으로 자동 조회**
- 조회하기 = cache bypass에 해당하는 **최신 조회**
- 자동 polling **없음**

---

## 3. 용어

| 사용 | 의미 |
|------|------|
| 시장 | `whsl_mrkt_*` |
| 청과법인 | `corp_*` |
| 산지 | `plor_*` (표시 축약 가능, 원본 보존) |
| 품종 | `gds_sclsf_*` / `corp_gds_vrty_nm` |
| 규격 | `unit_qty` + `unit_nm` |
| 경매수량 | 박스 |
| 경매중량 | kg |
| 경락가 | 원/박스 |
| 경매금액 | 원 |
| 경매시각 | `scsbd_dt` |

쓰지 않음: 판매중량/판매수량/판매금액/평균단가/회사/출하지.  
사용자 문구에서 쓰지 않음: 당일 경매, 정산 데이터, 진행중, 정산완료.

**1차 공통 리스트에서 등급·과수 제외.** 당일 원본에 없어도 추정하지 않음.

---

## 4. source (서버만)

사용자는 source를 보지 않는다. 지정 날짜의 **경매 결과**만 본다.

| 조회일자 | 서버 source |
|----------|-------------|
| 오늘 KST | `katRealTime2/trades2` |
| 과거 | `katSale` 원본 READ |

`source_type`은 서버 로그/디버그용. **모바일 기본 UI 비노출.**

---

## 5. 요약 · 계산

요약은 **필터 전체** 기준 (현재 페이지가 아님).

| 지표 | 단위 |
|------|------|
| 총 경매수량 | 박스 |
| 총 경매중량 | kg |
| 총 경매금액 | 원 |

**오늘 (realtime):**

```
box    = qty
weight = qty × unit_qty
amount = qty × scsbd_prc    # 원본 totprc 없음. 계산값.
```

**과거 (katSale):** 원본 계약 우선.

```
weight = unit_tot_qty       # kg
box    = unit_tot_qty / unit_qty   # 정수일 때만
amount = totprc
```

박스 비정수는 해당 행 박스 생략 · 중량·금액만 (OPEN-BOX-QTY). 반올림 추정 금지.

---

## 6. 리스트 UX

카드 반복 **금지**. 구분선 compact list.

한 거래 예:

```
14:28  한국청과㈜                    1,040,000원
화성시 · 신고 · 15kg
20박스 · 300kg  |  경락가 52,000원
```

필수: 경매시각 · 청과법인 · 산지 · 품종 · 규격 · 경매수량 · 경매중량 · 경락가 · 경매금액.

시장은 필터에 있으므로 행마다 반복하지 않음.

산지 표시: `경기도 화성시` → `화성시` 축약 가능. **원본 `origin_name`은 응답에서 유지.**

정렬: **경매시각 DESC**.

0건: `선택한 날짜의 경매 데이터가 없습니다`  
오류: 기존 결과 **유지 가능** + 재시도. 빈 화면으로 지우지 않음이 기본.

---

## 7. 대량 · paging

하루 1,000건 이상 가능.

| | 계약 |
|--|------|
| `page_size` | 기본 **50** |
| 최초 | 50건 |
| 더보기 | 다음 페이지 append |
| 필터/조회하기/초기화 | **1페이지부터** |
| PC 이전/다음 | **없음** |

응답: `page`, `page_size`, `has_more` (또는 `paging` 객체). `total_count`는 필터 전체 건수.

---

## 8. READ API

```
GET /api/v1/market-auctions
```

`/auction-markets`와 같이 farm 스코프 없음. path `/today` 없음.

### Query

| 이름 | 기본 | 비고 |
|------|------|------|
| `trade_date` | 오늘 | `YYYY-MM-DD`, 미래일 서버 거부 |
| `market_cd` | `110001` | |
| `item_cd` | `06-02` | UI 없음 |
| `corporation_cd` | — | 안정 식별. 소스에 코드 없으면 명칭 파라미터 OPEN |
| `origin` / `origin_cd` | — | `plor_cd` 우선 |
| `variety` | — | |
| `refresh` | `0` | `1` = cache bypass (조회하기) |
| `page` | `1` | 1-base |
| `page_size` | `50` | |

### Response (모바일)

`spm_no`, `auctn_seq`는 서버 identity. **UI 불필요 → 비노출.**

```json
{
  "trade_date": "2026-09-18",
  "fetched_at": "2026-09-18T14:45:33+09:00",
  "cache_hit": false,
  "stale": false,
  "market_cd": "110001",
  "market_name": "가락",
  "total_count": 1135,
  "summary": {
    "auction_box_qty": 0,
    "auction_weight_kg": 0,
    "auction_amount": 0
  },
  "page": 1,
  "page_size": 50,
  "has_more": true,
  "items": [
    {
      "trade_date": "2026-09-18",
      "auction_time": "2026-09-18 14:28:00",
      "corporation_cd": "11000105",
      "corporation_name": "한국청과㈜",
      "origin_cd": "410000",
      "origin_name": "경기도 화성시",
      "origin_label": "화성시",
      "variety_cd": "01",
      "variety_name": "신고",
      "unit_qty": 15,
      "unit_nm": "kg",
      "qty": 20,
      "auction_weight_kg": 300,
      "auction_price": 52000,
      "auction_amount": 1040000
    }
  ]
}
```

`source_type`은 응답에 넣더라도 화면 미사용. 넣지 않는 쪽을 우선.

오류: `{detail, error_code}`. 외부 실패를 0건으로 위장하지 않음.

Realtime fetch는 `spm_no`/`auctn_seq`/`scsbd_dt`/`mdfcn_dt`/`plor_*`/`qty`/`unit_*`/`scsbd_prc`/시장·법인·품종을 포함. 기존 `REALTIME_SELECTABLE_FIELDS`만으로는 부족.

서버 키 후보: `trade_date + market_cd + corp_cd + spm_no + auctn_seq` (DDL 없음).

---

## 9. cache

Server memory cache. DB 적재 없음.

| | 계약 |
|--|------|
| TTL | **60초** (PC 초기값. 공식 주기 아님) |
| 설정 | `ORCHARD_MARKET_AUCTION_CACHE_TTL_SEC` |
| 키 | `trade_date + market_cd + item_cd` (필터 전 raw) |
| 필터·page | cache 위 메모리 slice |
| 조회하기 | `refresh=1` |
| polling | 없음 |
| 탭 진입 | 자동 1회 (오늘) |

장애: TTL 안 캐시가 있으면 기존 결과 유지 + 오류 토스트. TTL 밖은 오류·재시도. 목록을 빈 화면으로 지우지 않음.

---

## 10. 과거일 데이터

화면 계약에 산지·경매금액이 있으므로 **katSale 원본 READ (B)**.  
`market_price_settlement` (A)는 산지·totprc 없음 → 이 화면 1차 SSOT 아님. DDL 없음.

---

## 11. OPEN / 확정 구분

**확정:** 5탭 `경매`, `OrderView` + `?tab=auction`, 조회일자 단일, 필터 5필드(품목 숨김), compact list, 더보기 50, 사용자 source 비구분, 등급·과수 1차 제외, API `GET /api/v1/market-auctions`, 당일 계산식, 과거 katSale, cache 60초, 상세화면 없음.

| ID | OPEN |
|----|------|
| OPEN-TODAY-AUTH | `X-User-Id` 필수 여부 |
| OPEN-TODAY-ORIGIN-MATCH | 산지 필터 = 코드 vs 시/군 문자 |
| OPEN-CORP-ID | `corporation_cd` 없는 소스 시 명칭 키 |
| OPEN-BOX-QTY | 정산 행 박스 비정수 표시 |
| OPEN-TAB-LABEL | 360px 5탭 라벨 말줄임 |
| OPEN-TTL-TUNE | 60초 실사용 후 조정 |
| OPEN-MARKET-ANALYSIS | 이후 시장분석 확장 위치 |

---

## 12. 비범위

- 하단 메뉴 변경, 독립 `/orders/auction-today`, 진입 카드
- 경매 상세 화면 (1차)
- 출하 경락매칭
- PC 시세, settlement DDL
- 당일 등급·과수 보정
- 자동 polling, push/deploy
