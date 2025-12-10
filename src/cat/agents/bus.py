from typing import Callable
from pydantic import BaseModel, ConfigDict

from cat.looking_glass.cheshire_cat import CheshireCat
from cat.auth.user import User
from cat.types import ChatRequest, ChatResponse


class AgentBus(BaseModel):
    """
    Data structure agents can collectively read and write.
    It is created from StrayCat.
    """
    ccat: CheshireCat
    user: User
    request: ChatRequest
    response: ChatResponse
    stream_callback: Callable

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    # def fork(self, **overrides) -> "AgentContext":
    #     """Create a copy for private agent execution without side effects.
        
    #     Usage:
    #         # Shared context
    #         context = await agent.call_agent("worker")
            
    #         # Private context  
    #         private = context.fork()
    #         private = await agent.call_agent("worker", private)
    #     """
    #     new_context = self.model_copy(deep=True)
    #     for key, value in overrides.items():
    #         setattr(new_context, key, value)
    #     return new_context