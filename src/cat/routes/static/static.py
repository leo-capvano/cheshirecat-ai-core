import os
import aiofiles
import mimetypes
import glob
from uuid import uuid5, NAMESPACE_URL
from typing import List
from pydantic import BaseModel

from fastapi import UploadFile, File, Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cat import utils
from cat.auth import check_permissions, AuthResource, AuthPermission

# TODOV2: test these routes

router = APIRouter(prefix="/static", tags=["Static Files"])


class UploadedFile(utils.BaseModelDict):
    path: bytes
    url: str
    mime_type: str

class UploadedFileResponse(BaseModel):
    url: str
    mime_type: str

@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    cat=check_permissions(AuthResource.STATIC, AuthPermission.WRITE)
) -> UploadedFileResponse:
    hashed_user_id = str(uuid5(NAMESPACE_URL, str(cat.user_id)))
    save_dir = os.path.join(utils.get_static_path(), hashed_user_id)
    os.makedirs(save_dir, exist_ok=True)

    safe_filename = os.path.basename(file.filename)
    file_location = os.path.join(save_dir, safe_filename)

    async with aiofiles.open(file_location, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await buffer.write(chunk)

    mime_type, _ = mimetypes.guess_type(safe_filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    url = f"{utils.get_static_url()}/{hashed_user_id}/{safe_filename}"

    await cat.execute_hook(
        "after_file_upload",
        UploadedFile(
            path=file_location,
            url=url,
            mime_type=mime_type
        )
    )

    return UploadedFileResponse(
        url=url,
        mime_type=mime_type
    )




@router.get("")
async def get_static_files(
    cat=check_permissions(AuthResource.STATIC, AuthPermission.LIST)
) -> List[str]:
    """Retrieve list of static file URLs uploaded by a specific user."""

    hashed_user_id = str(uuid5(NAMESPACE_URL, str(cat.user_id)))
    static_dir = utils.get_static_path()
    full_path = os.path.join(static_dir, hashed_user_id) # uuid3/5

    file_paths = glob.glob(f"{full_path}/**.*", recursive=True)
    urls = []
    for path in file_paths:
        urls.append(
            path.replace(utils.get_static_path(), utils.get_static_url())
        )
    return urls
    

@router.get("/{path:path}")
async def get_static_file(
    path: str = Path(...),
    cat=check_permissions(AuthResource.STATIC, AuthPermission.READ)
)-> FileResponse:
    static_dir = utils.get_static_path()
    full_path = os.path.join(static_dir, path)

    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)
    else:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    

# TODOV2: delete static route




# TODOV2: take away
def mount(cheshire_cat_api):

    # internal static files folder
    core_static_dir = utils.get_base_path() + "/routes/static/core_static_folder"
    cheshire_cat_api.mount(
        "/core-static",
        StaticFiles(directory=core_static_dir),
        name="core-static",
    )
