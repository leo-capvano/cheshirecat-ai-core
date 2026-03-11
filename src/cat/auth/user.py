from typing import Dict, List, Any
from uuid import UUID
from pydantic import BaseModel, field_validator

from cat.db import UserDB


class User(BaseModel):
    """
    Class to represent a User.
    Will be created by Auth handler(s) starting from a credential (jwt or key).
    Instance of the authenticated user is stored under request.state.user and is available in request services.
    Will be accessible in services via `Service.user`
    """

    id: UUID
    name: str

    # permissions as flat string list (e.g. ["chat:edit", "uploads:read", "admin"])
    permissions: List[str] = []

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

    def can(self, *required: str) -> bool:
        """
        Check user permissions (AND logic).

        Returns
        -------
        bool
            Whether the user has all required permissions.

        Examples
        --------
        >>> user.can("chat:edit", "uploads:read")
        True
        """
        return all(p in self.permissions for p in required)

    async def save_settings(self, settings: Dict) -> Dict:
        """
        Save user-specific settings.
        Will overwrite existing settings, so load existing settings first, update the dictionary, and then save.

        Parameters
        ----------
        settings : Dict
            The settings to store (must be JSON serialized).

        Returns
        -------
        Dict
            The saved settings.

        Examples
        --------
        >>> await user.save_settings({"theme": "dark"})
        {"theme": "dark"}
        """

        await UserDB.save(self.id, "settings", settings)
        return settings

    async def load_settings(self) -> Dict:
        """
        Load user-specific value by key.
        Returns an empty dict if no settings are found.

        Returns
        -------
        Dict
            The stored settings, or an empty dict if not found.
        Examples
        --------
        >>> await user.load_settings()
        {"theme": "dark"}
        """
        return await UserDB.load(self.id, "settings", {})