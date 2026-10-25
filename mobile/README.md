# Kuulis Mobile

React Native + Expo (SDK 57) + TypeScript + Expo Router, for iOS and Android. i18n in Spanish and English.

```bash
npm install
npm start                 # local API (EXPO_PUBLIC_API_URL, default http://localhost:8000/api/v1)
npm run start:qa          # points to https://kuulis-qa.top8.uk/api/v1
npm run lint && npm run typecheck && npm test
```

Use your machine's LAN IP in `EXPO_PUBLIC_API_URL` when testing against a local API from a phone.

## Google / Apple sign-in

- Google uses native sign-in (`@react-native-google-signin/google-signin`), which is **not in Expo Go**: there the
  button shows "Disponible en la app instalada". Set `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (required; it is the
  `aud` the API checks) and `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` (iOS; also adds the URL scheme plugin). Without
  them the button is hidden.
- Apple (`expo-apple-authentication`) is shown on iOS only. In Expo Go the token's `aud` is `host.exp.Exponent`.

## Structure

```
src/
├── app/                  # Expo Router routes
│   ├── _layout.tsx       # providers + auth guard (Stack.Protected)
│   ├── (auth)/           # login, register, forgot-password
│   ├── welcome.tsx       # pick Pasajero / Motorizado (stored per user on the device)
│   └── (app)/            # (tabs): home, notifications, profile · driver/: onboarding steps
├── components/           # design-system UI kit (ui.tsx), icons, tab bar, hero header
├── features/             # passenger and driver screens' building blocks
├── hooks/                # usePushNotifications, useRealtime (WebSocket), useDriver (react-query)
├── i18n/                 # i18next + locales/{es,en}.json
├── lib/                  # api client (JWT + refresh), config, secure storage, types
├── providers/            # AuthProvider, ModeProvider
└── theme/                # Verde Ávila tokens (light/dark), spacing, radii, Plus Jakarta Sans type scale
```

## Environments

`APP_ENV` (`local` | `qa` | `production`) picks the API URL and the app identity in `app.config.ts`, so QA and
production builds can be installed side by side (`uk.top8.kuulis.qa` vs `com.kuulis.app`). EAS build profiles in
`eas.json` set it for each build.

`APP_STORE` (`apk` | `play`) says where an Android build is distributed. The `play` profile builds an AAB for
Google Play without `REQUEST_INSTALL_PACKAGES` and without the APK updater (Play forbids self-updating): a
mandatory update sends people to the app's page in Play. OTA updates keep working. Production needs its own
`google-services.production.json` (Firebase Android app for `com.kuulis.app`) and `certs/updates-production.pem`. `API_URL` overrides the environment's API: the `play` profile points at QA during
the closed test, until the production server exists.

## Pending before store builds

See `docs/blockers.md`: Apple Developer and Google Play accounts, EAS project (`npx eas-cli init`, then set
`EAS_PROJECT_ID`), push credentials (APNs key / FCM), final bundle identifiers, icons and splash.

## Calidad (doc 20)

### Teléfonos de prueba
Supuesto hasta que Carlos confirme qué usan los motorizados (pregunta 1 del doc 20). La app se prueba en los
tres niveles antes de cada APK:

| Nivel | Referencia | RAM | Android | Para qué |
| --- | --- | --- | --- | --- |
| Gama baja (Go) | Samsung Galaxy A03 Core / A04e, Redmi A2, Tecno Spark Go | 2–3 GB | 10–13 (Go) | Presupuestos, sin señal, letra al 200 % |
| Gama media | Samsung Galaxy A14/A15, Redmi Note 12 | 4–6 GB | 13–14 | Flujo completo, Maestro |
| Reciente | Samsung Galaxy A54/A55, Pixel 7 | 8 GB | 14–15 | Regresiones visuales, modo oscuro |
| Emulador | AVD "Pixel 4a" Android 11 Go, 2 GB | 2 GB | 11 | Maestro en local |

### Presupuestos de rendimiento
Se miden con el APK de QA (Hermes, build de producción), nunca con Expo Go ni en modo desarrollo.

| Qué | Límite | Cómo medirlo |
| --- | --- | --- |
| Arranque en frío | < 3 s gama media, < 5 s gama baja | `adb shell am force-stop uk.top8.kuulis.qa && adb shell am start -W -n uk.top8.kuulis.qa/.MainActivity` → `TotalTime` (mediana de 5) |
| Tamaño del APK | < 60 MB | Tamaño del archivo que publica el builder (admin → Versiones) |
| Memoria en un viaje de 30 min | estable (sin subir más de 15 %) | `adb shell dumpsys meminfo uk.top8.kuulis.qa` al inicio, a los 15 y a los 30 min (`TOTAL PSS`) |
| Mapa con la moto moviéndose | 60 fps (≥ 55 en gama baja) | `adb shell dumpsys gfxinfo uk.top8.kuulis.qa reset`, 1 min en pantalla de viaje, `dumpsys gfxinfo` → "Janky frames" < 5 % |
| Datos del motorizado conectado 8 h | < 30 MB | Ajustes → Datos móviles de la app, o `adb shell dumpsys netstats detail` |
| Batería del motorizado conectado 8 h | < 35 % | `adb shell dumpsys batterystats --reset`, 8 h conectado, `dumpsys batterystats uk.top8.kuulis.qa` |

La ubicación se envía cada 4 s por defecto (`location_intervals` en el control remoto del admin, doc 10). Si
el consumo de batería o datos pasa del límite en gama baja, subir `online_seconds` (sin viaje) a 8–10 s desde
el admin, sin publicar código.

### Sin conexión
- Historial de viajes, detalle de cada viaje, billetera (saldo, movimientos, recargas, cuota), perfil del
  motorizado, lugares guardados y configuración se guardan en el teléfono (`lib/queryPersistence.ts`, 7 días)
  y se muestran al abrir la app sin señal. El viaje activo no se guarda: lo da siempre la API.
- La sesión no se cierra por falta de señal: se abre con el último perfil y se vuelve a leer al volver la red.
- Llegué / Iniciar / Finalizar, los mensajes del chat y las calificaciones pasan por una cola (`lib/outbox.ts`)
  guardada en un archivo, con `Idempotency-Key`: se reintentan solos al volver la señal y la API los aplica una
  sola vez. Pedir un viaje no se encola: sin conexión el botón queda desactivado con un aviso.
- Pedir viaje, cancelar, recargas, reclamos y transferencias usan `apiOnce`: mismo `Idempotency-Key` en el
  reintento, para que una respuesta perdida no cree un segundo viaje o una segunda transferencia.

### Pruebas
- `npm test`: lógica, i18n, contraste AA de los colores del tema, códigos de error traducidos y pantallas con
  React Native Testing Library (`__tests__/components/`: viaje del motorizado sin señal, calificación,
  registro de motorizado, billetera sin conexión).
- Códigos de error: `api/` exporta todos los `code` con `python manage.py error-codes` a
  `src/i18n/api-error-codes.json`. Un test de la app falla si alguno no tiene texto en es/en (los del panel
  admin están en `src/i18n/apiErrors.ts`) y un test de la API falla si el archivo no está al día.

### Pruebas E2E con Maestro
Flujos en `.maestro/` contra QA con el APK de QA instalado: registro, recarga manual, reporte, y el viaje
completo con dos dispositivos (`scripts/viaje-completo.sh`: pasajero en uno, motorizado en otro; el PIN de
inicio se lee de la API de QA). `motorizado-sin-senal.yaml` es el criterio de aceptación del doc 20 (un minuto
en modo avión al finalizar).

```bash
curl -fsSL "https://get.maestro.mobile.dev" | bash      # una vez
export PASSENGER_EMAIL=… PASSENGER_PASSWORD=… DRIVER_EMAIL=… DRIVER_PASSWORD=…
maestro test .maestro/registro.yaml
maestro test -e DRIVER_EMAIL=$DRIVER_EMAIL -e DRIVER_PASSWORD=$DRIVER_PASSWORD .maestro/recarga-manual.yaml
./.maestro/scripts/viaje-completo.sh                      # dos emuladores o teléfonos conectados por adb
```

### Accesibilidad
- Contraste AA (4,5:1) de cada texto sobre su fondo, en claro y oscuro: test `accessibility.test.ts`.
- Toques de al menos 48 dp (`MIN_TOUCH` en `components/ui.tsx`; los botones pequeños y los chips agrandan el
  área de toque) y 68 dp en las acciones del viaje del motorizado.
- Letra del sistema: los textos crecen hasta 160 % y los botones hasta 130 % (`maxFontSizeMultiplier`), así
  nada se corta con la letra del sistema al 200 %.
- Revisión manual con TalkBack antes de cada APK: inicio, pedir viaje, viaje en curso, conducir, billetera y
  calificar se leen en orden y cada botón dice qué hace.

### Mapas
Android usa Google Maps (`react-native-maps`) con la clave `GOOGLE_MAPS_ANDROID_API_KEY`. El Maps SDK para
Android no cobra por cargas de mapa en apps móviles, pero exige la clave con restricción por paquete y huella
del certificado (`com.kuulis.app` y `uk.top8.kuulis.qa`). Rutas y búsqueda ya son propias (OSRM y Photon, doc
02). Si Google cambia las condiciones, la alternativa es MapLibre con teselas propias (OpenMapTiles en el VPS):
cambia solo `components/map/RideMap.tsx`, que es la única pieza que dibuja mapas.
