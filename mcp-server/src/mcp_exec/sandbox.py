from __future__ import annotations

import re
from pathlib import Path

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class PathSandboxError(ValueError):
    pass


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.fullmatch(email):
        raise PathSandboxError(f"invalid exec_email: {email!r}")


def _ensure_inside(base: Path, target: Path) -> None:
    base_abs = base.resolve()
    target_abs = target.resolve()
    try:
        target_abs.relative_to(base_abs)
    except ValueError as e:
        raise PathSandboxError(f"path escapes sandbox: {target}") from e


def exec_analysis_path(repo_root: Path, exec_email: str, filename: str) -> Path:
    _validate_email(exec_email)
    if not filename.endswith(".html"):
        raise PathSandboxError("only .html files allowed in analyses/")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise PathSandboxError(f"invalid filename: {filename!r}")
    base = repo_root / "analyses" / exec_email
    target = base / filename
    _ensure_inside(base, target)
    return target


def exec_library_path(repo_root: Path, exec_email: str) -> Path:
    _validate_email(exec_email)
    base = repo_root / "library"
    target = base / f"{exec_email}.json"
    _ensure_inside(base, target)
    return target
