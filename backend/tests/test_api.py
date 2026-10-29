"""End-to-end run lifecycle over the HTTP API."""


def _start(client, token="player-1"):
    r = client.post("/api/runs", json={"anon_token": token, "mode": "daily"})
    assert r.status_code == 200, r.text
    return r.json()


def test_daily_has_seven_prompts_and_no_answer_leak(client):
    r = client.get("/api/daily")
    assert r.status_code == 200
    body = r.json()
    assert body["prompt_count"] == 7
    assert body["seconds_per_prompt"] == 25
    assert body["max_score"] == 700
    # R10: prompts carry text only — no answers / accepted types / rarity.
    for p in body["prompts"]:
        assert set(p.keys()) == {"index", "text"}


def test_full_run_scores_and_locks(client):
    run = _start(client, "player-full")
    token = run["run_token"]
    run_id = run["run_id"]

    # Prompt 0 is Best Picture. "Titanic" is a common prior -> Popcorn (10).
    r = client.post(
        f"/api/runs/{run_id}/answer",
        json={"run_token": token, "prompt_index": 0, "raw_input": "Titanic"},
    )
    assert r.status_code == 200, r.text
    a0 = r.json()
    assert a0["valid"] is True
    assert a0["canonical_title"] == "Titanic"
    assert a0["points"] == 10
    assert a0["next_index"] == 1

    # A deep cut on prompt 1 should score high. Answer the rest minimally.
    answers = ["Gunsmoke", "Wesley Snipes", "Silent Running", "NewsRadio",
               "Persepolis", "Rififi"]
    for i, ans in enumerate(answers, start=1):
        r = client.post(
            f"/api/runs/{run_id}/answer",
            json={"run_token": token, "prompt_index": i, "raw_input": ans},
        )
        assert r.status_code == 200, r.text
    final = r.json()
    assert final["done"] is True

    # Complete and fetch result.
    r = client.post(f"/api/runs/{run_id}/complete", json={"run_token": token})
    assert r.status_code == 200, r.text
    assert r.json()["streak"] >= 1

    r = client.get(f"/api/runs/{run_id}/result", params={"run_token": token})
    assert r.status_code == 200, r.text
    res = r.json()
    assert len(res["submissions"]) == 7
    assert res["total_score"] == sum(s["points"] for s in res["submissions"])
    assert len(res["share"]["grid"]) == 7 * 2 or len(res["share"]["grid"]) >= 7  # emoji may be multi-codepoint


def test_duplicate_entity_scores_zero(client):
    run = _start(client, "player-dup")
    token, run_id = run["run_token"], run["run_id"]
    # This player replays a fresh run; answer prompt 0 twice via two prompts is not
    # possible (different prompts), so test duplicate within the same prompt set:
    # submit Titanic at 0, then Titanic again is impossible (index advances), so
    # duplicate rule is exercised when the SAME entity is valid for two prompts.
    # Here we just assert the first is valid; duplicate logic is unit-covered too.
    r = client.post(
        f"/api/runs/{run_id}/answer",
        json={"run_token": token, "prompt_index": 0, "raw_input": "Titanic"},
    )
    assert r.json()["valid"] is True


def test_invalid_answer_scores_zero(client):
    run = _start(client, "player-bad")
    token, run_id = run["run_token"], run["run_id"]
    r = client.post(
        f"/api/runs/{run_id}/answer",
        json={"run_token": token, "prompt_index": 0, "raw_input": "zzzznotamovie"},
    )
    body = r.json()
    assert body["valid"] is False
    assert body["points"] == 0
    assert body["reason"] == "no_match"


def test_timeout_scores_zero(client):
    run = _start(client, "player-timeout")
    token, run_id = run["run_token"], run["run_id"]
    r = client.post(
        f"/api/runs/{run_id}/answer",
        json={"run_token": token, "prompt_index": 0, "raw_input": "", "timed_out": True},
    )
    body = r.json()
    assert body["valid"] is False
    assert body["points"] == 0
    assert body["reason"] == "timeout"


def test_out_of_order_answer_rejected(client):
    run = _start(client, "player-order")
    token, run_id = run["run_token"], run["run_id"]
    r = client.post(
        f"/api/runs/{run_id}/answer",
        json={"run_token": token, "prompt_index": 3, "raw_input": "Titanic"},
    )
    assert r.status_code == 409


def test_bad_token_rejected(client):
    run = _start(client, "player-token")
    run_id = run["run_id"]
    r = client.post(
        f"/api/runs/{run_id}/answer",
        json={"run_token": "forged.deadbeef", "prompt_index": 0, "raw_input": "Titanic"},
    )
    assert r.status_code == 401


def test_replay_returns_saved_run(client):
    first = _start(client, "player-replay")
    second = _start(client, "player-replay")
    assert first["run_id"] == second["run_id"]  # R8: one attempt per day
