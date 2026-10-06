// Registro del service worker (dist/sw.js, ver scripts/generate-sw.mjs) y
// aviso de "Hay datos nuevos" cuando se publica un despliegue nuevo.

// Las pantallas que se usan cada semana: se piden una vez tras instalar el
// service worker para que estén disponibles sin conexión desde el principio.
const CORE_PAGES = ["", "crear-once/", "jornada/", "liga/"];

function showUpdate(worker: ServiceWorker) {
  const banner = document.getElementById("sw-update");
  const button = document.getElementById("sw-reload");
  if (!banner || !button) return;
  banner.hidden = false;
  button.addEventListener(
    "click",
    () => worker.postMessage({ type: "SKIP_WAITING" }),
    { once: true },
  );
}

async function register() {
  const base = document.body.dataset.base ?? "/";
  const registration = await navigator.serviceWorker.register(`${base}sw.js`, {
    scope: base,
  });

  if (registration.waiting && navigator.serviceWorker.controller) {
    showUpdate(registration.waiting);
  }
  registration.addEventListener("updatefound", () => {
    const worker = registration.installing;
    worker?.addEventListener("statechange", () => {
      if (worker.state === "installed" && navigator.serviceWorker.controller) {
        showUpdate(worker);
      }
    });
  });

  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });

  await navigator.serviceWorker.ready;
  // Misma caché que usa el service worker para las navegaciones ("paginas").
  const cache = await caches.open("paginas");
  for (const page of CORE_PAGES) {
    const pageUrl = new URL(`${base}${page}`, window.location.origin).href;
    if (!(await cache.match(pageUrl))) {
      cache.add(pageUrl).catch(() => {
        // sin conexión: ya se guardará cuando se visite
      });
    }
  }
}

// En `astro dev` no hay sw.js (se genera tras el build).
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    register().catch(() => {
      // Sin service worker la web sigue funcionando igual, solo que sin offline.
    });
  });
}
