import { useCallback, useEffect, useRef, useState } from "react";

import { api, type AnswerResult, type Daily, type StartRun } from "../api";
import { ClimbCanvas, type ClimbHandle } from "../components/ClimbCanvas";
import { rememberRun } from "../player";

interface Props {
  daily: Daily;
  run: StartRun;
  reducedMotion: boolean;
  onReducedMotionChange: (v: boolean) => void;
  onDone: () => void;
}

interface Reveal {
  valid: boolean;
  tierName: string;
  points: number;
  canonicalTitle: string | null;
  reason: string | null;
}

// A completed prompt's outcome, kept so the side panel can show rarity history
// across the run (desktop uses the extra width for this).
interface HistoryItem {
  index: number;
  valid: boolean;
  tier: number;
  tierName: string;
  points: number;
  canonicalTitle: string | null;
}

// Tier -> swatch color (mirrors ResultScreen). Used in the progress rail.
const TIER_COLOR: Record<number, string> = {
  0: "#415a77",
  1: "#8a6d3b",
  2: "#ffcc33",
  3: "#f4a261",
  4: "#c1121f",
  5: "#415a77",
  6: "#9d4edd",
};

export function GameScreen({
  daily,
  run,
  reducedMotion,
  onReducedMotionChange,
  onDone,
}: Props) {
  const [index, setIndex] = useState(run.current_index);
  const [score, setScore] = useState(0);
  const [input, setInput] = useState("");
  const [timeLeft, setTimeLeft] = useState(daily.seconds_per_prompt);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const climbRef = useRef<ClimbHandle>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const submittingRef = useRef(false);

  const prompt = daily.prompts[index];
  const total = daily.prompt_count;

  const submit = useCallback(
    async (raw: string, timedOut: boolean) => {
      if (submittingRef.current || locked || !prompt) return;
      submittingRef.current = true;
      setLocked(true);
      try {
        const res: AnswerResult = await api.answer(
          run.run_id,
          run.run_token,
          index,
          raw,
          timedOut,
        );
        setScore(res.total_score);
        climbRef.current?.playScore(res.points, res.valid ? res.tier : 0);
        setReveal({
          valid: res.valid,
          tierName: res.tier_name,
          points: res.points,
          canonicalTitle: res.canonical_title,
          reason: res.reason,
        });
        setHistory((h) => [
          ...h,
          {
            index,
            valid: res.valid,
            tier: res.valid ? res.tier : 0,
            tierName: res.tier_name,
            points: res.points,
            canonicalTitle: res.canonical_title,
          },
        ]);

        // Brief reveal pause, then advance or finish.
        const delay = reducedMotion ? 650 : 1100;
        window.setTimeout(async () => {
          if (res.done) {
            await api.complete(run.run_id, run.run_token);
            onDone();
            return;
          }
          setIndex(res.next_index);
          setInput("");
          setReveal(null);
          setTimeLeft(daily.seconds_per_prompt);
          setLocked(false);
          submittingRef.current = false;
          inputRef.current?.focus();
        }, delay);
      } catch (e) {
        setError(String(e));
        setLocked(false);
        submittingRef.current = false;
      }
    },
    [index, locked, prompt, reducedMotion, run, daily.seconds_per_prompt, onDone],
  );

  // Per-prompt countdown (R3/R4). Submits whatever is typed at zero.
  useEffect(() => {
    if (locked || reveal) return;
    if (timeLeft <= 0) {
      submit(input, true);
      return;
    }
    const id = window.setTimeout(() => setTimeLeft((t) => t - 1), 1000);
    return () => window.clearTimeout(id);
  }, [timeLeft, locked, reveal, input, submit]);

  useEffect(() => {
    rememberRun(daily.date, run.run_id, run.run_token);
  }, [daily.date, run]);

  // On a resumed run (starting past prompt 0), hydrate the HUD score and snap
  // the climb to the height already earned so the character doesn't start over.
  useEffect(() => {
    if (run.current_index <= 0) return;
    let cancelled = false;
    api
      .result(run.run_id, run.run_token)
      .then((res) => {
        if (cancelled) return;
        setScore(res.total_score);
        climbRef.current?.setScoreInstant(res.total_score);
        setHistory(
          res.submissions.map((s) => ({
            index: s.prompt_index,
            valid: s.valid,
            tier: s.tier,
            tierName: s.tier_name,
            points: s.points,
            canonicalTitle: s.canonical_title,
          })),
        );
      })
      .catch(() => {
        /* best-effort hydration; gameplay continues regardless */
      });
    return () => {
      cancelled = true;
    };
    // Run once on mount for a resumed run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    inputRef.current?.focus();
  }, [index]);

  const onSubmitForm = (e: React.FormEvent) => {
    e.preventDefault();
    submit(input, false);
  };

  const timerPct = Math.max(0, (timeLeft / daily.seconds_per_prompt) * 100);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* ---------- Top bar: full width ---------- */}
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-white/10 bg-navy2/80 px-4 py-3 backdrop-blur md:px-8">
        <div className="flex items-baseline gap-3">
          <span className="font-pixel text-base text-gold md:text-xl">COLD OPEN</span>
          <span className="hidden text-xs text-haze sm:inline md:text-sm">
            #{daily.number} · {daily.date}
          </span>
        </div>
        <div className="flex items-center gap-5 md:gap-8">
          <Stat label="Prompt" value={`${Math.min(index + 1, total)}/${total}`} />
          <Stat label="Score" value={String(score)} live />
          <Stat
            label="Time"
            value={`0:${String(Math.max(0, timeLeft)).padStart(2, "0")}`}
            danger={timeLeft <= 5}
          />
        </div>
      </header>

      {/* Full-width timer bar */}
      <div className="h-1.5 shrink-0 bg-navy2" aria-hidden>
        <div
          className={`h-full transition-[width] duration-1000 ease-linear ${
            timeLeft <= 5 ? "bg-carpet" : "bg-gold"
          }`}
          style={{ width: `${timerPct}%` }}
        />
      </div>

      {/* ---------- Main region: left rail · stage · right rail ---------- */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
        {/* Left rail: run progress (hidden on small screens) */}
        <aside className="hidden min-h-0 flex-col gap-4 overflow-y-auto border-r border-white/10 bg-navy2/40 p-5 lg:flex">
          <h2 className="font-pixel text-xs text-gold">PROGRESS</h2>
          <ol className="space-y-1.5">
            {Array.from({ length: total }).map((_, i) => {
              const h = history.find((x) => x.index === i);
              const isCurrent = i === index && !reveal;
              return (
                <li
                  key={i}
                  className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs ${
                    isCurrent ? "bg-white/10 text-spotlight" : "text-haze"
                  }`}
                >
                  <span
                    className="inline-block h-3 w-3 shrink-0 rounded-sm"
                    style={{
                      backgroundColor: h ? TIER_COLOR[h.tier] : "#1b263b",
                      outline: isCurrent ? "1px solid #ffcc33" : "none",
                    }}
                    aria-hidden
                  />
                  <span className="truncate">
                    {h ? (h.valid ? `+${h.points}` : "CUT") : `Prompt ${i + 1}`}
                  </span>
                </li>
              );
            })}
          </ol>
          <div className="mt-auto rounded-lg bg-navy/60 p-3 text-[11px] leading-relaxed text-haze">
            The rarer your answer, the higher you climb. Obvious picks barely
            move the needle.
          </div>
        </aside>

        {/* Central stage: the enlarged pixel scene. The canvas wrapper is
            absolutely positioned so it always fills the stage regardless of how
            the grid row resolves its height (avoids a collapsed h-full in a
            grid cell). */}
        <main className="stage relative min-h-[40vh] overflow-hidden lg:min-h-0">
          {/* Marquee lights framing the top of the stage */}
          <div className="marquee-lights pointer-events-none absolute inset-x-0 top-0 z-10 h-1.5" aria-hidden />
          <div className="absolute inset-0 flex items-center justify-center p-4">
            <ClimbCanvas
              ref={climbRef}
              maxScore={daily.max_score}
              reducedMotion={reducedMotion}
            />
          </div>
          {/* Floating tier badge over the stage on a fresh reveal (desktop flourish) */}
          {reveal && (
            <div
              className="pointer-events-none absolute left-1/2 top-6 -translate-x-1/2"
              aria-hidden
            >
              <span
                className={`rounded-full px-4 py-1.5 font-pixel text-xs shadow-lg ${
                  reveal.valid ? "bg-gold text-navy" : "bg-carpet text-spotlight"
                }`}
              >
                {reveal.valid ? `${reveal.tierName} +${reveal.points}` : "CUT! +0"}
              </span>
            </div>
          )}
        </main>

        {/* Right rail: live rarity feedback (hidden on small screens) */}
        <aside className="hidden min-h-0 flex-col overflow-y-auto border-l border-white/10 bg-navy2/40 p-5 lg:flex">
          <h2 className="font-pixel text-xs text-gold">LAST ANSWER</h2>
          <div className="mt-3 min-h-[5.5rem]" aria-live="polite">
            {reveal ? (
              <RarityCard reveal={reveal} />
            ) : (
              <p className="text-sm text-haze">
                Answer the prompt to see how rare your pick was.
              </p>
            )}
          </div>

          <h2 className="mt-6 font-pixel text-xs text-gold">RARITY TIERS</h2>
          <ul className="mt-3 space-y-1 text-[11px] text-haze">
            {[
              ["Popcorn", 10, 1],
              ["Matinee", 25, 2],
              ["Marquee", 40, 3],
              ["Cult Classic", 60, 4],
              ["Deep Cut", 80, 5],
              ["Lost Reel", 100, 6],
            ].map(([name, pts, tier]) => (
              <li key={name as string} className="flex items-center gap-2">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: TIER_COLOR[tier as number] }}
                  aria-hidden
                />
                <span className="flex-1">{name}</span>
                <span className="text-spotlight/70">+{pts}</span>
              </li>
            ))}
          </ul>
        </aside>
      </div>

      {/* ---------- Prompt + input: full-width band beneath the stage ---------- */}
      <div className="film-strip-h shrink-0" aria-hidden style={{ height: 0 }} />
      <footer className="shrink-0 border-t border-white/10 bg-navy2/80 px-4 py-4 backdrop-blur md:px-8 md:py-5">
        <div className="mx-auto w-full max-w-3xl">
          <p
            className="mb-3 text-center text-lg font-medium leading-snug text-spotlight md:text-2xl"
            aria-live="polite"
          >
            {prompt?.text ?? "…"}
          </p>
          <form onSubmit={onSubmitForm} className="flex gap-3">
            <label htmlFor="answer" className="sr-only">
              Your answer
            </label>
            <input
              id="answer"
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={locked}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder="Type a movie or show…"
              className="min-w-0 flex-1 rounded-lg border-2 border-dusk bg-navy px-4 py-3 text-base text-spotlight outline-none transition-colors placeholder:text-haze hover:border-haze focus:border-gold focus:ring-2 focus:ring-gold/40 disabled:opacity-50 md:text-lg"
            />
            <button
              type="submit"
              disabled={locked}
              className="rounded-lg bg-gold px-6 py-3 font-pixel text-xs text-navy transition-transform hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-gold/60 active:scale-95 disabled:opacity-50 md:text-sm"
            >
              GO
            </button>
          </form>
          <div className="mt-2 flex items-center justify-between text-[11px] text-haze">
            <label className="flex cursor-pointer items-center gap-1.5">
              <input
                type="checkbox"
                checked={reducedMotion}
                onChange={(e) => onReducedMotionChange(e.target.checked)}
                className="accent-gold"
              />
              Reduce motion
            </label>
            <span>Press Enter to submit</span>
          </div>
          {error && <p className="mt-2 text-center text-xs text-carpet">{error}</p>}
        </div>
      </footer>
    </div>
  );
}

// Compact labeled stat for the top bar.
function Stat({
  label,
  value,
  live,
  danger,
}: {
  label: string;
  value: string;
  live?: boolean;
  danger?: boolean;
}) {
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wide text-haze">{label}</div>
      <div
        className={`font-pixel text-sm md:text-base ${danger ? "text-carpet" : "text-spotlight"}`}
        aria-live={live ? "polite" : "off"}
      >
        {value}
      </div>
    </div>
  );
}

// Rich rarity feedback card for the right rail (uses the extra desktop width).
function RarityCard({ reveal }: { reveal: Reveal }) {
  if (!reveal.valid) {
    return (
      <div className="rounded-lg border border-carpet/40 bg-carpet/10 p-4">
        <div className="font-pixel text-sm text-carpet">CUT! +0</div>
        <div className="mt-1 text-sm text-spotlight/80">
          {reveal.reason === "duplicate"
            ? "You already used that one this run."
            : "No match found for that answer."}
        </div>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-gold/40 bg-gold/10 p-4">
      <div className="font-pixel text-base text-gold">{reveal.tierName}</div>
      <div className="mt-1 text-2xl font-bold text-spotlight">+{reveal.points}</div>
      {reveal.canonicalTitle && (
        <div className="mt-1 text-sm text-spotlight/80">{reveal.canonicalTitle}</div>
      )}
    </div>
  );
}
