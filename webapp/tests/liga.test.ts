import { describe, expect, it } from "vitest";
import {
  MAX_BUDGET,
  FORMATIONS,
  getLigaJornadas,
  getAllPlayerSummaries,
} from "../src/lib/data";
import { bestEleven, idealEleven } from "../src/lib/liga";
import { combinedSd, expectedSd, expectedPoints } from "../src/lib/forecast";

describe("datos de la liga", () => {
  it("cada 11 con puntos coherentes: suma de los 11 + capitán doble = puntos de la jornada", () => {
    for (const j of getLigaJornadas()) {
      for (const e of j.entries) {
        const sum = e.players.reduce(
          (s, p) => s + p.points * (p.captain ? 2 : 1),
          0,
        );
        // Se guardan los puntos sin doblar; la liga cuenta el capitán doble.
        expect(sum, `J${j.number} ${e.participant}`).toBe(e.points);
      }
    }
  });

  it("11 jugadores por participante y un único capitán", () => {
    for (const j of getLigaJornadas()) {
      for (const e of j.entries) {
        expect(e.players, `J${j.number} ${e.participant}`).toHaveLength(11);
        expect(e.players.filter((p) => p.captain)).toHaveLength(1);
      }
    }
  });
});

describe("bestEleven", () => {
  const eleven = bestEleven(
    12,
    (s) => expectedPoints(s, 13),
    (s) => s.id_team !== 3,
  );

  it("no pasa del presupuesto de 180M", () => {
    expect(eleven).not.toBeNull();
    expect(eleven!.cost).toBeLessThanOrEqual(MAX_BUDGET);
  });

  it("son 11 jugadores distintos con una formación permitida", () => {
    const players = eleven!.players;
    expect(players).toHaveLength(11);
    expect(new Set(players.map((p) => p.summary.id)).size).toBe(11);
    const count = (pos: number) =>
      players.filter((p) => p.summary.position === pos).length;
    const formation = FORMATIONS.find((f) => f.key === eleven!.formationKey);
    expect(formation).toBeDefined();
    expect([count(1), count(2), count(3), count(4)]).toEqual([
      1,
      formation!.def,
      formation!.mid,
      formation!.fwd,
    ]);
  });

  it("respeta el filtro (sin Barcelona)", () => {
    expect(eleven!.players.every((p) => p.summary.id_team !== 3)).toBe(true);
  });

  it("el 11 ideal de una jornada no puntúa menos que el mejor de la liga", () => {
    const ideal = idealEleven(12);
    const best = Math.max(
      ...getLigaJornadas()
        .find((j) => j.number === 12)!
        .entries.map((e) => e.points),
    );
    expect(ideal!.points).toBeGreaterThanOrEqual(best);
  });
});

describe("margen de los puntos esperados", () => {
  it("combinedSd suma en cuadratura e ignora los desconocidos", () => {
    expect(combinedSd([3, 4])).toBeCloseTo(5);
    expect(combinedSd([3, null, 4])).toBeCloseTo(5);
    expect(combinedSd([null])).toBeNull();
  });

  it("todo jugador con predicción tiene un margen positivo", () => {
    const withModel = getAllPlayerSummaries().filter(
      (s) => expectedSd(s.id) !== null,
    );
    expect(withModel.length).toBeGreaterThan(300);
    expect(withModel.every((s) => (expectedSd(s.id) as number) >= 0)).toBe(
      true,
    );
  });
});
