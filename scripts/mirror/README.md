# Analysis 미러 도구

Private `orchard_platform` → 공개 `orchard_platform_analysis` 선별 동기화.

정책: 저장소 루트 [`MIRROR_POLICY.md`](../../MIRROR_POLICY.md)

## 요구 사항

- Python 3.11+
- PyYAML (`server/.venv` 권장)

```powershell
cd C:\orchard_platform
server\.venv\Scripts\python.exe scripts\mirror\preflight.py
```

## 절차

```powershell
# 1. Analysis 클론 (최초 1회)
git clone https://github.com/Junyd73/orchard_platform_analysis.git ..\orchard_platform_analysis

# 2. Push 전 점검 (실패 시 exit 1)
server\.venv\Scripts\python.exe scripts\mirror\preflight.py

# 3. 동기화 (dry-run)
server\.venv\Scripts\python.exe scripts\mirror\sync_to_analysis.py --dry-run

# 4. 실제 복사
server\.venv\Scripts\python.exe scripts\mirror\sync_to_analysis.py --target ..\orchard_platform_analysis

# 5. Analysis에서 커밋
cd ..\orchard_platform_analysis
git add -A
git status
git commit -m "feat(mobile): Project A ODS·생육관찰 UI 미러"
git push
```

## 파일

| 파일 | 설명 |
|------|------|
| `manifest.yaml` | Whitelist·경로 매핑 |
| `preflight.py` | Push 전 민감정보 점검 |
| `sync_to_analysis.py` | 선별 복사 |
| `_manifest.py` | manifest 파서 |

## 환경 변수

- `MIRROR_TARGET` — Analysis 저장소 경로 (기본: `../orchard_platform_analysis`)
