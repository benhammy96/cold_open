"""Per-run signed tokens (R50). A token binds a run id with an HMAC so the
client cannot forge or reuse a run it did not start. Not a substitute for
server-side state — the run row is still the source of truth."""
from __future__ import annotations

import hashlib
import hmac
import os

_SECRET = os.environ.get("COLDOPEN_TOKEN_SECRET", "dev-insecure-secret-change-me").encode()


def sign_run(run_id: str) -> str:
    sig = hmac.new(_SECRET, run_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{run_id}.{sig}"


def verify_run(token: str) -> str | None:
    """Return the run_id if the token is well-formed and the signature matches."""
    if not token or "." not in token:
        return None
    run_id, _, sig = token.rpartition(".")
    expected = hmac.new(_SECRET, run_id.encode(), hashlib.sha256).hexdigest()[:32]
    if hmac.compare_digest(sig, expected):
        return run_id
    return None
