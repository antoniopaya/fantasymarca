import {
  getAllPlayerSummaries,
  getPlayerStats,
  type PlayerGameStats,
} from "./data";

/**
 * De qué estadísticas salen los puntos de Marca ("Marca Stats"): cada partido
 * puntúa minutos, goles, asistencias, goles encajados, paradas, pases clave,
 * regates... más la valoración en estrellas de Marca. Los datos los descarga
 * fantasy_api/player_stats.py.
 */

export interface StatMeta {
  label: string;
  /** Cómo se lee el valor: "12 pases clave". */
  unit: string;
  /** Solo resta (tarjetas, pérdidas...): su ranking es "quién más pierde". */
  negative?: boolean;
  /** Qué cuenta, para la ayuda de la página. */
  help: string;
}

export const STATS: Record<string, StatMeta> = {
  minutesPlayed: {
    label: "Minutos",
    unit: "min",
    help: "1 punto por jugar, 2 a partir de 60 minutos.",
  },
  marca: {
    label: "Valoración Marca",
    unit: "estrellas",
    help: "Las estrellas del cronista de Marca: 1 punto por estrella.",
  },
  goals: {
    label: "Goles",
    unit: "goles",
    help: "Más cuanto más atrás juega: 6 un defensa, 5 un centrocampista, 4 un delantero.",
  },
  goalAssist: {
    label: "Asistencias",
    unit: "asistencias",
    help: "3 puntos por asistencia.",
  },
  goalsAgainst: {
    label: "Portería / goles encajados",
    unit: "goles encajados",
    help: "Suma con la portería a cero y resta por goles encajados (porteros y defensas, y algo los centrocampistas).",
  },
  saves: {
    label: "Paradas",
    unit: "paradas",
    help: "1 punto cada 2 paradas, aproximadamente.",
  },
  penaltySave: {
    label: "Penaltis parados",
    unit: "penaltis parados",
    help: "5 puntos por penalti parado.",
  },
  keyPass: {
    label: "Pases clave",
    unit: "pases clave",
    help: "Pases que acaban en tiro: 1 punto cada 2, aproximadamente.",
  },
  bigChanceCreated: {
    label: "Ocasiones claras creadas",
    unit: "ocasiones",
    help: "1 punto por ocasión clara creada.",
  },
  wonContest: {
    label: "Regates",
    unit: "regates",
    help: "Regates completados: 1 punto cada 2, aproximadamente.",
  },
  onTargetScoringAttempt: {
    label: "Tiros a puerta",
    unit: "tiros a puerta",
    help: "1 punto cada 2 tiros a puerta, aproximadamente.",
  },
  totalInterceptions: {
    label: "Intercepciones y entradas",
    unit: "acciones",
    help: "Balones cortados: 1 punto a partir de 5, 2 a partir de 10.",
  },
  totalClearance: {
    label: "Despejes",
    unit: "despejes",
    help: "1 punto a partir de 3 despejes, 2 a partir de 6.",
  },
  penaltyWon: {
    label: "Penaltis provocados",
    unit: "penaltis",
    help: "2 puntos por penalti provocado.",
  },
  possessionLostCtrl: {
    label: "Balones perdidos",
    unit: "pérdidas",
    negative: true,
    help: "Resta 1 punto por cada ~9 balones perdidos.",
  },
  yellowCard: {
    label: "Amarillas",
    unit: "amarillas",
    negative: true,
    help: "−1 por amarilla.",
  },
  doubleYellowCard: {
    label: "Doble amarilla",
    unit: "dobles amarillas",
    negative: true,
    help: "−1 más por la segunda amarilla.",
  },
  redCard: {
    label: "Rojas",
    unit: "rojas",
    negative: true,
    help: "−3 por roja directa.",
  },
  penaltyConceded: {
    label: "Penaltis cometidos",
    unit: "penaltis",
    negative: true,
    help: "−2 por penalti cometido.",
  },
  penaltyMiss: {
    label: "Penaltis fallados",
    unit: "penaltis",
    negative: true,
    help: "−2 por penalti fallado.",
  },
  ownGoals: {
    label: "Goles en propia",
    unit: "goles en propia",
    negative: true,
    help: "−2 por gol en propia puerta.",
  },
};

export function statLabel(key: string): string {
  return STATS[key]?.label ?? key;
}

export interface SeasonStats {
  id: number;
  games: number;
  minutes: number;
  xg: number;
  xa: number;
  /** Media de la nota de Sofascore (null si nunca la tuvo). */
  ss: number | null;
  points: number;
  /** Por estadística: valor acumulado y puntos acumulados. */
  comp: Record<string, { value: number; pts: number }>;
}

let seasonCache: Map<number, SeasonStats> | null = null;

/** Acumulado de la temporada de cada jugador (solo partidos con desglose). */
export function seasonStats(): Map<number, SeasonStats> {
  if (seasonCache) return seasonCache;
  const out = new Map<number, SeasonStats>();
  const ratings = new Map<number, number[]>();
  for (const games of getPlayerStats().values()) {
    for (const [key, g] of Object.entries(games)) {
      if (!g.c) continue;
      const id = Number(key);
      let s = out.get(id);
      if (!s) {
        s = {
          id,
          games: 0,
          minutes: 0,
          xg: 0,
          xa: 0,
          ss: null,
          points: 0,
          comp: {},
        };
        out.set(id, s);
      }
      s.games += 1;
      s.minutes += g.min;
      s.xg += g.xg;
      s.xa += g.xa;
      s.points += g.points;
      if (g.ss !== null) ratings.set(id, [...(ratings.get(id) ?? []), g.ss]);
      for (const [stat, [value, pts]] of Object.entries(g.c)) {
        const c = (s.comp[stat] ??= { value: 0, pts: 0 });
        c.value += value;
        c.pts += pts;
      }
    }
  }
  for (const [id, rs] of ratings)
    out.get(id)!.ss = rs.reduce((a, b) => a + b, 0) / rs.length;
  seasonCache = out;
  return out;
}

