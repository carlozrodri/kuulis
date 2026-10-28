# Kuulis WOW: plan para que la app se recuerde

Carpeta creada el 2026-10-28 a partir de la revisión crítica de la app mobile ([00-revision.md](00-revision.md)).
Convención de la carpeta: **Decidido** = Carlos lo aprobó; **Supuesto** = propuesta pendiente de confirmar
(las preguntas abiertas están en [07-preguntas.md](07-preguntas.md)).

## Archivos

| Archivo | Qué contiene | Estado |
| --- | --- | --- |
| [00-revision.md](00-revision.md) | Diagnóstico completo: debilidades, riesgos y plan priorizado | Hecho |
| [01-mapa-vivo.md](01-mapa-vivo.md) | Moto que se desliza, cámara, ETA y "Caracas en movimiento" (actividad real) | Supuesto |
| [02-movimiento.md](02-movimiento.md) | Librerías, hoja arrastrable, transiciones, reglas de animación | Decidido (agregar) |
| [03-alegria.md](03-alegria.md) | Los momentos de deleite, pantalla por pantalla | Decidido (agregar) |
| [04-identidad-iconos.md](04-identidad-iconos.md) | Íconos 3D (Thiings y alternativas), la moto Kuulis, sonidos | Supuesto |
| [05-voz-y-mensaje.md](05-voz-y-mensaje.md) | Voz venezolana y el mensaje "100 % para el motorizado" | Supuesto |
| [06-referencias.md](06-referencias.md) | Qué tomar de Yummy, Glovo y Fomo | Hecho |
| [07-preguntas.md](07-preguntas.md) | Preguntas abiertas para Carlos, con opción recomendada | Abierto |

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
