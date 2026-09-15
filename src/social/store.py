"""SQLite persistence for accounts, posts, events and metrics.

Plain ``sqlite3`` on purpose: one file, no server, no extra dependency, and the
whole queue is inspectable with any SQLite browser.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import Account, Post, now_iso, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           TEXT PRIMARY KEY,
    platform     TEXT NOT NULL,
    handle       TEXT NOT NULL,
    display_name TEXT,
    enabled      INTEGER NOT NULL DEFAULT 1,
    settings     TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,
    account_id    TEXT,
    platform      TEXT NOT NULL,
    campaign      TEXT,
    title         TEXT,
    body          TEXT,
    hashtags      TEXT,
    media         TEXT,
    link          TEXT,
    first_comment TEXT,
    scheduled_at  TEXT NOT NULL,
    status        TEXT NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    external_id   TEXT,
    external_url  TEXT,
    published_at  TEXT,
    source        TEXT,
    meta          TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_due ON posts (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_posts_campaign ON posts (campaign);

CREATE TABLE IF NOT EXISTS events (
    id         TEXT PRIMARY KEY,
    post_id    TEXT,
    kind       TEXT NOT NULL,
    message    TEXT,
    data       TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id         TEXT PRIMARY KEY,
    post_id    TEXT NOT NULL,
    platform   TEXT NOT NULL,
    impressions INTEGER DEFAULT 0,
    likes       INTEGER DEFAULT 0,
    comments    INTEGER DEFAULT 0,
    shares      INTEGER DEFAULT 0,
    clicks      INTEGER DEFAULT 0,
    collected_at TEXT NOT NULL
);
"""

POST_COLUMNS = (
    "id, account_id, platform, campaign, title, body, hashtags, media, link, "
    "first_comment, scheduled_at, status, attempts, error, external_id, "
    "external_url, published_at, source, meta, created_at, updated_at"
)
POST_PLACEHOLDERS = ", ".join("?" * len(POST_COLUMNS.split(",")))


class Store:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # -- plumbing --------------------------------------------------------
    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

    # -- accounts --------------------------------------------------------
    def save_account(self, account: Account) -> Account:
        with self._tx() as c:
            c.execute(
                "INSERT OR REPLACE INTO accounts "
                "(id, platform, handle, display_name, enabled, settings, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                account.to_row(),
            )
        return account

    def accounts(self, platform: str | None = None, enabled_only: bool = False) -> list[Account]:
        sql = "SELECT * FROM accounts"
        where, args = [], []
        if platform:
            where.append("platform = ?")
            args.append(platform)
        if enabled_only:
            where.append("enabled = 1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY platform, handle"
        return [Account.from_row(r) for r in self._conn.execute(sql, args)]

    def account(self, account_id: str) -> Account | None:
        row = self._conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return Account.from_row(row) if row else None

    def delete_account(self, account_id: str) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    # -- posts -----------------------------------------------------------
    def save_post(self, post: Post) -> Post:
        post.updated_at = now_iso()
        with self._tx() as c:
            c.execute(
                f"INSERT OR REPLACE INTO posts ({POST_COLUMNS}) VALUES ({POST_PLACEHOLDERS})",
                post.to_row(),
            )
        return post

    def save_posts(self, posts: list[Post]) -> list[Post]:
        for p in posts:
            self.save_post(p)
        return posts

    def post(self, post_id: str) -> Post | None:
        row = self._conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return Post.from_row(row) if row else None

    def posts(
        self,
        status: str | list[str] | None = None,
        platform: str | None = None,
        campaign: str | None = None,
        limit: int = 200,
        order: str = "scheduled_at ASC",
    ) -> list[Post]:
        sql = "SELECT * FROM posts"
        where, args = [], []
        if status:
            statuses = [status] if isinstance(status, str) else list(status)
            where.append(f"status IN ({', '.join('?' * len(statuses))})")
            args.extend(statuses)
        if platform:
            where.append("platform = ?")
            args.append(platform)
        if campaign:
            where.append("campaign = ?")
            args.append(campaign)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order} LIMIT ?"
        args.append(limit)
        return [Post.from_row(r) for r in self._conn.execute(sql, args)]

    def due_posts(self, as_of_iso: str, limit: int = 25) -> list[Post]:
        """Approved posts whose scheduled time has arrived, oldest first."""
        rows = self._conn.execute(
            "SELECT * FROM posts WHERE status = 'approved' AND scheduled_at <= ? "
            "ORDER BY scheduled_at ASC LIMIT ?",
            (as_of_iso, limit),
        )
        return [Post.from_row(r) for r in rows]

    def delete_post(self, post_id: str) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    def counts_by_status(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT status, COUNT(*) n FROM posts GROUP BY status")
        return {r["status"]: r["n"] for r in rows}

    def scheduled_times(self, platform: str) -> set[str]:
        """Times already taken on a platform, so the scheduler never double-books."""
        rows = self._conn.execute(
            "SELECT scheduled_at FROM posts WHERE platform = ? AND status IN "
            "('draft', 'approved', 'handoff')",
            (platform,),
        )
        return {r["scheduled_at"] for r in rows}

    # -- events ----------------------------------------------------------
    def log(self, kind: str, message: str, post_id: str | None = None, **data: Any) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO events (id, post_id, kind, message, data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (new_id("evt"), post_id, kind, message, json.dumps(data or {}), now_iso()),
            )

    def events(self, limit: int = 100, post_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events"
        args: list[Any] = []
        if post_id:
            sql += " WHERE post_id = ?"
            args.append(post_id)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    # -- metrics ---------------------------------------------------------
    def record_metrics(self, post_id: str, platform: str, **stats: int) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO metrics (id, post_id, platform, impressions, likes, comments, "
                "shares, clicks, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id("met"),
                    post_id,
                    platform,
                    stats.get("impressions", 0),
                    stats.get("likes", 0),
                    stats.get("comments", 0),
                    stats.get("shares", 0),
                    stats.get("clicks", 0),
                    now_iso(),
                ),
            )

    def metrics_summary(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT platform, COUNT(DISTINCT post_id) posts, SUM(impressions) impressions, "
            "SUM(likes) likes, SUM(comments) comments, SUM(shares) shares, SUM(clicks) clicks "
            "FROM metrics GROUP BY platform ORDER BY impressions DESC"
        )
        return [dict(r) for r in rows]
