"""Analytics: learn from post performance and recommend what to make next.

Closes the loop: research -> create -> publish -> measure -> create better.
As with market_research, MCP tools are agent-side, so the agent fetches live
Buffer metrics (get_aggregated_post_metrics / list_posts) and passes them in;
this module does the analysis with the LLM. Works in DRY-RUN with no API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .llm import LLM


@dataclass
class AnalyticsReport:
    summary: str = ""
    best_channel: str = ""
    best_times: list[str] = field(default_factory=list)
    top_posts: list[dict] = field(default_factory=list)   # {text, metric, value}
    what_worked: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    next_product_ideas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "best_channel": self.best_channel,
            "best_times": self.best_times,
            "top_posts": self.top_posts,
            "what_worked": self.what_worked,
            "recommendations": self.recommendations,
            "next_product_ideas": self.next_product_ideas,
        }

    def to_markdown(self) -> str:
        lines = ["# Performance Analytics\n", f"{self.summary}\n"]
        if self.best_channel:
            lines.append(f"**Best channel:** {self.best_channel}")
        if self.best_times:
            lines.append(f"**Best times:** {', '.join(self.best_times)}\n")
        if self.top_posts:
            lines.append("\n## Top posts")
            for p in self.top_posts:
                lines.append(
                    f"- {p.get('metric','')}: {p.get('value','')} — "
                    f"{str(p.get('text',''))[:90]}"
                )
        for title, items in (
            ("What worked", self.what_worked),
            ("Recommendations", self.recommendations),
            ("Next product ideas", self.next_product_ideas),
        ):
            if items:
                lines.append(f"\n## {title}")
                lines += [f"- {x}" for x in items]
        return "\n".join(lines) + "\n"

    def as_research_notes(self) -> str:
        """Feed back into config market_research.notes for the next run."""
        bits = []
        if self.what_worked:
            bits.append("What performed well: " + "; ".join(self.what_worked))
        if self.recommendations:
            bits.append("Do more of: " + "; ".join(self.recommendations))
        if self.next_product_ideas:
            bits.append("Product ideas from data: " + "; ".join(self.next_product_ideas))
        return "\n".join(bits)


def analyze(metrics: Any, brand: dict, llm: LLM) -> AnalyticsReport:
    if llm.dry_run:
        return AnalyticsReport(
            summary="[DRY-RUN] Set ANTHROPIC_API_KEY for real analysis. Pass Buffer "
            "metrics (get_aggregated_post_metrics / list_posts) to ground it.",
            best_channel="(dry-run)",
            best_times=["(dry-run)"],
            top_posts=[{"metric": "engagement", "value": "n/a", "text": "placeholder"}],
            what_worked=["(dry-run placeholder)"],
            recommendations=["(dry-run placeholder)"],
            next_product_ideas=["(dry-run placeholder)"],
        )

    system = (
        "You are a social-media analyst for a halal digital-products brand. Analyze "
        "the supplied Buffer metrics and give practical, honest, data-grounded "
        "recommendations. If data is thin, say so and give cautious guidance. Keep "
        "all suggestions halal and non-deceptive."
    )
    prompt = (
        f"Brand voice: {brand.get('voice','')}\nAudience: {brand.get('audience','')}\n\n"
        f"BUFFER METRICS (JSON):\n{json.dumps(metrics)[:7000]}\n\n"
        "Respond ONLY with JSON:\n"
        '{"summary": str, "best_channel": str, "best_times": [str], '
        '"top_posts": [{"text": str, "metric": str, "value": str}], '
        '"what_worked": [str], "recommendations": [str], "next_product_ideas": [str]}'
    )
    raw = llm.complete(system, prompt, temperature=0.3)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        d = json.loads(raw[start : end + 1])
        return AnalyticsReport(
            summary=str(d.get("summary", "")),
            best_channel=str(d.get("best_channel", "")),
            best_times=list(d.get("best_times", [])),
            top_posts=list(d.get("top_posts", [])),
            what_worked=list(d.get("what_worked", [])),
            recommendations=list(d.get("recommendations", [])),
            next_product_ideas=list(d.get("next_product_ideas", [])),
        )
    except Exception:
        return AnalyticsReport(summary=raw[:500])
