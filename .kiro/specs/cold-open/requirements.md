# Requirements — Cold Open

> Source of truth: the project handoff document. This file formalizes that handoff into reviewable requirements. Requirements use EARS phrasing ("WHEN ... THE SYSTEM SHALL ...", "THE SYSTEM SHALL ..."). Decisions already made by the product owner are marked **[DECISION]**; items awaiting a call are marked **[OPEN — proposed default]** with my recommendation.

## 1. Introduction

Cold Open is a free, browser-based daily game for movie and TV fans. Every day, all players receive the same 7 prompts about film and television. Players type one answer per prompt; the **rarer** a valid answer, the more points it scores. The experience is framed as a 2D pixel-art rags-to-fame climb: good answers launch a fixed, center-screen character up a vertical fame ladder, and the location reached is the player's daily rank.

This document defines the behavior for the MVP (Daily + Endless + the pixel-art climb) and names the v1/v2 features it must not block.

### 1.1 Goals (measured over first 30 days post-launch)

- Day-1 → Day-7 return rate above 25%.
- Average session length 3–5 minutes.
- Share rate above 15% of completed Dailies.
- No more than one scoring dispute per week requiring a manual fix.

### 1.2 Scope

- **In scope (MVP):** Daily Cold Open, Endless, server-authoritative matching and scoring, prior+observed rarity blend, pixel-art climb renderer with placeholder art, results + share card, anonymous local-storage identity and streaks, TMDB ingestion and prompt authoring pipeline.
- **In scope (v1, must not be blocked):** Themed Packs, Friend Challenge, OG image generation, optional sign-in with cross-device streaks, web push reminders, admin review queue.
- **Out of scope (now):** Live Rooms / real-time multiplayer, monetization, native apps, user-generated prompts, comments/chat.

### 1.3 Decisions on open questions (from handoff §13)

These are proposed defaults that shape the requirements below. Please confirm or override.

- **Q1 — mixed movie/TV answers:** **[OPEN — proposed default]** Prompts are *typed per prompt* (a prompt declares which entity types it accepts). A prompt may accept both movies and TV when its wording clearly allows it (e.g. "Name a story set in space" would be open; "Name a movie set in space" is movie-only). Default: prompt-level `accepted_entity_types` list.
- **Q2 — identical titles / remakes:** **[OPEN — proposed default]** Treat distinct TMDB entities as distinct valid answers. Require year disambiguation only when a typed answer is ambiguous across two valid entities for the same prompt; otherwise accept and canonicalize to the higher-popularity match.
- **Q3 — Endless rarity data:** **[OPEN — proposed default]** Endless shares the same per-prompt rarity data as Daily (same `answer_counts`), so a prompt's rarity is consistent wherever it appears.
- **Q4 — `prior_weight` decay:** **[OPEN — proposed default]** `prior_weight` starts at 200 and decays linearly with total submissions for the prompt, floored at 20: `prior_weight = max(20, 200 - total_submissions_for_prompt)`. Tunable in config.
- **Q5 — name/branding:** **[OPEN]** "Cold Open" is a working title; no requirement depends on the final name beyond "branding must be original and distinct from existing games."
- **Q6 — character skins at launch:** **[OPEN — proposed default]** Launch with one fixed character; skin selection is a v1 enhancement. Asset manifest must not assume a single skin so skins can be added without gameplay changes.
- **Q7 — pixel location image on share card:** **[OPEN — proposed default]** MVP share card ships the emoji grid + location name + score + streak. Adding a small pixel image of the final location is part of OG image generation (v1).

## 2. Glossary

- **Daily / Daily Cold Open:** the one shared 7-prompt puzzle for a calendar date.
- **Prompt:** a checkable category with many valid answers (e.g. "Name a sitcom from the 1990s").
- **Entity:** a canonical movie, show, person, or character record (TMDB-backed).
- **Alias:** an alternate normalized spelling that resolves to an entity.
- **Rarity tier:** one of six scoring bands (Popcorn → Lost Reel) based on an answer's submission share.
- **Rarity share:** the Bayesian blend of prior share and observed submission share for an answer.
- **Fame meter:** a 0–700 value equal to the run's total score, driving the climb.
- **Location / rank:** the fame-meter band the player finishes in; shown as their daily rank.
- **Run:** one play session of a puzzle or pack by one player.
- **Freeze token:** a streak protection earned per 7-day streak.

## 3. Functional requirements

### 3.1 Daily lifecycle

