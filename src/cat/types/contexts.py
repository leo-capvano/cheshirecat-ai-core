from typing import List
from pydantic import BaseModel

from cat.looking_glass import prompts
from cat.protocols.model_context.type_wrappers import Resource
from cat.protocols.model_context.server import MCPServer

class Context(BaseModel):
    instructions: str = prompts.MAIN_PROMPT_PREFIX
    resources: List[Resource] = []
    mcps: List[MCPServer] = []