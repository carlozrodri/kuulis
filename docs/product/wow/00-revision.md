# Revisión crítica de la app mobile: qué le falta para ser "WOW"

Fecha: 2026-10-28. Parte de la carpeta [wow](README.md). Base revisada: rama `qa` (commit 12f399b), carpeta `mobile/`, capturas en la carpeta
compartida (`app-capturas`, `rediseno-2026-10`, `perfil-2026-10`) y las referencias de Yummy en
`docs/product/references/yummy/`. No se cambió código de la app.

## Veredicto en una frase

La app está **muy bien construida y muy completa por dentro** (PIN de inicio, SOS, contactos de confianza,
compartir viaje, reasignación, no‑show, objetos perdidos, cola offline, accesibilidad con tests, Bs a BCV y
Binance), pero **por fuera se siente como una plantilla correcta**: íconos de línea en cuadritos de color,
tarjetas blancas, un mapa quieto y casi ninguna animación. Es una app que *funciona*, no una que *se siente*.
El trabajo que falta no es de funciones, es de **vida, carácter y momentos**.

## Lo que ya está bien (corto, para no perderlo)

- Flujo de viaje completo y con estados claros; pocas apps de LatAm tienen PIN, SOS y auto‑compartir.
- Mostrar el precio en USD **y** en Bs a tasa BCV y Binance es un acierto muy venezolano. Yummy pone la tasa
  arriba del inicio porque a la gente le importa.
- La oferta entrante del motorizado (pantalla oscura, anillo de cuenta regresiva, sonido) es la pantalla con
  más intención de toda la app.
- Sistema de diseño ordenado (tokens claro/oscuro, contraste probado). Es una buena base para subir el nivel.

## Las debilidades, sin anestesia

### 1. El mapa está muerto (el problema número uno)

El mapa es el 60 % de la pantalla en inicio, cotización y viaje, y hoy no cuenta nada:

- **En el inicio no se ven motos cerca.** Uber, Yummy, Ridery: todas pintan carritos/motos alrededor tuyo.
  Un mapa vacío dice "aquí no hay nadie", que es justo el miedo de una app nueva. (`PassengerHome.tsx` usa
  `RideMap` sin capa de motos; la `DemandLayer` existe solo para el motorizado.)
- **La moto salta** de posición en posición cuando llega cada GPS. No hay interpolación ni rotación según el
  rumbo (`RideMap.tsx` pone un `Marker` fijo con un ícono `Bike`; el `heading` llega en el evento pero no se usa).
  Ver tu moto *deslizarse* por la calle y girar en la esquina es el momento más mirado de cualquier app de
  transporte.
- La ruta es una línea estática. No hay animación de "dibujarse", ni pulso en el punto de recogida, ni la
  cámara siguiendo a la moto.
- No hay ETA en el mapa ("3 min") sobre el pin de recogida, ni chip de tiempo sobre la ruta (Yummy pone
  "22 min" en la ruta).

### 2. No hay identidad visual propia; se ve genérica

- Todo son íconos Lucide de línea dentro de un cuadrado verde o amarillo claro. Es lo que trae cualquier
  plantilla. Yummy usa **ilustraciones 3D** (el carro morado, la hamburguesa, la caja) y eso es lo que la
  gente recuerda.
- **No hay una moto Kuulis.** Ni ilustración, ni 3D, ni personaje. La marca es solo la palabra "kuulis." y el
  verde. El marcador de la moto en el mapa es un círculo negro con un ícono genérico de bicicleta.
- El encabezado verde con círculos difusos (bienvenida, auth) se ve de relleno, no de marca.
- El logo en una píldora blanca arriba del mapa ocupa espacio valioso y no aporta (nadie necesita que le
  recuerden en qué app está).
- Los anuncios que hicimos ("depende", los panas, el regateo) tienen **mucha más personalidad que la app**.
  Quien llegue por un anuncio con humor caraqueño se encuentra una app seria y neutra. Esa desconexión se nota.

### 3. Casi no hay movimiento

- No están instaladas `react-native-reanimated` ni `react-native-gesture-handler`. Todo el movimiento es la
  API `Animated` básica en 7 archivos; lo único realmente animado son los anillos de "buscando".
- **El "handle" de la hoja inferior es decorativo**: la hoja no se arrastra (`MapSheetLayout.tsx` dibuja la
  rayita pero no hay gesto). Los usuarios de Uber/Yummy la intentan arrastrar por reflejo, y no pasa nada.
  Eso se siente roto.
