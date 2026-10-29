// Canvas climb renderer (R32, R35, R36, R37).
// Renders at a fixed 180x320 internal resolution; the DOM canvas is CSS-scaled
// by integer factors with image smoothing off (set in the component). The world
// scrolls up a distance proportional to score so a 700 run reaches the top.
import { drawBackground, drawCharacter } from "./art";
import { locationForScore, type LocationDef } from "./locations";
import { CHARACTER_ANIMATIONS } from "./manifest";

const IW = 180;
const IH = 320;
const CHAR_X = IW / 2;
const CHAR_Y = Math.floor(IH * 0.62); // fixed center-ish, world scrolls past

export interface TierEffect {
  tier: number; // 0 invalid, 1..6
  shake: boolean;
  confetti: boolean;
  flash: boolean;
  rocket: boolean;
}

function effectForTier(tier: number): TierEffect {
  switch (tier) {
    case 6:
      return { tier, shake: true, confetti: true, flash: true, rocket: true };
    case 5:
      return { tier, shake: true, confetti: false, flash: true, rocket: false };
    case 4:
      return { tier, shake: true, confetti: true, flash: false, rocket: false };
    case 3:
      return { tier, shake: false, confetti: false, flash: true, rocket: false };
    default:
      return { tier, shake: false, confetti: false, flash: false, rocket: false };
  }
}

interface Confetto {
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  life: number;
}

export class ClimbRenderer {
  private ctx: CanvasRenderingContext2D;
  private raf = 0;
  private reducedMotion: boolean;

  // Fame meter 0..700 maps to scroll 0..maxScroll.
  private score = 0;
  private targetScore = 0;
  private maxScore = 700;

  private anim = "idle";
  private animStart = 0;
  private effect: TierEffect | null = null;
  private effectUntil = 0;
  private shakeUntil = 0;
  private flashUntil = 0;
  private confetti: Confetto[] = [];
  private invalidUntil = 0; // shows "CUT!" clapper overlay window

  constructor(ctx: CanvasRenderingContext2D, reducedMotion: boolean) {
    this.ctx = ctx;
    this.reducedMotion = reducedMotion;
  }

  setReducedMotion(v: boolean) {
    this.reducedMotion = v;
  }

  setMaxScore(m: number) {
    this.maxScore = m;
  }

  // Animate a scored answer: ease the world up by the points earned (R32) and
  // trigger the tier effect (R35). points<=0 => stumble + CUT, no climb.
  playScore(points: number, tier: number, now = performance.now()) {
    if (points > 0) {
      this.targetScore = Math.min(this.maxScore, this.targetScore + points);
      this.setAnim("climb", now);
    } else {
      this.setAnim("stumble", now);
      this.invalidUntil = now + (this.reducedMotion ? 500 : 900);
    }
    const eff = effectForTier(tier);
    this.effect = eff;
    this.effectUntil = now + 900;
    if (!this.reducedMotion) {
      if (eff.shake) this.shakeUntil = now + 350;
      if (eff.flash) this.flashUntil = now + 250;
      if (eff.confetti || eff.rocket) this.spawnConfetti(eff.rocket ? 60 : 24);
    }
  }

  private spawnConfetti(n: number) {
    const colors = ["#ffcc33", "#e5383b", "#fff5d6", "#415a77"];
    for (let i = 0; i < n; i++) {
      this.confetti.push({
        x: CHAR_X + (Math.random() * 40 - 20),
        y: CHAR_Y - 20,
        vx: Math.random() * 60 - 30,
        vy: -Math.random() * 80 - 20,
        color: colors[Math.floor(Math.random() * colors.length)],
        life: 1,
      });
    }
  }

  private setAnim(name: string, now: number) {
    if (this.anim !== name) {
      this.anim = name;
      this.animStart = now;
    }
  }

