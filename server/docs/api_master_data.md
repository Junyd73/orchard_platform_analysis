# 기준정보 조회 API (SQLite 읽기 전용)

현재 마스터 조회는 PyQt 원본 `orchard_platform.db`를 **읽기 전용**으로 사용한다.  
PostgreSQL은 `/health/db` 연결 확인만 사용한다.

## URL

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/farms/{farm_cd}` | 농장 상세 |
| GET | `/api/v1/farms/{farm_cd}/sites` | 필지 목록 |
| GET | `/api/v1/farms/{farm_cd}/sites/{site_id}` | 필지 상세 |
| GET | `/api/v1/common-codes` | 공통코드 목록 |

## Query Parameter

### `GET /api/v1/farms/{farm_cd}/sites`
| 이름 | 타입 | 기본 | 설명 |
|------|------|------|------|
| `active_only` | bool | `true` | `true`이면 `use_yn='Y'`만 |

### `GET /api/v1/common-codes`
| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `farm_cd` | string | Y | — | 농장 코드 |
| `parent_cd` | string | Y | — | 부모 코드 (예: `WT01`) |
| `active_only` | bool | N | `true` | `true`이면 `use_yn='Y'`만 |

## 응답 예시

### 농장 상세 `200`
```json
{
  "farm_cd": "OR001",
  "farm_nm": "예시농장",
  "owner_nm": "홍길동",
  "address": "주소",
  "lat": 36.1,
  "lon": 128.2,
  "nx": 1,
  "ny": 2,
  "reg_dt": "2026-01-01 00:00:00"
}
```

### 필지 목록 `200`
```json
[
  { "site_id": "SITE01", "site_nm": "1구역", "use_yn": "Y" }
]
```

### 공통코드 `200`
```json
[
  {
    "farm_cd": "OR001",
    "code_cd": "WT0101",
    "code_nm": "맑음",
    "parent_cd": "WT01",
    "use_yn": "Y"
  }
]
```

## 오류 코드

| HTTP | error_code | 상황 |
|------|------------|------|
| 404 | `ENTITY_NOT_FOUND` | 농장/필지 없음 |
| 409 | `DATA_INTEGRITY_ERROR` | 무결성 오류 |
| 500 | `REPOSITORY_ERROR` | Repository/DB 오류 |
| 422 | (FastAPI) | 필수 Query 누락 |

오류 본문 예:
```json
{
  "detail": "Farm not found",
  "error_code": "ENTITY_NOT_FOUND"
}
```

내부 DB 경로·SQL은 응답에 포함되지 않는다.

## active_only 정책

- 기본값 `true`
- `m_farm_site.use_yn = 'Y'`
- `m_common_code.use_yn = 'Y'`
- 모든 조회에 `farm_cd` 필터 적용

## 실행 예시

```bash
curl http://127.0.0.1:8000/api/v1/farms/OR001
curl "http://127.0.0.1:8000/api/v1/farms/OR001/sites?active_only=true"
curl "http://127.0.0.1:8000/api/v1/common-codes?farm_cd=OR001&parent_cd=WT01"
```
