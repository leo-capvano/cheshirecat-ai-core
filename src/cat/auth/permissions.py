from typing import TYPE_CHECKING

from fastapi import Depends, Request, HTTPException
from fastapi.security.api_key import APIKeyHeader

from cat.auth.user import User

if TYPE_CHECKING:
    from cat.looking_glass.cheshire_cat import CheshireCat


# Auto-registration of permission strings
_all_permissions: set[str] = set()


def get_all_permissions() -> set[str]:
    """Return all permission strings registered by get_user() calls across routes."""
    return _all_permissions.copy()


def get_user(*permissions: str) -> Depends:
    """
    Dependency that authenticates the user and checks permissions.

    Loops through auth handlers calling `auth.authenticate(request)`.
    First User returned wins. Then checks `user.can(*permissions)`.

    Parameters
    ----------
    *permissions : str
        Permission strings required for this route (AND logic).

    Returns
    -------
    Depends
        Dependency that resolves to the authenticated User.
        Raises HTTPException(403) if auth fails or permissions insufficient.

    Usage
    -----
    @router.post("/message")
    async def message(
        user: User = get_user("chat:edit"),
        ccat = get_ccat(),
    ):
        pass
    """
    # Auto-register permission strings at import time
    _all_permissions.update(permissions)

    async def authenticate_and_check(
        request: Request,
        credential: str | None = Depends(APIKeyHeader(
            name="Authorization",
            description="Insert here your CCAT_API_KEY, or Bearer JWT token.",
            auto_error=False,
        )),
    ) -> User:
        ccat = request.app.state.ccat
        auth_handlers = await ccat.get_auth_handlers()

        for ah in auth_handlers.values():
            user = await ah.authenticate(request)
            if user and isinstance(user, User):
                # Check permissions
                if not user.can(*permissions):
                    raise HTTPException(
                        status_code=403,
                        detail="Insufficient permissions",
                    )
                request.state.user = user
                return user

        raise HTTPException(status_code=403, detail="Invalid Credentials")

    return Depends(authenticate_and_check)


def get_ccat() -> Depends:
    """
    Dependency helper to get CheshireCat instance from request.

    Returns
    -------
    Depends
        Dependency that resolves to the CheshireCat instance.

    Usage
    -----
    @router.get("/status")
    async def status(ccat = get_ccat()):
        # ccat is the CheshireCat instance
        pass
    """
    def extract_ccat(request: Request) -> "CheshireCat":
        return request.app.state.ccat
    return Depends(extract_ccat)
