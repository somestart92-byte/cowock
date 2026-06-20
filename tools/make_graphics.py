"""Generate faceless CaroTech brand infographics (navy/dark-blue + gold).

Brand rules: navy/dark-blue background, gold accents, off-white text, NO pink,
text-only/faceless graphics. Serif headline (Lora-like) + sans body (Poppins-like).
Outputs a vertical Pinterest Pin and a 5-slide Instagram carousel.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "products/output/carotech-faceless-shop-graphics"
OUT.mkdir(parents=True, exist_ok=True)

# Palette
NAVY = (10, 31, 68)        # #0A1F44
NAVY2 = (20, 39, 78)       # #14274E (panel)
GOLD = (201, 162, 75)      # #C9A24B
CREAM = (244, 241, 234)    # #F4F1EA
MUTED = (183, 195, 214)    # soft blue-grey

SERIF_B = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
SANS_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def vgradient(w: int, h: int) -> Image.Image:
    """Subtle vertical navy gradient background."""
    base = Image.new("RGB", (w, h), NAVY)
    top, bottom = (8, 24, 54), (16, 34, 72)
    px = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return base


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_block(draw, text, fnt, x, y, max_w, fill, line_gap=12, center=False, cw=0):
    for line in wrap(draw, text, fnt, max_w):
        lw = draw.textlength(line, font=fnt)
        lx = x + (cw - lw) / 2 if center else x
        draw.text((lx, y), line, font=fnt, fill=fill)
        asc, desc = fnt.getmetrics()
        y += asc + desc + line_gap
    return y


def corner_accent(draw, w, h):
    """Minimal gold geometric corner marks (no imagery of people)."""
    draw.line([(60, 60), (160, 60)], fill=GOLD, width=4)
    draw.line([(60, 60), (60, 160)], fill=GOLD, width=4)
    draw.line([(w - 60, 60), (w - 160, 60)], fill=GOLD, width=4)
    draw.line([(w - 60, 60), (w - 60, 160)], fill=GOLD, width=4)


def footer(draw, w, h, tagline="beacons.ai/carotech36"):
    f_brand = font(SANS_B, 30)
    f_url = font(SANS, 26)
    draw.text((60, h - 110), "CAROTECH", font=f_brand, fill=GOLD)
    tw = draw.textlength(tagline, font=f_url)
    draw.text((w - 60 - tw, h - 108), tagline, font=f_url, fill=MUTED)


# ── Pinterest Pin (1000 x 1500) ──────────────────────────────────────────────
def pinterest_pin():
    w, h = 1000, 1500
    img = vgradient(w, h)
    d = ImageDraw.Draw(img)
    corner_accent(d, w, h)

    d.text((60, 150), "FACELESS SIDE HUSTLE", font=font(SANS_B, 34), fill=GOLD)
    y = draw_block(d, "How to start a digital shop in nap-time",
                   font(SERIF_B, 84), 60, 210, w - 120, CREAM, line_gap=6)

    d.line([(60, y + 20), (260, y + 20)], fill=GOLD, width=5)
    y += 70

    steps = [
        ("1", "Pick one small problem you've already solved."),
        ("2", "Make one simple printable in Canva."),
        ("3", "Share one helpful tip a day."),
    ]
    for num, text in steps:
        # gold number disc
        d.ellipse([(60, y), (130, y + 70)], outline=GOLD, width=4)
        nf = font(SERIF_B, 42)
        nw = d.textlength(num, font=nf)
        d.text((60 + (70 - nw) / 2, y + 8), num, font=nf, fill=GOLD)
        draw_block(d, text, font(SANS, 40), 160, y + 2, w - 220, CREAM, line_gap=8)
        y += 150

    d.text((60, y + 10), "No face. No audience. No fancy setup.",
           font=font(SERIF_I, 38), fill=MUTED)

    footer(d, w, h)
    path = OUT / "pinterest_pin.png"
    img.save(path)
    return path


# ── Instagram carousel (1080 x 1080 x5) ──────────────────────────────────────
def slide(filename, kicker, headline, body=None, big=False, cta=False):
    w = h = 1080
    img = vgradient(w, h)
    d = ImageDraw.Draw(img)
    corner_accent(d, w, h)

    if kicker:
        d.text((80, 150), kicker, font=font(SANS_B, 30), fill=GOLD)

    hsize = 92 if big else 72
    y = draw_block(d, headline, font(SERIF_B, hsize), 80, 230, w - 160, CREAM, line_gap=4)
    d.line([(80, y + 24), (250, y + 24)], fill=GOLD, width=5)
    y += 70

    if body:
        y = draw_block(d, body, font(SANS, 42), 80, y, w - 160, MUTED, line_gap=14)

    if cta:
        d.rounded_rectangle([(80, h - 250), (w - 80, h - 150)], radius=16,
                            outline=GOLD, width=4)
        txt = "Full step-by-step → link in bio"
        tf = font(SANS_B, 38)
        tw = d.textlength(txt, font=tf)
        d.text(((w - tw) / 2, h - 222), txt, font=tf, fill=CREAM)

    footer(d, w, h)
    path = OUT / filename
    img.save(path)
    return path


def carousel():
    paths = []
    paths.append(slide("ig_1_hook.png", "FOR THE BUSY MOM",
                       "You don't need a following to make your first sale.",
                       big=True))
    paths.append(slide("ig_2.png", "WHAT YOU ACTUALLY NEED",
                       "One useful product + a place to put it.",
                       body="That's it. No big audience required."))
    paths.append(slide("ig_3.png", "STEP 1",
                       "Pick one small problem you've already solved.",
                       body="Meal planning. Budgeting. Potty training. You know more than you think."))
    paths.append(slide("ig_4.png", "STEPS 2 & 3",
                       "Make one printable, then teach daily.",
                       body="Build it in Canva (beginner-easy). Share one helpful tip a day."))
    paths.append(slide("ig_5_cta.png", "START TODAY",
                       "Begin with step one. 💛",
                       body="No face. No audience. No fancy setup.", cta=True))
    return paths


if __name__ == "__main__":
    made = [pinterest_pin(), *carousel()]
    for p in made:
        print(p)
