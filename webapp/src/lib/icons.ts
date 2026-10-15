// Iconos de trazo (24x24, estilo Lucide) para toda la web: el mismo grosor y
// las mismas puntas en la barra de navegación, pestañas y botones. Se usan
// con <Icon name="..." /> (components/Icon.astro).
export const ICONS = {
  // Secciones
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  field: "M4 4h16v16H4zM4 12h16M12 4v4m0 8v4M9 12a3 3 0 0 0 6 0 3 3 0 0 0-6 0",
  users:
    "M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1M9 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7m13 9v-1a4 4 0 0 0-3-3.9M16 3.1a3.5 3.5 0 0 1 0 6.8",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4m8-4v4",
  trophy:
    "M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v1a3 3 0 0 0 3 3m10-4h3v1a3 3 0 0 1-3 3",
  // Pestañas
  search: "m21 21-4.3-4.3M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16",
  sparkles:
    "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 15l.7 1.8 1.8.7-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7z",
  chart: "M3 3v18h18M7 15l4-4 3 3 6-6",
  pie: "M21 12A9 9 0 1 1 12 3v9zM15 3.5A9 9 0 0 1 20.5 9H15z",
  list: "M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01",
  versus: "M7 4v16M17 4v16M3 8l4-4 4 4m2 8 4 4 4-4",
  // Acciones
  sliders:
    "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M2 14h4M10 8h4M18 16h4",
  x: "M18 6 6 18M6 6l12 12",
  chevronDown: "m6 9 6 6 6-6",
  arrowRight: "M5 12h14m-6-6 6 6-6 6",
  message: "M7.9 20A9 9 0 1 0 4 16.1L2 22z",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  undo: "M9 14 4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11",
  plus: "M12 5v14M5 12h14",
  trash: "M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6",
  eraser:
    "m7 21-4.3-4.3a1 1 0 0 1 0-1.4l10-10a1 1 0 0 1 1.4 0l5.6 5.6a1 1 0 0 1 0 1.4L13 21zM22 21H7M5 11l9 9",
  download: "M12 3v12m-5-5 5 5 5-5M5 21h14",
  refresh: "M21 12a9 9 0 1 1-2.6-6.4L21 8M21 3v5h-5",
} as const;

export type IconName = keyof typeof ICONS;
