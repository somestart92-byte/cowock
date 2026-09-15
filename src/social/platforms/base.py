"""Publisher interface shared by the delivery adapters.

There are two adapters on purpose, and neither one holds a platform API key:

* :class:`~src.social.platforms.dryrun.DryRunPublisher` writes the exact payload
  to disk so you can review it.
* :class:`~src.social.platforms.mcp_handoff.McpHandoffPublisher` emits a job
  describing the MCP tool call to make, which your Claude Code session runs
  against its connected MCP servers (Buffer, Canva, Drive, …).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Account, Post, PublishResult


class NotConfigured(RuntimeError):
    """Raised when routing for a platform is missing (no channel mapped, etc.)."""


class PublishError(RuntimeError):
    """Raised when delivery failed."""


class Publisher(ABC):
    """A delivery mechanism for a finished post."""

    name: str = ""

    def __init__(self, config=None):
        self.config = config

    def configured(self) -> bool:
        return True

    @abstractmethod
    def publish(self, post: Post, account: Account | None, media: list[Path]) -> PublishResult:
        """Deliver ``post``; raise :class:`PublishError` if it cannot be done."""

    @staticmethod
    def setting(account: Account | None, key: str, default: str = "") -> str:
        if account and key in account.settings:
            return str(account.settings[key])
        return default
