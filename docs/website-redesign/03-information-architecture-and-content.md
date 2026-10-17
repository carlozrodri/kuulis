# 03 · Arquitectura de información y contenido

Todo el texto de este documento es propuesta (Supuesto) hasta que Carlos lo apruebe. Los datos entre llaves
(`{months}`, `{max}`) salen de la API en tiempo real; nunca se escriben a mano.

## 1. Mapa del sitio
| Página | URL español (por defecto) | URL inglés (propuesta) | Cambio |
| --- | --- | --- | --- |
| Inicio | `/` | `/en` | Rediseño completo |
| Motorizados | `/motorizados` | `/en/drivers` | Rediseño completo |
| **Seguridad** | `/seguridad` | `/en/safety` | **Nueva** (las funciones ya existen en la app) |
| Descargar | `/descargar` | `/en/download` | Rediseño; misma lógica |
| Ayuda | `/ayuda`, `/ayuda/[slug]` | `/en/help`, `/en/help/[slug]` | Estilos nuevos; misma lógica |
| Contacto | `/contacto` | `/en/contact` | Estilos nuevos; misma lógica |
| Legal | `/legal`, `/legal/[kind]` | `/en/legal`, `/en/legal/[kind]` | Estilos nuevos |
| Viaje compartido, invitación, verificar email, cambiar contraseña | `/v/…`, `/i/…`, `/verify-email`, `/reset-password` | Sin cambio de URL (emails y app ya enlazan ahí); idioma por cookie como hoy | Solo estilos |

Las URLs en inglés dependen de la pregunta 1 del README. Si Carlos dice que no, todo sigue en las URLs actuales
con el idioma por cookie, y se pierde la indexación del inglés (ver 06 §4).

**Por qué no hay página «Pasajeros»:** el pasajero es el público principal; la página de inicio es su página.
**Por qué no hay «Nosotros»:** no hay empresa registrada ni equipo público; una página vacía resta credibilidad.
Se puede añadir cuando exista algo real que contar.

## 2. Navegación
**Cabecera (escritorio):** logotipo · Motorizados · Seguridad · Ayuda · selector de idioma · botón «Descargar».
**Cabecera (móvil):** logotipo · botón «Descargar» (siempre visible, compacto) · botón de menú. El menú abre un
panel a pantalla completa (ver 04) con los enlaces grandes, el selector de idioma y los enlaces legales al pie.
«Legal» sale de la cabecera: vive en el footer, donde se busca.

## 3. Footer
| Columna | Enlaces |
| --- | --- |
| Marca | Logotipo, lema, silueta del Ávila |
| Kuulis | Viajar (inicio), Motorizados, Seguridad, Descargar |
| Ayuda | Centro de ayuda, Contacto, email de soporte y WhatsApp (solo si están configurados en `/config/public` o en `NUXT_PUBLIC_SUPPORT_EMAIL`) |
| Legal | Términos y condiciones, Política de privacidad, Normas de la comunidad, Términos para motorizados, Condiciones de la billetera |
| Pie | Selector de idioma · «© {año} Kuulis · Hecho en Caracas» |

Sin iconos de redes sociales: hoy no existen cuentas (si Carlos las tiene, se añaden; pregunta abierta en README).

## 4. Rutas de conversión
| Visitante | Ruta |
| --- | --- |
| Pasajero desde WhatsApp/Google | Inicio → hero «Descargar para Android» → `/descargar` → APK |
| Pasajero indeciso | Inicio → precio claro → seguridad → bloque final → `/descargar` |
| Motorizado | Inicio → «Quiero manejar» o sección 0 % → `/motorizados` → requisitos → `/descargar` |
| Motorizado invitado | `/i/{code}` → `/descargar` (o abre la app) |
| Familiar con enlace de viaje | `/v/{token}` (sin CTA nueva en este proyecto; posible mejora futura) |
| Con iPhone | Cualquier CTA → `/descargar` → aviso honesto «todavía no hay app para iPhone» |

