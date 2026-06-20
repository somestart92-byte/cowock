"""Generate marketing assets for a finished product."""

from __future__ import annotations

from dataclasses import dataclass, field

from .llm import LLM
from .product import Product


@dataclass
class MarketingKit:
    posts: dict[str, str] = field(default_factory=dict)  # channel -> text
    email: str = ""
    cover_brief: str = ""  # design brief for Canva / a designer

    def to_dict(self) -> dict:
        return {"posts": self.posts, "email": self.email, "cover_brief": self.cover_brief}


def _post(channel: str, product: Product, brand: dict, llm: LLM) -> str:
    rules = {
        "twitter": "A punchy hook + 3-5 tweet thread. No hashtag spam.",
        "instagram": "An engaging caption + a 5-slide carousel outline.",
        "email": "A warm launch email: subject line + body, one clear CTA.",
    }
    system = (
        "You are a marketer for a halal brand. Honest, value-first copy. "
        "No false scarcity, no exaggerated guarantees, respectful tone."
    )
    prompt = (
        f"Product: {product.title} — {product.subtitle} (${product.price_usd:.0f})\n"
        f"Voice: {brand.get('voice')}\nAudience: {brand.get('audience')}\n\n"
        f"Channel: {channel}. {rules.get(channel, 'Write a short promo post.')}"
    )
    return llm.complete(system, prompt)


def _cover_brief(product: Product, brand: dict, llm: LLM) -> str:
    system = "You write concise design briefs for product covers."
    prompt = (
        f"Write a 4-6 line cover-design brief for '{product.title}'. "
        f"Brand voice: {brand.get('voice')}. Specify mood, colors, typography, "
        "and imagery. Keep it modest and Islamic-etiquette friendly (no imagery "
        "of people in immodest dress, no music/idol imagery)."
    )
    return llm.complete(system, prompt)


def build_kit(product: Product, channels: list[str], brand: dict, llm: LLM) -> MarketingKit:
    kit = MarketingKit()
    for channel in channels:
        if channel == "email":
            kit.email = _post("email", product, brand, llm)
        else:
            kit.posts[channel] = _post(channel, product, brand, llm)
    kit.cover_brief = _cover_brief(product, brand, llm)
    return kit
