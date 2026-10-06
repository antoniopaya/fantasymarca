import fs from "node:fs";
import path from "node:path";

// Todo esto lo genera fantasy_api/main.py (ver ../../../fantasy_api/main.py), a mano,
// 1-2 veces por semana. La webapp es 100% estática: nunca llama a fantasy.marca.com
// en producción, solo lee estos JSON ya generados dentro de public/data.
const DATA_DIR = path.resolve(process.cwd(), "public", "data");

export interface Team {
  id: number;
  name: string;
  slug: string;
}

export interface Player {
  id: number;
  name: string;
  slug: string;
  position: number;
  id_team: number;
  team_name: string;
}

export interface Gameweek {
  id: number;
  number: number;
  name: string;
  season: string;
  status: string;
}

export interface Match {
  id: number;
  id_gameweek: number;
  id_home: number;
  id_away: number;
  goals_home: string | number;
  goals_away: string | number;
  status: string;
  date: { text: string; ts: number };
  gameweek: string;
  home: string;
  away: string;
  // Ojo: Marca dejó de mandar homeLogoUrl/awayLogoUrl en el payload de partidos
  // (desaparecieron en el refresco del 2026-09-07). Los logos se derivan del id
  // del equipo con teamLogoUrl(); no vuelvas a declararlos aquí sin comprobar
  // antes que el JSON los trae de verdad, porque TypeScript no lo detecta.
}

export interface PlayerDetail {
  player: {
    id: number;
    name: string;
    position: number;
    points: number;
    avg: number;
    status: string | null;
    photoUrl: string;
    value: number;
    previousValue: number;
    team: { id: number; name: string; logoUrl: string };
    clause: { floor: number; value: number; multiplier: number };
    bio: {
      age: number;
      country: { flag: string; country: string };
      height: number;
      weight: number | null;
    };
    clausesRanking: number;
  };
  player_extra: { matches: number; goals: number; cards: number };
  points: Array<{
    id: number;
    number: number;
    shortName: string;
    startDate: string;
    endDate: string;
    points: { points: number | null; isLive: boolean };
    rivalLogoUrl: string;
  }>;
  points_history: Array<{
    season: string;
    points: number;
    avg: number;
    id_team: number;
    last_gameweek: number;
  }>;
  values: Array<{ time: string; value: number; change: number }>;
  // Marca devuelve `[]` (no un objeto) cuando el jugador no tiene histórico de
  // valor todavía (fichajes recién dados de alta, sin ninguna variación registrada).
  values_chart:
    | {
        points: Array<{ value: number; date: string }>;
        max: { value: number; date: string };
        min: { value: number; date: string };
      }
    | [];
}

export interface PlayerSummary {
  id: number;
  name: string;
  slug: string;
  position: number;
  id_team: number;
  team_name: string;
  photoUrl: string;
  value: number;
  weeklyChange: number;
  clauseValue: number;
  clausesRanking: number;
  points: number;
  avg: number;
  /** Puntos sumados en las últimas 3 jornadas ya jugadas (sin partido = 0). */
  form: number;
  lastSeason: { season: string; points: number; avg: number } | null;
  /** Precio de consenso de la liga (ver precios_fantastica.json), null si el jugador no está en el Excel. */
  precioFantastica: number | null;
  /** injury/doubt/red/other, o null si no hay ninguna incidencia (ver PLAYER_STATUS_LABELS). */
  status: string | null;
}

/** Etiqueta legible para PlayerSummary.status, para badges/tooltips en los listados. */
export const PLAYER_STATUS_LABELS: Record<string, string> = {
  injury: "Lesionado",
  doubt: "Duda",
  red: "Sancionado",
  other: "Baja",
};

/** Formaciones que admite la liga (defensas-medios-delanteros, siempre 1 portero). */
export const FORMATIONS = [
  { key: "3-4-3", def: 3, mid: 4, fwd: 3 },
  { key: "3-5-2", def: 3, mid: 5, fwd: 2 },
  { key: "4-3-3", def: 4, mid: 3, fwd: 3 },
  { key: "4-4-2", def: 4, mid: 4, fwd: 2 },
  { key: "4-5-1", def: 4, mid: 5, fwd: 1 },
  { key: "5-3-2", def: 5, mid: 3, fwd: 2 },
  { key: "5-4-1", def: 5, mid: 4, fwd: 1 },
];

/** Reglas de la liga Fantástica: tope del 11 y precio máximo (exclusivo) del capitán. */
export const MAX_BUDGET = 180_000_000;
export const MAX_CAPTAIN_PRICE = 18_000_000;

