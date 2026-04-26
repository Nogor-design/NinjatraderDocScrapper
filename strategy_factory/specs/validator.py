from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strategy_factory.specs.defaults import deep_merge_defaults


class StrategySpecError(ValueError):
    """Raised when a canonical strategy spec is invalid."""


SUPPORTED_ENTRY_TYPES = {
    "ema_cross",
    "sma_cross",
    "ma_cross",
    "large_candle_reversal",
    "opening_range_breakout",
    "rsi_threshold",
    "price_level",
}

SUPPORTED_TIMEFRAMES = {"1m", "3m", "5m", "10m", "15m", "30m", "1h"}
SUPPORTED_DIRECTIONS = {"long", "short", "both"}
SUPPORTED_TIMINGS = {"next_open", "break_extreme", "body_midpoint"}


def load_strategy_spec(path: str | Path, *, apply_defaults: bool = True) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize_strategy_spec(raw, apply_defaults=apply_defaults)


def normalize_strategy_spec(spec: dict[str, Any], *, apply_defaults: bool = True) -> dict[str, Any]:
    normalized = deep_merge_defaults(spec) if apply_defaults else dict(spec)
    validate_strategy_spec(normalized)
    return normalized


def validate_strategy_spec(spec: dict[str, Any]) -> None:
    _require(spec, "schema_version", str)
    if spec["schema_version"] != "0.1":
        raise StrategySpecError("schema_version must be '0.1'")

    strategy = _require(spec, "strategy", dict)
    strategy_id = _require(strategy, "id", str)
    if not strategy_id.replace("_", "").isalnum() or not strategy_id[0].isalpha():
        raise StrategySpecError("strategy.id must start with a letter and contain only letters, numbers, and underscores")
    _require(strategy, "name", str)

    market = _require(spec, "market", dict)
    _require(market, "instrument", str)
    timeframe = _require(market, "timeframe", str)
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise StrategySpecError(f"market.timeframe must be one of {sorted(SUPPORTED_TIMEFRAMES)}")
    _positive_number(market, "tick_size")
    _positive_number(market, "tick_value")

    direction = _require(spec, "direction", str).lower()
    if direction not in SUPPORTED_DIRECTIONS:
        raise StrategySpecError(f"direction must be one of {sorted(SUPPORTED_DIRECTIONS)}")
    spec["direction"] = direction

    data = _require(spec, "data", dict)
    calculation = str(data.get("calculation", "on_bar_close"))
    if calculation not in {"on_bar_close", "on_each_tick"}:
        raise StrategySpecError("data.calculation must be on_bar_close or on_each_tick")
    _positive_int(data, "lookback_bars")

    entries = _require(spec, "entries", list)
    if not entries:
        raise StrategySpecError("entries must contain at least one entry module")
    for index, entry in enumerate(entries):
        _validate_entry(entry, index)

    filters = spec.get("filters", [])
    if not isinstance(filters, list):
        raise StrategySpecError("filters must be a list")
    for index, item in enumerate(filters):
        if not isinstance(item, dict):
            raise StrategySpecError(f"filters[{index}] must be an object")
        _require(item, "type", str)
        _require(item, "params", dict)

    exits = _require(spec, "exits", dict)
    _validate_ticks_block(exits, "stop")
    _validate_ticks_block(exits, "target")
    _positive_int(exits, "max_hold_bars")

    sizing = _require(spec, "sizing", dict)
    sizing_type = _require(sizing, "type", str)
    if sizing_type == "fixed_contracts":
        _positive_int(sizing, "contracts")
        _positive_int(sizing, "max_contracts")
        if int(sizing["contracts"]) > int(sizing["max_contracts"]):
            raise StrategySpecError("sizing.contracts cannot exceed sizing.max_contracts")

    risk = _require(spec, "risk", dict)
    if "max_trades_per_day" in risk:
        _positive_int(risk, "max_trades_per_day")
    for key in ("use_soft_pnl_lock", "use_hard_kill"):
        if key in risk and not isinstance(risk[key], bool):
            raise StrategySpecError(f"risk.{key} must be boolean")
    for key in ("soft_profit_stop", "soft_loss_stop", "hard_kill_profit", "hard_kill_loss"):
        if key in risk:
            _non_negative_number(risk, key)
    if "max_consecutive_losses" in risk:
        _positive_int(risk, "max_consecutive_losses")


def _validate_entry(entry: Any, index: int) -> None:
    if not isinstance(entry, dict):
        raise StrategySpecError(f"entries[{index}] must be an object")
    _require(entry, "id", str)
    entry_type = _require(entry, "type", str)
    if entry_type not in SUPPORTED_ENTRY_TYPES:
        raise StrategySpecError(f"entries[{index}].type is unsupported: {entry_type}")
    timing = str(entry.get("timing", "next_open"))
    if timing not in SUPPORTED_TIMINGS:
        raise StrategySpecError(f"entries[{index}].timing must be one of {sorted(SUPPORTED_TIMINGS)}")
    entry["timing"] = timing
    params = _require(entry, "params", dict)

    if entry_type in {"ema_cross", "sma_cross", "ma_cross"}:
        _positive_int(params, "fast_period")
        _positive_int(params, "slow_period")
        if int(params["fast_period"]) >= int(params["slow_period"]):
            raise StrategySpecError(f"entries[{index}] fast_period must be less than slow_period")
        params.setdefault("fast_type", "ema" if entry_type == "ema_cross" else "sma")
        params.setdefault("slow_type", "ema" if entry_type == "ema_cross" else "sma")


def _validate_ticks_block(parent: dict[str, Any], key: str) -> None:
    block = _require(parent, key, dict)
    _require(block, "type", str)
    _positive_int(block, "ticks")


def _require(parent: dict[str, Any], key: str, expected_type: type) -> Any:
    if key not in parent:
        raise StrategySpecError(f"missing required field: {key}")
    value = parent[key]
    if not isinstance(value, expected_type):
        raise StrategySpecError(f"{key} must be {expected_type.__name__}")
    if expected_type is str and not value.strip():
        raise StrategySpecError(f"{key} cannot be empty")
    return value


def _positive_int(parent: dict[str, Any], key: str) -> None:
    value = parent.get(key)
    if not isinstance(value, int) or value <= 0:
        raise StrategySpecError(f"{key} must be a positive integer")


def _positive_number(parent: dict[str, Any], key: str) -> None:
    value = parent.get(key)
    if not isinstance(value, (int, float)) or value <= 0:
        raise StrategySpecError(f"{key} must be a positive number")


def _non_negative_number(parent: dict[str, Any], key: str) -> None:
    value = parent.get(key)
    if not isinstance(value, (int, float)) or value < 0:
        raise StrategySpecError(f"{key} must be a non-negative number")