## 5. Página de inicio: secciones, en orden
Cada sección tiene un solo trabajo. Junto a cada una, el texto propuesto en español (original) y en inglés
(escrito, no traducido).

### 5.1 Hero — campo verde
Trabajo: decir qué es y llevar a descargar.

**Titular, opción A (recomendada)**
- ES: «En moto por Caracas. Precio claro, y punto.»
- EN: «Across Caracas by motorbike. A clear price, full stop.»

Opción B — ES: «Pide tu moto. Mira el precio. Y punto.» · EN: «Book a bike. See the price. That's it.»
Opción C — ES: «Tu moto, sin regateo.» · EN: «Your ride, no haggling.»

- Lead ES: «Antes de pedir ves cuánto cuesta en dólares y en bolívares, sabes quién te va a buscar y le pagas
  directo al motorizado, como acuerden.»
- Lead EN: «See the fare in dollars and bolívares before you book, know exactly who's coming to pick you up, and
  pay your driver directly, however you both prefer.»
- CTA principal: «Descargar para Android» / «Download for Android» → `/descargar`
- CTA secundario: «Quiero manejar» / «Drive with Kuulis» → `/motorizados`
- Nota bajo los botones: «Gratis. Por ahora, solo para Android.» / «Free. Android only, for now.»
- Visual: captura real de la pantalla de inicio o de cotización de la app en `PhoneFrame`, entrando desde abajo;
  la ruta se dibuja desde el teléfono y termina en el punto del titular. Silueta del Ávila en la base.

### 5.2 Precio claro — fondo claro
Trabajo: probar con el producto real que el precio está claro.
- H2 ES: «Sabes el precio antes de subirte.» · EN: «You know the price before you get on.»
- Cuerpo ES: «La app calcula el viaje por distancia y tiempo y te lo muestra en dólares, con su equivalente en
  bolívares a tasa BCV y Binance. Ese es el precio, para ti y para el motorizado.»
- Cuerpo EN: «The app works out the fare from distance and time and shows it in dollars, alongside the bolívar
  amount at both the BCV and Binance rates. That's the price, for you and for your driver.»
- Tres filas (no tarjetas), con línea divisoria:
  1. «Dólares y bolívares» / «Dollars and bolívares» — «Las dos tasas a la vista, para que nadie saque cuentas en
     la calle.» / «Both rates on screen, so nobody has to do the maths on the street.»
  2. «Pagas como acuerden» / «Pay however you agree» — chips con los métodos de `/public/site`
     (Efectivo $, Efectivo Bs, Pago móvil, Zelle, Binance).
  3. «Sin regateo» / «No haggling» — «El precio lo pone la app, no la discusión.» / «The app sets the price, not
     an argument.»
- Visual: captura real de la cotización (precio USD + Bs), recortada por el borde.

### 5.3 Cómo funciona — fondo claro, la ruta con tres paradas
- H2 ES: «Tres paradas y llegaste.» · EN: «Three stops and you're there.»
- Paradas (sobre la línea de ruta, la última es el punto amarillo):
  1. ES «Pide» — «Escribe a dónde vas y mira el precio.» · EN «Book» — «Tell us where you're going and see the price.»
  2. ES «Te buscan» — «Ves el nombre, la foto, la moto y la placa de quien va en camino.» · EN «Get picked up» —
     «See the name, photo, bike and plate of the driver on the way.»
  3. ES «Llegas y pagas» — «Le pagas directo al motorizado y califican el viaje.» · EN «Arrive and pay» — «Pay
     your driver directly, then rate the ride.»
- Debajo: «Disponible en: {cities}» / «Available in: {cities}» (de la API).

