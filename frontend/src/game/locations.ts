// Fame-ladder locations (R33/R34). Mirrors the backend fame.py table. The client
// uses this only for presentation; the server is authoritative for the rank that
// goes on the share card.
import type { Outfit } from "./manifest";

export type LocationKey =
  | "bus_stop"
  | "audition_line"
  | "backlot"
  | "trailer"
  | "red_carpet"
  | "awards_stage"
  | "mansion"
  | "walk_of_fame";

export interface LocationDef {
  key: LocationKey;
  name: string;
  minScore: number;
  outfit: Outfit;
  // Two sky colors for a simple vertical gradient per location.
  skyTop: string;
  skyBottom: string;
  accent: string;
}

export const LOCATIONS: LocationDef[] = [
  { key: "bus_stop", name: "Bus Stop", minScore: 0, outfit: "hoodie_duffel", skyTop: "#1b263b", skyBottom: "#415a77", accent: "#778da9" },
  { key: "audition_line", name: "Audition Line", minScore: 100, outfit: "hoodie", skyTop: "#415a77", skyBottom: "#778da9", accent: "#e0e1dd" },
  { key: "backlot", name: "Backlot", minScore: 200, outfit: "jacket", skyTop: "#6d4c3d", skyBottom: "#f4a261", accent: "#ffcc33" },
  { key: "trailer", name: "Your Own Trailer", minScore: 300, outfit: "jacket", skyTop: "#415a77", skyBottom: "#f4a261", accent: "#ffcc33" },
  { key: "red_carpet", name: "Premiere Red Carpet", minScore: 400, outfit: "suit", skyTop: "#1b263b", skyBottom: "#c1121f", accent: "#ffcc33" },
  { key: "awards_stage", name: "Awards Stage", minScore: 500, outfit: "suit", skyTop: "#0d1b2a", skyBottom: "#1d2d44", accent: "#ffcc33" },
  { key: "mansion", name: "Hollywood Hills Mansion", minScore: 600, outfit: "tux", skyTop: "#0d1b2a", skyBottom: "#415a77", accent: "#fff5d6" },
  { key: "walk_of_fame", name: "Walk of Fame", minScore: 700, outfit: "tux_star", skyTop: "#0d1b2a", skyBottom: "#ffcc33", accent: "#ffd60a" },
];

export function locationForScore(score: number): LocationDef {
  let result = LOCATIONS[0];
  for (const loc of LOCATIONS) if (score >= loc.minScore) result = loc;
  return result;
}
