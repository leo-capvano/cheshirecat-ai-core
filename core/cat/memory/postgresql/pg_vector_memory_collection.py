import json
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from cat.env import get_env
from cat.log import log
from cat.memory.postgresql.qdrant_filter_to_pg import build_where_from_metadata
from cat.memory.vector_memory_collection import VectorMemoryCollection
from cat.memory.vector_memory_point import VectorMemoryPoint
from langchain.docstore.document import Document


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
        vector_memory,
        collection_name: str,
        embedder_name: str,
        embedder_size: int,
        schema: str = "public",
    ):
        super().__init__(
            collection_name=collection_name,
            embedder_name=embedder_name,
            embedder_size=embedder_size,
        )
        self._schema = schema

        self._vector_memory = vector_memory

        self._log_queries = get_env("CCAT_POSTGRESQL_LOG_QUERIES") == "true"

        # Optional: promote metadata keys to dedicated columns.
        # If CCAT_POSTGRESQL_METADATA_COLS is not set/empty, the collection
        # falls back to the legacy single-table behavior (JSONB extraction).
        self._promoted_metadata_cols = [
            c for c in self._parse_csv_env("CCAT_POSTGRESQL_METADATA_COLS") if c != "id"
        ]

        # Optional: customize conflict target for upsert.
        # If CCAT_POSTGRESQL_PRIMARY_KEY_COLS is not set/empty, default to (id).
        self._primary_key_cols = self._parse_csv_env("CCAT_POSTGRESQL_PRIMARY_KEY_COLS")
        if not self._primary_key_cols:
            self._primary_key_cols = ["id"]

        if "id" not in self._primary_key_cols:
            raise ValueError("CCAT_POSTGRESQL_PRIMARY_KEY_COLS must include 'id'")

        # If the configured PK references columns besides id, those columns must
        # be promoted so we can route inserts/upserts and build the conflict target.
        missing_from_promoted = [
            c
            for c in self._primary_key_cols
            if c != "id" and c not in self._promoted_metadata_cols
        ]
        if missing_from_promoted:
            raise ValueError(
                "CCAT_POSTGRESQL_PRIMARY_KEY_COLS contains columns that are "
                "not present in CCAT_POSTGRESQL_METADATA_COLS: "
                + ",".join(missing_from_promoted)
            )

        log.debug(f"PostgreSQL collection '{self.collection_name}' ready")

    @staticmethod
    def _parse_csv_env(name: str) -> List[str]:
        raw = get_env(name)
        if not raw:
            return []
        # preserve order, strip spaces, drop empties
        return [p.strip() for p in str(raw).split(",") if p.strip()]

    def _log_query(self, cur, query: str, params) -> None:
        """Log the fully-rendered SQL query when CCAT_POSTGRESQL_LOG_QUERIES=true.

        Uses psycopg2's mogrify() to substitute %s placeholders with
        actual parameter values, producing a copy-pasteable SQL string.
        """
        if not self._log_queries:
            return
        try:
            rendered = cur.mogrify(query, params)
            if isinstance(rendered, bytes):
                rendered = rendered.decode("utf-8", errors="replace")
            log.info(f"[PG-QUERY] collection={self.collection_name}\n{rendered}")
        except Exception as e:
            log.warning(f"[PG-QUERY] could not render query: {e}")

    @property
    def _table_name(self) -> str:
        """Schema-qualified, sanitized table name for this collection."""
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in self.collection_name)
        safe_schema = "".join(c if c.isalnum() or c == "_" else "_" for c in self._schema)
        return f"{safe_schema}.vector_{safe}"

    @property
    def _uses_promoted_metadata_columns(self) -> bool:
        return bool(self._promoted_metadata_cols)

    def _get_promoted_cols_from_metadata(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Optional[str]]:
        metadata = metadata or {}
        values: Dict[str, Optional[str]] = {}
        for col in self._promoted_metadata_cols:
            val = metadata.get(col)
            values[col] = str(val) if val is not None else None

        # If a promoted column participates in the configured PK, it must be present.
        for pk_col in self._primary_key_cols:
            if pk_col == "id":
                continue
            if pk_col in values and not values[pk_col]:
                raise ValueError(
                    f"PostgreSQL collection requires metadata['{pk_col}'] "
                    f"because it's part of the primary key ({','.join(self._primary_key_cols)})"
                )
        return values

    def _get_upsert_sql(self) -> str:
        if self._uses_promoted_metadata_columns:
            insert_cols: List[str] = (
                ["id"]
                + list(self._promoted_metadata_cols)
                + ["embedding", "page_content", "metadata", "embedder_name"]
            )
            placeholders = ", ".join(["%s"] * len(insert_cols))

            # Do not update primary key columns
            pk_set = set(self._primary_key_cols)
            update_cols = [
                c for c in self._promoted_metadata_cols if c not in pk_set
            ] + ["embedding", "page_content", "metadata", "embedder_name"]
            update_set = ",\n                    ".join(
                f"{c} = EXCLUDED.{c}" for c in update_cols
            )

            return f"""
                INSERT INTO {self._table_name} ({', '.join(insert_cols)})
                VALUES ({placeholders})
                ON CONFLICT ({', '.join(self._primary_key_cols)}) DO UPDATE SET
                    {update_set}
            """

        return f"""
            INSERT INTO {self._table_name} (id, embedding, page_content, metadata, embedder_name)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                page_content = EXCLUDED.page_content,
                metadata = EXCLUDED.metadata,
                embedder_name = EXCLUDED.embedder_name
        """

    def _get_upsert_params(
        self, point_id: str, vector: List[float], content: str, metadata: Optional[dict]
    ) -> Tuple[Any, ...]:
        if self._uses_promoted_metadata_columns:
            promoted = self._get_promoted_cols_from_metadata(metadata)
            promoted_values: Sequence[Optional[str]] = tuple(
                promoted.get(c) for c in self._promoted_metadata_cols
            )
            return (
                point_id,
                *promoted_values,
                str(vector),
                content,
                json.dumps(metadata) if metadata else None,
                self.embedder_name,
            )

        return (
            point_id,
            str(vector),
            content,
            json.dumps(metadata) if metadata else None,
            self.embedder_name,
        )

    def create_db_collection_if_not_exists(self):
        """No-op: the database schema and tables must be created externally."""
        pass

    def check_embedding_size(self):
        """No-op: embedder compatibility must be managed externally."""
        pass

    def create_collection(self):
        """No-op: collections must be created externally."""
        pass

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
        query = self._get_upsert_sql()
        params = self._get_upsert_params(point_id, vector_list, content, metadata)

        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()
        except Exception as e:
            log.error(f"PostgreSQL error in add_point: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

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
        query = self._get_upsert_sql()

        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                for point_id, payload, vector in zip(ids, payloads, vectors):
                    cur.execute(
                        query,
                        self._get_upsert_params(
                            point_id,
                            list(vector),
                            payload.get("page_content", ""),
                            payload.get("metadata"),
                        ),
                    )
            conn.commit()
        except Exception as e:
            log.error(f"PostgreSQL error in add_points_batch: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

    def _build_where_from_metadata(self, metadata: dict):
        return build_where_from_metadata(
            metadata, promoted_cols=self._promoted_metadata_cols
        )

    def delete_points_by_metadata_filter(self, metadata=None):
        if not metadata:
            return

        where_clause, values = self._build_where_from_metadata(metadata)
        if not where_clause:
            return

        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self._table_name} {where_clause}",
                    values,
                )
                deleted = cur.rowcount
            conn.commit()
        except Exception as e:
            log.error(f"PostgreSQL error in delete_points_by_metadata_filter: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

        return deleted

    def delete_points(self, points_ids):
        if not points_ids:
            return
        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(points_ids))
                cur.execute(
                    f"DELETE FROM {self._table_name} WHERE id IN ({placeholders})",
                    points_ids,
                )
            conn.commit()
        except Exception as e:
            log.error(f"PostgreSQL error in delete_points: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

    def recall_memories_from_embedding(
        self, embedding, metadata: dict = None, k: int = 5, threshold: float = None
    ) -> List[Tuple[Document, float, List[float], str]]:
        vector_str = str(list(embedding))

        where_clause, where_values = self._build_where_from_metadata(metadata)

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
        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                self._log_query(cur, query, params)
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
        except Exception as e:
            log.error(f"PostgreSQL error in recall_memories_from_embedding: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

        return results

    def _recall_memories_from_fts(
        self,
        fts_query: str,
        metadata: dict = None,
        k_fts: int = 3,
        fts_threshold: float = 0.0,
        fts_language: str = "simple",
    ) -> List[Tuple[Document, float, List[float], str]]:
        """Run a full-text search against the page_content_fts_vector column.

        Requires the column and a DB trigger to be set up externally.
        Uses immutable_unaccent (expected in the same schema) for
        accent-insensitive matching.

        Returns the same tuple shape as recall_memories_from_embedding.
        """
        if not fts_query:
            return []

        where_clause, where_values = self._build_where_from_metadata(metadata)

        safe_schema = "".join(c if c.isalnum() or c == "_" else "_" for c in self._schema)
        immutable_unaccent_fn = f"{safe_schema}.immutable_unaccent"

        fts_condition = (
            f"page_content_fts_vector @@ websearch_to_tsquery(%s, {immutable_unaccent_fn}(coalesce(%s, '')))"
        )
        fts_rank = f"ts_rank_cd(page_content_fts_vector, websearch_to_tsquery(%s, {immutable_unaccent_fn}(coalesce(%s, ''))), 34)"

        if where_clause:
            full_where = f"{where_clause} AND {fts_condition}"
        else:
            full_where = f"WHERE {fts_condition}"

        query = f"""
            SELECT id, page_content, metadata, embedding::text, {fts_rank} AS score
            FROM {self._table_name}
            {full_where}
            ORDER BY score DESC
            LIMIT %s
        """
        params = [fts_language, fts_query] + where_values + [fts_language, fts_query] + [k_fts]

        results = []
        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                self._log_query(cur, query, params)
                cur.execute(query, params)
                for row in cur.fetchall():
                    row_id, page_content, meta, vec_str, score = row
                    if fts_threshold is not None and score < fts_threshold:
                        continue

                    vector_embeddings = [float(x) for x in vec_str.strip("[]").split(",")] if vec_str else []
                    results.append(
                        (
                            Document(
                                page_content=page_content or "",
                                metadata=meta or {},
                            ),
                            float(score),
                            vector_embeddings,
                            row_id,
                        )
                    )
        except Exception as e:
            log.error(f"PostgreSQL error in _recall_memories_from_fts: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

        return results

    def recall_memories_hybrid(
        self,
        embedding,
        fts_query: str = "",
        metadata=None,
        k: int = 5,
        threshold: float = None,
        k_fts: int = 0,
        fts_threshold: float = 0.0,
        fts_language: str = "simple",
    ) -> List[Tuple[Document, float, List[float], str]]:
        """Hybrid recall: semantic search + full-text search, merged.

        When FTS is enabled (k_fts > 0 and fts_query non-empty), runs both
        searches in a single SQL statement (UNION ALL) on one connection.
        The merge keeps every semantic result, then appends FTS-only results
        (those whose id does not appear in the semantic set).

        When FTS is disabled, falls back to a plain semantic query.
        """
        # Fast path: FTS disabled → pure semantic
        if k_fts <= 0 or not fts_query:
            return self.recall_memories_from_embedding(embedding, metadata=metadata, k=k, threshold=threshold)

        vector_str = str(list(embedding))
        where_clause, where_values = self._build_where_from_metadata(metadata)

        # --- semantic CTE ------------------------------------------------
        semantic_sql = f"""
            SELECT id, page_content, metadata, embedding::text,
                   1 - (embedding <=> %s::vector) AS score,
                   'semantic' AS source
            FROM {self._table_name}
            {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        semantic_params = [vector_str] + where_values + [vector_str, k]

        # --- FTS CTE -----------------------------------------------------
        safe_schema = "".join(c if c.isalnum() or c == "_" else "_" for c in self._schema)
        immutable_unaccent_fn = f"{safe_schema}.immutable_unaccent"

        fts_condition = (
            f"page_content_fts_vector @@ websearch_to_tsquery(%s, {immutable_unaccent_fn}(coalesce(%s, '')))"
        )
        fts_rank = f"ts_rank_cd(page_content_fts_vector, websearch_to_tsquery(%s, {immutable_unaccent_fn}(coalesce(%s, ''))), 34)"

        if where_clause:
            fts_where = f"{where_clause} AND {fts_condition}"
        else:
            fts_where = f"WHERE {fts_condition}"

        fts_sql = f"""
            SELECT id, page_content, metadata, embedding::text,
                   {fts_rank} AS score,
                   'fts' AS source
            FROM {self._table_name}
            {fts_where}
            ORDER BY score DESC
            LIMIT %s
        """
        fts_params = [fts_language, fts_query] + where_values + [fts_language, fts_query] + [k_fts]

        # --- combined query using CTEs -----------------------------------
        query = f"""
            WITH semantic AS ({semantic_sql}),
                 fts AS ({fts_sql})
            SELECT * FROM semantic
            UNION ALL
            SELECT * FROM fts WHERE fts.id NOT IN (SELECT id FROM semantic)
        """
        params = semantic_params + fts_params

        semantic_results = []
        fts_results = []
        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
                self._log_query(cur, query, params)
                cur.execute(query, params)
                for row in cur.fetchall():
                    row_id, page_content, meta, vec_str, score, source = row

                    # Apply per-source thresholds
                    if source == "semantic" and threshold is not None and score < threshold:
                        continue
                    if source == "fts" and fts_threshold is not None and score < fts_threshold:
                        continue

                    vec = [float(x) for x in vec_str.strip("[]").split(",")] if vec_str else []
                    doc_tuple = (
                        Document(page_content=page_content or "", metadata=meta or {}),
                        float(score),
                        vec,
                        row_id,
                    )
                    if source == "semantic":
                        semantic_results.append(doc_tuple)
                    else:
                        fts_results.append(doc_tuple)
        except Exception as e:
            log.error(f"PostgreSQL error in recall_memories_hybrid: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

        log.info(f"Hybrid recall results: {len(semantic_results)} semantic, {len(fts_results)} FTS-only")
        return semantic_results + fts_results

    def get_points(self, ids: List[str]) -> List[VectorMemoryPoint]:
        if not ids:
            return []

        placeholders = ",".join(["%s"] * len(ids))
        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
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
                    vec = [float(x) for x in vec_str.strip("[]").split(",")] if vec_str else []
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
        except Exception as e:
            log.error(f"PostgreSQL error in get_points: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)
        return results

    def get_all_points(
        self,
        limit: int = 10000,
        offset: Optional[str] = None,
    ) -> Tuple[List[VectorMemoryPoint], Optional[str]]:
        conn = self._vector_memory.get_connection()
        try:
            with conn.cursor() as cur:
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
                    vec = [float(x) for x in vec_str.strip("[]").split(",")] if vec_str else []
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
        except Exception as e:
            log.error(f"PostgreSQL error in get_all_points: {e}")
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            self._vector_memory.put_connection(conn)

        next_offset = points[-1].id if len(points) == limit else None
        return points, next_offset

    def db_is_remote(self) -> bool:
        return True

    def save_dump(self, folder="dormouse/"):
        log.warning(
            f"PostgreSQL snapshot for collection '{self.collection_name}' "
            "is not yet implemented. Consider using pg_dump."
        )
