// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

// Sitio 100% estático: los datos vienen de public/data/*.json, generados aparte
// por fantasy_api/main.py. No hace falta adapter ni SSR.
//
// GitHub Pages sirve este repo en /fantasymarca/ (no es un repo <usuario>.github.io,
// así que no hay dominio propio a la raíz). GITHUB_ACTIONS lo pone a "true" el propio
// runner de Actions, así que en local (`astro dev`/`astro build` a mano) el sitio
// se sigue sirviendo en la raíz sin tener que tocar nada.
export default defineConfig({
  base: process.env.GITHUB_ACTIONS ? '/fantasymarca/' : '/',
  vite: {
    plugins: [tailwindcss()]
  }
});
