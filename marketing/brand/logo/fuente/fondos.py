"""Renders the logo on the brand's backgrounds into one HTML board (light and dark).

    python fondos.py <kit-dir> <out.html>
"""
import os, sys
D = sys.argv[1]
def svg(n): return open(os.path.join(D, 'svg', n)).read()
cells = [
    ('Blanco', '#FFFFFF', 'kuulis-horizontal.svg', 'kuulis-simbolo.svg', '#14201B'),
    ('Fondo app claro #F3F7F4', '#F3F7F4', 'kuulis-horizontal.svg', 'kuulis-simbolo.svg', '#14201B'),
    ('Noche #07120E', '#07120E', 'kuulis-horizontal-negativo.svg', 'kuulis-simbolo-negativo.svg', '#E7EFEB'),
    ('Fondo app oscuro #0B1310', '#0B1310', 'kuulis-horizontal-negativo.svg', 'kuulis-simbolo-negativo.svg', '#E7EFEB'),
    ('Tinta #14201B', '#14201B', 'kuulis-horizontal-negativo.svg', 'kuulis-simbolo-negativo.svg', '#E7EFEB'),
    ('Verde Kuulis #0E7C5A', '#0E7C5A', 'kuulis-horizontal-negativo.svg', 'kuulis-simbolo-negativo.svg', '#FFFFFF'),
    ('Verde profundo #0A5C43', '#0A5C43', 'kuulis-horizontal-negativo.svg', 'kuulis-simbolo-negativo.svg', '#FFFFFF'),
    ('Foto (noche en Caracas)', 'linear-gradient(135deg,#1d2b33,#3b2a1a 55%,#0b1310)', 'kuulis-horizontal-negativo.svg', 'kuulis-simbolo-negativo.svg', '#FFFFFF'),
]
html = ['<!doctype html><meta charset="utf-8"><title>Kuulis sobre fondos</title><style>body{margin:0;font:14px system-ui;background:#fff;color:#14201B}'
        'h1{font-size:22px;margin:24px 32px 8px}.g{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px 32px 32px}'
        '.c{border-radius:16px;padding:28px 32px;display:flex;align-items:center;gap:40px;min-height:150px;position:relative}'
        '.c .h svg{height:64px;width:auto;display:block}.c .s svg{height:72px;width:72px;display:block}'
        '.c .t{position:absolute;left:16px;bottom:10px;font-size:12px;opacity:.75}'
        '.icons{display:flex;gap:28px;align-items:end;padding:8px 32px 40px}.icons svg{display:block}.icons div{text-align:center;font-size:12px}</style>'
        '<h1>Kuulis · K punto sobre fondos claros y oscuros</h1><div class="g">']
for label, bg, h, s, fg in cells:
    html.append(f'<div class="c" style="background:{bg}"><div class="h">{svg(h)}</div><div class="s">{svg(s)}</div><div class="t" style="color:{fg}">{label}</div></div>')
html.append('</div><h1>Íconos de app (tema claro y oscuro)</h1><div class="icons">')
for n, lab in (('kuulis-icono-app.svg', 'Verde'), ('kuulis-icono-app-noche.svg', 'Noche')):
    for px in (120, 60, 32):
        html.append(f'<div>{svg(n).replace("<svg ", f"<svg style=\"width:{px}px;height:{px}px\" ")}{lab} {px}</div>')
html.append(f'<div>{svg("kuulis-favicon.svg").replace("<svg ", "<svg style=\"width:16px;height:16px\" ")}favicon 16</div></div>')
open(sys.argv[2], 'w').write(''.join(html))
