"""Unit tests for the Qdrant → PostgreSQL filter translation module.

Run with pytest:
    cd core
    python -m pytest tests/memory/test_qdrant_filter_to_pg.py -v

Run as plain script:
    cd core
    python tests/memory/test_qdrant_filter_to_pg.py
"""

import inspect
import os
import sys
import traceback

# Make `cat` importable when running as a plain script (python tests/memory/...)
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from cat.memory.postgresql.qdrant_filter_to_pg import (
    build_pg_filter_clause, build_pg_leaf_condition, build_where_from_metadata,
    parse_qdrant_key_to_jsonb)

# ------------------------------------------------------------------ #
#  parse_qdrant_key_to_jsonb
# ------------------------------------------------------------------ #


class TestParseQdrantKeyToJsonb:
    def test_simple_key_with_metadata_prefix(self):
        sql, params = parse_qdrant_key_to_jsonb("metadata.key1")
        assert sql == "metadata->>%s"
        assert params == ["key1"]

    def test_simple_key_without_prefix(self):
        sql, params = parse_qdrant_key_to_jsonb("key1")
        assert sql == "metadata->>%s"
        assert params == ["key1"]

    def test_nested_key_with_prefix(self):
        sql, params = parse_qdrant_key_to_jsonb("metadata.a.b")
        assert sql == "metadata #>> %s"
        assert params == ["{a,b}"]

    def test_nested_key_without_prefix(self):
        sql, params = parse_qdrant_key_to_jsonb("a.b.c")
        assert sql == "metadata #>> %s"
        assert params == ["{a,b,c}"]

    def test_promoted_key_uses_dedicated_column_when_enabled(self):
        sql, params = parse_qdrant_key_to_jsonb(
            "metadata.tenant", promoted_cols={"tenant"}
        )
        assert sql == "tenant"
        assert params == []


# ------------------------------------------------------------------ #
#  build_pg_leaf_condition
# ------------------------------------------------------------------ #


class TestBuildPgLeafCondition:
    def test_basic_leaf(self):
        cond = {"key": "metadata.key1", "match": {"value": "value1"}}
        sql, params = build_pg_leaf_condition(cond)
        assert sql == "metadata->>%s = %s"
        assert params == ["key1", "value1"]

    def test_numeric_value_converted_to_str(self):
        cond = {"key": "metadata.count", "match": {"value": 42}}
        sql, params = build_pg_leaf_condition(cond)
        assert params == ["count", "42"]

    def test_promoted_key_uses_dedicated_column_when_enabled(self):
        cond = {"key": "metadata.item_id", "match": {"value": "doc-123"}}
        sql, params = build_pg_leaf_condition(cond, promoted_cols={"item_id"})
        assert sql == "item_id = %s"
        assert params == ["doc-123"]


# ------------------------------------------------------------------ #
#  build_pg_filter_clause – must
# ------------------------------------------------------------------ #


class TestMustFilter:
    def test_single_must(self):
        f = {"must": [{"key": "metadata.key1", "match": {"value": "value1"}}]}
        sql, params = build_pg_filter_clause(f)
        assert sql == "(metadata->>%s = %s)"
        assert params == ["key1", "value1"]

    def test_multiple_must(self):
        f = {
            "must": [
                {"key": "metadata.key1", "match": {"value": "value1"}},
                {"key": "metadata.key2", "match": {"value": "value2"}},
            ]
        }
        sql, params = build_pg_filter_clause(f)
        assert sql == "(metadata->>%s = %s AND metadata->>%s = %s)"
        assert params == ["key1", "value1", "key2", "value2"]


# ------------------------------------------------------------------ #
#  build_pg_filter_clause – should
# ------------------------------------------------------------------ #


class TestShouldFilter:
    def test_single_should(self):
        f = {"should": [{"key": "metadata.key3", "match": {"value": "value3"}}]}
        sql, params = build_pg_filter_clause(f)
        assert sql == "(metadata->>%s = %s)"
        assert params == ["key3", "value3"]

    def test_multiple_should(self):
        f = {
            "should": [
                {"key": "metadata.key3", "match": {"value": "value3"}},
                {"key": "metadata.key3", "match": {"value": "value4"}},
            ]
        }
        sql, params = build_pg_filter_clause(f)
        assert sql == "(metadata->>%s = %s OR metadata->>%s = %s)"
        assert params == ["key3", "value3", "key3", "value4"]


# ------------------------------------------------------------------ #
#  build_pg_filter_clause – must_not
# ------------------------------------------------------------------ #


