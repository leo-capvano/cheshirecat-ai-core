"""Translate a supported subset of Qdrant filters to parameterised PostgreSQL.

The front-end may send a metadata dict containing a ``qdrant_dict_filter`` key
whose value follows Qdrant's filter structure. This module converts that
structure into a ``(sql_fragment, params_list)`` tuple ready for psycopg2's
``%s`` parameter style.

Currently supported Qdrant clauses/operators
--------------------------------------------
- Boolean groups: ``must``, ``should``, ``must_not``
- Match conditions:
    - ``match.value``
    - ``match.any``
    - ``match.except``
    - ``match.text`` (implemented as PostgreSQL ``ILIKE`` substring matching,
        not Qdrant full-text search)
- ``range``
    - numeric range
    - datetime-like range
- Presence / null-style checks:
    - ``is_empty``
    - ``is_null``

Behaviour notes
---------------
- Metadata fields are normally read from the JSONB ``metadata`` column.
- If some top-level metadata keys are promoted to dedicated PostgreSQL columns,
    this translator uses direct column comparisons for those keys.
- ``match.any`` / ``match.except`` / ``match.text`` handle both scalar JSON
    values and JSON arrays.
- JSONB numeric/datetime ranges are guarded so invalid values become
    non-matching instead of raising cast errors.
- For promoted columns, ``is_empty`` and ``is_null`` both map to ``IS NULL``;
    promoted-column storage cannot distinguish a missing key from an explicit
    null value.

Not currently supported
-----------------------
- Nested-object filters via ``nested``
- ``match.text_any``
- ``match.phrase``
- Geo filters (``geo_bounding_box``, ``geo_radius``, ``geo_polygon``)
- ``values_count``
- ``has_id``
- ``has_vector``
- Other Qdrant condition types not listed above

Unsupported or malformed conditions raise ``ValueError`` instead of silently
falling back to a no-op SQL predicate.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Set, Tuple


NUMERIC_REGEX = r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?$"
TIMESTAMP_REGEX = (
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?$"
)


def _normalize_promoted_cols(promoted_cols: Optional[Iterable[str]]) -> Set[str]:
    if not promoted_cols:
        return set()
    return {str(c).strip() for c in promoted_cols if str(c).strip()}


def _normalize_qdrant_key(key: str) -> List[str]:
    if not key or not str(key).strip():
        raise ValueError("Qdrant filter key cannot be empty")

    normalized = str(key).strip()
    if normalized.startswith("metadata."):
        normalized = normalized[len("metadata.") :]

    parts = [part for part in normalized.split(".") if part]
    if not parts:
        raise ValueError(f"Invalid Qdrant filter key: {key!r}")

    return parts


def _parse_qdrant_key(
    key: str,
    promoted_cols: Optional[Iterable[str]] = None,
    *,
    as_jsonb: bool,
) -> Tuple[str, List[str], bool]:
    promoted = _normalize_promoted_cols(promoted_cols)
    parts = _normalize_qdrant_key(key)

    if promoted and len(parts) == 1 and parts[0] in promoted:
        return parts[0], [], True

    if len(parts) == 1:
        operator = "->" if as_jsonb else "->>"
        return f"metadata{operator}%s", [parts[0]], False

    path = "{" + ",".join(parts) + "}"
    operator = "#>" if as_jsonb else "#>>"
    return f"metadata {operator} %s", [path], False


def _normalize_match_values(values: Any) -> List[str]:
    if not isinstance(values, list) or not values:
        raise ValueError("Qdrant match.any/match.except requires a non-empty list")
    return [str(value) for value in values]


def _detect_range_kind(range_config: dict) -> str:
    bounds = [value for value in range_config.values() if value is not None]
    if not bounds:
        raise ValueError("Qdrant range filter requires at least one bound")

    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in bounds):
        return "numeric"

    if all(isinstance(value, str) for value in bounds):
        if any(any(ch in value for ch in ("-", ":", "T", "Z", " ")) for value in bounds):
            return "datetime"
        return "numeric"

    raise ValueError("Qdrant range bounds must be all numeric or all datetime-like strings")


def _build_safe_range_comparison(
    expr_sql: str,
    expr_params: List[str],
    *,
    promoted: bool,
    regex: str,
    cast_type: str,
    operator: str,
    bound: Any,
    cast_bound: bool = False,
) -> Tuple[str, List[Any]]:
    text_expr = f"({expr_sql})::text" if promoted else f"({expr_sql})"
    cast_expr = f"({expr_sql})::{cast_type}"
    bound_sql = f"%s::{cast_type}" if cast_bound else "%s"
    sql = (
        f"(CASE WHEN {text_expr} ~ %s "
        f"THEN {cast_expr} {operator} {bound_sql} "
        f"ELSE FALSE END)"
    )

    if promoted:
        return sql, [regex, bound]

    return sql, expr_params + [regex] + expr_params + [bound]


def _build_pg_match_value_condition(
    key: str,
    value: Any,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    sql_key, key_params = parse_qdrant_key_to_jsonb(
        key,
        promoted_cols=promoted_cols,
    )
    return f"{sql_key} = %s", key_params + [str(value)]


def _build_pg_match_any_condition(
    key: str,
    values: Any,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    normalized_values = _normalize_match_values(values)
    text_sql, text_params, promoted = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=False,
    )

    if promoted:
        return f"{text_sql} = ANY(%s)", [normalized_values]

    json_sql, json_params, _ = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=True,
    )
    sql = (
        "("
        f"(jsonb_typeof({json_sql}) = 'array' AND EXISTS ("
        f"SELECT 1 FROM jsonb_array_elements_text({json_sql}) AS elem(value) "
        f"WHERE elem.value = ANY(%s)"
        "))"
        " OR "
        f"(jsonb_typeof({json_sql}) <> 'array' AND {text_sql} = ANY(%s))"
        ")"
    )
    params = json_params + json_params + [normalized_values] + json_params + text_params + [normalized_values]
    return sql, params


def _build_pg_match_except_condition(
    key: str,
    values: Any,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    normalized_values = _normalize_match_values(values)
    text_sql, text_params, promoted = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=False,
    )

    if promoted:
        return f"({text_sql} IS NOT NULL AND NOT ({text_sql} = ANY(%s)))", [normalized_values]

    json_sql, json_params, _ = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=True,
    )
    sql = (
        "("
        f"(jsonb_typeof({json_sql}) = 'array' AND EXISTS ("
        f"SELECT 1 FROM jsonb_array_elements_text({json_sql}) AS elem(value) "
        f"WHERE NOT (elem.value = ANY(%s))"
        "))"
        " OR "
        f"(jsonb_typeof({json_sql}) <> 'array' AND {text_sql} IS NOT NULL AND NOT ({text_sql} = ANY(%s)))"
        ")"
    )
    params = (
        json_params
        + json_params
        + [normalized_values]
        + json_params
        + text_params
        + text_params
        + [normalized_values]
    )
    return sql, params


def _build_pg_match_text_condition(
    key: str,
    text: Any,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    pattern = f"%{str(text)}%"
    text_sql, text_params, promoted = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=False,
    )

    if promoted:
        return f"{text_sql} ILIKE %s", [pattern]

    json_sql, json_params, _ = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=True,
    )
    sql = (
        "("
        f"(jsonb_typeof({json_sql}) = 'array' AND EXISTS ("
        f"SELECT 1 FROM jsonb_array_elements_text({json_sql}) AS elem(value) "
        f"WHERE elem.value ILIKE %s"
        "))"
        " OR "
        f"(jsonb_typeof({json_sql}) <> 'array' AND {text_sql} ILIKE %s)"
        ")"
    )
    params = json_params + json_params + [pattern] + json_params + text_params + [pattern]
    return sql, params


def _build_pg_range_condition(
    condition: dict,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    key = condition["key"]
    range_config = condition["range"]
    kind = _detect_range_kind(range_config)
    expr_sql, expr_params, promoted = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=False,
    )

    comparisons: List[str] = []
    params: List[Any] = []
    for field_name, operator in (("gt", ">"), ("gte", ">="), ("lt", "<"), ("lte", "<=")):
        bound = range_config.get(field_name)
        if bound is None:
            continue

        if kind == "numeric":
            sql, clause_params = _build_safe_range_comparison(
                expr_sql,
                expr_params,
                promoted=promoted,
                regex=NUMERIC_REGEX,
                cast_type="double precision",
                operator=operator,
                bound=float(bound),
            )
        else:
            sql, clause_params = _build_safe_range_comparison(
                expr_sql,
                expr_params,
                promoted=promoted,
                regex=TIMESTAMP_REGEX,
                cast_type="timestamptz",
                operator=operator,
                bound=str(bound),
                cast_bound=True,
            )

        comparisons.append(sql)
        params.extend(clause_params)

    if not comparisons:
        raise ValueError("Qdrant range filter requires at least one non-null bound")

    return "(" + " AND ".join(comparisons) + ")", params


def _build_pg_is_empty_condition(
    key: str,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    json_sql, json_params, promoted = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=True,
    )

    if promoted:
        return f"{json_sql} IS NULL", []

    sql = (
        "("
        f"{json_sql} IS NULL "
        "OR "
        f"jsonb_typeof({json_sql}) = 'null' "
        "OR "
        f"{json_sql} = '[]'::jsonb"
        ")"
    )
    return sql, json_params + json_params + json_params


def _build_pg_is_null_condition(
    key: str,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    json_sql, json_params, promoted = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=True,
    )

    if promoted:
        return f"{json_sql} IS NULL", []

    return f"jsonb_typeof({json_sql}) = 'null'", json_params


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
    sql, params, _ = _parse_qdrant_key(
        key,
        promoted_cols=promoted_cols,
        as_jsonb=False,
    )
    return sql, params


def build_pg_leaf_condition(
    condition: dict,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    """Translate a single Qdrant leaf condition to ``(sql, params)``.

    Leaf format::

        {"key": "metadata.tenant", "match": {"value": "acme"}}
    """
    if "key" in condition and "match" in condition:
        key = condition["key"]
        match_config = condition["match"]
        if "value" in match_config:
            return _build_pg_match_value_condition(
                key,
                match_config["value"],
                promoted_cols=promoted_cols,
            )
        if "any" in match_config:
            return _build_pg_match_any_condition(
                key,
                match_config["any"],
                promoted_cols=promoted_cols,
            )
        if "except" in match_config:
            return _build_pg_match_except_condition(
                key,
                match_config["except"],
                promoted_cols=promoted_cols,
            )
        if "text" in match_config:
            return _build_pg_match_text_condition(
                key,
                match_config["text"],
                promoted_cols=promoted_cols,
            )

        raise ValueError(f"Unsupported Qdrant match condition: {condition}")

    if "key" in condition and "range" in condition:
        return _build_pg_range_condition(
            condition,
            promoted_cols=promoted_cols,
        )

    if "is_empty" in condition:
        payload_field = condition["is_empty"]
        return _build_pg_is_empty_condition(
            payload_field["key"],
            promoted_cols=promoted_cols,
        )

    if "is_null" in condition:
        payload_field = condition["is_null"]
        return _build_pg_is_null_condition(
            payload_field["key"],
            promoted_cols=promoted_cols,
        )

    raise ValueError(f"Unsupported Qdrant leaf condition: {condition}")


def build_pg_condition(
    condition: dict,
    promoted_cols: Optional[Iterable[str]] = None,
) -> Tuple[str, List[Any]]:
    """Dispatch: leaf condition or nested filter group."""
    if any(key in condition for key in ("match", "range", "is_empty", "is_null")):
        return build_pg_leaf_condition(
            condition,
            promoted_cols=promoted_cols,
        )

    # Nested group (has must / should / must_not)
    if any(key in condition for key in ("must", "should", "must_not")):
        return build_pg_filter_clause(
            condition,
            promoted_cols=promoted_cols,
        )

    raise ValueError(f"Unsupported Qdrant condition: {condition}")


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
