# FantasyMarca — webapp

Sitio Astro + Tailwind, 100% estático. Para qué es esto y de dónde salen los
datos de `public/data/`, ver el [README de la raíz del repo](../README.md).

## Estructura

```
src/pages/         una carpeta/archivo por ruta (file-based routing de Astro)
src/components/    componentes .astro, incluidos los gráficos (src/components/charts/)
src/layouts/       Layout.astro envuelve todas las páginas (nav, footer, <head>)
src/lib/data.ts    toda la lectura de datos (fs.readFileSync sobre public/data/)
public/data/       JSON generados por fantasy_api/ (no se tocan a mano)
```

## Comandos

| Comando                | Qué hace                                                   |
| :--------------------- | :--------------------------------------------------------- |
| `npm install`          | Instala dependencias                                       |
| `npm run dev`          | Servidor de desarrollo en `localhost:4321`                 |
| `npm run build`        | Build de producción a `./dist/`                            |
| `npm run preview`      | Sirve el build de `./dist/` en local, antes de desplegar   |
| `npm run lint`         | ESLint (`.astro` + `.ts`, incluye reglas de accesibilidad) |
| `npm run format`       | Prettier — reformatea en sitio                             |
| `npm run format:check` | Prettier en modo comprobación (lo que corre en CI)         |
| `npm run astro check`  | Type-check de Astro/TypeScript                             |

`npm run lint`, `format:check` y `astro check` son exactamente lo que corre
`.github/workflows/verify.yml` en cada push/PR.