class TestMustNotFilter:
    def test_single_must_not(self):
        f = {"must_not": [{"key": "metadata.key5", "match": {"value": "value5"}}]}
        sql, params = build_pg_filter_clause(f)
        assert sql == "(NOT (metadata->>%s = %s))"
        assert params == ["key5", "value5"]

    def test_multiple_must_not(self):
        f = {
            "must_not": [
                {"key": "metadata.key5", "match": {"value": "value5"}},
                {"key": "metadata.key5", "match": {"value": "value6"}},
            ]
        }
        sql, params = build_pg_filter_clause(f)
        assert sql == "(NOT (metadata->>%s = %s) AND NOT (metadata->>%s = %s))"
        assert params == ["key5", "value5", "key5", "value6"]


# ------------------------------------------------------------------ #
#  build_pg_filter_clause – combined must + should
# ------------------------------------------------------------------ #


class TestCombinedFilter:
    def test_must_and_should(self):
        """The full example from the FE."""
        f = {
            "must": [{"key": "metadata.key1", "match": {"value": "value1"}}],
            "should": [
                {"must": [{"key": "metadata.key3", "match": {"value": "value3"}}]},
                {
                    "must": [
                        {
                            "key": "metadata.key3",
                            "match": {"value": "value4"},
                        }
                    ]
                },
            ],
        }
        sql, params = build_pg_filter_clause(f)
        assert (
            "(metadata->>%s = %s) AND ((metadata->>%s = %s) OR (metadata->>%s = %s))"
            == sql
        )
        assert params == [
            "key1",
            "value1",
            "key3",
            "value3",
            "key3",
            "value4",
        ]

    def test_must_should_must_not(self):
        f = {
            "must": [{"key": "metadata.key1", "match": {"value": "value1"}}],
            "should": [
                {"key": "metadata.key3", "match": {"value": "value3"}},
                {"key": "metadata.key3", "match": {"value": "value4"}},
            ],
            "must_not": [{"key": "metadata.key5", "match": {"value": "value5"}}],
        }
        sql, params = build_pg_filter_clause(f)
        # Three AND-joined groups
        assert (
            sql
            == "(metadata->>%s = %s) AND (metadata->>%s = %s OR metadata->>%s = %s) AND (NOT (metadata->>%s = %s))"
        )
        assert params == [
            "key1",
            "value1",
            "key3",
            "value3",
            "key3",
            "value4",
            "key5",
            "value5",
        ]


# ------------------------------------------------------------------ #
#  build_pg_filter_clause – nested groups
# ------------------------------------------------------------------ #


class TestNestedGroups:
    def test_should_with_nested_must(self):
        """should items that are themselves filter groups (must inside should)."""
        f = {
            "should": [
                {
                    "must": [
                        {"key": "metadata.key3", "match": {"value": "value3"}},
                        {"key": "metadata.key7", "match": {"value": "value7"}},
                    ]
                },
                {
                    "must": [
                        {
                            "key": "metadata.key3",
                            "match": {"value": "value4"},
                        },
                        {"key": "metadata.key8", "match": {"value": "value8"}},
                    ]
                },
            ]
        }
        sql, params = build_pg_filter_clause(f)
        # Each OR branch is a must-AND group
        assert (
            sql
            == "((metadata->>%s = %s AND metadata->>%s = %s) OR (metadata->>%s = %s AND metadata->>%s = %s))"
        )
        assert params == [
            "key3",
            "value3",
            "key7",
            "value7",
            "key3",
            "value4",
            "key8",
            "value8",
        ]


# ------------------------------------------------------------------ #
#  build_pg_filter_clause – edge cases
# ------------------------------------------------------------------ #


class TestEdgeCases:
    def test_empty_filter(self):
        sql, params = build_pg_filter_clause({})
        assert sql == "TRUE"
        assert params == []

    def test_empty_must_list(self):
        sql, params = build_pg_filter_clause({"must": []})
        assert sql == "TRUE"
        assert params == []


# ------------------------------------------------------------------ #
#  build_where_from_metadata
# ------------------------------------------------------------------ #


