from .base import ModelProvider
from ...protocols.future.llm import DefaultLLM
from ...protocols.future.embedder import DefaultEmbedder

class DefaultModelProvider(ModelProvider):
    """Default model provider (placeholder models)."""

    slug = "default"
    name = "Default model provider"
    description = "Default model provider with placeholder models."

    async def setup(self):
        """Setup the vendor (e.g. load API keys from settings)."""
        self.llms = {
            "default": DefaultLLM()
        }
        self.embedders = {
            "default": DefaultEmbedder()
        }