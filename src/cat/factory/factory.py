from typing import Any, Dict
from pydantic import BaseModel

from cat.factory.defaults import (
    AuthHandlerDefault, LLMDefault, EmbedderDefault, AgentDefault
)


class FactoryCategory(BaseModel):
    default: Any
    keep_default: bool
    at_least_one: bool
    objects: Dict[str, Any] = {}


class Factory:

    def __init__(self):

        self.categories = {
            "auth_handler" : FactoryCategory(
                default = AuthHandlerDefault(),
                keep_default=False,
                at_least_one=True
            ),
            "llm" : FactoryCategory(
                default = LLMDefault(),
                keep_default=False,
                at_least_one=True
            ),
            "embedder" : FactoryCategory(
                default = EmbedderDefault(),
                keep_default=False,
                at_least_one=True
            ),
            "agent" : FactoryCategory(
                default = AgentDefault(),
                keep_default=True,
                at_least_one=True
            ),
            "mcp" : FactoryCategory(
                default = None,
                keep_default=False,
                at_least_one=False
            ),
        }

    async def load_objects(self, mad_hatter):
        """Collect objects instantiated by plugins (llms, auth handlers, agents, etc)."""

        for category_name, category in self.categories.items():
            category.objects = mad_hatter.execute_hook(
                f"factory_allowed_{category_name}s", {}, cat=None
            )
            # TODO: should add type checks
            # TODO: if agents, objects[slug].cat = cat


            if category.keep_default or (category.at_least_one and len(category.objects) == 0):
                category.objects["default"] = category.default
                
    def get_objects(self, category_name: str):
        return self.categories[category_name].objects

    def get_default(self, category_name: str):
        return self.categories[category_name].default
