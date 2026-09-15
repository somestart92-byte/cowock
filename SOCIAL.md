# cowock social — publish & video automation

Generate posts, render short-form videos, schedule everything, and publish
**through MCP** — no platform API keys, no OAuth apps, no tokens in `.env`.

```
topic ──▶ copy per platform ──▶ compliance screen ──▶ scheduled queue
      └─▶ video script ──▶ slides ──▶ MP4 ─────────┘         │
                                                      you approve
                                                             │
                                          MCP job ──▶ your agent runs
                                       mcp__Buffer__create_post
                                                             │
                                                    mark_published
```

## Why MCP instead of platform APIs

Your Claude Code session already has publishing tools connected (Buffer, Canva,
Drive) with permissions **you** granted. This app never authenticates to a
social network. When a post comes due it emits the exact tool call that
publishes it; the agent runs it, then records the result back into the queue.
Nothing can go out behind your back, and there is no credential to leak.

## Quick start

```bash
pip install -r requirements.txt
python -m src.main social post "Screen-free summer activities for kids"
python -m src.main social queue
python -m src.main social approve --all
python -m src.main social serve          # dashboard on http://127.0.0.1:8000
```

With no `ANTHROPIC_API_KEY` the copy comes from built-in templates — the whole
pipeline (scheduling, rendering, queueing, hand-off) still works end to end.
Add the key for real, on-brand writing.

## Make a video

```bash
python -m src.main social video "Three ways to cut your grocery bill"
python -m src.main social video "Three ways to cut your grocery bill" --post \
    --platforms tiktok,instagram,youtube --theme sand --scenes 5
```

Renders 1080×1920 MP4s: branded slides, a slow Ken Burns push, crossfades and a
progress bar, optional voiceover. `--post` also writes the captions for each
platform and drops them into the queue with the video attached.

| Flag | What it does |
|---|---|
| `--scenes N` | how many beats in the script (hook → value → CTA) |
| `--theme` | `midnight`, `ink`, `sand`, `berry`, `slate` |
| `--preset` | `vertical` (9:16), `square`, `landscape` |
| `--voiceover` | `none`, `espeak` (offline), `elevenlabs` (`ELEVENLABS_API_KEY`) |
| `--music path.mp3` | background bed, ducked under the voice |
| `--seconds` | seconds per scene (voiceover stretches scenes automatically) |

Video needs ffmpeg. `pip install imageio-ffmpeg` ships a binary, or install
ffmpeg system-wide — the renderer finds either.

## Going live (the MCP hand-off)

1. Map each platform to a channel on your publishing MCP server. Ask your
   agent: *"list my Buffer channels"*, then:
   ```bash
   python -m src.main social accounts --add instagram --handle @you --channel-id <id>
   ```
   (or fill in `social.mcp.channels` in `config.yaml`).
2. Switch the mode in `config.yaml`: `social.publish_mode: live`.
3. Approve what you want out: `python -m src.main social approve --all`.
4. When slots arrive, the app emits jobs:
   ```bash
   python -m src.main social run        # or: social worker --interval 60
   python -m src.main social jobs       # shows the exact tool calls to run
   ```
5. Your agent runs each call and acknowledges:
   ```bash
   python -m src.main social ack <post_id> --external-id <id> --url <url>
   ```

Steps 4–5 are what you hand to Claude in one sentence: *"run the pending cowock
social jobs and ack them."*

## Driving it entirely from Claude Code

The app is itself an MCP server, so the agent can do the whole loop:

```bash
claude mcp add cowock-social -- python3 -m src.social.mcp_server
```

(`.mcp.json` in this repo already declares it; approve the tools by renaming
`.claude/settings.sample.json` → `.claude/settings.json` and restarting.)

Tools it exposes:

| Tool | Purpose |
|---|---|
| `generate_posts` | platform-native copy for a topic |
| `generate_video` / `create_video_campaign` | script + MP4, optionally with captions queued |
| `generate_image` | branded slide or quote card |
| `list_queue`, `edit_post`, `approve_posts`, `cancel_posts` | review workflow |
| `next_jobs` | due posts as ready-to-run MCP tool calls |
| `mark_published`, `mark_failed` | close the loop |
| `add_account`, `list_accounts` | channel mapping |
| `record_metrics`, `stats` | performance and queue health |

Then just say: *"write this week's posts about meal planning, render a video for
the best one, and queue everything for approval."*

## The dashboard

`python -m src.main social serve`

* **Queue** — every post with its status, char count and platform warnings; approve, cancel or publish
* **Compose** — topic in, drafts out
* **Video studio** — render and preview an MP4 in the browser, queue the captions
* **MCP jobs** — the pending tool calls, with a form to record the result
* **Accounts** — platform → channel-id mapping
* **Activity** — everything the app has done

## Safety rails

* Posts start as **drafts**; only `approved` posts are ever picked up.
* Every generated post is screened by the existing halal/honesty reviewer
  (`src/agent/compliance.py`) — flagged posts stay drafts.
* Platform limits (characters, hashtags, attachments, video requirements) are
  validated before anything is queued for delivery.
* `dry_run` mode writes the payload to `data/outbox/` and publishes nothing.
* An unmapped channel is an error, never a guess.

## Where things live

```
src/social/
  models.py       posts, accounts, platform limits, validation
  store.py        SQLite queue (data/social.db)
  generate.py     copy + video scripts (LLM, with offline templates)
  scheduler.py    posting slots, retries, the publish loop
  service.py      the application layer everything else calls
  platforms/      dry-run preview + MCP hand-off
  render/         slides (Pillow), video (ffmpeg), voiceover
  web/            FastAPI dashboard
  mcp_server.py   the app as an MCP server
  cli.py          python -m src.main social …
```

Local state (`data/`) is gitignored: the queue database, rendered media and the
job outbox.

## Tests

```bash
python tests/test_social.py      # 15 tests, offline, no network
```
