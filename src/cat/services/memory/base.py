
from typing import List, TYPE_CHECKING

from cat.types import Resource
from ..service import RequestService

if TYPE_CHECKING:
    from cat.auth.user import User


class Memory(RequestService):
    """Base class for Memory."""

    service_type = "memory"

    async def store(self, resources: List[Resource]) -> None:
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

    async def recall(self, query: List[Resource]) -> List[Resource]:
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
        return []
    
    async def clear(self) -> None:
        """
        Clear all memory. Override in subclasses.
        """
        pass