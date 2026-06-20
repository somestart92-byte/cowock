"""Halal-compliance reviewer.

Every generated asset passes through here before it can be queued for human
approval. It does a fast keyword screen, then (when an API key is present) an
LLM judgement against the rules in config.yaml. The result is advisory and
always surfaced to the human — the agent never silently publishes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .llm import LLM

# Fast, conservative keyword screen. Catches obvious problems with zero cost.
_RED_FLAGS = [
    "interest rate", "apr", "credit card rewards", "casino", "lottery",
    "betting", "gambling", "alcohol", "wine", "beer", "pork", "bacon",
    "get rich quick", "guaranteed returns", "double your money", "nft pump",
    "crypto pump", "forex signals", "nude", "dating app", "onlyfans",
]


@dataclass
class Verdict:
    ok: bool
    score: int  # 0-100, higher = more compliant
    issues: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "score": self.score,
            "issues": self.issues,
            "notes": self.notes,
        }


def _keyword_screen(text: str) -> list[str]:
    lowered = text.lower()
    return [flag for flag in _RED_FLAGS if flag in lowered]


def review(text: str, halal_rules: dict, llm: LLM) -> Verdict:
    hits = _keyword_screen(text)

    if llm.dry_run:
        # Without an LLM we rely on the keyword screen only.
        if hits:
            return Verdict(
                ok=False,
                score=40,
                issues=[f"keyword match: {h}" for h in hits],
                notes="DRY-RUN keyword screen only. Human review required.",
            )
        return Verdict(
            ok=True,
            score=80,
            notes="DRY-RUN keyword screen passed. Human review still required.",
        )

    forbid = "\n".join(f"- {r}" for r in halal_rules.get("forbid", []))
    require = "\n".join(f"- {r}" for r in halal_rules.get("require", []))
    system = (
        "You are a careful Islamic-compliance reviewer for a digital-products "
        "business. Judge whether the supplied marketing/product text complies "
        "with Islamic (halal) principles. Be fair and practical, not overly "
        "strict, but flag genuine issues."
    )
    prompt = (
        f"FORBIDDEN:\n{forbid}\n\nREQUIRED:\n{require}\n\n"
        f"TEXT TO REVIEW:\n'''\n{text[:6000]}\n'''\n\n"
        "Respond ONLY with JSON: "
        '{"ok": bool, "score": 0-100, "issues": [string], "notes": string}'
    )
    raw = llm.complete(system, prompt, temperature=0.0)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1])
        verdict = Verdict(
            ok=bool(data.get("ok", False)),
            score=int(data.get("score", 0)),
            issues=list(data.get("issues", [])),
            notes=str(data.get("notes", "")),
        )
    except Exception:
        verdict = Verdict(
            ok=False, score=0, issues=["could not parse reviewer output"], notes=raw[:300]
        )

    # Merge in keyword hits the LLM may have missed.
    for h in hits:
        kw = f"keyword match: {h}"
        if kw not in verdict.issues:
            verdict.issues.append(kw)
            verdict.ok = False
    return verdict
