from __future__ import annotations

from dataclasses import dataclass

import msal


class AzureAuthError(RuntimeError):
    pass


@dataclass
class AzureTokenInfo:
    email: str
    aad_access_token: str
    expires_in_s: int


@dataclass
class AzureAuth:
    tenant_id: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = ("User.Read",)

    def _app(self) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            client_id=self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

    def authorization_url(self, state: str) -> str:
        return self._app().get_authorization_request_url(
            scopes=list(self.scopes),
            state=state,
            redirect_uri=self.redirect_uri,
        )

    def exchange_code(self, code: str) -> AzureTokenInfo:
        result = self._app().acquire_token_by_authorization_code(
            code=code,
            scopes=list(self.scopes),
            redirect_uri=self.redirect_uri,
        )
        if "access_token" not in result:
            raise AzureAuthError(f"azure ad returned no access_token: {result.get('error_description', result)}")
        claims = result.get("id_token_claims", {})
        email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
        if not email:
            raise AzureAuthError("no email claim in id_token")
        return AzureTokenInfo(
            email=email,
            aad_access_token=result["access_token"],
            expires_in_s=int(result.get("expires_in", 3600)),
        )
