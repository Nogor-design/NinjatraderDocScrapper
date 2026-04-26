from __future__ import annotations

import argparse
from pathlib import Path

from strategy_factory.parity.ledger import read_python_signal_csv_ledger, write_jsonl_ledger


def convert_python_signals_to_jsonl(
    input_path: str | Path,
    output_path: str | Path,
    *,
    strategy_id: str,
    reason: str,
    stop_ticks: int | None = None,
    target_ticks: int | None = None,
    quantity: int | None = None,
    timestamp_column: str = "",
    price_column: str = "close",
) -> Path:
    events = read_python_signal_csv_ledger(
        input_path,
        strategy_id=strategy_id,
        reason=reason,
        stop_ticks=stop_ticks,
        target_ticks=target_ticks,
        quantity=quantity,
        timestamp_column=timestamp_column,
        price_column=price_column,
    )
    return write_jsonl_ledger(output_path, events)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert ta_foundation signal CSV output to parity JSONL.")
    parser.add_argument("--input", required=True, help="CSV containing ta_foundation signal rows.")
    parser.add_argument("--out", required=True, help="Output JSONL ledger path.")
    parser.add_argument("--strategy-id", required=True, help="Strategy id used in the ledger.")
    parser.add_argument("--reason", required=True, help="Entry module id or reason, e.g. entry_ema_9_21.")
    parser.add_argument("--stop-ticks", type=int, default=None, help="Optional stop ticks to include in each event.")
    parser.add_argument("--target-ticks", type=int, default=None, help="Optional target ticks to include in each event.")
    parser.add_argument("--quantity", type=int, default=None, help="Optional quantity to include in each event.")
    parser.add_argument("--timestamp-column", default="", help="Optional explicit timestamp column.")
    parser.add_argument("--price-column", default="close", help="Price column to use for price_basis.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = convert_python_signals_to_jsonl(
        args.input,
        args.out,
        strategy_id=args.strategy_id,
        reason=args.reason,
        stop_ticks=args.stop_ticks,
        target_ticks=args.target_ticks,
        quantity=args.quantity,
        timestamp_column=args.timestamp_column,
        price_column=args.price_column,
    )
    print(f"Saved Python JSONL ledger to {out_path}")


if __name__ == "__main__":
    main()
