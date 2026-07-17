# Analysis 미러 도구

Private `orchard_platform` → 공개 `orchard_platform_analysis` 선별 동기화.

정책: 저장소 루트 [`MIRROR_POLICY.md`](../../MIRROR_POLICY.md)

## 기본 방식 (권장)

로컬 폴더는 **`orchard_platform` 하나만** 사용한다.

1. Private `main` 에 push  
2. GitHub Actions `Sync whitelist to analysis` 가  
   `preflight` → whitelist 복사 → Analysis `main` 커밋·푸시  

필수 Secret (Private 저장소):

- `TARGET_REPO_TOKEN` — Analysis 저장소 push 권한 PAT

수동 실행: GitHub → Actions → Sync whitelist to analysis → Run workflow

## 로컬 수동 (비상용만)

상시로 `../orchard_platform_analysis` 를 두지 않는다. 필요 시 임시 클론만 사용한다.

```powershell
cd C:\orchard_platform
server\.venv\Scripts\python.exe scripts\mirror\preflight.py

$tmp = Join-Path $env:TEMP "orchard_platform_analysis"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
git clone --depth 1 https://github.com/Junyd73/orchard_platform_analysis.git $tmp
server\.venv\Scripts\python.exe scripts\mirror\sync_to_analysis.py --target $tmp
# $tmp 에서 검토·commit·push 후 폴더 삭제
```

## 파일

| 파일 | 설명 |
|------|------|
| `manifest.yaml` | Whitelist·경로 매핑 |
| `preflight.py` | 민감정보 점검 |
| `sync_to_analysis.py` | 선별 복사 |
| `_manifest.py` | manifest 파서 |
| `../../.github/workflows/sync_to_analysis.yml` | CI 자동 미러 |

## 환경 변수

- `MIRROR_TARGET` — (수동 시) Analysis 체크아웃 경로
