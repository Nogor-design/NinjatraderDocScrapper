from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from strategy_factory.parity.ledger import read_nt_print_ledger, read_jsonl_ledger, write_jsonl_ledger


class LedgerTests(unittest.TestCase):
    def test_sf_ledger_preserves_diagnostic_metadata(self) -> None:
        line = (
            "SF_LEDGER|strategy_id=Demo|timestamp=2026-04-29T10:00:00.0000000Z|"
            "event=ENTER_LONG|reason=entry_ema_9_21|price_basis=19000.25|bar_index=42|"
            "stop_ticks=20|target_ticks=40|quantity=1|fast_ma=19001.5|slow_ma=19000.75|close=19000.25"
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "nt_output.txt"
            source.write_text(line + "\n", encoding="utf-8")

            events = read_nt_print_ledger(source, strategy_id="Fallback")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].strategy_id, "Demo")
        self.assertEqual(events[0].metadata["fast_ma"], "19001.5")
        self.assertEqual(events[0].metadata["slow_ma"], "19000.75")
        self.assertEqual(events[0].metadata["close"], "19000.25")

    def test_jsonl_round_trip_keeps_metadata(self) -> None:
        line = (
            "SF_LEDGER|strategy_id=Demo|timestamp=2026-04-29T10:00:00.0000000Z|"
            "event=ENTER_SHORT|reason=test|price_basis=19000|extra=value"
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "nt_output.txt"
            out = Path(tmp) / "ledger.jsonl"
            source.write_text(line + "\n", encoding="utf-8")
            events = read_nt_print_ledger(source, strategy_id="Fallback")
            write_jsonl_ledger(out, events)

            restored = read_jsonl_ledger(out)

        self.assertEqual(restored[0].metadata, {"extra": "value"})


if __name__ == "__main__":
    unittest.main()
