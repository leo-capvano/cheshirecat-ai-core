
from pydantic import BaseModel, ConfigDict

class FactoryObjectMetadata(BaseModel):
    
    slug: str
    name: str
    description: str
    plugin_id: str | None
    factory_type: str | None = None

    # allow extra fields
    model_config = ConfigDict(extra="allow")

class CatFactoryObject:
    """Base class for factory objects (model, agent, auth handler, etc.)."""
    
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    plugin_id: str | None = None
    factory_type: str | None = None

    @classmethod
    def get_factory_metadata(cls) -> FactoryObjectMetadata:
        return FactoryObjectMetadata(
            slug=cls.slug,
            name=cls.name,
            description=cls.description,
            plugin_id=cls.plugin_id,
            factory_type=cls.factory_type,
        )