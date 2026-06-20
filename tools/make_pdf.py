"""Render the Screen-Free Summer Vault as a visual, printable PDF (WeasyPrint).

Dark branded cover + back page, clean printer-friendly interior pages with
green accents, activity cards, "what's printable" boxes, and takeaway callouts.
Black + emerald-green brand palette, faceless (no people imagery).
"""

from __future__ import annotations

from pathlib import Path

from weasyprint import HTML

OUT = Path(__file__).resolve().parents[1] / "products/output/carotech-screen-free-summer-vault"

PACKS = [
    {
        "n": 1, "title": "Backyard & Outdoor Boredom-Busters", "count": 20,
        "blurb": "Print-and-go ideas that send them outside and burn energy.",
        "items": [
            "Nature scavenger hunt cards — find something rough, something that flies, a yellow flower, a heart-shaped rock.",
            "Driveway chalk challenge list — hopscotch maze, giant tic-tac-toe, trace your shadow at 3 times of day.",
            "Water-play stations — sponge toss, fence “painting” with a brush + bucket, ice-cube rescue.",
            "Backyard Olympics scorecard — long jump, balloon keep-up, bean-bag toss.",
            "Bug explorer log — draw and count the bugs you find.",
        ],
        "printable": "Scavenger hunt cards, chalk challenge poster, Olympics scorecard.",
        "takeaway": "Outdoor + a printed “mission” = 45 minutes of independent play.",
    },
    {
        "n": 2, "title": "Rainy-Day Quiet Time", "count": 18,
        "blurb": "For the indoor days when you still need a calm house.",
        "items": [
            "Quiet-time box checklist — sticker books, lacing cards, busy bags.",
            "Build-a-fort cards — cushion castle, blanket cave, reading nook.",
            "“Calm corner” breathing poster — smell the flower, blow the candle.",
            "Indoor treasure hunt clue cards (fill in your own hiding spots).",
            "Paper-only crafts — airplanes, fortune tellers, origami boats.",
        ],
        "printable": "Quiet-time checklist, breathing poster, treasure-hunt clue cards.",
        "takeaway": "A printed “quiet-time menu” turns rainy days from chaos to calm.",
    },
    {
        "n": 3, "title": "Road-Trip & Travel Pack", "count": 16,
        "blurb": "Tested for car, plane, and waiting rooms.",
        "items": [
            "License-plate & spot-it bingo (4 reusable cards).",
            "“Are we there yet?” countdown strip kids color in.",
            "Travel journal pages — draw what you saw, rate the snacks.",
            "Would-you-rather road-trip cards (50 prompts).",
            "Window I-Spy checklist.",
        ],
        "printable": "Bingo cards, countdown strip, travel journal, WYR cards.",
        "takeaway": "One laminated bingo card = a quiet back seat for miles.",
    },
    {
        "n": 4, "title": "Sensory & Life-Skills Activities", "count": 15,
        "blurb": "Play that secretly teaches. Great for toddlers and littles.",
        "items": [
            "Sensory-bin recipe cards — rice, pasta, water beads, themes by color.",
            "Practical-life task cards — pour, sort, button, fold a napkin.",
            "Play-dough mat printables (count the spots, feed the monster).",
            "Color & shape hunt around the house.",
            "“Helper of the day” chart — match small chores to ages.",
        ],
        "printable": "Sensory-bin cards, play-dough mats, helper chart.",
        "takeaway": "Sensory play buys you focused, independent time — and builds real skills.",
    },
    {
        "n": 5, "title": "Kids' Kitchen (no-cook + easy)", "count": 12,
        "blurb": "Confidence-building food fun with minimal mess.",
        "items": [
            "No-cook recipe cards — fruit kebabs, yogurt parfaits, ants-on-a-log, trail-mix bar.",
            "“Chef checklist” — wash hands, gather, measure, clean up.",
            "Taste-test scorecard — rate new fruits and veggies.",
            "Set-the-table placemat (where the fork goes).",
        ],
        "printable": "Recipe cards, chef checklist, taste-test scorecard, placemat.",
        "takeaway": "Picture recipe cards let kids “cook” while you sip your coffee.",
    },
    {
        "n": 6, "title": "Screen-Free Reward System", "count": 10,
        "blurb": "Make the screen-free habit stick — gently, without nagging.",
        "items": [
            "Screen-free tracker — color a square for each screen-free hour/day.",
            "“Boredom = brilliant” idea-jar slips (cut, fold, draw one).",
            "Reward coupons — extra story, stay-up-15-min, pick dinner (time & attention, not money).",
            "Summer bucket-list poster to fill in together.",
        ],
        "printable": "Tracker, idea-jar slips, coupons, bucket-list poster.",
        "takeaway": "Track the wins, not the screen time — kids chase the colored squares.",
    },
    {
        "n": 7, "title": "Weekly Summer Rhythm Planner", "count": 8,
        "blurb": "A light, intentional structure — flexible, not a rigid schedule.",
        "items": [
            "Weekly rhythm page — morning / afternoon / evening blocks.",
            "“One outing, one rest, one create” daily anchor.",
            "Meal & snack jotter.",
            "Sunday reset checklist.",
        ],
        "printable": "Weekly rhythm page, daily anchor card, meal jotter.",
        "takeaway": "A loose rhythm beats a strict schedule — and beats “what do we do today?”",
    },
    {
        "n": 8, "title": "Boredom-Buster Cards (Master Deck)", "count": 30,
        "blurb": "The grab-one-and-go deck that ties it all together.",
        "items": [
            "30+ mix-and-match activity cards drawing from every pack.",
            "Blank cards to add your family's own favorites.",
            "“Pick a number 1–30” poster for decision-free days.",
        ],
        "printable": "Full card deck + blanks + number poster.",
        "takeaway": "When all else fails, “pick a card” ends the boredom debate in seconds.",
    },
]