export const POSITION_NAMES: Record<number, string> = {
  1: "Portero",
  2: "Defensa",
  3: "Centrocampista",
  4: "Delantero",
};

export const POSITION_SHORT: Record<number, string> = {
  1: "POR",
  2: "DEF",
  3: "CEN",
  4: "DEL",
};

// Paleta categórica validada (dataviz skill: node scripts/validate_palette.js) para el
// surface oscuro del sitio — 4 slots, adjacent-pairs, todos los checks en PASS.
// La misma posición usa siempre el mismo color en todos los gráficos (donut, barras...).
export const POSITION_COLORS: Record<number, string> = {
  1: "#3987e5", // portero — azul
  2: "#d95926", // defensa — naranja
  3: "#199e70", // centrocampista — aqua
  4: "#c98500", // delantero — amarillo
};

function loadJson<T>(relativePath: string): T {
  const raw = fs.readFileSync(path.join(DATA_DIR, relativePath), "utf-8");
  return JSON.parse(raw) as T;
}

let teamsCache: Team[] | null = null;
let playersCache: Player[] | null = null;
let gameweeksCache: Gameweek[] | null = null;
let preciosFantasticaCache: Record<string, number> | null = null;

export function getTeams(): Team[] {
  teamsCache ??= loadJson<Team[]>("teams.json");
  return teamsCache;
}

export function getPlayers(): Player[] {
  playersCache ??= loadJson<Player[]>("players.json");
  return playersCache;
}

export function getGameweeks(): Gameweek[] {
  gameweeksCache ??= loadJson<Gameweek[]>("gameweeks.json");
  return gameweeksCache;
}

/**
 * Precio de consenso de la liga Fantástica, en euros (para usar con formatMoney
 * igual que `value`). Viene de fantasy_api/build_precios_fantastica.py, que lo
 * genera a partir del Excel en public/data/*.xlsx y vive en su propio fichero
 * porque main.py/build_catalog.py regeneran players.json entero cada vez.
 */
export function getPreciosFantastica(): Record<string, number> {
  preciosFantasticaCache ??= loadJson<Record<string, number>>(
    "precios_fantastica.json",
  );
  return preciosFantasticaCache;
}

export function getPrecioFantastica(id: number): number | null {
  const millones = getPreciosFantastica()[String(id)];
  return millones === undefined ? null : millones * 1_000_000;
}

export function getTeamById(id: number): Team | undefined {
  return getTeams().find((t) => t.id === id);
}

export function getPlayerById(id: number): Player | undefined {
  return getPlayers().find((p) => p.id === id);
}

/**
 * La jornada "actual": la primera con algún partido pendiente que se juegue antes
 * de que arranque la siguiente; si no queda ninguna, la última de la temporada.
 *
 * No se usa el `status` de Marca porque un partido aplazado deja su jornada en
 * "ongoing" durante semanas (p.ej. la 6, con un partido movido al 21 oct): con
 * esta regla ese rezagado no cuenta, porque se juega después de que empiece la
 * jornada siguiente, mientras que una jornada a medio jugar el fin de semana sí.
 */
export function getNextGameweek(): Gameweek {
  const gameweeks = getGameweeks();
  const firstKickoff = (n: number) =>
    Math.min(...getMatches(n).map((m) => m.date.ts ?? Infinity));
  for (const [i, gw] of gameweeks.entries()) {
    const nextStart = gameweeks[i + 1]
      ? firstKickoff(gameweeks[i + 1].number)
      : Infinity;
    const pendingBeforeNext = getMatches(gw.number).some(
      (m) => m.status !== "played" && (m.date.ts ?? Infinity) < nextStart,
    );
    if (pendingBeforeNext) return gw;
  }
  return gameweeks[gameweeks.length - 1];
}

export function getMatches(gameweekNumber: number): Match[] {
  return loadJson<Match[]>(`matches/${gameweekNumber}.json`);
}

const detailCache = new Map<number, PlayerDetail>();

export function getPlayerDetail(id: number): PlayerDetail {
  let detail = detailCache.get(id);
  if (!detail) {
    detail = loadJson<PlayerDetail>(`players/${id}.json`);
    detailCache.set(id, detail);
  }
  return detail;
}

/** Puntos de Marca de un jugador en una jornada (null si no jugó o aún no se ha jugado). */
export function getGameweekPoints(id: number, gameweek: number): number | null {
  return (
    getPlayerDetail(id).points.find((p) => p.number === gameweek)?.points
      .points ?? null
  );
}

