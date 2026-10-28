# Kuulis WOW: plan para que la app se recuerde

Carpeta creada el 2026-10-28 a partir de la revisión crítica de la app mobile ([00-revision.md](00-revision.md)).
Convención de la carpeta: **Decidido** = Carlos lo aprobó; **Supuesto** = propuesta pendiente de confirmar
(las preguntas abiertas están en [07-preguntas.md](07-preguntas.md)).

## Archivos

| Archivo | Qué contiene | Estado |
| --- | --- | --- |
| [00-revision.md](00-revision.md) | Diagnóstico completo: debilidades, riesgos y plan priorizado | Hecho |
| [01-mapa-vivo.md](01-mapa-vivo.md) | Moto que se desliza, cámara, ETA y "Caracas en movimiento" (actividad real) | Implementado |
| [02-movimiento.md](02-movimiento.md) | Librerías, hoja arrastrable, transiciones, reglas de animación | Decidido (agregar) |
| [03-alegria.md](03-alegria.md) | Los momentos de deleite, pantalla por pantalla | Decidido (agregar) |
| [04-identidad-iconos.md](04-identidad-iconos.md) | Íconos 3D (Thiings y alternativas), la moto Kuulis, sonidos | Supuesto |
| [05-voz-y-mensaje.md](05-voz-y-mensaje.md) | Voz venezolana y el mensaje "100 % para el motorizado" | Supuesto |
| [06-referencias.md](06-referencias.md) | Qué tomar de Yummy, Glovo y Fomo | Hecho |
| [07-preguntas.md](07-preguntas.md) | Preguntas y respuestas de Carlos (2026-10-28) | Respondido |

## Lo decidido el 2026-10-28

- Carlos está de acuerdo con el diagnóstico.
- **Agregar movimiento** (02) y **agregar alegría** (03) a la app.
- **Motos cerca de verdad**: todavía no, porque aún no hay motorizados disponibles reales. Carlos propuso
  mostrar motos "en viaje" para que se vea actividad; la forma honesta de hacerlo está en 01 y la decisión
  final en 07.
- Carlos quiere íconos 3D tipo **thiings.co** y alternativas (en 04).
- Apps de referencia de Carlos: **Yummy, Glovo y Fomo** (en 06).

## Orden de trabajo propuesto

1. **Build nuevo** con `react-native-reanimated` y `react-native-gesture-handler` (no sale por OTA). Todo lo
   demás de movimiento depende de esto.
2. Movimiento base: hoja arrastrable, transiciones, botones con resorte (02).
3. Momentos de alegría del pasajero y del motorizado (03), con sonido y háptica.
4. Mapa vivo del viaje: moto interpolada y rotada, cámara, ETA (01, parte A).
5. Voz venezolana y mensaje del 100 % (05). Es casi solo texto: puede ir en paralelo.
6. Íconos 3D y moto Kuulis (04), cuando Carlos elija la fuente.
7. "Caracas en movimiento" (01, parte B), cuando haya viajes reales.

## Implementado (2026-10-28, rama `claude/project-thread-lt9950`, PR #105 a `qa`)

Requiere **APK nuevo** (Reanimated, Worklets y Gesture Handler son nativos); el compilador de QA lo hace solo
porque cambia el runtime.

- Movimiento base: `src/components/motion.tsx` (`Rise`, `Pop`, `Beat`, `CountUp`, `Confetti`), todo respeta
  "Reducir movimiento".
- Botones y tarjetas con resorte y cambio de color animado (`ui.tsx`).
- Hoja inferior que se recoge tocando o arrastrando la rayita (inicio del pasajero, viaje en curso, detalle
  del viaje). Se vuelve a abrir sola cuando cambia el estado del viaje.
- Barra inferior: la burbuja verde se desliza entre pestañas, con háptica.
- Cotización: el precio cuenta hasta su valor y aparece "Los $X van completos pa'l motorizado… sin regateo".
- Buscando: la frase de abajo cambia cada 4 s.
- Motorizado aceptó: la tarjeta del motorizado entra con resorte, sonido propio y vibración.
- Motorizado llegó: tarjeta "Busca esta placa" con la placa grande, doble vibración y sonido.
- Fin del viaje (pantalla de calificación): confeti, "¡Llegaste fino, María!" + "Todito va pa' su bolsillo";
  para el motorizado "+$1.80" que cuenta y "100 % tuyo".
- Sonidos nuevos en `mobile/assets/sounds/` (aceptado, llegó, llegaste, ganancia), misma familia que la oferta.
- Voz venezolana en las frases emocionales (es); el inglés sigue neutro.
- Capturas: `/mnt/project-files/kuulis/wow/capturas-2026-10-28/`.

## Implementado (2026-10-28, segunda parte, rama `claude/project-thread-lt9950`)

- **Moto Kuulis A** en la cotización, en la celebración de llegada, en "Todavía no has rodado" y en el viaje
  terminado (`src/components/illustrations.tsx`, `assets/illustrations/`). Marcador del mapa con una moto
  vista desde arriba en la misma paleta (dibujada en código; cambiarla por una versión 3D cuando la tengamos).
- **Mapa vivo (01‑A)**: la moto se desliza entre dos posiciones GPS y gira por el camino corto (rumbo del
  GPS o dirección del movimiento), la cámara la sigue con calma hasta que la persona mueve el mapa, un anillo
  suave sale del punto de recogida mientras viene, y una píldora negra "Llega en 4 min" queda visible aunque
  la hoja esté recogida. Todo se apaga con "Reducir movimiento".
- **Sin la píldora del logo** en el inicio del pasajero.
- **Caracas en movimiento (01‑B)**, solo viajes reales: API `GET /public/rides/activity`
  ([contrato](../../api/actividad-publica.md)), umbral y apagado en el admin, interruptor del motorizado
  "Mostrar mis viajes en el mapa público". En la app: motos en viaje en el mapa del inicio (al tocar una:
  precio, distancia aproximada y "Todito pa'l motorizado"), tira de viajes recientes y, por debajo del
  umbral, "Kuulis está arrancando en Caracas" con el número real de motorizados verificados.

Pendiente: agregar al aviso de privacidad (texto legal, nueva versión) que mostramos viajes anónimos y
aproximados; metas del motorizado y deslizar para conectarse; moto 3D vista desde arriba.