- **R1 — [DECISION]** WHEN a player opens the site on a new day THE SYSTEM SHALL show today's Daily with its prompt count (7) and the per-prompt time limit (25s), plus a countdown to the next Daily.
- **R2 — [DECISION]** The puzzle ID SHALL be the calendar date in `America/New_York`, rolling over at midnight Eastern for all players regardless of their local timezone.
- **R3** WHEN a player starts the Daily THE SYSTEM SHALL present prompts one at a time, each with a visible countdown starting from 25 seconds.
- **R4** WHEN the per-prompt timer reaches zero THE SYSTEM SHALL submit whatever text is currently typed (empty counts as a non-answer) and advance to the next prompt.
- **R5** WHEN a player has already completed today's Daily THE SYSTEM SHALL show their saved result instead of allowing a replay.
- **R6** WHEN a player completes the Daily THE SYSTEM SHALL finalize the run, update their streak, and present the results screen with a share card.
- **R7** WHEN a player refreshes or closes the tab mid-run THE SYSTEM SHALL resume at the current prompt on return, SHALL NOT restore elapsed time, and SHALL forfeit the in-progress prompt (treated as a timed-out non-answer).
- **R8** THE SYSTEM SHALL allow exactly one Daily attempt per player per date.

### 3.2 Answer submission, matching, scoring

- **R9 — [DECISION]** WHEN a player submits an answer THE SYSTEM SHALL validate and score it on the server; validation and scoring SHALL NOT occur on the client.
- **R10 — [DECISION]** THE SYSTEM SHALL NOT transmit the list of valid answers, the rarity of any answer, or per-prompt answer sets to the client before submission.
- **R11** WHEN an answer matches a valid entity for the prompt THE SYSTEM SHALL return the matched entity's canonical title, rarity tier, and points.
- **R12** WHEN an answer does not match any valid entity THE SYSTEM SHALL return an invalid result with 0 points and SHALL log the raw normalized input to `rejected_answers`.
- **R13** WHEN a player submits the same canonical entity twice within one run THE SYSTEM SHALL score the second submission as invalid with 0 points.
- **R14 — matching pipeline** WHEN matching an answer THE SYSTEM SHALL, in order: (1) normalize (lowercase, strip punctuation, strip leading articles, collapse whitespace); (2) attempt exact match against canonical titles and the alias table; (3) attempt a conservatively tuned fuzzy match (trigram or edit distance); (4) if still unmatched, treat as invalid and log it.
- **R15 — disambiguation [OPEN — proposed default]** WHEN a normalized answer maps to more than one valid entity for the prompt THE SYSTEM SHALL resolve to the higher-popularity entity and SHALL surface year disambiguation only where titles are genuinely ambiguous.
- **R16 — accepted types [OPEN — proposed default]** WHEN scoring an answer THE SYSTEM SHALL only count entities whose type is in the prompt's `accepted_entity_types`.
- **R17 — score locking [DECISION]** WHEN an answer is scored THE SYSTEM SHALL lock the shown tier and points at submission time using the rarity blend current at that moment, so a player's recorded score never changes afterward.
- **R18 — rarity blend [DECISION]** THE SYSTEM SHALL compute an answer's rarity share as `(prior_weight * prior_share + observed_count) / (prior_weight + total_submissions_for_prompt)`, where `prior_share` derives from TMDB popularity and vote count.
- **R19 — [DECISION]** THE SYSTEM SHALL map rarity share to tier/points using configurable thresholds, not hardcoded values:
  | Tier | Name | Points | Submission share |
  |---|---|---|---|
  | 1 | Popcorn | 10 | ≥ 20% |
  | 2 | Matinee | 25 | 10–20% |
  | 3 | Marquee | 40 | 5–10% |
  | 4 | Cult Classic | 60 | 1–5% |
  | 5 | Deep Cut | 80 | 0.1–1% |
  | 6 | Lost Reel | 100 | < 0.1%, or valid but never submitted before |
- **R20** THE SYSTEM SHALL cap the maximum Daily score at 700 (7 prompts × 100) and SHALL score invalid or timed-out answers as 0.
- **R21 — observed data** WHEN a valid answer is scored THE SYSTEM SHALL increment that answer's `answer_counts` and the prompt's total-submissions total, so future rarity reflects real play.
- **R22 — [OPEN — proposed default]** The "global percentage" statistic on the results screen MAY update live after play, while the tier/points recorded for the player remain locked per R17.

### 3.3 Endless mode

