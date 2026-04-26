from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strategy_factory.specs.validator import load_strategy_spec, normalize_strategy_spec


class PythonTemplateGenerationError(ValueError):
    """Raised when a canonical spec cannot be mapped to ta_foundation."""


def generate_ta_foundation_template(spec: dict[str, Any]) -> dict[str, Any]:
    """Map a canonical Strategy Factory spec into ta_foundation StrategyTemplate JSON."""
    normalized = normalize_strategy_spec(spec)
    entry = _single_entry(normalized)
    session_rules = _session_rules(normalized.get("filters", []))

    stop = normalized["exits"]["stop"]
    target = normalized["exits"]["target"]
    partial = normalized["exits"].get("partial") or {"enabled": False}
    runner = normalized["exits"].get("runner") or {"enabled": False}
    risk = normalized["risk"]

    return {
        "template_name": normalized["strategy"]["id"],
        "hypothesis": normalized["strategy"].get("hypothesis", ""),
        "version": normalized["strategy"].get("version", "0.1"),
        "instrument": normalized["market"]["instrument"],
        "contract": normalized["market"].get("contract", ""),
        "timeframe": normalized["market"]["timeframe"],
        "direction": normalized["direction"],
        "entry_signal": _map_entry(entry),
        "ledger_rules": {
            "entry_reason": entry["id"],
            "price_basis_column": "close",
        },
        "entry_filters": _map_entry_filters(normalized.get("filters", [])),
        "stop_mode": _map_stop_mode(stop),
        "hard_stop_ticks_cap": int(stop["ticks"]),
        "initial_target_ticks": int(target["ticks"]),
        "partial_rules": {
            "enabled": bool(partial.get("enabled", False)),
            "partial_size_pct": int(partial.get("partial_size_pct", 50)),
            "partial_target_ticks": int(partial.get("partial_target_ticks", target["ticks"])),
            "move_stop_to_break_even_after_partial": bool(
                partial.get("move_stop_to_break_even_after_partial", True)
            ),
        },
        "runner_rules": {
            "enabled": bool(runner.get("enabled", False)),
            "trail_mode": str(runner.get("trail_mode", "none")),
            "atr_multiple": float(runner.get("atr_multiple", 1.8)),
            "runner_size_pct": int(runner.get("runner_size_pct", 50)),
        },
        "session_rules": session_rules,
        "risk_rules": {
            "max_trades_per_day": int(risk.get("max_trades_per_day", 3)),
            "use_soft_pnl_lock": bool(risk.get("use_soft_pnl_lock", False)),
            "soft_profit_stop": float(risk.get("soft_profit_stop", 0.0)),
            "soft_loss_stop": float(risk.get("soft_loss_stop", 0.0)),
            "use_hard_kill": bool(risk.get("use_hard_kill", False)),
            "hard_kill_profit": float(risk.get("hard_kill_profit", 0.0)),
            "hard_kill_loss": float(risk.get("hard_kill_loss", 0.0)),
        },
        "max_hold_bars": int(normalized["exits"].get("max_hold_bars", 20)),
        "flatten_on_session_end": bool(normalized["exits"].get("flatten_on_session_end", True)),
        "factory_metadata": {
            "schema_version": normalized["schema_version"],
            "strategy_id": normalized["strategy"]["id"],
            "source_prompt": normalized["strategy"].get("source_prompt", ""),
            "risk": normalized.get("risk", {}),
            "sizing": normalized.get("sizing", {}),
            "execution": normalized.get("execution", {}),
        },
    }


def write_ta_foundation_template(spec_path: str | Path, output_path: str | Path) -> Path:
    spec = load_strategy_spec(spec_path)
    template = generate_ta_foundation_template(spec)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    return out_path


def _single_entry(spec: dict[str, Any]) -> dict[str, Any]:
    entries = spec.get("entries") or []
    if len(entries) != 1:
        raise PythonTemplateGenerationError("ta_foundation template generation currently supports exactly one entry")
    return entries[0]


