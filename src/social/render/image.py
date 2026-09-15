"""Brand slide rendering with Pillow.

Every video frame and every static graphic is a slide: a themed background,
a big headline set in a readable width, an optional kicker, and a footer with
the handle plus a progress bar.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIRS = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/freefont",
    "/usr/share/fonts/truetype",
)
FONT_CANDIDATES = {
    "bold": ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "FreeSansBold.ttf"),
    "regular": ("DejaVuSans.ttf", "LiberationSans-Regular.ttf", "FreeSans.ttf"),
    "serif_bold": ("DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf", "FreeSerifBold.ttf"),
}

SIZES = {
    "vertical": (1080, 1920),   # Reels / Shorts / TikTok
    "square": (1080, 1080),     # feed
    "landscape": (1920, 1080),  # YouTube / X
    "pin": (1000, 1500),        # Pinterest
}


@dataclass(frozen=True)
class Theme:
    bg: tuple[int, int, int]
    bg2: tuple[int, int, int]
    text: tuple[int, int, int]
    accent: tuple[int, int, int]
    muted: tuple[int, int, int]
    serif: bool = False


THEMES: dict[str, Theme] = {
    "midnight": Theme((10, 12, 11), (18, 24, 20), (244, 247, 244), (46, 204, 113), (150, 170, 158)),
    "ink": Theme((14, 16, 22), (24, 28, 40), (240, 242, 248), (99, 132, 255), (140, 150, 175)),
    "sand": Theme((244, 240, 232), (232, 226, 214), (28, 26, 24), (186, 122, 60), (120, 112, 102), serif=True),
    "berry": Theme((26, 10, 24), (46, 16, 42), (252, 240, 250), (233, 84, 150), (180, 150, 175)),
    "slate": Theme((30, 34, 38), (44, 50, 56), (238, 242, 245), (255, 189, 68), (155, 168, 178)),
}


def _font_path(kind: str) -> str:
    for name in FONT_CANDIDATES[kind]:
        for directory in FONT_DIRS:
            candidate = Path(directory) / name
            if candidate.exists():
                return str(candidate)
    raise FileNotFoundError(
        "No usable TrueType font found. Install fonts-dejavu-core or fonts-liberation."
    )


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_font_path(kind), size)


def _gradient(size: tuple[int, int], theme: Theme) -> Image.Image:
    """Smooth vertical wash between the two theme backgrounds, plus an accent glow."""
    w, h = size
    base = Image.new("RGB", (1, h))
    top, bottom = theme.bg2, theme.bg
    px = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    base = base.resize((w, h), Image.BICUBIC)

    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse(
        (-w // 2, -h // 3, int(w * 1.2), int(h * 0.45)), fill=64
    )
    glow = glow.filter(ImageFilter.GaussianBlur(w // 6))
    accent = Image.new("RGB", (w, h), theme.accent)
    return Image.composite(Image.blend(base, accent, 0.22), base, glow)


def _wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=f) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    kind: str,
    max_width: int,
    max_height: int,
    start: int,
    minimum: int = 36,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Shrink the headline until it fits the text box."""
    size = start
    while size > minimum:
        f = font(kind, size)
        lines = _wrap(draw, text, f, max_width)
        line_h = int(size * 1.22)
        if len(lines) * line_h <= max_height:
            return f, lines
        size -= 4
    f = font(kind, minimum)
    return f, _wrap(draw, text, f, max_width)


def render_slide(
    text: str,
    *,
    theme: str | Theme = "midnight",
    size: str | tuple[int, int] = "vertical",
    emphasis: str = "",
    kicker: str = "",
    footer: str = "",
    index: int = 0,
    total: int = 0,
    background: str | Path | None = None,
) -> Image.Image:
    """Render one branded slide."""
    th = theme if isinstance(theme, Theme) else THEMES.get(str(theme), THEMES["midnight"])
    dims = SIZES.get(size, SIZES["vertical"]) if isinstance(size, str) else size
    w, h = dims

    if background and Path(background).exists():
        img = Image.open(background).convert("RGB")
        img = _cover(img, (w, h))
        shade = Image.new("RGB", (w, h), th.bg)
        img = Image.blend(img, shade, 0.55)
    else:
        img = _gradient((w, h), th)

    draw = ImageDraw.Draw(img)
    margin = int(w * 0.09)
    box_w = w - margin * 2
    head_kind = "serif_bold" if th.serif else "bold"

    head_font, lines = _fit_font(
        draw, text, head_kind, box_w, int(h * 0.42), start=int(w * 0.105), minimum=int(w * 0.035)
    )
    line_h = int(head_font.size * 1.2)
    block_h = line_h * len(lines)
    y = (h - block_h) // 2 - int(h * 0.04)

    # Accent rule above the headline, with the kicker label above that.
    rule_y = y - int(h * 0.05)
    draw.rounded_rectangle(
        (margin, rule_y, margin + int(w * 0.14), rule_y + max(6, w // 180)),
        radius=6,
        fill=th.accent,
    )
    if kicker:
        kf = font("bold", int(w * 0.028))
        draw.text(
            (margin, rule_y - int(kf.size * 2.1)),
            " ".join(kicker.upper()),
            font=kf,
            fill=th.muted,
        )

    for line in lines:
        draw.text((margin, y), line, font=head_font, fill=th.text)
        y += line_h

    if emphasis:
        ef = font("regular", int(w * 0.040))
        for line in _wrap(draw, emphasis, ef, box_w)[:3]:
            y += int(ef.size * 0.6)
            draw.text((margin, y), line, font=ef, fill=th.accent)
            y += int(ef.size * 1.05)

    if footer:
        ff = font("regular", int(w * 0.028))
        draw.text((margin, h - int(h * 0.075)), footer, font=ff, fill=th.muted)

    if total > 1:
        bar_h = max(6, h // 260)
        track_y = h - bar_h
        draw.rectangle((0, track_y, w, h), fill=th.bg2)
        progress = int(w * min(max(index, 0) + 1, total) / total)
        draw.rectangle((0, track_y, progress, h), fill=th.accent)

    return img


def _cover(img: Image.Image, dims: tuple[int, int]) -> Image.Image:
    """Scale-and-crop an image to fill ``dims`` without distortion."""
    w, h = dims
    ratio = max(w / img.width, h / img.height)
    resized = img.resize((max(w, int(img.width * ratio)), max(h, int(img.height * ratio))), Image.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def render_quote_card(
    text: str,
    *,
    attribution: str = "",
    theme: str = "midnight",
    size: str = "square",
    footer: str = "",
) -> Image.Image:
    """A static feed graphic — same visual language as the video slides."""
    return render_slide(
        f"“{text.strip().strip('“”')}”",
        theme=theme,
        size=size,
        emphasis=attribution,
        footer=footer,
    )


def save_slides(images: Iterable[Image.Image], out_dir: str | Path, stem: str = "slide") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, img in enumerate(images):
        p = out / f"{stem}-{i:02d}.png"
        img.save(p, "PNG")
        paths.append(p)
    return paths
