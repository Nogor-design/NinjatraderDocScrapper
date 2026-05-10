from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from strategy_factory.factory import build_strategy_outputs
from strategy_factory.generators.ninjascript_generator import generate_ninjascript_strategy
from strategy_factory.generators.ninjascript_template_generator import generate_ninjascript_template_xml
from strategy_factory.generators.python_template_generator import generate_ta_foundation_template
from strategy_factory.specs.validator import load_strategy_spec


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SPEC = ROOT / "strategy_factory" / "specs" / "examples" / "ema_cross_fixed_stop_target.json"
TREND_FILTER_SPEC = ROOT / "strategy_factory" / "specs" / "examples" / "ema_cross_trend_filter.json"


class StrategyFactoryTests(unittest.TestCase):
    def test_factory_builds_all_outputs_from_example_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outputs = build_strategy_outputs(EXAMPLE_SPEC, tmp)

            self.assertEqual(
                set(outputs),
                {"manifest", "normalized_spec", "ta_foundation_template", "ninjascript", "ninjascript_template"},
            )
            for path in outputs.values():
                self.assertTrue(path.is_file(), path)

            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
            self.assertEqual(manifest["strategy_id"], "EmaCrossFixedStopTarget")

    def test_ninjascript_contains_risk_guards_and_diagnostic_ledger_fields(self) -> None:
        spec = load_strategy_spec(EXAMPLE_SPEC)
        code = generate_ninjascript_strategy(spec)

        self.assertIn("EvaluateSoftRiskLock()", code)
        self.assertIn("EvaluateHardKill", code)
        self.assertIn("SetStopLoss(CalculationMode.Ticks, StopTicks)", code)
        self.assertIn("fast_ma={9}|slow_ma={10}|close={11}", code)
        self.assertNotIn("{{FILTER_", code)

    def test_ta_foundation_template_maps_core_fields(self) -> None:
        spec = load_strategy_spec(EXAMPLE_SPEC)
        template = generate_ta_foundation_template(spec)

        self.assertEqual(template["entry_signal"]["type"], "ma_cross")
        self.assertEqual(template["entry_signal"]["fast_period"], 9)
        self.assertEqual(template["hard_stop_ticks_cap"], 20)
        self.assertEqual(template["initial_target_ticks"], 40)

    def test_ninjascript_template_targets_generated_class(self) -> None:
        spec = load_strategy_spec(EXAMPLE_SPEC)
        xml = generate_ninjascript_template_xml(spec)

        self.assertIn("NinjaTrader.NinjaScript.Strategies.EmaCrossFixedStopTarget", xml)
        self.assertIn("<FastPeriod>9</FastPeriod>", xml)
        self.assertIn("<TargetTicks>40</TargetTicks>", xml)

    def test_ninjascript_supports_ma_trend_filter(self) -> None:
        spec = load_strategy_spec(TREND_FILTER_SPEC)
        code = generate_ninjascript_strategy(spec)

        self.assertIn("private EMA trendMa1;", code)
        self.assertIn("TrendPeriod1 = 50;", code)
        self.assertIn("trendMa1 = EMA(TrendPeriod1);", code)
        self.assertIn("if (Close[0] <= trendMa1[0])", code)
        self.assertIn("public int TrendPeriod1 { get; set; }", code)
        self.assertIn("BarsRequiredToTrade = 50;", code)

    def test_ninjascript_template_includes_trend_filter_parameter(self) -> None:
        spec = load_strategy_spec(TREND_FILTER_SPEC)
        xml = generate_ninjascript_template_xml(spec)

        self.assertIn("<TrendPeriod1>50</TrendPeriod1>", xml)
        self.assertIn("<Name>TrendPeriod1</Name>", xml)


if __name__ == "__main__":
    unittest.main()
