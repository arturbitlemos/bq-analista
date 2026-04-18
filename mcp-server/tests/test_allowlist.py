from pathlib import Path

from mcp_exec.allowlist import Allowlist


def test_email_in_list(tmp_path: Path) -> None:
    f = tmp_path / "a.json"
    f.write_text('{"allowed_emails": ["a@x.com", "B@X.COM"]}')
    al = Allowlist(path=f)
    assert al.is_allowed("a@x.com")
    assert al.is_allowed("A@X.com")  # case-insensitive
    assert al.is_allowed("b@x.com")
    assert not al.is_allowed("c@x.com")


def test_reload_picks_up_new_emails(tmp_path: Path) -> None:
    f = tmp_path / "a.json"
    f.write_text('{"allowed_emails": ["a@x.com"]}')
    al = Allowlist(path=f)
    assert not al.is_allowed("b@x.com")
    f.write_text('{"allowed_emails": ["a@x.com", "b@x.com"]}')
    al.reload()
    assert al.is_allowed("b@x.com")
