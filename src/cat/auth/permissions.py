from enum import Enum
from typing import Dict, List

from fastapi import Depends
from cat.utils import BaseModelDict


class AuthResource(str, Enum):
    """Enum of core authorization resources. Can be extended via plugin."""
    CHAT = "CHAT"
    SETTING = "SETTING"
    PLUGIN = "PLUGIN"
    STATIC = "STATIC"


class AuthPermission(str, Enum):
    """Enum of core authorization permissions. Can be extended via plugin."""
    WRITE = "WRITE"
    EDIT = "EDIT"
    LIST = "LIST"
    READ = "READ"
    DELETE = "DELETE"


def get_full_permissions() -> Dict[AuthResource, List[AuthPermission]]:
    """
    Returns all available resources and permissions.
    """
    # TODOV2: should include plugins defined permissions
    perms = {}
    for res in AuthResource:
        perms[res.name] = [p.name for p in AuthPermission]
    return perms


def get_base_permissions() -> Dict[AuthResource, List[AuthPermission]]:
    """
    Returns the default permissions for new users (chat only!).
    """

    all_permissions = [p.name for p in AuthPermission]

    # TODOV2: should include plugins defined permissions
    return {
        AuthResource.CHAT: all_permissions,
        AuthResource.STATIC: all_permissions,
    }


def check_permissions(resource: AuthResource | str, permission: AuthPermission | str):
    """
    Helper function to inject a StrayCat into endpoints after checking for required permissions.

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
    """

    # import here to avoid circular imports
    from cat.auth.connection import HTTPAuth

    return Depends(HTTPAuth(
        # in case strings are passed, we do not force to the enum, to allow custom permissions
        # (which in any case are to be matched in the endpoint)
        resource = resource, 
        permission = permission,
    ))


class User(BaseModelDict):
    """
    Class to represent token content after the token has been decoded.
    Will be creted by AuthHandler(s) to standardize their output.
    Core will use this object to retrieve or create a StrayCat (session)
    """

    # Best practice is to have a human readable name and a uuid5 as id
    id: str
    name: str

    # permissions
    permissions: Dict[
        AuthResource, List[AuthPermission]] | Dict[str, List[str]
    ] = get_base_permissions()

    # only put in here what you are comfortable to pass plugins:
    # - profile data
    # - custom attributes
    # - roles
    extra: BaseModelDict = BaseModelDict()

    def can(
            self,
            resource: AuthResource,
            permission: AuthPermission
        ) -> bool:
        """
        Check user permissions.
        
        Returns
        -------
        boolean : bool
            Whether the user has permission on the resource.

        Examples
        --------

        Obtain the path in which your plugin is located
        >>> cat.user.can("PLUGIN", "DELETE")
        True
        """

        return (resource in self.permissions) and \
            permission in self.permissions[resource]


