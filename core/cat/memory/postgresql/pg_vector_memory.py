import psycopg2

from cat.memory.vector_memory import VectorMemory
from cat.memory.vector_memory_point import CollectionInfo
from cat.memory.postgresql.pg_vector_memory_collection import PostgreSQLVectorMemoryCollection
from cat.log import log
from cat.env import get_env


class PostgreSQLVectorMemory(VectorMemory):
    """PostgreSQL + pgvector implementation of VectorMemory.

    Configure via env variables:
        CCAT_POSTGRESQL_HOST (default: localhost)
        CCAT_POSTGRESQL_PORT (default: 5432)
        CCAT_POSTGRESQL_USER (default: ccat)
        CCAT_POSTGRESQL_PASSWORD (default: ccat)
        CCAT_POSTGRESQL_DB   (default: ccat)
    """

    def connect_to_vector_memory(self) -> None:
        host = get_env("CCAT_POSTGRESQL_HOST") or "localhost"
        port = int(get_env("CCAT_POSTGRESQL_PORT") or "5432")
        user = get_env("CCAT_POSTGRESQL_USER") or "ccat"
        password = get_env("CCAT_POSTGRESQL_PASSWORD") or "ccat"
        dbname = get_env("CCAT_POSTGRESQL_DB") or "ccat"

        log.info(f"Connecting to PostgreSQL at {host}:{port}/{dbname}")

        self.connection = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
        )
        self.connection.autocommit = False

    def _create_collection(self, collection_name, embedder_name, embedder_size):
        return PostgreSQLVectorMemoryCollection(
            connection=self.connection,
            collection_name=collection_name,
            embedder_name=embedder_name,
            embedder_size=embedder_size,
        )

    def delete_collection(self, collection_name: str):
        """Delete a collection (drop the table)."""
        safe_name = "".join(
            c if c.isalnum() or c == "_" else "_" for c in collection_name
        )
        table_name = f"vector_{safe_name}"
        with self.connection.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.connection.commit()
        log.warning(f"Dropped PostgreSQL table '{table_name}'")
        return True

    def get_collection(self, collection_name: str) -> CollectionInfo:
        """Get collection info."""
        safe_name = "".join(
            c if c.isalnum() or c == "_" else "_" for c in collection_name
        )
        table_name = f"vector_{safe_name}"
        with self.connection.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
        return CollectionInfo(points_count=count)
