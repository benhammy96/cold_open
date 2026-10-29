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
    <div className="flex h-full flex-col overflow-y-auto bg-navy px-5 py-6 text-spotlight">
      <h1 className="text-center font-pixel text-lg text-gold">That's a wrap!</h1>

      <div className="my-4 text-center">
        <div className="font-pixel text-4xl text-spotlight">
          {result.total_score}
          <span className="text-base text-haze">/{result.max_score}</span>
        </div>
        <div className="mt-1 text-sm text-gold">
          {share.location_emoji} {result.location_name}
        </div>
        <div className="text-xs text-haze">🔥 Streak: {result.streak}</div>
      </div>

      {/* Emoji grid preview */}
      <div className="mb-4 flex justify-center gap-1" aria-hidden>
        {result.submissions.map((s) => (
          <div
            key={s.prompt_index}
            className={`h-6 w-6 rounded-sm ${TIER_SWATCH[s.tier] ?? "bg-dusk"}`}
          />
        ))}
      </div>

      {/* Per-prompt reveal */}
      <ul className="mb-4 space-y-2">
        {result.submissions.map((s) => (
          <li
            key={s.prompt_index}
            className="rounded bg-navy2 px-3 py-2 text-sm"
          >
            <div className="text-xs text-haze">{s.prompt_text}</div>
            <div className="flex items-center justify-between">
              <span className={s.valid ? "text-spotlight" : "text-carpet"}>
                {s.valid ? s.canonical_title : s.raw_input || "—"}
              </span>
              <span className="font-pixel text-xs text-gold">
                {s.valid ? `${s.tier_name} +${s.points}` : "CUT +0"}
              </span>
            </div>
            {s.valid && s.global_percentage > 0 && (
              <div className="text-[10px] text-haze">
                {s.global_percentage}% of players named this
              </div>
            )}
          </li>
        ))}
      </ul>

      <pre className="mb-3 whitespace-pre-wrap rounded bg-navy2 p-3 text-center text-sm">
        {share.text}
      </pre>

      <button
        onClick={copyShare}
        className="rounded bg-gold py-3 font-pixel text-xs text-navy"
      >
        {copied ? "COPIED!" : "SHARE YOUR SCORE"}
      </button>

      <p className="mt-4 text-center text-[11px] text-haze">
        Come back tomorrow for a new Cold Open. This product uses movie &amp; TV
        data modeled on TMDB and is not endorsed or certified by TMDB.
      </p>
    </div>
  );
}
