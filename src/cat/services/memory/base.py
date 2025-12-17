
from typing import List
from abc import ABC, abstractmethod

from cat.types import Resource
from cat.looking_glass.execution_context import ExecutionContext
from ..service import SingletonService

class Memory(ABC, SingletonService):
    """Base class for Memory."""

    service_type = "memory"

    @abstractmethod
    async def store(self, resources: List[Resource], ctx: ExecutionContext):
        """
        Store resources into memory. Override in subclasses.
        """
        pass

    @abstractmethod
    async def recall(
        self, query: List[Resource], ctx: ExecutionContext
    ) -> List[Resource]:
        """
        Recall relevant information from memory. Override in subclasses.
        """
        pass