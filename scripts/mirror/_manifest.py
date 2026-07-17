# -*- coding: utf-8 -*-
"""manifest.yaml 로드 및 mirror 대상 파일 수집."""

from __future__ import annotations

import fnmatch
from pathlib import Path

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.yaml"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML이 필요합니다. server/.venv Python으로 실행하거나 pip install pyyaml"
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _expand_src_glob(repo_root: Path, pattern: str) -> list[Path]:
    pattern = pattern.replace("\\", "/").strip()
    if pattern.endswith("/**"):
        base = pattern[:-3]
        root = repo_root / base
        if not root.exists():
            return []
        return [p for p in root.rglob("*") if p.is_file()]
    # 단일 파일
    p = repo_root / pattern
    return [p] if p.is_file() else []


def _map_dest(src_rel: str, src_pattern: str, dest_pattern: str) -> str:
    src_pattern = src_pattern.replace("\\", "/")
    dest_pattern = dest_pattern.replace("\\", "/")
    src_rel = src_rel.replace("\\", "/")

    if src_pattern.endswith("/**") and dest_pattern.endswith("/**"):
        src_base = src_pattern[:-3]
        dest_base = dest_pattern[:-3]
        if src_rel.startswith(src_base + "/"):
            return dest_base + src_rel[len(src_base) :]
        if src_rel == src_base:
            return dest_base
    return dest_pattern


def _excluded(rel_posix: str, exclude_globs: list[str]) -> bool:
    for g in exclude_globs:
        g = g.replace("\\", "/")
        if fnmatch.fnmatch(rel_posix, g):
            return True
    return False


def load_manifest(manifest_path: Path | None = None) -> dict:
    path = manifest_path or _MANIFEST_PATH
    return _load_yaml(path)


def is_relaxed_preflight_path(rel_posix: str, manifest: dict | None = None) -> bool:
    manifest = manifest or load_manifest()
    globs = list(manifest.get("preflight_relaxed_globs") or [])
    rel_posix = rel_posix.replace("\\", "/")
    return _excluded(rel_posix, globs)


def collect_mirror_pairs(repo_root: Path, manifest_path: Path | None = None) -> list[tuple[str, str]]:
    """(private_rel, analysis_rel) 목록."""
    manifest = load_manifest(manifest_path)
    includes = manifest.get("include") or []
    exclude_globs = list(manifest.get("exclude_globs") or [])

    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    for entry in includes:
        if not isinstance(entry, dict):
            continue
        src_pat = str(entry.get("src") or "").strip()
        dest_pat = str(entry.get("dest") or src_pat).strip()
        if not src_pat:
            continue
        for abs_path in _expand_src_glob(repo_root, src_pat):
            rel = abs_path.relative_to(repo_root).as_posix()
            if _excluded(rel, exclude_globs):
                continue
            dest = _map_dest(rel, src_pat, dest_pat)
            if rel not in seen:
                seen.add(rel)
                pairs.append((rel, dest))

    return sorted(pairs, key=lambda x: x[0])


def collect_mirror_files(repo_root: Path, manifest_path: Path | None = None) -> list[str]:
    return [src for src, _ in collect_mirror_pairs(repo_root, manifest_path)]
