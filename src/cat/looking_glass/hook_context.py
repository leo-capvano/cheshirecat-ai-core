from typing import Callable, Union, TYPE_CHECKING
from fastapi import Request

if TYPE_CHECKING:
    from cat.auth.user import User
    from cat.looking_glass.cheshire_cat import CheshireCat
    from cat.services.service import SingletonService, RequestService, Service
    from cat.mad_hatter.mad_hatter import MadHatter
    from cat.services.__factory import ServiceFactory
    from cat.protocols.model_context.client import MCPClients


class HookContext:
    """
    Context passed to plugin hooks (the old `cat` in version 1).
    Provides access to services and optional user context.
    """

    def __init__(
            self,
            caller: Union["CheshireCat", "SingletonService", "RequestService", Callable],
            request: Union["Request", None] = None,
        ) -> None:
        """
        Initialize hook context.

        Parameters
        ----------
        ccat : CheshireCat
            The CheshireCat instance.
        user : User, optional
            The current user (for request-scoped hooks).
        """

        from cat.looking_glass.cheshire_cat import CheshireCat
        from cat.services.service import SingletonService, RequestService

        if isinstance(caller, CheshireCat):
            ccat = caller
            user = None
        elif isinstance(caller, SingletonService):
            ccat = caller.ccat
            user = None
        elif isinstance(caller, RequestService):
            ccat = caller.ccat
            user = caller.user
        else:
            raise ValueError("Invalid caller type for HookContext")
        
        self._ccat = ccat
        self._user = user

    @property
    def ccat(self) -> "CheshireCat":
        """Access to the CheshireCat instance."""
        return self._ccat

    @property
    def factory(self) -> "ServiceFactory":
        """Access to the ServiceFactory."""
        return self._ccat.factory

    @property
    def mad_hatter(self) -> "MadHatter":
        """Access to the MadHatter plugin manager."""
        return self._ccat.mad_hatter

    @property
    def user(self) -> "User | None":
        """Access to the current user (if available)."""
        return self._user

    @property
    def user_id(self) -> str | None:
        """Get the current user ID (if user is available)."""
        return self._user.id if self._user else None
