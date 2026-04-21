from __future__ import annotations

import re
from pathlib import Path

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")  # min 1 char, lowercase, hyphens ok


class PathSandboxError(ValueError):
    pass


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.fullmatch(email):
        raise PathSandboxError(f"invalid exec_email: {email!r}")


def _validate_domain(domain: str) -> None:
    if not _DOMAIN_RE.fullmatch(domain):
        raise PathSandboxError(f"invalid domain: {domain!r}")


def _ensure_inside(base: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError as e:
        raise PathSandboxError(f"path escapes sandbox: {target}") from e


def exec_analysis_path(repo_root: Path, domain: str, exec_email: str, filename: str) -> Path:
    _validate_domain(domain)
    _validate_email(exec_email)
    if not filename.endswith(".html") or len(filename) <= len(".html"):
        raise PathSandboxError("only non-empty .html files allowed in analyses/")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise PathSandboxError(f"invalid filename: {filename!r}")
    base = repo_root / "analyses" / domain / exec_email
    target = base / filename
    _ensure_inside(base, target)
    return target


def exec_library_path(repo_root: Path, domain: str, exec_email: str) -> Path:
    _validate_domain(domain)
    _validate_email(exec_email)
    base = repo_root / "library" / domain
    target = base / f"{exec_email}.json"
    _ensure_inside(base, target)
    return target


def public_library_path(repo_root: Path, domain: str) -> Path:
    _validate_domain(domain)
    base = repo_root / "library" / domain
    target = base / "public.json"
    _ensure_inside(base, target)
    return target
