"""
Generate the built-in menu pictures (SVG illustrations) in static/cafes/stock/.

Cafés without their own photos can pick one of these in the dashboard. They're
plain static files, so they survive redeploys and need no image storage.

Run:  python tools/make_stock_images.py
"""

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "cafes" / "stock"

W, H = 600, 450


def svg(body, bg=("#f6e7d6", "#e9cfb3"), w=W, h=H, defs=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<defs>
  <radialGradient id="bg" cx="50%" cy="40%" r="75%">
    <stop offset="0" stop-color="{bg[0]}"/><stop offset="1" stop-color="{bg[1]}"/>
  </radialGradient>
  <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="10" dy="14" stdDeviation="12" flood-color="#3b2416" flood-opacity=".28"/>
  </filter>
  <filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="4" dy="6" stdDeviation="5" flood-color="#3b2416" flood-opacity=".25"/>
  </filter>
  {defs}
</defs>
<rect width="{w}" height="{h}" fill="url(#bg)"/>
{body}
</svg>
"""


def beans(n, seed, area=(0, 0, W, H), avoid=(W / 2, H / 2, 190), scale=1.0):
    rnd = random.Random(seed)
    out = []
    placed = 0
    while placed < n:
        x, y = rnd.uniform(area[0] + 20, area[2] - 20), rnd.uniform(area[1] + 20, area[3] - 20)
        if math.hypot(x - avoid[0], y - avoid[1]) < avoid[2]:
            continue
        a = rnd.uniform(0, 180)
        s = scale * rnd.uniform(0.8, 1.15)
        out.append(
            f'<g transform="translate({x:.0f} {y:.0f}) rotate({a:.0f}) scale({s:.2f})" filter="url(#soft)">'
            '<ellipse rx="13" ry="18" fill="#4a2a17"/>'
            '<path d="M0 -15 C-5 -5 5 5 0 15" stroke="#2a160b" stroke-width="2.5" fill="none"/></g>'
        )
        placed += 1
    return "\n".join(out)


def cup_top(cx, cy, r, liquid, art="", cup="#fbf8f4", saucer="#efe7de", handle=True, spoon=False):
    """A cup seen from above, sitting on a saucer."""
    parts = [f'<g filter="url(#shadow)"><circle cx="{cx}" cy="{cy}" r="{r * 1.55:.0f}" fill="{saucer}"/>']
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 1.2:.0f}" fill="none" stroke="#e2d7cb" stroke-width="2"/></g>')
    if spoon:
        sx = cx - r * 0.35
        parts.append(
            f'<g transform="rotate(35 {cx} {cy})" filter="url(#soft)">'
            f'<rect x="{sx:.0f}" y="{cy + r * 0.9:.0f}" width="{r * 0.16:.0f}" height="{r * 0.95:.0f}" rx="5" fill="#cfc6bb"/>'
            f'<ellipse cx="{sx + r * 0.08:.0f}" cy="{cy + r * 0.95:.0f}" rx="{r * 0.17:.0f}" ry="{r * 0.25:.0f}" fill="#d9d1c7"/></g>'
        )
    if handle:
        parts.append(
            f'<rect x="{cx + r * 0.85:.0f}" y="{cy - r * 0.17:.0f}" width="{r * 0.62:.0f}" height="{r * 0.34:.0f}" '
            f'rx="{r * 0.17:.0f}" fill="{cup}" filter="url(#soft)"/>'
        )
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{cup}" filter="url(#soft)"/>')
    parts.append(
        f'<radialGradient id="liq{cx}{cy}" cx="45%" cy="40%" r="60%"><stop offset="0" stop-color="{liquid[0]}"/>'
        f'<stop offset="1" stop-color="{liquid[1]}"/></radialGradient>'
    )
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 0.84:.0f}" fill="url(#liq{cx}{cy})"/>')
    parts.append(art)
    return "\n".join(parts)


def heart(cx, cy, s, colour="#fbf3e6"):
    return (
        f'<path transform="translate({cx} {cy}) scale({s})" fill="{colour}" opacity=".95" '
        'd="M0 30 C-55 -5 -40 -45 -12 -38 C-4 -36 0 -28 0 -22 C0 -28 4 -36 12 -38 C40 -45 55 -5 0 30Z"/>'
        f'<path transform="translate({cx} {cy}) scale({s})" stroke="{colour}" stroke-width="3" d="M0 30 L0 52"/>'
    )


def rosetta(cx, cy, s, colour="#fbf3e6"):
    leaves = []
    for i in range(6):
        y = -40 + i * 13
        w = 42 - i * 6
        leaves.append(f'<path d="M{-w} {y} Q0 {y - 16} {w} {y} Q0 {y + 9} {-w} {y}Z" fill="{colour}" opacity=".93"/>')
    return (
        f'<g transform="translate({cx} {cy}) scale({s})">'
        + "".join(leaves)
        + f'<path d="M0 -55 L0 42" stroke="{colour}" stroke-width="3"/>'
        + f'<circle cx="0" cy="-50" r="8" fill="{colour}"/></g>'
    )


def dusting(cx, cy, r, seed, colour="#6b3a1f", n=90):
    rnd = random.Random(seed)
    dots = []
    for _ in range(n):
        a, d = rnd.uniform(0, 2 * math.pi), r * math.sqrt(rnd.random())
        dots.append(
            f'<circle cx="{cx + d * math.cos(a):.1f}" cy="{cy + d * math.sin(a):.1f}" r="{rnd.uniform(1, 2.6):.1f}"/>'
        )
    return f'<g fill="{colour}" opacity=".55">{"".join(dots)}</g>'


# --- Drinks ---------------------------------------------------------------


def espresso():
    cx, cy, r = 300, 225, 78
    crema = (
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.62:.0f}" fill="#b86a35" opacity=".55"/>'
        f'<circle cx="{cx - 8}" cy="{cy - 8}" r="{r * 0.3:.0f}" fill="#d48c4f" opacity=".5"/>'
    )
    return svg(beans(14, 1) + cup_top(cx, cy, r, ("#a65a28", "#5a2b10"), crema, spoon=True))


def cappuccino():
    cx, cy, r = 300, 225, 110
    art = dusting(cx, cy, r * 0.8, 2) + heart(cx, cy - 8, 1.25)
    return svg(beans(10, 2) + cup_top(cx, cy, r, ("#f0dcc1", "#c99665"), art))


def latte():
    cx, cy, r = 300, 225, 115
    return svg(
        beans(9, 3) + cup_top(cx, cy, r, ("#d6a66f", "#9b5f2e"), rosetta(cx, cy, 1.35)), bg=("#f3e9df", "#dcc4ab")
    )


def chai():
    cx, cy, r = 285, 230, 105
    stick = (
        '<g transform="rotate(-25 500 340)" filter="url(#soft)">'
        '<rect x="430" y="330" width="150" height="20" rx="9" fill="#8b4a22"/>'
        '<rect x="430" y="336" width="150" height="5" fill="#6d3618"/></g>'
    )
    star = "".join(
        f'<ellipse cx="{105 + 22 * math.cos(math.radians(a)):.0f}" cy="{105 + 22 * math.sin(math.radians(a)):.0f}" '
        f'rx="14" ry="7" transform="rotate({a} {105 + 22 * math.cos(math.radians(a)):.0f} '
        f'{105 + 22 * math.sin(math.radians(a)):.0f})" fill="#5b2e14"/>'
        for a in range(0, 360, 45)
    )
    star = f'<g filter="url(#soft)">{star}<circle cx="105" cy="105" r="8" fill="#3f1f0c"/></g>'
    swirl = (
        f'<path d="M{cx - 40} {cy} a40 40 0 1 1 80 0 a25 25 0 1 1 -50 0" stroke="#e8c79c" stroke-width="5" '
        'fill="none" opacity=".7"/>'
    )
    return svg(
        stick + star + cup_top(cx, cy, r, ("#d39a5e", "#9a5a28"), swirl, cup="#f4ede4"), bg=("#f7e6d2", "#e3c39d")
    )


def hot_chocolate():
    cx, cy, r = 300, 225, 110
    rnd = random.Random(5)
    mallows = []
    for _ in range(9):
        a, d = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, r * 0.55)
        x, y = cx + d * math.cos(a), cy + d * math.sin(a)
        mallows.append(
            f'<rect x="{x - 13:.0f}" y="{y - 13:.0f}" width="26" height="26" rx="8" fill="#fff8f2" '
            f'transform="rotate({rnd.uniform(0, 90):.0f} {x:.0f} {y:.0f})" filter="url(#soft)"/>'
        )
    art = dusting(cx, cy, r * 0.75, 6, colour="#2a1206", n=60) + "".join(mallows)
    return svg(beans(8, 6) + cup_top(cx, cy, r, ("#7a4126", "#3d1d0e"), art, cup="#c94f3d"), bg=("#f6e2d6", "#e3bfa8"))


def glass(liquid_stops, extras="", straw="#e05a47", ice=True, garnish=""):
    """A tall glass seen from the side."""
    x0, x1, top, bottom = 225, 375, 85, 395
    inset = 18
    path = f"M{x0} {top} L{x1} {top} L{x1 - inset} {bottom} L{x0 + inset} {bottom}Z"
    stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in liquid_stops)
    parts = [
        f'<linearGradient id="drink" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient>',
        f'<rect x="{x0 + 10}" y="{bottom - 6}" width="{x1 - x0 - 20}" height="16" rx="8" fill="#3b2416" opacity=".18"/>',
        f'<g transform="rotate(12 300 {top})"><rect x="318" y="30" width="14" height="250" rx="7" fill="{straw}"/>'
        f'<rect x="321" y="30" width="4" height="250" fill="#fff" opacity=".35"/></g>',
        f'<path d="M{x0 + 4} {top + 40} L{x1 - 4} {top + 40} L{x1 - inset - 2} {bottom - 4} '
        f'L{x0 + inset + 2} {bottom - 4}Z" fill="url(#drink)"/>',
    ]
    if ice:
        for _i, (x, y, a) in enumerate([(255, 140, 12), (300, 128, -8), (330, 165, 20), (270, 185, -15)]):
            parts.append(
                f'<rect x="{x}" y="{y}" width="40" height="40" rx="7" fill="#ffffff" opacity=".45" '
                f'stroke="#ffffff" stroke-opacity=".7" transform="rotate({a} {x + 20} {y + 20})"/>'
            )
    parts.append(extras)
    parts.append(
        f'<path d="{path}" fill="#ffffff" fill-opacity=".12" stroke="#ffffff" stroke-opacity=".85" stroke-width="4"/>'
    )
    parts.append(
        f'<path d="M{x0 + 14} {top + 20} L{x0 + 28} {bottom - 30}" stroke="#fff" stroke-opacity=".6" stroke-width="6" stroke-linecap="round"/>'
    )
    parts.append(garnish)
    return "\n".join(parts)


def iced_latte():
    body = glass([(0, "#e9d6bf"), (0.35, "#c58d58"), (0.7, "#8d5128"), (1, "#5d3014")])
    return svg(beans(10, 7, avoid=(300, 240, 200)) + f'<g filter="url(#shadow)">{body}</g>', bg=("#eef0f2", "#cfd8de"))


def passion_juice():
    seeds = "".join(
        f'<circle cx="{x}" cy="{y}" r="4" fill="#3a2a10" opacity=".8"/>'
        for x, y in [(262, 220), (290, 260), (330, 235), (310, 300), (275, 330), (340, 340), (300, 200), (250, 280)]
    )
    fruit = (
        '<g filter="url(#soft)" transform="translate(452 352)"><circle r="62" fill="#5b2a5e"/>'
        '<circle r="52" fill="#f2b51f"/><circle r="40" fill="#f6c94a"/>'
        + "".join(
            f'<circle cx="{30 * math.cos(a):.0f}" cy="{30 * math.sin(a):.0f}" r="5" fill="#3a2a10"/>'
            for a in [i * 0.9 for i in range(7)]
        )
        + "</g>"
    )
    body = glass([(0, "#ffd45a"), (0.6, "#f8a91f"), (1, "#e9841a")], extras=seeds, straw="#5b2a5e", ice=True)
    return svg(f'<g filter="url(#shadow)">{body}</g>' + fruit, bg=("#fff3dc", "#f4d7a6"))


# --- Food -----------------------------------------------------------------


def plate(cx, cy, r, fill="#fbf8f4"):
    return (
        f'<g filter="url(#shadow)"><circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/></g>'
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.78:.0f}" fill="none" stroke="#ebe3d9" stroke-width="3"/>'
    )


def croissant():
    segs = []
    for _i, (a, s) in enumerate([(-62, 0.62), (-36, 0.82), (-12, 0.97), (12, 0.97), (36, 0.82), (62, 0.62)]):
        x = 300 + 150 * math.sin(math.radians(a))
        y = 255 - 70 * math.cos(math.radians(a)) + 30
        segs.append(
            f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{48 * s:.0f}" ry="{70 * s:.0f}" '
            f'transform="rotate({a} {x:.0f} {y:.0f})" fill="url(#crust)" stroke="#a0581f" stroke-width="2"/>'
        )
    order = [segs[0], segs[5], segs[1], segs[4], segs[2], segs[3]]
    defs = (
        '<radialGradient id="crust" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#f6c06a"/>'
        '<stop offset=".6" stop-color="#d98b33"/><stop offset="1" stop-color="#a65a1c"/></radialGradient>'
    )
    return svg(plate(300, 235, 185) + f'<g filter="url(#soft)">{"".join(order)}</g>', defs=defs)


def banana_bread():
    walnuts = "".join(
        f'<ellipse cx="{x}" cy="{y}" rx="9" ry="6" fill="#c9a06a" transform="rotate({a} {x} {y})"/>'
        for x, y, a in [
            (260, 200, 20),
            (330, 230, -30),
            (290, 270, 60),
            (350, 290, 10),
            (240, 300, -10),
            (310, 180, 45),
        ]
    )
    crumbs = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#9a5d2b"/>'
        for x, y, r in [(470, 330, 4), (455, 350, 3), (140, 150, 3)]
    )
    slice_ = (
        '<g filter="url(#soft)"><path d="M200 150 Q300 110 400 150 L410 330 Q300 350 190 330Z" fill="#7a4220"/>'
        '<path d="M212 162 Q300 128 388 162 L396 318 Q300 336 204 318Z" fill="#c7884a"/></g>'
    )
    return svg(plate(300, 240, 190) + slice_ + walnuts + crumbs)


def mandazi():
    tris = []
    for x, y, a in [(240, 210, -10), (360, 215, 15), (300, 300, 185)]:
        tris.append(
            f'<g transform="translate({x} {y}) rotate({a})" filter="url(#soft)">'
            '<path d="M0 -62 Q8 -62 60 34 Q62 44 52 44 L-52 44 Q-62 44 -60 34 Q-8 -62 0 -62Z" fill="url(#fried)" '
            'stroke="#9a5418" stroke-width="2"/></g>'
        )
    sugar = dusting(300, 245, 120, 9, colour="#ffffff", n=70)
    defs = (
        '<radialGradient id="fried" cx="45%" cy="40%" r="70%"><stop offset="0" stop-color="#f3c27b"/>'
        '<stop offset="1" stop-color="#c47a2c"/></radialGradient>'
    )
    return svg(plate(300, 240, 190) + "".join(tris) + sugar, defs=defs)


def full_breakfast():
    def egg(x, y):
        return (
            f'<g filter="url(#soft)"><path d="M{x - 48} {y} q-6 -40 30 -46 q30 -12 52 10 q30 18 10 46 q-20 30 -56 22 q-36 -2 -36 -32Z" '
            f'fill="#fffdf8"/><circle cx="{x + 4}" cy="{y - 6}" r="19" fill="#f6b21b"/>'
            f'<circle cx="{x - 2}" cy="{y - 12}" r="6" fill="#fde08a"/></g>'
        )

    sausages = "".join(
        f'<rect x="{x}" y="{y}" width="110" height="30" rx="15" fill="#8b3e1f" transform="rotate({a} {x + 55} {y + 15})" filter="url(#soft)"/>'
        f'<rect x="{x + 10}" y="{y + 6}" width="80" height="6" rx="3" fill="#b5653a" transform="rotate({a} {x + 55} {y + 15})"/>'
        for x, y, a in [(330, 255, -18), (325, 295, -12)]
    )
    toast = (
        '<g transform="rotate(-12 205 300)" filter="url(#soft)"><rect x="150" y="250" width="110" height="100" rx="14" fill="#a8642c"/>'
        '<rect x="160" y="260" width="90" height="80" rx="10" fill="#e3ab62"/></g>'
    )
    rnd = random.Random(11)
    bean_dots = "".join(
        f'<ellipse cx="{360 + rnd.uniform(-35, 35):.0f}" cy="{175 + rnd.uniform(-22, 22):.0f}" rx="8" ry="6" fill="#d9541e"/>'
        for _ in range(26)
    )
    beans_ = f'<ellipse cx="360" cy="175" rx="50" ry="34" fill="#c94416" filter="url(#soft)"/>{bean_dots}'
    tomato = (
        '<g filter="url(#soft)"><circle cx="250" cy="170" r="30" fill="#d93a2b"/><circle cx="250" cy="170" r="20" fill="#ef6a4a"/>'
        '<circle cx="243" cy="164" r="3" fill="#ffd27a"/><circle cx="257" cy="174" r="3" fill="#ffd27a"/></g>'
    )
    return svg(plate(300, 240, 200) + toast + beans_ + tomato + egg(240, 245) + sausages)


def avocado_toast():
    rnd = random.Random(12)
    flakes = "".join(
        f'<circle cx="{300 + rnd.uniform(-85, 85):.0f}" cy="{235 + rnd.uniform(-65, 65):.0f}" r="{rnd.uniform(1.5, 3):.1f}" fill="#c3271b"/>'
        for _ in range(45)
    )
    mash = "".join(
        f'<circle cx="{300 + rnd.uniform(-80, 80):.0f}" cy="{235 + rnd.uniform(-60, 60):.0f}" r="{rnd.uniform(16, 30):.0f}" '
        f'fill="{rnd.choice(["#9cc15a", "#a9cc66", "#8bb34a", "#b6d47a"])}"/>'
        for _ in range(26)
    )
    toast = (
        '<g filter="url(#soft)"><path d="M180 140 Q180 110 215 112 Q240 92 300 95 Q360 92 385 112 Q420 110 420 140 L420 345 Q420 365 400 365 L200 365 Q180 365 180 345Z" fill="#9e5a24"/>'
        '<path d="M196 150 Q196 126 222 128 Q245 110 300 113 Q355 110 378 128 Q404 126 404 150 L404 338 Q404 350 392 350 L208 350 Q196 350 196 338Z" fill="#dca45c"/></g>'
    )
    return svg(
        plate(300, 240, 205) + toast + f'<g clip-path="url(#tc)">{mash}</g>' + flakes,
        defs='<clipPath id="tc"><rect x="205" y="140" width="190" height="200" rx="16"/></clipPath>',
    )


# --- Cover ----------------------------------------------------------------


def cover():
    w, h = 1600, 700
    body = [
        '<rect width="1600" height="700" fill="url(#wood)"/>',
        beans(40, 21, area=(0, 0, w, h), avoid=(800, 350, 0), scale=1.4),
    ]
    body.append(
        cup_top(420, 330, 120, ("#d6a66f", "#9b5f2e"), rosetta(420, 330, 1.4))
        + cup_top(1180, 360, 105, ("#f0dcc1", "#c99665"), dusting(1180, 360, 85, 22) + heart(1180, 352, 1.2))
        + cup_top(
            820, 160, 70, ("#a65a28", "#5a2b10"), '<circle cx="820" cy="160" r="40" fill="#b86a35" opacity=".5"/>'
        )
    )
    defs = (
        '<linearGradient id="wood" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5a3420"/>'
        '<stop offset=".5" stop-color="#3f2416"/><stop offset="1" stop-color="#2b170d"/></linearGradient>'
    )
    return svg("\n".join(body), w=w, h=h, defs=defs)


STOCK = {
    "espresso": espresso,
    "cappuccino": cappuccino,
    "latte": latte,
    "chai": chai,
    "hot-chocolate": hot_chocolate,
    "iced-latte": iced_latte,
    "juice": passion_juice,
    "croissant": croissant,
    "banana-bread": banana_bread,
    "mandazi": mandazi,
    "breakfast": full_breakfast,
    "avocado-toast": avocado_toast,
    "cover": cover,
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in STOCK.items():
        (OUT / f"{name}.svg").write_text(fn())
        print("wrote", name)
