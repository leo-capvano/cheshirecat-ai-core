from enum import Enum
from typing import Annotated, TYPE_CHECKING
from fastapi import Depends, Request
from httpx import request
from cat.auth.user import User

if TYPE_CHECKING:
    from cat.looking_glass.cheshire_cat import CheshireCat


# TODOV2: these Enums should be easily extensible (so maybe not even enums)
class AuthResource(str, Enum):
    """Enum of core authorization resources. Can be extended via plugin."""
    #SETTING = "SETTING"
    #PROFILE = "PROFILE"
    CHAT = "CHAT"
    PLUGIN = "PLUGIN"
    FILE = "FILE"


class AuthPermission(str, Enum):
    """Enum of core authorization permissions. Can be extended via plugin."""
    WRITE = "WRITE"
    EDIT = "EDIT"
    LIST = "LIST"
    READ = "READ"
    DELETE = "DELETE"


def check_permissions(
        resource: AuthResource | str,
        permission: AuthPermission | str
    ) -> Depends:
    """
    DEPRECATED - DO NOT USE.

    This function is broken after v2 refactoring and will be removed.
    Use get_user() and get_ccat() instead.

    OLD PATTERN (broken):
    =====================
    @router.post("/message")
    async def message(cat=check_permissions(AuthResource.CHAT, AuthPermission.EDIT)):
        ...

    NEW PATTERN (use this):
    =======================
    @router.post("/message")
    async def message(
        request: Request,
        user: User = get_user(AuthResource.CHAT, AuthPermission.EDIT),
        ccat = get_ccat(),
    ):
        # Access user, ccat directly
        # For agent operations, use factory:
        # agent = await ccat.factory.get("agents", "default", request=request)
        ...

    Parameters
    ----------
    resource: AuthResource | str
        The resource that the user must have permission for.
    permission: AuthPermission | str
        The permission that the user must have for the resource.

    Raises
    ------
    NotImplementedError
        Always raises - this function is deprecated and non-functional.
    """
    raise NotImplementedError(
        "check_permissions is deprecated and broken after v2 refactoring. "
        "Use get_user(resource, permission) and get_ccat() instead. "
        "See docstring for migration examples."
    )


def get_user(
        resource: str,
        permission: str
    ) -> Depends:
    """
    Dependency that extracts authenticated user from request.state.

    The user is placed in request.state.user by the Connection.authorize flow.
    This dependency retrieves it and provides clean access.

    Parameters
    ----------
    resource: AuthResource | str
        The resource that the user must have permission for.
    permission: AuthPermission | str
        The permission that the user must have for the resource.

    Returns
    -------
    Depends
        Dependency that resolves to the authenticated User.
        Raises HTTPException(403) if auth fails.

    Usage
    -----
    @router.post("/message")
    async def message(
        user: User = get_user(AuthResource.CHAT, AuthPermission.EDIT)
    ):
        # user is an authenticated User object
        pass
    """
    from cat.auth.connection import HTTPConnection

    async def extract_user(
        request = Depends(HTTPConnection(resource, permission))
    ) -> User:
        # HTTPConnection already validated and set request.state.user
        return request.state.user

    return Depends(extract_user)


def get_ccat(
    
) -> Depends:
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