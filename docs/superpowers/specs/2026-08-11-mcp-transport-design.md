# MCP Transport Design

## Goal

Replace the in-process `inline` tool adapter with Model Context Protocol transports. Support only `stdio` and Streamable HTTP, beginning with a working local `stdio` path while retaining an explicit HTTP configuration boundary.

## Scope

- Replace `app/mcp_server/client.py` transport implementation.
- Update MCP configuration and the engine's client construction.
- Update `app/mcp_server/server.py` so its process entry point selects a supported official transport.
- Update focused MCP tests.

The simulation agents, `RoleToolRouter`, tool business functions, RAG behavior, API routes, and scenario rules do not change.

## Transport Contract

### Supported Modes

- `stdio`: Starts the local `app.mcp_server.server` process and communicates using the official MCP stdio transport. This is the default local-development path.
- `http`: Connects to a remote MCP server over the official Streamable HTTP transport. It requires a configured endpoint URL and optional bearer token.

`inline`, plain application HTTP, and direct imports of `app.mcp_server.tools` from the client are not MCP transports and must not be accepted.

### Configuration

Add the following settings, read only from environment variables:

- `MCP_TRANSPORT`: `stdio` or `http`; default `stdio` when MCP is enabled.
- `MCP_HTTP_URL`: required only for `http`.
- `MCP_HTTP_TOKEN`: optional bearer token for a remote MCP server.
- `MCP_STDIO_COMMAND`: optional executable override; default is the current Python interpreter.

The HTTP configuration is included now so deployment can switch transports without business-code changes. No ModelScope configuration is needed unless an external ModelScope MCP server is chosen; in that case its published MCP endpoint and authentication token populate the HTTP settings.

## Client Design

`McpToolClient` retains a synchronous `call(tool_name, arguments) -> McpToolResult` surface for existing agents. Internally it:

1. Opens an MCP `ClientSession` through the selected transport.
2. Performs `initialize` once per client lifecycle.
3. Calls `list_tools` lazily for the existing allowlist and invokes tools with `call_tool`.
4. Converts protocol errors, timeouts, unknown tools, and empty content to the current typed result contract.
5. Closes the session and its transport deterministically.

The `stdio` version runs the existing FastMCP server in a child process. Tool responses come only from MCP `CallToolResult` content blocks, never through direct Python function calls.

## Server Design

`server.py` continues to define one `FastMCP` instance and the existing tool metadata. Its command-line entry point selects:

- `stdio` by default using `mcp.run(transport="stdio")`.
- Streamable HTTP only when explicitly configured, using a separate MCP serving process/endpoint rather than mounting onto the existing FastAPI business application.

Unsupported transport values fail at startup with a clear configuration error.

## Reliability And Security

- Use a bounded timeout for MCP initialization and each tool call.
- Do not log tokens or full tool payloads.
- Preserve tool allowlisting at the client boundary.
- An unavailable MCP service returns `McpToolResult(status="error")`; agents retain their existing local/RAG fallbacks.

## Testing And Verification

- Replace tests that assert `inline` behavior with configuration validation and protocol behavior tests.
- Start the real local server via `stdio`, initialize the MCP session, list the four registered tools, and invoke a non-network tool.
- Unit-test HTTP configuration validation without connecting to an external server.
- Run focused MCP tests and the relevant agent-router tests, then run the full pytest suite if it completes in the local environment.
