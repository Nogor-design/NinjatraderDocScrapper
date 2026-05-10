from __future__ import annotations

import unittest
from pathlib import Path

from generate_ninjascript import build_code_review, build_local_context, build_user_prompt
from strategy_factory.generators.ninjascript_generator import generate_ninjascript_strategy
from strategy_factory.specs.validator import load_strategy_spec


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SPEC = ROOT / "strategy_factory" / "specs" / "examples" / "ema_cross_fixed_stop_target.json"


class PromptContextTests(unittest.TestCase):
    def test_code_review_context_is_included_in_prompt(self) -> None:
        code = generate_ninjascript_strategy(load_strategy_spec(EXAMPLE_SPEC))
        review = build_code_review(code, path="generated.cs")
        prompt = build_user_prompt(
            "Fix compiler errors.",
            [{"title": "OnBarUpdate", "url": "local", "score": 1.0, "chunk_index": 0, "text": "Use OnBarUpdate."}],
            code,
            "CS0103 example",
            code_review=review,
        )

        self.assertIn("Static review of existing code", prompt)
        self.assertIn("Strategy Review: EmaCrossFixedStopTarget", prompt)
        self.assertIn("CS0103 example", prompt)

    def test_local_context_can_retrieve_module_cards_for_prompt(self) -> None:
        context = build_local_context("session pnl lockout max trades risk", top_k=3)

        self.assertIn("Session PnL Lockout Risk Module", context)


if __name__ == "__main__":
    unittest.main()
