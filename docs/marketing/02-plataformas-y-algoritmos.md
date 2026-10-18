# 02 · Plataformas: cómo reparten el contenido y qué exige cada una

Los algoritmos cambian a menudo y ninguna plataforma publica su fórmula completa. Lo de abajo es lo que las
propias plataformas han explicado en sus centros de ayuda y lo que se observa de forma consistente en 2026.
El agente analista (ver [08](08-arquitectura-de-agentes.md)) revisa este documento cada mes con los datos
propios y lo corrige.

## 1. Lo común a los tres formatos cortos
- **El reparto es por prueba.** Cada video se muestra primero a un grupo pequeño. Si ese grupo lo ve
  completo, lo repite, lo comparte o lo guarda, se muestra a un grupo más grande, y así sucesivamente. Los
  seguidores importan menos que en el pasado: una cuenta nueva puede llegar lejos con un buen video.
- **Los primeros 1 a 3 segundos deciden.** Si la gente desliza al instante, el video muere.
- **Retención y repetición** (ver hasta el final, volver a verlo) pesan más que los «me gusta».
- **Compartidos y guardados** son las señales más fuertes de valor; los compartidos por mensaje privado
  (DM, WhatsApp) son oro para una marca local.
- **Originalidad:** las tres penalizan contenido reciclado con marca de agua de otra red o sin
  transformación. Se exporta **una versión limpia por plataforma**, sin el logo de TikTok en Reels ni Shorts.
- **Texto en pantalla y subtítulos:** gran parte de la gente ve sin sonido. Todo video lleva subtítulos
  quemados, legibles y fuera de las zonas que tapan los botones.

## 2. Ficha por plataforma

| | TikTok | Instagram Reels | YouTube Shorts |
| --- | --- | --- | --- |
| Formato | 9:16, 1080×1920 | 9:16, 1080×1920; portada 1080×1440 (se ve 4:5 en el perfil) | 9:16, 1080×1920 |
| Duración que suele rendir para Kuulis | 15 a 45 s | 7 a 30 s | 20 a 50 s |
| Duración máxima | Varios minutos | Hasta 3 min | Hasta 3 min |
| Zona segura de texto | Evitar el 20 % inferior y la franja derecha (botones) | Evitar el 20 % inferior | Evitar el 15 % inferior y la derecha |
| Qué premia | Retención, repetición, compartidos, comentarios; tendencias de audio | Compartidos por DM, guardados, originalidad; alcance a no seguidores | Retención y tiempo de visión; búsquedas; vive más tiempo |
| Carruseles de fotos | Sí (photo mode), funcionan muy bien para explicaciones | Sí, y se recomiendan por guardados | No (Posts de comunidad aparte) |
| Música | **Cuenta empresa: solo la biblioteca comercial (Commercial Music Library)** | Cuenta empresa: biblioteca con licencia limitada | Biblioteca de audio de YouTube libre |
| Enlace | En la bio (cuenta empresa) | En la bio, en historias con sticker, en comentarios por DM automatizado | En la descripción del canal; los enlaces en Shorts están limitados |
| Publicación por API | Content Posting API, **exige auditoría**; sin ella los videos quedan privados | Graph API con cuenta Business o Creator vinculada a una página de Facebook | YouTube Data API; proyectos sin verificar suben como privados |
| Métricas por API | Display API (vistas, likes, comentarios, compartidos por video) y API for Business para cuentas empresa | Insights API (alcance, reproducciones, guardados, compartidos) | YouTube Analytics API (vistas, retención, fuentes) |

Las cifras de duración que rinden son un **supuesto inicial**; se ajustan con los datos propios en F1.

## 3. TikTok
- **Rol:** laboratorio de ideas y principal motor de descubrimiento.
- **Cuenta:** empresa (Business) por seguridad legal con la música y por las métricas. Contrapartida: no
  se pueden usar las canciones de moda que no estén en la biblioteca comercial. Se compensa con **audio
  original** (voz del personaje, sonidos de la calle, el «tin» de una notificación de viaje) que otros pueden
  reutilizar.
- **Formatos fuertes para Kuulis:** reacción a precio («¿Cuánto te cobraron de Chacao a Altamira?»),
  POV de motorizado, carrusel de fotos con cuentas («$3 de carrera: así se reparte en otras apps vs Kuulis»),
  respuestas en video a comentarios, dúos y stitches.
- **Comunidad:** responder todos los comentarios las primeras 2 horas; responder en video a las preguntas
  frecuentes (es contenido gratis y el algoritmo lo premia).

## 4. Instagram
- **Rol:** vitrina y canal de confianza (la gente revisa el perfil antes de instalar una app desconocida).
- **Perfil:** bio con propuesta en una línea, enlace a `/descargar` con UTM, historias destacadas fijas:
  «Cómo pido», «Motorizados», «Seguridad», «Instalar en Android», «Precios».
- **Formatos:** Reels (alcance), carruseles (guardados y explicación de la cuota), historias diarias con
  encuestas y preguntas (relación), colaboraciones (Collab posts) con creadores caraqueños.
- **Automatización útil:** respuesta por DM a quien comente una palabra («MOTO» → le llega el enlace de
  registro de motorizado). Se hace con la API oficial de mensajes de Instagram, sin bots no oficiales.

## 5. YouTube Shorts
- **Rol:** alcance extra y búsqueda («cómo pedir moto en Caracas», «app mototaxi Caracas»).
- Se suben las mismas piezas sin marca de agua, con título que contenga la búsqueda.
- A mediano plazo, un video largo mensual (por ejemplo, «un día con un motorizado de Kuulis») alimenta
  los Shorts y da profundidad.

## 6. WhatsApp y Facebook
- **Estados de WhatsApp** del número de soporte y de los motorizados aliados: versión de 15 a 30 s de cada
  pieza, con texto grande.
- **Canal de WhatsApp de Kuulis:** novedades, promociones y zonas nuevas. Bajo esfuerzo, alta lectura en
  Venezuela.
- **Facebook:** Reels cruzados desde Instagram y grupos de motorizados y de barrios (con cuidado de no hacer
  spam: se participa, no se pega el enlace en todos los grupos).

## 7. Horarios
No hay una hora mágica universal. **Supuesto de partida** para Caracas (hora de Venezuela, UTC−4):
mañana 6:30–8:00 (camino al trabajo), mediodía 12:00–13:30 y noche 19:00–22:00. En F1 se publica el mismo
tipo de pieza en franjas distintas y el analista fija los horarios con datos propios a la semana 3.
