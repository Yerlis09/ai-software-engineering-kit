"""The context benchmark runs and routed context is never larger than the direct baseline."""

from __future__ import annotations

import sys

from netsf_testkit import PLUGIN_ROOT

sys.path.insert(0, str(PLUGIN_ROOT / "benchmarks"))

import context_benchmark


def test_benchmark_routed_context_is_smaller_than_direct() -> None:
    rows = context_benchmark.run(repeat=1, scenarios=["fastapi", "frontend"])
    assert rows[0]["scenario"] == "kit-project" and rows[0]["state"] == "OPTIMIZED"
    for row in rows:
        assert row["direct_tokens"] and row["routed_tokens"] and row["lean_tokens"]
        assert row["lean_tokens"] <= row["routed_tokens"] < row["direct_tokens"], row
    table = context_benchmark.render(rows)
    assert table.startswith("| Scenario |") and "Total over" in table


def test_autonomy_benchmark_measures_interaction() -> None:
    import autonomy_benchmark

    rows = {r["scenario"]: r for r in autonomy_benchmark.run()}
    normal = rows["existing-flask"]
    assert normal["decision"] == "PROCEED" and normal["user_prompts_required"] == 1
    assert normal["approval_requests"] == 0 and normal["questions"] == 0
    assert normal["relevant_files"] >= 2 and normal["test_commands"] == 1
    assert rows["existing-flask-migration"]["approval_requests"] == 1
    assert rows["existing-flask-dry-run"]["decision"] == "READ_ONLY"
    assert rows["new-api-with-persistence"]["questions"] == 1
    assert rows["new-file-processing"]["decision"] == "PROCEED"
    assert all(r["user_prompts_required"] <= 2 for r in rows.values())
    assert "| Scenario | Decision |" in autonomy_benchmark.render(list(rows.values()))
