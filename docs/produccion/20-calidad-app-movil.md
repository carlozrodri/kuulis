# 20 · Calidad de la app móvil

**Prioridad:** P1 · **Área:** Mobile · **Depende de:** 01

## Objetivo
Que la app funcione bien en los teléfonos que de verdad se usan en Caracas (Android de gama baja, poca memoria,
datos lentos e intermitentes), que sea accesible y que tenga tests que eviten regresiones en el flujo de viaje.

## Estado actual
- App cuidada: sistema de diseño Verde Ávila, modo oscuro, banner de conexión (`ConnectionBanner`), toasts,
  esqueletos, reconexión de WebSocket con backoff, reporte de crashes a los logs, ~80 `accessibilityLabel`.
- Tests: 9 archivos de jest, sobre todo lógica e i18n; **sin tests de componentes ni E2E** (pendiente en
  `docs/pending.md`).
- Sin persistencia de caché de React Query: al abrir sin conexión no se ve el historial ni la billetera.
- Sin medición de rendimiento (arranque, memoria, tamaño del APK).
- Ubicación en segundo plano solo en Android (iOS necesita build, fuera de alcance).

## Alcance
### Incluye
1. **Matriz de dispositivos de prueba**: al menos un Android Go/gama baja (2–3 GB RAM, Android 10–11), uno medio
   y uno reciente. Lista en `mobile/README.md`.
2. **Presupuestos de rendimiento**: arranque en frío < 3 s en gama media y < 5 s en gama baja; APK < 60 MB;
   memoria estable durante un viaje de 30 min; 60 fps en el mapa con la moto moviéndose.
   Medición con builds de producción (Hermes), y ajustes: carga perezosa de pantallas, imágenes optimizadas,
   menos re-renders en el mapa.
3. **Consumo de datos y batería** del motorizado conectado 8 h: medirlo y reducirlo (frecuencia adaptativa de
   18, compresión del WebSocket si aplica, mapas en caché).
4. **Modo sin conexión**: caché persistente (historial, billetera, perfil, último viaje) con React Query
   persistido; cola de acciones idempotentes (calificar, mensaje de chat) que se envían al volver la conexión;
   el motorizado en viaje puede marcar "llegué/iniciar/terminar" con reintento seguro (claves de idempotencia).
5. **Idempotencia en la API** para acciones de viaje y billetera (`Idempotency-Key`), para que los reintentos
   no dupliquen nada.
6. **Accesibilidad**: auditoría con TalkBack, tamaños de letra grandes del sistema (hasta 200 %) sin cortes,
   contraste AA en claro y oscuro, objetivos táctiles ≥ 48 px (≥ 60 en motorizado).
7. **Tests**:
   - Componentes con React Native Testing Library para las pantallas del flujo de viaje, billetera y onboarding.
   - **E2E con Maestro** (gratis, en local o en el servidor con emulador) de: registro, pedir y completar un
     viaje con dos dispositivos simulados contra QA, recarga manual, reporte.
   - Prueba de las traducciones en ambos idiomas por pantalla (capturas).
8. **Errores amables**: catálogo revisado de todos los códigos de error de la API con su texto es/en
   (test que falla si un `code` del backend no tiene traducción en la app).
9. **Mapa sin Google**: confirmar costos y límites de `react-native-maps` con Google en Android (la clave de
   Maps SDK para Android es gratuita en uso móvil, pero requiere clave); alternativa MapLibre con teselas
   propias si cambian las condiciones.

### Fuera
- Build de iOS nativa (bloqueo 3). La PWA cubre iPhone en 09.

## App móvil
### Pasajero
- Historial y último viaje visibles sin conexión; mensaje claro "Sin conexión: tu pedido se enviará al volver"
  solo donde aplique (no se piden viajes sin conexión).
### Motorizado
- Acciones del viaje con reintento automático y estado "Enviando…" visible.
- Indicador de calidad de señal y de GPS en la pantalla de conducir.

## Admin
Sin cambios.

## API y datos
- Middleware de `Idempotency-Key` (Redis, 24 h) para `POST /rides`, acciones de viaje, ratings, top-ups y
  transferencias.
- Script que exporta todos los `code` de `AppError` para el test de traducciones de la app.

## Criterios de aceptación
- Los presupuestos de rendimiento se cumplen en el teléfono de gama baja de la matriz.
- Un motorizado sin señal durante 1 min al terminar el viaje termina sin duplicados al volver la señal.
- Las pruebas de Maestro del viaje completo corren en verde de forma repetible.
- Con letra al 200 % ninguna pantalla principal corta textos ni botones.
- Todos los códigos de error del backend tienen traducción.

## Dependencias
01 (CI para jest y lint). 18 para frecuencia adaptativa de ubicación.

## Preguntas para Carlos
1. ¿Qué teléfonos usan los motorizados que conoces? Ayuda a fijar la matriz de pruebas.
