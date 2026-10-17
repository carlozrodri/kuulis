# 04 · UX e interacción

## 1. Puntos de corte y comportamiento general
| Nombre | Ancho | Qué cambia |
| --- | --- | --- |
| `xs` | 320–379 px | Teléfonos pequeños (Android de gama baja). Márgenes de 16 px, display mínimo 2,75 rem |
| `sm` | 380–599 px | Teléfonos grandes. Márgenes de 20 px |
| `md` | 600–959 px | Tabletas y teléfonos en horizontal. Composiciones de 2 columnas en secciones con imagen |
| `lg` | 960–1279 px | Portátiles. Rejilla de 12 columnas, navegación completa |
| `xl` | ≥ 1280 px | Escritorio grande. Contenedor máximo 1200 px; los campos de color siguen a sangre |

- Diseño desde `xs` hacia arriba. Tipografía y espacios fluidos con `clamp()`; solo 3 media queries de layout
  (`600`, `960`, `1280`).
- Altura del hero en móvil: el titular, el lead y el CTA principal caben en la primera pantalla de un teléfono
  de 360×640; la captura empieza a asomar debajo (nunca un hero de 100 vh que esconda el CTA).
- Ninguna página desborda en horizontal a 320 px (comprobado con Playwright en 08).

## 2. Cabecera
- Fija arriba. Sobre el hero verde es transparente con texto blanco; al pasar el hero (`IntersectionObserver`
  sobre un centinela, sin escuchar el scroll) cambia a fondo sólido `--bg` con borde inferior, en 200 ms.
  Sin `backdrop-filter`.
- Altura 64 px en móvil, 72 px en escritorio.
- Enlace activo: punto amarillo de 6 px bajo el texto (sobre fondo claro se usa verde, por contraste).
- CTA «Descargar» siempre visible, también en móvil (compacto, 40 px de alto, con zona táctil de 44 px).

## 3. Menú móvil
- Botón de menú de 44×44 px con `aria-expanded`, `aria-controls` y etiqueta «Abrir menú» / «Cerrar menú».
- Abre un panel a pantalla completa con fondo `--text` (tinta), enlaces de 1,75 rem y el selector de idioma.
  Entra con opacidad + 8 px de desplazamiento, 200 ms.
- Mientras está abierto: el foco queda dentro del panel, `Escape` lo cierra y devuelve el foco al botón, el
  resto de la página es `inert` y no se desplaza (`overflow: hidden` en `html`).
- Se cierra al navegar y al cambiar de idioma (como hoy).
- Funciona sin JavaScript: los enlaces del menú también están en el footer.

## 4. Selector de idioma
- Botón con el **nombre del otro idioma en su propio idioma** («English» desde español, «Español» desde inglés),
  con `lang` correspondiente y `hreflang` en el enlace. En escritorio, forma compacta «EN» / «ES» con texto
  accesible completo.
- Es un **enlace** a la misma página en el otro idioma (con URLs `/en`, ver 06), no un botón que cambia el
  estado: se puede abrir en otra pestaña, compartir e indexar. Conserva la ruta equivalente
  (`/motorizados` ↔ `/en/drivers`) y la query string (`/ayuda?q=…`).
- Guarda la preferencia en la cookie `kuulis_locale` (como hoy). La detección por navegador solo redirige en la
  raíz `/` y solo la primera vez.

## 5. Botones y enlaces
| Elemento | Reposo | Hover (punteros finos) | Pulsado | Foco | Deshabilitado |
| --- | --- | --- | --- | --- | --- |
| Botón principal sobre verde/tinta | Amarillo, texto `#3A2A00` | Amarillo 6 % más oscuro | Escala 0,98, 120 ms | Anillo de dos tonos | 55 % opacidad, `cursor: not-allowed` |
| Botón principal sobre claro | Verde, texto blanco | `--primary-pressed` | Escala 0,98 | Anillo de dos tonos | Igual |
| Botón secundario | Contorno 2 px `currentColor` | Fondo 8 % del color del texto | Escala 0,98 | Anillo | Igual |
| Enlace de texto | Subrayado 1 px, offset 3 px | Subrayado 2 px | — | Anillo | — |
| Enlace con flecha («Ver requisitos →») | Flecha en su sitio | Flecha se desplaza 3 px a la derecha, 200 ms | — | Anillo | — |

- Alturas: 52 px (como hoy) para CTAs, 44 px mínimo para cualquier objetivo táctil.
- Los efectos de hover solo con `@media (hover: hover)`, para que no se queden «pegados» en Android.

