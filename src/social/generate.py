"""Content generation: platform-native posts and short-video scripts.

Uses the Anthropic API when ``ANTHROPIC_API_KEY`` is present and falls back to
deterministic templates otherwise, so the whole app is demoable offline.
"""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field, asdict
from typing import Any

from src.agent.llm import LLM

from .config import SocialConfig
from .models import LIMITS, Post

SYSTEM = (
    "You are a senior social media strategist and copywriter. You write "
    "platform-native copy that sounds like a real person, never like an ad. "
    "You never invent statistics, never promise results or earnings, and never "
    "use false scarcity. Every claim must be literally true and defensible."
)

PLATFORM_STYLE = {
    "x": "One punchy idea. Max 280 characters including hashtags. No emoji spam. Hook in the first 7 words.",
    "threads": "Conversational, max 500 characters, a little warmth, ends with a question.",
    "instagram": "Hook line, a line break, 3-5 short value lines, then a CTA. Up to 2200 chars. Emoji used sparingly.",
    "tiktok": "Short spoken-style caption under 150 chars that teases the video payoff.",
    "youtube": "A Shorts title under 70 chars plus a 2-3 sentence description.",
    "linkedin": "Professional but human. Short paragraphs, a concrete lesson, no hashtag soup.",
    "facebook": "Friendly and plain-spoken, 2-4 short paragraphs, a clear CTA.",
    "pinterest": "A keyword-rich title under 60 chars plus a descriptive 2-sentence blurb.",
    "telegram": "Direct and useful, under 1000 chars, markdown allowed.",
}


