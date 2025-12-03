from typing import Any, Dict
from pydantic import BaseModel


class FactoryCategory(BaseModel):
    default: Any
    keep_default: bool
    at_least_one: bool
    objects: Dict[str, Any] = {}


class Factory:

    def __init__(self):

        # Import here to avoid circular dependencies
        from cat.auth.handler.default import DefaultAuth
        from cat.protocols.future.llm import DefaultLLM
        from cat.protocols.future.embedder import DefaultEmbedder
        #from cat.protocols.future.memory import DefaultMemory
        from cat.agents.default import DefaultAgent

        self.categories = {
            "auth_handler" : FactoryCategory(
                default = DefaultAuth(),
                keep_default=False,
                at_least_one=True
            ),
            "llm" : FactoryCategory(
                default = DefaultLLM(),
                keep_default=False,
                at_least_one=True
            ),
            "embedder" : FactoryCategory(
                default = DefaultEmbedder(),
                keep_default=False,
                at_least_one=True
            ),
            "agent" : FactoryCategory(
                default = DefaultAgent(),
                keep_default=True,
                at_least_one=True
            ),
            "mcp" : FactoryCategory(
                default = None,
                keep_default=False,
                at_least_one=False
            ),
        }

    async def load_objects(self, cat):
        """Collect objects instantiated by plugins (llms, auth handlers, agents, etc)."""

        for category_name, category in self.categories.items():
            category.objects = await cat.mad_hatter.execute_hook(
                f"factory_allowed_{category_name}s", {}, cat
            )
            # TODOV2: should add type checks (have method in FactoryCategory)

            if category.keep_default or (category.at_least_one and len(category.objects) == 0):
                category.objects["default"] = category.default
                
    def get_objects(self, category_name: str):
        return self.categories[category_name].objects

    def get_default(self, category_name: str):
        return self.categories[category_name].default
