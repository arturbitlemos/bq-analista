from pathlib import Path

import pytest

from mcp_exec.settings import Settings, load_settings


def test_loads_example_settings(tmp_path: Path) -> None:
    toml = tmp_path / "settings.toml"
    toml.write_text(
        '[server]\nhost="0.0.0.0"\nport=3000\n'
        '[bigquery]\nproject_id="p"\nmax_bytes_billed=5000000000\n'
        'query_timeout_s=60\nmax_rows=100000\nallowed_datasets=["d"]\n'
        '[github]\nrepo_path="/r"\nbranch="main"\n'
        'author_name="bot"\nauthor_email="bot@x.com"\n'
        '[auth]\njwt_issuer="iss"\naccess_token_ttl_s=1800\nrefresh_token_ttl_s=2592000\n'
        '[audit]\ndb_path="/var/x.db"\nretention_days=90\n'
    )
    s = load_settings(toml)
    assert isinstance(s, Settings)
    assert s.server.port == 3000
    assert s.bigquery.max_bytes_billed == 5_000_000_000
    assert s.audit.retention_days == 90


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.toml")
