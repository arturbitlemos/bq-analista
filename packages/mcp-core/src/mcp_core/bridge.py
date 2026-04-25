"""Stdio MCP bridge: Claude Desktop ↔ remote HTTP MCP server with SSO auth.

Claude Desktop spawns this as a local subprocess. The bridge:
  1. Reads creds from ~/.mcp/credentials.json (runs login flow if missing/expired).
  2. Opens a streamable-HTTP MCP session to MCP_SERVER_URL/mcp with Bearer auth.
  3. Proxies list_tools / call_tool / list_resources / read_resource / list_prompts / get_prompt
     back to Claude Desktop over stdio.

Entry point: `mcp-exec-bridge` (see pyproject.toml).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, cast

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from mcp_core.cli_login import _capture_code

CREDS_PATH = Path.home() / ".mcp" / "credentials.json"
DEFAULT_SERVER = "https://mcp-azzas.azzas.com.br"
CALLBACK_PORT = 8765
REFRESH_MARGIN_S = 120


def _log(msg: str) -> None:
    # stdout is MCP protocol; diagnostics go to stderr.
    print(f"[bridge] {msg}", file=sys.stderr, flush=True)


def _load_creds() -> dict[str, object] | None:
    if not CREDS_PATH.exists():
        return None
    try:
        return json.loads(CREDS_PATH.read_text())  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None


def _save_creds(payload: dict[str, object]) -> None:
    CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDS_PATH.write_text(json.dumps(payload, indent=2))
    os.chmod(CREDS_PATH, 0o600)


def _try_refresh(server_url: str, refresh_token: str) -> tuple[str, int] | None:
    try:
        r = httpx.post(
            f"{server_url}/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return str(data["access_token"]), int(data["expires_at"])
    except httpx.HTTPError as e:
        _log(f"refresh failed: {e}")
    return None


def _interactive_login(server_url: str) -> dict[str, object]:
    _log(f"opening browser for SSO login at {server_url}/auth/start ...")
    webbrowser.open(f"{server_url}/auth/start")
    code = _capture_code(port=CALLBACK_PORT, timeout_s=180)
    r = httpx.get(f"{server_url}/auth/callback", params={"code": code}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"auth/callback failed: {r.status_code} {r.text}")
    payload: dict[str, object] = r.json()
    _save_creds(payload)
    _log(f"logged in as {payload.get('email')}")
    return payload


def _ensure_access_token(server_url: str) -> str:
    creds = _load_creds()
    now = int(time.time())

    if creds and cast(int, creds.get("expires_at", 0)) - REFRESH_MARGIN_S > now:
        return cast(str, creds["access_token"])

    if creds and creds.get("refresh_token"):
        result = _try_refresh(server_url, cast(str, creds["refresh_token"]))
        if result:
            new_access, expires_at = result
            creds["access_token"] = new_access
            creds["expires_at"] = expires_at
            _save_creds(creds)
            return new_access
        _log("refresh token rejected; falling back to full SSO login")

    creds = _interactive_login(server_url)
    return cast(str, creds["access_token"])


def _build_bridge(session: ClientSession) -> Server:
    bridge = Server("bq-analista-bridge")

    @bridge.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return (await session.list_tools()).tools

    @bridge.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
        result = await session.call_tool(name, arguments or {})
        if result.isError:
            # Propagate remote error as MCP tool error
            text = "\n".join(
                c.text for c in result.content if isinstance(c, types.TextContent)
            ) or "remote tool error"
            raise RuntimeError(text)
        return list(result.content)

    @bridge.list_resources()
    async def _list_resources() -> list[types.Resource]:
        try:
            return (await session.list_resources()).resources
        except Exception as e:
            _log(f"list_resources unavailable: {e}")
            return []

    @bridge.read_resource()
    async def _read_resource(uri: types.AnyUrl) -> str | bytes:
        result = await session.read_resource(uri)
        if result.contents and hasattr(result.contents[0], "text"):
            return result.contents[0].text
        return b""

    @bridge.list_prompts()
    async def _list_prompts() -> list[types.Prompt]:
        try:
            return (await session.list_prompts()).prompts
        except Exception as e:
            _log(f"list_prompts unavailable: {e}")
            return []

    @bridge.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        return await session.get_prompt(name, arguments or {})

    return bridge


async def _run() -> None:
    server_url = os.environ.get("MCP_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    mcp_url = f"{server_url}/mcp"

    token = _ensure_access_token(server_url)
    headers = {"Authorization": f"Bearer {token}"}

    _log(f"connecting to {mcp_url}")
    async with streamable_http_client(mcp_url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            _log("remote session initialized")
            bridge = _build_bridge(session)
            async with stdio_server() as (r, w):
                await bridge.run(r, w, bridge.create_initialization_options())


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        _log(f"fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
