// "Tu semana": qué revisar del 11 antes del cierre, a partir del 11 de la
// última jornada de la liga (lo que tienes ahora) y de lib/forecast.ts.

import {
  getAllPlayerSummaries,
  getMatches,
  getNextGameweek,
  MAX_CAPTAIN_PRICE,
  PLAYER_STATUS_LABELS,
  type LigaEntry,
  type PlayerSummary,
} from "./data";
import {
  difficulty,
  expectedPoints,
  expectedPointsHorizon,
  fixtureIn,
} from "./forecast";

export interface WeekPlayer {
  summary: PlayerSummary;
  xp: number;
  /** Puntos esperados sumando la próxima jornada y las dos siguientes. */
  xp3: number;
  rivalName: string | null;
  home: boolean | null;
  difficulty: number | null;
}

function toWeekPlayer(s: PlayerSummary, gameweek: number): WeekPlayer {
  const f = fixtureIn(s.id_team, gameweek);
  return {
    summary: s,
    xp: expectedPoints(s, gameweek),
    xp3: expectedPointsHorizon(s).total,
    rivalName: f?.rivalName ?? null,
    home: f?.home ?? null,
    difficulty: f ? difficulty(f.rivalId, s.position, f.home) : null,
  };
}

/** Primer partido de la próxima jornada: hasta entonces se puede cambiar el 11. */
export function deadline(): { ts: number; label: string } | null {
  const gw = getNextGameweek();
  let matches: ReturnType<typeof getMatches> = [];
  try {
    matches = getMatches(gw.number);
  } catch {
    return null;
  }
  const first = matches
    .filter((m) => m.status !== "played")
    .sort((a, b) => a.date.ts - b.date.ts)[0];
  return first
    ? { ts: first.date.ts, label: `${first.home}–${first.away}` }
    : null;
}

export function weekPlan(entry: LigaEntry) {
  const gameweek = getNextGameweek().number;
  const byId = new Map(getAllPlayerSummaries().map((s) => [s.id, s]));
  const mine = entry.players
    .map((p) => (p.id !== null ? byId.get(p.id) : undefined))
    .filter((s): s is PlayerSummary => s !== undefined)
    .map((s) => toWeekPlayer(s, gameweek));
  const mineIds = new Set(mine.map((p) => p.summary.id));

  const alerts = mine.flatMap((p) => {
    if (!p.rivalName) return [{ player: p, text: "no juega esta jornada" }];
    if (p.summary.status) {
      return [
        {
          player: p,
          text: (
            PLAYER_STATUS_LABELS[p.summary.status] ?? "baja"
          ).toLowerCase(),
        },
      ];
    }
    return [];
  });

  const captains = mine
    .filter((p) => (p.summary.precioFantastica ?? Infinity) < MAX_CAPTAIN_PRICE)
    .sort((a, b) => b.xp - a.xp)
    .slice(0, 3);

  // Los 3 que menos se espera que sumen en las próximas 3 jornadas (un
  // cambio se queda varias semanas), y para cada uno los mejores que podrías
  // fichar con su precio más tu saldo (un cambio cada vez).
  const saldo = (entry.saldo ?? 0) * 1_000_000;
  const candidates = getAllPlayerSummaries().filter(
    (s) =>
      s.precioFantastica !== null && !mineIds.has(s.id) && s.status === null,
  );
  const changes = [...mine]
    .sort((a, b) => a.xp3 - b.xp3)
    .slice(0, 3)
    .map((out) => {
      const budget = (out.summary.precioFantastica ?? 0) + saldo;
      const options = candidates
        .filter(
          (s) =>
            s.position === out.summary.position &&
            (s.precioFantastica as number) <= budget,
        )
        .map((s) => toWeekPlayer(s, gameweek))
        .filter((s) => s.xp3 >= out.xp3 + 2)
        .sort((a, b) => b.xp3 - a.xp3)
        .slice(0, 3);
      return { out, budget, options };
    })
    .filter((c) => c.options.length > 0);

  const expectedTotal =
    mine.reduce((s, p) => s + p.xp, 0) +
    (mine.find((p) => entry.players.find((x) => x.id === p.summary.id)?.captain)
      ?.xp ?? 0);

  return { mine, alerts, captains, changes, expectedTotal };
}
