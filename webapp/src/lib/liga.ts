// Cálculos sobre los datos de la liga Fantástica (public/data/liga/<n>.json).
// Todo se ejecuta en build: las páginas reciben ya los resultados.

import {
  FORMATIONS,
  MAX_BUDGET,
  MAX_CAPTAIN_PRICE,
  getAllPlayerSummaries,
  getGameweekPoints,
  getLigaJornadas,
  getPrecioFantastica,
  type LigaEntry,
  type LigaJornada,
  type PlayerSummary,
} from "./data";

// Azul, naranja y aqua: los tres primeros huecos de la paleta categórica
// validada para fondo oscuro (skill dataviz), sin pares confundibles entre sí.
export const FAMILIA_COLORS: Record<string, string> = {
  Antonio: "#3987e5",
  Toño: "#d95926",
  Jandro: "#199e70",
};

/** Premios de la clasificación general (1º..7º), en euros. */
export const PREMIOS_LIGA = [400, 300, 200, 100, 80, 70, 60];

export function rankIn(jornada: LigaJornada, participant: string): number {
  const entry = jornada.entries.find((e) => e.participant === participant);
  if (!entry) return jornada.entries.length;
  return 1 + jornada.entries.filter((e) => e.total > entry.total).length;
}

export interface StandingRow {
  entry: LigaEntry;
  rank: number;
  /** Puestos ganados (+) o perdidos (-) respecto a la jornada anterior. */
  movement: number | null;
  premio: number | null;
}

export function standings(): StandingRow[] {
  const jornadas = getLigaJornadas();
  const last = jornadas[jornadas.length - 1];
  const prev = jornadas[jornadas.length - 2];
  if (!last) return [];
  return last.entries.map((entry) => {
    const rank = rankIn(last, entry.participant);
    return {
      entry,
      rank,
      movement: prev ? rankIn(prev, entry.participant) - rank : null,
      premio: PREMIOS_LIGA[rank - 1] ?? null,
    };
  });
}

/** Por participante: puesto, puntos y total tras cada jornada. */
export function history(participant: string) {
  return getLigaJornadas().map((j) => {
    const entry = j.entries.find((e) => e.participant === participant);
    return {
      jornada: j.number,
      rank: entry ? rankIn(j, participant) : null,
      points: entry?.points ?? null,
      total: entry?.total ?? null,
    };
  });
}

export function averagePoints(jornada: LigaJornada): number {
  const sum = jornada.entries.reduce((s, e) => s + e.points, 0);
  return sum / jornada.entries.length;
}

/** Quién hizo más puntos en cada jornada. */
export function jornadaWinners() {
  return getLigaJornadas().map((j) => {
    const best = Math.max(...j.entries.map((e) => e.points));
    return {
      jornada: j.number,
      points: best,
      winners: j.entries
        .filter((e) => e.points === best)
        .map((e) => e.participant),
      average: averagePoints(j),
    };
  });
}

// --- Uso de jugadores ------------------------------------------------------

/** id -> nº de participantes que lo llevaban en esa jornada. */
export function ownershipCounts(jornada: LigaJornada): Map<number, number> {
  const counts = new Map<number, number>();
  for (const e of jornada.entries) {
    for (const p of e.players) {
      if (p.id !== null) counts.set(p.id, (counts.get(p.id) ?? 0) + 1);
    }
  }
  return counts;
}

export interface OwnedPlayer {
  summary: PlayerSummary;
  pct: number;
  /** Variación en puntos porcentuales respecto a la jornada anterior. */
  delta: number | null;
}

let summaryById: Map<number, PlayerSummary> | null = null;
export function summaryOf(id: number): PlayerSummary | undefined {
  summaryById ??= new Map(getAllPlayerSummaries().map((s) => [s.id, s]));
  return summaryById.get(id);
}

export function mostOwned(limit: number): OwnedPlayer[] {
  const jornadas = getLigaJornadas();
  const last = jornadas[jornadas.length - 1];
  const prev = jornadas[jornadas.length - 2];
  if (!last) return [];
  const now = ownershipCounts(last);
  const before = prev ? ownershipCounts(prev) : null;
  const pct = (n: number, j: LigaJornada) => (n / j.entries.length) * 100;
  return [...now.entries()]
    .map(([id, n]) => ({ id, n }))
    .sort((a, b) => b.n - a.n)
    .slice(0, limit)
    .flatMap(({ id, n }) => {
      const summary = summaryOf(id);
      if (!summary) return [];
      return [
        {
          summary,
          pct: pct(n, last),
          delta:
            before && prev
              ? pct(n, last) - pct(before.get(id) ?? 0, prev)
              : null,
        },
      ];
    });
}

