"""CLI: python -m app.prompts validate <file.yaml>

Parses a prompts file and runs quality checks. Wording rules (subjective words,
spoilers) are checked for every prompt. Answer-set rules (count, spread,
dominance) need the resolved answer set:
  - curated prompts: validated against their listed titles (shares are derived
    from ingested entities if available, else a neutral uniform prior).
  - query prompts:   fully validated once resolved against the DB (Task 4).

Exit code is non-zero if any prompt has errors, so this is CI-friendly.
"""
from __future__ import annotations

import argparse
import sys

from .schema import load_prompts_file
from .validator import format_results, validate_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a prompts YAML file.")
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("file")
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve answer sets against the DB (requires ingested entities).",
    )
    args = parser.parse_args()

    prompts = load_prompts_file(args.file)

    if args.resolve:
        # Full validation using the resolver + DB (Task 4).
        from ..db import SessionLocal
        from .resolver import resolve_answer_set

        db = SessionLocal()
        try:
            results = []
            for p in prompts:
                answers = resolve_answer_set(db, p)
                results.append(validate_prompt(p, answers))
        finally:
            db.close()
    else:
        # Structure + wording only; curated prompts also get a count check using
        # their raw titles with a neutral uniform prior so spread/dominance are
        # not falsely triggered.
        results = []
        for p in prompts:
            if p.kind == "curated" and p.answers:
                share = 1.0 / len(p.answers)
                answers = [(t, share) for t in p.answers]
            else:
                answers = []
            results.append(validate_prompt(p, answers))

    print(format_results(results))
    return 1 if any(r.errors for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
