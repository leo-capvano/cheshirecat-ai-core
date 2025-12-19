import os
import aiofiles
import mimetypes
import glob
from uuid import uuid5, NAMESPACE_URL
from typing import List
from pydantic import BaseModel

from fastapi import UploadFile, File, Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from cat import paths, urls
from cat.auth import get_user, get_ccat, AuthResource, AuthPermission

# TODOV2: test these routes

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadedFile(BaseModel):
    path: str
    url: str
    mime_type: str

class UploadedFileResponse(BaseModel):
    url: str
    mime_type: str

@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user = get_user(AuthResource.FILE, AuthPermission.WRITE),
    ccat = get_ccat(),
) -> UploadedFileResponse:
    hashed_user_id = str(uuid5(NAMESPACE_URL, str(user.id)))
    save_dir = os.path.join(paths.UPLOADS_PATH, hashed_user_id)
    os.makedirs(save_dir, exist_ok=True)

    safe_filename = os.path.basename(file.filename)
    file_location = os.path.join(save_dir, safe_filename)

    async with aiofiles.open(file_location, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await buffer.write(chunk)

    mime_type, _ = mimetypes.guess_type(safe_filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    url = f"{urls.API_URL}/uploads/{hashed_user_id}/{safe_filename}"

    await ccat.mad_hatter.execute_hook(
        "after_file_upload",
        UploadedFile(
            path=file_location,
            url=url,
            mime_type=mime_type
        ),
        caller=ccat
    )

    return UploadedFileResponse(
        url=url,
        mime_type=mime_type
    )

@router.get("")
async def get_uploaded_files(
    user = get_user(AuthResource.FILE, AuthPermission.LIST)
) -> List[UploadedFileResponse]:
    """Retrieve list of uploaded file URLs uploaded by a specific user."""

    hashed_user_id = str(uuid5(NAMESPACE_URL, str(user.id)))
    upload_dir = paths.UPLOADS_PATH
    full_path = os.path.join(upload_dir, hashed_user_id) # uuid5

    file_paths = glob.glob(f"{full_path}/**.*", recursive=True)
    uploads = []
    for path in file_paths:
        uploads.append(
            UploadedFileResponse(
                url=path.replace(paths.UPLOADS_PATH, urls.API_URL + "/uploads"),
                mime_type=mimetypes.guess_type(path)[0]
            )
        )
    return uploads

@router.get("/{path:path}")
async def get_uploaded_file(
    path: str = Path(...),
    user = get_user(AuthResource.FILE, AuthPermission.READ)
)-> FileResponse:
    full_path = os.path.join(paths.UPLOADS_PATH, path)

    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)
    else:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

