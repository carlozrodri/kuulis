# marketing/

Material de trabajo del contenido en redes de Kuulis. El plan está en
[`docs/marketing/`](../docs/marketing/README.md); aquí vive lo que usan a diario los agentes y las personas.

| Carpeta | Qué hay | Quién lo usa |
| --- | --- | --- |
| [`brand/`](brand/) | Hechos permitidos, tono, identidad visual, biblia del personaje «Kuu», autorización de imagen | Todos los agentes, sobre todo guionista y revisor |
| [`playbooks/`](playbooks/) | Fórmulas de ganchos, guía por plataforma, hashtags | Estratega, guionista, publicador |
| [`guiones/`](guiones/) | Plantilla de guion y guiones (empezando por los 5 de la prueba de herramientas) | Guionista, productor |

Reglas:
- Los archivos de video e imagen **no van a git**: se guardan en S3 (bucket `kuulis-marketing`, ver
  [`docs/marketing/09`](../docs/marketing/09-registro-datos-y-medicion.md)). Aquí solo texto.
- Un cambio en `brand/` cambia lo que dicen todos los agentes: va por PR y lo aprueba Carlos.
- Los playbooks se actualizan con lo que el recomendador **demuestra** con datos, citando las piezas.
