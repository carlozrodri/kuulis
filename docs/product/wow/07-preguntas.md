# 07 · Preguntas abiertas para Carlos

Cada pregunta tiene la opción recomendada marcada con ⭐. Cuando Carlos responda, se pasa a "Decidido" en el
archivo correspondiente y se anota aquí la fecha.

1. **Motos en el inicio mientras no hay motorizados disponibles** (01‑B)
   - ⭐ A. "Caracas en movimiento" solo con viajes reales (posición retrasada y difuminada), con umbral; por
     debajo del umbral, mensaje honesto con el número real de motorizados verificados.
   - B. Lo mismo, pero con viajes simulados solo en QA y demos, nunca en producción.
   - C. Motos y precios inventados en producción. No recomendado (riesgo de confianza y de tiendas).
2. **Umbral para mostrar la capa**: ⭐ 3 viajes reales en la última hora / otro número.
3. **Al tocar una moto en viaje, mostrar el precio** de ese viaje (sin nombre, foto ni dirección):
   ⭐ sí / no.
4. **Íconos 3D**: ⭐ comprar Thiings Indie ($49 de por vida) + Fluent Emoji 3D gratis / solo gratuitos
   (3dicons + Fluent).
5. **La moto Kuulis**: ⭐ primero genero yo 3‑4 propuestas en estilo Thiings y eliges; si no convence, un
   ilustrador 3D (~$100‑300) / directamente ilustrador.
6. **Animaciones ilustradas**: ⭐ Lottie / Rive.
7. **Voz venezolana**: ⭐ nivel medio (las frases de la tabla de 05, marcando cuáles sí) / suave (solo 3‑4
   frases) / fuerte (mucha jerga).
8. **Regateo**: ⭐ "Precio justo, sin regateo" dicho con orgullo / estudiar un "Cuádralo" propio más adelante.
9. **Build nuevo** para Reanimated y Gesture Handler: ⭐ sí, primero un build de QA y luego producción.
10. **Orden**: ⭐ movimiento + alegría primero, luego mapa vivo / mapa vivo primero.
11. **Sonidos propios**: ⭐ los compongo yo como la música de los anuncios / comprar en una librería de sonidos.
12. **Fechas especiales** (Navidad, Vinotinto): ⭐ después del lanzamiento / desde ya.
13. **Capturas de Glovo y Fomo**: Carlos manda 4‑6 de cada una (pendiente).

## Respuestas (Carlos, 2026-10-28) — Decidido

1. **Nada simulado.** "Caracas en movimiento" solo con viajes reales; por debajo del umbral, mensaje honesto.
2. Umbral: 3 viajes reales en la última hora (valor por defecto, ajustable desde el admin).
3. Sí se muestra el precio del viaje, **sin nombres y sin dirección**.
4. **No pagar íconos.** Claude elige fuentes gratuitas pero que se vean únicas (ver 04).
5. Sí: Claude genera las propuestas de la moto Kuulis.
6. Sí, voz venezolana (nivel medio).
7. Sí: "Precio justo, sin regateo".
8. Sí: build nuevo de QA.
9. Sí: movimiento y alegría primero, luego el mapa.
10. Sí: Claude compone los sonidos propios.
11. Referencias nuevas en `references/carlos-2026-10-28/` (ver 06).
