from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
import asyncpg


@dataclass
class AnalysisRow:
    id: str
    agent_slug: str
    author_email: str
    title: str
    brand: str | None = None
    period_label: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    public: bool = False
    shared_with: list[str] = field(default_factory=list)
    archived_by: list[str] = field(default_factory=list)
    blob_pathname: str = ""
    blob_url: str | None = None
    refresh_spec: dict[str, Any] | None = None
    last_refreshed_at: datetime | None = None
    last_refreshed_by: str | None = None
    last_refresh_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_record(cls, r: asyncpg.Record) -> "AnalysisRow":
        d = dict(r)
        d.pop("search_doc", None)
        d.pop("rank", None)  # search() adds this column
        if d.get("refresh_spec") is not None and isinstance(d["refresh_spec"], str):
            d["refresh_spec"] = json.loads(d["refresh_spec"])
        return cls(**d)


_COLS = (
    "id, agent_slug, author_email, title, brand, period_label, period_start, period_end, "
    "description, tags, public, shared_with, archived_by, blob_pathname, blob_url, refresh_spec, "
    "last_refreshed_at, last_refreshed_by, last_refresh_error, created_at, updated_at"
)


async def insert(conn: asyncpg.Connection, row: AnalysisRow) -> None:
    await conn.execute(
        f"""INSERT INTO analyses ({_COLS}) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,
            COALESCE($20, NOW()), COALESCE($21, NOW())
        )""",
        row.id, row.agent_slug, row.author_email, row.title, row.brand, row.period_label,
        row.period_start, row.period_end, row.description, row.tags, row.public,
        row.shared_with, row.archived_by, row.blob_pathname, row.blob_url,
        json.dumps(row.refresh_spec) if row.refresh_spec else None,
        row.last_refreshed_at, row.last_refreshed_by, row.last_refresh_error,
        row.created_at, row.updated_at,
    )


async def update_blob_url(conn: asyncpg.Connection, analysis_id: str, *, blob_url: str) -> None:
    """Updates blob_url after upload (publish or refresh). Idempotent."""
    await conn.execute(
        "UPDATE analyses SET blob_url = $1, updated_at = NOW() WHERE id = $2",
        blob_url, analysis_id,
    )


async def get(conn: asyncpg.Connection, analysis_id: str) -> AnalysisRow | None:
    rec = await conn.fetchrow(f"SELECT {_COLS} FROM analyses WHERE id = $1", analysis_id)
    return AnalysisRow.from_record(rec) if rec else None


async def list_for_user(conn: asyncpg.Connection, *, agent_slug: str, email: str) -> list[AnalysisRow]:
    rows = await conn.fetch(
        f"""SELECT {_COLS} FROM analyses
            WHERE agent_slug = $1 AND (author_email = $2 OR public = TRUE OR $2 = ANY(shared_with))
            ORDER BY COALESCE(last_refreshed_at, created_at) DESC""",
        agent_slug, email,
    )
    return [AnalysisRow.from_record(r) for r in rows]


async def update_acl(conn: asyncpg.Connection, analysis_id: str, *, public: bool, shared_with: list[str]) -> None:
    await conn.execute(
        "UPDATE analyses SET public = $1, shared_with = $2, updated_at = NOW() WHERE id = $3",
        public, shared_with, analysis_id,
    )


async def update_archive(conn: asyncpg.Connection, analysis_id: str, *, email: str, archive: bool) -> None:
    if archive:
        # remove first to avoid duplicates, then append (idempotent set semantics)
        await conn.execute(
            "UPDATE analyses SET archived_by = array_append(array_remove(archived_by, $1), $1), updated_at = NOW() WHERE id = $2",
            email, analysis_id,
        )
    else:
        await conn.execute(
            "UPDATE analyses SET archived_by = array_remove(archived_by, $1), updated_at = NOW() WHERE id = $2",
            email, analysis_id,
        )


async def update_refresh_state(
    conn: asyncpg.Connection, analysis_id: str, *,
    period_start: date, period_end: date, actor_email: str,
) -> None:
    await conn.execute(
        """UPDATE analyses SET
            period_start = $1, period_end = $2,
            last_refreshed_at = NOW(), last_refreshed_by = $3, last_refresh_error = NULL,
            updated_at = NOW()
           WHERE id = $4""",
        period_start, period_end, actor_email, analysis_id,
    )


async def set_refresh_error(conn: asyncpg.Connection, analysis_id: str, *, error: str) -> None:
    await conn.execute(
        "UPDATE analyses SET last_refresh_error = $1, updated_at = NOW() WHERE id = $2",
        error, analysis_id,
    )


async def search(
    conn: asyncpg.Connection, *,
    query: str, email: str,
    agent: str | None = None, brand: str | None = None,
    days_back: int = 90, limit: int = 10,
) -> list[AnalysisRow]:
    sql = f"""
        SELECT {_COLS}, ts_rank(search_doc, plainto_tsquery('portuguese', $1)) AS rank
        FROM analyses
        WHERE search_doc @@ plainto_tsquery('portuguese', $1)
          AND (author_email = $2 OR public = TRUE OR $2 = ANY(shared_with))
          AND COALESCE(last_refreshed_at, created_at) >= NOW() - make_interval(days => $3)
          {{agent_clause}}
          {{brand_clause}}
        ORDER BY rank DESC, COALESCE(last_refreshed_at, created_at) DESC
        LIMIT $4
    """.format(
        agent_clause="AND agent_slug = $5" if agent else "",
        brand_clause=("AND brand = $6" if (agent and brand) else ("AND brand = $5" if brand else "")),
    )
    args: list[Any] = [query, email, days_back, max(1, min(limit, 25))]
    if agent:
        args.append(agent)
    if brand:
        args.append(brand)
    rows = await conn.fetch(sql, *args)
    return [AnalysisRow.from_record(r) for r in rows]


async def try_acquire_refresh_lock(conn: asyncpg.Connection, analysis_id: str) -> bool:
    """pg_try_advisory_xact_lock — returns True if lock acquired in this transaction.
    Lock auto-releases at COMMIT/ROLLBACK.

    Uses the two-arg int4 form (64-bit lock space) to make collisions between
    distinct analysis_ids astronomically rare. The single-arg int8 form would
    require a single hash that we don't have a stable Postgres function for;
    the two-arg form derives the second key from a different prefix so we
    effectively get two independent 32-bit hashes."""
    return await conn.fetchval(
        "SELECT pg_try_advisory_xact_lock(hashtext($1), hashtext($2))",
        f"refresh:fwd:{analysis_id}",
        f"refresh:rev:{analysis_id}",
    )
