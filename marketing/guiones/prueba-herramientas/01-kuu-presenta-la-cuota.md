---
codigo: PRUEBA-01
titulo: Kuu se presenta y explica la cuota
pilar: CUENTAS
formato: F-HOST
publico: motorizado
duracion_s: 28
produccion: ia
personaje: true
hechos: [H3, H4, H5, H6]
ganchos:
  - {tipo: G3, texto: "Soy una IA y vengo a hablarte de plata."}
  - {tipo: G1, texto: "Motorizado: ganaste $150. ¿Cuánto se te va?"}
  - {tipo: G2, texto: "Si manejas moto en Caracas, escúchame 20 segundos."}
gancho_elegido: 0
redes: [tiktok, instagram, youtube, whatsapp]
estado: guion
---

# Kuu se presenta y explica la cuota

## Idea en una frase
Kuu dice que es una IA, se presenta como la voz de Kuulis y hace la cuenta: con $150 al mes, una app con
comisión del 20 % se queda con $30 y Kuulis cobra $5.

## Guion
| Tiempo | Plano | Voz (Kuu) | Texto en pantalla |
| --- | --- | --- | --- |
| 0–2 s | Primer plano de Kuu, acera de Altamira, el Ávila desenfocado. Gira hacia cámara | «Soy una IA… y vengo a hablarte de plata.» | SOY UNA IA. Y VENGO A HABLARTE DE PLATA. |
| 2–6 s | Plano medio, Kuu camina hacia cámara | «Soy Kuu, la voz de Kuulis. Mira esta cuenta, motorizado.» | Kuu · la voz de Kuulis |
| 6–13 s | Plano medio, Kuu cuenta con los dedos | «Si este mes ganaste ciento cincuenta dólares y la app te quita el veinte por ciento… se te fueron treinta.» | $150 → −20 % = −$30 |
| 13–21 s | Primer plano, sonrisa | «En Kuulis no hay comisión por carrera. Con ciento cincuenta pagas una cuota de cinco. Y si el mes te fue mal, cero.» | $5 · mes flojo = $0 |
| 21–25 s | Plano medio | «Y los primeros tres meses, nada. Cuentas claras, y punto.» | 3 MESES SIN CUOTA. |
| 25–28 s | Cierre de marca (Remotion) | — | Link en la bio · Android |

**Nota de hechos:** los $150 y el 20 % son ejemplo explícito («si…»); la cuota de $5 para ganancias de $100,01 a
$200 sale de `fee_tiers` [H4]. «Si el mes te fue mal, cero» se refiere a ganar $100 o menos o no trabajar [H4, H5].

## Prompts de producción
**Personaje (Higgsfield, AI Influencer Studio):** el de [`brand/kuu.md`](../../brand/kuu.md#prompt-base-para-mk3).
Guardar como elemento reutilizable.

**Plano 1, 0–6 s (video desde imagen del personaje, con voz/labios):**
> The same young Venezuelan woman (Kuu) in a deep green bomber jacket with a small yellow dot on the left chest,
> standing on a sidewalk in Altamira, Caracas, El Ávila mountain softly blurred behind, golden hour. She turns to
> the camera with a playful smile and starts talking, then walks two steps toward the camera. Handheld
> smartphone look, vertical 9:16, natural skin, no text, no logos.

**Plano 2, 6–25 s:** igual, plano medio fijo, «she counts on her fingers while explaining, expressive hands,
then smiles warmly», lip-sync con el audio de la voz elegida.

**Buzzy:** mismos prompts en su lienzo, con el modelo de video que su agente recomiende para personas hablando
(anotar cuál). Sin subida de cara (plan Basic): describir a Kuu con el prompt base.

## Textos de publicación
- **TikTok:** «Soy una IA y vengo a hablarte de plata 🤖 Motorizado, haz la cuenta conmigo. Comenta MOTO y te
  mando cómo registrarte.» `#Kuulis #MotorizadosDeCaracas #SinComision #Caracas`
- **Instagram:** «Soy Kuu, la voz de Kuulis (sí, soy una IA). Si ganaste $150 este mes y la app te quita el 20 %,
  se te fueron $30. En Kuulis no hay comisión por carrera: con $150 pagas una cuota de $5, y si el mes te fue mal,
  $0. Los primeros 3 meses, nada. Comenta MOTO 🏍️» `#Kuulis #Motorizados #Caracas #CuentasClaras`
- **YouTube Shorts:** título «Motorizado en Caracas: haz esta cuenta 🏍️»; descripción «Cero comisión por carrera
  en Kuulis. Descárgala para Android.» `#Kuulis #Caracas`
- **WhatsApp:** «Motorizado: $150 al mes = $5 de cuota en Kuulis. Sin comisión por carrera. Hecho con IA.»

## Notas del revisor
Etiqueta de IA: sí. Hechos H3–H6 verificados contra `/public/site` (2026-10-18). Comparación sin nombrar marcas.
