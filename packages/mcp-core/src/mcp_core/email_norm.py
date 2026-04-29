def normalize_email(s: str) -> str:
    """Lowercased + stripped. Raises ValueError on empty or malformed."""
    if not s or not s.strip():
        raise ValueError("empty email")
    out = s.strip().lower()
    if "@" not in out:
        raise ValueError(f"invalid email: missing @ in {out!r}")
    return out
