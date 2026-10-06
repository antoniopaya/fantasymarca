// Genera los iconos de la app (favicon + PWA) a partir de un único diseño:
// "FM" sobre el mismo degradado esmeralda que el logo de la navbar.
// Uso: node scripts/generate-icons.mjs  (solo hace falta si cambia el diseño)

import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const OUT = path.resolve("public/icons");
fs.mkdirSync(OUT, { recursive: true });

// rounded: icono "normal" con esquinas; maskable/apple: a sangre (el sistema
// recorta la forma) y con las letras dentro de la zona segura del 80%.
function svg({ rounded, fontSize }) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#34d399"/>
      <stop offset="1" stop-color="#059669"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="${rounded ? 112 : 0}" fill="url(#g)"/>
  <text x="256" y="256" dy="0.35em" text-anchor="middle"
    font-family="Inter, 'DejaVu Sans', Arial, sans-serif" font-weight="900"
    font-size="${fontSize}" letter-spacing="-8" fill="#020617">FM</text>
</svg>`;
}

const normal = svg({ rounded: true, fontSize: 250 });
const fullBleed = svg({ rounded: false, fontSize: 200 });

fs.writeFileSync(path.resolve("public/favicon.svg"), normal);
await sharp(Buffer.from(normal))
  .resize(192)
  .png()
  .toFile(`${OUT}/icon-192.png`);
await sharp(Buffer.from(normal))
  .resize(512)
  .png()
  .toFile(`${OUT}/icon-512.png`);
await sharp(Buffer.from(fullBleed))
  .resize(512)
  .png()
  .toFile(`${OUT}/maskable-512.png`);
await sharp(Buffer.from(fullBleed))
  .resize(180)
  .png()
  .toFile(`${OUT}/apple-touch-icon.png`);
console.log("Iconos generados en public/icons y public/favicon.svg");
