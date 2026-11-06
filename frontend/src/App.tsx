import { useCallback, useEffect, useState } from "react";

import { api, type Daily, type StartRun } from "./api";
import { getAnonToken, prefersReducedMotion, recallRun, rememberRun } from "./player";
import { SiteFooter } from "./components/SiteFooter";
import { GameScreen } from "./screens/GameScreen";
import { ResultScreen } from "./screens/ResultScreen";

type Phase = "loading" | "intro" | "playing" | "result" | "error";

export default function App() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [daily, setDaily] = useState<Daily | null>(null);
  const [run, setRun] = useState<StartRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await api.getDaily();
        if (cancelled) return;
        setDaily(d);

        // Resume-on-refresh (R7). If we have a remembered run for today, rejoin
        // it instead of showing the intro.
        const remembered = recallRun(d.date);
        if (remembered) {
          try {
            const result = await api.result(remembered.runId, remembered.runToken);
            if (cancelled) return;
            if (result.status === "complete") {
              // Already finished today -> show the saved result (R5).
              setRun(resumeStub(remembered, d));
              setPhase("result");
              return;
            }
            // In progress: re-establish the run via the idempotent start, then
            // resume. start_run returns the existing run with its current_index.
            const started = await api.startRun(getAnonToken(), "daily");
            if (cancelled) return;
            const resumed = await forfeitInProgressPrompt(started);
            setRun(resumed);
            setPhase(resumed.already_completed ? "result" : "playing");
            return;
          } catch {
            // Remembered run is stale/invalid; fall through to a clean intro.
          }
        }
        setPhase("intro");
      } catch (e) {
        if (cancelled) return;
        setError(String(e));
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const begin = useCallback(async () => {
    if (!daily) return;
    try {
      const started = await api.startRun(getAnonToken(), "daily");
      rememberRun(daily.date, started.run_id, started.run_token);
      setRun(started);
      // If they already finished today, jump straight to the result (R5).
      setPhase(started.already_completed ? "result" : "playing");
    } catch (e) {
      setError(String(e));
      setPhase("error");
    }
  }, [daily]);

  return (
    // Full-viewport theater. No phone column — regions fill 100vw/100vh.
    <div className="theater-bg relative flex h-dvh w-full flex-col overflow-hidden">
      {/* Drifting spotlight glow behind everything. */}
      <div className="theater-spot pointer-events-none absolute inset-0" aria-hidden />

      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        {phase === "loading" && <Centered>Loading today's Cold Open…</Centered>}

        {phase === "error" && (
          <Centered>
            <div className="font-pixel text-carpet">Couldn't load the game.</div>
            <div className="mt-3 max-w-md text-sm text-haze">{error}</div>
            <div className="mt-2 text-xs text-haze">
              Is the backend reachable?
            </div>
          </Centered>
        )}

        {phase === "intro" && daily && (
          <IntroScreen daily={daily} onPlay={begin} />
        )}

        {phase === "playing" && daily && run && (
          <GameScreen
            daily={daily}
            run={run}
            reducedMotion={reducedMotion}
            onReducedMotionChange={setReducedMotion}
            onDone={() => setPhase("result")}
          />
        )}

        {phase === "result" && run && (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <ResultScreen runId={run.run_id} runToken={run.run_token} />
          </div>
        )}
      </div>

      <SiteFooter />
    </div>
  );
}

// Desktop-first intro: a wide marquee hero with the title, how-to, and PLAY.
function IntroScreen({ daily, onPlay }: { daily: Daily; onPlay: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center p-6">
      <div className="w-full max-w-4xl">
        <div className="marquee-lights mx-auto mb-8 h-2 w-full max-w-2xl rounded" aria-hidden />
        <div className="text-center">
          <h1 className="font-pixel text-4xl leading-tight text-gold md:text-6xl">
            COLD OPEN
          </h1>
          <p className="mt-4 text-sm text-haze md:text-base">
            Daily #{daily.number} · {daily.date}
          </p>
          <p className="mx-auto mt-6 max-w-xl text-base text-spotlight/90 md:text-lg">
            Everyone gets the same {daily.prompt_count} prompts. You've got{" "}
            {daily.seconds_per_prompt} seconds each. The rarer your answer, the
            higher your little star climbs the fame ladder.
          </p>
        </div>

        <div className="mx-auto mt-10 grid max-w-3xl gap-4 sm:grid-cols-3">
          {[
            ["1", "Read the prompt", "Type one movie or show."],
            ["2", "Rarer is better", "Obvious picks barely score; deep cuts launch you up."],
            ["3", "Finish & share", "All 7 prompts, then a spoiler-free score card."],
          ].map(([n, title, body]) => (
            <div
              key={n}
              className="rounded-xl border border-white/10 bg-navy2/50 p-5 text-left"
            >
              <div className="font-pixel text-sm text-gold">{n}</div>
              <div className="mt-2 font-medium text-spotlight">{title}</div>
              <div className="mt-1 text-sm text-haze">{body}</div>
            </div>
          ))}
        </div>

        <div className="mt-10 text-center">
          <button
            onClick={onPlay}
            className="rounded-lg bg-gold px-10 py-4 font-pixel text-base text-navy transition-transform hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-gold/60 active:scale-95"
          >
            PLAY
          </button>
        </div>
        <div className="marquee-lights mx-auto mt-8 h-2 w-full max-w-2xl rounded" aria-hidden />
      </div>
    </div>
  );
}

// The ResultScreen only reads run_id + run_token, so a light stub is enough when
// resuming directly into a completed result.
function resumeStub(
  remembered: { runId: string; runToken: string },
  daily: Daily,
): StartRun {
  return {
    run_id: remembered.runId,
    run_token: remembered.runToken,
    mode: "daily",
    date: daily.date,
    prompt_count: daily.prompt_count,
    seconds_per_prompt: daily.seconds_per_prompt,
    current_index: daily.prompt_count,
    already_completed: true,
  };
}

// R7: the prompt that was in progress when the tab closed is forfeited. We
// submit a timed-out (empty) answer for the run's current prompt, then return
// the run advanced to the next index. If the run was between prompts (nothing in
// progress) the server rejects the out-of-range/duplicate index and we just keep
// the run as-is.
async function forfeitInProgressPrompt(run: StartRun): Promise<StartRun> {
  if (run.already_completed || run.current_index >= run.prompt_count) {
    return run;
  }
  try {
    const res = await api.answer(
      run.run_id,
      run.run_token,
      run.current_index,
      "",
      true, // timed_out
    );
    return { ...run, current_index: res.next_index, already_completed: res.done };
  } catch {
    // Index mismatch or similar: leave the run untouched and resume normally.
    return run;
  }
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center p-6 text-center text-spotlight">
      {children}
    </div>
  );
}