CSS = """
@page { size: Letter; margin: 0; }
@page content {
  margin: 56px 56px 70px 56px;
  @bottom-center {
    content: "CAROTECH  ·  Screen-Free Summer Vault  ·  beacons.ai/carotech36";
    font-family: 'Liberation Sans', sans-serif; font-size: 8.5pt; color: #9bbfa9;
  }
  @bottom-right { content: counter(page); font-family: 'Liberation Sans', sans-serif;
    font-size: 8.5pt; color: #2e7d4f; }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Liberation Sans', 'DejaVu Sans', sans-serif; color: #1c2b22; }
h1,h2,h3 { font-family: 'Liberation Serif', 'DejaVu Serif', serif; }

/* ---- Cover ---- */
.cover { page: cover; height: 100vh; background:
  radial-gradient(1200px 700px at 80% -10%, #14241b 0%, #060807 55%) , #060807;
  color: #f4f7f4; padding: 90px 70px; position: relative; }
.cover .kick { color:#2ECC71; letter-spacing:3px; font-weight:bold; font-size:13pt; }
.cover h1 { font-size: 52pt; line-height:1.05; margin: 18px 0 10px; }
.cover .sub { color:#c9d8cf; font-size:15pt; max-width: 78%; line-height:1.4; }
.cover .badges { margin-top: 40px; }
.cover .badge { display:inline-block; border:2px solid #2ECC71; color:#2ECC71;
  border-radius: 40px; padding: 8px 18px; font-weight:bold; font-size:12pt; margin-right:10px;}
.cover .rule { width:90px; height:5px; background:#2ECC71; margin: 26px 0; }
.cover .foot { position:absolute; bottom:70px; left:70px; right:70px;
  display:flex; justify-content:space-between; color:#7fae93; font-size:11pt; }
.cover .brand { color:#2ECC71; font-weight:bold; letter-spacing:2px; }
.corner { position:absolute; width:64px; height:64px; border-color:#2ECC71; border-style:solid; }
.c-tl { top:46px; left:46px; border-width:4px 0 0 4px; }
.c-tr { top:46px; right:46px; border-width:4px 4px 0 0; }

/* ---- Interior ---- */
.content { page: content; }
.toc h2 { font-size:26pt; color:#13351f; margin-bottom:4px;}
.toc .lead { color:#5b6f63; margin-top:0; }
.toc ol { list-style:none; padding:0; margin-top:18px; }
.toc li { display:flex; align-items:center; padding:11px 0; border-bottom:1px solid #e3efe8; font-size:12.5pt;}
.toc .num { width:30px; height:30px; border:2px solid #2ECC71; color:#1f8a4c; border-radius:50%;
  display:inline-flex; align-items:center; justify-content:center; font-weight:bold; margin-right:14px;
  font-family:'Liberation Serif',serif;}
.toc .cnt { margin-left:auto; color:#2e7d4f; font-weight:bold; font-size:10.5pt; }

.pack { page-break-before: always; }
.pack-head { background: linear-gradient(100deg,#0c1f15,#13351f); color:#fff;
  border-radius:14px; padding:22px 24px; display:flex; align-items:center; }
.pack-head .pn { width:54px; height:54px; min-width:54px; background:#2ECC71; color:#06210f;
  border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:24pt;
  font-weight:bold; font-family:'Liberation Serif',serif; margin-right:18px;}
.pack-head .pt { font-size:19pt; margin:0; line-height:1.1;}
.pack-head .pc { color:#a9e8c4; font-size:10pt; font-weight:bold; letter-spacing:1px; }
.blurb { color:#5b6f63; font-style:italic; margin:16px 2px 10px; font-size:11.5pt;}

.card { background:#f4faf6; border:1px solid #dcefe3; border-left:5px solid #2ECC71;
  border-radius:10px; padding:12px 16px; margin:9px 0; font-size:11.5pt; line-height:1.4;}
.card b { color:#13351f; }

.box { margin-top:16px; background:#ffffff; border:1.5px dashed #2ECC71; border-radius:10px;
  padding:12px 16px; font-size:11pt;}
.box .lab { color:#1f8a4c; font-weight:bold; letter-spacing:1px; font-size:9.5pt; display:block; margin-bottom:3px;}
.take { margin-top:14px; background:#eafaf0; border-radius:10px; padding:13px 16px; font-size:11.5pt;
  color:#0f3d23;}
.take .lab { color:#1f8a4c; font-weight:bold; }

/* ---- Closing ---- */
.closing { page-break-before: always; text-align:center; padding-top:90px; }
.closing h2 { font-size:30pt; color:#13351f; }
.closing p { color:#5b6f63; max-width:80%; margin:14px auto; font-size:12pt; line-height:1.5;}
.disc { margin-top:40px; font-size:9pt; color:#9aa8a0; max-width:82%; margin-left:auto; margin-right:auto;}
"""


