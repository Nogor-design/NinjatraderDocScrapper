from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StrategyLedgerEvent:
    strategy_id: str
    timestamp: str
    event: str
    reason: str
    price_basis: float
    bar_index: int | None = None
    stop_ticks: int | None = None
    target_ticks: int | None = None
    quantity: int | None = None
    source: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def read_jsonl_ledger(path: str | Path) -> list[StrategyLedgerEvent]:
    events: list[StrategyLedgerEvent] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        events.append(StrategyLedgerEvent(**payload))
    return events


def write_jsonl_ledger(path: str | Path, events: Iterable[StrategyLedgerEvent]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(asdict(event), separators=(",", ":")) + "\n")
    return out_path


def read_nt_print_ledger(path: str | Path, *, strategy_id: str, source: str = "ninjascript") -> list[StrategyLedgerEvent]:
    """Parse Print lines emitted by generated NinjaScript strategies."""
    events: list[StrategyLedgerEvent] = []
    for raw in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("SF_LEDGER|"):
            event = _parse_sf_ledger_line(line, fallback_strategy_id=strategy_id, source=source)
            if event is not None:
                events.append(event)
            continue
        legacy_event = _parse_legacy_nt_print_line(line, strategy_id=strategy_id, source=source)
        if legacy_event is not None:
            events.append(legacy_event)
    return events


def read_python_signal_csv_ledger(
    path: str | Path,
    *,
    strategy_id: str,
    reason: str,
    stop_ticks: int | None = None,
    target_ticks: int | None = None,
    quantity: int | None = None,
    source: str = "python",
    timestamp_column: str = "",
    price_column: str = "close",
) -> list[StrategyLedgerEvent]:
    """Convert a ta_foundation signal CSV into parity ledger events."""
    events: list[StrategyLedgerEvent] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            direction = _direction_to_event(row.get("direction", ""))
            if direction is None:
                continue
            timestamp = _first_present(row, [timestamp_column, "signal_dt", "dt", "timestamp"])
            if not timestamp:
                continue
            price_basis = _float_or_zero(_first_present(row, [price_column, "entry_price", "close", "open"]))
            events.append(
                StrategyLedgerEvent(
                    strategy_id=strategy_id,
                    timestamp=timestamp,
                    event=direction,
                    reason=reason,
                    price_basis=price_basis,
                    bar_index=_int_or_none(row.get("bar_index") or row.get("index")) or index,
                    stop_ticks=stop_ticks,
                    target_ticks=target_ticks,
                    quantity=quantity,
                    source=source,
                )
            )
    return events


def write_csv_ledger(path: str | Path, events: Iterable[StrategyLedgerEvent]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(event) for event in events]
    for row in rows:
        row["metadata"] = json.dumps(row["metadata"], separators=(",", ":"))
    fieldnames = list(StrategyLedgerEvent.__dataclass_fields__.keys())
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def _parse_detail(parts: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def _parse_sf_ledger_line(line: str, *, fallback_strategy_id: str, source: str) -> StrategyLedgerEvent | None:
    detail = _parse_detail(line.split("|")[1:])
    if "event" not in detail or "timestamp" not in detail:
        return None
    known_fields = {
        "strategy_id",
        "timestamp",
        "event",
        "reason",
        "price_basis",
        "bar_index",
        "stop_ticks",
        "target_ticks",
        "quantity",
    }
    return StrategyLedgerEvent(
        strategy_id=detail.get("strategy_id", fallback_strategy_id),
        timestamp=detail["timestamp"],
        event=detail["event"],
        reason=detail.get("reason", ""),
        price_basis=_float_or_zero(detail.get("price_basis")),
        bar_index=_int_or_none(detail.get("bar_index")),
        stop_ticks=_int_or_none(detail.get("stop_ticks")),
        target_ticks=_int_or_none(detail.get("target_ticks")),
        quantity=_int_or_none(detail.get("quantity")),
        source=source,
        metadata={key: value for key, value in detail.items() if key not in known_fields},
    )


def _parse_legacy_nt_print_line(line: str, *, strategy_id: str, source: str) -> StrategyLedgerEvent | None:
    if "|ENTER_" not in line and "|RISK_LOCK|" not in line:
        return None
    parts = line.split("|")
    if len(parts) < 3:
        return None
    detail = _parse_detail(parts[3:])
    return StrategyLedgerEvent(
        strategy_id=strategy_id,
        timestamp=parts[0],
        event=parts[1],
        reason=parts[2],
        price_basis=_float_or_zero(detail.get("price")),
        source=source,
    )


def _float_or_zero(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _first_present(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if key and row.get(key):
            return str(row[key])
    return ""


def _direction_to_event(value: str) -> str | None:
    normalized = str(value).strip().lower()
    if normalized in {"1", "1.0", "long", "buy", "enter_long"}:
        return "ENTER_LONG"
    if normalized in {"-1", "-1.0", "short", "sell", "enter_short"}:
        return "ENTER_SHORT"
    return None
