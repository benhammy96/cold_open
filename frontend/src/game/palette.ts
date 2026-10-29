// Single restricted palette (R40). Every pixel drawn to the canvas comes from
// here so placeholder and future real art stay visually consistent. 18 colors.
export const PALETTE = {
  night: "#0d1b2a",
  night2: "#1b263b",
  dusk: "#415a77",
  haze: "#778da9",
  cloud: "#e0e1dd",
  white: "#fff5d6",
  gold: "#ffcc33",
  amber: "#f4a261",
  carpet: "#c1121f",
  rose: "#e5383b",
  skin: "#f0c8a0",
  skinShadow: "#c89a74",
  hoodie: "#4a5859",
  jacket: "#6d4c3d",
  suit: "#1d2d44",
  tux: "#0b090a",
  shadow: "#000000",
  star: "#ffd60a",
} as const;

export type PaletteKey = keyof typeof PALETTE;
