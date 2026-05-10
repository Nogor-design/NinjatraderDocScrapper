from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from strategy_factory.specs.validator import load_strategy_spec, normalize_strategy_spec


class NinjaScriptGenerationError(ValueError):
    """Raised when a canonical spec cannot be mapped to deterministic NinjaScript."""


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "skeletons" / "nt8_managed_strategy.cs.tmpl"


def generate_ninjascript_strategy(spec: dict[str, Any]) -> str:
    normalized = normalize_strategy_spec(spec)
    entry = _single_entry(normalized)
    if entry["type"] not in {"ema_cross", "sma_cross", "ma_cross"}:
        raise NinjaScriptGenerationError("NinjaScript v1 generator supports only MA cross entries")

    stop = normalized["exits"]["stop"]
    target = normalized["exits"]["target"]
    if stop["type"] != "fixed_ticks" or target["type"] != "fixed_ticks":
        raise NinjaScriptGenerationError("NinjaScript v1 generator supports only fixed tick stop/target exits")

    params = entry["params"]
    fast_type = str(params.get("fast_type", "ema")).lower()
    slow_type = str(params.get("slow_type", "ema")).lower()
    risk = normalized["risk"]
    trend_filters = _trend_filters(normalized.get("filters", []))
    _validate_supported_filters(normalized.get("filters", []))
    bars_required = max(
        int(params["fast_period"]),
        int(params["slow_period"]),
        int(normalized["data"]["lookback_bars"]),
        *[int(item["params"].get("period", 50)) for item in trend_filters],
    )
    replacements = {
        "CLASS_NAME": _class_name(normalized["strategy"]["id"]),
        "DESCRIPTION": _escape_csharp_string(normalized["strategy"].get("hypothesis", "")),
        "FAST_INDICATOR_TYPE": _indicator_type(fast_type),
        "SLOW_INDICATOR_TYPE": _indicator_type(slow_type),
        "FAST_INDICATOR_FACTORY": _indicator_factory(fast_type),
        "SLOW_INDICATOR_FACTORY": _indicator_factory(slow_type),
        "FAST_PERIOD": str(int(params["fast_period"])),
        "SLOW_PERIOD": str(int(params["slow_period"])),
        "STOP_TICKS": str(int(stop["ticks"])),
        "TARGET_TICKS": str(int(target["ticks"])),
        "QUANTITY": str(int(normalized["sizing"].get("contracts", 1))),
        "MAX_TRADES_PER_DAY": str(int(risk.get("max_trades_per_day", 3))),
        "USE_SOFT_PNL_LOCK": _csharp_bool(bool(risk.get("use_soft_pnl_lock", False))),
        "SOFT_PROFIT_STOP": _csharp_decimal(float(risk.get("soft_profit_stop", 0.0))),
        "SOFT_LOSS_STOP": _csharp_decimal(float(risk.get("soft_loss_stop", 0.0))),
        "USE_HARD_KILL": _csharp_bool(bool(risk.get("use_hard_kill", False))),
        "HARD_KILL_PROFIT": _csharp_decimal(float(risk.get("hard_kill_profit", 0.0))),
        "HARD_KILL_LOSS": _csharp_decimal(float(risk.get("hard_kill_loss", 0.0))),
        "START_TIME": _session_time(normalized.get("filters", []), "session_start", "083000"),
        "END_TIME": _session_time(normalized.get("filters", []), "session_end", "113000"),
        "BARS_REQUIRED": str(bars_required),
        "ENTRY_LOGIC": _entry_logic(normalized["direction"], _escape_csharp_string(entry["id"])),
        "FILTER_FIELD_DECLARATIONS": _filter_field_declarations(trend_filters),
        "FILTER_DEFAULTS": _filter_defaults(trend_filters),
        "FILTER_INITIALIZERS": _filter_initializers(trend_filters),
        "FILTER_GUARDS": _filter_guards(trend_filters),
        "FILTER_PROPERTIES": _filter_properties(trend_filters),
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def write_ninjascript_strategy(spec_path: str | Path, output_path: str | Path) -> Path:
    spec = load_strategy_spec(spec_path)
    code = generate_ninjascript_strategy(spec)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(code, encoding="utf-8")
    return out_path


def _single_entry(spec: dict[str, Any]) -> dict[str, Any]:
    entries = spec.get("entries") or []
    if len(entries) != 1:
        raise NinjaScriptGenerationError("NinjaScript v1 generation currently supports exactly one entry")
    return entries[0]


def _class_name(strategy_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", strategy_id)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "GeneratedStrategy_" + cleaned
    return cleaned


def _indicator_type(value: str) -> str:
    if value == "ema":
        return "EMA"
    if value == "sma":
        return "SMA"
    raise NinjaScriptGenerationError(f"Unsupported MA type for NinjaScript: {value}")


def _indicator_factory(value: str) -> str:
    return _indicator_type(value)


def _session_time(filters: list[dict[str, Any]], key: str, default: str) -> str:
    for item in filters:
        if item.get("type") != "time_window":
            continue
        value = str((item.get("params") or {}).get(key, default))
        return _to_hhmmss_int(value)
    return _to_hhmmss_int(default)


def _validate_supported_filters(filters: list[dict[str, Any]]) -> None:
    supported = {"time_window", "moving_average_trend", "trend"}
    for item in filters:
        filter_type = str(item.get("type", ""))
        if filter_type not in supported:
            raise NinjaScriptGenerationError(f"NinjaScript v1 generator does not support filter type: {filter_type}")
        if filter_type in {"moving_average_trend", "trend"}:
            params = item.get("params") or {}
            indicator = str(params.get("indicator", params.get("ma_type", "ema"))).lower()
            _indicator_type(indicator)
            condition = str(params.get("condition", "price_above")).lower()
            if condition not in {"price_above", "price_below"}:
                raise NinjaScriptGenerationError(
                    f"NinjaScript v1 trend filter supports only price_above/price_below, got: {condition}"
                )


def _trend_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in filters if item.get("type") in {"moving_average_trend", "trend"}]


def _filter_field_declarations(filters: list[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(filters, start=1):
        indicator = _trend_indicator(item)
        lines.append(f"        private {_indicator_type(indicator)} trendMa{index};")
    return "\n".join(lines)


def _filter_defaults(filters: list[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(filters, start=1):
        period = int((item.get("params") or {}).get("period", 50))
        lines.append(f"                TrendPeriod{index} = {period};")
    return "\n".join(lines)


def _filter_initializers(filters: list[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(filters, start=1):
        indicator = _trend_indicator(item)
        lines.append(f"                trendMa{index} = {_indicator_factory(indicator)}(TrendPeriod{index});")
    return "\n".join(lines)


def _filter_guards(filters: list[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(filters, start=1):
        condition = str((item.get("params") or {}).get("condition", "price_above")).lower()
        if condition == "price_above":
            lines.append(
                f"""            if (Close[0] <= trendMa{index}[0])
                return;"""
            )
        elif condition == "price_below":
            lines.append(
                f"""            if (Close[0] >= trendMa{index}[0])
                return;"""
            )
        else:
            raise NinjaScriptGenerationError(f"Unsupported trend filter condition: {condition}")
    return "\n\n".join(lines)


def _filter_properties(filters: list[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(filters, start=1):
        indicator = _trend_indicator(item).upper()
        lines.append(
            f"""        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "{indicator} Trend Period {index}", Order = {20 + index}, GroupName = "Filters")]
        public int TrendPeriod{index} {{ get; set; }}"""
        )
    return "\n\n".join(lines)


def _trend_indicator(filter_item: dict[str, Any]) -> str:
    params = filter_item.get("params") or {}
    return str(params.get("indicator", params.get("ma_type", "ema"))).lower()


def _to_hhmmss_int(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) == 4:
        digits += "00"
    if len(digits) != 6:
        raise NinjaScriptGenerationError(f"Session time must be HH:mm or HH:mm:ss: {value}")
    return str(int(digits))


def _entry_logic(direction: str, entry_reason: str) -> str:
    parts: list[str] = []
    if direction in {"long", "both"}:
        parts.append(
            f"""            if (CrossAbove(fastMa, slowMa, 1))
            {{
                EnterLong(Quantity, "LongEntry");
                tradesToday++;
                PrintLedgerEvent("ENTER_LONG", "{entry_reason}", Close[0]);
            }}"""
        )
    if direction in {"short", "both"}:
        prefix = "            else " if parts else "            "
        parts.append(
            prefix
            + f"""if (CrossBelow(fastMa, slowMa, 1))
            {{
                EnterShort(Quantity, "ShortEntry");
                tradesToday++;
                PrintLedgerEvent("ENTER_SHORT", "{entry_reason}", Close[0]);
            }}"""
        )
    return "\n".join(parts)


def _escape_csharp_string(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _csharp_bool(value: bool) -> str:
    return "true" if value else "false"


def _csharp_decimal(value: float) -> str:
    text = f"{value:.10g}"
    return text if "." in text else f"{text}.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic NinjaTrader 8 strategy code from a canonical spec.")
    parser.add_argument("--spec", required=True, help="Path to canonical Strategy Factory spec JSON.")
    parser.add_argument("--out", required=True, help="Output path for generated .cs strategy.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = write_ninjascript_strategy(args.spec, args.out)
    print(f"Saved NinjaScript strategy to {out_path}")


if __name__ == "__main__":
    main()
