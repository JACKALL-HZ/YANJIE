# MCP Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the non-protocol `inline` MCP adapter with official `stdio` and Streamable HTTP transports, with a fully working local `stdio` path.

**Architecture:** `McpToolClient` keeps its synchronous `list_tools()` / `call()` API for `RoleToolRouter`, but owns a dedicated asyncio loop thread. That thread opens and initializes one `mcp.ClientSession` with either `stdio_client` or `streamable_http_client`; synchronous callers submit coroutines with a bounded timeout. The FastMCP server owns transport selection at process startup and continues to expose the existing tool definitions unchanged.

**Tech Stack:** Python 3.12, MCP SDK 1.29.0, AnyIO, asyncio, httpx, FastMCP, pytest.

## Global Constraints

- Supported MCP transports are exactly `stdio` and `http`; reject `inline` and any other value.
- `http` means MCP Streamable HTTP, never a plain business API request.
- Do not direct-import `app.mcp_server.tools` from `McpToolClient`.
- Preserve the synchronous `McpToolResult` contract and existing `RoleToolRouter` fallback behavior.
- Do not log tokens or full tool payloads.
- Do not commit or push.

### Task 1: Add MCP Transport Configuration

**Files:**
- Modify: `app/core/config.py`
- Test: `tests/test_mcp_client.py`

**Interfaces:**
- Produces `Settings.mcp_transport: Literal["stdio", "http"]`, `mcp_http_url`, `mcp_http_token`, `mcp_stdio_command`, and `mcp_timeout_seconds`.
- `SimulationEngine` consumes these settings in Task 4.

- [x] **Step 1: Write failing configuration tests**

Add tests asserting that the environment accepts `MCP_TRANSPORT=stdio` and `MCP_TRANSPORT=http`, rejects `inline`, and rejects HTTP mode without `MCP_HTTP_URL` when `MCP_ENABLED=1`.

```python
def test_settings_reject_inline_mcp_transport(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "1")
    monkeypatch.setenv("MCP_TRANSPORT", "inline")
    with pytest.raises(ValueError, match="MCP_TRANSPORT"):
        get_settings()
```

- [x] **Step 2: Run the focused test and confirm failure**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py::test_settings_reject_inline_mcp_transport -q`

Expected: FAIL because `get_settings()` has no MCP transport validation.

- [x] **Step 3: Implement the settings fields and validation**

Add typed settings values from `MCP_TRANSPORT`, `MCP_HTTP_URL`, `MCP_HTTP_TOKEN`, `MCP_STDIO_COMMAND`, and `MCP_TIMEOUT_SECONDS`. Default the transport to `stdio`; use `sys.executable` when no stdio command override is supplied. In `_validate_settings`, accept only `stdio` / `http`, require the URL for enabled HTTP mode, and require a timeout in a bounded range such as 1-120 seconds.

- [x] **Step 4: Run focused configuration tests**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py -q`

Expected: configuration tests pass; old inline tests remain intentionally failing until Task 2 updates them.

### Task 2: Replace The Inline Client With An Official Session Client

**Files:**
- Modify: `app/mcp_server/client.py`
- Modify: `tests/test_mcp_client.py`

**Interfaces:**
- `McpToolClient(mode: Literal["stdio", "http"], *, http_url: str | None = None, http_token: str = "", stdio_command: str | None = None, timeout_seconds: float = 15.0)`.
- Public methods remain `list_tools() -> list[str]`, `call(tool_name, arguments) -> McpToolResult`, and `close() -> None`.

- [x] **Step 1: Replace inline tests with protocol-level contract tests**

Delete tests that mutate `client._tools` or expect `inline`. Add tests that assert unsupported mode returns a configuration error, a `stdio` client can list the four server tools, an unknown tool returns `UNKNOWN_TOOL`, and the non-network `assess_execution_capacity` call returns a typed `ok` result.

```python
def test_stdio_client_lists_registered_mcp_tools():
    with McpToolClient(mode="stdio", timeout_seconds=10) as client:
        assert {"search_knowledge", "search_web", "assess_execution_capacity", "run_risk_stress_test"} <= set(client.list_tools())
```

