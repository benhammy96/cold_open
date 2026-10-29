import { useCallback, useEffect, useState } from "react";

import { api, type Daily, type StartRun } from "./api";
import { getAnonToken, prefersReducedMotion } from "./player";
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
    api
      .getDaily()
      .then((d) => {
        setDaily(d);
        setPhase("intro");
      })
      .catch((e) => {
        setError(String(e));
        setPhase("error");
      });
  }, []);

  const begin = useCallback(async () => {
    if (!daily) return;
    try {
      const started = await api.startRun(getAnonToken(), "daily");
      setRun(started);
      // If they already finished today, jump straight to the result (R5).
      setPhase(started.already_completed ? "result" : "playing");
    } catch (e) {
      setError(String(e));
      setPhase("error");
    }
  }, [daily]);

  return (
    <div className="theater-bg relative flex min-h-dvh items-center justify-center overflow-hidden">
      {/* Drifting spotlight glow behind everything (desktop ambiance). */}
      <div className="theater-spot pointer-events-none absolute inset-0 hidden md:block" aria-hidden />

      {/* Wide-screen layout: info panel + framed phone, centered together. */}
      <div className="relative z-10 flex w-full max-w-5xl items-stretch justify-center gap-0 md:gap-8 md:px-6">
        {/* Left info panel — only on large screens, fills the void with context. */}
        <aside className="hidden flex-col justify-center py-10 text-spotlight lg:flex lg:w-80">
          <h1 className="font-pixel text-3xl leading-tight text-gold">
            COLD
            <br />
            OPEN
          </h1>
          <p className="mt-4 text-sm text-haze">
            A daily movie &amp; TV game. Everyone gets the same 7 prompts. The
            rarer your answer, the higher you climb the fame ladder.
          </p>
          <ol className="mt-6 space-y-2 text-sm text-spotlight/90">
            <li>
              <span className="font-pixel text-xs text-gold">1 </span>
              Read the prompt, type one answer.
            </li>
            <li>
              <span className="font-pixel text-xs text-gold">2 </span>
              Obvious answers barely score. Deep cuts launch you up.
            </li>
            <li>
              <span className="font-pixel text-xs text-gold">3 </span>
              Finish all 7 and share your score — no spoilers.
            </li>
          </ol>
          <p className="mt-8 text-[11px] text-haze/70">
            Best on a phone, but right at home here too. Keyboard only: type and
            press Enter.
          </p>
        </aside>

        {/* Film strip + phone column. */}
        <div className="film-strip hidden w-5 md:block" aria-hidden />
        <div className="relative flex h-dvh w-full max-w-[430px] flex-col overflow-hidden bg-navy shadow-[0_0_60px_rgba(0,0,0,0.6)] md:my-6 md:h-[min(860px,calc(100dvh-3rem))] md:rounded-[1.75rem] md:border md:border-white/10 md:shadow-[0_0_80px_rgba(255,204,51,0.08)]">
        {phase === "loading" && <Centered>Loading today's Cold Open…</Centered>}

        {phase === "error" && (
          <Centered>
            <div className="text-carpet">Couldn't load the game.</div>
            <div className="mt-2 text-xs text-haze">{error}</div>
            <div className="mt-2 text-xs text-haze">
              Is the backend running on :8000?
            </div>
          </Centered>
        )}

        {phase === "intro" && daily && (
          <Centered>
            <h1 className="font-pixel text-2xl text-gold">COLD OPEN</h1>
            <p className="mt-2 text-sm text-spotlight">#{daily.number}</p>
            <p className="mt-4 max-w-[18rem] text-center text-sm text-haze">
              {daily.prompt_count} prompts. {daily.seconds_per_prompt} seconds each.
              The rarer your answer, the higher you climb.
            </p>
            <button
              onClick={begin}
              className="mt-6 rounded bg-gold px-6 py-3 font-pixel text-sm text-navy"
            >
              PLAY
            </button>
          </Centered>
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
          <ResultScreen runId={run.run_id} runToken={run.run_token} />
        )}
        </div>
        <div className="film-strip hidden w-5 md:block" aria-hidden />
      </div>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 text-spotlight">
      {children}
    </div>
  );
}
