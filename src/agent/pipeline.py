"""Orchestrate the full run: idea -> product -> marketing -> compliance -> approval.

The pipeline NEVER publishes or touches money. It writes everything to disk and
drops an approval request you must accept before anything goes live. This is the
'without you involving' model done honestly: the agent does the work, you give
the final yes.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from . import compliance, marketing, product
from .config import Config
from .llm import LLM


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "product"


def run(cfg: Config) -> Path:
    llm = LLM(
        model=cfg.llm.get("model", "claude-opus-4-8"),
        max_tokens=cfg.llm.get("max_tokens", 4000),
        temperature=cfg.llm.get("temperature", 0.7),
    )

    mode = "DRY-RUN (no API key)" if llm.dry_run else f"LIVE ({llm.model})"
    print(f"▶ cowock run — {mode}")
    print(f"  niche: {cfg.niche}")

    product_type = cfg.product_types[0]
    print(f"  building product ({product_type})…")
    prod = product.build_product(product_type, cfg.niche, cfg.brand, llm)
    print(f"  → {prod.title}  (${prod.price_usd:.0f})")

    print("  building marketing kit…")
    kit = marketing.build_kit(prod, cfg.channels, cfg.brand, llm)

    # Compliance review across product body + all marketing copy.
    combined = "\n\n".join(
        [prod.title, prod.subtitle, prod.body_markdown, kit.email, *kit.posts.values()]
    )
    print("  running halal-compliance review…")
    verdict = compliance.review(combined, cfg.halal_rules, llm)
    print(f"  → compliance ok={verdict.ok} score={verdict.score}")
    if verdict.issues:
        for issue in verdict.issues:
            print(f"     ⚠ {issue}")

    # Persist artifacts.
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = cfg.output_dir / f"{stamp}-{_slug(prod.title)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "product.md").write_text(
        f"# {prod.title}\n\n*{prod.subtitle}*\n\n"
        f"**Suggested price:** ${prod.price_usd:.2f}\n\n---\n\n{prod.body_markdown}\n",
        encoding="utf-8",
    )
    (run_dir / "marketing.md").write_text(_render_marketing(kit), encoding="utf-8")
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "product": prod.to_dict(),
                "compliance": verdict.to_dict(),
                "channels": cfg.channels,
                "created": stamp,
                "mode": mode,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    approval = _write_approval(cfg, run_dir, prod, verdict)
    print(f"✓ done. Artifacts: {run_dir}")
    print(f"✓ approval request: {approval}")
    print("  Review it, set \"approved\": true, then run the publish step.")
    return run_dir


def _render_marketing(kit: marketing.MarketingKit) -> str:
    parts = ["# Marketing Kit\n"]
    for channel, text in kit.posts.items():
        parts.append(f"## {channel.title()}\n\n{text}\n")
    if kit.email:
        parts.append(f"## Email\n\n{kit.email}\n")
    if kit.cover_brief:
        parts.append(f"## Cover design brief\n\n{kit.cover_brief}\n")
    return "\n".join(parts)


def _write_approval(cfg: Config, run_dir: Path, prod, verdict) -> Path:
    payload = {
        "approved": False,
        "title": prod.title,
        "price_usd": prod.price_usd,
        "compliance_ok": verdict.ok,
        "compliance_score": verdict.score,
        "compliance_issues": verdict.issues,
        "artifacts_dir": str(run_dir),
        "instructions": (
            "Review product.md and marketing.md in artifacts_dir. If you approve, "
            "set 'approved' to true. Publishing (Buffer/Gumroad/email) is a "
            "separate, deliberate step — the agent will not act until you do."
        ),
    }
    path = cfg.approvals_dir / f"{run_dir.name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