- [x] **Step 2: Run the stdio test and confirm failure**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py::test_stdio_client_lists_registered_mcp_tools -q`

Expected: FAIL because the old client rejects `stdio`.

- [x] **Step 3: Implement the session lifecycle worker**

Remove `subprocess`, `_tools`, and `_init_inline`. Implement a private worker thread that:

1. Creates an asyncio event loop.
2. Opens `async with stdio_client(StdioServerParameters(command=..., args=["-m", "app.mcp_server.server"], cwd=<repo root>))` for stdio, or `async with create_mcp_http_client(headers=...)` plus `async with streamable_http_client(url, http_client=...)` for HTTP.
3. Opens `async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=timeout))` and awaits `session.initialize()`.
4. Stores the active loop/session, signals readiness, and stays alive until `close()` signals an asyncio shutdown event.

`call()` must enforce the static allowlist discovered from `session.list_tools()`, schedule `session.call_tool(name, arguments)` with `asyncio.run_coroutine_threadsafe`, use `.result(timeout_seconds)`, and transform text content blocks into `McpToolResult`. Map missing names to `UNKNOWN_TOOL`, timeout to `TOOL_TIMEOUT`, protocol errors to `TOOL_EXECUTION_FAILED`, and blank text to `empty`.

- [x] **Step 4: Implement deterministic close and context-manager support**

Make `close()` signal shutdown through `loop.call_soon_threadsafe`, join the worker with a bounded timeout, and clear all references. Add `__enter__` and `__exit__` so focused tests cannot leak child processes or sockets.

- [x] **Step 5: Run the focused MCP client tests**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py -q`

Expected: all tests pass and the local stdio child exits after every context manager block.

### Task 3: Make The MCP Server Transport Explicit

**Files:**
- Modify: `app/mcp_server/server.py`
- Modify: `tests/test_mcp.py`

**Interfaces:**
- Module execution respects `MCP_SERVER_TRANSPORT=stdio|http`.
- `stdio` maps to FastMCP's `"stdio"`; `http` maps to `"streamable-http"`.

- [x] **Step 1: Write failing transport-selection tests**

Extract a small pure function such as `resolve_transport(raw: str | None) -> Literal["stdio", "streamable-http"]` and test default stdio, explicit HTTP, and invalid input.

```python
def test_resolve_transport_maps_http_to_streamable_http():
    assert resolve_transport("http") == "streamable-http"
```

- [x] **Step 2: Run the test and confirm failure**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp.py::test_resolve_transport_maps_http_to_streamable_http -q`

Expected: FAIL because `resolve_transport` does not exist.

- [x] **Step 3: Implement explicit server transport selection**

Read `MCP_SERVER_TRANSPORT`, resolve it through the pure helper, and call `mcp.run(transport=resolved_transport)` under `if __name__ == "__main__"`. Keep default stdio. Do not mount this application into FastAPI.

- [x] **Step 4: Run focused server tests**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp.py -q`

Expected: server metadata/tool tests and the new transport-selection tests pass.

### Task 4: Wire The Engine To Settings And Preserve Fallbacks

**Files:**
- Modify: `app/engine/engine.py`
- Modify: `app/services/simulation_service.py`
- Modify: `tests/test_role_tool_router.py`
- Modify: `tests/test_mcp_client.py`

**Interfaces:**
- `SimulationEngine` creates `McpToolClient` from `Settings` only when MCP is enabled and the engine is not running in stub mode.
- `RoleToolRouter` remains unchanged and receives the same synchronous result type.

- [x] **Step 1: Write a failing construction test**

Patch `app.engine.engine.McpToolClient` and assert the engine passes configured `mcp_transport`, HTTP URL/token, command, and timeout instead of the removed inline literal.

- [x] **Step 2: Run the focused test and confirm failure**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py -q`

Expected: FAIL because the engine still calls `McpToolClient(mode="inline")`.

- [x] **Step 3: Implement settings-based client construction and cleanup**

Construct the client with settings fields and store it on `SimulationEngine`. Add an idempotent `SimulationEngine.close()` that closes the MCP client and exits the existing checkpointer context manager. In `SimulationService`, wrap synchronous `run`, `resume_from_state`, and `compare` calls in `try/finally: engine.close()`. Replace the direct return from `aiter_events` with an async generator wrapper that closes the engine in `finally` after completion, cancellation, or disconnect. Do not close it between the four tool calls within one coordination pass. Preserve the no-MCP retriever fallback when client initialization fails.

- [x] **Step 4: Run focused regression tests**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py tests/test_role_tool_router.py -q`

Expected: PASS. Existing injected failing clients still create error evidence and local fallback behavior remains intact.

### Task 5: Verify End To End

**Files:**
- Verify: `app/mcp_server/client.py`, `app/mcp_server/server.py`, `app/engine/engine.py`

- [ ] **Step 1: Run all focused MCP and router tests**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_mcp.py tests/test_mcp_client.py tests/test_role_tool_router.py -q`

Expected: PASS.

- [ ] **Step 2: Manually verify the stdio protocol path**

Run a short Python invocation that constructs `McpToolClient(mode="stdio")`, lists the server tools, calls `assess_execution_capacity`, prints only result status, and closes the client. Do not print the full payload or environment values.

- [ ] **Step 3: Validate HTTP configuration without remote credentials**

Run the HTTP configuration validation test without an endpoint and confirm it fails with the documented configuration error. Do not call external HTTP services.

- [ ] **Step 4: Run the complete test suite**

Run: `& .\.venv\Scripts\python.exe -m pytest --continue-on-collection-errors --maxfail=20`

Expected: all tests pass. If pre-existing unrelated tests stall, report the last completed test and keep the focused MCP suite result separate.
