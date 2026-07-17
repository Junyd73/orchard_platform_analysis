# -*- coding: utf-8 -*-
"""Whitelist 기반 Analysis 저장소 동기화.

Usage (repo root):
  python scripts/mirror/sync_to_analysis.py
  python scripts/mirror/sync_to_analysis.py --target ..\\orchard_platform_analysis
  python scripts/mirror/sync_to_analysis.py --dry-run

환경 변수 MIRROR_TARGET 으로 기본 대상 경로 지정 가능.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.mirror._manifest import collect_mirror_pairs  # noqa: E402
from scripts.mirror._rewrite import rewrite_mirror_text, should_rewrite_dest  # noqa: E402
from scripts.mirror.preflight import run_preflight  # noqa: E402

_DEFAULT_TARGET = _REPO_ROOT.parent / "orchard_platform_analysis"


def _copy_pair(repo_root: Path, target_root: Path, src_rel: str, dest_rel: str) -> None:
    src = repo_root / src_rel
    dest = target_root / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if should_rewrite_dest(dest_rel) and src.suffix.lower() in {
        ".vue",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".css",
    }:
        raw = src.read_text(encoding="utf-8")
        dest.write_text(rewrite_mirror_text(raw), encoding="utf-8", newline="\n")
    else:
        shutil.copy2(src, dest)


def sync(
    repo_root: Path,
    target_root: Path,
    *,
    dry_run: bool = False,
    skip_preflight: bool = False,
) -> int:
    pairs = collect_mirror_pairs(repo_root)
    if not pairs:
        print("[sync] 동기화할 파일이 없습니다.", file=sys.stderr)
        return 1

    src_files = [s for s, _ in pairs]
    if not skip_preflight:
        code = run_preflight(repo_root, src_files)
        if code != 0:
            print("[sync] preflight 실패 — 복사를 중단합니다.", file=sys.stderr)
            return code

    target_root.mkdir(parents=True, exist_ok=True)
    print(f"[sync] target: {target_root}")
    print(f"[sync] files: {len(pairs)}")

    for src_rel, dest_rel in pairs:
        line = f"  {src_rel} -> {dest_rel}"
        if dry_run:
            print(line)
            continue
        _copy_pair(repo_root, target_root, src_rel, dest_rel)
        print(line)

    if dry_run:
        print("[sync] dry-run done (no files copied)")
    else:
        print("[sync] done - review git diff in Analysis repo, then commit.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analysis 미러 동기화")
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.environ.get("MIRROR_TARGET", str(_DEFAULT_TARGET))),
        help="Analysis 저장소 루트",
    )
    parser.add_argument("--repo", type=Path, default=_REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true", help="점검 생략(비권장)")
    args = parser.parse_args()
    return sync(
        args.repo.resolve(),
        args.target.expanduser().resolve(),
        dry_run=args.dry_run,
        skip_preflight=args.skip_preflight,
    )


if __name__ == "__main__":
    raise SystemExit(main())
