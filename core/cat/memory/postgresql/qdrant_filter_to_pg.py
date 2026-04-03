"""Translate Qdrant-compatible filter dicts to parameterised PostgreSQL
WHERE clauses.

The front-end sends a metadata dict that may contain a ``qdrant_dict_filter``
key whose value follows the Qdrant filter syntax (``must`` / ``should`` /
``must_not``).  The functions in this module convert that structure into a
``(sql_fragment, params_list)`` tuple ready for ``psycopg2``'s ``%s``
parameter style.

For PostgreSQL collections that promote some metadata fields to dedicated
columns (e.g. partition routing columns), those keys can be translated to
column comparisons instead of JSONB metadata extraction.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Set, Tuple


def _normalize_promoted_cols(promoted_cols: Optional[Iterable[str]]) -> Set[str]:
    if not promoted_cols:
        return set()
    return {str(c).strip() for c in promoted_cols if str(c).strip()}


def parse_qdrant_key_to_jsonb(
    key: str,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[str]]:
    """Convert a Qdrant-style dotted key to a SQL accessor.

    ``metadata.tenant``  → ``tenant``,          ``[]``
    ``metadata.a.b``     → ``metadata #>> %s``, ``['{a,b}']``
    ``tenant``           → ``tenant``,          ``[]``

    If ``promoted_cols`` is provided and the key is a promoted top-level field,
    it is translated to a direct column accessor.

    """
    promoted = _normalize_promoted_cols(promoted_cols)

    if key.startswith("metadata."):
        key = key[len("metadata.") :]

    parts = key.split(".")
    if promoted and len(parts) == 1 and parts[0] in promoted:
        return parts[0], []

    if len(parts) == 1:
        return "metadata->>%s", [parts[0]]

    path = "{" + ",".join(parts) + "}"
    return "metadata #>> %s", [path]


def build_pg_leaf_condition(
    condition: dict,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    """Translate a single Qdrant leaf condition to ``(sql, params)``.

    Leaf format::

        {"key": "metadata.tenant", "match": {"value": "acme"}}
    """
    key = condition["key"]
    value = condition["match"]["value"]
    sql_key, key_params = parse_qdrant_key_to_jsonb(
        key,
        promoted_cols=promoted_cols,
    )
    return f"{sql_key} = %s", key_params + [str(value)]


def build_pg_condition(
    condition: dict,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    """Dispatch: leaf condition or nested filter group."""
    if "key" in condition and "match" in condition:
        return build_pg_leaf_condition(
            condition,
            promoted_cols=promoted_cols,
        )

    # Nested group (has must / should / must_not)
    return build_pg_filter_clause(
        condition,
        promoted_cols=promoted_cols,
    )


def build_pg_filter_clause(
    qdrant_filter: dict,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    """Recursively convert a Qdrant filter dict to ``(sql, params)``.

    Supports ``must`` (AND), ``should`` (OR), ``must_not`` (NOT).
    """
    clauses: List[str] = []
    params: List[Any] = []

    # must → AND
    if "must" in qdrant_filter:
        parts = []
        for cond in qdrant_filter["must"]:
            sql, p = build_pg_condition(
                cond,
                promoted_cols=promoted_cols,
            )
            parts.append(sql)
            params.extend(p)
        if parts:
            clauses.append("(" + " AND ".join(parts) + ")")

    # should → OR
    if "should" in qdrant_filter:
        parts = []
        for cond in qdrant_filter["should"]:
            sql, p = build_pg_condition(
                cond,
                promoted_cols=promoted_cols,
            )
            parts.append(sql)
            params.extend(p)
        if parts:
            clauses.append("(" + " OR ".join(parts) + ")")

    # must_not → NOT
    if "must_not" in qdrant_filter:
        parts = []
        for cond in qdrant_filter["must_not"]:
            sql, p = build_pg_condition(
                cond,
                promoted_cols=promoted_cols,
            )
            parts.append(f"NOT ({sql})")
            params.extend(p)
        if parts:
            clauses.append("(" + " AND ".join(parts) + ")")

    if not clauses:
        return "TRUE", []

    return " AND ".join(clauses), params


def build_where_from_metadata(
    metadata: dict | None,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
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
            },
            promoted_cols=promoted_cols,
        )
    else:
        sql, params = build_pg_filter_clause(
            qdrant_filter,
            promoted_cols=promoted_cols,
        )

    if not sql or sql == "TRUE":
        return "", []

    return f"WHERE {sql}", params
