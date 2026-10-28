# 05 · Voz venezolana y el mensaje "100 % para el motorizado"

## Voz (Supuesto)

Hoy el español es neutro y correcto. Los anuncios tienen humor caraqueño ("depende", los panas) y la app no.
La regla propuesta: **voz local solo en los momentos emocionales**. Errores, pagos, legales, seguridad y
soporte siguen claros y neutros.

### Frases candidatas (para que Carlos marque cuáles sí)

| Dónde | Hoy | Propuesta |
| --- | --- | --- |
| Saludo del inicio | "Buenos días, María" | "¡Buenos días, María! ¿Pa' dónde vamos?" |
| Buscador | "¿A dónde vamos?" | "¿Pa' dónde vamos?" |
| Buscando | "Buscando tu motorizado" | "Buscándote una moto…" |
| Aceptado | "Pedro va en camino" | "¡Listo! Pedro ya viene pa' allá" |
| A 1 minuto | (no existe) | "Pedro está a un minutico, ve bajando" |
| Llegó | "Tu motorizado llegó" | "Pedro te está esperando abajo" |
| Llegaste | "¡Llegaste!" | "¡Llegaste fino, María!" |
| Calificar | (título actual) | "¿Qué tal estuvo la rodada?" |
| Historial vacío | (actual) | "Todavía no has rodado con nosotros" |
| Sin conexión | (actual) | "Se fue la señal… apenas vuelva seguimos" |
| Motorizado, fin del viaje | (no existe) | "¡Epa! +$1.80, todito pa' ti" |
| Motorizado, fin del día | (no existe) | "Hoy la rompiste: $23 en 9 viajes" |
| Motorizado aprobado | (actual) | "¡Bienvenido a la familia Kuulis!" |

Cuidados:

- Probar con 5‑10 personas reales de Caracas antes de publicar; lo que suena simpático en un anuncio puede
  sonar forzado repetido 20 veces al día.
- En inglés se queda neutro y amable (no traducir la jerga).
- Mantener los tests de i18n (mismos `{{placeholders}}` en es y en).

Esfuerzo: S (2‑3 días, casi todo es `es.json`).

## El mensaje "100 % para el motorizado" (Supuesto)

Es el diferenciador más fuerte y el pasajero casi no lo ve. Dónde ponerlo:

1. **Cotización**, debajo del precio: "Los $1.80 van completos para tu motorizado. Kuulis no le cobra comisión."
2. **Al llegar**: "Págale $1.80 a Pedro. Todo es para él."
3. **Perfil del pasajero**: contador "Has apoyado a 9 motorizados con $16.20, sin comisiones".
4. **Motorizado, cada viaje**: "+$1.80 · 100 % tuyo".
5. **Onboarding**: una de las tres pantallas.

### Regateo

El precio lo fija Kuulis (modelo de negocio) y Yummy tiene "Cuádralo" (tú pones el precio). Propuesta: no
copiarlo, sino **adueñarse de lo contrario** con orgullo: "Precio justo desde el principio. Sin regateo, sin
sorpresas." en la cotización y en el onboarding. Decisión en 07.
