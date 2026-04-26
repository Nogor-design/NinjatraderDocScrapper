from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from strategy_factory.parity.ledger import StrategyLedgerEvent, read_jsonl_ledger


@dataclass(frozen=True)
class LedgerComparison:
    matched: int
    missing_from_right: int
    extra_in_right: int
    left_event_counts: dict[str, int]
    right_event_counts: dict[str, int]
    missing_keys: list[str]
    extra_keys: list[str]
    price_mismatches: list[dict[str, float | str]]


def compare_ledgers(
    left: list[StrategyLedgerEvent],
    right: list[StrategyLedgerEvent],
    *,
    price_tolerance: float = 0.0,
) -> LedgerComparison:
    left_keys = Counter(_event_key(event) for event in left)
    right_keys = Counter(_event_key(event) for event in right)
    intersection = left_keys & right_keys
    missing = left_keys - right_keys
    extra = right_keys - left_keys
    price_mismatches = _price_mismatches(left, right, price_tolerance=price_tolerance)
    return LedgerComparison(
        matched=sum(intersection.values()),
        missing_from_right=sum(missing.values()),
        extra_in_right=sum(extra.values()),
        left_event_counts=dict(Counter(event.event for event in left)),
        right_event_counts=dict(Counter(event.event for event in right)),
        missing_keys=sorted(missing.elements()),
        extra_keys=sorted(extra.elements()),
        price_mismatches=price_mismatches,
    )


def _event_key(event: StrategyLedgerEvent) -> str:
    return "|".join(
        [
            event.strategy_id,
            event.timestamp,
            event.event,
            event.reason,
            "" if event.bar_index is None else str(event.bar_index),
            "" if event.stop_ticks is None else str(event.stop_ticks),
            "" if event.target_ticks is None else str(event.target_ticks),
            "" if event.quantity is None else str(event.quantity),
        ]
    )


def _price_mismatches(
    left: list[StrategyLedgerEvent],
    right: list[StrategyLedgerEvent],
    *,
    price_tolerance: float,
) -> list[dict[str, float | str]]:
    left_by_key = _events_by_key(left)
    right_by_key = _events_by_key(right)
    mismatches: list[dict[str, float | str]] = []
    for key in sorted(set(left_by_key) & set(right_by_key)):
        for left_event, right_event in zip(left_by_key[key], right_by_key[key]):
            delta = abs(left_event.price_basis - right_event.price_basis)
            if delta > price_tolerance:
                mismatches.append(
                    {
                        "key": key,
                        "left_price_basis": left_event.price_basis,
                        "right_price_basis": right_event.price_basis,
                        "delta": delta,
                    }
                )
    return mismatches


def _events_by_key(events: list[StrategyLedgerEvent]) -> dict[str, list[StrategyLedgerEvent]]:
    grouped: dict[str, list[StrategyLedgerEvent]] = defaultdict(list)
    for event in events:
        grouped[_event_key(event)].append(event)
    return grouped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two strategy signal ledgers.")
    parser.add_argument("--left", required=True, help="Left JSONL ledger path, usually Python.")
    parser.add_argument("--right", required=True, help="Right JSONL ledger path, usually NinjaScript.")
    parser.add_argument("--out", default="", help="Optional JSON comparison output path.")
    parser.add_argument("--price-tolerance", type=float, default=0.0, help="Allowed price_basis delta.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison = compare_ledgers(
        read_jsonl_ledger(args.left),
        read_jsonl_ledger(args.right),
        price_tolerance=args.price_tolerance,
    )
    payload = asdict(comparison)
    text = json.dumps(payload, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"Saved comparison to {out_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
