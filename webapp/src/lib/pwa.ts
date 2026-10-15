// Registro del service worker (dist/sw.js, ver scripts/generate-sw.mjs) y
// aviso de "Hay datos nuevos" cuando la página abierta tiene datos más viejos
// que los publicados.

// Las pantallas que se usan cada semana: se guardan para que estén disponibles
// sin conexión desde el principio.
const CORE_PAGES = ["", "crear-once/", "jornada/", "liga/"];

const base = document.body.dataset.base ?? "/";

// Compara la fecha de los datos de esta página con la de version.json (sin
// caché). Se mira al cargar y al volver a la app, que en el móvil puede
// quedarse abierta días.
const CHECK_EVERY_MS = 60_000;
let lastCheck = 0;

async function checkForNewData() {
  if (Date.now() - lastCheck < CHECK_EVERY_MS) return;
  lastCheck = Date.now();
  const current = Number(document.body.dataset.version ?? 0);
  try {
    const response = await fetch(`${base}version.json`, { cache: "no-store" });
    if (!response.ok) return;
    const { data } = (await response.json()) as { data: number };
    if (data > current) showUpdate();
  } catch {
    // sin conexión: se vuelve a mirar al volver a la app
  }
}

function showUpdate() {
  const banner = document.getElementById("sw-update");
  const button = document.getElementById("sw-reload");
  if (!banner || !button) return;
  banner.hidden = false;
  button.addEventListener("click", () => window.location.reload(), {
    once: true,
  });
}

// Tras instalar o actualizar el service worker se vuelven a guardar las
// páginas principales: una copia de un despliegue anterior apuntaría a CSS y
// JS que el service worker nuevo ya ha borrado.
async function cacheCorePages() {
  const cache = await caches.open("paginas");
  for (const page of CORE_PAGES) {
    const pageUrl = new URL(`${base}${page}`, window.location.origin).href;
    cache.add(pageUrl).catch(() => {
      // sin conexión: ya se guardará cuando se visite
    });
  }
}

async function register() {
  const registration = await navigator.serviceWorker.register(`${base}sw.js`, {
    scope: base,
  });
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    cacheCorePages().catch(() => {});
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    checkForNewData();
    registration.update().catch(() => {});
  });
}

// En `astro dev` no hay sw.js (se genera tras el build).
if (import.meta.env.PROD) {
  window.addEventListener("load", () => {
    checkForNewData();
    if ("serviceWorker" in navigator) {
      register().catch(() => {
        // Sin service worker la web sigue funcionando igual, solo que sin offline.
      });
    }
  });
}