def card_html(text: str) -> str:
    if " — " in text:
        head, rest = text.split(" — ", 1)
        return f'<div class="card"><b>{head}</b> — {rest}</div>'
    return f'<div class="card">{text}</div>'


def build_html() -> str:
    toc = "".join(
        f'<li><span class="num">{p["n"]}</span>{p["title"]}'
        f'<span class="cnt">{p["count"]} activities</span></li>'
        for p in PACKS
    )
    packs = ""
    for p in PACKS:
        cards = "".join(card_html(i) for i in p["items"])
        packs += f"""
        <section class="pack">
          <div class="pack-head">
            <div class="pn">{p['n']}</div>
            <div><div class="pc">PACK {p['n']} · {p['count']} ACTIVITIES</div>
            <h2 class="pt">{p['title']}</h2></div>
          </div>
          <p class="blurb">{p['blurb']}</p>
          {cards}
          <div class="box"><span class="lab">WHAT'S PRINTABLE</span>{p['printable']}</div>
          <div class="take"><span class="lab">Quick win:</span> {p['takeaway']}</div>
        </section>"""

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
    <div class="cover">
      <div class="corner c-tl"></div><div class="corner c-tr"></div>
      <div class="kick">SCREEN-FREE SUMMER</div>
      <h1>The Screen-Free<br>Summer Vault</h1>
      <div class="rule"></div>
      <div class="sub">120+ boredom-busting activities to keep kids happy, busy &amp; off
        screens — all summer long. Print at home. Grab one when boredom hits.</div>
      <div class="badges">
        <span class="badge">8 printable packs</span>
        <span class="badge">120+ activities</span>
        <span class="badge">Zero prep</span>
      </div>
      <div class="foot"><span class="brand">CAROTECH</span><span>beacons.ai/carotech36</span></div>
    </div>

    <div class="content">
      <section class="toc">
        <h2>What's inside</h2>
        <p class="lead">Print the packs you want, pop them in a binder, and pull one out whenever you need it.</p>
        <ol>{toc}</ol>
        <div class="box" style="margin-top:26px;"><span class="lab">HOW TO USE THIS VAULT</span>
          1) Print the packs you like (all printer-friendly).&nbsp; 2) Slip them in a binder or laminate the reusable ones.&nbsp;
          3) When boredom hits, let your child pick a page. Done.</div>
      </section>
      {packs}
      <section class="closing">
        <h2>You're doing a good job. 💛</h2>
        <p>This vault is meant to make your summer lighter, not to add pressure. Use one page
        or all 120 — there's no “right” way, and a screen day here and there doesn't undo anything.</p>
        <p style="color:#1f8a4c;font-weight:bold;">Loved it? The full CaroTech library lives at beacons.ai/carotech36</p>
        <div class="disc">This is a general activity resource for families; it is not medical, educational,
        or developmental advice. Adapt activities to your child's age and always supervise water,
        kitchen, and craft play.</div>
      </section>
    </div>
    </body></html>"""


if __name__ == "__main__":
    out = OUT / "Screen-Free-Summer-Vault.pdf"
    HTML(string=build_html()).write_pdf(str(out))
    print("saved", out)
