"""Builds every Kuulis logo SVG from geometry (concept «K punto»).

The symbol is a lowercase k whose leg is the brand's yellow full stop: «kuulis.» and «y punto» in one letter.
The wordmark is Plus Jakarta Sans ExtraBold (SIL OFL) converted to outlines, like the web's live-text wordmark.

    pip install fonttools
    python build_logo.py <font.ttf> <out-dir>
"""
import math
import os
import sys

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT, OUT = sys.argv[1], sys.argv[2]
SVG_DIR = os.path.join(OUT, 'svg')
os.makedirs(SVG_DIR, exist_ok=True)

GREEN, YELLOW, INK, NIGHT, WHITE = '#0E7C5A', '#FFC83D', '#14201B', '#07120E', '#FFFFFF'

font = TTFont(FONT)
glyphs, cmap = font.getGlyphSet(), font.getBestCmap()


def bounds(ch):
    pen = BoundsPen(glyphs)
    glyphs[cmap[ord(ch)]].draw(pen)
    return pen.bounds


ASC = bounds('l')[3]  # 757: top of k, l, i
UNDER = -bounds('u')[1]  # 12: overshoot of round letters below the baseline
XH = bounds('u')[3]  # 546: x-height (flat tops of u)


# --- Symbol geometry (256 grid; baseline y=224, ascender y=32, stem 48 units) ---------------------------------
def symbol_shapes(inset=0.0, small=False):
    """Returns (k path, dot circle) in 256 units. inset thins the reversed version (irradiation)."""
    if small:
        # Cut for 16–32 px: heavier stem and arm, bigger dot, wider gap. Shifted -10 to centre.
        x0, x1, top, base, c1, w, r, cx = 30, 90, 28, 228, 202, 60, 38, 188
    else:
        x0, x1, top, base, c1, w, r, cx = 48, 96, 32, 224, 216, 48, 31, 174
    c2 = c1 + w * math.sqrt(2)  # arm's lower edge: x + y = c2 (45°)
    arm_top = base - (base - top) * XH / ASC  # arm ends exactly at the wordmark's x-height
    i, d = inset, inset * math.sqrt(2)
    k = (f'M{x0 + i:.2f} {top + i:.2f}H{x1 - i:.2f}V{base - i:.2f}H{x0 + i:.2f}Z'
         f'M{x1 - i:.2f} {c1 - x1 + d + i:.2f}L{c1 - arm_top + d:.2f} {arm_top + i:.2f}'
         f'H{c2 - arm_top - d:.2f}L{x1 - i:.2f} {c2 - x1 - d + i:.2f}Z')
    cy = base - r + 1  # 1 unit overshoot below the baseline: round forms look short otherwise
    return k, (cx, cy, r - inset)


def symbol_body(k_color, dot_color, inset=0.0, small=False):
    k, (cx, cy, r) = symbol_shapes(inset, small)
    return (f'<path fill="{k_color}" d="{k}"/>'
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{dot_color}"/>')


def symbol_bbox(small=False):
    k, (cx, cy, r) = symbol_shapes(small=small)
    return (30 if small else 48), (28 if small else 32), cx + r, cy + r


# --- Wordmark ------------------------------------------------------------------------------------------------
def wordmark_paths(size, x, baseline, track=-0.03):
    """«kuulis» as one outline path plus the full stop as a circle (the font's period is square; the brand dot is
    always round, like the symbol's). Returns (letters, (cx, cy, r), right edge)."""
    s = size / font['head'].unitsPerEm
    letters = ''
    for ch in 'kuulis':
        pen = SVGPathPen(glyphs)
        glyphs[cmap[ord(ch)]].draw(TransformPen(pen, (s, 0, 0, -s, x, baseline)))
        letters += pen.getCommands()
        last_x = x
        x += glyphs[cmap[ord(ch)]].width * s + track * size
    r = 84 * s  # a touch wider than the 150-unit square period, so the circle carries the same weight
    cx = last_x + (bounds('s')[2] + 60) * s + r  # 60 units after the ink of the «s»
    cy = baseline + 6 * s - r  # overshoots the baseline like the round letters
    return letters, (cx, cy, r), cx + r


def wordmark_body(text_color, dot_color, size, x, baseline):
    letters, (cx, cy, r), right = wordmark_paths(size, x, baseline)
    return (f'<path fill="{text_color}" d="{letters}"/>'
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{dot_color}"/>'), right


def write(name, body, vb, title='Kuulis'):
    x, y, w, h = vb
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:.2f} {y:.2f} {w:.2f} {h:.2f}" '
           f'width="{w:.0f}" height="{h:.0f}" role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')
    with open(os.path.join(SVG_DIR, name), 'w') as f:
        f.write(svg)


