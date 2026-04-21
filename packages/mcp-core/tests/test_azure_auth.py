from unittest.mock import MagicMock, patch

import pytest

from mcp_core.azure_auth import AzureAuthError, AzureAuth


def _cfg() -> dict:
    return {"tenant_id": "t", "client_id": "c", "client_secret": "s", "redirect_uri": "http://localhost:8765"}


def test_exchange_code_extracts_email() -> None:
    fake_msal = MagicMock()
    fake_msal.acquire_token_by_authorization_code.return_value = {
        "access_token": "aad_tok",
        "id_token_claims": {"preferred_username": "e@x.com", "upn": "e@x.com"},
        "expires_in": 3600,
    }
    with patch("mcp_core.azure_auth.msal.ConfidentialClientApplication", return_value=fake_msal):
        az = AzureAuth(**_cfg())
        out = az.exchange_code(code="abc")
        assert out.email == "e@x.com"
        assert out.aad_access_token == "aad_tok"


def test_exchange_code_no_email_raises() -> None:
    fake = MagicMock()
    fake.acquire_token_by_authorization_code.return_value = {"error": "bad"}
    with patch("mcp_core.azure_auth.msal.ConfidentialClientApplication", return_value=fake):
        az = AzureAuth(**_cfg())
        with pytest.raises(AzureAuthError):
            az.exchange_code(code="abc")
