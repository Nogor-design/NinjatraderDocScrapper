from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from strategy_factory.parity.compare_ledgers import compare_ledgers
from strategy_factory.parity.ledger import read_jsonl_ledger
from strategy_factory.parity.nt_print_to_jsonl import convert_nt_print_to_jsonl
from strategy_factory.parity.run_ta_foundation_signals import run_ta_foundation_signals


def run_signal_parity_check(
    *,
    template_path: str | Path,
    bars_csv_path: str | Path,
    nt_output_path: str | Path,
    output_dir: str | Path,
    strategy_id: str,
    price_tolerance: float = 0.0,
) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    python_signals_path = out_dir / "python_signals.csv"
    python_ledger_path = out_dir / "python_ledger.jsonl"
    ninjascript_ledger_path = out_dir / "ninjascript_ledger.jsonl"
    comparison_path = out_dir / "signal_parity_comparison.json"

    run_ta_foundation_signals(
        template_path=template_path,
        bars_csv_path=bars_csv_path,
        signals_out=python_signals_path,
        ledger_out=python_ledger_path,
    )
    convert_nt_print_to_jsonl(
        nt_output_path,
        ninjascript_ledger_path,
        strategy_id=strategy_id,
    )
    comparison = compare_ledgers(
        read_jsonl_ledger(python_ledger_path),
        read_jsonl_ledger(ninjascript_ledger_path),
        price_tolerance=price_tolerance,
    )
    comparison_path.write_text(json.dumps(asdict(comparison), indent=2) + "\n", encoding="utf-8")

    return {
        "python_signals": python_signals_path,
        "python_ledger": python_ledger_path,
        "ninjascript_ledger": ninjascript_ledger_path,
        "comparison": comparison_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Python-vs-NinjaScript signal parity from generated outputs.")
    parser.add_argument("--template", required=True, help="Generated ta_foundation template JSON.")
    parser.add_argument("--bars", required=True, help="Bars CSV used by the Python signal runner.")
    parser.add_argument("--nt-output", required=True, help="Text file containing NinjaTrader Output-window lines.")
    parser.add_argument("--out-dir", required=True, help="Directory for generated ledgers and comparison JSON.")
    parser.add_argument("--strategy-id", required=True, help="Fallback strategy id for NT print parsing.")
    parser.add_argument("--price-tolerance", type=float, default=0.0, help="Allowed price_basis delta.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_signal_parity_check(
        template_path=args.template,
        bars_csv_path=args.bars,
        nt_output_path=args.nt_output,
        output_dir=args.out_dir,
        strategy_id=args.strategy_id,
        price_tolerance=args.price_tolerance,
    )
    print("Generated signal parity outputs:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
