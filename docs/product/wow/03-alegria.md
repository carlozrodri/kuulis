# 03 · Alegría (momentos de deleite)

**Decidido (2026-10-28): agregar alegría a la app.** Los detalles de abajo son la propuesta (Supuesto).

La regla: **pocos momentos, muy bien hechos.** Si todo celebra, nada celebra. Cada momento combina tres
cosas: animación, sonido corto (si el teléfono no está en silencio) y háptica.

## Pasajero

| Momento | Hoy | Propuesta |
| --- | --- | --- |
| Pide la moto | Aparecen los anillos | El botón se convierte en los anillos; textos que van rotando cada 4 s ("Avisando a los motorizados cerca…", "Ya casi…") |
| **Un motorizado acepta** | Cambia el texto | **Revelación**: la tarjeta del motorizado sube con resorte, foto grande, nombre, placa, "Verificado ✓", vibración de éxito y un sonido corto propio de Kuulis |
| Moto a 1 minuto | Nada | Notificación y aviso en pantalla "Pedro está a 1 minuto, ve bajando" |
| **El motorizado llegó** | Píldora amarilla | Pantalla llena: placa enorme, color de la moto, PIN grande, vibración doble |
| En viaje | Texto con hora de llegada | Barra de progreso del viaje sobre la ruta, la moto avanza por ella |
| **Llegaste** | "¡Llegaste! Recuerda pagar $1.80" | Celebración breve (la moto Kuulis frena y saluda, confeti verde y amarillo 1 s), "¡Llegaste, María!", resumen bonito (km, min, hora). Después, tranquilo: "Págale $1.80 a Pedro. Todo es para él." |
| Califica | Estrellas y etiquetas | Las estrellas rebotan al tocarlas; con 5 estrellas, chispas. |
| **Primer viaje** | Nada | Insignia "Primer viaje en Kuulis", tarjeta para compartir por WhatsApp o Instagram con su recorrido dibujado |
| Hitos | Nada | 10, 25, 50 viajes: insignia y mensaje. Visible en el perfil |
| Resumen del mes | Nada | Tarjeta compartible: viajes, km, "le diste $X a motorizados venezolanos, sin comisiones" |

## Motorizado

| Momento | Hoy | Propuesta |
| --- | --- | --- |
| Aprobado como motorizado | Aviso | Pantalla de bienvenida con la moto Kuulis, "¡Ya eres parte de Kuulis!" y su primer paso |
| Se conecta | Botón | Deslizar para conectarse, el mapa "se enciende" (de gris a color) |
| **Termina un viaje** | Vuelve a la pantalla | "+$1.80" sube y se suma al total del día con conteo, sonido de caja |
| Fin del día | Números | "Hoy hiciste $23 en 9 viajes. **Te quedas con el 100 %.**" compartible |
| Meta diaria | No existe | Meta que elige él ("$20 hoy"), anillo que se llena, celebración al cumplirla |
| Primera calificación de 5 | Nada | Aviso "¡Tu primer 5 estrellas!" (sin mostrar quién la dio) |
| Meses gratis | Aviso amarillo | Contador visible "Te quedan 47 días gratis" en la billetera |

## Detalles que suman

- **Sonidos propios de Kuulis**: 4 sonidos cortos (aceptado, llegó, llegaste, ganancia). Mismo tono para que
  se vuelvan "el sonido de Kuulis". Se pueden componer con la misma herramienta que usamos para la música de
  los anuncios.
- **Fechas especiales**: el ícono y la moto cambian en Navidad, Carnaval, partidos de la Vinotinto (se
  activa desde el admin, sin build).
- **Estados vacíos con personalidad**: la moto Kuulis en el historial vacío ("Todavía no has rodado con
  nosotros"), en notificaciones, en sin conexión ("Se fue la señal… te esperamos").

## Lo que NO hacer

- Celebrar algo que es una mala noticia para el otro (cancelaciones, reportes, pagos en disputa).
- Confeti en pantallas de dinero del motorizado que tienen problemas (saldo negativo, suscripción vencida).
- Sonidos con el teléfono en silencio, salvo la oferta entrante del motorizado (ya existe así).

Esfuerzo: M (1,5 semanas), después de la base de movimiento. Los sonidos y la moto Kuulis (04) se pueden
hacer en paralelo.
