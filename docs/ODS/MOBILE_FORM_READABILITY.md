# 모바일 폼 가독성 — Project A 적용 규칙

> ODS PDF(`mobile/docs/ODS/ODS_v1.0.pdf`) **원본은 수정하지 않는다.**  
> 본 문서는 대표님 실기·논의로 확정한 **현장 적용 보완 기준**이다.  
> 버전: 1.0 · 2026-07 · SCR-002 기본정보부터 적용

---

## 확정 규칙

| 항목 | 기준 |
|------|------|
| 입력 라벨 | **16px 이상**, SemiBold/Bold(**600~700**), 진한 본문색 `#2D3748` (`--ods-color-text-label`) |
| 라벨–입력 간격 | **8~10px** (`--ods-form-label-gap` = 8px) |
| 입력값 | **17~18px**, Medium(500) |
| Placeholder | **16px**, Regular, 보조색 |
| 도움말·검증 | **13px 이상** |
| 필수/선택 | 필수 `*`, 선택 `(선택)` 명시. 조건부 필수는 도움말로 설명 |
| 컨트롤 높이 | 최소 **52px** (`--ods-control-height`) |
| 필드 세로 간격 | **20~24px** (`--ods-form-field-gap` = 24px) |
| 관찰일자 | **오늘(로컬) 이하만** (`max` + 검증). 문구: 「관찰일자는 오늘까지만 허용됩니다.」 (ODS v1.1.1) |

## 구현 위치

- 토큰: `src/design-system/tokens.css`
- 컴포넌트: `OdsFormField`, `OdsInput variant="form"`, `OdsSelect variant="form"`
- `variant="default"`(기본값)은 SCR-001 등 **기존 화면 유지**

## 적용 범위

- 우선: SCR-002 기본정보 (`ObservationNewView`)
- 이후 등록형 폼에 동일 규칙 재사용
- ODS 승인 PDF·SCR 레이아웃 구조는 임의 변경하지 않음