- **R23** WHEN Endless mode is active THE SYSTEM SHALL draw prompts from the full prompt pool.
- **R24 — [DECISION]** WHEN Endless mode is active THE SYSTEM SHALL drain a single shared "air bar" timer only while the player is actively typing, and SHALL end the run when the bar reaches zero.
- **R25 — [OPEN — proposed default]** Endless runs SHALL use the same per-prompt rarity data as Daily.

### 3.4 Retention and social (streaks, sharing, archive)

- **R26 — [DECISION]** THE SYSTEM SHALL track a streak as the count of consecutive calendar dates (Eastern) on which the player completed the Daily, and SHALL grant one freeze token per completed 7-day streak.
- **R27** WHEN a player misses a day and holds a freeze token THE SYSTEM SHALL consume one token to preserve the streak rather than reset it.
- **R28 — share card [DECISION]** WHEN a run completes THE SYSTEM SHALL produce a spoiler-free share card containing: puzzle number, total score out of 700, a 7-square emoji grid colored by per-prompt tier, the final location/rank, and current streak. The grid SHALL NOT reveal any answer.
- **R29 — archive** THE SYSTEM SHALL allow past Dailies to be played, and such plays SHALL NOT affect streaks. *(Archive UI itself is Phase 2; the no-streak-effect rule applies whenever archive play exists.)*
- **R30 — identity [DECISION]** THE SYSTEM SHALL let players play anonymously using a local-storage identity with no login required, and SHALL NOT block play behind authentication.
- **R31 — [v1]** WHEN a player signs in THE SYSTEM SHALL upgrade their anonymous profile and preserve streaks across devices.

### 3.5 Pixel-art climb and presentation

- **R32 — [DECISION]** WHEN an answer is scored THE SYSTEM SHALL animate the character's climb a distance proportional to the points earned (0–100 points → proportional scroll within the 0–700 fame meter).
- **R33 — [DECISION]** WHEN the fame meter crosses a location threshold THE SYSTEM SHALL transition the background to the new location and update the character's outfit. Thresholds:
  | Score | Location / Rank | Outfit |
  |---|---|---|
  | 0–99 | Bus Stop | hoodie + duffel |
  | 100–199 | Audition Line | hoodie |
  | 200–299 | Backlot (extra) | jacket |
  | 300–399 | Your Own Trailer | jacket |
  | 400–499 | Premiere Red Carpet | suit |
  | 500–599 | Awards Stage | suit |
  | 600–699 | Hollywood Hills Mansion | tux/gown |
  | 700 | Walk of Fame | tux/gown + star |
- **R34 — [DECISION]** WHEN a run completes THE SYSTEM SHALL present the player's final location as their rank and include it on the share card.
- **R35 — per-tier animation [DECISION]** WHEN an answer is scored THE SYSTEM SHALL play the tier's animation: Popcorn = small hop; Matinee = short climb; Marquee = climb + spotlight sweep; Cult Classic = big climb + shake + confetti; Deep Cut = elevator rise + flashbulbs; Lost Reel = full-screen rocket + film-reel burst; Invalid = stumble + "CUT!" clapperboard, no movement.
- **R36 — reduced motion [DECISION]** WHEN `prefers-reduced-motion` is enabled (OS setting or in-game toggle) THE SYSTEM SHALL disable screen shake and flash effects and substitute simple fades.
- **R37 — resolution [DECISION]** THE SYSTEM SHALL render the game at a fixed internal resolution of 180×320, scaled up by integer factors only, with image smoothing disabled (`image-rendering: pixelated`).
- **R38 — asset manifest [DECISION]** THE SYSTEM SHALL load all art and animation data through an asset manifest, so placeholder art can be replaced with final art without changing gameplay code.
- **R39 — placeholder art [DECISION]** The MVP SHALL ship with placeholder art drawn procedurally in code (flat-color palette shapes, a simple 4-frame character sprite) so gameplay is never blocked on art assets.
- **R40 — palette [DECISION]** THE SYSTEM SHALL draw all art from a single restricted palette (16–24 colors) defined in one file.
- **R41 — layout [DECISION]** THE SYSTEM SHALL present a single-screen mobile-portrait layout during play (thin HUD, scrolling pixel world with a fixed center character, prompt text, autofocused input), with no modals or page changes between prompts.
- **R42 — sound [DECISION]** THE SYSTEM SHALL keep sound optional and off by default; when enabled it SHALL play short per-tier stings and a clapper snap on invalid.

### 3.6 Admin / content pipeline