### 5.4 Motorizados — campo tinta
Trabajo: el diferencial más fuerte, con un número.
- Número héroe en amarillo: **0 %**
- H2 ES: «De cada viaje, Kuulis se queda con 0 %.» · EN: «Kuulis takes 0% of every ride.»
- Cuerpo ES: «Lo que te paga el pasajero es tuyo completo. Pagas una cuota mensual según lo que ganaste, con
  tope de {max}, y nada en los meses que no trabajas. Tus primeros {months} meses, nada.»
- Cuerpo EN: «Every dollar your rider pays is yours. You pay a monthly fee based on what you earned, capped at
  {max}, and nothing in months you don't drive. Your first {months} months are free.»
- Tabla real de la cuota (componente `FeeTable` restilizado).
- CTA: «Ver requisitos y cuota» / «See requirements and fees» → `/motorizados`.

### 5.5 Seguridad — fondo claro
- H2 ES: «Sabes quién te lleva. Y alguien de confianza también.»
- H2 EN: «You know who's driving you. So does someone you trust.»
- Cuatro filas con icono:
  1. «Motorizados verificados» — «Revisamos su cédula, licencia, certificado médico y los papeles de la moto antes
     de que puedan conectarse.» / «Verified drivers» — «We check their ID, licence, medical certificate and bike
     papers before they can go online.»
  2. «PIN de inicio» — «El viaje no empieza hasta que le dices tu PIN al motorizado.» / «Start PIN» — «The ride
     doesn't start until you give your driver your PIN.»
  3. «Viaje en vivo» — «Comparte un enlace y tu gente ve el viaje en el mapa hasta que llegues.» / «Live trip» —
     «Share a link so the people you trust can follow the ride on a map until you arrive.»
  4. «Botón SOS» — «Llama al 911 y avisa a tus contactos de confianza con tu ubicación.» / «SOS button» — «Calls
     911 and alerts your trusted contacts with your location.»
- Visual: `PinDigits` (gráfico, con dígitos de ejemplo y marcado como ilustración).
- Enlace: «Todo sobre seguridad» / «More on safety» → `/seguridad`.

### 5.6 Preguntas frecuentes — fondo claro
Se mantienen las 5 preguntas actuales con estos ajustes: la de iPhone dice «Todavía no. Por ahora Kuulis es solo
para Android; cuando haya versión para iPhone lo anunciaremos aquí.» / «Not yet. Kuulis is Android-only for now;
we'll announce an iPhone version here when it's ready.» Al final: «¿Otra duda? Visita el centro de ayuda.»

### 5.7 Descarga — campo verde
- H2 ES: «Instálala una vez. Muévete cuando quieras.» · EN: «Install it once. Ride whenever you need.»
- Cuerpo ES: «Kuulis se descarga desde esta web, no desde la Play Store. Te explicamos cómo, paso a paso, y cómo
  comprobar que el archivo es el nuestro.»
- Cuerpo EN: «You download Kuulis from this site, not from the Play Store. We'll walk you through it and show you
  how to check the file really comes from us.»
- CTA: «Descargar para Android» / «Download for Android». La ruta termina aquí, en el punto.

## 6. Motorizados (`/motorizados`)
1. **Hero (tinta):** H1 ES «Lo que cobras es tuyo.» · EN «What you earn is yours.» Lead ES «Kuulis no cobra
   comisión por viaje. Tú pones la moto y el tiempo; nosotros te traemos los viajes.» · EN «Kuulis charges no
   commission per ride. You bring the bike and the hours; we bring you the rides.» CTA «Descargar la app».
2. **El número:** «0 %» + tres filas: «Cero comisión», «{months} meses gratis desde tu primer viaje», «Tú decides
   cuándo te conectas» (textos actuales mejorados).
3. **Tu cuota, con números:** tabla real + ejemplo calculado con los tramos reales: ES «Ejemplo: si en un mes
   ganas $250, pagas {fee}. Te quedan {rest}.» · EN «Example: earn $250 in a month and you pay {fee}. You keep
   {rest}.» Nota: «Se paga desde tu billetera Kuulis. Si un mes no tienes viajes, no pagas nada.»
