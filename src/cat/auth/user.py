from typing import Dict, List, Any
from uuid import UUID

from pydantic import BaseModel
from .permissions import AuthResource, AuthPermission

class User(BaseModel):
    """
    Class to represent a User.
    Will be creted by Auth handler(s) starting from a JWT.
    Core will use this object to build a StrayCat (session).
    User will be accessible via `StrayCat.user`
    """

    id: UUID
    name: str

    # permissions
    permissions: Dict[
        AuthResource, List[AuthPermission]] | Dict[str, List[str]
    ]

    # only put in here what you are comfortable to pass plugins:
    # - profile data
    # - custom attributes
    # - roles
    custom: Any = {}

    def can(
            self,
            resource: AuthResource | str,
            permission: AuthPermission | str
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