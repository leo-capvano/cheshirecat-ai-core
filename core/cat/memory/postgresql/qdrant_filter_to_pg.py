"""Translate Qdrant-compatible filter dicts to parameterised PostgreSQL
JSONB WHERE clauses.

The front-end sends a metadata dict that may contain a ``qdrant_dict_filter``
key whose value follows the Qdrant filter syntax (``must`` / ``should`` /
``must_not``).  The functions in this module convert that structure into a
``(sql_fragment, params_list)`` tuple ready for ``psycopg2``'s ``%s``
parameter style.
"""

from __future__ import annotations

from typing import Any, List, Tuple


def parse_qdrant_key_to_jsonb(key: str) -> Tuple[str, List[str]]:
    """Convert a Qdrant-style dotted key to a parameterised JSONB accessor.

    ``metadata.domain``  → ``metadata->>%s``,  ``['domain']``
    ``metadata.a.b``     → ``metadata #>> %s``, ``['{a,b}']``
    ``domain``           → ``metadata->>%s``,   ``['domain']``   (no prefix)
    """
    if key.startswith("metadata."):
        key = key[len("metadata.") :]

    parts = key.split(".")
    if len(parts) == 1:
        return "metadata->>%s", [parts[0]]
    path = "{" + ",".join(parts) + "}"
    return "metadata #>> %s", [path]


def build_pg_leaf_condition(condition: dict) -> Tuple[str, List[Any]]:
    """Translate a single Qdrant leaf condition to ``(sql, params)``.

    Leaf format::

        {"key": "metadata.domain", "match": {"value": "maestro"}}
    """
    key = condition["key"]
    value = condition["match"]["value"]
    sql_key, key_params = parse_qdrant_key_to_jsonb(key)
    return f"{sql_key} = %s", key_params + [str(value)]


def build_pg_condition(condition: dict) -> Tuple[str, List[Any]]:
    """Dispatch: leaf condition or nested filter group."""
    if "key" in condition and "match" in condition:
        return build_pg_leaf_condition(condition)
    # Nested group (has must / should / must_not)
    return build_pg_filter_clause(condition)


def build_pg_filter_clause(qdrant_filter: dict) -> Tuple[str, List[Any]]:
    """Recursively convert a Qdrant filter dict to ``(sql, params)``.

    Supports ``must`` (AND), ``should`` (OR), ``must_not`` (NOT).
    """
    clauses: List[str] = []
    params: List[Any] = []

    # must → AND
    if "must" in qdrant_filter:
        parts = []
        for cond in qdrant_filter["must"]:
            sql, p = build_pg_condition(cond)
            parts.append(sql)
            params.extend(p)
        if parts:
            clauses.append("(" + " AND ".join(parts) + ")")

    # should → OR
    if "should" in qdrant_filter:
        parts = []
        for cond in qdrant_filter["should"]:
            sql, p = build_pg_condition(cond)
            parts.append(sql)
            params.extend(p)
        if parts:
            clauses.append("(" + " OR ".join(parts) + ")")

    # must_not → NOT
    if "must_not" in qdrant_filter:
        parts = []
        for cond in qdrant_filter["must_not"]:
            sql, p = build_pg_condition(cond)
            parts.append(f"NOT ({sql})")
            params.extend(p)
        if parts:
            clauses.append("(" + " AND ".join(parts) + ")")

    if not clauses:
        return "TRUE", []

    return " AND ".join(clauses), params


def build_where_from_metadata(metadata: dict | None) -> Tuple[str, List[Any]]:
    """Build ``(where_clause, params)`` from the metadata dict.

    Only the ``qdrant_dict_filter`` key is used for structured filtering.
    If absent, all top-level key/value pairs are treated as simple equality
    conditions (legacy behaviour).
    """
    if not metadata:
        return "", []

    qdrant_filter = metadata.get("qdrant_dict_filter")
    if not qdrant_filter:
        # Legacy: treat flat key/value pairs as must-match conditions
        sql, params = build_pg_filter_clause(
            {
                "must": [
                    {"key": key, "match": {"value": val}}
                    for key, val in metadata.items()
                ]
            }
        )
    else:
        sql, params = build_pg_filter_clause(qdrant_filter)

    if not sql or sql == "TRUE":
        return "", []

    return f"WHERE {sql}", params
