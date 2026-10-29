// Thin API client. The client never sees valid answers or rarity before
// submission (R10) — these types reflect exactly what the server returns.

export interface PromptPublic {
  index: number;
  text: string;
}

export interface Daily {
  date: string;
  number: number;
  mode: string;
  prompt_count: number;
  seconds_per_prompt: number;
  max_score: number;
  prompts: PromptPublic[];
}

export interface StartRun {
  run_id: string;
  run_token: string;
  mode: string;
  date: string | null;
  prompt_count: number;
  seconds_per_prompt: number;
  current_index: number;
  already_completed: boolean;
}

export interface AnswerResult {
  valid: boolean;
  tier: number;
  tier_name: string;
  points: number;
  canonical_title: string | null;
  total_score: number;
  next_index: number;
  done: boolean;
  reason: string | null;
}

export interface SubmissionResult {
  prompt_index: number;
  prompt_text: string;
  raw_input: string;
  valid: boolean;
  tier: number;
  tier_name: string;
  points: number;
  canonical_title: string | null;
  global_percentage: number;
}

export interface ShareCard {
  number: number;
  total_score: number;
  max_score: number;
  grid: string;
  location_name: string;
  location_emoji: string;
  streak: number;
  text: string;
}

export interface RunResult {
  run_id: string;
  mode: string;
  date: string | null;
  total_score: number;
  max_score: number;
  location_key: string;
  location_name: string;
  outfit: string;
  streak: number;
  status: string;
  submissions: SubmissionResult[];
  share: ShareCard;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getDaily: (date?: string) =>
    req<Daily>(`/api/daily${date ? `?date=${date}` : ""}`),

  startRun: (anonToken: string, mode = "daily", date?: string) =>
    req<StartRun>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ anon_token: anonToken, mode, date }),
    }),

  answer: (
    runId: string,
    runToken: string,
    promptIndex: number,
    rawInput: string,
    timedOut = false,
  ) =>
    req<AnswerResult>(`/api/runs/${runId}/answer`, {
      method: "POST",
      body: JSON.stringify({
        run_token: runToken,
        prompt_index: promptIndex,
        raw_input: rawInput,
        timed_out: timedOut,
      }),
    }),

  complete: (runId: string, runToken: string) =>
    req<{ total_score: number; streak: number; freezes: number; location_name: string }>(
      `/api/runs/${runId}/complete`,
      { method: "POST", body: JSON.stringify({ run_token: runToken }) },
    ),

  result: (runId: string, runToken: string) =>
    req<RunResult>(`/api/runs/${runId}/result?run_token=${encodeURIComponent(runToken)}`),
};
