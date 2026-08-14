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
  homeLogoUrl: string;
  awayLogoUrl: string;
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
  lastSeason: { season: string; points: number; avg: number } | null;
  /** Precio de consenso de la liga (ver precios_fantastica.json), null si el jugador no está en el Excel. */
  precioFantastica: number | null;
}

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

/** La próxima jornada sin empezar; si no queda ninguna, la última de la temporada. */
export function getNextGameweek(): Gameweek {
  const gameweeks = getGameweeks();
  return (
    gameweeks.find((gw) => gw.status === "unstarted") ??
    gameweeks[gameweeks.length - 1]
  );
}

export function getMatches(gameweekNumber: number): Match[] {
  return loadJson<Match[]>(`matches/${gameweekNumber}.json`);
}

export function getPlayerDetail(id: number): PlayerDetail {
  return loadJson<PlayerDetail>(`players/${id}.json`);
}

let summariesCache: PlayerSummary[] | null = null;

/** Une el catálogo con la ficha de cada jugador para poder rankear/agregar. Cara la primera vez (501 lecturas), luego cacheada. */
export function getAllPlayerSummaries(): PlayerSummary[] {
  if (summariesCache) return summariesCache;

  summariesCache = getPlayers().map((catalogEntry) => {
    const detail = getPlayerDetail(catalogEntry.id);
    const weekly = detail.values.find((v) => v.time === "Una semana");
    const lastSeasonEntry = detail.points_history[0];

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
      lastSeason: lastSeasonEntry
        ? {
            season: lastSeasonEntry.season,
            points: lastSeasonEntry.points,
            avg: lastSeasonEntry.avg,
          }
        : null,
      precioFantastica: getPrecioFantastica(catalogEntry.id),
    };
  });

  return summariesCache;
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
