# marketing/studio · Plantillas de video (MK4)

Plantillas de marca en [Remotion](https://www.remotion.dev/) que convierten un archivo de **pieza** (JSON) en
los archivos listos para publicar en TikTok, Instagram, YouTube Shorts y WhatsApp. Las usa el agente productor
(MK6) y cualquiera que quiera montar una pieza a mano. Plan en
[`docs/marketing/11`](../../docs/marketing/11-hoja-de-ruta.md) (paso MK4); marca en [`../brand/visual.md`](../brand/visual.md).

## Uso

```bash
pnpm install
pnpm studio                                   # vista previa interactiva de todas las plantillas
pnpm render data/ejemplos/prueba-01-kuu-cuota.json   # → out/PRUEBA-01/
pnpm test && pnpm typecheck
pnpm smoke                                    # render mínimo de las 3 familias (lo corre CI)
```

Requiere Node 22 y pnpm 10. Si Remotion no puede descargar su Chrome, apunta `REMOTION_BROWSER_EXECUTABLE` a
uno local.

## Plantillas

| Plantilla | Tipo | Para qué | Formato |
| --- | --- | --- | --- |
| `Subtitulos` | Video | El caballo de batalla: un fondo (clip de Kuu, escena IA o color) con gancho, subtítulos y textos en pantalla | 1080×1920 |
| `Dato` | Video | Cifras grandes una tras otra (0 %, $0, $30, 3 meses) sobre verde o noche | 1080×1920 |
| `Cierre` | Video | Cierre de marca de 1,2 s («kuulis.» + CTA); `Subtitulos` y `Dato` lo añaden solos | 1080×1920 |
| `Carrusel` | Imágenes | 2 a 10 láminas (`foto`, `verde` o `noche`) | 1080×1350 en Instagram, 1080×1920 en TikTok |
| `Portada` | Imagen | Miniatura del video, con el titular dentro de la franja 4:5 central | 1080×1920 |

Todos los textos respetan la zona segura de [`../brand/visual.md`](../brand/visual.md) (arriba 150, abajo 420,
izquierda 60, derecha 180 px) para que la interfaz de cada red no los tape.

## Archivo de pieza

Un JSON por pieza; `codigo` nombra la carpeta de salida y luego el registro (MK5). El esquema completo está en
[`src/schema.ts`](src/schema.ts) y hay ejemplos en [`data/ejemplos/`](data/ejemplos/).

```json
{
  "codigo": "PRUEBA-01",
  "salidas": [
    {
      "plantilla": "Subtitulos",
      "redes": ["tiktok", "instagram", "youtube", "whatsapp"],
      "props": {
        "fondo": { "tipo": "video", "src": "https://…/kuu-cuota.mp4" },
        "gancho": { "texto": "Soy una IA y vengo a hablarte de plata." },
        "subtitulos": [{ "desdeS": 0, "hastaS": 2.4, "texto": "Soy una IA… y vengo a hablarte de plata." }],
        "textos": [{ "desdeS": 6, "hastaS": 10, "texto": "$150 → -20 % = -$30", "destacado": "-$30" }],
        "duracionS": 25
      }
    },
    { "plantilla": "Portada", "redes": ["tiktok"], "props": { "fondo": { "tipo": "color", "color": "verde" }, "titulo": "¿Cuánto te quita la app?" } }
  ]
}
```

- `fondo.src` acepta una ruta dentro de `public/` o una URL (por ejemplo, un enlace firmado de S3).
- Si no hay `subtitulos` con tiempos, `voz` se corta sola en frases de hasta 4 palabras repartidas en el video.
  Con tiempos reales (de la transcripción) quedan mejor.
- En los titulares (gancho, `titulo` de lámina y portada) un `\n` fuerza el salto de línea; si no, el corte se
  equilibra solo.
- `destacado` pinta en amarillo esa parte del texto. Las cifras siempre deben salir de
  [`../brand/hechos.md`](../brand/hechos.md).

## Qué produce

En `out/<codigo>/`: un archivo por red y `manifest.json` con la lista (red, plantilla, archivo, ancho, alto),
que MK5 usará para subir todo al bucket `kuulis-marketing`.

- TikTok, Reels y Shorts reciben el mismo master 1080×1920 h264 sin marcas de agua.
- WhatsApp recibe una copia 720×1280 y un aviso si pasa de 30 s (los estados se cortan ahí).
- Los carruseles salen en 4:5 para Instagram y a pantalla completa para TikTok; otras redes se omiten.

`out/` no va a git. Las fuentes (Archivo Poster y Plus Jakarta Sans, licencia OFL) sí, en `public/fonts/` y
como dependencia.

## Pendiente para pasos siguientes
- Música y voz: se montan en el clip de fondo (Higgsfield o Buzzy) o se añaden en la red; la plantilla conserva
  el audio del video de fondo.
- Subida a S3 y registro de cada archivo: MK5.