def _map_entry(entry: dict[str, Any]) -> dict[str, Any]:
    entry_type = entry["type"]
    params = dict(entry.get("params") or {})
    timing = entry.get("timing", "next_open")

    if entry_type in {"ema_cross", "sma_cross", "ma_cross"}:
        return {
            "type": "ma_cross",
            "fast_type": params.get("fast_type", "ema" if entry_type == "ema_cross" else "sma"),
            "fast_period": int(params["fast_period"]),
            "slow_type": params.get("slow_type", "ema" if entry_type == "ema_cross" else "sma"),
            "slow_period": int(params["slow_period"]),
            "timing": timing,
        }

    if entry_type == "opening_range_breakout":
        return {
            "type": "orb",
            "orb_minutes": int(params.get("orb_minutes", 15)),
            "session_start": str(params.get("session_start", "08:30")),
            "retest_bars": int(params.get("retest_bars", 0)),
            "timing": timing,
        }

    if entry_type == "rsi_threshold":
        return {
            "type": "rsi_threshold",
            "period": int(params.get("period", 14)),
            "threshold": float(params.get("threshold", 30)),
            "cross_direction": str(params.get("cross_direction", "cross_above")),
            "timing": timing,
        }

    if entry_type == "price_level":
        mapped = {"type": "price_level", "timing": timing}
        mapped.update(params)
        return mapped

    if entry_type == "large_candle_reversal":
        pattern = params.get("pattern", "large_body")
        return {
            "type": "candle_pattern",
            "pattern": pattern,
            "timing": timing,
        }

    raise PythonTemplateGenerationError(f"Unsupported Python template entry type: {entry_type}")


def _map_entry_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in filters:
        filter_type = item.get("type")
        params = dict(item.get("params") or {})
        if filter_type == "time_window":
            continue
        if filter_type in {"moving_average_trend", "trend"}:
            mapped.append(
                {
                    "type": "trend",
                    "indicator": params.get("indicator", params.get("ma_type", "ema")),
                    "period": int(params.get("period", 50)),
                    "condition": params.get("condition", "price_above"),
                    "description": params.get("description", "trend filter"),
                }
            )
        elif filter_type in {"atr_volatility", "volatility"}:
            mapped.append(
                {
                    "type": "volatility",
                    "period": int(params.get("period", 14)),
                    "condition": params.get("condition", "above_median"),
                    "lookback": int(params.get("lookback", 20)),
                    "description": params.get("description", "volatility filter"),
                }
            )
        elif filter_type == "rsi":
            mapped.append(
                {
                    "type": "rsi",
                    "period": int(params.get("period", 14)),
                    "condition": params.get("condition", "below"),
                    "threshold": float(params.get("threshold", 60)),
                    "description": params.get("description", "rsi filter"),
                }
            )
        else:
            raise PythonTemplateGenerationError(f"Unsupported Python template filter type: {filter_type}")
    return mapped


def _session_rules(filters: list[dict[str, Any]]) -> dict[str, Any]:
    for item in filters:
        if item.get("type") == "time_window":
            params = item.get("params") or {}
            return {
                "enabled": True,
                "session_start": str(params.get("session_start", "08:30:00")),
                "session_end": str(params.get("session_end", "15:00:00")),
                "timezone": str(params.get("timezone", "America/Denver")),
            }
    return {
        "enabled": False,
        "session_start": "08:30:00",
        "session_end": "15:00:00",
        "timezone": "America/Denver",
    }


def _map_stop_mode(stop: dict[str, Any]) -> str:
    stop_type = stop.get("type")
    if stop_type == "fixed_ticks":
        return "fixed_ticks"
    if stop_type == "atr_based":
        return "atr_based"
    if stop_type == "signal_extreme_capped":
        return "signal_extreme_capped"
    raise PythonTemplateGenerationError(f"Unsupported stop type: {stop_type}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ta_foundation StrategyTemplate JSON from a canonical spec.")
    parser.add_argument("--spec", required=True, help="Path to canonical Strategy Factory spec JSON.")
    parser.add_argument("--out", required=True, help="Output path for ta_foundation template JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = write_ta_foundation_template(args.spec, args.out)
    print(f"Saved ta_foundation template to {out_path}")


if __name__ == "__main__":
    main()