/** Jugadores que pocos llevan y que vienen puntuando: la forma de remontar. */
export function differentials(maxPct: number, limit: number) {
  const jornadas = getLigaJornadas();
  const last = jornadas[jornadas.length - 1];
  if (!last) return [];
  const counts = ownershipCounts(last);
  return getAllPlayerSummaries()
    .filter((s) => s.precioFantastica !== null && s.status === null)
    .map((s) => ({
      summary: s,
      pct: ((counts.get(s.id) ?? 0) / last.entries.length) * 100,
    }))
    .filter((d) => d.pct <= maxPct)
    .sort((a, b) => b.summary.form - a.summary.form)
    .slice(0, limit);
}

/** Los más llevados por posición, con la formación más usada en la última jornada. */
export function templateEleven() {
  const jornadas = getLigaJornadas();
  const last = jornadas[jornadas.length - 1];
  if (!last) return null;
  const formationCount = new Map<string, number>();
  for (const e of last.entries) {
    const pos = e.players
      .map((p) => (p.id !== null ? summaryOf(p.id)?.position : undefined))
      .filter((x): x is number => x !== undefined);
    const key = [2, 3, 4]
      .map((n) => pos.filter((x) => x === n).length)
      .join("-");
    formationCount.set(key, (formationCount.get(key) ?? 0) + 1);
  }
  const [formationKey] = [...formationCount.entries()].sort(
    (a, b) => b[1] - a[1],
  )[0];
  const formation =
    FORMATIONS.find((f) => f.key === formationKey) ?? FORMATIONS[0];
  const counts = ownershipCounts(last);
  const need: Record<number, number> = {
    1: 1,
    2: formation.def,
    3: formation.mid,
    4: formation.fwd,
  };
  const rows = [1, 2, 3, 4].map((position) =>
    [...counts.entries()]
      .map(([id, n]) => ({ summary: summaryOf(id), n }))
      .filter(
        (x): x is { summary: PlayerSummary; n: number } =>
          x.summary?.position === position,
      )
      .sort((a, b) => b.n - a.n)
      .slice(0, need[position])
      .map((x) => ({ ...x, pct: (x.n / last.entries.length) * 100 })),
  );
  return { formationKey: formation.key, rows };
}

// --- Capitanes ---------------------------------------------------------------

export function captaincies() {
  const tally = new Map<
    number,
    { times: number; points: number; lastJornada: number }
  >();
  for (const j of getLigaJornadas()) {
    for (const e of j.entries) {
      const c = e.players.find((p) => p.captain);
      if (!c || c.id === null) continue;
      const t = tally.get(c.id) ?? { times: 0, points: 0, lastJornada: 0 };
      t.times++;
      t.points += c.points;
      t.lastJornada = j.number;
      tally.set(c.id, t);
    }
  }
  return [...tally.entries()]
    .flatMap(([id, t]) => {
      const summary = summaryOf(id);
      return summary ? [{ summary, ...t, avgPoints: t.points / t.times }] : [];
    })
    .sort((a, b) => b.times - a.times);
}

