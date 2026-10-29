// Anonymous local-storage identity (R30). No login; a stable token per browser.
const KEY = "coldopen.anon_token";

export function getAnonToken(): string {
  let t = localStorage.getItem(KEY);
  if (!t) {
    t =
      "anon_" +
      (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36));
    localStorage.setItem(KEY, t);
  }
  return t;
}

// Remember the run id for a given date so a refresh resumes the same run (R7/R8).
export function rememberRun(date: string, runId: string, runToken: string) {
  localStorage.setItem(`coldopen.run.${date}`, JSON.stringify({ runId, runToken }));
}

export function recallRun(date: string): { runId: string; runToken: string } | null {
  const raw = localStorage.getItem(`coldopen.run.${date}`);
  return raw ? JSON.parse(raw) : null;
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}
