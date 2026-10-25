"""Renders the raster deliverables (PNG set, web icons, Expo/Android icons) from the SVGs of build_logo.py.

    python export_assets.py <kit-dir> <logo-design scripts dir>

Needs the logo-design skill's render_png.py and export_variants.py (Chrome or any SVG renderer).
"""
import os
import re
import shutil
import subprocess
import sys

KIT, SCRIPTS = sys.argv[1], sys.argv[2]
SVG = os.path.join(KIT, 'svg')
GREEN = '#0E7C5A'
TMP = os.path.join(KIT, '.tmp')
os.makedirs(TMP, exist_ok=True)


def run(*args):
    subprocess.run([sys.executable, *args], check=True, stdout=subprocess.DEVNULL)


def render(svg, out, w, h=None):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    run(os.path.join(SCRIPTS, 'render_png.py'), svg, '-o', out, '--width', str(w), '--height', str(h or w))


def inner(name):
    """The drawing of an SVG in the kit, without its <svg>/<title> wrapper."""
    body = open(os.path.join(SVG, name)).read()
    return re.sub(r'^<svg[^>]*>(<title>[^<]*</title>)?|</svg>\s*$', '', body)


def canvas(name, size, body, bg=None):
    path = os.path.join(TMP, name)
    rect = f'<rect width="{size}" height="{size}" fill="{bg}"/>' if bg else ''
    with open(path, 'w') as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">{rect}{body}</svg>')
    return path


def mark(name, size, fraction, dy=0.0):
    """Places a 256-unit symbol so its 256 canvas covers `fraction` of a size×size canvas, centred."""
    s = size * fraction / 256
    off = (size - 256 * s) / 2
    return f'<g transform="translate({off:.2f} {off + dy * size:.2f}) scale({s:.4f})">{inner(name)}</g>'


# 1) PNG of every SVG variant (transparent), for documents and decks.
for name in sorted(os.listdir(SVG)):
    if name.endswith('.svg'):
        wide = name.startswith(('kuulis-horizontal', 'kuulis-logotipo'))
        out = os.path.join(KIT, 'png', name[:-4] + '.png')
        if wide:
            vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', open(os.path.join(SVG, name)).read()).group(1).split()]
            render(os.path.join(SVG, name), out, 2000, round(2000 * vb[3] / vb[2]))
        elif name.startswith('kuulis-vertical'):
            render(os.path.join(SVG, name), out, 1200)
        else:
            render(os.path.join(SVG, name), out, 1024)

# 2) Web: tile favicon (visible on light and dark tabs) + PWA icons from export_variants.py.
web = os.path.join(KIT, 'web')
run(os.path.join(SCRIPTS, 'export_variants.py'), os.path.join(SVG, 'kuulis-simbolo-negativo.svg'), '--out-dir', TMP,
    '--name', 'kuulis', '--title', 'Kuulis', '--icon-bg', GREEN, '--icon-fg', 'keep',
    '--favicon-source', os.path.join(SVG, 'kuulis-simbolo-pequeno-negativo.svg'), '--web-icons')
os.makedirs(web, exist_ok=True)
for f in ('apple-touch-icon.png', 'icon-192.png', 'icon-512.png', 'maskable-512.png', 'site.webmanifest',
          'head-snippet.html'):
    shutil.copy(os.path.join(TMP, f), os.path.join(web, f))
shutil.copy(os.path.join(SVG, 'kuulis-favicon.svg'), os.path.join(web, 'favicon.svg'))
for px in (16, 32, 48):
    render(os.path.join(SVG, 'kuulis-favicon.svg'), os.path.join(web, f'favicon-{px}.png'), px)
run(os.path.join(SCRIPTS, 'render_png.py'), os.path.join(SVG, 'kuulis-favicon.svg'), '--ico',
    os.path.join(web, 'favicon.ico'), '--ico-sizes', '16', '32', '48')

# 3) Expo / Android: same file names and sizes as mobile/assets (drop-in replacements).
app = os.path.join(KIT, 'app')
render(canvas('icon.svg', 1024, mark('kuulis-simbolo-negativo.svg', 1024, 0.72), GREEN), os.path.join(app, 'icon.png'), 1024)
# Adaptive icon: the launcher masks a 108 dp layer to ~72 dp and keeps a 66 dp safe zone; the mark stays inside it.
render(canvas('fg.svg', 512, mark('kuulis-simbolo-negativo.svg', 512, 0.56)), os.path.join(app, 'android-icon-foreground.png'), 512)
render(canvas('bg.svg', 512, '', GREEN), os.path.join(app, 'android-icon-background.png'), 512)
render(canvas('mono.svg', 432, mark('kuulis-simbolo-blanco.svg', 432, 0.56)), os.path.join(app, 'android-icon-monochrome.png'), 432)
render(canvas('splash.svg', 1024, mark('kuulis-simbolo-negativo.svg', 1024, 1.0)), os.path.join(app, 'splash-icon.png'), 1024)
render(os.path.join(SVG, 'kuulis-favicon.svg'), os.path.join(app, 'favicon.png'), 48)

shutil.rmtree(TMP)
print('ok')
