from typing import Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from cat.services.service import SingletonService

from ...protocols.future.llm import DefaultLLM
from ...protocols.future.embedder import DefaultEmbedder

# TODOV2: would be cool to:
# - totally eradicate langchain from core
# - allow plugins to expose also image generators, audio (stt and tts) and others.
class ModelProvider(SingletonService):
    """Base class to expose deep learning models."""

    service_type = "model_provider"

    async def setup(self):
        """Setup the vendor (e.g. load available model slugs, load API keys from settings)."""

        # load plugin settings
        #settings = await

        self.llms = {}
        self.embedders = {}

    async def get_llms(self, cat) -> Dict[str, BaseChatModel]:
        """Return a dictionary: slug -> LLM instance."""
        return self.llms
    
    async def get_embedders(self, cat) -> Dict[str, Embeddings]:
        """Return a dictionary: slug -> Embedder instance."""
        return self.embedders
    
    async def get_meta(self):
        meta = await super().get_meta()
        meta.llms = list(self.llms.keys())
        meta.embedders = list(self.embedders.keys())
        return meta