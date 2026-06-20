"""Generate the digital product itself (the thing customers pay for)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .llm import LLM


@dataclass
class Product:
    product_type: str
    title: str
    subtitle: str
    price_usd: float
    outline: list[str] = field(default_factory=list)
    body_markdown: str = ""

    def to_dict(self) -> dict:
        return {
            "product_type": self.product_type,
            "title": self.title,
            "subtitle": self.subtitle,
            "price_usd": self.price_usd,
            "outline": self.outline,
        }


def _idea(niche: str, brand: dict, product_type: str, llm: LLM, hint: str = "") -> dict:
    system = (
        "You are a product strategist for a halal digital-products brand. "
        "Propose ONE specific, sellable product idea. Be concrete and useful."
    )
    hint_block = f"\nMarket-research hint (favor this):\n{hint}\n" if hint else ""
    prompt = (
        f"Brand voice: {brand.get('voice', 'practical')}\n"
        f"Audience: {brand.get('audience', 'Muslims')}\n"
        f"Niche: {niche}\n"
        f"Product type: {product_type}{hint_block}\n\n"
        "Respond ONLY with JSON: "
        '{"title": str, "subtitle": str, "price_usd": number, '
        '"outline": [str, ...]}  (6-10 outline items for an ebook, 5-8 for others)'
    )
    raw = llm.complete(system, prompt, temperature=0.6)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        return json.loads(raw[start : end + 1])
    except Exception:
        return {
            "title": f"The {niche} Starter Guide",
            "subtitle": "A practical, halal, no-fluff guide.",
            "price_usd": 9.0,
            "outline": [f"Chapter {i}: (dry-run placeholder)" for i in range(1, 7)],
        }


def _write_body(product: Product, niche: str, brand: dict, llm: LLM) -> str:
    system = (
        "You are a skilled writer for a halal digital-products brand. Write "
        "clear, genuinely useful content in Markdown. Honest tone, no fluff, "
        "no overpromising, respectful of Islamic etiquette."
    )
    sections = []
    for i, item in enumerate(product.outline, start=1):
        prompt = (
            f"Product: {product.title} — {product.subtitle}\n"
            f"Niche: {niche}\nVoice: {brand.get('voice')}\n\n"
            f"Write section {i}: '{item}'.\n"
            "300-500 words, Markdown, with a short actionable takeaway at the end."
        )
        sections.append(f"## {item}\n\n{llm.complete(system, prompt)}")
    return "\n\n".join(sections)


def build_product(product_type: str, niche: str, brand: dict, llm: LLM,
                  hint: str = "") -> Product:
    idea = _idea(niche, brand, product_type, llm, hint)
    product = Product(
        product_type=product_type,
        title=idea.get("title", "Untitled"),
        subtitle=idea.get("subtitle", ""),
        price_usd=float(idea.get("price_usd", 9.0)),
        outline=list(idea.get("outline", [])),
    )
    product.body_markdown = _write_body(product, niche, brand, llm)
    return product