4. **Requisitos:** lista de `/public/site` (edad, año de moto, documentos, teléfono Android).
5. **Cómo registrarte:** los 4 pasos actuales sobre la línea de ruta.
6. **Preguntas de motorizados** (nuevas, todas verificables en `business-model.md`): «¿Desde cuándo cuentan los
   meses gratis?» (desde tu primer viaje completado), «¿Qué pasa si un mes no trabajo?» (no pagas), «¿Cómo cobro
   los viajes?» (el pasajero te paga directo), «¿Cómo pago la cuota?» (desde tu billetera Kuulis).
7. CTA final de descarga.

El programa de invitaciones (doc 22) no se anuncia en la web pública: su premio y condiciones cambian desde el
admin. Se explica en la app y en `/i/{code}`.

## 7. Seguridad (`/seguridad`, nueva)
- H1 ES «Viajar tranquilo también es parte del viaje.» · EN «Feeling safe is part of the ride.»
- Secciones: **Antes** (verificación de motorizados, ves nombre, foto, moto y placa), **Durante** (PIN de inicio,
  viaje en vivo, chat dentro de la app, pedir para otra persona con su propio enlace y PIN), **Si algo pasa** (SOS
  al 911 y a tus contactos; reportar un problema y objetos perdidos desde el historial), **Después** (calificación
  de los dos lados después de cada viaje; normas de la comunidad).
- Nota honesta al final, ES: «Kuulis no reemplaza a los servicios de emergencia. Si estás en peligro, llama al
  911.» · EN: «Kuulis doesn't replace emergency services. If you're in danger, call 911.»
- Antes de publicar, Claude verifica en la app cada función citada (ver 08).

## 8. Descargar (`/descargar`)
Misma lógica (APK, versión, tamaño, fecha, huella, detección de iPhone). Cambios: titular ES «Kuulis para
Android» se mantiene; los 4 pasos de instalación se ilustran con capturas reales del proceso en Android (ver 05);
el aviso de seguridad («Descarga Kuulis solo desde esta página…») pasa a ser un bloque destacado.

## 9. Estrategia de idiomas
- **Español primero.** Se escribe para Caracas: tuteo, «motorizado», «pago móvil», «cédula», «bolívares»,
  «moto». Sin voseo ni regionalismos de otros países.
- **Inglés escrito por y para nativos**, no traducido: «driver» (no «motorizado» ni «biker»), «rider»,
  «motorbike», «fare», «licence/license» según `en-US` (se usa `license`). Las marcas locales se dejan en
  original con explicación cuando haga falta («Pago Móvil, Venezuela's instant bank transfer»).
- Juegos de palabras: «y punto» funciona en inglés como «full stop». Si una frase no funciona en inglés, se
  escribe otra, no se fuerza.
- Revisión: Carlos aprueba el español; el inglés lo revisa Claude contra una lista de comprobación de calidad
  nativa (sin calcos, sin «Kuulis is the app that…»). Si Carlos tiene un hablante nativo de confianza, mejor.
- Cada texto vive en `web/i18n/locales/{es,en}.json`; un test comprueba que los dos archivos tienen exactamente las
  mismas claves (ver 06).

## 10. Contenido pendiente o a confirmar
| Dato | Estado | Qué hacer |
| --- | --- | --- |
| Dominio de producción | No existe | Las URLs canónicas usan `NUXT_PUBLIC_SITE_URL`, no se escriben a mano |
| Redes sociales | Desconocido | Pregunta en README; sin ellas no hay iconos |
| Email/WhatsApp de soporte | Configurables | Se muestran solo si están configurados (como hoy) |
| Versión mínima de Android | Desconocido para la web | No se menciona hasta confirmarla en `mobile/app.json` y en un teléfono real |
| Texto `invite.freeMonth` | Posiblemente obsoleto (doc 22) | Revisar en el milestone de páginas secundarias, sin tocar la lógica |
