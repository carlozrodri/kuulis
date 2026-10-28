# 04 · Identidad: íconos 3D, la moto Kuulis y sonidos

Hoy todo son íconos de línea (Lucide) dentro de cuadritos de color. Funcionan bien para acciones pequeñas,
pero no tienen personalidad. La propuesta es **dos niveles**:

- **Íconos de línea (Lucide)** se quedan para lo funcional: flechas, cerrar, ajustes, filas de menú.
- **Ilustraciones 3D** para lo emocional: servicios, estados vacíos, onboarding, celebraciones, insignias,
  la moto del mapa.

## Fuentes de íconos 3D

| Sitio | Estilo | Licencia para una app comercial | Comentario |
| --- | --- | --- | --- |
| **thiings.co** (el que le gusta a Carlos) | 3D suave tipo juguete, +11.000 objetos | Gratis **no** permite uso comercial. Plan Indie **$49 de por vida** (empresas con menos de $200 mil/año) permite apps sin atribución. No se pueden redistribuir sueltos. | La mejor opción por estilo y cantidad. Revisar que no existan motos con marca visible. |
| **3dicons.co** | 3D limpio, varios ángulos y colores | Gratis, CC0 (uso libre) | Menos objetos, pero se pueden descargar los archivos fuente y recolorear en verde Ávila |
| **Fluent Emoji 3D** (Microsoft, en GitHub) | Emoji 3D brillantes | Gratis, licencia MIT | Ideal para reacciones, celebraciones e insignias. Muy reconocible |
| **IconScout 3D** | Miles de packs de distintos autores | De pago por pack o suscripción | Útil si falta algo puntual; cuidado con estilos que no combinan |
| **Spline** (spline.design) | Herramienta para crear 3D propio | Gratis con límites, planes de pago | Para hacer **la moto Kuulis** propia y exportarla como imagen o video |
| **LottieFiles** | Animaciones vectoriales listas | Gratis y de pago, depende del autor | Para confeti, check animado, cargas |
| **Rive** (rive.app) | Animaciones interactivas | Gratis para empezar | Si queremos una moto que reaccione al toque; más trabajo |

Antes de comprar, verificar los términos vigentes en cada sitio (cambian).

**Decidido (2026-10-28): no se compran íconos.** Para que sean únicos y gratis, generamos nuestro propio set
3D (misma luz, mismo material, verde Ávila + amarillo mango), empezando por la moto Kuulis. Fluent Emoji 3D
(MIT) queda como apoyo para reacciones si hace falta. Propuestas de la moto en
`/mnt/project-files/kuulis/moto-kuulis/`.

**Elegida (Carlos, 2026-10-28): propuesta A**, la moto 3D tipo juguete verde Ávila con rines y franja del
asiento en amarillo mango (`docs/product/references/moto-kuulis-a.png`). Todo el set 3D sigue ese estilo.

~~**Recomendación:** comprar Thiings Indie para el grueso, Fluent Emoji 3D para reacciones y celebraciones, y
crear la moto Kuulis propia (abajo).~~ Mezclar más de dos estilos 3D se ve desordenado.

## La moto Kuulis (lo más importante de esta sección)

Una sola moto 3D, propia, en verde Ávila con un detalle amarillo, que aparece en:

1. El marcador del mapa (vista desde arriba, pequeña, que gira con el rumbo).
2. La tarjeta "Moto" de la cotización (vista de lado).
3. Onboarding, estados vacíos, celebración de llegada (con casco y saludando).
4. Ícono de servicio cuando lleguen Envíos u otros.
5. Anuncios y redes (ya hacemos los anuncios con Remotion: la misma moto debe salir ahí).

Cómo hacerla: generarla en el estilo de Thiings (o pedirla a un ilustrador 3D por Fiverr o Behance, ~$100‑300
por el modelo con 5‑6 poses) y pulirla en Spline. Sin logos de marcas reales de motos.

## Sonidos

Cuatro sonidos propios y cortos (menos de 1 s): aceptado, llegó, llegaste, ganancia. El de oferta entrante ya
existe (`assets/sounds/ride-offer.wav`); los nuevos deben sonar a la misma familia.

## Otros toques de marca

- Quitar la píldora blanca con el logo del inicio del pasajero; la marca la ponen la moto y los colores.
- Ícono de la app: probar una versión con la moto Kuulis, no solo la palabra.
- Splash con la moto entrando y frenando (Lottie, 1 s).

Esfuerzo: L (2‑3 semanas en paralelo, depende de quién haga la moto). Integrar en la app: S‑M.
