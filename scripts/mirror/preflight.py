# -*- coding: utf-8 -*-
"""Analysis 미러 Push 전 보안·민감정보 점검.

Usage (repo root):
  python scripts/mirror/preflight.py
  python scripts/mirror/preflight.py --paths mobile/src server/app/schemas

exit 0: 통과
exit 1: 차단 항목 발견 → Push 중단
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.mirror._manifest import collect_mirror_files, is_relaxed_preflight_path, load_manifest  # noqa: E402

# 파일명·경로 차단
_BLOCKED_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\.env", re.I),
    re.compile(r"\.env\.", re.I),
    re.compile(r"\.(db|sqlite)$", re.I),
    re.compile(r"(keystore|credential|secret)", re.I),
)

# 내용 스캔 (실제 비밀값 — 환경변수 *이름* 문자열은 허용)
# ENV 이름 예: ENV_API_KEY = "OPENAI_API_KEY"  → 통과
# 실제 키 리터럴(sk- / ghp_ 등)만 차단
_CONTENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*['\"]"
            r"(sk-|rk-|AIza|ghp_|github_pat_)[A-Za-z0-9_\-]{8,}"
        ),
        "api key / token",
    ),
    (
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*['\"]"
            r"[A-Za-z0-9_\-]{32,}"
        ),
        "api key / token",
    ),
    (re.compile(r"(?i)password\s*[=:]\s*['\"]?[^\s'\"#]{4,}"), "password"),
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9_\-\.]{20,}"), "bearer token"),
    (re.compile(r"\b\d{6}-\d{7}\b"), "주민번호 형식"),
    (re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"), "휴대폰 번호"),
)

# 사설 IP (문서·코드 내 하드코딩)
_PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})\b"
)

# 운영·내부 URL 의심
_INTERNAL_URL = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.)",
    re.I,
)

# 바이너리 확장자 (내용 스캔 스킵)
_BINARY_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ico", ".woff", ".woff2"})

# 자기 자신·패턴 정의 파일은 내용 키 검사 제외 (정규식 예시 오탐 방지)
_SKIP_CONTENT_RELS = frozenset({"scripts/mirror/preflight.py"})

# 대용량 이미지 (관찰 실사진 의심, KB)
_MAX_IMAGE_BYTES = 48 * 1024


def _is_blocked_path(path: Path) -> str | None:
    name = path.name
    for pat in _BLOCKED_NAME_PATTERNS:
        if pat.search(name):
            return f"차단 파일명: {name}"
    return None


def _scan_text(rel: str, text: str, *, relaxed: bool = False) -> list[str]:
    issues: list[str] = []
    for pat, label in _CONTENT_PATTERNS:
        if pat.search(text):
            issues.append(f"{rel}: {label}")
    if relaxed:
        return issues
    if _PRIVATE_IP.search(text):
        issues.append(f"{rel}: 사설 IP")
    if _INTERNAL_URL.search(text):
        issues.append(f"{rel}: 내부/로컬 URL")
    if re.search(r"(?i)SQLITE_DB_PATH\s*=", text) or re.search(
        r"[A-Za-z]:\\.*orchard_platform\.db", text
    ):
        issues.append(f"{rel}: 운영 DB 경로")
    return issues


def _scan_file(repo_root: Path, rel: str, *, relaxed: bool = False) -> list[str]:
    path = repo_root / rel
    if not path.is_file():
        return []

    blocked = _is_blocked_path(path)
    if blocked:
        return [f"{rel}: {blocked}"]

    ext = path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        rel_posix = rel.replace("\\", "/")
        if not rel_posix.startswith(("mobile/docs/", "docs/")):
            size = path.stat().st_size
            if size > _MAX_IMAGE_BYTES:
                return [f"{rel}: 대용량 이미지 ({size} bytes) — 실사진 의심"]

    if ext in _BINARY_EXT:
        return []

    rel_posix = rel.replace("\\", "/")
    if rel_posix in _SKIP_CONTENT_RELS:
        return []

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError as exc:
        return [f"{rel}: 읽기 실패 ({exc})"]

    return _scan_text(rel, raw, relaxed=relaxed)


def run_preflight(repo_root: Path, paths: list[str] | None = None) -> int:
    manifest = load_manifest()
    files = paths if paths is not None else collect_mirror_files(repo_root)
    if not files:
        print("[preflight] 동기화 대상 파일이 없습니다. manifest를 확인하세요.", file=sys.stderr)
        return 1

    issues: list[str] = []
    for rel in sorted(files):
        relaxed = is_relaxed_preflight_path(rel, manifest)
        issues.extend(_scan_file(repo_root, rel, relaxed=relaxed))

    if issues:
        print("[preflight] Push 차단 — 다음 항목을 제거하거나 manifest에서 제외하세요:", file=sys.stderr)
        for item in issues:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(f"[preflight] 통과 ({len(files)} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analysis 미러 Push 전 점검")
    parser.add_argument(
        "--paths",
        nargs="*",
        help="점검할 상대 경로(미지정 시 manifest whitelist 전체)",
    )
    parser.add_argument("--repo", type=Path, default=_REPO_ROOT, help="Private repo root")
    args = parser.parse_args()
    return run_preflight(args.repo.resolve(), args.paths)


if __name__ == "__main__":
    raise SystemExit(main())
