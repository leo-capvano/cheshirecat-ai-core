from typing import Dict, List, Any
from uuid import UUID
from pydantic import BaseModel, field_validator

from .permissions import AuthResource, AuthPermission
from cat.db import UserDB

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
    permissions: Dict[AuthResource, List[AuthPermission]] | Dict[str, List[str]]

    # only put in here what you are comfortable to pass plugins:
    # - profile data
    # - custom attributes
    # - roles
    custom: Any = {}

    @field_validator("id", mode="before")
    def ensure_uuid(cls, v):
        """
        Accept either a uuid.UUID or a UUID string; normalize to uuid.UUID.
        """
        if isinstance(v, UUID):
            return v
        try:
            return UUID(str(v))
        except Exception:
            raise ValueError("User id must be a valid UUID or UUID string")

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

        Check if user can delete a plugin:
        >>> cat.user.can("PLUGIN", "DELETE")
        True
        """

        return (resource in self.permissions) and \
            permission in self.permissions[resource]

    async def save(self, key: str, value: Any) -> Any:
        """
        Save user-specific key-value pair.

        Parameters
        ----------
        key : str
            The key to store the value under.
        value : Any
            The value to store (will be JSON serialized).

        Returns
        -------
        Any
            The saved value.

        Examples
        --------
        >>> await user.save("theme", "dark")
        "dark"
        """
        return await UserDB.save(self.id, key, value)

    async def load(self, key: str, default: Any = None) -> Any:
        """
        Load user-specific value by key.

        Parameters
        ----------
        key : str
            The key to load.
        default : Any, optional
            Default value to return if key doesn't exist (default: None).

        Returns
        -------
        Any
            The stored value, or default if not found.

        Examples
        --------
        >>> await user.load("theme", "light")
        "dark"
        """
        return await UserDB.load(self.id, key, default)

    async def delete(self, key: str) -> bool:
        """
        Delete user-specific key-value pair.

        Parameters
        ----------
        key : str
            The key to delete.

        Returns
        -------
        bool
            True if the key was deleted, False if it didn't exist.

        Examples
        --------
        >>> await user.delete("theme")
        True
        """
        return await UserDB.delete(self.id, key)

    async def exists(self, key: str) -> bool:
        """
        Check if user-specific key exists.

        Parameters
        ----------
        key : str
            The key to check.

        Returns
        -------
        bool
            True if the key exists, False otherwise.

        Examples
        --------
        >>> await user.exists("theme")
        True
        """
        return await UserDB.exists(self.id, key)