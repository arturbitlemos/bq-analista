import json
import os
from pathlib import Path

from mcp_exec.cli_login import save_credentials


def test_save_credentials_writes_600_file(tmp_path: Path) -> None:
    out = tmp_path / "creds.json"
    save_credentials(path=out, payload={"access_token": "a", "refresh_token": "r", "expires_at": 123, "email": "e@x.com"})
    data = json.loads(out.read_text())
    assert data["access_token"] == "a"
    mode = oct(out.stat().st_mode & 0o777)
    assert mode == "0o600"