let summariesCache: PlayerSummary[] | null = null;

/** Une el catálogo con la ficha de cada jugador para poder rankear/agregar. Cara la primera vez (501 lecturas), luego cacheada. */
export function getAllPlayerSummaries(): PlayerSummary[] {
  if (summariesCache) return summariesCache;

  const nextGameweek = getNextGameweek();
  const currentSeason = nextGameweek.season;

  summariesCache = getPlayers().map((catalogEntry) => {
    const detail = getPlayerDetail(catalogEntry.id);
    const weekly = detail.values.find((v) => v.time === "Una semana");
    // points_history[0] ya no es fiable para "temporada anterior": en cuanto la
    // temporada en curso acumula alguna jornada, la API la mete ella también en
    // el histórico (en primera posición), así que hay que descartarla explícitamente.
    const lastSeasonEntry = detail.points_history.find(
      (h) => h.season !== currentSeason,
    );

    return {
      id: catalogEntry.id,
      name: catalogEntry.name,
      slug: catalogEntry.slug,
      position: catalogEntry.position,
      id_team: catalogEntry.id_team,
      team_name: catalogEntry.team_name,
      photoUrl: detail.player.photoUrl,
      value: detail.player.value,
      weeklyChange:
        weekly?.change ?? detail.player.value - detail.player.previousValue,
      clauseValue: detail.player.clause.value,
      clausesRanking: detail.player.clausesRanking,
      points: detail.player.points,
      avg: detail.player.avg,
      form: detail.points
        .filter(
          (p) =>
            p.number < nextGameweek.number &&
            p.number >= nextGameweek.number - 3,
        )
        .reduce((sum, p) => sum + (p.points.points ?? 0), 0),
      lastSeason: lastSeasonEntry
        ? {
            season: lastSeasonEntry.season,
            points: lastSeasonEntry.points,
            avg: lastSeasonEntry.avg,
          }
        : null,
      precioFantastica: getPrecioFantastica(catalogEntry.id),
      status: detail.player.status,
    };
  });

  return summariesCache;
}

// --- Liga Fantástica (fantasy_api/build_liga.py, a partir de los PDFs) ------

export interface LigaPlayer {
  /** null si el jugador ya no está en el catálogo de Marca. */
  id: number | null;
  name: string;
  /** Puntos de Marca en la jornada, sin doblar aunque sea el capitán. */
  points: number;
  captain: boolean;
}

export interface LigaEntry {
  participant: string;
  won: number;
  lost: number;
  players: LigaPlayer[];
  /** Puntos de la jornada en la liga (el capitán ya cuenta doble). */
  points: number;
  prev_total: number;
  total: number;
  dif: number | null;
  /** Millones que sobraron de los 180M al hacer el 11. */
  saldo: number | null;
  /** Cambios disponibles para la jornada siguiente (3/6/11 según la clasificación). */
  changes: number | null;
}

export interface LigaJornada {
  number: number;
  /** Ordenadas por total, de primero a último. */
  entries: LigaEntry[];
}

let ligaCache: LigaJornada[] | null = null;

export function getLigaJornadas(): LigaJornada[] {
  if (ligaCache) return ligaCache;
  const dir = path.join(DATA_DIR, "liga");
  const files = fs.existsSync(dir) ? fs.readdirSync(dir) : [];
  ligaCache = files
    .filter((f) => f.endsWith(".json"))
    .map((f) => loadJson<LigaJornada>(`liga/${f}`))
    .sort((a, b) => a.number - b.number);
  return ligaCache;
}

export function getLatestLigaJornada(): LigaJornada | null {
  const jornadas = getLigaJornadas();
  return jornadas[jornadas.length - 1] ?? null;
}

const CDN_BASE = "https://cdn-fantasy.marca.com/file/cdn-common";

export function playerPhotoUrl(id: number): string {
  return `${CDN_BASE}/players/${id}.png`;
}

export function teamLogoUrl(id: number): string {
  return `${CDN_BASE}/teams/${id}.png`;
}

/**
 * Antepone el `base` del sitio (vacío en local, "/fantasymarca" en GitHub Pages,
 * ver astro.config.mjs) a una ruta interna. Los `href="/algo"` escritos a mano no
 * se reescriben solos: hay que pasarlos por aquí para que funcionen bajo un subpath.
 */
export function url(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}${path}`;
}

export function formatMoney(value: number): string {
  return `${(value / 1_000_000).toFixed(2)} M€`;
}