class TestBuildWhereFromMetadata:
    def test_none_metadata(self):
        sql, params = build_where_from_metadata(None)
        assert sql == ""
        assert params == []

    def test_empty_metadata(self):
        sql, params = build_where_from_metadata({})
        assert sql == ""
        assert params == []

    def test_with_qdrant_dict_filter(self):
        metadata = {
            "key1": "value1",
            "correlation_id": "chat-123",
            "user_filters": {"sources_selection": {}},
            "qdrant_dict_filter": {
                "must": [{"key": "metadata.key1", "match": {"value": "value1"}}],
                "should": [
                    {
                        "must": [
                            {"key": "metadata.key3", "match": {"value": "value3"}}
                        ]
                    },
                    {
                        "must": [
                            {
                                "key": "metadata.key3",
                                "match": {"value": "value4"},
                            }
                        ]
                    },
                ],
            },
        }
        sql, params = build_where_from_metadata(metadata)
        assert (
            sql
            == "WHERE (metadata->>%s = %s) AND ((metadata->>%s = %s) OR (metadata->>%s = %s))"
        )
        assert params == [
            "key1",
            "value1",
            "key3",
            "value3",
            "key3",
            "value4",
        ]

    def test_legacy_flat_metadata(self):
        """Without qdrant_dict_filter, flat key/value pairs become must conditions."""
        metadata = {"source": "user_123"}
        sql, params = build_where_from_metadata(metadata)
        assert sql == "WHERE (metadata->>%s = %s)"
        assert params == ["source", "user_123"]

    def test_qdrant_dict_filter_empty_must(self):
        metadata = {"source": "user_123", "qdrant_dict_filter": {"must": []}}
        sql, params = build_where_from_metadata(metadata)
        assert sql == ""
        assert params == []

    def test_legacy_flat_metadata_uses_promoted_columns_when_enabled(self):
        metadata = {"tenant": "tenant-a", "kind": "file", "source": "legacy"}
        sql, params = build_where_from_metadata(metadata, promoted_cols={"tenant", "kind"})
        assert (
            sql
            == "WHERE (tenant = %s AND kind = %s AND metadata->>%s = %s)"
        )
        assert params == ["tenant-a", "file", "source", "legacy"]

    def test_qdrant_filter_uses_promoted_columns_when_enabled(self):
        metadata = {
            "qdrant_dict_filter": {
                "must": [
                    {"key": "metadata.tenant", "match": {"value": "tenant-a"}},
                    {
                        "key": "metadata.kind",
                        "match": {"value": "sharepoint"},
                    },
                    {"key": "metadata.source", "match": {"value": "manual"}},
                ]
            }
        }
        sql, params = build_where_from_metadata(metadata, promoted_cols={"tenant", "kind"})
        assert (
            sql
            == "WHERE (tenant = %s AND kind = %s AND metadata->>%s = %s)"
        )
        assert params == ["tenant-a", "sharepoint", "source", "manual"]


# ------------------------------------------------------------------ #
#  Full real-world example round-trip
# ------------------------------------------------------------------ #


class TestFullExample:
    """End-to-end test with the exact payload from the FE."""

    FE_METADATA = {
        "key1": "value1",
        "key2": {
            "nested1": {
                "value3": ["value7"],
                "value4": ["value8"],
                "sharepoint": [],
            },
            "nested2": ["value3", "value4"],
            "nested3": 2,
            "nested4": "value3: 1, value4: 1",
        },
        "qdrant_dict_filter": {
            "must": [{"key": "metadata.key1", "match": {"value": "value1"}}],
            "should": [
                {"must": [{"key": "metadata.key3", "match": {"value": "value3"}}]},
                {
                    "must": [
                        {
                            "key": "metadata.key3",
                            "match": {"value": "value4"},
                        }
                    ]
                },
            ],
        },
    }

    def test_where_clause_generated(self):
        sql, params = build_where_from_metadata(self.FE_METADATA)
        assert (
            sql
            == "WHERE (metadata->>%s = %s) AND ((metadata->>%s = %s) OR (metadata->>%s = %s))"
        )
        assert params == [
            "key1",
            "value1",
            "key3",
            "value3",
            "key3",
            "value4",
        ]
        # FE-only keys must NOT appear
        assert "key2" not in str(sql)

    def test_params_are_all_strings(self):
        _, params = build_where_from_metadata(self.FE_METADATA)
        for p in params:
            assert isinstance(p, str)

    def test_param_count_matches_placeholders(self):
        sql, params = build_where_from_metadata(self.FE_METADATA)
        # Count %s occurrences in the WHERE clause (after "WHERE ")
        placeholder_count = sql.count("%s")
        assert placeholder_count == len(params)


# ------------------------------------------------------------------ #
#  Plain-script runner
# ------------------------------------------------------------------ #

_TEST_CLASSES = [
    TestParseQdrantKeyToJsonb,
    TestBuildPgLeafCondition,
    TestMustFilter,
    TestShouldFilter,
    TestMustNotFilter,
    TestCombinedFilter,
    TestNestedGroups,
    TestEdgeCases,
    TestBuildWhereFromMetadata,
    TestFullExample,
]


def run_tests() -> None:
    passed = 0
    failed = 0
    errors = []

    for cls in _TEST_CLASSES:
        instance = cls()
        methods = [
            name
            for name, _ in inspect.getmembers(instance, predicate=inspect.ismethod)
            if name.startswith("test_")
        ]
        for method_name in methods:
            label = f"{cls.__name__}.{method_name}"
            try:
                getattr(instance, method_name)()
                print(f"  PASS  {label}")
                passed += 1
            except Exception:
                print(f"  FAIL  {label}")
                errors.append((label, traceback.format_exc()))
                failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for label, tb in errors:
            print(f"\n--- {label} ---")
            print(tb)
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run_tests()
