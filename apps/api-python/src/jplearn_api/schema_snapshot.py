"""Structural snapshot of the live PostgreSQL schema.

ADR-004 moves DDL ownership from Prisma to Alembic. The migration is only
trustworthy if the database it builds is structurally identical to the one
Prisma built, so both sides are reduced to the same normalized dict and
compared (see tests/test_schema_ddl.py and docs/qa/adr-004-schema-baseline.json).

Deliberately ignores anything that is not part of the contract: OIDs, the
Alembic/Prisma bookkeeping tables, row data, and physical ordering.
"""

from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

BOOKKEEPING_TABLES = frozenset({"_prisma_migrations", "alembic_version"})

ENUMS_SQL = """
SELECT t.typname AS name,
       array_agg(e.enumlabel ORDER BY e.enumsortorder) AS labels
FROM pg_type t
JOIN pg_enum e ON e.enumtypid = t.oid
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname = 'public'
GROUP BY t.typname
"""

COLUMNS_SQL = """
SELECT table_name, column_name, data_type, udt_name, is_nullable,
       column_default, character_maximum_length, numeric_precision,
       numeric_scale, datetime_precision
FROM information_schema.columns
WHERE table_schema = 'public'
"""

CONSTRAINTS_SQL = """
SELECT c.conname AS name,
       c.contype::text AS type,
       rel.relname AS table_name,
       pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class rel ON rel.oid = c.conrelid
JOIN pg_namespace n ON n.oid = rel.relnamespace
WHERE n.nspname = 'public'
"""

INDEXES_SQL = """
SELECT tablename AS table_name, indexname AS name, indexdef AS definition
FROM pg_indexes
WHERE schemaname = 'public'
"""


async def snapshot(conn: asyncpg.Connection) -> dict:
    enums = {
        row["name"]: list(row["labels"])
        for row in await conn.fetch(ENUMS_SQL)
    }

    columns: dict[str, dict[str, dict]] = {}
    for row in await conn.fetch(COLUMNS_SQL):
        if row["table_name"] in BOOKKEEPING_TABLES:
            continue
        columns.setdefault(row["table_name"], {})[row["column_name"]] = {
            "data_type": row["data_type"],
            "udt_name": row["udt_name"],
            "is_nullable": row["is_nullable"],
            "default": row["column_default"],
            "character_maximum_length": row["character_maximum_length"],
            "numeric_precision": row["numeric_precision"],
            "numeric_scale": row["numeric_scale"],
            "datetime_precision": row["datetime_precision"],
        }

    constraints: dict[str, dict] = {}
    for row in await conn.fetch(CONSTRAINTS_SQL):
        if row["table_name"] in BOOKKEEPING_TABLES:
            continue
        constraints[row["name"]] = {
            "table": row["table_name"],
            "type": row["type"],
            "definition": row["definition"],
        }

    indexes: dict[str, dict] = {}
    for row in await conn.fetch(INDEXES_SQL):
        if row["table_name"] in BOOKKEEPING_TABLES:
            continue
        indexes[row["name"]] = {
            "table": row["table_name"],
            "definition": row["definition"],
        }

    return {
        "enums": dict(sorted(enums.items())),
        "tables": {
            table: dict(sorted(cols.items()))
            for table, cols in sorted(columns.items())
        },
        "constraints": dict(sorted(constraints.items())),
        "indexes": dict(sorted(indexes.items())),
    }


async def snapshot_url(database_url: str) -> dict:
    conn = await asyncpg.connect(database_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        return await snapshot(conn)
    finally:
        await conn.close()


def diff(expected: dict, actual: dict) -> list[str]:
    """Human-readable structural differences, empty when identical."""
    problems: list[str] = []
    for section in ("enums", "tables", "constraints", "indexes"):
        left, right = expected[section], actual[section]
        for key in sorted(set(left) - set(right)):
            problems.append(f"{section}: missing {key!r}")
        for key in sorted(set(right) - set(left)):
            problems.append(f"{section}: unexpected {key!r}")
        for key in sorted(set(left) & set(right)):
            if left[key] != right[key]:
                problems.append(
                    f"{section}.{key}: expected {json.dumps(left[key], sort_keys=True)} "
                    f"got {json.dumps(right[key], sort_keys=True)}",
                )
    return problems


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m jplearn_api.schema_snapshot <database-url> [out.json]", file=sys.stderr)
        return 2
    result = asyncio.run(snapshot_url(sys.argv[1]))
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
