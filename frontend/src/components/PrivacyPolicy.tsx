import { useEffect } from "react";

// Minimal, honest privacy policy (R57). The game is anonymous by default and
// collects minimal data; this states exactly what and why. Shown as an overlay
// so no router is needed.
export function PrivacyPolicy({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Privacy policy"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-lg bg-navy2 p-5 text-sm text-spotlight"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-pixel text-base text-gold">Privacy</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded px-2 py-1 text-haze hover:text-spotlight"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 text-[13px] leading-relaxed text-spotlight/90">
          <p>
            Cold Open is anonymous by default. You can play without an account and
            we don't ask for your name, email, or any personal details.
          </p>
          <p>
            <strong className="text-spotlight">Stored in your browser:</strong> a
            random anonymous ID, your current run, and your streak — all kept in
            this device's local storage. Clearing your browser data resets them.
          </p>
          <p>
            <strong className="text-spotlight">Stored on our server:</strong> your
            anonymous ID, the answers you submit, and your scores — used to run the
            game, compute rarity, and keep your streak. Submitted answers that
            don't match are logged (without the anonymous ID attached) to improve
            the answer database.
          </p>
          <p>
            <strong className="text-spotlight">We don't:</strong> sell data, run
            third-party ad or analytics trackers, or share your data except as
            needed to operate the game.
          </p>
          <p>
            Movie and TV data is provided by{" "}
            <a
              href="https://www.themoviedb.org/"
              target="_blank"
              rel="noreferrer noopener"
              className="underline hover:text-gold"
            >
              The Movie Database (TMDB)
            </a>
            . This product uses the TMDB API but is not endorsed or certified by
            TMDB.
          </p>
          <p className="text-haze">Last updated: when this build shipped.</p>
        </div>
      </div>
    </div>
  );
}
