from typing import List
from pydantic import BaseModel, HttpUrl, field_serializer

from cat.looking_glass import prompts
from cat.protocols.model_context.type_wrappers import Resource

class Context(BaseModel):
    instructions: str = prompts.MAIN_PROMPT_PREFIX
    resources: List[Resource] = []
    mcps: List[HttpUrl] = []

    @field_serializer("mcps")
    def serialize_uri(self, mcps):
        return [str(m) for m in mcps]