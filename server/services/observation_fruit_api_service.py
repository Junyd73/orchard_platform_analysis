# -*- coding: utf-8 -*-
"""과실 측정·추적 REST 어댑터 — Stage2 함수만 호출."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from app.core.ops_biz_date import now_ops
from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.core.observation_constants import OBS_TARGET_FRUIT_CD
from app.db.sqlite import get_sqlite_connection, get_sqlite_write_connection
from app.repository.interfaces.observation_photo_repository import (
    ObservationPhotoRepository,
)
from app.schemas.observation_fruit import (
    FollowupUpdateResponse,
    FruitMeasurementDto,
    FruitMeasurementResponse,
    FruitMeasurementUpsertRequest,
    ObservationTrackItemDto,
    ObservationTrackResponse,
)
from app.services.observation_ai_db_bridge import ServerDbBridge

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ensure_repo_root_on_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.append(root_s)
    return root


def _import_stage2():
    _ensure_repo_root_on_path()
    from core import observation_stage2 as stage2  # noqa: WPS433

    return stage2


def _s(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _f(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _delta(curr, prev) -> float | None:
    a = _f(curr)
    b = _f(prev)
    if a is None or b is None:
        return None
    return round(a - b, 2)


class ObservationFruitApiService:
    def __init__(
        self,
        *,
        db_path: Path | str,
        photo_repo: ObservationPhotoRepository,
        default_user_id: str = "MOBILE",
    ):
        self._db_path = Path(db_path)
        self._photo_repo = photo_repo
        self._default_user_id = str(default_user_id or "MOBILE").strip() or "MOBILE"

    def _user_id(self, user_id: str | None) -> str:
        uid = _s(user_id)
        return uid or self._default_user_id

    def _ensure_farm_and_obs(self, farm_cd: str, obs_id: str) -> dict:
        farm = _s(farm_cd)
        oid = _s(obs_id)
        if not farm or not self._photo_repo.farm_exists(farm):
            raise EntityNotFoundError("Farm not found")
        if not oid:
            raise EntityNotFoundError("Observation not found")
        obs = self._photo_repo.get_observation(farm, oid)
        if not obs:
            raise EntityNotFoundError("Observation not found")
        return obs

    def _to_measurement_dto(self, row: dict | None) -> FruitMeasurementDto | None:
        if not row:
            return None
        return FruitMeasurementDto(
            farm_cd=_s(row.get("farm_cd")),
            obs_id=_s(row.get("obs_id")),
            width_mm=_f(row.get("width_mm")),
            height_mm=_f(row.get("height_mm")),
            circumference_mm=_f(row.get("circumference_mm")),
            estimated_weight_g=_f(row.get("estimated_weight_g")),
            shape_cd=_s(row.get("shape_cd")) or None,
            skin_color_cd=_s(row.get("skin_color_cd")) or None,
            asymmetry_level=_i(row.get("asymmetry_level")),
            spot_yn=_s(row.get("spot_yn")) or "N",
            wound_yn=_s(row.get("wound_yn")) or "N",
            crack_yn=_s(row.get("crack_yn")) or "N",
            russet_yn=_s(row.get("russet_yn")) or "N",
            sunburn_yn=_s(row.get("sunburn_yn")) or "N",
            deformity_yn=_s(row.get("deformity_yn")) or "N",
            stalk_status_cd=_s(row.get("stalk_status_cd")) or None,
            calyx_status_cd=_s(row.get("calyx_status_cd")) or None,
            fruit_rmk=_s(row.get("fruit_rmk")) or None,
        )

    def get_measurement(
        self, farm_cd: str, obs_id: str
    ) -> FruitMeasurementResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = _s(obs.get("farm_cd") or farm_cd)
        oid = _s(obs.get("obs_id") or obs_id)
        stage2 = _import_stage2()
        with get_sqlite_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            row = stage2.get_fruit_measurement(db, farm, oid)
        return FruitMeasurementResponse(
            success=True,
            measurement=self._to_measurement_dto(row),
        )

    def upsert_measurement(
        self,
        farm_cd: str,
        obs_id: str,
        body: FruitMeasurementUpsertRequest,
        *,
        user_id: str | None,
    ) -> FruitMeasurementResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = _s(obs.get("farm_cd") or farm_cd)
        oid = _s(obs.get("obs_id") or obs_id)
        if _s(obs.get("target_type_cd")) != OBS_TARGET_FRUIT_CD:
            raise BusinessRuleError("열매 관찰에서만 측정값을 저장할 수 있습니다.")
        uid = self._user_id(user_id)
        payload = body.model_dump()
        stage2 = _import_stage2()
        with get_sqlite_write_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            ok, msg = stage2.save_fruit_measurement(db, farm, oid, payload, uid)
            if not ok:
                raise BusinessRuleError(msg or "열매 측정 저장에 실패했습니다.")
            row = stage2.get_fruit_measurement(db, farm, oid)
        return FruitMeasurementResponse(
            success=True,
            measurement=self._to_measurement_dto(row),
        )

    def list_track(self, farm_cd: str, obs_id: str) -> ObservationTrackResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = _s(obs.get("farm_cd") or farm_cd)
        oid = _s(obs.get("obs_id") or obs_id)
        root = _s(obs.get("root_obs_id")) or oid
        stage2 = _import_stage2()
        with get_sqlite_connection(self._db_path) as conn:
            db = ServerDbBridge(conn)
            rows = stage2.list_observation_track(db, farm, root)

        items: list[ObservationTrackItemDto] = []
        prev: dict | None = None
        followup: str | None = None
        for row in rows:
            d_w = _delta(row.get("width_mm"), prev.get("width_mm") if prev else None)
            d_h = _delta(row.get("height_mm"), prev.get("height_mm") if prev else None)
            d_c = _delta(
                row.get("circumference_mm"),
                prev.get("circumference_mm") if prev else None,
            )
            d_wt = _delta(
                row.get("estimated_weight_g"),
                prev.get("estimated_weight_g") if prev else None,
            )
            item_oid = _s(row.get("obs_id"))
            fu = _s(row.get("followup_dt")) or None
            if item_oid == oid and fu:
                followup = fu
            elif not followup and fu:
                followup = fu
            items.append(
                ObservationTrackItemDto(
                    obs_id=item_oid,
                    farm_cd=_s(row.get("farm_cd")) or farm,
                    obs_dt=_s(row.get("obs_dt")),
                    root_obs_id=_s(row.get("root_obs_id")) or None,
                    parent_obs_id=_s(row.get("parent_obs_id")) or None,
                    followup_dt=fu,
                    obs_title=_s(row.get("obs_title")) or None,
                    obs_content=_s(row.get("obs_content")) or None,
                    site_id=_s(row.get("site_id")) or None,
                    zone_nm=_s(row.get("zone_nm")) or None,
                    row_no=_s(row.get("row_no")) or None,
                    tree_no=_s(row.get("tree_no")) or None,
                    branch_no=_s(row.get("branch_no")) or None,
                    sample_no=_s(row.get("sample_no")) or None,
                    thumb_photo_id=_s(row.get("thumb_photo_id")) or None,
                    thumb_path=_s(row.get("thumb_path")) or None,
                    width_mm=_f(row.get("width_mm")),
                    height_mm=_f(row.get("height_mm")),
                    circumference_mm=_f(row.get("circumference_mm")),
                    estimated_weight_g=_f(row.get("estimated_weight_g")),
                    shape_cd=_s(row.get("shape_cd")) or None,
                    skin_color_cd=_s(row.get("skin_color_cd")) or None,
                    fruit_rmk=_s(row.get("fruit_rmk")) or None,
                    delta_width_mm=d_w,
                    delta_height_mm=d_h,
                    delta_circumference_mm=d_c,
                    delta_estimated_weight_g=d_wt,
                    is_current=item_oid == oid,
                )
            )
            prev = row

        # 현재 건 followup 우선, 없으면 최신 건
        if not followup and items:
            followup = items[-1].followup_dt

        return ObservationTrackResponse(
            success=True,
            root_obs_id=root,
            current_obs_id=oid,
            track_count=len(items),
            followup_dt=followup,
            items=items,
        )

    def update_followup(
        self,
        farm_cd: str,
        obs_id: str,
        followup_dt: str | None,
        *,
        user_id: str | None,
    ) -> FollowupUpdateResponse:
        obs = self._ensure_farm_and_obs(farm_cd, obs_id)
        farm = _s(obs.get("farm_cd") or farm_cd)
        oid = _s(obs.get("obs_id") or obs_id)
        uid = self._user_id(user_id)
        raw = _s(followup_dt) or None
        if raw and not _DATE_RE.match(raw):
            raise BusinessRuleError("재관찰 예정일은 YYYY-MM-DD 형식이어야 합니다.")
        obs_dt = _s(obs.get("obs_dt"))
        if raw and obs_dt and raw < obs_dt:
            raise BusinessRuleError("재관찰 예정일은 관찰일자보다 이전일 수 없습니다.")

        from datetime import datetime

        now = now_ops().strftime("%Y-%m-%d %H:%M:%S")
        with get_sqlite_write_connection(self._db_path) as conn:
            cur = conn.execute(
                """
                UPDATE t_observation_master
                SET followup_dt = ?, mod_id = ?, mod_dt = ?
                WHERE farm_cd = ? AND obs_id = ?
                  AND COALESCE(use_yn, 'Y') = 'Y'
                """,
                (raw, uid, now, farm, oid),
            )
            conn.commit()
            if cur.rowcount <= 0:
                raise EntityNotFoundError("Observation not found")
        return FollowupUpdateResponse(
            success=True,
            obs_id=oid,
            followup_dt=raw,
            message="재관찰 예정일이 저장되었습니다." if raw else "재관찰 예정일이 해제되었습니다.",
        )