- Todas las pantallas cambian con el mismo `fade` (`app/_layout.tsx`). No hay transiciones con continuidad
  (por ejemplo, la barra "¿A dónde vamos?" que crece hasta la pantalla de búsqueda).
- El precio aparece de golpe; no hay conteo, ni la tarjeta de la moto "aterriza".
- Háptica solo en 11 lugares. El pasajero no recibe vibración ni sonido cuando un motorizado acepta o llega.

### 4. No hay momentos de deleite

Los momentos que la gente cuenta a sus amigos hoy son pantallas de texto:

| Momento | Hoy | Debería sentirse como |
| --- | --- | --- |
| Un motorizado acepta | Cambia el texto a "Pedro va en camino" | Revelación: foto grande, nombre, placa, "verificado", vibración y sonido corto |
| El motorizado llegó | Píldora amarilla "Tu motorizado llegó" | Pantalla llena con la placa en grande, color de la moto y el PIN, más vibración |
| Llegaste al destino | Estado vacío "¡Llegaste! Recuerda pagar $1.80" | Celebración breve ("¡Llegaste, María!"), resumen bonito del viaje, y *luego* el recordatorio de pago |
| Primer viaje | Nada especial | Algo único: insignia, mensaje, quizás descuento del próximo |
| Motorizado termina el día | Números en una tarjeta | "Hoy hiciste $23. **Te quedas con el 100 %.**" grande y compartible |

Hoy la pantalla de llegada recuerda una deuda en vez de celebrar.

### 5. El gran diferenciador está escondido

"Sin comisión, el 100 % es para el motorizado" es la historia más fuerte de Kuulis y casi no se ve:

- Aparece en una nota amarilla para motorizados y en la descripción del modo. Para el pasajero, no aparece
  en el momento que importa (cotización y pago).
- Idea: en la cotización y al pagar, una línea con emoción: "Los $1.80 van completos para Pedro. Kuulis no le
  quita nada." Eso convierte un modelo de negocio en un motivo para elegirte.
- **Ojo con el regateo.** El modelo dice que el monto lo fija Kuulis, mientras Yummy ofrece "Cuádralo"
  (tú pones el precio). No hace falta copiarlo, pero hay que *apropiarse* de la decisión: "Precio justo, sin
  regateo" dicho con orgullo, no en silencio. Hoy el usuario no sabe si puede negociar o no.

### 6. Onboarding frío

- No hay ningún momento de "por qué Kuulis" antes del login: se abre directo a un formulario.
- La primera pantalla después de entrar es "¿Cómo quieres usar Kuulis hoy?" con dos tarjetas. Funciona, pero
  es una pregunta administrativa en el momento de mayor curiosidad.
- Propuesta: 3 pantallas cortas y animadas (moto que llega, "le pagas directo", "verificados y con PIN"),
  saltables, y pedir ubicación con contexto ("para mostrarte las motos cerca").

### 7. Inicio y cotización: espacio desperdiciado

- Inicio: saludo grande + buscador + "Agregar casa / trabajo" + una barra de navegación negra muy pesada.
  Falta información viva: motos cerca, tiempo estimado de recogida, tasa del día.
- La barra inferior negra pesa más visualmente que el contenido. En modo claro es lo más oscuro de la pantalla.
- Cotización: la tarjeta "Moto" es grande para una sola opción y no dice lo que el usuario quiere saber:
  **en cuánto llega una moto a buscarme**. Los métodos de pago se cortan en el borde (Binance queda cortado).

### 8. El copy es correcto pero sin acento

- El español es neutro y cuidado ("Buscando tu motorizado", "¡Llegaste!"). En todo `es.json` (2.451 líneas)
  hay **un** "vale" y ningún "pana", "chévere" o "fino".
- No hace falta llenar la app de jerga, pero los momentos emocionales sí piden voz local: "¡Épale, Pedro ya
  viene!", "Llegaste fino", "Tu pana Pedro te espera abajo". Un tono con chispa en 15‑20 frases clave
  cambia la percepción por completo, sin tocar el resto.

### 9. Confianza: las funciones están, la sensación no

- PIN, SOS, compartir y contactos son de primer nivel, pero aparecen como tres botones redondos iguales.
- En el momento de asignación se debería *ver* la verificación: "Cédula y licencia verificadas", años en
  Kuulis, número de viajes, la foto de la moto real. La placa debería ser enorme, como en Uber.

### 10. Rendimiento percibido

- Hay skeletons en pocas pantallas (billetera, calidad). En inicio, cotización e historial lo que se ve es
  vacío y luego contenido.
