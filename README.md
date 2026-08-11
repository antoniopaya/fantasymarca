# FantasyMarca

Panel personal (no oficial, sin afiliación con MARCA) para seguir la liga de
[Fantasy Marca](https://fantasy.marca.com): próxima jornada, ficha y
estadísticas de los 500+ jugadores, y una herramienta para montar el once
respetando el precio "Fantástica" que pactamos en nuestra liga privada.

En vivo: **https://antoniopaya.github.io/fantasymarca/**

## Qué hay

- **Inicio** — resumen: próximos partidos, jugadores más valiosos.
- **Próxima jornada** — calendario completo, jornada a jornada.
- **Jugadores** — buscador con filtros (equipo, posición, precio) y ficha
  individual (valor de mercado, cláusula, evolución, calendario).
- **Estadísticas** — rankings y gráficos: precio Fantástica vs. puntos,
  gangas, ratio puntos/precio, cláusulas, distribución por posición, valor de
  plantilla por equipo...
- **Crear once** — arma un XI con la táctica que quieras, tope de 180M€ en
  precio Fantástica, capitán por debajo de 18M€, y compártelo por WhatsApp.
  Se guarda en el navegador (`localStorage`), no hay cuentas ni servidor.

## Estructura del repo

```
fantasy_api/    Scripts en Python que hablan con fantasy.marca.com
  main.py               genera todo lo que consume la webapp (ver más abajo)
  build_precios_fantastica.py   cruza el Excel de precios con el catálogo
  client.py, auth_store.py      autenticación y cliente HTTP compartidos
  get_*.py, search_players.py   scripts sueltos para explorar la API a mano
webapp/         Sitio Astro + Tailwind, 100% estático
  src/pages/            una carpeta/archivo por ruta
  src/components/       componentes Astro, incluidos los gráficos
  src/lib/data.ts        toda la lectura de datos (fs.readFileSync) vive aquí
  public/data/           JSON generados por fantasy_api (ver abajo)
.github/workflows/
  deploy.yml            build + publica en GitHub Pages (push a main)
  refresh-data.yml       corre main.py en cron y commitea si cambian los datos
  verify.yml             lint + type-check + build en cada push/PR (sin desplegar)
```

## De dónde salen los datos

La webapp es **100% estática**: nunca llama a fantasy.marca.com en producción,
solo lee JSON ya generados en `webapp/public/data/`. Ese directorio se llena
de dos formas distintas, y por eso hay dos scripts separados:

1. **Catálogo de Marca** (`fantasy_api/main.py`) — equipos, jornadas,
   partidos y la ficha completa de cada jugador (valor de mercado, cláusula,
   puntos, calendario). Se regenera entero cada vez que se ejecuta: a mano,
   o automáticamente por `refresh-data.yml` (lunes y jueves).
2. **Precio Fantástica** (`fantasy_api/build_precios_fantastica.py`) — el
   precio de consenso que pactamos en la liga, mantenido a mano en un Excel
   (`webapp/public/data/*.xlsx`). El script empareja cada fila del Excel
   contra el catálogo por nombre+equipo+posición (el Excel no trae IDs de
   Marca) y escribe `precios_fantastica.json`. Vive en un fichero aparte
   porque si estuviera en el mismo sitio que el catálogo, `main.py` lo
   pisaría en su próxima ejecución.

Como el emparejamiento es por nombre, un puñado de filas quedan sin
correspondencia clara (fichajes que Marca no ha dado de alta todavía, o
jugadores que han cambiado de equipo desde la última vez que se actualizó el
Excel) — el propio script las lista al final de su salida para revisarlas a
mano; ver `MANUAL_OVERRIDES` dentro del script para los casos ya resueltos.

## Correr en local

**Webapp** (Node 22+):

```bash
cd webapp
npm install
npm run dev       # http://localhost:4321
npm run lint      # ESLint
npm run format    # Prettier
npm run build     # build de producción a webapp/dist/
```

**fantasy_api** (Python 3.13+, solo hace falta si quieres regenerar datos):

```bash
pip install curl_cffi
# fantasy_api/auth_store.json con tus credenciales (x_auth + refresh_token
# capturados desde las DevTools del navegador logueado en fantasy.marca.com);
# no está en el repo, es un secreto y va en .gitignore.
cd fantasy_api
python main.py
```

## Despliegue

Cada push a `main` que toque `webapp/**` dispara `deploy.yml`: build de Astro
y publicación en GitHub Pages. Como el repo no se llama `<usuario>.github.io`,
el sitio se sirve bajo `/fantasymarca/`; `astro.config.mjs` fija el `base`
solo cuando `GITHUB_ACTIONS=true`, así que en local (`npm run dev`) todo
sigue funcionando en la raíz sin tocar nada.

`refresh-data.yml` necesita dos secrets del repo para autenticarse contra
fantasy.marca.com: `FANTASY_X_AUTH` y `FANTASY_REFRESH_TOKEN` (los mismos
valores que `fantasy_api/auth_store.json` en local). Si el token de sesión
llegara a invalidarse alguna vez, el workflow fallará con un 401 claro y
tocará recapturar las credenciales a mano desde el navegador.