@dataclass
class ContentBrief:
    """Everything the generator needs to write a batch of posts."""

    topic: str
    platforms: list[str] = field(default_factory=list)
    angle: str = ""
    audience: str = ""
    cta: str = ""
    link: str = ""
    campaign: str = "default"
    count: int = 1                      # variants per platform
    tone: str = ""
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Scene:
    """One beat of a short video: on-screen text plus what the voice says."""

    text: str
    voiceover: str = ""
    seconds: float = 0.0
    emphasis: str = ""      # optional small kicker line under the main text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoScript:
    title: str
    hook: str
    scenes: list[Scene]
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "hook": self.hook,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "scenes": [s.to_dict() for s in self.scenes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoScript":
        return cls(
            title=data.get("title", ""),
            hook=data.get("hook", ""),
            caption=data.get("caption", ""),
            hashtags=list(data.get("hashtags", [])),
            scenes=[
                Scene(
                    text=s.get("text", ""),
                    voiceover=s.get("voiceover", ""),
                    seconds=float(s.get("seconds", 0) or 0),
                    emphasis=s.get("emphasis", ""),
                )
                for s in data.get("scenes", [])
            ],
        )


# ---------------------------------------------------------------- helpers
def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of an LLM response."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except ValueError:
        pass
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except ValueError:
                continue
    raise ValueError("no JSON found in model response")


def clean_hashtags(tags: Any, platform: str) -> list[str]:
    limit = LIMITS.get(platform, {}).get("hashtags", 5)
    out: list[str] = []
    for tag in tags or []:
        slug = re.sub(r"[^0-9A-Za-z]", "", str(tag))
        if slug and slug.lower() not in {t.lower() for t in out}:
            out.append(slug)
    return out[:limit]


def fit(text: str, platform: str, reserved: int = 0) -> str:
    """Trim copy to the platform limit at a sentence boundary where possible."""
    limit = LIMITS.get(platform, {}).get("chars", 2200) - reserved
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? ", "\n"):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1].strip()
    return cut[: limit - 1].rstrip() + "…"


def _brand_context(cfg: SocialConfig, brief: ContentBrief) -> str:
    brand = cfg.brand or {}
    lines = [
        f"Brand: {brand.get('name', 'the brand')}",
        f"Voice: {brief.tone or brand.get('voice', 'clear, warm, practical')}",
        f"Audience: {brief.audience or brand.get('audience', 'general audience')}",
    ]
    if cfg.niche:
        lines.append(f"Niche: {cfg.niche}")
    forbid = (cfg.rules or {}).get("forbid") or []
    if forbid:
        lines.append("Never: " + "; ".join(str(f) for f in forbid[:6]))
    return "\n".join(lines)


# ------------------------------------------------------------ post copy
def generate_posts(brief: ContentBrief, cfg: SocialConfig, llm: LLM) -> list[Post]:
    """Return one :class:`Post` per platform per requested variant."""
    platforms = brief.platforms or cfg.default_platforms
    if llm.dry_run:
        drafts = _template_posts(brief, platforms)
    else:
        drafts = _llm_posts(brief, platforms, cfg, llm)

    posts: list[Post] = []
    for draft in drafts:
        platform = draft["platform"]
        hashtags = clean_hashtags(draft.get("hashtags") or cfg.hashtag_pool, platform)
        reserved = len(" ".join(f"#{h}" for h in hashtags)) + len(brief.link) + 4
        posts.append(
            Post(
                platform=platform,
                title=draft.get("title", "")[:100],
                body=fit(draft.get("body", ""), platform, reserved=max(reserved, 0)),
                hashtags=hashtags,
                link=brief.link,
                first_comment=draft.get("first_comment", ""),
                campaign=brief.campaign,
                source="generated",
                meta={"topic": brief.topic, "angle": brief.angle, "brief": brief.to_dict()},
            )
        )
    return posts


def _llm_posts(
    brief: ContentBrief, platforms: list[str], cfg: SocialConfig, llm: LLM
) -> list[dict[str, Any]]:
    style = "\n".join(
        f"- {p}: {PLATFORM_STYLE.get(p, 'platform-native copy')} (hard limit "
        f"{LIMITS.get(p, {}).get('chars', 2200)} characters)"
        for p in platforms
    )
    prompt = textwrap.dedent(
        f"""
        {_brand_context(cfg, brief)}

        Topic: {brief.topic}
        Angle: {brief.angle or "pick the most useful, specific angle"}
        Call to action: {brief.cta or "invite a reply or a save"}
        Link to include (may be empty): {brief.link}
        Keywords to weave in naturally: {", ".join(brief.keywords) or "(none)"}

        Write {brief.count} distinct variant(s) for EACH of these platforms:
        {style}

        Rules:
        - Each variant must stand alone and be genuinely useful on its own.
        - No fabricated numbers, no earnings or results claims, no false urgency.
        - Hashtags: relevant, lowercase, no '#' in the value, within the platform limit.
        - `first_comment` is optional and only for instagram/linkedin.

        Return ONLY a JSON array, no prose:
        [{{"platform": "x", "title": "", "body": "...", "hashtags": ["..."], "first_comment": ""}}]
        """
    ).strip()

    raw = llm.complete(SYSTEM, prompt)
    data = extract_json(raw)
    if isinstance(data, dict):
        data = data.get("posts", [])
    out = [d for d in data if isinstance(d, dict) and d.get("platform") in platforms]
    return out or _template_posts(brief, platforms)


def _template_posts(brief: ContentBrief, platforms: list[str]) -> list[dict[str, Any]]:
    """Offline fallback — real, usable copy built from the brief."""
    topic = brief.topic.strip().rstrip(".")
    angle = (brief.angle or "the part most people skip").strip().rstrip(".")
    cta = brief.cta or "Save this for the next time you need it."
    tags = brief.keywords or [w.lower() for w in re.findall(r"[A-Za-z]{4,}", topic)][:3]
    bodies = {
        "x": f"{topic}: {angle}.\n\nStart with one small step today. {cta}",
        "threads": f"{topic} — {angle}.\n\nOne small step beats a perfect plan. What's yours this week?",
        "instagram": (
            f"{topic} ✦\n\n{angle.capitalize()}.\n\n"
            "• Pick one thing you can do in 10 minutes\n"
            "• Do it at the same time tomorrow\n"
            "• Track it somewhere you can see\n\n"
            f"{cta}"
        ),
        "tiktok": f"{topic} — {angle}. Watch to the end for the simple version.",
        "youtube": f"{topic}: {angle}. A short, practical walkthrough you can use today.",
        "linkedin": (
            f"{topic}.\n\n{angle.capitalize()}.\n\n"
            "What worked for me was shrinking the task until it was too small to skip, "
            "then repeating it at the same time each day.\n\n"
            f"{cta}"
        ),
        "facebook": f"{topic}\n\n{angle.capitalize()}. Here's the simple version you can start this week.\n\n{cta}",
        "pinterest": f"{topic} — {angle}. A simple, practical starting point.",
        "telegram": f"*{topic}*\n\n{angle.capitalize()}.\n\n{cta}",
    }
    out: list[dict[str, Any]] = []
    for platform in platforms:
        for n in range(max(brief.count, 1)):
            body = bodies.get(platform, f"{topic} — {angle}. {cta}")
            if n:
                body = f"{body}\n\n(variant {n + 1})"
            out.append(
                {
                    "platform": platform,
                    "title": topic[:70],
                    "body": body,
                    "hashtags": tags,
                    "first_comment": "",
                }
            )
    return out


# ---------------------------------------------------------- video script
def generate_video_script(
    topic: str,
    cfg: SocialConfig,
    llm: LLM,
    scenes: int = 6,
    angle: str = "",
    cta: str = "",
) -> VideoScript:
    """Write a short-form video script: a hook, value beats and a CTA."""
    if llm.dry_run:
        return _template_script(topic, scenes, angle, cta)

    brief = ContentBrief(topic=topic, angle=angle, cta=cta)
    prompt = textwrap.dedent(
        f"""
        {_brand_context(cfg, brief)}

        Write a {scenes}-scene vertical short-form video script about: {topic}
        Angle: {angle or "the most useful, specific take"}
        Call to action for the final scene: {cta or "follow for more"}

        Requirements:
        - Scene 1 is the hook: at most 8 words, makes someone stop scrolling.
        - Middle scenes each carry ONE idea, at most 12 words of on-screen text.
        - `voiceover` is what a narrator says for that scene: one natural sentence.
        - `emphasis` is an optional 2-5 word kicker shown under the main text.
        - No fabricated statistics, no earnings or results claims.
        - `caption` is the post caption (max 150 words).

        Return ONLY JSON:
        {{"title": "...", "hook": "...", "caption": "...", "hashtags": ["..."],
          "scenes": [{{"text": "...", "voiceover": "...", "emphasis": ""}}]}}
        """
    ).strip()

    try:
        data = extract_json(llm.complete(SYSTEM, prompt))
        script = VideoScript.from_dict(data)
        if script.scenes:
            script.hashtags = clean_hashtags(script.hashtags, "tiktok")
            return script
    except (ValueError, KeyError, TypeError):
        pass
    return _template_script(topic, scenes, angle, cta)


def _template_script(topic: str, scenes: int, angle: str, cta: str) -> VideoScript:
    topic = topic.strip().rstrip(".")
    angle = (angle or "the part most people skip").strip().rstrip(".")
    beats = [
        Scene(text=topic, voiceover=f"Here is {topic.lower()}.", emphasis="in 30 seconds"),
        Scene(text=angle.capitalize(), voiceover=f"Most advice misses {angle.lower()}."),
        Scene(text="Start smaller than feels useful", voiceover="Shrink the task until it is too small to skip."),
        Scene(text="Attach it to something you already do", voiceover="Anchor it to a habit that already happens."),
        Scene(text="Track it where you can see it", voiceover="Keep the streak visible and it keeps itself."),
        Scene(text=cta or "Follow for more", voiceover=cta or "Follow for more practical breakdowns.", emphasis="save this"),
    ]
    chosen = beats[: max(2, min(scenes, len(beats)))]
    if chosen[-1].text != (cta or "Follow for more"):
        chosen[-1] = beats[-1]
    return VideoScript(
        title=topic[:70],
        hook=chosen[0].text,
        caption=f"{topic} — {angle}. The short version, in under a minute.",
        hashtags=[w.lower() for w in re.findall(r"[A-Za-z]{4,}", topic)][:3] or ["tips"],
        scenes=chosen,
    )