# Colour treatments: (symbol k, symbol dot, wordmark letters, wordmark dot, inset)
TREATMENTS = {
    '': (GREEN, YELLOW, INK, YELLOW, 0),  # on white and light backgrounds
    '-negativo': (WHITE, YELLOW, WHITE, YELLOW, 0.75),  # on night, ink, green and photos
    '-negro': ('#000000', '#000000', '#000000', '#000000', 0),
    '-blanco': (WHITE, WHITE, WHITE, WHITE, 0.75),
    '-verde': (GREEN, GREEN, GREEN, GREEN, 0),
}

# Symbol: full 256 canvas (optically centred: equal side margins)
for suffix, (kc, dc, _, _, inset) in TREATMENTS.items():
    write(f'kuulis-simbolo{suffix}.svg', f'<g transform="translate(1.5 0)">{symbol_body(kc, dc, inset)}</g>',
          (0, 0, 256, 256), 'Kuulis')
# Small-size cut (favicons, 16–32 px)
write('kuulis-simbolo-pequeno.svg', symbol_body(GREEN, YELLOW, small=True), (0, 0, 256, 256))
write('kuulis-simbolo-pequeno-negativo.svg', symbol_body(WHITE, YELLOW, 0.75, small=True), (0, 0, 256, 256))

# Horizontal lockup: symbol stem = height of «l»; arm top = x-height; gap = 1.25 × stem.
SIZE = 192 * 1000 / ASC  # font size whose ascender is 192 units
LETTER_X = 205 + 60  # symbol right edge (dot) + gap
for suffix, (kc, dc, tc, wdc, inset) in TREATMENTS.items():
    wm, right = wordmark_body(tc, wdc, SIZE, LETTER_X - bounds('k')[0] * SIZE / 1000, 224)
    write(f'kuulis-horizontal{suffix}.svg', symbol_body(kc, dc, inset) + wm, (48, 32, right - 48, 192 + UNDER * SIZE / 1000))

# Stacked lockup: symbol 1.6× the wordmark's ascender, centred; gap = one dot diameter.
SCALE = 1.6
sym_w = (205 - 48) * SCALE
for suffix, (kc, dc, tc, wdc, inset) in TREATMENTS.items():
    _, _, right0 = wordmark_paths(SIZE, 0, 0)
    left0 = bounds('k')[0] * SIZE / 1000
    word_w = right0 - left0
    width = max(word_w, sym_w)
    sym_x = (width - sym_w) / 2 - 48 * SCALE
    base = 193 * SCALE + 62 * SCALE + 192
    wm, _ = wordmark_body(tc, wdc, SIZE, (width - word_w) / 2 - left0, base)
    sym = f'<g transform="translate({sym_x:.2f} {-32 * SCALE:.2f}) scale({SCALE})">{symbol_body(kc, dc, inset)}</g>'
    write(f'kuulis-vertical{suffix}.svg', sym + wm, (0, 0, width, base + UNDER * SIZE / 1000))

# Wordmark only
for suffix, (_, _, tc, wdc, _) in TREATMENTS.items():
    left0 = bounds('k')[0] * SIZE / 1000
    wm, right = wordmark_body(tc, wdc, SIZE, -left0, 192)
    write(f'kuulis-logotipo{suffix}.svg', wm, (0, 0, right, 192 + UNDER * SIZE / 1000))

# App icons: tile with the reversed symbol (large) and the small cut (favicon)
TILE = 'translate(40 40) scale(0.6875)'
for name, bg in (('kuulis-icono-app.svg', GREEN), ('kuulis-icono-app-noche.svg', NIGHT)):
    write(name, f'<rect width="256" height="256" rx="56" fill="{bg}"/>'
                f'<g transform="{TILE} translate(1.5 0)">{symbol_body(WHITE, YELLOW, 0.75)}</g>', (0, 0, 256, 256))
write('kuulis-favicon.svg', f'<rect width="256" height="256" rx="56" fill="{GREEN}"/>'
                            f'<g transform="translate(26 26) scale(0.797)">{symbol_body(WHITE, YELLOW, 0.75, True)}</g>',
      (0, 0, 256, 256))
print('ok')
