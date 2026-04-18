#!/usr/bin/env python3
"""Purge audit entries older than settings.audit.retention_days. Intended for daily cron."""
from __future__ import annotations

import os
from pathlib import Path

from mcp_exec.audit import AuditLog
from mcp_exec.settings import load_settings


def main() -> None:
    settings = load_settings(Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml")))
    log = AuditLog(db_path=Path(settings.audit.db_path))
    deleted = log.purge_older_than_days(settings.audit.retention_days)
    print(f"deleted {deleted} audit rows older than {settings.audit.retention_days}d")


if __name__ == "__main__":
    main()
