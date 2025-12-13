
from pydantic import BaseModel, ConfigDict

class ServiceMetadata(BaseModel):
    
    slug: str
    name: str
    description: str
    plugin_id: str | None
    service_type: str | None = None

    # allow extra fields
    model_config = ConfigDict(extra="allow")

class Service:
    """Base class for factory objects (model, agent, auth handler, etc.)."""
    
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    plugin_id: str | None = None
    service_type: str | None = None

    @classmethod
    def get_factory_metadata(cls) -> ServiceMetadata:
        return ServiceMetadata(
            slug=cls.slug,
            name=cls.name,
            description=cls.description,
            plugin_id=cls.plugin_id,
            service_type=cls.service_type,
        )