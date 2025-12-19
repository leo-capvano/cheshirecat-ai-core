
from typing import List, TYPE_CHECKING
from abc import ABC, abstractmethod

from cat.types import Resource
from ..service import SingletonService

if TYPE_CHECKING:
    from cat.auth.user import User


class Memory(ABC, SingletonService):
    """Base class for Memory."""

    service_type = "memory"

    @abstractmethod
    async def store(self, resources: List[Resource], user: "User") -> None:
        """
        Store resources into memory. Override in subclasses.

        Parameters
        ----------
        resources : List[Resource]
            Resources to store.
        user : User
            The user storing the resources.
        """
        pass

    @abstractmethod
    async def recall(
        self, query: List[Resource], user: "User"
    ) -> List[Resource]:
        """
        Recall relevant information from memory. Override in subclasses.

        Parameters
        ----------
        query : List[Resource]
            Query resources.
        user : User
            The user querying memory.

        Returns
        -------
        List[Resource]
            Retrieved resources.
        """
        pass