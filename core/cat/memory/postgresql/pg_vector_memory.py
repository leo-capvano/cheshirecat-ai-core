from psycopg2 import pool

from cat.memory.vector_memory import VectorMemory
from cat.memory.vector_memory_point import CollectionInfo
from cat.memory.postgresql.pg_vector_memory_collection import (
    PostgreSQLVectorMemoryCollection,
)
from cat.log import log
from cat.env import get_env


class PostgreSQLVectorMemory(VectorMemory):
    """PostgreSQL + pgvector implementation of VectorMemory.

    Configure via env variables:
        CCAT_POSTGRESQL_HOST (default: localhost)
        CCAT_POSTGRESQL_PORT (default: 5432)
        CCAT_POSTGRESQL_USER (default: ccat)
        CCAT_POSTGRESQL_PASSWORD (default: ccat)
        CCAT_POSTGRESQL_DB     (default: ccat)
        CCAT_POSTGRESQL_SCHEMA (default: public)
    """

    def connect_to_vector_memory(self) -> None:
        self._host = get_env("CCAT_POSTGRESQL_HOST") or "localhost"
        self._port = int(get_env("CCAT_POSTGRESQL_PORT") or "5432")
        self._user = get_env("CCAT_POSTGRESQL_USER") or "ccat"
        self._password = get_env("CCAT_POSTGRESQL_PASSWORD") or "ccat"
        self._dbname = get_env("CCAT_POSTGRESQL_DB") or "ccat"
        self.schema = get_env("CCAT_POSTGRESQL_SCHEMA") or "public"
        self._min_conn = int(get_env("CCAT_POSTGRESQL_MIN_CONN") or "1")
        self._max_conn = int(get_env("CCAT_POSTGRESQL_MAX_CONN") or "10")

        log.info(
            f"Connecting to PostgreSQL at {self._host}:{self._port}/{self._dbname} "
            f"(schema: {self.schema}, pool: {self._min_conn}-{self._max_conn})"
        )

        safe_schema = "".join(
            c if c.isalnum() or c == "_" else "_" for c in self.schema
        )

        self.pool = pool.ThreadedConnectionPool(
            minconn=self._min_conn,
            maxconn=self._max_conn,
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            dbname=self._dbname,
            options=f"-c search_path={safe_schema},public",
        )

        # Create schema if it doesn't exist
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {safe_schema}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def get_connection(self):
        """Get a connection from the pool."""
        return self.pool.getconn()

    def put_connection(self, conn, close=False):
        """Return a connection to the pool."""
        self.pool.putconn(conn, close=close)

    def close(self):
        """Close all connections in the pool."""
        if hasattr(self, "pool") and self.pool and not self.pool.closed:
            self.pool.closeall()
            log.info("PostgreSQL connection pool closed")

    def __del__(self):
        self.close()

    def _create_collection(self, collection_name, embedder_name, embedder_size):
        return PostgreSQLVectorMemoryCollection(
            vector_memory=self,
            collection_name=collection_name,
            embedder_name=embedder_name,
            embedder_size=embedder_size,
            schema=self.schema,
        )

    def delete_collection(self, collection_name: str):
        """Delete a collection (drop the table)."""
        safe_name = "".join(
            c if c.isalnum() or c == "_" else "_" for c in collection_name
        )
        safe_schema = "".join(
            c if c.isalnum() or c == "_" else "_" for c in self.schema
        )
        table_name = f"{safe_schema}.vector_{safe_name}"
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
        log.warning(f"Dropped PostgreSQL table '{table_name}'")
        return True

    def get_collection(self, collection_name: str) -> CollectionInfo:
        """Get collection info."""
        safe_name = "".join(
            c if c.isalnum() or c == "_" else "_" for c in collection_name
        )
        safe_schema = "".join(
            c if c.isalnum() or c == "_" else "_" for c in self.schema
        )
        table_name = f"{safe_schema}.vector_{safe_name}"
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
        return CollectionInfo(points_count=count)
