import { getAllPlayerSummaries } from "../../lib/data";
import { expectedPoints, prediction } from "../../lib/forecast";

// Datos del comparador de la ficha de jugador, uno por posición. Antes iban
// incrustados en cada ficha (~30 KB repetidos en las 530); así se descarga
// una vez y el navegador lo reutiliza.
export function getStaticPaths() {
  return [1, 2, 3, 4].map((pos) => ({ params: { pos: String(pos) } }));
}

export function GET({ params }: { params: { pos: string } }) {
  const position = Number(params.pos);
  const rows = getAllPlayerSummaries()
    .filter((p) => p.position === position)
    .map((p) => ({
      id: p.id,
      name: p.name,
      team: p.team_name,
      price: p.precioFantastica,
      points: p.points,
      avg: p.avg,
      value: p.value,
      clause: p.clauseValue,
      xp: Math.round(expectedPoints(p) * 10) / 10,
      prob: prediction(p.id)?.prob ?? null,
    }))
    .sort((a, b) => a.name.localeCompare(b.name, "es"));
  return new Response(JSON.stringify(rows), {
    headers: { "Content-Type": "application/json" },
  });
}
