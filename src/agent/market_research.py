"""Market research: analyze a niche before building products.

Live web data is gathered by the agent (via web search) and passed in as
`notes`; this module structures and analyzes it with the LLM into a usable
report — opportunities, pricing, keywords, and ranked product ideas — that the
product generator can consume. Falls back to LLM-only knowledge when no notes
are supplied, and to a placeholder in DRY-RUN.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .llm import LLM


@dataclass
class MarketReport:
    niche: str
    summary: str = ""
    opportunities: list[str] = field(default_factory=list)
    pricing: str = ""
    keywords: list[str] = field(default_factory=list)
    product_ideas: list[dict] = field(default_factory=list)  # {title, why, price_usd, demand}

    def to_dict(self) -> dict:
        return {
            "niche": self.niche,
            "summary": self.summary,
            "opportunities": self.opportunities,
            "pricing": self.pricing,
            "keywords": self.keywords,
            "product_ideas": self.product_ideas,
        }

    def top_idea(self) -> dict | None:
        return self.product_ideas[0] if self.product_ideas else None

    def to_markdown(self) -> str:
        lines = [f"# Market Research — {self.niche}\n", f"{self.summary}\n"]
        if self.opportunities:
            lines.append("## Opportunities")
            lines += [f"- {o}" for o in self.opportunities]
            lines.append("")
        if self.pricing:
            lines.append("## Pricing\n" + self.pricing + "\n")
        if self.keywords:
            lines.append("## Keywords / SEO\n" + ", ".join(self.keywords) + "\n")
        if self.product_ideas:
            lines.append("## Product ideas (ranked by demand)")
            for i, idea in enumerate(self.product_ideas, 1):
                lines.append(
                    f"{i}. **{idea.get('title','')}** "
                    f"(${idea.get('price_usd','?')}, demand: {idea.get('demand','?')}) — "
                    f"{idea.get('why','')}"
                )
            lines.append("")
        return "\n".join(lines)


def research(niche: str, brand: dict, llm: LLM, notes: str = "") -> MarketReport:
    if llm.dry_run:
        return MarketReport(
            niche=niche,
            summary="[DRY-RUN] Set ANTHROPIC_API_KEY for real analysis. Pass live "
            "web findings via `notes` to ground the report in current data.",
            opportunities=["(dry-run placeholder opportunity)"],
            pricing="(dry-run) typical digital-product range applies",
            keywords=["placeholder", "keyword"],
            product_ideas=[
                {"title": f"{niche} starter bundle", "why": "placeholder",
                 "price_usd": 17, "demand": "n/a"}
            ],
        )

    system = (
        "You are a market analyst for a halal digital-products brand. Analyze the "
        "niche and produce a practical, honest report. Prefer the supplied live "
        "research notes over assumptions. Keep all suggestions halal (no riba, "
        "gambling, haram, or deceptive tactics)."
    )
    grounding = f"\n\nLIVE RESEARCH NOTES (prefer these):\n{notes}\n" if notes else ""
    prompt = (
        f"Niche: {niche}\n"
        f"Brand voice: {brand.get('voice','')}\n"
        f"Audience: {brand.get('audience','')}{grounding}\n\n"
        "Respond ONLY with JSON:\n"
        '{"summary": str, "opportunities": [str], "pricing": str, '
        '"keywords": [str], "product_ideas": [{"title": str, "why": str, '
        '"price_usd": number, "demand": "high|medium|low"}]}\n'
        "Rank product_ideas best-first; give 4-6 ideas."
    )
    raw = llm.complete(system, prompt, temperature=0.4)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1])
        return MarketReport(
            niche=niche,
            summary=str(data.get("summary", "")),
            opportunities=list(data.get("opportunities", [])),
            pricing=str(data.get("pricing", "")),
            keywords=list(data.get("keywords", [])),
            product_ideas=list(data.get("product_ideas", [])),
        )
    except Exception:
        return MarketReport(niche=niche, summary=raw[:500])
