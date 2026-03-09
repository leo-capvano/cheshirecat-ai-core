from typing import List, TYPE_CHECKING
from abc import abstractmethod

from langchain_core.embeddings import Embeddings

from cat.services.service import SingletonService

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from cat.types import Message
    from cat.mad_hatter.decorators import Tool


class ModelProvider(SingletonService):
    """
    Base class to expose deep learning models.

    ModelProviders are singleton services that make LLM calls directly
    and provide factory methods for embedders.
    """

    service_type = "model_providers"

    async def setup(self):
        """
        Setup the vendor (e.g. load API keys from settings).

        Override this method to load configuration (API keys, hosts, etc.).
        """
        pass

    def list_llms(self) -> List[str]:
        """
        Return a list of available LLM slugs (without provider prefix).

        Example: ["gpt-4", "gpt-3.5-turbo"]

        Override this in subclasses.
        """
        return []

    def list_embedders(self) -> List[str]:
        """
        Return a list of available embedder slugs (without provider prefix).

        Example: ["text-embedding-3-small", "text-embedding-ada-002"]

        Override this in subclasses.
        """
        return []

    @abstractmethod
    async def llm(
        self,
        model: str,
        messages: list["Message"],
        system_prompt: str = "",
        tools: list["Tool"] = [],
        on_token: "Callable[[str], Awaitable[None]] | None" = None,
    ) -> "Message":
        """
        Chat completion.

        Parameters
        ----------
        model : str
            Model identifier (e.g. "gpt-4", "llama3").
        messages : list[Message]
            Conversation history (user, assistant, tool messages).
        system_prompt : str
            System instructions.
        tools : list[Tool]
            Available tools. Each has .name, .description, .input_schema.
        on_token : callback
            If provided, enables streaming. Called with each text delta
            as it arrives.

        Returns
        -------
        Message
            Complete assistant Message with role="assistant",
            content=[TextContent(...)], and optionally
            tool_calls=[{"id": ..., "name": ..., "args": {...}}, ...]
        """
        ...

    async def get_embedder(self, slug: str) -> Embeddings | None:
        """
        Create and return an Embedder instance for the given slug.

        Parameters
        ----------
        slug : str
            The embedder slug (without provider prefix, e.g., "text-embedding-3-small").

        Returns
        -------
        Embeddings | None
            The Embedder instance if the slug is valid, None otherwise.

        Override this in subclasses to implement embedder instantiation.
        """
        return None
