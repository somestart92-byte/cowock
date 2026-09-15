"""Tests for the social automation app — all offline, no API key, no network."""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.social.config import load_config
from src.social.generate import ContentBrief, clean_hashtags, extract_json, fit, generate_posts
from src.social.models import APPROVED, DRAFT, HANDOFF, PUBLISHED, Account, MediaAsset, Post
from src.social.platforms import DryRunPublisher, McpHandoffPublisher
from src.social.platforms.base import NotConfigured
from src.social.scheduler import schedule_posts, upcoming_slots
from src.social.service import SocialService
from src.social.store import Store

UTC = timezone.utc


def _tmp_config(tmp: Path):
    os.environ.pop("ANTHROPIC_API_KEY", None)
    cfg = load_config()
    cfg.db_path = str(tmp / "social.db")
    cfg.media_dir = str(tmp / "media")
    return cfg


# ------------------------------------------------------------------ models
def test_post_validation_catches_platform_limits():
    long_post = Post(platform="x", body="x" * 400)
    assert any("exceeds" in p for p in long_post.validate())

    ok = Post(platform="x", body="short and sweet", hashtags=["tips"])
    assert ok.validate() == []
    assert ok.full_text.endswith("#tips")

    video_only = Post(platform="tiktok", body="caption")
    assert "tiktok requires a video attachment" in video_only.validate()

    with_video = Post(
        platform="tiktok", body="caption", media=[MediaAsset(path="data/media/a.mp4", kind="video")]
    )
    assert with_video.validate() == []


def test_hashtag_and_fit_helpers():
    # '#' stripped, duplicates dropped case-insensitively, capped at the x limit of 3.
    assert clean_hashtags(["#Tips", "tips", "Budget!", "a b", "extra"], "x") == ["Tips", "Budget", "ab"]
    assert len(fit("word " * 200, "x")) <= 280
    assert extract_json('```json\n[{"platform": "x"}]\n```') == [{"platform": "x"}]


# ------------------------------------------------------------------- store
def test_store_roundtrip_and_due_posts():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "s.db")
        account = store.save_account(Account(platform="x", handle="@me", settings={"channel_id": "c1"}))
        assert store.account(account.id).settings["channel_id"] == "c1"

        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        store.save_post(Post(platform="x", body="due now", status=APPROVED, scheduled_at=past))
        store.save_post(Post(platform="x", body="later", status=APPROVED, scheduled_at=future))
        store.save_post(Post(platform="x", body="draft", status=DRAFT, scheduled_at=past))

        due = store.due_posts(datetime.now(UTC).isoformat())
        assert [p.body for p in due] == ["due now"]
        assert store.counts_by_status()["approved"] == 2

        store.log("test", "hello", post_id=due[0].id)
        assert store.events(post_id=due[0].id)[0]["kind"] == "test"
        store.close()


# -------------------------------------------------------------- generation
def test_offline_generation_respects_platform_limits():
    cfg = load_config()
    from src.agent.llm import LLM

    llm = LLM(model="test")
    assert llm.dry_run, "tests must run without an API key"
    posts = generate_posts(
        ContentBrief(topic="Weekly meal planning", platforms=["x", "instagram", "linkedin"], cta="Save this"),
        cfg,
        llm,
    )
    assert {p.platform for p in posts} == {"x", "instagram", "linkedin"}
    for post in posts:
        assert len(post.full_text) <= post.limits()["chars"]
        assert post.body.strip()


# --------------------------------------------------------------- scheduling
def test_slots_are_in_the_future_and_never_double_booked():
    cfg = load_config()
    start = datetime(2026, 1, 5, 6, 0, tzinfo=UTC)
    slots = upcoming_slots(cfg, "x", 4, start=start, per_day=2)
    assert len(slots) == 4
    assert all(s > start for s in slots)
    assert len(set(slots)) == 4

    taken = {slots[0].isoformat()}
    again = upcoming_slots(cfg, "x", 1, start=start, taken=taken, per_day=2)
    assert again[0].isoformat() not in taken


def test_schedule_posts_assigns_distinct_times():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        store = Store(cfg.db_path)
        posts = [Post(platform="x", body=f"post {i}") for i in range(3)]
        schedule_posts(store, cfg, posts)
        assert len({p.scheduled_at for p in posts}) == 3
        store.close()


# --------------------------------------------------------------- publishing
def test_dry_run_publisher_writes_the_payload():
    with tempfile.TemporaryDirectory() as tmp:
        publisher = DryRunPublisher(outbox=Path(tmp))
        post = Post(platform="x", body="hello", hashtags=["tips"])
        result = publisher.publish(post, Account(platform="x", handle="@me"), [])
        assert result.ok and result.dry_run
        written = json.loads(next(Path(tmp).glob("*.json")).read_text())
        assert written["text"] == post.full_text
        assert written["platform"] == "x"


