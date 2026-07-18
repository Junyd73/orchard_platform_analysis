# -*- coding: utf-8 -*-
"""저장소 루트를 sys.path 에 추가 (server 에서 core.* import)."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.append(root_s)
    return root
