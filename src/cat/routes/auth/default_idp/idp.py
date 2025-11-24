import os
import hashlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Form

from cat import utils
from cat.env import get_env

router = APIRouter()

# TODOV2: internal idp should give a 403 when default auth handler is not active

@router.get(
    "/internal-idp",
    include_in_schema=False
)
async def internal_idp(
    redirect_uri: str
):
    html_path = os.path.join( utils.get_base_path(), "routes/auth/default_idp/idp.html" )
    with open(html_path, "r") as f:
        html = f.read()
    html = html.replace("{{redirect_uri}}", redirect_uri)
    return HTMLResponse(html)


@router.post(
    "/internal-idp/login",
    include_in_schema=False
)
async def internal_idp_login(
    api_key: str = Form(...),
    redirect_uri: str = Form(...)
):
    if api_key == get_env("CCAT_API_KEY"):
        code = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return RedirectResponse(
            url=f"{redirect_uri}?code={code}", # TODOV2: find a code based on CCAT_API_KEY to actually restrict access
            status_code=303
        )
    return RedirectResponse(
        url=f"/auth/internal-idp?redirect_uri={redirect_uri}",
        status_code=303
    )

@router.post(
    "/internal-idp/token",
    include_in_schema=False
)
async def token_endpoint(code: str = Form(...)):
    valid_code = hashlib.sha256(get_env("CCAT_API_KEY").encode()).hexdigest()[:16]
    if code != valid_code:
        raise HTTPException(
            detail="Invalid code.",
            status_code=403
        )
    
    # return access token
    return {
        "access_token": "mock_access_token", # Auth handlers issue their own JWTs
        "token_type": "Bearer",
        "expires_in": 3600
    }