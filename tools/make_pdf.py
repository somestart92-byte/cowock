"""Render the Screen-Free Summer Vault as a visual, printable PDF (WeasyPrint).

Dark branded cover + clean printer-friendly interior pages with green accents,
activity cards, "what's printable" boxes, and takeaway callouts. Black + emerald
brand palette, faceless (no people imagery). Contains the FULL 120+ activities
so the marketing claim is accurate (counts sum to 129).
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
            "Nature scavenger hunt — find something rough, something that flies, a yellow flower, a heart-shaped rock.",
            "Driveway chalk obstacle course — hop, spin, tip-toe along the chalk path.",
            "Giant chalk tic-tac-toe — draw a grid, use rocks as markers.",
            "Shadow tracing — trace your shadow at morning, noon, and evening; compare.",
            "Sponge toss relay — soak sponges, race to fill a cup across the yard.",
            "Fence “painting” — a bucket of water + a big brush = mess-free art.",
            "Ice-cube rescue — freeze small toys, free them with warm water.",
            "Backyard Olympics — long jump, bean-bag toss, balloon keep-up, medals.",
            "Bug explorer log — find, draw, and count the bugs you spot.",
            "Mud kitchen — old pots + dirt + water = an hour of “cooking.”",
            "Kindness rocks — paint smooth rocks and hide them for neighbors.",
            "Bubble station — mix dish soap + water; try giant-bubble wands.",
            "Household obstacle course — hula hoop, broom hurdle, pillow leap.",
            "Plant-a-cup garden — seeds in a cup, water daily, watch it grow.",
            "Cloud-watching journal — draw the shapes you see in the sky.",
            "Water-balloon target toss — chalk a target, aim and splash.",
            "Nature mandala — arrange leaves, petals, and stones in circles.",
            "Sprinkler dance / hose limbo — music optional, giggles guaranteed.",
            "Sandbox treasure dig — bury coins or toys to excavate.",
            "Backyard campout — build a fort, grab a flashlight, tell stories.",
        ],
        "printable": "Scavenger hunt cards, chalk challenge poster, Olympics scorecard, bug log.",
        "takeaway": "Outdoor + a printed “mission” = 45 minutes of independent play.",
    },
    {
        "n": 2, "title": "Rainy-Day Quiet Time", "count": 18,
        "blurb": "For the indoor days when you still need a calm house.",
        "items": [
            "Quiet-time box checklist — sticker books, lacing cards, busy bags.",
            "Build-a-fort cards — cushion castle, blanket cave, reading nook.",
            "Calm-corner breathing poster — smell the flower, blow the candle.",
            "Indoor treasure hunt — clue cards you fill with your own hiding spots.",
            "Paper airplane squadron — fold, decorate, race for distance.",
            "Origami boats — fold and float them in the sink or tub.",
            "Fortune tellers — the classic folded paper game.",
            "Sticker-by-number pages — match stickers to numbered spots.",
            "Lacing cards — thread yarn around punched shapes.",
            "Pom-pom color sort — tongs + a muffin tin = fine-motor fun.",
            "Sock matching race — dump clean socks, beat the timer.",
            "Indoor bowling — plastic cups + a soft ball.",
            "Reading nook challenge — cozy up and finish five books.",
            "Puzzle race — beat your own best time.",
            "Drawing-prompt jar — pull a slip, draw what it says.",
            "Shadow puppets — a flashlight and a blank wall.",
            "Toy “museum” — set up favorites and make little labels.",
            "Animal yoga cards — be a cat, a flamingo, a sleepy bear.",
        ],
        "printable": "Quiet-time checklist, breathing poster, treasure-hunt clues, drawing prompts, yoga cards.",
        "takeaway": "A printed “quiet-time menu” turns rainy days from chaos to calm.",
    },
    {
        "n": 3, "title": "Road-Trip & Travel Pack", "count": 16,
        "blurb": "Tested for car, plane, and waiting rooms.",
        "items": [
            "License-plate bingo — spot plates and mark your card.",
            "Spot-it bingo — cow, red car, bridge, water tower.",
            "“Are we there yet?” countdown strip — color a box every 15 minutes.",
            "Travel journal pages — draw what you saw, rate the snacks.",
            "Would-you-rather cards — 50 silly travel prompts.",
            "Window I-Spy checklist — tick off what you find.",
            "Alphabet hunt — find A–Z on signs in order.",
            "Story-building game — each person adds one line.",
            "Color hunt checklist — find all the rainbow colors outside.",
            "Sticker scene page — build a picture with reusable stickers.",
            "Map-the-trip coloring page — mark your route.",
            "Snack rating scorecard — give stars to each snack.",
            "20 questions cards — guess the animal/object.",
            "Audiobook listening log — draw your favorite part.",
            "Dot-to-dot travel pack — connect to reveal the picture.",
            "“Quiet mouse” challenge — who can stay calm the longest?",
        ],
        "printable": "Bingo cards, countdown strip, travel journal, WYR cards, I-Spy list.",
        "takeaway": "One laminated bingo card = a quiet back seat for miles.",
    },
    {
        "n": 4, "title": "Sensory & Life-Skills Activities", "count": 15,
        "blurb": "Play that secretly teaches. Great for toddlers and littles.",
        "items": [
            "Rice sensory bin — scoop, pour, hide and find small toys.",
            "Pasta scoop-and-pour bin — cups, spoons, funnels.",
            "Water-bead bin — themed by color (supervise closely).",
            "Pour-and-transfer station — move water between cups.",
            "Sort-by-color tray — buttons, pom-poms, or blocks.",
            "Practical-life cards — pour, sort, button, zip, fold a napkin.",
            "Play-dough “count the spots” mat.",
            "Play-dough “feed the monster” mat.",
            "Color hunt — find 5 things of each color around the house.",
            "Shape hunt — circles, squares, triangles indoors.",
            "Helper-of-the-day chart — match small chores to ages.",
            "Texture treasure bag — guess each object by feel.",
            "Tweezers pom-pom transfer — into an ice tray.",
            "Pasta-necklace threading — patterns by color.",
            "Sticky-wall art — contact paper + torn paper shapes.",
        ],
        "printable": "Sensory-bin recipe cards, play-dough mats, helper chart, practical-life cards.",
        "takeaway": "Sensory play buys you focused, independent time — and builds real skills.",
    },
    {
        "n": 5, "title": "Kids' Kitchen (no-cook + easy)", "count": 12,
        "blurb": "Confidence-building food fun with minimal mess.",
        "items": [
            "Fruit kebabs — thread soft fruit onto straws.",
            "Yogurt parfaits — layer yogurt, fruit, and cereal.",
            "Ants-on-a-log — celery, nut/seed butter, raisins.",
            "Trail-mix bar — scoop and mix their own bag.",
            "No-bake energy balls — oats, banana, honey; roll and chill.",
            "Rainbow veggie + dip plate — arrange by color.",
            "Chef checklist — wash hands, gather, measure, clean up.",
            "Taste-test scorecard — rate new fruits and veggies.",
            "Set-the-table placemat — where the fork and cup go.",
            "Smoothie “recipe roulette” — pick a fruit from each column.",
            "Sandwich shape cutouts — use cookie cutters.",
            "Frozen banana pops — dip and freeze.",
        ],
        "printable": "Recipe cards, chef checklist, taste-test scorecard, placemat.",
        "takeaway": "Picture recipe cards let kids “cook” while you sip your coffee.",
    },
    {
        "n": 6, "title": "Screen-Free Reward System", "count": 10,
        "blurb": "Make the screen-free habit stick — gently, without nagging.",
        "items": [
            "Screen-free hour tracker — color a square for each hour.",
            "Daily streak calendar — build a chain of screen-free days.",
            "“Boredom = brilliant” idea-jar slips — cut, fold, pull one out.",
            "Reward coupon — one extra bedtime story.",
            "Reward coupon — stay up 15 minutes later.",
            "Reward coupon — pick tonight's dinner.",
            "Reward coupon — choose a special outing.",
            "Summer bucket-list poster — fill it in together.",
            "“I did it myself” sticker chart — celebrate independence.",
            "Family screen-free pledge page — everyone signs.",
        ],
        "printable": "Tracker, streak calendar, idea-jar slips, coupons, bucket-list poster, pledge.",
        "takeaway": "Track the wins, not the screen time — kids chase the colored squares.",
    },
    {
        "n": 7, "title": "Weekly Summer Rhythm Planner", "count": 8,
        "blurb": "A light, intentional structure — flexible, not a rigid schedule.",
        "items": [
            "Weekly rhythm page — morning / afternoon / evening blocks.",
            "Daily anchor card — “one outing, one rest, one create.”",
            "Meal & snack jotter — plan the week's food at a glance.",
            "Sunday reset checklist — restock, tidy, plan ahead.",
            "Morning routine cards — get dressed, brush, breakfast.",
            "Bedtime routine cards — bath, books, lights out.",
            "Weekly chore wheel — spin or assign by age.",
            "“Today I'm grateful for” line — one small gratitude a day.",
        ],
        "printable": "Weekly rhythm page, daily anchor card, meal jotter, routine cards, chore wheel.",
        "takeaway": "A loose rhythm beats a strict schedule — and beats “what do we do today?”",
    },
    {
        "n": 8, "title": "Boredom-Buster Master Deck", "count": 30, "compact": True,
        "blurb": "30 grab-one-and-go cards that pull from every pack — plus blanks to add your own.",
        "items": [
            "Build a blanket fort", "Draw your dream treehouse", "Make a paper-airplane fleet",
            "Have an indoor picnic", "Go on a bug hunt", "Create an obstacle course",
            "Put on a puppet show", "Invent a secret handshake", "Write a letter to grandma",
            "Build the tallest block tower", "Sort toys by color", "Make a comic strip",
            "Play “the floor is lava”", "Hide a treasure for a sibling", "Make a magazine collage",
            "Press some flowers", "Have a one-song dance party", "Build a marble run",
            "Make a pretend restaurant menu", "Do a 5-minute clean-up race", "Invent a brand-new game",
            "Paint a kindness rock", "Start a nature journal", "Build a fort for stuffed animals",
            "Write your name in fancy letters", "Make a paper crown", "Set up a pretend post office",
            "Do three animal yoga poses", "List what you love about summer", "Pick a card for someone else",
        ],
        "printable": "Full 30-card deck + blank cards + a “pick a number 1–30” poster.",
        "takeaway": "When all else fails, “pick a card” ends the boredom debate in seconds.",
    },
]

TOTAL = sum(p["count"] for p in PACKS)  # 129

CSS = """
@page { size: Letter; margin: 0; }
@page content {
  margin: 52px 52px 64px 52px;
  @bottom-center { content: "CAROTECH  ·  Screen-Free Summer Vault  ·  beacons.ai/carotech36";
    font-family: 'Liberation Sans', sans-serif; font-size: 8.5pt; color: #9bbfa9; }
  @bottom-right { content: counter(page); font-family: 'Liberation Sans', sans-serif;
    font-size: 8.5pt; color: #2e7d4f; }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Liberation Sans', 'DejaVu Sans', sans-serif; color: #1c2b22; }
h1,h2,h3 { font-family: 'Liberation Serif', 'DejaVu Serif', serif; }

.cover { page: cover; height: 100vh;
  background: radial-gradient(1200px 700px at 80% -10%, #14241b 0%, #060807 55%), #060807;
  color: #f4f7f4; padding: 90px 70px; position: relative; }
.cover .kick { color:#2ECC71; letter-spacing:3px; font-weight:bold; font-size:13pt; }
.cover h1 { font-size: 52pt; line-height:1.05; margin: 18px 0 10px; }
.cover .sub { color:#c9d8cf; font-size:15pt; max-width: 80%; line-height:1.4; }
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

.content { page: content; }
.toc h2 { font-size:26pt; color:#13351f; margin-bottom:4px;}
.toc .lead { color:#5b6f63; margin-top:0; }
.toc ol { list-style:none; padding:0; margin-top:18px; }
.toc li { display:flex; align-items:center; padding:10px 0; border-bottom:1px solid #e3efe8; font-size:12.5pt;}
.toc .num { width:30px; height:30px; border:2px solid #2ECC71; color:#1f8a4c; border-radius:50%;
  display:inline-flex; align-items:center; justify-content:center; font-weight:bold; margin-right:14px;
  font-family:'Liberation Serif',serif;}
.toc .cnt { margin-left:auto; color:#2e7d4f; font-weight:bold; font-size:10.5pt; }

.pack { page-break-before: always; }
.pack-head { background: linear-gradient(100deg,#0c1f15,#13351f); color:#fff;
  border-radius:14px; padding:20px 22px; display:flex; align-items:center; }
.pack-head .pn { width:52px; height:52px; min-width:52px; background:#2ECC71; color:#06210f;
  border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:23pt;
  font-weight:bold; font-family:'Liberation Serif',serif; margin-right:18px;}
.pack-head .pt { font-size:18pt; margin:0; line-height:1.1;}
.pack-head .pc { color:#a9e8c4; font-size:10pt; font-weight:bold; letter-spacing:1px; }
.blurb { color:#5b6f63; font-style:italic; margin:14px 2px 8px; font-size:11.5pt;}

.card { background:#f4faf6; border:1px solid #dcefe3; border-left:5px solid #2ECC71;
  border-radius:9px; padding:7px 14px; margin:5px 0; font-size:10.5pt; line-height:1.3;}
.card b { color:#13351f; }
.box, .take { page-break-inside: avoid; }

.grid { display:grid; grid-template-columns:1fr 1fr; gap:7px 14px; margin-top:6px; }
.gitem { background:#f4faf6; border:1px solid #dcefe3; border-left:4px solid #2ECC71;
  border-radius:8px; padding:7px 10px; font-size:10.5pt; }
.gitem .gn { color:#1f8a4c; font-weight:bold; margin-right:6px; }

.box { margin-top:14px; background:#ffffff; border:1.5px dashed #2ECC71; border-radius:10px;
  padding:11px 15px; font-size:11pt;}
.box .lab { color:#1f8a4c; font-weight:bold; letter-spacing:1px; font-size:9.5pt; display:block; margin-bottom:3px;}
.take { margin-top:12px; background:#eafaf0; border-radius:10px; padding:12px 15px; font-size:11.5pt; color:#0f3d23;}
.take .lab { color:#1f8a4c; font-weight:bold; }

.closing { page-break-before: always; text-align:center; padding-top:80px; }
.closing h2 { font-size:30pt; color:#13351f; }
.closing p { color:#5b6f63; max-width:80%; margin:14px auto; font-size:12pt; line-height:1.5;}
.disc { margin-top:36px; font-size:9pt; color:#9aa8a0; max-width:82%; margin-left:auto; margin-right:auto;}
"""


def card_html(text: str) -> str:
    if " — " in text:
        head, rest = text.split(" — ", 1)
        return f'<div class="card"><b>{head}</b> — {rest}</div>'
    return f'<div class="card">{text}</div>'


def pack_body(p: dict) -> str:
    if p.get("compact"):
        cells = "".join(
            f'<div class="gitem"><span class="gn">{i}.</span>{t}</div>'
            for i, t in enumerate(p["items"], 1)
        )
        return f'<div class="grid">{cells}</div>'
    return "".join(card_html(i) for i in p["items"])


def build_html() -> str:
    toc = "".join(
        f'<li><span class="num">{p["n"]}</span>{p["title"]}'
        f'<span class="cnt">{p["count"]} activities</span></li>'
        for p in PACKS
    )
    packs = ""
    for p in PACKS:
        packs += f"""
        <section class="pack">
          <div class="pack-head">
            <div class="pn">{p['n']}</div>
            <div><div class="pc">PACK {p['n']} · {p['count']} ACTIVITIES</div>
            <h2 class="pt">{p['title']}</h2></div>
          </div>
          <p class="blurb">{p['blurb']}</p>
          {pack_body(p)}
          <div class="box"><span class="lab">WHAT'S PRINTABLE</span>{p['printable']}</div>
          <div class="take"><span class="lab">Quick win:</span> {p['takeaway']}</div>
        </section>"""

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
    <div class="cover">
      <div class="corner c-tl"></div><div class="corner c-tr"></div>
      <div class="kick">SCREEN-FREE SUMMER</div>
      <h1>The Screen-Free<br>Summer Vault</h1>
      <div class="rule"></div>
      <div class="sub">{TOTAL} boredom-busting activities to keep kids happy, busy &amp; off
        screens — all summer long. Print at home. Grab one when boredom hits.</div>
      <div class="badges">
        <span class="badge">8 printable packs</span>
        <span class="badge">{TOTAL} activities</span>
        <span class="badge">Zero prep</span>
      </div>
      <div class="foot"><span class="brand">CAROTECH</span><span>beacons.ai/carotech36</span></div>
    </div>

    <div class="content">
      <section class="toc">
        <h2>What's inside</h2>
        <p class="lead">{TOTAL} activities across 8 packs. Print what you want, pop it in a binder, pull one out whenever you need it.</p>
        <ol>{toc}</ol>
        <div class="box" style="margin-top:22px;"><span class="lab">HOW TO USE THIS VAULT</span>
          1) Print the packs you like (all printer-friendly).&nbsp; 2) Slip them in a binder or laminate the reusable ones.&nbsp;
          3) When boredom hits, let your child pick a page. Done.</div>
      </section>
      {packs}
      <section class="closing">
        <h2>You're doing a good job. 💛</h2>
        <p>This vault is meant to make your summer lighter, not to add pressure. Use one page
        or all {TOTAL} — there's no “right” way, and a screen day here and there doesn't undo anything.</p>
        <p style="color:#1f8a4c;font-weight:bold;">Loved it? The full CaroTech library lives at beacons.ai/carotech36</p>
        <div class="disc">This is a general activity resource for families; it is not medical, educational,
        or developmental advice. Adapt activities to your child's age and always supervise water,
        kitchen, and craft play.</div>
      </section>
    </div>
    </body></html>"""


def build_markdown() -> str:
    """Generate product.md from the SAME data as the PDF (single source of truth)."""
    lines = [
        "# The Screen-Free Summer Activity Vault",
        f"### {TOTAL} Boredom-Busting Activities to Keep Kids Happy, Busy & Off "
        "Screens — All Summer Long",
        "",
        "*A faceless CaroTech printable bundle. Print at home, grab-and-go, zero prep.*",
        "",
        "**Suggested price:** $27 (bundle of 8 printable packs)",
        "",
        "---",
        "",
        "## Welcome, Mama 💛",
        "",
        f"The Screen-Free Summer Vault is a done-for-you stack of **8 printable packs "
        f"and {TOTAL} activities** so you always have something ready that doesn't "
        "involve a tablet. Print the pages you want, pop them in a binder, and pull "
        "one out whenever you need it.",
        "",
    ]
    for p in PACKS:
        lines.append(f"## Pack {p['n']} — {p['title']} ({p['count']} activities)")
        lines.append("")
        lines.append(f"*{p['blurb']}*")
        lines.append("")
        for i, item in enumerate(p["items"], 1):
            lines.append(f"{i}. {item}")
        lines.append("")
        lines.append(f"**What's printable:** {p['printable']}")
        lines.append("")
        lines.append(f"> **Quick win:** {p['takeaway']}")
        lines.append("")
    lines += [
        "---",
        "",
        "## You're doing a good job. 💛",
        "",
        f"Use one page or all {TOTAL} — there's no “right” way, and a screen day here "
        "and there doesn't undo anything. The full CaroTech library lives at "
        "beacons.ai/carotech36.",
        "",
        "*This is a general activity resource for families; it is not medical, "
        "educational, or developmental advice. Adapt activities to your child's age "
        "and always supervise water, kitchen, and craft play.*",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    out = OUT / "Screen-Free-Summer-Vault.pdf"
    HTML(string=build_html()).write_pdf(str(out))
    (OUT / "product.md").write_text(build_markdown(), encoding="utf-8")
    print(f"saved {out} + product.md  ({TOTAL} activities)")
