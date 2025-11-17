from urllib.parse import urljoin

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from cat.looking_glass.stray_cat import StrayCat
from cat.auth import (
    User,
    AuthPermission, AuthResource,
    check_permissions
)
from cat import utils
from cat.env import get_env


router = APIRouter(prefix="/auth", tags=["Auth"])

# TODOAUTH TODOV2 /logout endpoint
# TODOAUTH TODOV2 /token/verify
# TODOAUTH TODOV2 /token/refresh


@router.get("/login/{name}")
async def oauth_login(r: Request, name: str) -> RedirectResponse:
    """Starts the OAuth flow."""
    
    auth = r.app.state.ccat.auth_handlers.get(name, None)
    
    if auth is None:
        raise HTTPException(status_code=404, detail=f"Auth Handler {name} not found.")
    
    redirect_uri = urljoin(utils.get_base_url(), f"auth/callback/{name}")

    # start OAuth flow
    return RedirectResponse(
        url = await auth.get_provider_login_url(redirect_uri)
    )


@router.get("/callback/{name}")
async def oauth_callback(r: Request, name: str, code: str):
    """OAuth callback."""

    auth = r.app.state.ccat.auth_handlers.get(name, None)

    if auth is None:
        raise HTTPException(
            status_code=404,
            detail=f"Auth Handler {name} not found."
        )

    redirect_uri = urljoin(utils.get_base_url(), f"auth/callback/{name}")

    user = await auth.authorize_user_from_oauth_code(
        redirect_uri,
        dict(r.query_params)
    )
    if user is None:
        raise HTTPException(
            status_code=403,
            detail=f"Auth Handler {name} could not complete the OAuth flow."
        )

    token = auth.issue_jwt(user)

    # TODOV2: should keep somewhere the frontend url where the whole flow started
    # TODOV2: not secure to pass JWT via url fragments
    frontend_url = utils.get_base_url() + f"#token={token}"
    response = RedirectResponse(utils.get_base_url())

    return response

@router.get("/me")
async def get_user_info(
    cat: StrayCat = check_permissions(AuthResource.CHAT, AuthPermission.READ),
) -> User:
    """Returns user information."""
    return cat.user.model_dump()

