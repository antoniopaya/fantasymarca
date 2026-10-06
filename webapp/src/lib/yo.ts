// Quién está usando la web ("¿Quién eres?" de la navbar). Va en un módulo
// aparte de data.ts porque se importa desde scripts de cliente, y data.ts
// arrastra node:fs.

/** Los únicos participantes que usan la web; el resto de la liga solo aparece en estadísticas. */
export const FAMILIA = ["Antonio", "Toño", "Jandro"] as const;
export type Familiar = (typeof FAMILIA)[number];

export const YO_STORAGE_KEY = "fantasymarca:yo";
/** Evento en `window` cuando cambia la selección; `detail` es el nombre o null. */
export const YO_EVENT = "fantasymarca:yo-change";

export function getYo(): Familiar | null {
  try {
    const value = localStorage.getItem(YO_STORAGE_KEY);
    return FAMILIA.find((f) => f === value) ?? null;
  } catch {
    return null;
  }
}

export function setYo(value: Familiar | null): void {
  try {
    if (value) localStorage.setItem(YO_STORAGE_KEY, value);
    else localStorage.removeItem(YO_STORAGE_KEY);
  } catch {
    // Sin localStorage (modo privado...): la selección dura lo que la página.
  }
  window.dispatchEvent(new CustomEvent(YO_EVENT, { detail: value }));
}
