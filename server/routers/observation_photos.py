# -*- coding: utf-8 -*-
"""관찰 사진 API — 등록 저장과 분리 (SCR-002 사진 단계)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import get_observation_photo_service
from app.schemas.observation_photo import (
    ObservationPhotoItem,
    ObservationPhotoListResponse,
    ObservationPhotoReorderRequest,
    ObservationPhotoUploadResponse,
)
from app.services.observation_photo_service import ObservationPhotoService

router = APIRouter(
    prefix="/farms/{farm_cd}/observations/{obs_id}/photos",
    tags=["observation-photos"],
)


def _user_header(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str | None:
    return x_user_id


@router.get("", response_model=ObservationPhotoListResponse)
def list_photos(
    farm_cd: str,
    obs_id: str,
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> ObservationPhotoListResponse:
    return service.list_photos(farm_cd, obs_id)


@router.get("/representative", response_model=ObservationPhotoItem | None)
def get_representative(
    farm_cd: str,
    obs_id: str,
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> ObservationPhotoItem | None:
    return service.get_representative(farm_cd, obs_id)


@router.post("", response_model=ObservationPhotoUploadResponse)
async def upload_photos(
    farm_cd: str,
    obs_id: str,
    files: list[UploadFile] = File(..., description="multipart 이미지 (최대 남은 장수)"),
    x_user_id: str | None = Depends(_user_header),
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> ObservationPhotoUploadResponse:
    return await service.upload_photos(
        farm_cd, obs_id, files, user_id=x_user_id
    )


@router.put("/order", response_model=ObservationPhotoListResponse)
def reorder_photos(
    farm_cd: str,
    obs_id: str,
    body: ObservationPhotoReorderRequest,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> ObservationPhotoListResponse:
    return service.reorder_photos(
        farm_cd, obs_id, body.photo_ids, user_id=x_user_id
    )


@router.delete("/{photo_id}")
def delete_photo(
    farm_cd: str,
    obs_id: str,
    photo_id: str,
    x_user_id: str | None = Depends(_user_header),
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> dict[str, str]:
    service.delete_photo(farm_cd, obs_id, photo_id, user_id=x_user_id)
    return {"detail": "deleted"}


@router.get("/{photo_id}/thumbnail")
def get_thumbnail(
    farm_cd: str,
    obs_id: str,
    photo_id: str,
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> FileResponse:
    path = service.resolve_photo_file(
        farm_cd, obs_id, photo_id, kind="thumbnail"
    )
    return FileResponse(path)


@router.get("/{photo_id}/original")
def get_original(
    farm_cd: str,
    obs_id: str,
    photo_id: str,
    service: ObservationPhotoService = Depends(get_observation_photo_service),
) -> FileResponse:
    path = service.resolve_photo_file(
        farm_cd, obs_id, photo_id, kind="original"
    )
    return FileResponse(path)
