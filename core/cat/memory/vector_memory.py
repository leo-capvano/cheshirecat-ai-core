from abc import ABC, abstractmethod

from cat.memory.vector_memory_point import CollectionInfo
from cat.log import log
from cat.env import get_env


class VectorMemory(ABC):
    """Abstract base class for vector memory.

    Manages connection to the vector database and creates collections.
    Subclasses must implement connect_to_vector_memory, _create_collection,
    delete_collection, and get_collection.
    """

    def __init__(
        self,
        embedder_name=None,
        embedder_size=None,
    ) -> None:
        # connects to the vector DB (implementation-specific)
        self.connect_to_vector_memory()

        # Create vector collections
        # - Episodic memory will contain user and eventually cat utterances
        # - Declarative memory will contain uploaded documents' content
        # - Procedural memory will contain tools and knowledge on how to do things
        self.collections = {}
        for collection_name in ["episodic", "declarative", "procedural"]:
            # Instantiate collection (implementation-specific)
            collection = self._create_collection(
                collection_name=collection_name,
                embedder_name=embedder_name,
                embedder_size=embedder_size,
            )

            # Update dictionary containing all collections
            # Useful for cross-searching and to create/use collections from plugins
            self.collections[collection_name] = collection

            # Have the collection as an instance attribute
            # (i.e. do things like cat.memory.vectors.declarative.something())
            setattr(self, collection_name, collection)

    @abstractmethod
    def connect_to_vector_memory(self) -> None:
        """Connect to the vector database. Must set up any client needed."""
        pass

    @abstractmethod
    def _create_collection(self, collection_name, embedder_name, embedder_size):
        """Create and return a VectorMemoryCollection instance for the given collection."""
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str):
        """Delete a specific vector collection."""
        pass

    @abstractmethod
    def get_collection(self, collection_name: str) -> CollectionInfo:
        """Get collection info. Returns a CollectionInfo with at least points_count."""
        pass


def create_vector_memory(embedder_name=None, embedder_size=None) -> VectorMemory:
    """Factory function to create the appropriate VectorMemory backend.

    The backend is selected via the CCAT_VECTOR_DB env variable.
    Supported values: 'qdrant' (default), 'postgresql'.

    Each backend will have its own configuration via env variables (e.g. connection details).
    """

    vector_db_type = (get_env("CCAT_VECTOR_DB") or "qdrant").lower()

    if vector_db_type == "qdrant":
        from cat.memory.qdrant.qdrant_vector_memory import QdrantVectorMemory
        return QdrantVectorMemory(
            embedder_name=embedder_name,
            embedder_size=embedder_size,
        )
    elif vector_db_type == "postgresql":
        from cat.memory.postgresql.pg_vector_memory import PostgreSQLVectorMemory
        return PostgreSQLVectorMemory(
            embedder_name=embedder_name,
            embedder_size=embedder_size,
        )
    else:
        raise ValueError(
            f"Unsupported vector database type: '{vector_db_type}'. "
            "Supported: 'qdrant', 'postgresql'."
        )