/** Posición de cada jugador del catálogo. */
function positions(): Map<number, number> {
  return new Map(getAllPlayerSummaries().map((p) => [p.id, p.position]));
}

/** Estadísticas que han dado o quitado algún punto, en el orden de STATS. */
export function activeStats(): string[] {
  const used = new Set<string>();
  for (const s of seasonStats().values()) {
    for (const [key, c] of Object.entries(s.comp)) if (c.pts) used.add(key);
  }
  return [
    ...Object.keys(STATS).filter((k) => used.has(k)),
    ...[...used].filter((k) => !STATS[k]),
  ];
}

export interface StatWeight {
  key: string;
  /** Puntos netos de la estadística (todos los jugadores). */
  pts: number;
  /** % de todos los puntos (netos) que vienen de ella; negativo si resta. */
  share: number;
  /** % de la diferencia de puntos por partido entre jugadores que explica. */
  influence: number;
}

const MIN_GAMES_INFLUENCE = 3;

/**
 * Peso e influencia de cada estadística, para todos o una posición.
 *
 * - Peso: de cada 100 puntos repartidos, cuántos salen de ella.
 * - Influencia: cuánto de la diferencia entre jugadores (en puntos por
 *   partido, con 3+ partidos) explica. Es la descomposición exacta de la
 *   varianza: cov(estadística, total) / var(total); entre todas suman 100%.
 *   Los minutos pesan mucho pero casi todos los titulares los sacan igual, así
 *   que influyen poco: lo que separa a los buenos está en otras.
 */
export function statWeights(position: number | null): StatWeight[] {
  const pos = positions();
  const players = [...seasonStats().values()].filter(
    (s) => position === null || pos.get(s.id) === position,
  );
  const keys = activeStats();
  const totals = Object.fromEntries(keys.map((k) => [k, 0]));
  for (const s of players)
    for (const k of keys) totals[k] += s.comp[k]?.pts ?? 0;
  const net = Object.values(totals).reduce((a, b) => a + b, 0) || 1;

  const sample = players.filter((s) => s.games >= MIN_GAMES_INFLUENCE);
  const perGame = sample.map((s) =>
    Object.fromEntries(keys.map((k) => [k, (s.comp[k]?.pts ?? 0) / s.games])),
  );
  const total = perGame.map((r) => keys.reduce((a, k) => a + r[k], 0));
  const mean = (xs: number[]) =>
    xs.reduce((a, b) => a + b, 0) / (xs.length || 1);
  const totalMean = mean(total);
  const varTotal =
    mean(total.map((t) => (t - totalMean) ** 2)) || Number.EPSILON;

  return keys
    .map((key) => {
      const xs = perGame.map((r) => r[key]);
      const m = mean(xs);
      const cov = mean(xs.map((x, i) => (x - m) * (total[i] - totalMean)));
      return {
        key,
        pts: totals[key],
        share: (totals[key] / net) * 100,
        influence: (cov / varTotal) * 100,
      };
    })
    .filter((w) => w.pts !== 0);
}

export interface StatLeader {
  id: number;
  name: string;
  team: string;
  position: number;
  pts: number;
  value: number;
  games: number;
}

/**
 * Quién más puntos saca (o más pierde, en las que restan) con cada
 * estadística: estadística -> posición (0 = todas) -> los `n` primeros.
 */
export function statLeaders(
  n = 10,
): Record<string, Record<number, StatLeader[]>> {
  const byId = new Map(getAllPlayerSummaries().map((p) => [p.id, p]));
  const out: Record<string, Record<number, StatLeader[]>> = {};
  for (const key of activeStats()) {
    const rows: StatLeader[] = [];
    for (const s of seasonStats().values()) {
      const c = s.comp[key];
      const p = byId.get(s.id);
      if (!c || !c.pts || !p) continue;
      rows.push({
        id: s.id,
        name: p.name,
        team: p.team_name,
        position: p.position,
        pts: c.pts,
        value: c.value,
        games: s.games,
      });
    }
    const negative = STATS[key]?.negative ?? false;
    rows.sort((a, b) =>
      negative ? a.pts - b.pts || b.value - a.value : b.pts - a.pts,
    );
    out[key] = { 0: rows.slice(0, n) };
    for (const position of [1, 2, 3, 4])
      out[key][position] = rows
        .filter((r) => r.position === position)
        .slice(0, n);
  }
  return out;
}

/** Desglose de un jugador por jornada: [jornada, partido] en orden. */
export function playerBreakdown(id: number): [number, PlayerGameStats][] {
  const out: [number, PlayerGameStats][] = [];
  for (const [gw, games] of getPlayerStats()) {
    const g = games[String(id)];
    if (g?.c) out.push([gw, g]);
  }
  return out;
}
