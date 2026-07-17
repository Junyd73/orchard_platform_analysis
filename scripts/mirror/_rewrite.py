# -*- coding: utf-8 -*-
"""Analysis 미러 복사 시 import 경로 치환."""

from __future__ import annotations

_REWRITE_PAIRS: tuple[tuple[str, str], ...] = (
    ("@/features/", "@/views/"),
    ("@/shared/stores/", "@/composables/stores/"),
    ("@/shared/constants/", "@/composables/constants/"),
    ("@/shared/obsDraft", "@/composables/obsDraft"),
    ("@/shared/mediaUrl", "@/utils/mediaUrl"),
    ("@/shared/photoCardLabel", "@/utils/photoCardLabel"),
    ("@/shared/fileInput", "@/utils/fileInput"),
    ("@/shared/layouts/", "@/layouts/"),
)

_TEXT_SUFFIXES = {".vue", ".ts", ".tsx", ".js", ".jsx", ".css"}


def should_rewrite_dest(dest_rel: str) -> bool:
    norm = dest_rel.replace("\\", "/")
    return norm.startswith("mobile/src/")


def rewrite_mirror_text(content: str) -> str:
    out = content
    for old, new in _REWRITE_PAIRS:
        out = out.replace(old, new)
    return out
