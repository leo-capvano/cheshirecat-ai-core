import uuid
import json
import os
from typing import Any, List, Iterable, Optional, Tuple

from langchain.docstore.document import Document

from cat.log import log
from cat.env import get_env
from cat.memory.vector_memory_collection import VectorMemoryCollection
from cat.memory.vector_memory_point import VectorMemoryPoint


class PostgreSQLVectorMemoryCollection(VectorMemoryCollection):
    """PostgreSQL + pgvector implementation of VectorMemoryCollection.

    Requires the 'pgvector' and 'psycopg2' (or 'psycopg') packages.
    Set up with:
        pip install pgvector psycopg2-binary

    The following env variables configure the connection (set in VectorMemory):
        CCAT_POSTGRESQL_HOST, CCAT_POSTGRESQL_PORT, CCAT_POSTGRESQL_USER,
        CCAT_POSTGRESQL_PASSWORD, CCAT_POSTGRESQL_DB
    """

    def __init__(
        self,
        connection,
        collection_name: str,
        embedder_name: str,
        embedder_size: int,
    ):
        super().__init__(
            collection_name=collection_name,
            embedder_name=embedder_name,
            embedder_size=embedder_size,
        )
        self._hnsw_m = int(os.getenv("CCAT_POSTGRESQL_HNSW_M", "16"))
        self._hnsw_ef_construction = int(
            os.getenv("CCAT_POSTGRESQL_HNSW_EF_CONSTRUCTION", "64")
        )
        self._hnsw_operator_class = os.getenv(
            "CCAT_POSTGRESQL_HNSW_OPERATOR_CLASS", "vector_cosine_ops"
        )

        self.connection = connection

        self.create_db_collection_if_not_exists()
        self.check_embedding_size()

        log.debug(f"PostgreSQL collection '{self.collection_name}' ready")

    @property
    def _table_name(self) -> str:
        """Sanitized table name for this collection."""
        # Only allow alphanumeric and underscore
        safe = "".join(
            c if c.isalnum() or c == "_" else "_" for c in self.collection_name
        )
        return f"vector_{safe}"

    def create_db_collection_if_not_exists(self):
        """Create the pgvector table if it doesn't exist."""
        with self.connection.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    id TEXT PRIMARY KEY,
                    embedding vector({self.embedder_size}),
                    page_content TEXT,
                    metadata JSONB,
                    embedder_name TEXT
                )
                """
            )
            # HNSW index creation
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table_name}_embedding
                ON {self._table_name}
                USING hnsw (embedding {self._hnsw_operator_class})
                WITH (m={self._hnsw_m}, ef_construction={self._hnsw_ef_construction})
                """
            )
            self.connection.commit()

    def check_embedding_size(self):
        """Check if current embedder matches. If not, recreate the table."""
        with self.connection.cursor() as cur:
            # Check stored embedder name
            cur.execute(f"SELECT embedder_name FROM {self._table_name} LIMIT 1")
            row = cur.fetchone()

            if row is not None and row[0] != self.embedder_name:
                log.warning(
                    f'Collection "{self.collection_name}" has a different embedder '
                    f"(stored: {row[0]}, current: {self.embedder_name}). Recreating."
                )
                if get_env("CCAT_SAVE_MEMORY_SNAPSHOTS") == "true":
                    self.save_dump()

                cur.execute(f"DROP TABLE IF EXISTS {self._table_name}")
                self.connection.commit()
                self.create_collection()
            else:
                log.debug(f'Collection "{self.collection_name}" embedder check passed')

    def create_collection(self):
        """Drop and recreate the collection table."""
        self.create_db_collection_if_not_exists()

    def add_point(
        self,
        content: str,
        vector: Iterable,
        metadata: dict = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[VectorMemoryPoint]:
        point_id = id or uuid.uuid4().hex
        vector_list = list(vector)

        with self.connection.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self._table_name} (id, embedding, page_content, metadata, embedder_name)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    page_content = EXCLUDED.page_content,
                    metadata = EXCLUDED.metadata,
                    embedder_name = EXCLUDED.embedder_name
                """,
                (
                    point_id,
                    str(vector_list),
                    content,
                    json.dumps(metadata) if metadata else None,
                    self.embedder_name,
                ),
            )
            self.connection.commit()

        return VectorMemoryPoint(
            id=point_id,
            vector=vector_list,
            payload={
                "page_content": content,
                "metadata": metadata,
            },
        )

    def add_points_batch(
        self,
        ids: List[str],
        payloads: List[dict],
        vectors: List[List[float]],
        **kwargs: Any,
    ) -> None:
        with self.connection.cursor() as cur:
            for point_id, payload, vector in zip(ids, payloads, vectors):
                cur.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, embedding, page_content, metadata, embedder_name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        page_content = EXCLUDED.page_content,
                        metadata = EXCLUDED.metadata,
                        embedder_name = EXCLUDED.embedder_name
                    """,
                    (
                        point_id,
                        str(list(vector)),
                        payload.get("page_content", ""),
                        (
                            json.dumps(payload.get("metadata"))
                            if payload.get("metadata")
                            else None
                        ),
                        self.embedder_name,
                    ),
                )
            self.connection.commit()

    def delete_points_by_metadata_filter(self, metadata=None):
        if not metadata:
            return

        conditions = []
        values = []
        for key, value in metadata.items():
            conditions.append(f"metadata->>%s = %s")
            values.extend([key, str(value)])

        where_clause = " AND ".join(conditions)
        with self.connection.cursor() as cur:
            cur.execute(
                f"DELETE FROM {self._table_name} WHERE {where_clause}",
                values,
            )
            self.connection.commit()

    def delete_points(self, points_ids):
        if not points_ids:
            return
        with self.connection.cursor() as cur:
            placeholders = ",".join(["%s"] * len(points_ids))
            cur.execute(
                f"DELETE FROM {self._table_name} WHERE id IN ({placeholders})",
                points_ids,
            )
            self.connection.commit()

    def recall_memories_from_embedding(
        self, embedding, metadata=None, k=5, threshold=None
    ) -> List[Tuple[Document, float, List[float], str]]:
        vector_str = str(list(embedding))

        where_parts = []
        where_values = []
        if metadata:
            for key, value in metadata.items():
                where_parts.append(f"metadata->>%s = %s")
                where_values.extend([key, str(value)])

        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)

        # cosine distance: 1 - similarity; lower = more similar
        query = f"""
            SELECT id, page_content, metadata, embedding::text,
                   1 - (embedding <=> %s::vector) AS score
            FROM {self._table_name}
            {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params = [vector_str] + where_values + [vector_str, k]

        results = []
        with self.connection.cursor() as cur:
            cur.execute(query, params)
            for row in cur.fetchall():
                point_id, page_content, meta, vec_str, score = row
                if threshold is not None and score < threshold:
                    continue
                # Parse vector from string
                vec = [float(x) for x in vec_str.strip("[]").split(",")]
                results.append(
                    (
                        Document(
                            page_content=page_content or "",
                            metadata=meta or {},
                        ),
                        float(score),
                        vec,
                        point_id,
                    )
                )

        return results

    def get_points(self, ids: List[str]) -> List[VectorMemoryPoint]:
        if not ids:
            return []

        placeholders = ",".join(["%s"] * len(ids))
        with self.connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, page_content, metadata, embedding::text
                FROM {self._table_name}
                WHERE id IN ({placeholders})
                """,
                ids,
            )
            results = []
            for row in cur.fetchall():
                point_id, page_content, meta, vec_str = row
                vec = (
                    [float(x) for x in vec_str.strip("[]").split(",")]
                    if vec_str
                    else []
                )
                results.append(
                    VectorMemoryPoint(
                        id=point_id,
                        vector=vec,
                        payload={
                            "page_content": page_content,
                            "metadata": meta or {},
                        },
                    )
                )
            return results

    def get_all_points(
        self,
        limit: int = 10000,
        offset: Optional[str] = None,
    ) -> Tuple[List[VectorMemoryPoint], Optional[str]]:
        with self.connection.cursor() as cur:
            if offset:
                cur.execute(
                    f"""
                    SELECT id, page_content, metadata, embedding::text
                    FROM {self._table_name}
                    WHERE id > %s
                    ORDER BY id
                    LIMIT %s
                    """,
                    (offset, limit),
                )
            else:
                cur.execute(
                    f"""
                    SELECT id, page_content, metadata, embedding::text
                    FROM {self._table_name}
                    ORDER BY id
                    LIMIT %s
                    """,
                    (limit,),
                )

            points = []
            for row in cur.fetchall():
                point_id, page_content, meta, vec_str = row
                vec = (
                    [float(x) for x in vec_str.strip("[]").split(",")]
                    if vec_str
                    else []
                )
                points.append(
                    VectorMemoryPoint(
                        id=point_id,
                        vector=vec,
                        payload={
                            "page_content": page_content,
                            "metadata": meta or {},
                        },
                    )
                )

            next_offset = points[-1].id if len(points) == limit else None
            return points, next_offset

    def db_is_remote(self) -> bool:
        return True

    def save_dump(self, folder="dormouse/"):
        log.warning(
            f"PostgreSQL snapshot for collection '{self.collection_name}' "
            "is not yet implemented. Consider using pg_dump."
        )
