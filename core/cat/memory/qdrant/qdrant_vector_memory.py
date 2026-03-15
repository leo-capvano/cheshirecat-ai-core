import sys
import socket

from qdrant_client import QdrantClient

from cat.memory.vector_memory import VectorMemory
from cat.memory.vector_memory_point import CollectionInfo
from cat.memory.qdrant.qdrant_vector_memory_collection import QdrantVectorMemoryCollection
from cat.log import log
from cat.env import get_env
from cat.utils import extract_domain_from_url, is_https


class QdrantVectorMemory(VectorMemory):
    """Qdrant implementation of VectorMemory."""

    local_vector_db = None

    def connect_to_vector_memory(self) -> None:
        db_path = "cat/data/local_vector_memory/"
        qdrant_host = get_env("CCAT_QDRANT_HOST")

        if not qdrant_host:
            log.debug(f"Qdrant path: {db_path}")
            # Qdrant local vector DB client

            # reconnect only if it's the first boot and not a reload
            if QdrantVectorMemory.local_vector_db is None:
                QdrantVectorMemory.local_vector_db = QdrantClient(
                    path=db_path, force_disable_check_same_thread=True
                )

            self.vector_db = QdrantVectorMemory.local_vector_db
        else:
            # Qdrant remote or in other container
            qdrant_port = int(get_env("CCAT_QDRANT_PORT"))
            qdrant_https = is_https(qdrant_host)
            qdrant_host = extract_domain_from_url(qdrant_host)
            qdrant_api_key = get_env("CCAT_QDRANT_API_KEY")

            qdrant_client_timeout = get_env("CCAT_QDRANT_CLIENT_TIMEOUT")
            qdrant_client_timeout = int(qdrant_client_timeout) if qdrant_client_timeout is not None else None

            try:
                s = socket.socket()
                s.connect((qdrant_host, qdrant_port))
            except Exception:
                log.error(f"QDrant does not respond to {qdrant_host}:{qdrant_port}")
                sys.exit()
            finally:
                s.close()

            # Qdrant vector DB client
            self.vector_db = QdrantClient(
                host=qdrant_host,
                port=qdrant_port,
                https=qdrant_https,
                api_key=qdrant_api_key,
                timeout=qdrant_client_timeout,
            )

    def _create_collection(self, collection_name, embedder_name, embedder_size):
        return QdrantVectorMemoryCollection(
            client=self.vector_db,
            collection_name=collection_name,
            embedder_name=embedder_name,
            embedder_size=embedder_size,
        )

    def delete_collection(self, collection_name: str):
        """Delete specific vector collection."""
        return self.vector_db.delete_collection(collection_name)

    def get_collection(self, collection_name: str) -> CollectionInfo:
        """Get collection info as a vendor-neutral CollectionInfo."""
        qdrant_info = self.vector_db.get_collection(collection_name)
        return CollectionInfo(points_count=qdrant_info.points_count)
