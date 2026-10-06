// Genera dist/sw.js después de `astro build` (ver "build" en package.json).
// @vite-pwa/astro no soporta Astro 7, así que se usa workbox-build directamente.
//
// Estrategia:
// - Precaché: solo JS/CSS de Astro, iconos, manifest y la página offline.
// - Páginas: red primero (los datos cambian varias veces por semana) y, sin
//   conexión, la copia guardada o la página offline.
// - Imágenes de Marca: ni se tocan. Su CDN no manda CORS (en Chrome cada
//   respuesta opaca cuenta ~7MB de cuota) y ya las sirve con caché de un año,
//   así que la caché HTTP normal las tiene también sin conexión.

import { generateSW } from "workbox-build";

const { count, size, warnings } = await generateSW({
  globDirectory: "dist",
  globPatterns: [
    "_astro/**/*.{js,css}",
    "icons/*.png",
    "favicon.svg",
    "manifest.webmanifest",
    "offline/index.html",
  ],
  swDest: "dist/sw.js",
  // Sin skipWaiting: la página enseña "Datos nuevos · Recargar" y manda
  // SKIP_WAITING cuando se pulsa (workbox añade el listener solo).
  skipWaiting: false,
  clientsClaim: true,
  cleanupOutdatedCaches: true,
  sourcemap: false,
  navigateFallback: null,
  runtimeCaching: [
    {
      urlPattern: ({ request }) => request.mode === "navigate",
      handler: "NetworkFirst",
      options: {
        cacheName: "paginas",
        networkTimeoutSeconds: 4,
        expiration: { maxEntries: 80, maxAgeSeconds: 30 * 24 * 60 * 60 },
        precacheFallback: { fallbackURL: "offline/index.html" },
      },
    },
  ],
});

for (const w of warnings) console.warn(w);
console.log(
  `sw.js: ${count} ficheros precacheados (${(size / 1024).toFixed(0)} KB)`,
);
