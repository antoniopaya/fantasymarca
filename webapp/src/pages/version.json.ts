import { getDataUpdatedAt } from "../lib/data";

// Fecha de los datos de esta publicación. La web la compara con la de la
// página que tiene abierta para avisar de "Hay datos nuevos" (ver lib/pwa.ts).
export function GET() {
  return new Response(
    JSON.stringify({ data: getDataUpdatedAt()?.getTime() ?? 0 }),
    { headers: { "Content-Type": "application/json" } },
  );
}
