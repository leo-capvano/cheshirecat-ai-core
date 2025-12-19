from enum import Enum

from fastapi import Depends


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
    DEPRECATED: Use get_user() for new code.

    Helper function to inject authenticated Request into endpoints after
    checking permissions. Kept for backwards compatibility.

    For new endpoints, prefer:
    - user = get_user(resource, permission) to get authenticated user
    - ccat = get_ccat() to get CheshireCat instance
    - Or access directly via request.state.user and request.app.state.ccat

    Parameters
    ----------
    resource: AuthResource | str
        The resource that the user must have permission for.
    permission: AuthPermission | str
        The permission that the user must have for the resource.

    Returns
    -------
    Depends
        Dependency that resolves to authenticated Request.
        User available at request.state.user.
        Raises HTTPException(403) if auth fails.
    """

    # import here to avoid circular imports
    from cat.auth.connection import HTTPConnection

    return Depends(HTTPConnection(
        # in case strings are passed, we do not force to the enum, to allow custom permissions
        # (which in any case are to be matched in the endpoint)
        resource = resource,
        permission = permission,
    ))


def get_user(
        resource: AuthResource | str,
        permission: AuthPermission | str
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
    from fastapi import Request

    async def extract_user(request: Request = Depends(HTTPConnection(resource, permission))):
        # HTTPConnection already validated and set request.state.user
        return request.state.user

    return Depends(extract_user)


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
    from fastapi import Request

    return Depends(lambda request: request.app.state.ccat)



