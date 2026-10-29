// Asset manifest (R38). All art + animation data is referenced through here so
// placeholder procedural art can later be swapped for real sprite sheets WITHOUT
// touching gameplay or renderer code. In this slice every "asset" is a procedural
// draw function keyed by name; a future manifest would point at image URLs + frame
// rects instead, and the renderer would branch on asset.kind.

import { LOCATIONS, type LocationKey } from "./locations";

export type Outfit = "hoodie_duffel" | "hoodie" | "jacket" | "suit" | "tux" | "tux_star";

export interface AnimationDef {
  // Data-driven frame list (R: animations are data-driven, not hardcoded).
  frames: number[]; // frame indices into the character sprite
  fps: number;
  loop: boolean;
}

export const CHARACTER_ANIMATIONS: Record<string, AnimationDef> = {
  idle: { frames: [0, 1], fps: 2, loop: true },
  climb: { frames: [2, 3, 2, 1], fps: 8, loop: true },
  stumble: { frames: [4], fps: 1, loop: false },
  cheer: { frames: [1, 3], fps: 6, loop: true },
};

export interface AssetManifest {
  internalWidth: number;
  internalHeight: number;
  characterFrameCount: number;
  locations: LocationKey[];
  animations: Record<string, AnimationDef>;
  // When real art lands, add: characterSheet: { url, frameW, frameH, frames }
  //                          backgrounds: Record<LocationKey, { url }>
  art: "procedural" | "sheet";
}

export const MANIFEST: AssetManifest = {
  internalWidth: 180,
  internalHeight: 320,
  characterFrameCount: 5,
  locations: LOCATIONS.map((l) => l.key),
  animations: CHARACTER_ANIMATIONS,
  art: "procedural",
};
