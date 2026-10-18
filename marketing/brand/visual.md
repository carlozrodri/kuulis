# Identidad visual en redes

Misma marca que la web y la app (`web/app/assets/css/tokens.css`, `docs/product/mobile-design.md`). Aquí no se
inventan colores nuevos: solo se dice cómo se usan en video corto.

## Color
| Uso | Color | Hex |
| --- | --- | --- |
| Verde Kuulis (campos de color, chaqueta de Kuu) | `--primary` | `#0E7C5A` |
| Verde profundo (fondos, Ávila) | `--primary-deep` | `#0A5C43` |
| Amarillo del punto (cifra clave, punto final, detalle de Kuu) | `--accent` | `#FFC83D` |
| Noche (fondos oscuros, «Kuulis de noche») | `--night` | `#07120E` |
| Tinta (contorno de subtítulos) | `--text` | `#14201B` |
| Blanco | — | `#FFFFFF` |

Reglas: el amarillo es solo para **una** cosa por pantalla (la cifra o el punto). Nunca texto amarillo sobre
fondo claro. Nada de degradados de colores ajenos a la marca.

## Tipografía
- **Titulares de cartel:** Archivo condensado y pesado (el de la web, `Archivo Poster`), en mayúsculas o frase
  corta, terminando en el **punto amarillo**: «LO QUE COBRAS ES TUYO.»
- **Subtítulos y textos:** Plus Jakarta Sans, peso 700, blanco con contorno tinta de 6 px o caja tinta al 70 %.
- Las dos fuentes tienen licencia libre (SIL OFL); las plantillas de Remotion las cargan desde el repo.

## Formato y zonas seguras (1080×1920)
```
┌──────────────────────────┐ 0
│  margen superior 150 px  │   (hora, cuenta, botón seguir)
│                          │
│   ZONA SEGURA DE TEXTO   │   ancho útil: x 60–900 (deja ~180 px a la derecha para los botones)
│                          │
│                          │
├──────────────────────────┤ 1500
│  margen inferior 420 px  │   (caption, música, barra de navegación)
└──────────────────────────┘ 1920
```
- Gancho y cifras: tercio superior de la zona segura (y 250–700).
- Subtítulos: y 1150–1450.

## Firma de marca
- **Cierre** de 1 segundo: fondo verde, logotipo «kuulis.» blanco con el punto amarillo que «aterriza».
  Nunca al inicio (el inicio es del gancho).
- **Marca de agua:** ninguna. Las redes ya muestran la cuenta.

## Imágenes generadas con IA
- Caracas reconocible: el Ávila, avenidas con motos, edificios de Chacao y Altamira, aceras con quioscos; luz de
  hora dorada o noche con farolas cálidas (coherente con «Kuulis de noche» de la web).
- **Prohibido:** banderas, símbolos políticos, fachadas o logotipos de negocios reales, matrículas legibles
  que no sean inventadas, uniformes de cuerpos de seguridad, personas reales reconocibles, menores.
- Casco puesto en toda persona sobre una moto. Conducción tranquila.
- Revisar manos, dientes, texto y placas en cada imagen (errores típicos de la IA).
