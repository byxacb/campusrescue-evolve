"""Lazy MCP toolset loader for ADK agents.

Wraps `McpToolset` so ADK agents can declare MCP tools at construction time
without performing the network handshake until first invocation. We expose a
synchronous helper `get_mcp_tools(name)` that returns a list of `MCPTool`
objects suitable for passing to `LlmAgent(tools=...)`.
"""
from __future__ import annotations
import asyncio
import os
from typing import List
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool import McpToolset

# Map of MCP name → env var holding its URL
_MCP_ENV = {
    "data_retrieve": "MCP_DATA_RETRIEVE_URL",
    "evaluator_run": "MCP_EVALUATOR_RUN_URL",
    "audit_report": "MCP_AUDIT_REPORT_URL",
    "hardagents_compile": "MCP_HARDAGENTS_COMPILE_URL",
    "campusflow_run": "MCP_CAMPUSFLOW_RUN_URL",
}

# Default URLs (production Cloud Run endpoints in us-central1)
_MCP_DEFAULTS = {
    "data_retrieve": "https://mcp-data-retrieve-5l3z4bmblq-uc.a.run.app/mcp",
    "evaluator_run": "https://mcp-evaluator-run-5l3z4bmblq-uc.a.run.app/mcp",
    "audit_report": "https://mcp-audit-report-5l3z4bmblq-uc.a.run.app/mcp",
    "hardagents_compile": "https://mcp-hardagents-compile-5l3z4bmblq-uc.a.run.app/mcp",
    "campusflow_run": "https://mcp-campusflow-run-5l3z4bmblq-uc.a.run.app/mcp",
}

def mcp_url(name: str) -> str:
    env = _MCP_ENV.get(name)
    if env and os.environ.get(env):
        return os.environ[env]
    return _MCP_DEFAULTS[name]

async def _get_tools_async(name: str) -> List:
    url = mcp_url(name)
    params = StreamableHTTPConnectionParams(url=url)
    ts = McpToolset(connection_params=params)
    return await ts.get_tools()

def get_mcp_tools(name: str) -> List:
    """Synchronously fetch tools from MCP server `name` (one of the 5 BYO-MCPs)."""
    return asyncio.run(_get_tools_async(name))

def get_mcp_toolsets(names: List[str]) -> List:
    """Return a flat list of MCPTools for several MCPs at once (used by orchestrator)."""
    out = []
    for n in names:
        out.extend(get_mcp_tools(n))
    return out
