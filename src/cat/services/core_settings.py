from pydantic import BaseModel

from cat.services.service import SingletonService


class CoreSettings(SingletonService):
    """Framework-wide installation settings (default LLM, embedder, etc.)."""

    service_type = "core"
    slug = "core"
    name = "Core Settings"
    description = "Framework-wide installation defaults."
    plugin_id = "core"

    class Settings(BaseModel):
        default_llm: str = "default:default"
        default_embedder: str = "default:default"
