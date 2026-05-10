from __future__ import annotations

import unittest
from pathlib import Path

from strategy_factory.generators.ninjascript_generator import generate_ninjascript_strategy
from strategy_factory.specs.validator import load_strategy_spec
from webgui_server import review_strategy_payload


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SPEC = ROOT / "strategy_factory" / "specs" / "examples" / "ema_cross_fixed_stop_target.json"


class WebGuiReviewTests(unittest.TestCase):
    def test_review_payload_returns_markdown_and_structured_review(self) -> None:
        code = generate_ninjascript_strategy(load_strategy_spec(EXAMPLE_SPEC))
        result = review_strategy_payload({"code": code, "path": "editor.cs"})

        self.assertIn("markdown", result)
        self.assertIn("# Strategy Review: EmaCrossFixedStopTarget", result["markdown"])
        self.assertEqual(result["review"]["class_name"], "EmaCrossFixedStopTarget")


if __name__ == "__main__":
    unittest.main()
