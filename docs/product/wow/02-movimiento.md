# 02 · Movimiento

**Decidido (2026-10-28): agregar movimiento a la app.** Los detalles de abajo son la propuesta (Supuesto).

## Base técnica

- Instalar `react-native-reanimated` (v4, con `react-native-worklets`) y `react-native-gesture-handler`.
  Ambas son nativas: **requieren un build nuevo**, no salen por OTA. Hacerlo primero y publicar el build antes
  de cualquier pantalla que las use.
- Opcional, para animaciones ilustradas: `lottie-react-native` (archivos de LottieFiles) o `rive-react-native`.
  Una sola de las dos; propuesta: Lottie, por catálogo y peso (ver 07).
- Todas las animaciones corren en el hilo nativo (Reanimated). Nada de `Animated` con `useNativeDriver: false`.
- Respetar "Reducir movimiento" del sistema (`useReducedMotion`): sin rebotes ni confeti, solo fundidos.

## Reglas (para agregar a `mobile-design.md`)

| Tipo | Duración | Curva |
| --- | --- | --- |
| Toque en botón o tarjeta | 120 ms | resorte corto, escala 0,97 |
| Aparecer o salir de un elemento | 200‑250 ms | `easeOut` |
| Cambio de pantalla | 280‑320 ms | resorte sin rebote visible |
| Hoja inferior (arrastre y soltar) | física del gesto | resorte con amortiguación alta |
| Celebraciones | 600‑1200 ms | libre, una sola vez |

Un movimiento siempre explica algo (de dónde viene, a dónde va, qué cambió). Si no explica nada, sobra.

## Lista de cambios

1. **Hoja inferior arrastrable** (`MapSheetLayout`): tres alturas (mínima, media, completa), se arrastra por
   la rayita y por el contenido, el mapa se re‑encuadra al soltar. Hoy la rayita es solo un dibujo.
2. **Botones y tarjetas con resorte** al tocar (`Button`, `Card`, `Pressable` de `ui.tsx`), con háptica
   ligera en las acciones principales.
3. **Transiciones con continuidad**:
   - La barra "¿A dónde vamos?" crece hasta convertirse en la pantalla de búsqueda.
   - La tarjeta de la moto en la cotización "aterriza" desde abajo y el precio cuenta hasta su valor.
   - Al confirmar, el botón "Pedir moto" se transforma en los anillos de "buscando".
   - Pantallas de detalle (perfil, billetera, ayuda) entran desde la derecha; modales desde abajo. Hoy todas
     usan el mismo `fade`.
4. **Listas que aparecen escalonadas** (historial, notificaciones, lugares frecuentes): 30 ms entre filas,
   solo la primera vez.
5. **Cambios de estado del viaje animados**: los pasos (`ProgressSteps`) avanzan con relleno, el título hace
   un cruce suave y la píldora de estado late una vez.
6. **Números vivos**: precio, ganancias del motorizado, saldo de billetera y contador de espera cuentan hasta
   su valor en vez de aparecer.
7. **Skeletons con brillo** en inicio, cotización, historial y perfil, en lugar de pantalla vacía.
8. **Tab bar**: la burbuja verde se desliza entre pestañas en vez de saltar.
9. **Motorizado**: el botón "Conectarme" tiene un deslizar para confirmar (como Fomo "desliza para comprar"),
   y la oferta entrante entra con un golpe de resorte y vibración.

Esfuerzo: M‑L (2 semanas para todo). Los puntos 1, 2, 3 y 7 son los que más se notan.

## Cómo se verifica

- Grabar en video (Android barato y iPhone) cada flujo antes y después.
- Medir que no baje de 55 fps en el mapa con la hoja en movimiento.
- Probar con "Reducir movimiento" activado.
