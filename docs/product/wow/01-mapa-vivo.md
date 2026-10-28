# 01 · Mapa vivo

El mapa ocupa más de la mitad de la pantalla en inicio, cotización y viaje. Hoy está quieto. Este documento
tiene dos partes: **A** (el viaje en curso, se puede hacer ya) y **B** (que el inicio no se vea vacío).

## A. El viaje en curso (Supuesto, listo para hacer)

Hoy `RideMap.tsx` pinta la moto como un `Marker` fijo que salta en cada actualización y el `heading` que
llega por tiempo real no se usa.

1. **Moto que se desliza.** Interpolar entre la posición anterior y la nueva durante el tiempo que hay entre
   dos actualizaciones (normalmente 3‑5 s), con curva lineal para que parezca velocidad constante.
   En `react-native-maps` se usa `AnimatedRegion` / `MarkerAnimated`, o se anima la coordenada con
   Reanimated y se pasa al marcador.
2. **Moto que gira.** Rotar el marcador según `heading` (o según el ángulo entre la posición anterior y la
   nueva si `heading` viene vacío). Rotación suavizada, nunca un giro de 180° de golpe.
3. **Marcador propio.** La moto Kuulis vista desde arriba (ver 04), no el círculo con un ícono de bici.
4. **Cámara que acompaña.** Mientras el usuario no toque el mapa, la cámara sigue a la moto con un encuadre
   que incluya moto + punto de recogida (en camino) o moto + destino (en viaje). Si el usuario mueve el mapa,
   aparece el botón "Centrar".
5. **Punto de recogida con pulso** (dos anillos suaves, como los de "buscando").
6. **Chip de ETA en el mapa**: "3 min" pegado al punto de recogida, o "Llegas 10:53" sobre el destino.
7. **Ruta que se dibuja** de punta a punta en 600 ms al confirmar, y la parte ya recorrida se vuelve gris
   mientras avanza el viaje.
8. **Rendimiento**: probar en un Android barato. El marcador de la moto mantiene `tracksViewChanges`
   apagado y lo que se anima es la coordenada, no la vista.

Esfuerzo: M (1 semana). Solo app, la API ya manda posición y rumbo.

## B. Que el inicio no se vea vacío

### La idea de Carlos

Mostrar motos "que van en viaje" aunque todavía no haya motorizados disponibles, y que al tocarlas se vea
cuánto está pagando ese pasajero.

### Mi posición, con franqueza

La idea de fondo es muy buena (es lo mismo que hace Fomo con "mira lo que están comprando los demás" y genera
mucha confianza). **Pero si las motos o los precios son inventados, es un riesgo serio:**

- En Venezuela la gente compara apps entre panas. Basta que un motorizado diga "yo no estaba en ningún viaje"
  o que alguien pida y no llegue nadie habiendo "10 motos" en el mapa, para que se viralice como estafa.
- Las reglas de Apple y Google prohíben las apps que engañan al usuario; mostrar actividad inventada como real puede costar un rechazo o una retirada de la tienda.
- Choca con lo más fuerte de la marca: confianza, verificación, precio justo.

### Propuesta honesta: "Caracas en movimiento" (Supuesto)

Lo mismo que quiere Carlos, pero con datos reales:

1. **Motos en viaje reales.** Solo viajes `in_progress` de verdad, con la posición **retrasada y difuminada**
   (por ejemplo 2‑3 minutos de retraso y redondeada a ~200 m) para proteger a motorizado y pasajero. Se ve la
   moto moviéndose por la ciudad, sin mostrar de dónde sale ni a dónde va.
2. **Al tocar una moto**: una tarjeta tipo "Viaje en curso · ~2,1 km · $1.80 · 100 % para el motorizado".
   El precio es el real del viaje (es público en la tarifa de todos modos). Nunca nombre, foto ni dirección.
3. **Viajes recientes (estilo Fomo)**: una tira en el inicio con viajes terminados en las últimas horas:
   "Hace 12 min · Chacao → Altamira · $1.60". Solo zonas (municipio o urbanización), nunca direcciones.
4. **Umbral**: la capa solo aparece si hay al menos N viajes reales en la última hora (N lo decide Carlos;
   propuesta 3). Por debajo, en vez de mapa vacío, un mensaje honesto y simpático: "Kuulis está arrancando en
   Caracas. Los primeros motorizados ya están verificados." con el número real de motorizados aprobados.
5. **Antes del lanzamiento** (QA y demos), se puede mostrar con viajes simulados **solo en QA** o con una
   etiqueta visible "Ejemplo". En producción, nunca.
6. **Privacidad**: agregar al aviso de privacidad que mostramos viajes en curso de forma anónima y aproximada,
   y un interruptor en el perfil del motorizado "No mostrar mis viajes en el mapa público".

Necesita: endpoint nuevo en la API (`GET /public/activity` con caché de 30 s en Redis, sin datos personales),
capa en `RideMap` y tira de recientes en `PassengerHome`. Esfuerzo: M (API + app) y revisión legal del texto.

### Motos disponibles de verdad (más adelante)

Cuando haya motorizados conectados: motos disponibles cerca con la misma técnica de posición difuminada y
"moto a 3 min" en el buscador y en la cotización. La parte B ya deja la capa lista para esto.
