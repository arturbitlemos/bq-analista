-- packages/mcp-core/migrations/0001_create_analyses_audit.sql
BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- IMMUTABLE wrapper around array_to_string for use in GENERATED columns.
-- Core array_to_string is STABLE (overly cautious — text[] -> text serialization
-- is deterministic in practice); GENERATED ALWAYS AS ... STORED requires IMMUTABLE.
-- Created OUTSIDE the DO block so re-runs are safe (CREATE OR REPLACE).
CREATE OR REPLACE FUNCTION immutable_array_to_string(text[], text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $fn$
    SELECT array_to_string($1, $2)
$fn$;

-- Skip the rest if this migration was already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE name = '0001_create_analyses_audit') THEN
        RAISE NOTICE 'migration 0001 already applied, skipping';
        RETURN;
    END IF;

    CREATE TABLE IF NOT EXISTS analyses (
        id              TEXT PRIMARY KEY,
        agent_slug      TEXT NOT NULL,
        author_email    TEXT NOT NULL,
        title           TEXT NOT NULL,
        brand           TEXT,
        period_label    TEXT,
        period_start    DATE,
        period_end      DATE,
        description     TEXT,
        tags            TEXT[]      NOT NULL DEFAULT '{}',
        public          BOOLEAN     NOT NULL DEFAULT FALSE,
        shared_with     TEXT[]      NOT NULL DEFAULT '{}',
        archived_by     TEXT[]      NOT NULL DEFAULT '{}',
        blob_pathname   TEXT        NOT NULL,
        blob_url        TEXT,
        refresh_spec    JSONB,
        last_refreshed_at  TIMESTAMPTZ,
        last_refreshed_by  TEXT,
        last_refresh_error TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        search_doc      tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('portuguese'::regconfig,coalesce(title, '')), 'A') ||
            setweight(to_tsvector('portuguese'::regconfig,coalesce(description, '')), 'B') ||
            setweight(to_tsvector('portuguese'::regconfig, immutable_array_to_string(tags, ' ')), 'B') ||
            setweight(to_tsvector('portuguese'::regconfig,coalesce(brand, '')), 'C')
        ) STORED
    );

    CREATE INDEX IF NOT EXISTS analyses_agent_author_idx ON analyses(agent_slug, author_email);
    CREATE INDEX IF NOT EXISTS analyses_agent_public_idx ON analyses(agent_slug) WHERE public = TRUE;
    CREATE INDEX IF NOT EXISTS analyses_shared_with_gin  ON analyses USING GIN(shared_with);
    CREATE INDEX IF NOT EXISTS analyses_archived_by_gin  ON analyses USING GIN(archived_by);
    CREATE INDEX IF NOT EXISTS analyses_period_idx       ON analyses(agent_slug, period_end DESC);
    CREATE INDEX IF NOT EXISTS analyses_search_idx       ON analyses USING GIN(search_doc);

    CREATE TABLE IF NOT EXISTS audit_log (
        id            BIGSERIAL PRIMARY KEY,
        occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        actor_email   TEXT NOT NULL,
        action        TEXT NOT NULL,
        analysis_id   TEXT REFERENCES analyses(id) ON DELETE SET NULL,
        metadata      JSONB
    );

    CREATE INDEX IF NOT EXISTS audit_actor_time_idx ON audit_log(actor_email, occurred_at DESC);
    CREATE INDEX IF NOT EXISTS audit_analysis_idx   ON audit_log(analysis_id, occurred_at DESC);

    INSERT INTO schema_migrations (name) VALUES ('0001_create_analyses_audit');
END $$;

COMMIT;
