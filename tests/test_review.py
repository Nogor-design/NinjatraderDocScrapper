from __future__ import annotations

import unittest
from pathlib import Path

from strategy_factory.generators.ninjascript_generator import generate_ninjascript_strategy
from strategy_factory.review import review_strategy_code, review_to_markdown
from strategy_factory.specs.validator import load_strategy_spec


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SPEC = ROOT / "strategy_factory" / "specs" / "examples" / "ema_cross_fixed_stop_target.json"


class ReviewTests(unittest.TestCase):
    def test_review_generated_strategy_summarizes_core_shape(self) -> None:
        code = generate_ninjascript_strategy(load_strategy_spec(EXAMPLE_SPEC))
        review = review_strategy_code(code, path="generated.cs")

        self.assertEqual(review.class_name, "EmaCrossFixedStopTarget")
        self.assertEqual(review.base_class, "Strategy")
        self.assertEqual(review.order_style, "managed")
        self.assertEqual(review.exit_style, "managed set-method exits")
        self.assertIn("OnBarUpdate", review.lifecycle_methods)
        self.assertIn("SetStopLoss", review.order_methods)
        self.assertTrue(any(parameter.name == "FastPeriod" for parameter in review.parameters))
        self.assertIn("realized PnL lockout", review.risk_guards)

    def test_review_warns_when_set_stop_and_explicit_stop_are_mixed(self) -> None:
        code = """
namespace NinjaTrader.NinjaScript.Strategies
{
    public class MixedExitDemo : Strategy
    {
        protected override void OnBarUpdate()
        {
            SetStopLoss(CalculationMode.Ticks, 20);
            ExitLongStopMarket(0, true, 1, Close[0] - 10 * TickSize, "Stop", "LongEntry");
        }
    }
}
"""
        review = review_strategy_code(code)

        self.assertEqual(review.exit_style, "mixed managed set-method and explicit exits")
        self.assertTrue(any("SetStopLoss is mixed" in warning for warning in review.warnings))

    def test_review_markdown_is_cross_chat_friendly(self) -> None:
        code = generate_ninjascript_strategy(load_strategy_spec(EXAMPLE_SPEC))
        markdown = review_to_markdown(review_strategy_code(code, path="generated.cs"))

        self.assertIn("# Strategy Review: EmaCrossFixedStopTarget", markdown)
        self.assertIn("## Risk Guards", markdown)
        self.assertIn("FastPeriod", markdown)


if __name__ == "__main__":
    unittest.main()
