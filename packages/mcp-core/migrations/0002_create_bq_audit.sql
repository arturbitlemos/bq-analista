-- packages/mcp-core/migrations/0002_create_bq_audit.sql
CREATE TABLE IF NOT EXISTS bq_audit (
  id            BIGSERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  exec_email    TEXT NOT NULL,
  agent         TEXT NOT NULL,
  tool          TEXT NOT NULL,
  sql           TEXT,
  bytes_scanned BIGINT  DEFAULT 0,
  row_count     INT     DEFAULT 0,
  duration_ms   INT     DEFAULT 0,
  result        TEXT    NOT NULL,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_bq_audit_ts    ON bq_audit (ts);
CREATE INDEX IF NOT EXISTS idx_bq_audit_exec  ON bq_audit (exec_email);
CREATE INDEX IF NOT EXISTS idx_bq_audit_agent ON bq_audit (agent);
