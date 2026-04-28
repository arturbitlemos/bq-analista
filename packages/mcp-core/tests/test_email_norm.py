from mcp_core.email_norm import normalize_email


def test_lowercase():
    assert normalize_email("Maria.Filo@Somagrupo.com.br") == "maria.filo@somagrupo.com.br"


def test_strip():
    assert normalize_email("  artur@somagrupo.com.br  ") == "artur@somagrupo.com.br"


def test_empty_string_raises():
    import pytest
    with pytest.raises(ValueError):
        normalize_email("")
    with pytest.raises(ValueError):
        normalize_email("   ")


def test_no_at_raises():
    import pytest
    with pytest.raises(ValueError):
        normalize_email("notanemail")
