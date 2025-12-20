from typing import List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from .base import ModelProvider
from ...protocols.future.llm import DefaultLLM
from ...protocols.future.embedder import DefaultEmbedder

class DefaultModelProvider(ModelProvider):
    """Default model provider (placeholder models)."""

    slug = "default"
    name = "Default model provider"
    description = "Default model provider with placeholder models."

    async def setup(self):
        """Setup is minimal for default provider."""
        pass

    def list_llms(self) -> List[str]:
        """Return list of available LLM slugs."""
        return ["default"]

    def list_embedders(self) -> List[str]:
        """Return list of available embedder slugs."""
        return ["default"]

    async def get_llm(self, slug: str) -> BaseChatModel:
        """Create and return LLM instance."""
        return DefaultLLM()

    async def get_embedder(self, slug: str) -> Embeddings:
        """Create and return embedder instance."""
        return DefaultEmbedder()