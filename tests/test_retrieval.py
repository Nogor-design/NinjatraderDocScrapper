from __future__ import annotations

import unittest
from pathlib import Path

from strategy_factory.retrieval import retrieve_context_for_spec, retrieve_local_context
from strategy_factory.specs.validator import load_strategy_spec


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SPEC = ROOT / "strategy_factory" / "specs" / "examples" / "ema_cross_fixed_stop_target.json"


class RetrievalTests(unittest.TestCase):
    def test_local_retrieval_prefers_relevant_module_card(self) -> None:
        results = retrieve_local_context("hard kill pnl lockout realized unrealized risk", root=ROOT, top_k=3)

        self.assertTrue(results)
        self.assertEqual(results[0].kind, "module_card")
        self.assertIn("hard_kill_pnl_lockout.md", results[0].path)

    def test_local_retrieval_finds_trend_filter_module(self) -> None:
        results = retrieve_local_context("moving average trend filter price above ema", root=ROOT, top_k=3)

        self.assertTrue(any("moving_average_trend.md" in item.path for item in results))

    def test_spec_retrieval_returns_strategy_context(self) -> None:
        spec = load_strategy_spec(EXAMPLE_SPEC)
        results = retrieve_context_for_spec(spec, root=ROOT, top_k=5)
        kinds = {item.kind for item in results}

        self.assertIn("module_card", kinds)
        self.assertTrue(any(item.kind == "skeleton" for item in results))


if __name__ == "__main__":
    unittest.main()
