# 07 · Evaluación de `msitarzewski/agency-agents`

Repositorio revisado el **2026-10-18** (clonado, último commit del 2026-10-15):
<https://github.com/msitarzewski/agency-agents>.

## 1. Qué es
Una colección muy popular (unas 161 000 estrellas, licencia MIT) de **más de 230 «personalidades» de agentes**
escritas en Markdown, organizadas por departamentos (ingeniería, diseño, marketing, ventas, etc.). Cada agente
es un archivo con frontmatter (`name`, `description`, `color`) y secciones: identidad, misión, reglas,
entregables, flujo de trabajo y métricas de éxito. Trae scripts para instalarlos en Claude Code
(`~/.claude/agents/`), Cursor, Gemini CLI y otros.

En marketing hay 37 agentes: TikTok Strategist, Instagram Curator, Social Media Strategist, Content Creator,
Video Optimization Specialist (YouTube), Growth Hacker, Carousel Growth Engine, App Store Optimizer, y muchos
centrados en China (Douyin, Xiaohongshu, WeChat, Bilibili…). En `paid-media/` hay estrategas de pauta.

## 2. Lo que vale
- **La estructura** de cada agente (identidad, reglas, entregables, flujo, métricas) es buena y se puede copiar.
- **Carousel Growth Engine** describe un patrón que encaja con lo que Carlos quiere: generar → publicar por la
  API oficial → leer métricas → guardar aprendizajes en un archivo (`learnings.json`) → mejorar la siguiente
  pieza. Es la idea correcta.
- **Multi-Platform Publisher** tiene una regla sensata: **publicar como borrador y que una persona confirme**.
- Licencia MIT: se pueden reutilizar fragmentos citando la fuente.

## 3. Lo que no sirve tal cual
- **Son prompts genéricos, no un sistema.** No hay código que publique, mida ni guarde datos (salvo
  instrucciones para que el agente lo haga). No traen base de datos, ni registro, ni integración con
  ninguna API ya hecha.
- **No conocen Kuulis:** ni la marca, ni los hechos permitidos, ni Caracas, ni el modelo de cuota. Un
  «TikTok Strategist» genérico propondrá retos de hashtag de un millón de vistas y retornos 4:1 que no
  tienen base para una app nueva en Venezuela.
- **Cifras inventadas:** por ejemplo, el agente de TikTok fija «8 % de engagement (media del sector 5,96 %)»
  sin fuente. Justo lo que la marca no puede hacer.
- **Enfoque equivocado de público:** el de TikTok apunta a Generación Z y Alfa; el pasajero de Kuulis tiene
  18–45 años y el motorizado es adulto trabajador.
- **Autonomía peligrosa:** Carousel Growth Engine se define como «cero confirmación», publica sin aprobación.
  Para una marca nueva con cuentas nuevas eso es un riesgo de reputación y de bloqueo.
- **La mitad del departamento es para China** y no aplica.

## 4. Veredicto
**No instalarlo como sistema. Construir agentes propios de Kuulis, inspirados en su formato.**

- Se toman como referencia (con atribución MIT): la estructura de secciones, el bucle de aprendizaje de
  Carousel Growth Engine y la regla de borrador primero de Multi-Platform Publisher.
- Los agentes propios viven en el repo (ver [08](08-arquitectura-de-agentes.md)), llevan dentro la verdad de la
  marca, las reglas de [10](10-riesgos-y-cumplimiento.md) y leen datos reales de Kuulis, no cifras de manual.
- Coste de esta decisión: escribir 6–8 archivos de agente bien pensados, una vez. Es menos trabajo que limpiar
  37 agentes genéricos y mucho más fiable.
