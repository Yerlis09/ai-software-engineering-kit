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
