# 04 · Calendario y flujo diario

## 1. Cadencia por fase
| Fase | TikTok | Instagram | YouTube Shorts | WhatsApp |
| --- | --- | --- | --- | --- |
| F1 · Arranque (sem. 1–4) | 2 videos/día | 1 Reel/día + 3–5 historias/día + 2 carruseles/semana | 1/día (reutilizado) | 1 estado/día; canal 2/semana |
| F2 · Tracción (sem. 5–12) | 2–3/día | 1–2 Reels/día + historias + 2 carruseles/semana | 1–2/día | igual |
| F3 · Escala (sem. 13+) | Según capacidad y datos | Según datos | Según datos | igual |

En F1 el objetivo es **volumen de pruebas**: unas 14 piezas originales por semana (2 por día), cada una
adaptada a tres plataformas. Con 2 piezas diarias, en 4 semanas hay unas 56 pruebas, suficiente para ver
patrones.

## 2. Semana tipo (F1)
| Día | Pieza A (mañana) | Pieza B (noche) |
| --- | --- | --- |
| Lunes | CUENTAS · F-CARRUSEL | CALLE · F-POV |
| Martes | CONFIANZA · F-HOST | CALLE · F-CALLE |
| Miércoles | PRECIO · F-PANTALLA («¿Cuánto es?») | GENTE · F-CALLE |
| Jueves | CUENTAS · F-HOST | CALLE · F-TENDENCIA |
| Viernes | COMO · F-PANTALLA | Todos · F-RESPUESTA |
| Sábado | CALLE · F-SKETCH | PRECIO · F-DATO |
| Domingo | GENTE · reposteo del mejor de la semana con gancho nuevo | Descanso o tendencia |

El calendario concreto de cada semana lo propone el agente estratega los domingos, a partir de esta plantilla
y de lo que aprendió el recomendador (ver [08](08-arquitectura-de-agentes.md)).

## 3. Flujo diario
```
06:00  Analista: recoge métricas de las últimas 24 h, 72 h y 7 días de cada publicación (API o carga manual).
06:30  Recomendador: actualiza el registro de aprendizajes y propone ajustes del día.
07:00  Guionista: escribe los guiones del día siguiente (2 piezas, 3 ganchos cada una) sobre el calendario.
07:30  Revisor de marca: valida hechos, tono, riesgos y disclosure. Rechaza o pide cambios.
08:00  Productor: prepara prompts y genera assets (IA o plantillas Remotion); lista de tomas para lo que se graba real.
       → Paquete del día en el hilo del proyecto: guion, ganchos, borrador del video, textos y hashtags por red.
       → Carlos aprueba, pide cambios o descarta (objetivo: 5 minutos al día).
Mañana / noche  Publicación en las franjas del calendario (manual en F1; ver abajo).
+2 h   Comunidad: respuestas a comentarios (el agente sugiere, una persona publica en F1).
Domingo  Informe semanal + calendario de la semana siguiente.
```
Los horarios son orientativos (hora de Venezuela). Lo importante es el orden: **datos → aprendizaje →
guion → revisión → producción → aprobación → publicación → datos**.

## 4. Quién publica
- **F1: publica una persona desde el teléfono**, con el paquete que dejan los agentes (video final, texto,
  hashtags, portada, enlace con UTM). Motivos: TikTok fuerza a privado lo que se publica por API sin
  auditoría; publicar desde la app permite usar los sonidos y las herramientas nativas; y reduce el riesgo de
  que una cuenta nueva sea marcada por automatización.
- **F2: Instagram y YouTube por API** (programado desde el sistema), TikTok sigue manual mientras se tramita
  la auditoría de su API.
- **F3: todo programado** desde el panel, con aprobación previa obligatoria.

Cada publicación manual se registra igual que una automática: quien publica pega el enlace de la publicación
en el panel (o en el hilo) y el sistema la asocia a la pieza (ver [09](09-registro-datos-y-medicion.md)).

## 5. Banco de contenido
Siempre debe haber **al menos 7 piezas aprobadas en reserva** para no depender del día a día (lluvia, apagón,
falta de internet, un día sin tiempo para aprobar). El estratega avisa cuando la reserva baja de 5.

## 6. Grabación real
Una **sesión semanal de grabación** de 2 a 3 horas con motorizados reales y en la calle produce el material de
F-CALLE, F-POV y GENTE para toda la semana. Quién graba lo decide Carlos (pregunta del README). Los agentes
entregan la lista de tomas, las preguntas para la calle y el formulario de autorización de imagen.

## 7. Reacción a tendencias
El estratega revisa tendencias dos veces al día (Centro Creativo de TikTok, audios en subida en Reels,
temas del momento en Caracas). Si encuentra una que encaja con la marca, propone una pieza **F-TENDENCIA**
con prioridad y plazo de 24 a 48 horas. Nunca se usan tragedias, política ni noticias sensibles.
