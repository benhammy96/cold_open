import { useEffect, useState } from "react";

import { api, type RunResult } from "../api";

interface Props {
  runId: string;
  runToken: string;
}

const TIER_SWATCH: Record<number, string> = {
  0: "bg-dusk",
  1: "bg-[#8a6d3b]",
  2: "bg-gold",
  3: "bg-amber",
  4: "bg-carpet",
  5: "bg-dusk",
  6: "bg-[#9d4edd]",
};

export function ResultScreen({ runId, runToken }: Props) {
  const [result, setResult] = useState<RunResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.result(runId, runToken).then(setResult).catch((e) => setError(String(e)));
  }, [runId, runToken]);

  if (error) return <div className="p-6 text-carpet">{error}</div>;
  if (!result) return <div className="p-6 text-spotlight">Loading your result…</div>;

  const share = result.share;

  const copyShare = async () => {
    try {
      await navigator.clipboard.writeText(share.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-8 text-spotlight md:px-8 md:py-12">
      <div className="marquee-lights mx-auto mb-8 h-2 w-full max-w-xl rounded" aria-hidden />

      {/* Hero: score + location */}
      <div className="text-center">
        <h1 className="font-pixel text-xl text-gold md:text-3xl">That's a wrap!</h1>
        <div className="mt-6 font-pixel text-5xl text-spotlight md:text-7xl">
          {result.total_score}
          <span className="text-2xl text-haze md:text-3xl">/{result.max_score}</span>
        </div>
        <div className="mt-3 text-lg text-gold md:text-xl">
          {share.location_emoji} {result.location_name}
        </div>
        <div className="mt-1 text-sm text-haze">🔥 Streak: {result.streak}</div>

        {/* Emoji grid preview */}
        <div className="mt-6 flex justify-center gap-1.5" aria-hidden>
          {result.submissions.map((s) => (
            <div
              key={s.prompt_index}
              className={`h-8 w-8 rounded ${TIER_SWATCH[s.tier] ?? "bg-dusk"}`}
            />
          ))}
        </div>
      </div>

      {/* Two-column body: breakdown + share, using the width */}
      <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Per-prompt breakdown */}
        <div>
          <h2 className="mb-3 font-pixel text-xs text-gold">YOUR ANSWERS</h2>
          <ul className="space-y-2">
            {result.submissions.map((s) => (
              <li
                key={s.prompt_index}
                className="flex items-center gap-4 rounded-lg bg-navy2/60 px-4 py-3"
              >
                <span
                  className={`h-4 w-4 shrink-0 rounded-sm ${TIER_SWATCH[s.tier] ?? "bg-dusk"}`}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-haze">{s.prompt_text}</div>
                  <div className="truncate text-sm">
                    <span className={s.valid ? "text-spotlight" : "text-carpet"}>
                      {s.valid ? s.canonical_title : s.raw_input || "—"}
                    </span>
                    {s.valid && s.global_percentage > 0 && (
                      <span className="ml-2 text-[11px] text-haze">
                        {s.global_percentage}% named this
                      </span>
                    )}
                  </div>
                </div>
                <span className="shrink-0 font-pixel text-xs text-gold">
                  {s.valid ? `${s.tier_name} +${s.points}` : "CUT +0"}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Share card */}
        <div className="lg:sticky lg:top-6 lg:self-start">
          <h2 className="mb-3 font-pixel text-xs text-gold">SHARE</h2>
          <pre className="whitespace-pre-wrap rounded-lg bg-navy2/60 p-4 text-center text-sm">
            {share.text}
          </pre>
          <button
            onClick={copyShare}
            className="mt-3 w-full rounded-lg bg-gold py-3 font-pixel text-xs text-navy transition-transform hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-gold/60 active:scale-95"
          >
            {copied ? "COPIED!" : "SHARE YOUR SCORE"}
          </button>
          <p className="mt-4 text-center text-[11px] text-haze">
            Come back tomorrow for a new Cold Open. Uses the TMDB API but is not
            endorsed or certified by TMDB.
          </p>
        </div>
      </div>
    </div>
  );
}
