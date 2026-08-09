"""MCP server connections.

Only reach for this module after the user has explicitly confirmed the MCP AND the
connection has been verified against the real server. An unverified MCP is a broken
agent that fails at the first tool call.

Directory is named `mcp_servers`, not `mcp`: a package called `app/mcp/` shadows the
installed `mcp` package under pytest's default import mode and produces baffling errors.
"""

from agents.mcp import MCPServer, MCPServerStreamableHttp, create_static_tool_filter

from app.config import Settings


async def connect_mcp_servers(settings: Settings) -> list[MCPServer]:
    """Connect every configured MCP server and prove it exposes usable tools.

    Called once from the app lifespan. Connect and clean up from the same task —
    the underlying MCP session uses task-scoped cancel scopes.
    """
    servers: list[MCPServer] = []

    if settings.mcp_server_url:
        headers: dict[str, str] = {}
        if settings.mcp_server_token:
            headers["Authorization"] = f"Bearer {settings.mcp_server_token}"

        server = MCPServerStreamableHttp(
            name="<server-label>",
            params={
                "url": settings.mcp_server_url,
                "headers": headers,
                "timeout": 30,
            },
            # The tool list is fetched on every agent run otherwise — one extra
            # round trip per request against a list that rarely changes.
            cache_tools_list=True,
            client_session_timeout_seconds=30,
            # Expose only the tools this agent actually needs. A server offering
            # 40 tools degrades tool selection and inflates every prompt.
            tool_filter=create_static_tool_filter(allowed_tool_names=["<tool-a>", "<tool-b>"]),
        )
        await server.connect()

        tools = await server.list_tools()
        if not tools:
            await server.cleanup()
            raise RuntimeError(
                f"MCP server at {settings.mcp_server_url} connected but exposes no tools "
                "(check the token, the server label, and the tool_filter allowlist)."
            )
        servers.append(server)

    return servers


async def disconnect_mcp_servers(servers: list[MCPServer]) -> None:
    for server in servers:
        try:
            await server.cleanup()
        except Exception:  # noqa: BLE001 - shutdown must not mask the original error
            pass