  start() {
    const loop = (ts: number) => {
      this.frame(ts);
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  stop() {
    cancelAnimationFrame(this.raf);
  }

  private currentFrameIndex(now: number): number {
    const def = CHARACTER_ANIMATIONS[this.anim] ?? CHARACTER_ANIMATIONS.idle;
    const elapsed = (now - this.animStart) / 1000;
    const i = Math.floor(elapsed * def.fps);
    if (!def.loop && i >= def.frames.length) {
      // settle back to idle after a one-shot
      if (this.anim !== "idle") this.setAnim("idle", now);
      return CHARACTER_ANIMATIONS.idle.frames[0];
    }
    return def.frames[i % def.frames.length];
  }

  private frame(now: number) {
    const ctx = this.ctx;
    const dt = 1 / 60;

    // Ease displayed score toward target (smooth climb).
    const diff = this.targetScore - this.score;
    this.score += diff * (this.reducedMotion ? 0.5 : 0.12);
    if (Math.abs(diff) < 0.5) this.score = this.targetScore;

    const loc: LocationDef = locationForScore(Math.round(this.score));
    const climbRatio = this.score / this.maxScore; // 0..1
    const worldY = climbRatio * 1000;

    // Screen shake offset.
    let ox = 0;
    let oy = 0;
    if (!this.reducedMotion && now < this.shakeUntil) {
      ox = (Math.random() - 0.5) * 4;
      oy = (Math.random() - 0.5) * 4;
    }

    ctx.save();
    ctx.clearRect(0, 0, IW, IH);
    ctx.translate(ox, oy);

    drawBackground(ctx, loc, worldY, IH);

    // A climbing "pole"/ladder line so vertical motion reads clearly.
    ctx.fillStyle = "#ffffff22";
    for (let y = -((worldY * 2) % 24); y < IH; y += 24) {
      ctx.fillRect(CHAR_X - 1, y, 2, 12);
    }

    const frame = this.currentFrameIndex(now);
    drawCharacter(ctx, CHAR_X, CHAR_Y, loc.outfit, frame);

    // Confetti.
    if (this.confetti.length) {
      for (const c of this.confetti) {
        c.x += c.vx * dt;
        c.y += c.vy * dt;
        c.vy += 120 * dt;
        c.life -= dt;
        if (c.life > 0) {
          ctx.fillStyle = c.color;
          ctx.fillRect(Math.round(c.x), Math.round(c.y), 2, 2);
        }
      }
      this.confetti = this.confetti.filter((c) => c.life > 0);
    }

    // Tier badge bubble over the character.
    if (this.effect && now < this.effectUntil) {
      this.drawTierBadge(ctx, this.effect.tier);
    }

    // Invalid "CUT!" clapperboard.
    if (now < this.invalidUntil) {
      this.drawCut(ctx);
    }

    // Flash overlay.
    if (!this.reducedMotion && now < this.flashUntil) {
      const a = (this.flashUntil - now) / 250;
      ctx.fillStyle = `rgba(255,245,214,${a * 0.6})`;
      ctx.fillRect(-ox, -oy, IW, IH);
    }

    ctx.restore();
  }

  private drawTierBadge(ctx: CanvasRenderingContext2D, tier: number) {
    const labels: Record<number, string> = {
      1: "POPCORN",
      2: "MATINEE",
      3: "MARQUEE",
      4: "CULT",
      5: "DEEP CUT",
      6: "LOST REEL",
    };
    const label = labels[tier];
    if (!label) return;
    const y = CHAR_Y - 34;
    ctx.fillStyle = "#000000cc";
    ctx.fillRect(CHAR_X - 34, y, 68, 12);
    ctx.fillStyle = "#ffcc33";
    ctx.font = "7px monospace";
    ctx.textAlign = "center";
    ctx.fillText(label, CHAR_X, y + 9);
    ctx.textAlign = "left";
  }

  private drawCut(ctx: CanvasRenderingContext2D) {
    const y = CHAR_Y - 36;
    ctx.fillStyle = "#0b090a";
    ctx.fillRect(CHAR_X - 20, y, 40, 14);
    // clapper stripes
    ctx.fillStyle = "#fff5d6";
    for (let i = 0; i < 4; i++) ctx.fillRect(CHAR_X - 20 + i * 10, y, 5, 3);
    ctx.fillStyle = "#e5383b";
    ctx.font = "8px monospace";
    ctx.textAlign = "center";
    ctx.fillText("CUT!", CHAR_X, y + 12);
    ctx.textAlign = "left";
  }
}

export { CHAR_Y, IW, IH };