## 6. Animaciones (lista completa)
| # | Qué | Disparo | Duración / curva | Con movimiento reducido |
| --- | --- | --- | --- | --- |
| 1 | La ruta del hero se dibuja y el punto «llega» | Carga, una vez, tras el primer pintado | 1,1 s `cubic-bezier(.2,.7,.2,1)` + 240 ms | Ruta y punto ya dibujados |
| 2 | Aparición de secciones (16 px + opacidad) | Entra al 15 % del viewport, una vez | 320 ms `ease-out` | Visibles desde el inicio |
| 3 | Captura del hero sube 24 px | Con la #1 | 600 ms | Estática |
| 4 | Cabecera transparente → sólida | Centinela | 200 ms | Cambio instantáneo |
| 5 | Panel del menú móvil | Abrir/cerrar | 200 ms | Instantáneo |
| 6 | FAQ: abrir `<details>` | Clic | Contenido aparece con opacidad 160 ms | Instantáneo |
| 7 | Botones, enlaces, flechas | Hover/pulsar | 120–200 ms | Sin transición |

Reglas: solo `transform` y `opacity` (la ruta usa `stroke-dashoffset`, barato en un SVG pequeño); nunca se
oculta contenido esperando a JavaScript — sin JS, todo se ve en su estado final (la clase que oculta para animar
se añade desde JS). Nada se mueve en bucle.

## 7. Recorridos principales
### 7.1 Pasajero con Android que llega por un enlace de WhatsApp (ES)
1. Ve el hero: qué es, precio claro, botón amarillo.
2. Toca «Descargar para Android» → `/descargar`: ve la versión, tamaño y el botón grande.
3. Toca «Descargar Kuulis (APK)» → el navegador descarga → sigue los 4 pasos ilustrados.
Criterio: desde la llegada hasta el inicio de la descarga, 2 toques.

### 7.2 Pasajero con iPhone
1. Toca cualquier CTA de descarga → `/descargar` detecta iPhone y muestra primero el aviso honesto («todavía no
   hay app para iPhone»), sin botón de APK inútil delante.
Sin callejones: ofrece enlaces a Seguridad, Ayuda y, si existe, al canal donde se anunciará.

### 7.3 Motorizado
Inicio → sección 0 % → «Ver requisitos y cuota» → `/motorizados` → revisa tabla y requisitos → «Descargar la app».

### 7.4 Visitante en inglés
Llega a `/en` (por enlace, por buscador o por redirección de la raíz si su navegador está en inglés) → todo en
inglés, incluidos títulos, descripciones, imágenes OG y textos alternativos → cambia a español y llega a la
página equivalente.

### 7.5 Familiar con enlace `/v/{token}`
Sin cambios de lógica. Hereda la cabecera, el footer y los tokens nuevos; el mapa y los avisos de SOS conservan
su prioridad visual.

## 8. Estados de datos de la API
Cada bloque que depende de `/public/site` o `/app/version` tiene estado sin datos:
| Bloque | Si la API no responde |
| --- | --- |
| Tabla de cuota | Se oculta; el texto no menciona cifras (hoy ya se oculta) |
| Ciudades | «Caracas» como valor por defecto (igual que hoy) |
| Métodos de pago | Se oculta la fila de chips |
| `{max}` en el texto de motorizados | Variante del texto sin la cifra («con un tope bajo») |
| APK | Tarjeta «Muy pronto» (igual que hoy) |

## 9. Accesibilidad (WCAG 2.2 AA)
- **Semántica:** un `h1` por página; jerarquía sin saltos; `header`, `nav` con nombre, `main`, `footer`; listas
  reales para pasos y filas; `table` con `th` y `caption` para la cuota.
- **Teclado:** todo operable con teclado; orden de foco = orden visual; enlace «Saltar al contenido» visible al
  recibir foco; sin trampas salvo el menú abierto (intencional y con Escape).
- **Foco:** anillo de dos tonos (tinta + amarillo) visible sobre cualquier fondo, de al menos 2 px (2.4.11 / 2.4.13).
- **Contraste:** texto ≥ 4,5:1, texto grande y componentes ≥ 3:1. Ver tabla de 00 §3 y reglas de 02 §5.
- **Tamaño de objetivos:** ≥ 24×24 px siempre (2.5.8) y ≥ 44×44 px en los táctiles principales.
- **Imágenes:** capturas con `alt` descriptivo y traducido («Pantalla de la app de Kuulis con el precio del viaje
  en dólares y bolívares»); gráficos de marca con `aria-hidden="true"`; el `PinDigits` con texto alternativo que
  dice que es un ejemplo.
- **Idioma:** `<html lang>` correcto; fragmentos en el otro idioma con `lang`.
- **Movimiento:** `prefers-reduced-motion` respetado (§6); nada parpadea.
- **Zoom y reflow:** usable al 200 % de zoom y a 320 px CSS sin desplazamiento horizontal (1.4.10).
- **Formularios** (contacto, ayuda): se mantienen etiquetas, mensajes de error asociados (`aria-describedby`) y
  estados actuales.
- **`.sr-only`** corregido al patrón completo (con `margin: -1px; padding: 0; border: 0`).

## 10. Modo oscuro
Se mantiene siguiendo al sistema (`prefers-color-scheme`). Sin selector manual en este proyecto (lo añadiría
complejidad y JS sin una petición real). Cada milestone visual se revisa en claro y oscuro.
