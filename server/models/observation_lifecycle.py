# -*- coding: utf-8 -*-
"""관찰 작성/관리 상태 상수 (progress_status_cd / use_yn 과 별개)."""

# 작성 상태 (observation_status)
OBS_STATUS_DRAFT = "DRAFT"
OBS_STATUS_COMPLETED = "COMPLETED"
OBS_STATUS_CANCELLED = "CANCELLED"

# 관리 상태 (record_status)
OBS_RECORD_ACTIVE = "ACTIVE"
OBS_RECORD_DELETED = "DELETED"

# 목록·통계 노출 조건
PUBLISHED_FILTER_SQL = (
    "COALESCE(o.observation_status, 'DRAFT') = 'COMPLETED' "
    "AND COALESCE(o.record_status, 'ACTIVE') = 'ACTIVE'"
)
