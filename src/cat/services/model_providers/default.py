import random
from typing import List, TYPE_CHECKING
from collections.abc import Awaitable, Callable

from .base import ModelProvider
from ...types import Message
from ...protocols.model_context.type_wrappers import TextContent

if TYPE_CHECKING:
    from cat.mad_hatter.decorators import Tool


class DefaultModelProvider(ModelProvider):
    """Default model provider (placeholder models)."""

    slug = "default"
    name = "Default model provider"
    description = "Default model provider with placeholder models."

    async def setup(self):
        pass

    def list_llms(self) -> List[str]:
        return ["default"]

    def list_embedders(self) -> List[str]:
        return ["default"]

    async def llm(
        self,
        model: str,
        messages: list[Message],
        system_prompt: str = "",
        tools: list["Tool"] = [],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> Message:
        text = "You did not configure a Language Model. Do it in the settings!"
        return Message(
            role="assistant",
            content=[TextContent(text=text)]
        )

    async def embed(self, text: str, model: str) -> list[float]:
        return [random.random() for _ in range(8)]
