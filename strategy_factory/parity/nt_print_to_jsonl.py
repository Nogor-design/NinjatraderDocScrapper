from __future__ import annotations

import argparse
from pathlib import Path

from strategy_factory.parity.ledger import read_nt_print_ledger, write_jsonl_ledger


def convert_nt_print_to_jsonl(
    input_path: str | Path,
    output_path: str | Path,
    *,
    strategy_id: str,
) -> Path:
    events = read_nt_print_ledger(input_path, strategy_id=strategy_id)
    return write_jsonl_ledger(output_path, events)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert generated NinjaScript Print output to parity JSONL.")
    parser.add_argument("--input", required=True, help="Text file containing NinjaTrader Output window lines.")
    parser.add_argument("--out", required=True, help="Output JSONL ledger path.")
    parser.add_argument("--strategy-id", required=True, help="Fallback strategy id for legacy print lines.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = convert_nt_print_to_jsonl(args.input, args.out, strategy_id=args.strategy_id)
    print(f"Saved NinjaScript JSONL ledger to {out_path}")


if __name__ == "__main__":
    main()
