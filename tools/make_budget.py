"""Render 'The No-Guilt Budget Planner for Moms' as a printable PDF + product.md.

Dark branded cover + WHITE printer-friendly interior form pages with emerald-green
headers/accents. Halal: no riba/interest/credit promotion. Truthful: no income
claims. US English, faceless.
"""

from __future__ import annotations
from pathlib import Path
from weasyprint import HTML

OUT = Path(__file__).resolve().parents[1] / "products/output/carotech-no-guilt-budget-planner"
OUT.mkdir(parents=True, exist_ok=True)

PRICE = 17

# Each page: (title, kicker, intro, body-html). Body uses helper builders below.
def rows(n, cols):
    """A table with header cols + n blank rows."""
    head = "".join(f"<th>{c}</th>" for c in cols)
    blank = "<tr>" + "".join("<td>&nbsp;</td>" for _ in cols) + "</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{blank*n}</tbody></table>"

def lines(n, label=""):
    one = f'<div class="line"><span>{label}</span></div>'
    return "".join(one for _ in range(n))

def boxes(items):
    return "".join(f'<div class="chk"><span class="box"></span>{t}</div>' for t in items)


PAGES = [
    ("Monthly Budget Overview", "START HERE",
     "Three numbers tell the whole story: what comes in, what must go out, and what's left.",
     f"""<div class="grid3">
        <div class="stat"><div class="lbl">Income this month</div><div class="big">$________</div></div>
        <div class="stat"><div class="lbl">Fixed costs</div><div class="big">$________</div></div>
        <div class="stat"><div class="lbl">Left to assign</div><div class="big">$________</div></div>
       </div>
       <h3>Where it goes</h3>
       {rows(8, ["Category", "Planned", "Actual"])}"""),

    ("Bill & Due-Date Tracker", "NEVER MISS ONE",
     "List every bill and check it off when it's paid. Calm beats late fees.",
     rows(12, ["Bill", "Due date", "Amount", "Paid ✔"])),

    ("Weekly Spending Log", "SEE IT CLEARLY",
     "Jot every spend for one week. Awareness changes habits faster than willpower.",
     rows(14, ["Date", "What", "Category", "Amount"])),

    ("Savings Goals", "ONE STEP AT A TIME",
     "Name the goal, set the target, color in your progress.",
     f"""{rows(5, ["Goal", "Target $", "Saved so far $", "By when"])}
        <h3>Progress</h3>
        <p class="muted">Color one block per milestone:</p>
        <div class="track">{''.join('<span></span>' for _ in range(10))}</div>"""),

    ("Guilt-Free Money", "YOU'RE IN THE PLAN TOO",
     "A small amount that's just yours — no justifying. Being in your own budget isn't selfish.",
     f"""<div class="stat wide"><div class="lbl">My guilt-free amount this month</div><div class="big">$________</div></div>
        <h3>What I'd love to use it on</h3>
        {lines(6)}"""),

    ("No-Spend Challenge", "RESET YOUR HABITS",
     "Pick your days. Color a square for each no-spend day. Note what you did instead.",
     f"""<div class="track big-track">{''.join('<span></span>' for _ in range(31))}</div>
        <h3>Instead of spending, I…</h3>{lines(5)}"""),

    ("Grocery & Meal Budget", "THE BIGGEST FLEX COST",
     "Plan the week's meals and a grocery cap. Small wins here add up fast.",
     f"""<div class="stat wide"><div class="lbl">Weekly grocery cap</div><div class="big">$________</div></div>
        {rows(7, ["Day", "Meal plan", "Notes"])}"""),

    ("Sinking Funds", "NO MORE SURPRISES",
     "Save a little each month for the things you know are coming.",
     rows(9, ["Fund (birthdays, back-to-school, holidays…)", "Goal $", "Monthly set-aside $"])),

    ("Debt Pay-Off Tracker", "ONE BALANCE AT A TIME",
     "List what you owe and chip away. Smallest balance first for quick momentum.",
     rows(8, ["Owed to", "Balance $", "Payment $", "New balance $"])),

    ("Monthly Review", "CLOSE THE LOOP",
     "Be kind to yourself here. Progress, not perfection.",
     f"""<h3>This month I'm proud of…</h3>{lines(3)}
        <h3>Where money leaked…</h3>{lines(3)}
        <h3>One change for next month…</h3>{lines(2)}
        <div class="chkwrap">{boxes(['Bills paid on time','Hit my guilt-free money','Stayed under grocery cap','Added to savings'])}</div>"""),
]