export function latestCaptains() {
  const jornadas = getLigaJornadas();
  const last = jornadas[jornadas.length - 1];
  if (!last) return [];
  const counts = new Map<number, number>();
  for (const e of last.entries) {
    const c = e.players.find((p) => p.captain);
    if (c?.id != null) counts.set(c.id, (counts.get(c.id) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .flatMap(([id, n]) => {
      const summary = summaryOf(id);
      return summary ? [{ summary, n }] : [];
    });
}

/**
 * Puntos que se dejó cada participante por no elegir como capitán al mejor
 * de su propio 11 (entre los que podían serlo por precio).
 */
export function captainLoss(entry: LigaEntry): number {
  const captain = entry.players.find((p) => p.captain);
  const eligible = entry.players.filter((p) => {
    if (p.id === null) return false;
    const price = getPrecioFantastica(p.id);
    return price !== null && price < MAX_CAPTAIN_PRICE;
  });
  if (!captain || eligible.length === 0) return 0;
  const best = Math.max(...eligible.map((p) => p.points));
  return Math.max(0, best - captain.points);
}

// --- Favoritos y parecidos -----------------------------------------------------

export function favorites(participant: string, limit: number) {
  const counts = new Map<number, { jornadas: number; captain: number }>();
  let played = 0;
  for (const j of getLigaJornadas()) {
    const e = j.entries.find((x) => x.participant === participant);
    if (!e) continue;
    played++;
    for (const p of e.players) {
      if (p.id === null) continue;
      const c = counts.get(p.id) ?? { jornadas: 0, captain: 0 };
      c.jornadas++;
      if (p.captain) c.captain++;
      counts.set(p.id, c);
    }
  }
  return {
    played,
    players: [...counts.entries()]
      .sort(
        (a, b) => b[1].jornadas - a[1].jornadas || b[1].captain - a[1].captain,
      )
      .slice(0, limit)
      .flatMap(([id, c]) => {
        const summary = summaryOf(id);
        return summary ? [{ summary, ...c }] : [];
      }),
  };
}

function jaccard(a: LigaEntry, b: LigaEntry): number {
  const ids = (e: LigaEntry) =>
    new Set(e.players.map((p) => p.id).filter((x) => x !== null));
  const sa = ids(a);
  const sb = ids(b);
  const shared = [...sa].filter((x) => sb.has(x)).length;
  return shared / (sa.size + sb.size - shared);
}

/** Jugadores en común (de 11) con cada participante en la última jornada. */
export function similarTo(participant: string) {
  const jornadas = getLigaJornadas();
  const last = jornadas[jornadas.length - 1];
  const me = last?.entries.find((e) => e.participant === participant);
  if (!last || !me) return [];
  const mine = new Set(me.players.map((p) => p.id));
  return last.entries
    .filter((e) => e !== me)
    .map((e) => ({
      participant: e.participant,
      shared: e.players.filter((p) => p.id !== null && mine.has(p.id)).length,
      similarity: jaccard(me, e),
    }))
    .sort((a, b) => b.similarity - a.similarity);
}

// --- 11 ideal de cada jornada ---------------------------------------------------

export interface IdealEleven {
  jornada: number;
  formationKey: string;
  players: { summary: PlayerSummary; points: number; captain: boolean }[];
  /** Con el capitán ya doblado, como en la liga. */
  points: number;
  cost: number;
}

const idealCache = new Map<number, IdealEleven | null>();

/**
 * El mejor 11 posible a toro pasado: máximos puntos de Marca sin pasar de
 * 180M en precio Fantástica, con alguna de las formaciones permitidas.
 * Mochila exacta por posición (k jugadores, coste <= c) y luego se combinan
 * las cuatro posiciones. El capitán se elige después (el mejor que cueste
 * menos de 18M), así que el total puede quedarse un poco por debajo del óptimo
 * real si compensara meter un capitán más barato.
 */
export function idealEleven(jornada: number): IdealEleven | null {
  if (idealCache.has(jornada)) return idealCache.get(jornada) ?? null;
  const budget = MAX_BUDGET / 1_000_000;
  const maxK: Record<number, number> = { 1: 1, 2: 5, 3: 5, 4: 3 };

  type Cell = { pts: number; ids: number[] } | null;
  const tables: Record<number, Cell[][]> = {};
  for (const position of [1, 2, 3, 4]) {
    const K = maxK[position];
    const dp: Cell[][] = Array.from({ length: K + 1 }, (_, k) =>
      Array.from({ length: budget + 1 }, () =>
        k === 0 ? { pts: 0, ids: [] } : null,
      ),
    );
    for (const s of getAllPlayerSummaries()) {
      if (s.position !== position || s.precioFantastica === null) continue;
      const cost = Math.round(s.precioFantastica / 1_000_000);
      const pts = getGameweekPoints(s.id, jornada) ?? 0;
      for (let k = K; k >= 1; k--) {
        for (let c = budget; c >= cost; c--) {
          const from = dp[k - 1][c - cost];
          if (!from) continue;
          const cand = from.pts + pts;
          if (!dp[k][c] || cand > (dp[k][c] as { pts: number }).pts) {
            dp[k][c] = { pts: cand, ids: [...from.ids, s.id] };
          }
        }
      }
    }
    tables[position] = dp;
  }

  let best: { pts: number; ids: number[]; formationKey: string } | null = null;
  for (const f of FORMATIONS) {
    const parts = [
      tables[1][1],
      tables[2][f.def],
      tables[3][f.mid],
      tables[4][f.fwd],
    ];
    // Combinar posiciones: acc[c] = mejor reparto con coste total <= c.
    let acc: Cell[] = parts[0];
    for (const part of parts.slice(1)) {
      const next: Cell[] = Array.from({ length: budget + 1 }, () => null);
      for (let c = 0; c <= budget; c++) {
        for (let a = 0; a <= c; a++) {
          const x = acc[a];
          const y = part[c - a];
          if (!x || !y) continue;
          const pts = x.pts + y.pts;
          if (!next[c] || pts > (next[c] as { pts: number }).pts) {
            next[c] = { pts, ids: [...x.ids, ...y.ids] };
          }
        }
      }
      acc = next;
    }
    const top = acc[budget];
    if (top && (!best || top.pts > best.pts)) {
      best = { ...top, formationKey: f.key };
    }
  }
  if (!best) {
    idealCache.set(jornada, null);
    return null;
  }

  const players = best.ids.flatMap((id) => {
    const summary = summaryOf(id);
    return summary
      ? [
          {
            summary,
            points: getGameweekPoints(id, jornada) ?? 0,
            captain: false,
          },
        ]
      : [];
  });
  const captain = players
    .filter((p) => (p.summary.precioFantastica ?? Infinity) < MAX_CAPTAIN_PRICE)
    .sort((a, b) => b.points - a.points)[0];
  if (captain) captain.captain = true;
  players.sort((a, b) => a.summary.position - b.summary.position);
  const result: IdealEleven = {
    jornada,
    formationKey: best.formationKey,
    players,
    points: best.pts + (captain?.points ?? 0),
    cost: players.reduce((s, p) => s + (p.summary.precioFantastica ?? 0), 0),
  };
  idealCache.set(jornada, result);
  return result;
}

/** % de los puntos del 11 ideal que consiguió cada uno, de media por jornada. */
export function efficiency(participant: string) {
  const rows = getLigaJornadas().flatMap((j) => {
    const e = j.entries.find((x) => x.participant === participant);
    const ideal = idealEleven(j.number);
    if (!e || !ideal || ideal.points <= 0) return [];
    return [
      {
        jornada: j.number,
        pct: (e.points / ideal.points) * 100,
        captainLoss: captainLoss(e),
      },
    ];
  });
  const avg = rows.reduce((s, r) => s + r.pct, 0) / (rows.length || 1);
  const lost = rows.reduce((s, r) => s + r.captainLoss, 0);
  return { rows, avgPct: avg, captainLoss: lost };
}

// --- Índice por jugador (fichas y listado de jugadores) ---------------------

export interface LigaPlayerInfo {
  perJornada: { jornada: number; count: number; pct: number }[];
  /** Quién lo llevaba en la última jornada. */
  owners: string[];
  /** Quién lo hizo capitán en la última jornada. */
  captainedBy: string[];
  captainTimes: number;
}

let playerIndex: Map<number, LigaPlayerInfo> | null = null;

export function ligaPlayerInfo(id: number): LigaPlayerInfo | null {
  if (!playerIndex) {
    playerIndex = new Map();
    const jornadas = getLigaJornadas();
    const lastNumber = jornadas.at(-1)?.number;
    for (const j of jornadas) {
      const counts = ownershipCounts(j);
      for (const [pid, count] of counts) {
        let info = playerIndex.get(pid);
        if (!info) {
          info = {
            perJornada: [],
            owners: [],
            captainedBy: [],
            captainTimes: 0,
          };
          playerIndex.set(pid, info);
        }
        info.perJornada.push({
          jornada: j.number,
          count,
          pct: (count / j.entries.length) * 100,
        });
      }
      for (const e of j.entries) {
        for (const p of e.players) {
          if (p.id === null) continue;
          const info = playerIndex.get(p.id);
          if (!info) continue;
          if (p.captain) info.captainTimes++;
          if (j.number === lastNumber) {
            info.owners.push(e.participant);
            if (p.captain) info.captainedBy.push(e.participant);
          }
        }
      }
    }
  }
  return playerIndex.get(id) ?? null;
}

/** % de la liga que lo llevaba en la última jornada (0 si nadie). */
export function latestOwnershipPct(id: number): number {
  const last = getLigaJornadas().at(-1);
  const info = ligaPlayerInfo(id);
  return info?.perJornada.find((p) => p.jornada === last?.number)?.pct ?? 0;
}

let shortNames: Map<number, string> | null = null;

/** Nombre corto: el que usa la liga en sus PDFs ("Fermín L.") o, si no, el apellido. */
export function ligaShortName(id: number, name: string): string {
  if (!shortNames) {
    shortNames = new Map();
    for (const j of getLigaJornadas()) {
      for (const e of j.entries) {
        for (const p of e.players)
          if (p.id !== null) shortNames.set(p.id, p.name);
      }
    }
  }
  return shortNames.get(id) ?? name.split(" ").slice(-1)[0];
}
