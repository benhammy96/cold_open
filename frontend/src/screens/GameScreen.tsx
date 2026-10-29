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

  useEffect(() => {
    inputRef.current?.focus();
  }, [index]);

  const onSubmitForm = (e: React.FormEvent) => {
    e.preventDefault();
    submit(input, false);
  };

  const timerPct = Math.max(0, (timeLeft / daily.seconds_per_prompt) * 100);

  return (
    <div className="flex h-full flex-col">
      {/* Thin HUD (R41) */}
      <div className="flex items-center justify-between bg-navy2 px-3 py-2 text-xs text-spotlight">
        <span className="font-pixel">
          {index + 1}/{total}
        </span>
        <span aria-live="polite">Score {score}</span>
        <span className={timeLeft <= 5 ? "text-carpet" : "text-gold"} aria-live="off">
          :{String(timeLeft).padStart(2, "0")}
        </span>
      </div>
      <div className="h-1 bg-navy2" aria-hidden>
        <div
          className="h-full bg-gold transition-[width] duration-1000 ease-linear"
          style={{ width: `${timerPct}%` }}
        />
      </div>

      {/* Pixel world */}
      <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-navy">
        <div className="flex h-full items-center justify-center py-2">
          <ClimbCanvas
            ref={climbRef}
            maxScore={daily.max_score}
            reducedMotion={reducedMotion}
          />
        </div>
      </div>

      {/* Prompt + input (R41) */}
      <div className="bg-navy2 px-4 pb-5 pt-4">
        {reveal ? (
          <div
            className="mb-3 min-h-[3.5rem] text-center"
            aria-live="assertive"
            role="status"
          >
            {reveal.valid ? (
              <>
                <div className="font-pixel text-sm text-gold">
                  {reveal.tierName} +{reveal.points}
                </div>
                <div className="text-xs text-spotlight/80">{reveal.canonicalTitle}</div>
              </>
            ) : (
              <div className="font-pixel text-sm text-carpet">
                CUT! {reveal.reason === "duplicate" ? "Already used" : "No match"} +0
              </div>
            )}
          </div>
        ) : (
          <p className="mb-3 min-h-[3.5rem] text-center text-base font-medium leading-snug text-spotlight">
            {prompt?.text}
          </p>
        )}

        <form onSubmit={onSubmitForm}>
          <label htmlFor="answer" className="sr-only">
            Your answer
          </label>
          <div className="flex gap-2">
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
              className="min-w-0 flex-1 rounded border-2 border-dusk bg-navy px-3 py-3 text-spotlight placeholder:text-haze focus:border-gold focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={locked}
              className="rounded bg-gold px-4 py-3 font-pixel text-xs text-navy disabled:opacity-50"
            >
              GO
            </button>
          </div>
        </form>

        <div className="mt-2 flex items-center justify-between text-[10px] text-haze">
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={reducedMotion}
              onChange={(e) => onReducedMotionChange(e.target.checked)}
            />
            Reduce motion
          </label>
          <span>Enter to submit</span>
        </div>

        {error && <p className="mt-2 text-xs text-carpet">{error}</p>}
      </div>
    </div>
  );
}
