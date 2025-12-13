
from typing import List, Dict
from abc import ABC, abstractmethod

from cat.types import Resource
from cat.agents.base import Agent
from cat.mad_hatter.decorators import Service

class Memory(ABC, Service):
    """Base class for Memory."""
    
    service_type = "memory"

    @abstractmethod
    async def store(self, resources: List[Resource], ctx: Agent) -> None:
        """
        Store resources into memory. Override in subclasses.
        """
        pass

    @abstractmethod
    async def recall(self, query: List[Resource], ctx: Agent) -> None:
        """
        Recall relevant information from memory. Override in subclasses.
        """
        pass