CSS = """
@page { size: Letter; margin: 0; }
@page content { margin: 48px 52px 60px 52px;
  @bottom-center { content: "CAROTECH  ·  The No-Guilt Budget Planner  ·  beacons.ai/carotech36";
    font-family:'Liberation Sans',sans-serif; font-size:8pt; color:#9bbfa9; }
  @bottom-right { content: counter(page); font-family:'Liberation Sans',sans-serif; font-size:8pt; color:#2e7d4f; }
}
* { box-sizing:border-box; }
body { margin:0; font-family:'Liberation Sans','DejaVu Sans',sans-serif; color:#15231b; }
h1,h2,h3 { font-family:'Liberation Serif','DejaVu Serif',serif; }

/* Cover (dark) */
.cover { page: cover; height:100vh; background:
  radial-gradient(1200px 700px at 80% -10%, #14241b 0%, #060807 55%), #060807;
  color:#f4f7f4; padding:96px 70px; position:relative; }
.cover .kick { color:#2ECC71; letter-spacing:3px; font-weight:bold; font-size:13pt; }
.cover h1 { font-size:62pt; line-height:1.04; margin:18px 0 12px; }
.cover .sub { color:#c9d8cf; font-size:16pt; max-width:80%; }
.cover .rule { width:90px; height:5px; background:#2ECC71; margin:26px 0; }
.cover .pill { display:inline-block; background:#2ECC71; color:#06210f; font-weight:bold;
  font-family:'Liberation Serif',serif; font-size:30pt; padding:8px 26px; border-radius:40px; margin-top:24px;}
.cover .foot { position:absolute; bottom:70px; left:70px; right:70px; display:flex;
  justify-content:space-between; color:#7fae93; font-size:11pt; }
.cover .brand { color:#2ECC71; font-weight:bold; letter-spacing:2px; }
.corner { position:absolute; width:64px; height:64px; border-color:#2ECC71; border-style:solid; }
.c-tl{top:46px;left:46px;border-width:4px 0 0 4px;} .c-tr{top:46px;right:46px;border-width:4px 4px 0 0;}

/* Interior (white, printable) */
.content { page: content; page-break-before: always; }
.phead { border-left:7px solid #2ECC71; padding-left:16px; margin-bottom:8px; }
.phead .kick { color:#1f8a4c; font-weight:bold; letter-spacing:2px; font-size:10pt; }
.phead h2 { font-size:30pt; margin:2px 0 0; color:#10331f; }
.intro { color:#5b6f63; font-size:11.5pt; margin:6px 2px 18px; }
h3 { color:#10331f; font-size:14pt; margin:20px 0 8px; }
.muted { color:#7c8c83; font-size:10.5pt; margin:2px 0 6px; }
table { width:100%; border-collapse:collapse; }
th { background:#eafaf0; color:#10331f; font-size:11pt; text-align:left; padding:9px 10px; border:1px solid #cfe9da; }
td { padding:14px 10px; border:1px solid #dfeee7; }
.grid3 { display:flex; gap:16px; }
.stat { flex:1; border:2px solid #2ECC71; border-radius:12px; padding:16px; text-align:center; }
.stat.wide { max-width:340px; }
.stat .lbl { color:#1f8a4c; font-weight:bold; font-size:10.5pt; }
.stat .big { font-family:'Liberation Serif',serif; font-size:24pt; color:#10331f; margin-top:6px; }
.line { border-bottom:1.5px solid #cfe2d8; height:34px; margin:10px 0; }
.track { display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }
.track span { width:54px; height:40px; border:2px solid #2ECC71; border-radius:8px; display:inline-block; }
.big-track span { width:54px; height:44px; }
.chkwrap { margin-top:14px; }
.chk { font-size:12pt; margin:9px 0; color:#15231b; }
.chk .box { display:inline-block; width:22px; height:22px; border:2px solid #2ECC71; border-radius:5px;
  margin-right:12px; vertical-align:-5px; }
.closing { color:#5b6f63; font-size:9pt; margin-top:26px; }
"""

def build_html():
    cover = f"""<div class="cover">
      <div class="corner c-tl"></div><div class="corner c-tr"></div>
      <div class="kick">CAROTECH PRINTABLE</div>
      <h1>The No-Guilt<br>Budget Planner</h1>
      <div class="rule"></div>
      <div class="sub">A simple, kind way for moms to see their money clearly — and feel
      in control without the shame.</div>
      <div class="pill">${PRICE}</div>
      <div class="foot"><span class="brand">CAROTECH</span><span>beacons.ai/carotech36</span></div>
    </div>"""
    toc_items = "".join(f"<li>{t}</li>" for t,_,_,_ in PAGES)
    intro_pg = f"""<section class="content"><div class="phead"><div class="kick">HOW TO USE</div>
      <h2>Start with one page</h2></div>
      <p class="intro">You don't have to fill this all in today. Print what helps, start with
      the Monthly Budget Overview, and add a page when you're ready. Budgeting isn't about
      restriction — it's about knowing, so you can breathe easier.</p>
      <ol style="font-size:12pt;line-height:2;">{toc_items}</ol>
      <p class="closing">A general budgeting resource for moms — not financial advice.
      No interest, loans, or credit are promoted here; this is about your own money, plainly.</p>
    </section>"""
    pages = ""
    for title, kick, intro, body in PAGES:
        pages += f"""<section class="content">
          <div class="phead"><div class="kick">{kick}</div><h2>{title}</h2></div>
          <p class="intro">{intro}</p>{body}</section>"""
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{cover}{intro_pg}{pages}</body></html>"


def build_markdown():
    lines_md = [
        "# The No-Guilt Budget Planner for Moms",
        f"### A kind, simple way to see your money clearly — without the shame",
        "",
        "*A faceless CaroTech printable. Print at home, fill it in, breathe easier.*",
        "",
        f"**Suggested price:** ${PRICE}",
        "",
        "---", "",
        "## How to use",
        "Print what helps and start with the Monthly Budget Overview. Add a page when "
        "you're ready. This is about *knowing* your money, not restricting yourself.",
        "",
        "## What's inside",
    ]
    for i,(t,_,intro,_) in enumerate(PAGES,1):
        lines_md.append(f"{i}. **{t}** — {intro}")
    lines_md += [
        "",
        "*A general budgeting resource for moms — not financial advice. No interest, "
        "loans, or credit are promoted; this is about your own money, plainly. Personal "
        "use only.*", "",
    ]
    return "\n".join(lines_md)


if __name__ == "__main__":
    HTML(string=build_html()).write_pdf(str(OUT / "The-No-Guilt-Budget-Planner.pdf"))
    (OUT / "product.md").write_text(build_markdown(), encoding="utf-8")
    print(f"saved PDF + product.md ({len(PAGES)+2} pages)")
