// Dificultad de los partidos y puntos esperados (todo en build).
//
// Con pocas jornadas jugadas no hay datos para un modelo serio, así que esto
// es deliberadamente simple y explicable:
// - Fuerza de cada equipo a partir de sus partidos jugados esta temporada,
//   encogida hacia la media de la liga (SHRINK partidos "de media") para que
//   un 4-0 en la jornada 1 no lo decida todo.
// - Dificultad 1 (fácil) a 5 (muy difícil) según el rival: para porteros y
//   defensas cuenta cuánto marca el rival; para medios y delanteros, cuánto
//   encaja. Jugar en casa la rebaja un poco.
// - Puntos esperados = mezcla de media de la temporada y forma reciente,
//   ajustada por dificultad, casa/fuera y estado (lesión, duda...).

import {
  getAllPlayerSummaries,
  getGameweeks,
  getMatches,
  getNextGameweek,
  getPredictions,
  type Prediction,
  type Match,
  type PlayerSummary,
} from "./data";

const SHRINK = 3;

interface TeamStats {
  played: number;
  points: number;
  gf: number;
  ga: number;
}

let allMatchesCache: Match[] | null = null;
function allMatches(): Match[] {
  allMatchesCache ??= getGameweeks().flatMap((gw) => {
    try {
      return getMatches(gw.number);
    } catch {
      return [];
    }
  });
  return allMatchesCache;
}

let strengthCache: Map<
  number,
  { attack: number; defense: number; ppg: number }
> | null = null;

/** attack: goles a favor por partido; defense: goles en contra por partido (ambos encogidos). */
export function teamStrength() {
  if (strengthCache) return strengthCache;
  const stats = new Map<number, TeamStats>();
  const get = (id: number) => {
    let s = stats.get(id);
    if (!s) {
      s = { played: 0, points: 0, gf: 0, ga: 0 };
      stats.set(id, s);
    }
    return s;
  };
  for (const m of allMatches()) {
    get(m.id_home);
    get(m.id_away);
    if (m.status !== "played") continue;
    const gh = Number(m.goals_home);
    const ga = Number(m.goals_away);
    if (Number.isNaN(gh) || Number.isNaN(ga)) continue;
    const home = get(m.id_home);
    const away = get(m.id_away);
    home.played++;
    away.played++;
    home.gf += gh;
    home.ga += ga;
    away.gf += ga;
    away.ga += gh;
    home.points += gh > ga ? 3 : gh === ga ? 1 : 0;
    away.points += ga > gh ? 3 : gh === ga ? 1 : 0;
  }
  const totals = [...stats.values()].reduce(
    (acc, s) => ({
      played: acc.played + s.played,
      gf: acc.gf + s.gf,
      points: acc.points + s.points,
    }),
    { played: 0, gf: 0, points: 0 },
  );
  const avgGoals = totals.played ? totals.gf / totals.played : 1.3;
  const avgPpg = totals.played ? totals.points / totals.played : 1.4;
  strengthCache = new Map(
    [...stats.entries()].map(([id, s]) => [
      id,
      {
        attack: (s.gf + SHRINK * avgGoals) / (s.played + SHRINK),
        defense: (s.ga + SHRINK * avgGoals) / (s.played + SHRINK),
        ppg: (s.points + SHRINK * avgPpg) / (s.played + SHRINK),
      },
    ]),
  );
  return strengthCache;
}

/** Cuánto "aprieta" un rival a un jugador de esa posición: más alto = más difícil. */
function threat(rivalId: number, position: number): number {
  const s = teamStrength().get(rivalId);
  if (!s) return 0;
  // Porteros/defensas sufren a los que marcan mucho; medios/delanteros, a los
  // que encajan poco. El ppg suma algo de "calidad general" del rival.
  return position <= 2 ? s.attack + s.ppg * 0.4 : -s.defense + s.ppg * 0.4;
}

let thresholdsCache: Record<"def" | "att", number[]> | null = null;
function thresholds(position: number): number[] {
  if (!thresholdsCache) {
    const teams = [...teamStrength().keys()];
    const quintiles = (pos: number) => {
      const values = teams.map((t) => threat(t, pos)).sort((a, b) => a - b);
      return [0.2, 0.4, 0.6, 0.8].map(
        (q) =>
          values[Math.min(values.length - 1, Math.floor(q * values.length))],
      );
    };
    thresholdsCache = { def: quintiles(2), att: quintiles(4) };
  }
  return position <= 2 ? thresholdsCache.def : thresholdsCache.att;
}

/** 1 = muy fácil ... 5 = muy difícil. */
export function difficulty(
  rivalId: number,
  position: number,
  home: boolean,
): 1 | 2 | 3 | 4 | 5 {
  const t = thresholds(position);
  // En casa se juega como contra un rival "un escalón" más flojo, aprox.
  const spread = (t[3] - t[0]) / 3 || 0.1;
  const value = threat(rivalId, position) + (home ? -0.35 : 0.35) * spread;
  const level = 1 + t.filter((x) => value > x).length;
  return level as 1 | 2 | 3 | 4 | 5;
}