- **R43** WHEN an admin reviews rejected answers THE SYSTEM SHALL allow promoting a rejected answer to valid and attaching it as an alias of an existing entity.
- **R44 — [OPEN]** THE SYSTEM MAY provide an offline LLM adjudication queue that proposes promotions/aliases for rejected answers; this SHALL never run in the submission hot path.
- **R45 — prompt quality** THE SYSTEM SHALL provide a prompt authoring format (YAML or JSON) and a validator enforcing: ≥40 valid answers (target 100+); a popularity spread; objective checkability (no subjective superlatives); no plot spoilers in wording; no single answer expected to exceed ~40% of submissions.
- **R46 — content foundation** THE SYSTEM SHALL ingest movie/TV/person/character entities, aliases, and popularity from TMDB into Postgres via offline scripts, and SHALL author and validate at least 60 seed prompts for launch.

## 4. Non-functional requirements

### 4.1 Compatibility and accessibility

- **R47 — [DECISION]** THE SYSTEM SHALL work on mobile browsers from 360px width with no install step (PWA).
- **R48 — [DECISION]** THE SYSTEM SHALL meet WCAG AA contrast and support keyboard-only play (autofocused input, Enter to submit, no mouse required). *(Full WCAG validation requires manual assistive-technology testing and expert review; this requirement targets AA contrast and keyboard operability.)*
- **R49 — performance [DECISION]** THE SYSTEM SHALL target stable 60 fps on a mid-range phone and keep total first-load assets under 1.5 MB.

### 4.2 Security, anti-cheat, abuse

- **R50 — [DECISION]** THE SYSTEM SHALL be server-authoritative for timing and scoring, SHALL ship no answer lists in client bundles (reinforces R10), and SHALL use per-run signed tokens to authorize answer submissions.
- **R51 — [DECISION]** THE SYSTEM SHALL rate limit answer submissions per client and per IP.
- **R52** THE SYSTEM SHALL run a profanity filter over any raw logged input before it is shown in any UI (e.g. admin review).

### 4.3 Observability

- **R53** THE SYSTEM SHALL emit structured logs and error tracking, and SHALL record daily metrics: plays, completes, shares, and tier distribution per prompt.

### 4.4 Legal and privacy

- **R54 — [DECISION]** WHEN TMDB data is displayed THE SYSTEM SHALL show the required TMDB attribution.
- **R55** THE SYSTEM SHALL comply with TMDB terms (verify commercial-use terms before any monetization), SHALL NOT use copyrighted posters/clips beyond what TMDB permits, and SHALL use original branding distinct from existing games.
- **R56 — asset licensing** THE SYSTEM SHALL use only CC0, properly licensed, or commissioned art, and SHALL record every asset's license in `ASSETS.md`.
- **R57 — privacy [DECISION]** THE SYSTEM SHALL be anonymous by default, collect minimal data, and provide a clear privacy policy page.

## 5. Traceability to handoff

- Handoff §7 requirements R1–R23 map to: R1/R3 (1), R3 (2), R4 (3), R9 (4), R10 (5), R11 (6), R12 (7), R5 (8), R6/R26 (9), R7 (10), R13 (11), R24 (12), R51 (13), R47 (14), R48 (15), R54 (16), R43 (17), R32 (18), R33 (19), R34 (20), R36 (21), R37 (22), R38 (23).
- Handoff §5 scoring → R17–R22; §6 retention/social → R26–R31; §9 visual/climb → R32–R42; §10 non-functional → R50–R57.

## 6. Acceptance criteria (MVP exit)

1. A player can open the site, play all 7 Daily prompts under a 25s-per-prompt timer, and see a locked total score out of 700 — without any login (R1–R9, R30).
2. No valid-answer or rarity data is present in any client network payload before submission (R10, R50).
3. Scores are reproducible from server state: given the same submissions in the same order, the server yields the same per-answer tier and points (R14–R21).
4. The climb renders at 180×320 integer-scaled with placeholder procedural art and reaches the Walk of Fame on a 700 run (R32–R41).
5. Completing the Daily updates the streak and produces a spoiler-free share card with the emoji grid, location, score, and streak (R26, R28, R34).
6. Reduced-motion users get a shake/flash-free experience (R36).
7. 60 seed prompts pass the authoring validator; TMDB attribution is visible wherever TMDB data appears (R45, R46, R54).

---

**Review gate:** Please review and approve `requirements.md`. On approval I'll generate `design.md` (architecture, data model, API contracts, matching/scoring internals, renderer/asset-manifest design), then pause again before `tasks.md`.