- La cotización podría mostrar la tarjeta de inmediato con el precio animándose al llegar, en vez de esperar.

### 11. Funciones que faltan y que suman "wow" o retención

- **Seguimiento fuera de la app**: notificación persistente en Android con la ETA y Live Activity en iOS
  (Dynamic Island). Es de lo más moderno que se puede ofrecer y muy pocas apps venezolanas lo tienen.
- **Envíos con moto** (paquetes, comida que tú mismo pediste, llaves). Es el servicio natural de una moto y el
  primero que Yummy tiene y nosotros no.
- Motorizado favorito / repetir con el mismo.
- Programar un viaje.
- Resumen mensual compartible para motorizados ("Este mes ganaste $X y te quedaste con todo").

## Plan priorizado

Esfuerzo: S = 1‑3 días, M = 1 semana, L = 2‑3 semanas (una persona, con QA).

| # | Qué | Impacto | Esfuerzo |
| --- | --- | --- | --- |
| 1 | **Mapa vivo**: moto interpolada y rotada según rumbo, cámara que la sigue, pulso en recogida, chip de ETA. | Muy alto | M |
| 2 | **Motos cerca en el inicio** (endpoint con posiciones aproximadas y redondeadas por privacidad) + "moto a 3 min" en inicio y cotización. | Muy alto | M (API + app) |
| 3 | **Instalar Reanimated + Gesture Handler** y hacer la hoja inferior arrastrable de verdad. Base de todo lo demás. | Alto | M |
| 4 | **Momentos clave**: revelación del motorizado al aceptar, pantalla "llegó" con placa grande, celebración al llegar, sonido y háptica para el pasajero. | Muy alto | M |
| 5 | **Mensaje "100 % para el motorizado"** en cotización, pago y fin de viaje; postura clara sobre "precio justo, sin regateo". | Alto | S |
| 6 | **Voz venezolana** en 15‑20 frases de momentos emocionales (es), revisada por Carlos. | Alto | S |
| 7 | **Identidad propia**: ilustración/3D de la moto Kuulis (marcador del mapa, vacíos, onboarding, ícono de servicio), menos íconos genéricos en cuadritos. Encargar a ilustrador o generar y pulir. | Muy alto | L |
| 8 | Onboarding de 3 pantallas antes del login y permiso de ubicación con contexto. | Medio | S‑M |
| 9 | Inicio más vivo: quitar la píldora del logo, tasa del día visible, barra inferior más liviana en claro. | Medio | S |
| 10 | Confianza visible en la asignación: verificaciones, viajes, foto de la moto. | Medio | S (si la API ya expone los datos) |
| 11 | Notificación persistente Android + Live Activity iOS con la ETA. | Alto | L (requiere build nativo, no OTA) |
| 12 | Skeletons en inicio, cotización e historial; precio con animación. | Medio | S |
| 13 | Envíos con moto. | Alto (negocio) | L (producto + API + app + admin) |

### Orden recomendado

1. **Sprint 1 (sensación inmediata):** 3, 1, 4, 5, 6. Con esto la app pasa de "correcta" a "se siente viva"
   sin cambiar el diseño visual. Todo sale por OTA salvo instalar Reanimated/Gesture Handler, que requiere
   un build nuevo (hacerlo primero).
2. **Sprint 2:** 2, 9, 10, 12. El inicio deja de verse vacío.
3. **En paralelo, desde ya:** 7 (identidad). Es lo que más tarda y lo que más hace que la gente *recuerde*
   la app. Recomiendo empezar pidiendo a Carlos 3‑5 apps que le parezcan WOW (no solo de transporte), ya que
   las direcciones de rediseño propuestas a ciegas en octubre fueron descartadas.
4. **Después:** 8, 11, 13.

## Riesgos a tener en cuenta

- **Motos cerca con pocos motorizados**: al lanzar puede haber 2 motos en todo el mapa, lo que se ve peor que
  no mostrar ninguna. Mostrar solo desde cierto umbral o mostrar "X motorizados activos en Caracas".
- **Privacidad del motorizado**: las posiciones públicas deben ir redondeadas y con retraso.
- **Rendimiento en Android de gama baja** (muy común en Venezuela): animaciones en el hilo nativo
  (Reanimated) y marcadores con `tracksViewChanges` congelado, como ya se hace. Probar en un teléfono barato.
- **No sobrecargar de jerga**: el tono local va en momentos, no en errores, legales ni pagos.
- Más servicios (como Yummy) no es el camino al WOW a corto plazo; el WOW viene de hacer el viaje en moto
  mucho más bonito y emocional que el de ellos.