export const DIFFICULTY_LABELS: Record<number, string> = {
  1: "Muy fácil",
  2: "Fácil",
  3: "Normal",
  4: "Difícil",
  5: "Muy difícil",
};

/**
 * Escala divergente (skill dataviz): azul = fácil, gris = normal, rojo =
 * difícil. Cada brazo validado como rampa de un solo tono sobre el fondo
 * oscuro; nunca verde/rojo (el par que peor distinguen los daltónicos). El
 * número va siempre dentro, así que el color nunca es la única pista.
 */
export const DIFFICULTY_COLORS: Record<number, string> = {
  1: "#3987e5",
  2: "#1c5cab",
  3: "#5c5b57",
  4: "#9e3b3b",
  5: "#e66767",
};

export interface Fixture {
  gameweek: number;
  rivalId: number;
  rivalName: string;
  home: boolean;
  /** Timestamp (s) del partido. */
  ts: number;
}

let fixturesCache: Map<number, Fixture[]> | null = null;

/** Partidos pendientes de cada equipo, por jornada (los aplazados van en su jornada). */
export function teamFixtures(teamId: number): Fixture[] {
  if (!fixturesCache) {
    fixturesCache = new Map();
    for (const gw of getGameweeks()) {
      let matches: Match[] = [];
      try {
        matches = getMatches(gw.number);
      } catch {
        continue;
      }
      for (const m of matches) {
        if (m.status === "played") continue;
        const push = (team: number, f: Fixture) => {
          const list = fixturesCache!.get(team) ?? [];
          list.push(f);
          fixturesCache!.set(team, list);
        };
        push(m.id_home, {
          gameweek: gw.number,
          rivalId: m.id_away,
          rivalName: m.away,
          home: true,
          ts: m.date.ts,
        });
        push(m.id_away, {
          gameweek: gw.number,
          rivalId: m.id_home,
          rivalName: m.home,
          home: false,
          ts: m.date.ts,
        });
      }
    }
  }
  return fixturesCache.get(teamId) ?? [];
}

/** El partido de un equipo en una jornada concreta, si lo tiene. */
export function fixtureIn(teamId: number, gameweek: number): Fixture | null {
  return teamFixtures(teamId).find((f) => f.gameweek === gameweek) ?? null;
}

const DIFFICULTY_FACTOR: Record<number, number> = {
  1: 1.25,
  2: 1.1,
  3: 1,
  4: 0.9,
  5: 0.78,
};

const xpCache = new Map<string, number>();

/** Predicción del modelo de ML para la jornada, si existe y es de esa jornada. */
export function prediction(
  playerId: number,
  gameweek = getNextGameweek().number,
): Prediction | null {
  const preds = getPredictions();
  if (!preds || preds.jornada !== gameweek) return null;
  return preds.players[String(playerId)] ?? null;
}

/**
 * Puntos esperados de un jugador en una jornada (sin doblar por capitán).
 * Si fantasy_api/ml_model.py ha predicho esa jornada, se usa el modelo
 * (que ya tiene en cuenta alineaciones probables, rival, forma...). Si no,
 * la fórmula sencilla de abajo: 0 si su equipo no juega o está lesionado/
 * sancionado; la mitad si es duda.
 */
export function expectedPoints(
  player: PlayerSummary,
  gameweek = getNextGameweek().number,
): number {
  const key = `${player.id}:${gameweek}`;
  const cached = xpCache.get(key);
  if (cached !== undefined) return cached;
  const fixtureForModel = fixtureIn(player.id_team, gameweek);
  const predicted = prediction(player.id, gameweek);
  if (predicted && fixtureForModel) {
    const value = Math.max(0, Math.round(predicted.xp * 10) / 10);
    xpCache.set(key, value);
    return value;
  }
  const fixture = fixtureIn(player.id_team, gameweek);
  let xp = 0;
  if (fixture && !["injury", "red", "other"].includes(player.status ?? "")) {
    const recent = player.form / 3;
    const base = 0.6 * player.avg + 0.4 * recent;
    xp =
      base *
      DIFFICULTY_FACTOR[
        difficulty(fixture.rivalId, player.position, fixture.home)
      ] *
      (fixture.home ? 1.05 : 0.95) *
      (player.status === "doubt" ? 0.5 : 1);
  }
  xp = Math.max(0, Math.round(xp * 10) / 10);
  xpCache.set(key, xp);
  return xp;
}

/** Los próximos `n` partidos de un jugador con su dificultad. */
export function upcomingFor(player: PlayerSummary, n: number) {
  const next = getNextGameweek().number;
  return teamFixtures(player.id_team)
    .filter((f) => f.gameweek >= next)
    .slice(0, n)
    .map((f) => ({
      ...f,
      difficulty: difficulty(f.rivalId, player.position, f.home),
    }));
}

export function summariesWithXp() {
  return getAllPlayerSummaries().map((s) => ({ ...s, xp: expectedPoints(s) }));
}
