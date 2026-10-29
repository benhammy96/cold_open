// Procedural placeholder art (R39). Flat-color shapes from the palette only.
// Each function draws into a 180-wide internal context. Swapping to real sprite
// sheets later means replacing these with manifest-driven blits; nothing else
// in the renderer changes.
import type { LocationDef } from "./locations";
import type { Outfit } from "./manifest";
import { PALETTE } from "./palette";

const W = 180;

// Deterministic pseudo-random so parallax stars/buildings are stable per frame.
function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

// Draw a full-height sky gradient + simple parallax layers for a location.
// worldY is the scroll offset (larger = climbed higher) used for parallax.
export function drawBackground(
  ctx: CanvasRenderingContext2D,
  loc: LocationDef,
  worldY: number,
  height: number,
) {
  const grad = ctx.createLinearGradient(0, 0, 0, height);
  grad.addColorStop(0, loc.skyTop);
  grad.addColorStop(1, loc.skyBottom);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, height);

  // Far layer: stars / dots, slow parallax.
  const r1 = rng(1337 + loc.minScore);
  ctx.fillStyle = PALETTE.cloud;
  for (let i = 0; i < 24; i++) {
    const x = Math.floor(r1() * W);
    const y = Math.floor((r1() * height + worldY * 0.2) % height);
    ctx.fillRect(x, y, 1, 1);
  }

  // Mid layer: skyline blocks, medium parallax.
  const r2 = rng(42 + loc.minScore);
  ctx.fillStyle = loc.accent + "55";
  for (let i = 0; i < 6; i++) {
    const bw = 16 + Math.floor(r2() * 24);
    const bh = 20 + Math.floor(r2() * 50);
    const x = Math.floor(r2() * (W - bw));
    const y = height - bh + ((worldY * 0.5) % 40) - 20;
    ctx.fillRect(x, y, bw, bh);
  }

  // Near layer: ground line + a prop for flavor.
  ctx.fillStyle = loc.accent;
  ctx.fillRect(0, height - 14 + ((worldY) % 28), W, 2);
}

// 12x16 character, drawn centered at (cx, cy) (cy = feet baseline).
// Frame indices: 0 idle-a, 1 idle-b, 2 climb-a, 3 climb-b, 4 stumble.
export function drawCharacter(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  outfit: Outfit,
  frame: number,
) {
  const px = (x: number, y: number, w: number, h: number, color: string) => {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(cx + x), Math.round(cy + y), w, h);
  };

  const bodyColor =
    outfit === "hoodie_duffel" || outfit === "hoodie"
      ? PALETTE.hoodie
      : outfit === "jacket"
        ? PALETTE.jacket
        : outfit === "suit"
          ? PALETTE.suit
          : PALETTE.tux;

  const bob = frame === 1 || frame === 3 ? -1 : 0;
  const legSplit = frame === 2 || frame === 3; // mid-climb pose

  // Shadow.
  px(-5, 1, 10, 2, PALETTE.shadow + "88");
  // Head.
  px(-3, -16 + bob, 6, 6, PALETTE.skin);
  px(-3, -16 + bob, 6, 1, PALETTE.skinShadow);
  // Body.
  px(-4, -10 + bob, 8, 8, bodyColor);
  // Arms (raised when climbing).
  if (legSplit) {
    px(-6, -11 + bob, 2, 4, bodyColor);
    px(4, -11 + bob, 2, 4, bodyColor);
  } else {
    px(-6, -8 + bob, 2, 4, bodyColor);
    px(4, -8 + bob, 2, 4, bodyColor);
  }
  // Legs.
  if (frame === 4) {
    // stumble: legs askew
    px(-4, -2, 3, 4, PALETTE.night);
    px(2, -2, 4, 3, PALETTE.night);
  } else if (legSplit) {
    px(-4, -2, 3, 4, PALETTE.night);
    px(1, -3, 3, 5, PALETTE.night);
  } else {
    px(-3, -2, 2, 4, PALETTE.night);
    px(1, -2, 2, 4, PALETTE.night);
  }

  // Outfit extras.
  if (outfit === "hoodie_duffel") {
    px(4, -6 + bob, 4, 3, PALETTE.amber); // duffel bag
  }
  if (outfit === "suit" || outfit === "tux" || outfit === "tux_star") {
    px(-1, -10 + bob, 2, 6, PALETTE.white); // shirt front
  }
  if (outfit === "tux_star") {
    px(-1, -19 + bob, 2, 2, PALETTE.star); // little sparkle
  }
}
