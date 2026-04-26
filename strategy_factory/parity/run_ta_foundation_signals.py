from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strategy_factory.parity.ledger import StrategyLedgerEvent, write_jsonl_ledger


REQUIRED_BAR_COLUMNS = {"dt", "open", "high", "low", "close"}


class TaFoundationSignalRunError(RuntimeError):
    """Raised when ta_foundation signal generation cannot run."""


def run_ta_foundation_signals(
    *,
    template_path: str | Path,
    bars_csv_path: str | Path,
    signals_out: str | Path,
    ledger_out: str | Path,
) -> dict[str, Path | int]:
    try:
        import pandas as pd
        from ta_foundation.analysis.strategy_composer.template import StrategyTemplate
    except ImportError as exc:
        raise TaFoundationSignalRunError(
            "Could not import pandas/ta_foundation. Run this with ta_foundation on PYTHONPATH "
            "or from the ta_foundation virtual environment."
        ) from exc

    template_source = Path(template_path)
    template_payload = json.loads(template_source.read_text(encoding="utf-8"))
    template = StrategyTemplate.from_dict(template_payload)
    bars = _normalize_bars(pd.read_csv(bars_csv_path))
    signals = template.generate_signals(bars)

    signals_path = Path(signals_out)
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(signals_path, index=False)

    events = _signals_to_events(signals, template_payload)
    ledger_path = write_jsonl_ledger(ledger_out, events)
    return {
        "signals": signals_path,
        "ledger": ledger_path,
        "event_count": len(events),
    }


def _normalize_bars(bars: Any) -> Any:
    bars = bars.copy()
    bars.columns = [str(column).strip().lower() for column in bars.columns]
    rename_map = {
        "datetime": "dt",
        "date_time": "dt",
        "timestamp": "dt",
        "time": "dt",
        "last": "close",
    }
    bars = bars.rename(columns={key: value for key, value in rename_map.items() if key in bars.columns})
    missing = REQUIRED_BAR_COLUMNS - set(bars.columns)
    if missing:
        raise TaFoundationSignalRunError(f"Bars CSV is missing required columns: {sorted(missing)}")
    if "bar_index" not in bars.columns:
        bars.insert(0, "bar_index", range(len(bars)))
    return bars


def _signals_to_events(signals: Any, template: dict[str, Any]) -> list[StrategyLedgerEvent]:
    if signals.empty:
        return []

    metadata = template.get("factory_metadata") or {}
    sizing = metadata.get("sizing") or {}
    ledger_rules = template.get("ledger_rules") or {}
    strategy_id = str(metadata.get("strategy_id") or template.get("template_name") or "UnknownStrategy")
    reason = str(ledger_rules.get("entry_reason") or (template.get("entry_signal") or {}).get("type") or "entry")
    price_column = str(ledger_rules.get("price_basis_column") or "close")
    stop_ticks = _int_or_none(template.get("hard_stop_ticks_cap"))
    target_ticks = _int_or_none(template.get("initial_target_ticks"))
    quantity = _int_or_none(sizing.get("contracts"))

    events: list[StrategyLedgerEvent] = []
    for index, row in signals.reset_index(drop=True).iterrows():
        event = _direction_to_event(row.get("direction"))
        if event is None:
            continue
        timestamp = str(_first_value(row, ["signal_dt", "dt", "timestamp"]))
        if not timestamp:
            continue
        events.append(
            StrategyLedgerEvent(
                strategy_id=strategy_id,
                timestamp=timestamp,
                event=event,
                reason=reason,
                price_basis=_float_or_zero(_first_value(row, [price_column, "entry_price", "close", "open"])),
                bar_index=_int_or_none(row.get("bar_index")) if "bar_index" in signals.columns else index,
                stop_ticks=stop_ticks,
                target_ticks=target_ticks,
                quantity=quantity,
                source="python",
            )
        )
    return events


def _first_value(row: Any, keys: list[str]) -> Any:
    for key in keys:
        if key and key in row and row.get(key) is not None:
            return row.get(key)
    return ""


def _direction_to_event(value: Any) -> str | None:
    normalized = str(value).strip().lower()
    if normalized in {"1", "1.0", "long", "buy", "enter_long"}:
        return "ENTER_LONG"
    if normalized in {"-1", "-1.0", "short", "sell", "enter_short"}:
        return "ENTER_SHORT"
    return None


def _float_or_zero(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a ta_foundation template on bars CSV and emit parity outputs.")
    parser.add_argument("--template", required=True, help="Generated ta_foundation template JSON.")
    parser.add_argument("--bars", required=True, help="Bars CSV with dt, open, high, low, close columns.")
    parser.add_argument("--signals-out", required=True, help="Output CSV path for raw Python signals.")
    parser.add_argument("--ledger-out", required=True, help="Output JSONL path for parity ledger events.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_ta_foundation_signals(
        template_path=args.template,
        bars_csv_path=args.bars,
        signals_out=args.signals_out,
        ledger_out=args.ledger_out,
    )
    print("Generated ta_foundation parity outputs:")
    for name, value in result.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
