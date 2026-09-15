"""Delivery adapters: dry-run preview and MCP hand-off."""

from __future__ import annotations

from .base import NotConfigured, PublishError, Publisher
from .dryrun import DryRunPublisher
from .mcp_handoff import McpHandoffPublisher, ToolCall

__all__ = [
    "NotConfigured",
    "PublishError",
    "Publisher",
    "DryRunPublisher",
    "McpHandoffPublisher",
    "ToolCall",
    "get_publisher",
]


def get_publisher(config) -> Publisher:
    """Pick the adapter for the configured publish mode."""
    mode = getattr(config, "publish_mode", "dry_run")
    if mode == "live":
        return McpHandoffPublisher(config)
    return DryRunPublisher(config)
