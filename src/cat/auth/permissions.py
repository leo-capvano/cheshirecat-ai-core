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


def check_permissions(resource: AuthResource | str, permission: AuthPermission | str):
    """
    Helper function to inject a StrayCat (cat) into endpoints after checking for required permissions.

    Parameters
    ----------
    resource: AuthResource | str
        The resource that the user must have permission for.
    permission: AuthPermission | str
        The permission that the user must have for the resource.

    Returns
    ----------
    cat: StrayCat | None
        User session object if auth is successfull, None otherwise.
        In case of None, auth will fail and endpoint will give status 403.
    """

    # import here to avoid circular imports
    from cat.auth.connection import HTTPConnection

    return Depends(HTTPConnection(
        # in case strings are passed, we do not force to the enum, to allow custom permissions
        # (which in any case are to be matched in the endpoint)
        resource = resource, 
        permission = permission,
    ))



