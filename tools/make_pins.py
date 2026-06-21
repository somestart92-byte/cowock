"""Generate 3 black+green CaroTech infographics to replace placeholder pins."""

from __future__ import annotations
import importlib.util
from pathlib import Path
from PIL import ImageDraw

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mg", ROOT / "tools/make_graphics.py")
mg = importlib.util.module_from_spec(spec); spec.loader.exec_module(mg)

GREEN, CREAM, MUTED = mg.GOLD, mg.CREAM, mg.MUTED
W, H = 1000, 1500


def base(kicker, title):
    img = mg.vgradient(W, H); d = ImageDraw.Draw(img); mg.corner_accent(d, W, H)
    d.text((60, 150), kicker, font=mg.font(mg.SANS_B, 32), fill=GREEN)
    y = mg.draw_block(d, title, mg.font(mg.SERIF_B, 74), 60, 196, W - 120, CREAM, line_gap=4)
    d.line([(60, y + 16), (250, y + 16)], fill=GREEN, width=5)
    return img, d, y + 70


def tiles(d, y, items):
    """Numbered list of point cards."""
    for i, t in enumerate(items, 1):
        d.ellipse([(60, y), (118, y + 58)], outline=GREEN, width=4)
        nf = mg.font(mg.SERIF_B, 30); nw = d.textlength(str(i), font=nf)
        d.text((60 + (58 - nw) / 2, y + 11), str(i), font=nf, fill=GREEN)
        mg.draw_block(d, t, mg.font(mg.SANS_B, 34), 144, y + 6, W - 200, CREAM, line_gap=4)
        y += 132
    return y


def checks(d, y, items):
    for t in items:
        # drawn check mark in a green rounded square (font has no ✓ glyph)
        d.rounded_rectangle([(60, y), (108, y + 48)], radius=10, fill=GREEN)
        d.line([(72, y + 25), (84, y + 37)], fill=mg.NAVY, width=6)
        d.line([(84, y + 37), (98, y + 13)], fill=mg.NAVY, width=6)
        mg.draw_block(d, t, mg.font(mg.SANS, 34), 134, y + 2, W - 190, CREAM, line_gap=4)
        y += 118
    return y


def footer_line(d, line):
    d.text((60, H - 230), line, font=mg.font(mg.SERIF_I, 32), fill=MUTED)
    mg.footer(d, W, H)


def pin_2hr():
    img, d, y = base("THE 2-HOUR MOMPRENEUR", "Start an online business in 2 hours")
    y = tiles(d, y + 6, [
        "Pick one idea you already know",
        "Build a simple PDF or printable",
        "Set up a free sales page",
        "Share the link & make your first sale",
    ])
    footer_line(d, "No tech skills. No startup costs.")
    img.save(ROOT / "assets/pin_2hr.png")


def pin_passive():
    img, d, y = base("PASSIVE INCOME, EXPLAINED", "Make it once. Sell it forever.")
    y = checks(d, y + 6, [
        "Create one digital product",
        "It sells hundreds of times",
        "No inventory, no shipping",
        "Nap time becomes income time",
    ])
    footer_line(d, "It's not magic — but it is possible.")
    img.save(ROOT / "assets/pin_passive.png")


def pin_messystart():
    img, d, y = base("FOR THE MOM WHO'S WAITING", "Done beats perfect.")
    y = tiles(d, y + 6, [
        "It doesn't have to be perfect",
        "The messy start IS the start",
        "Begin before you feel ready",
    ])
    footer_line(d, "If you've been waiting — this is it.")
    img.save(ROOT / "assets/pin_messystart.png")


if __name__ == "__main__":
    pin_2hr(); pin_passive(); pin_messystart()
    print("saved 3 infographics")
