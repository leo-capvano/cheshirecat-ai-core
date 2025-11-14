from typing import Dict, List

from cat.utils import BaseModelDict
from .permissions import AuthResource, AuthPermission

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
    ]

    # only put in here what you are comfortable to pass plugins:
    # - profile data
    # - custom attributes
    # - roles
    extra: BaseModelDict = BaseModelDict()

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