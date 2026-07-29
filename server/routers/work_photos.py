# -*- coding: utf-8 -*-
"""작업 결과 사진 API — 관찰 사진과 분리."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import get_work_photo_service
from app.schemas.work_photo import WorkPhotoListResponse, WorkPhotoUploadResponse
from app.services.work_photo_service import WorkPhotoService

router = APIRouter(
    prefix="/farms/{farm_cd}/work-logs/works/{work_id}/photos",
    tags=["work-photos"],
)


def _user_header(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str | None:
    return x_user_id


@router.get("", response_model=WorkPhotoListResponse)
def list_photos(
    farm_cd: str,
    work_id: str,
    service: WorkPhotoService = Depends(get_work_photo_service),
) -> WorkPhotoListResponse:
    return service.list_photos(farm_cd, work_id)


@router.post("", response_model=WorkPhotoUploadResponse)
async def upload_photos(
    farm_cd: str,
    work_id: str,
    files: list[UploadFile] | None = File(
        default=None, description="multipart 이미지 (files)"
    ),
    file: UploadFile | None = File(
        default=None, description="단일 이미지 (file)"
    ),
    x_user_id: str | None = Depends(_user_header),
    service: WorkPhotoService = Depends(get_work_photo_service),
) -> WorkPhotoUploadResponse:
    upload_list: list[UploadFile] = []
    if file is not None:
        upload_list.append(file)
    if files:
        upload_list.extend(files)
    return await service.upload_photos(
        farm_cd, work_id, upload_list, user_id=x_user_id
    )


@router.delete("/{photo_id}")
def delete_photo(
    farm_cd: str,
    work_id: str,
    photo_id: str,
    x_user_id: str | None = Depends(_user_header),
    service: WorkPhotoService = Depends(get_work_photo_service),
) -> dict[str, str]:
    service.delete_photo(farm_cd, work_id, photo_id, user_id=x_user_id)
    return {"detail": "deleted"}


@router.get("/{photo_id}/thumbnail")
def get_thumbnail(
    farm_cd: str,
    work_id: str,
    photo_id: str,
    service: WorkPhotoService = Depends(get_work_photo_service),
) -> FileResponse:
    path = service.resolve_photo_file(
        farm_cd, work_id, photo_id, kind="thumbnail"
    )
    return FileResponse(path)


@router.get("/{photo_id}/original")
def get_original(
    farm_cd: str,
    work_id: str,
    photo_id: str,
    service: WorkPhotoService = Depends(get_work_photo_service),
) -> FileResponse:
    path = service.resolve_photo_file(
        farm_cd, work_id, photo_id, kind="original"
    )
    return FileResponse(path)
