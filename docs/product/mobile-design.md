# Diseño de la app móvil

## Decidido
- La app tiene que verse **de primer nivel mundial**: que al verla den ganas de usarla.
- Carlos compartirá **screenshots de referencia** más adelante; se agregarán en `docs/product/references/`.

## Principios (supuesto, a validar con las referencias)
1. **El mapa es la pantalla.** Pedir un viaje se hace sobre el mapa, con paneles inferiores deslizables.
2. **Pocos toques.** Pedir un viaje en 3 toques: destino, ver precio, confirmar.
3. **Precio en dólares, grande y claro** antes de confirmar. Nada de sorpresas.
4. **Estados del viaje siempre visibles**: buscando, asignado, llegando, en viaje y finalizado, con animaciones suaves.
5. **Movimiento con intención**: transiciones de 200–300 ms, feedback háptico al confirmar y al recibir solicitud.
6. **Modo oscuro y claro** desde el inicio.
7. **Funciona con mala conexión**: pantallas esqueleto, reintentos automáticos y mensajes claros sin conexión.
8. **Accesible**: textos grandes legibles al sol, contraste alto, botones de al menos 48 px.
9. **Español primero**, inglés disponible.
10. **Dos experiencias en una app**: pasajero y motorizado con la misma identidad visual pero
    pantallas pensadas para cada uno. Por ejemplo, el motorizado necesita botones enormes para usar en la moto.

## Pantallas clave a diseñar
- Bienvenida y registro (pasajero y motorizado).
- Mapa y pedir viaje.
- Precio y confirmación.
- Buscando motorizado y motorizado asignado.
- Viaje en curso y viaje terminado con calificación.
- Motorizado: disponible/no disponible, solicitud entrante, viaje activo, ganancias del mes y cuota.
- Perfil, historial y ayuda.

## Siguiente paso
Con los screenshots de Carlos: extraer paleta, tipografía, componentes y patrones, y armar un sistema de
diseño (colores, tipografía, espaciado, componentes) antes de escribir pantallas.
