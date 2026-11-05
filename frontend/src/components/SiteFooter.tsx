import { useState } from "react";

import { PrivacyPolicy } from "./PrivacyPolicy";

// Persistent footer: TMDB attribution (R54) shown wherever TMDB data appears,
// plus a link to the privacy policy (R57). Kept compact for the phone column.
export function SiteFooter() {
  const [showPrivacy, setShowPrivacy] = useState(false);
  return (
    <>
      <footer className="shrink-0 border-t border-white/10 bg-navy px-3 py-2 text-center text-[10px] leading-tight text-haze/80">
        <span>
          Uses the{" "}
          <a
            href="https://www.themoviedb.org/"
            target="_blank"
            rel="noreferrer noopener"
            className="underline hover:text-gold"
          >
            TMDB
          </a>{" "}
          API but is not endorsed or certified by TMDB.
        </span>
        <span aria-hidden> · </span>
        <button onClick={() => setShowPrivacy(true)} className="underline hover:text-gold">
          Privacy
        </button>
      </footer>
      {showPrivacy && <PrivacyPolicy onClose={() => setShowPrivacy(false)} />}
    </>
  );
}
