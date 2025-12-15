
from typing import List, Dict
from abc import ABC, abstractmethod

from cat.types import Resource
from cat.looking_glass.execution_context import ExecutionContext
from cat.mad_hatter.decorators import Service

class Memory(ABC, Service):
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