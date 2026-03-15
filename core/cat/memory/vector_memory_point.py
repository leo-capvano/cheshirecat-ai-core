from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VectorMemoryPoint:
    """Vendor-neutral representation of a point stored in vector memory.

    Attributes
    ----------
    id : str
        Unique identifier for the point.
    vector : List[float]
        The embedding vector.
    payload : Dict[str, Any]
        Contains 'page_content' and 'metadata' keys.
    """

    id: str
    vector: List[float]
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionInfo:
    """Vendor-neutral collection metadata.

    Attributes
    ----------
    points_count : int
        Number of points stored in the collection.
    """

    points_count: int
