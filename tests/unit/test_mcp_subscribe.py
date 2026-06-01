"""MCP resource subscription stub handlers."""

from __future__ import annotations

import mcp.types as types

from km.adapters.mcp.server import mcp


def test_resource_subscription_stubs_registered() -> None:
    handlers = mcp._mcp_server.request_handlers
    assert types.SubscribeRequest in handlers
    assert types.UnsubscribeRequest in handlers
