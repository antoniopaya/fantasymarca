# FantasyMarca

App personal (no oficial, sin afiliación con MARCA) para que los Payás
(Antonio, Toño y Jandro) preparen cada semana su 11 de la liga privada
"Fantástica" de [Fantasy Marca](https://fantasy.marca.com): precio
Fantástica pactado, tope de 180M€, capitán de menos de 18M€ que puntúa doble
y 3/6/11 cambios por jornada según la clasificación.

En vivo: **https://antoniopaya.github.io/fantasymarca/** — se puede instalar
como app (PWA): en Android sale el botón "Instalar"; en iPhone, Safari →
Compartir → "Añadir a pantalla de inicio". Funciona sin conexión con las
páginas ya abiertas.

## Qué hay

Cinco pestañas (abajo en el móvil, arriba en escritorio):

- **Inicio ("Tu semana")** — cuenta atrás al primer partido de la jornada,
  avisos sobre tu 11 (lesionados, dudas, sin partido), capitán recomendado,
  cambios que suman con lo que te cabe, tu clasificación y Los Payás.
- **Mi 11** — tu 11 en el campo con barra fija de presupuesto, cambios y
  capitán. "Preparar mi 11" carga el 11 de tu última jornada de la liga con tus
  cambios disponibles; al tocar un jugador se puede cambiar, hacer capitán o
  quitar. El selector ordena por puntos esperados y filtra lo que te cabe.
  Compartir por WhatsApp manda solo los cambios ("sale - entra") y el capitán.
  Se guarda en el navegador (`localStorage`), no hay cuentas ni servidor.
- **Jugadores** — buscador (orden por puntos esperados, filtro "mi 11") y
  estadísticas (precio vs. puntos, puntos por millón...; lo del mercado de
  Marca, al final). La ficha de cada jugador trae sus próximos partidos con la
  dificultad, sus últimas jornadas y quién lo lleva en la liga.
- **Jornada** — calendario con tus jugadores y sus puntos esperados en cada
  partido.
- **Liga** — clasificación con premios y evolución, estadísticas de la liga
  (más usados, capitanes, diferenciales, 11 ideal, tus fijos y eficiencia) y
  "Cara a cara" entre dos participantes.

"¿Quién eres?" (arriba a la derecha) personaliza todo lo anterior.

**Puntos esperados y dificultad** (`webapp/src/lib/forecast.ts`): fuerza de
cada equipo con los partidos jugados, dificultad 1-5 de cada partido según la
posición del jugador y casa/fuera, y puntos esperados = media de la temporada
+ forma de las últimas 3 jornadas, ajustados por dificultad y estado. Es una
estimación sencilla para ordenar opciones, no una predicción fina.

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
  data/                  JSON generados por fantasy_api (ver abajo); no se publican
.github/workflows/
  deploy.yml            build + publica en GitHub Pages (push a main)
  refresh-data.yml       corre main.py en cron (lun, jue, vie x2, sáb y dom),
                         commitea si cambian los datos
                         y dispara deploy.yml a mano (ver abajo)
  verify.yml             lint + type-check + build en cada push/PR (sin desplegar)
```

## De dónde salen los datos

La webapp es **100% estática**: nunca llama a fantasy.marca.com en producción,
solo lee JSON ya generados en `webapp/data/` (en el build: no se publican). Ese directorio se llena
de tres fuentes distintas, cada una con su script:

1. **Catálogo de Marca** (`fantasy_api/main.py`) — equipos, jornadas,
   partidos y la ficha completa de cada jugador (valor de mercado, cláusula,
   puntos, calendario). Se regenera entero cada vez que se ejecuta: a mano,
   o automáticamente por `refresh-data.yml` (lunes, jueves, viernes mañana y
   tarde, sábado y domingo).
2. **Precio Fantástica** (`fantasy_api/build_precios_fantastica.py`) — el
   precio de consenso que pactamos en la liga, mantenido a mano en un Excel
   (`webapp/data/*.xlsx`). El script empareja cada fila del Excel
   contra el catálogo por nombre+equipo+posición (el Excel no trae IDs de
   Marca) y escribe `precios_fantastica.json`. Vive en un fichero aparte
   porque si estuviera en el mismo sitio que el catálogo, `main.py` lo
   pisaría en su próxima ejecución.

Como el emparejamiento es por nombre, un puñado de filas quedan sin
correspondencia clara (fichajes que Marca no ha dado de alta todavía, o
jugadores que han cambiado de equipo desde la última vez que se actualizó el
Excel) — el propio script las lista al final de su salida para revisarlas a
mano; ver `MANUAL_OVERRIDES` dentro del script para los casos ya resueltos.

3. **Liga Fantástica** (`fantasy_api/build_liga.py`) — alineaciones,
   capitanes, puntos, saldo y cambios de cada participante, jornada a
   jornada. La liga los manda como un PDF por jornada; basta con dejarlo en
   `data/Jornadas/` y hacer push: `build-liga.yml` lo lee, escribe
   `liga/<n>.json` y despliega. El PDF solo trae nombres abreviados, así que
   cada jugador se empareja con el catálogo por nombre y desempatando con
   sus puntos de Marca en esa jornada; el script comprueba además que los
   11 precios Fantástica + saldo sumen 180M. Lo que no resuelva lo lista al
   final para añadirlo a `LIGA_ALIASES`.

4. **Alineaciones probables** (`fantasy_api/scrape_alineaciones.py`) — dos
   fuentes contrastadas: la "Posible alineación" de la página de cada equipo
   en [futbolfantasy.com](https://www.futbolfantasy.com/laliga/equipos/real-madrid)
   y la página de la jornada de
   [analiticafantasy.com](https://www.analiticafantasy.com/la-liga/alineaciones-probables)
   (datos incrustados en el HTML; su robots.txt prohíbe /api/, así que no se
   usa). Empareja a cada jugador con su id de Marca, guarda la probabilidad
   de titular de cada fuente y su media, y marca cuándo no coinciden (una lo
   pone de titular y la otra no, o se separan 40+ puntos). Escribe
   `alineaciones.json` y una copia por jornada (la de antes del cierre) en
   `alineaciones_hist/`. Unas 22 peticiones con pausa entre ellas, solo
   cuando se refrescan los datos.
5. **Modelo de puntos esperados** (`fantasy_api/ml_model.py`) — machine
   learning con scikit-learn: P(juega) × puntos si juega, con variables
   calculadas solo con lo que se sabía antes de cada jornada (forma,
   titularidades, goles/asistencias, precio, fuerza del rival y de su equipo,
   casa/fuera, y cruces posición × rival: un rival goleador no afecta igual a
   un portero que a un delantero). Predice la próxima jornada y las dos
   siguientes, para fichar pensando en varias semanas. Prueba un modelo lineal y uno de boosting, valida cada jornada
   pasada entrenando solo con las anteriores y se queda el mejor; para la
   jornada a predecir combina su P(juega) con las alineaciones probables
   (cuando haya 2+ jornadas guardadas, las usa como variable y aprende su
   peso). Escribe `predicciones.json`, que la web usa para los puntos
   esperados y la pestaña Jugadores → Recomendados (incluido el 11 de 180M
   que más puntos espera). Si falta, la web vuelve a la fórmula sencilla.

`refresh-data.yml` ejecuta los tres seguidos: `main.py`, el scraper (si
falla, se sigue sin alineaciones) y el modelo.

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
pip install -r fantasy_api/requirements.txt
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

Los commits de datos son la excepción a ese "cada push dispara el deploy":
`refresh-data.yml` commitea con el `GITHUB_TOKEN` del propio workflow, y GitHub
no encadena workflows desde pushes hechos con ese token, así que `deploy.yml`
nunca se enteraba y el sitio se quedaba servido con datos viejos. Por eso
`refresh-data.yml` termina llamando a `gh workflow run deploy.yml` (el
`workflow_dispatch` sí es la excepción documentada a esa regla), y necesita
permiso `actions: write` para poder hacerlo.

`refresh-data.yml` necesita dos secrets del repo para autenticarse contra
fantasy.marca.com: `FANTASY_X_AUTH` y `FANTASY_REFRESH_TOKEN` (los mismos
valores que `fantasy_api/auth_store.json` en local). Si el token de sesión
llegara a invalidarse alguna vez, el workflow fallará con un 401 claro y
tocará recapturar las credenciales a mano desde el navegador.