def test_mcp_handoff_builds_the_tool_call():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        cfg.mcp = {**cfg.mcp, "channels": {"x": "chan_x"}, "posting_type": "schedule"}
        publisher = McpHandoffPublisher(cfg, outbox=Path(tmp) / "outbox")
        post = Post(platform="x", body="hello", hashtags=["tips"])

        result = publisher.publish(post, None, [])
        assert result.pending and result.ok
        call = result.tool_call
        assert call["name"] == "mcp__Buffer__create_post"
        assert call["arguments"]["channelIds"] == ["chan_x"]
        assert call["arguments"]["text"] == post.full_text
        assert "scheduledAt" in call["arguments"]

        jobs = publisher.pending_jobs()
        assert len(jobs) == 1 and jobs[0]["post_id"] == post.id
        publisher.complete(post.id)
        assert publisher.pending_jobs() == []


def test_unmapped_channel_is_reported_not_guessed():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        publisher = McpHandoffPublisher(cfg, outbox=Path(tmp) / "outbox")
        try:
            publisher.publish(Post(platform="pinterest", body="hi"), None, [])
        except NotConfigured as exc:
            assert "no MCP channel mapped" in str(exc)
        else:
            raise AssertionError("expected NotConfigured")


# ------------------------------------------------------------------ service
def test_full_flow_generate_approve_handoff_ack():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        cfg.publish_mode = "live"
        cfg.mcp = {**cfg.mcp, "channels": {"x": "chan_x"}}
        service = SocialService(cfg)
        service.add_account("x", "@cowock", channel_id="chan_x")

        result = service.create_posts("Weekly meal planning", ["x"], cta="Save this")
        post = result.posts[0]
        assert post.status == DRAFT

        assert service.approve([post.id])
        assert service.store.post(post.id).status == APPROVED

        # Due now → the app emits a job instead of calling any API.
        service.reschedule(post.id, (datetime.now(UTC) - timedelta(minutes=1)).isoformat())
        report = service.run_due()
        assert report.handed_off == 1 and report.published == 0
        assert service.store.post(post.id).status == HANDOFF

        jobs = service.pending_jobs()
        assert jobs[0]["tool_call"]["name"].startswith("mcp__")

        service.ack(post.id, external_id="buf_1", url="https://x.com/cowock/status/1")
        done = service.store.post(post.id)
        assert done.status == PUBLISHED and done.external_id == "buf_1"
        assert service.pending_jobs() == []
        service.close()


def test_compliance_flag_keeps_a_post_out_of_the_approved_queue():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        service = SocialService(cfg)
        result = service.create_posts(
            "Guaranteed returns from a casino betting system", ["x"], approve=True
        )
        assert result.flagged, "the reviewer should flag this topic"
        assert all(p.status == DRAFT for p in result.posts)
        service.close()


# -------------------------------------------------------------------- video
def test_video_renders_a_playable_mp4():
    from src.social.render.video import VideoError, ffmpeg_path

    try:
        ffmpeg_path()
    except VideoError:
        print("skipped: ffmpeg not available")
        return

    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        cfg.video = {**cfg.video, "seconds_per_scene": 1.2, "fps": 12, "zoom": False}
        service = SocialService(cfg)
        rendered, script = service.make_video("Meal planning in ten minutes", scenes=3)
        assert rendered.path.exists() and rendered.path.stat().st_size > 10_000
        assert rendered.scenes == 3 and rendered.duration > 1
        assert len(script.scenes) == 3
        service.close()


def test_video_campaign_attaches_the_video_to_every_post():
    from src.social.render.video import VideoError, ffmpeg_path

    try:
        ffmpeg_path()
    except VideoError:
        print("skipped: ffmpeg not available")
        return

    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        cfg.video = {**cfg.video, "seconds_per_scene": 1.0, "fps": 12, "zoom": False}
        service = SocialService(cfg)
        result = service.create_video_campaign(
            "Meal planning in ten minutes", ["tiktok", "instagram"], scenes=2
        )
        assert result.video is not None
        for post in result.posts:
            assert post.media and post.media[0].kind == "video"
            assert post.validate() == []
        service.close()


# ---------------------------------------------------------------------- web
def test_dashboard_pages_render():
    from fastapi.testclient import TestClient
    from src.social.web.app import create_app

    with tempfile.TemporaryDirectory() as tmp:
        cfg = _tmp_config(Path(tmp))
        client = TestClient(create_app(cfg))
        for path in ("/", "/compose", "/studio", "/jobs", "/accounts", "/events"):
            assert client.get(path).status_code == 200, path
        assert client.post(
            "/compose", data={"topic": "Weekly meal planning", "platforms": "x", "count": "1"}
        ).status_code == 200
        assert client.get("/api/stats").json()["publish_mode"] == cfg.publish_mode


# ---------------------------------------------------------------- mcp server
def test_mcp_server_exposes_the_expected_tools():
    import asyncio

    import src.social.mcp_server as mcp_server

    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    for expected in (
        "generate_posts",
        "generate_video",
        "create_video_campaign",
        "list_queue",
        "approve_posts",
        "next_jobs",
        "mark_published",
        "stats",
    ):
        assert expected in names, expected


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"  ✓ {test.__name__}")
    print(f"OK — {len(tests)} tests")
