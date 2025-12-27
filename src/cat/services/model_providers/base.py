from typing import Dict, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from cat.services.service import SingletonService


# TODOV2: would be cool to:
# - totally eradicate langchain from core
# - allow plugins to expose also image generators, audio (stt and tts) and others.
class ModelProvider(SingletonService):
    """
    Base class to expose deep learning models.

    ModelProviders are singleton services that provide factory methods to create
    LLM and Embedder instances on-demand, rather than pre-creating all instances.
    """

    service_type = "model_providers"


    async def setup(self):
        """
        Setup the vendor (e.g. load API keys from settings).

        Override this method to load configuration (API keys, hosts, etc.)
        but do NOT create model instances here. Models should be created
        on-demand via get_llm() and get_embedder().
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

    async def get_llm(self, slug: str) -> BaseChatModel | None:
        """
        Create and return an LLM instance for the given slug.

        Parameters
        ----------
        slug : str
            The model slug (without provider prefix, e.g., "gpt-4").

        Returns
        -------
        BaseChatModel | None
            The LLM instance if the slug is valid, None otherwise.

        Override this in subclasses to implement model instantiation.
        """
        return None

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

    async def get_meta(self):
        """Get metadata including available model lists."""
        meta = await super().get_meta()
        meta.llms = self.list_llms()
        meta.embedders = self.list_embedders()
        return meta