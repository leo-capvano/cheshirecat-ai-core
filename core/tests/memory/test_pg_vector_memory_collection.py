import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from cat.memory.postgresql.pg_vector_memory_collection import \
    PostgreSQLVectorMemoryCollection


def _set_env(temp: dict):
    prev = {}
    for k, v in temp.items():
        prev[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return prev


def _restore_env(prev: dict):
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split())


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((_normalize_sql(query), params))

    def mogrify(self, query, params):
        return query.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.closed = 0
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeVectorMemory:
    def __init__(self):
        self.connection = FakeConnection()
        self.returned_connections = []

    def get_connection(self):
        return self.connection

    def put_connection(self, conn, close=False):
        self.returned_connections.append((conn, close))


class TestPostgreSQLVectorMemoryCollection:
    def test_declarative_without_promoted_cols_falls_back_to_legacy_upsert(self):
        prev = _set_env(
            {
                "CCAT_POSTGRESQL_METADATA_COLS": None,
                "CCAT_POSTGRESQL_PRIMARY_KEY_COLS": None,
            }
        )
        vector_memory = FakeVectorMemory()
        try:
            collection = PostgreSQLVectorMemoryCollection(
                vector_memory=vector_memory,
                collection_name="declarative",
                embedder_name="test-embedder",
                embedder_size=3,
                schema="knowledge_base",
            )

            collection.add_point(
                content="hello",
                vector=[0.1, 0.2, 0.3],
                metadata={"source": "manual"},
                id="point-1",
            )

            query, params = vector_memory.connection.cursor_instance.executed[0]
            assert (
                "INSERT INTO knowledge_base.vector_declarative (id, embedding, page_content, metadata, embedder_name)"
                in query
            )
            assert "ON CONFLICT (id) DO UPDATE SET" in query
            assert params == (
                "point-1",
                "[0.1, 0.2, 0.3]",
                "hello",
                '{"source": "manual"}',
                "test-embedder",
            )
        finally:
            _restore_env(prev)

    def test_add_point_uses_partition_routing_columns_for_declarative(self):
        prev = _set_env(
            {
                "CCAT_POSTGRESQL_METADATA_COLS": "tenant,kind,item_id",
                "CCAT_POSTGRESQL_PRIMARY_KEY_COLS": "tenant,id",
            }
        )
        vector_memory = FakeVectorMemory()
        try:
            collection = PostgreSQLVectorMemoryCollection(
                vector_memory=vector_memory,
                collection_name="declarative",
                embedder_name="test-embedder",
                embedder_size=3,
                schema="knowledge_base",
            )

            collection.add_point(
                content="hello",
                vector=[0.1, 0.2, 0.3],
                metadata={
                    "tenant": "tenant-a",
                    "kind": "sharepoint",
                    "item_id": "doc-123",
                    "source": "manual",
                },
                id="point-1",
            )

            query, params = vector_memory.connection.cursor_instance.executed[0]
            assert (
                "INSERT INTO knowledge_base.vector_declarative (id, tenant, kind, item_id, embedding, page_content, metadata, embedder_name)"
                in query
            )
            assert "ON CONFLICT (tenant, id) DO UPDATE SET" in query
            assert "kind = EXCLUDED.kind" in query
            assert "item_id = EXCLUDED.item_id" in query
            assert params[:4] == ("point-1", "tenant-a", "sharepoint", "doc-123")
            assert vector_memory.connection.committed is True
        finally:
            _restore_env(prev)

    def test_add_point_keeps_legacy_upsert_for_non_declarative(self):
        prev = _set_env(
            {
                "CCAT_POSTGRESQL_METADATA_COLS": "",
                "CCAT_POSTGRESQL_PRIMARY_KEY_COLS": "",
            }
        )
        vector_memory = FakeVectorMemory()
        try:
            collection = PostgreSQLVectorMemoryCollection(
                vector_memory=vector_memory,
                collection_name="episodic",
                embedder_name="test-embedder",
                embedder_size=3,
                schema="knowledge_base",
            )

            collection.add_point(
                content="hello",
                vector=[0.1, 0.2, 0.3],
                metadata={"source": "chat"},
                id="point-1",
            )

            query, params = vector_memory.connection.cursor_instance.executed[0]
            assert "INSERT INTO knowledge_base.vector_episodic (id, embedding, page_content, metadata, embedder_name)" in query
            assert "ON CONFLICT (id) DO UPDATE SET" in query
            assert params == (
                "point-1",
                "[0.1, 0.2, 0.3]",
                "hello",
                '{"source": "chat"}',
                "test-embedder",
            )
        finally:
            _restore_env(prev)

    def test_declarative_add_point_requires_domain(self):
        prev = _set_env(
            {
                "CCAT_POSTGRESQL_METADATA_COLS": "tenant,kind,item_id",
                "CCAT_POSTGRESQL_PRIMARY_KEY_COLS": "tenant,id",
            }
        )
        vector_memory = FakeVectorMemory()
        try:
            collection = PostgreSQLVectorMemoryCollection(
                vector_memory=vector_memory,
                collection_name="declarative",
                embedder_name="test-embedder",
                embedder_size=3,
                schema="knowledge_base",
            )

            try:
                collection.add_point(
                    content="hello",
                    vector=[0.1, 0.2, 0.3],
                    metadata={"kind": "sharepoint", "item_id": "doc-123"},
                    id="point-1",
                )
                assert False, "Expected ValueError"
            except ValueError as exc:
                assert "metadata['tenant']" in str(exc)

            assert vector_memory.connection.cursor_instance.executed == []
        finally:
            _restore_env(prev)
