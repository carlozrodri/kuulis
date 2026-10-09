# Diseño de la app móvil

## Decidido
- La app tiene que verse **de primer nivel mundial**: que al verla den ganas de usarla.
- Referencia visual: **Yummy Rides**. Carlos compartió 9 screenshots (2026-10-09), guardados en
  `docs/product/references/yummy/`. Son inspiración de calidad y patrones, **no** algo a copiar: Kuulis necesita
  su propia marca (colores, logo, ilustraciones).

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

## Análisis de las referencias de Yummy
| Screenshot | Qué muestra | Qué tomamos para Kuulis |
| --- | --- | --- |
| `01-elegir-modo` | Al abrir: elegir **Pasajero** o **Motorizado**, se puede cambiar cuando quiera | Igual: una sola app y una cuenta con dos modos (coincide con lo planeado) |
| `02-login-motorizado` | Cabecera con degradado, login por teléfono o email, botón grande "Regístrate como conductor" con el gancho "100 % de tus ganancias por 30 días" | Mismo patrón con nuestro gancho: "**3 meses gratis y sin comisión nunca**" |
| `03-requisitos-motorizado` | Antes de registrarse ve la lista de requisitos (edad, documentos, año del vehículo) | Igual, con nuestra lista de documentos; reduce rechazos en la aprobación |
| `04-solicitud-motorizado` | Solicitud por pasos con barra de progreso; tipo de servicio con ilustraciones 3D y ciudad | Registro por pasos con progreso. Al inicio solo "personas en moto" |
| `05-inicio-pasajero` | Inicio con buscador "¿A dónde vamos?", tasa en Bs arriba a la derecha, tarjetas de servicios, banners y barra inferior con botón central flotante | Buscador arriba, tasa visible y barra inferior con botón central para pedir viaje. Sin las secciones de comida, mercado, etc. |
| `06-tasa-de-cambio` | Panel inferior con conversor USD ⇄ Bs (tasa BCV) | Igual, pero con **dos tasas**: BCV y Binance |
| `07-ruta-y-precio` | Mapa con la ruta dibujada y el tiempo, panel inferior con el precio, precio tachado por promoción y "Primer viaje gratis" | Igual. Agregamos el equivalente en Bs debajo del precio en USD |
| `08-lista-de-servicios` | Lista de tipos de vehículo con ilustración, capacidad, precio y promociones | Solo una opción (Moto) al inicio; la lista ya queda lista para carros |
| `09-lista-envios` | Pestaña de envíos ("Mandaditos") | Fuera del alcance por ahora |

### Patrones visuales que adoptamos
- Fondo lila muy claro, tarjetas blancas con bordes suaves y esquinas de 16–24 px.
- Un color de marca fuerte para el botón principal (ancho completo, en forma de píldora, texto en mayúsculas).
- Ilustraciones 3D de vehículos y personajes, que dan mucha personalidad. Habrá que encargarlas o generarlas
  con la marca de Kuulis.
- Tipografía geométrica y redondeada (parecida a Montserrat), con títulos en negrita.
- Paneles inferiores deslizables sobre el mapa, con una manija arriba.
- Precio grande y en color de marca; descuentos con el precio original tachado y etiquetas de promoción.

### Diferencias a propósito
- **Precio fijo:** Yummy tiene "Cuádralo" (el pasajero propone el precio). En Kuulis el precio lo fija la app.
- **Sin suscripción para pasajeros:** Yummy vende "Prime" al pasajero. En Kuulis solo pagan los motorizados.
- **Identidad propia:** no usar el morado de Yummy, para no parecer una copia.

## Siguiente paso
Con los screenshots de Carlos: extraer paleta, tipografía, componentes y patrones, y armar un sistema de
diseño (colores, tipografía, espaciado, componentes) antes de escribir pantallas.
