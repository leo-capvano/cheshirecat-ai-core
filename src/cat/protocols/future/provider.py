from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from cat.mad_hatter.decorators import CatFactoryObject

from .llm import DefaultLLM
from .embedder import DefaultEmbedder

class BaseModelProvider(CatFactoryObject):
    """Base LLM class for all LLM implementations."""
    
    factory_type = "model"

    async def setup(self, cat):
        """Setup the vendor (e.g. load API keys from settings)."""
        self.llms = {}
        self.embedders = {}

    async def get_llms(self, cat) -> Dict[str, BaseChatModel]:
        """Return a dictionary: slug -> LLM instance."""
        return self.llms
    
    async def get_embedders(self, cat) -> Dict[str, Embeddings]:
        """Return a dictionary: slug -> Embedder instance."""
        return self.embedders
    
class DefaultModels(BaseModelProvider):
    """Default model provider (placeholder models)."""

    slug = "default"
    name = "Default model provider"
    description = "Default model provider with placeholder models."

    async def setup(self, cat):
        """Setup the vendor (e.g. load API keys from settings)."""
        self.llms = {
            "default": DefaultLLM()
        }
        self.embedders = {
            "default": DefaultEmbedder()
        }