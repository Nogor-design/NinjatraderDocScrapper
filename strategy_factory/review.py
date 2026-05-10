from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_\.]*)")
NAMESPACE_RE = re.compile(r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_\.]*)\s*\{")
METHOD_RE = re.compile(r"\b(?:protected|private|public)\s+(?:override\s+)?(?:void|bool|int|double|string)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PROPERTY_RE = re.compile(
    r"(?P<attributes>(?:\s*\[[^\]]+\]\s*)+)\s*public\s+(?P<type>[A-Za-z0-9_<>\.\?]+)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{\s*get;\s*set;\s*\}",
    re.MULTILINE,
)
INDICATOR_ASSIGN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Z][A-Za-z0-9_]*)\s*\(")


@dataclass(frozen=True)
class StrategyParameter:
    name: str
    type: str
    display_name: str = ""
    group_name: str = ""
    range_text: str = ""


@dataclass(frozen=True)
class StrategyReview:
    path: str
    namespace: str = ""
    class_name: str = ""
    base_class: str = ""
    lifecycle_methods: list[str] = field(default_factory=list)
    parameters: list[StrategyParameter] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    order_methods: list[str] = field(default_factory=list)
    order_style: str = "unknown"
    exit_style: str = "unknown"
    risk_guards: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def review_strategy_file(path: str | Path) -> StrategyReview:
    source_path = Path(path)
    return review_strategy_code(source_path.read_text(encoding="utf-8", errors="replace"), path=str(source_path))


def review_strategy_code(code: str, *, path: str = "") -> StrategyReview:
    namespace = _first_match(NAMESPACE_RE, code)
    class_match = CLASS_RE.search(code)
    class_name = class_match.group(1) if class_match else ""
    base_class = class_match.group(2) if class_match else ""
    methods = sorted(set(METHOD_RE.findall(code)))
    order_methods = _find_order_methods(code)
    warnings = _warnings(code, class_name, base_class, methods, order_methods)
    return StrategyReview(
        path=path,
        namespace=namespace,
        class_name=class_name,
        base_class=base_class,
        lifecycle_methods=[method for method in methods if method.startswith("On")],
        parameters=_parameters(code),
        indicators=_indicators(code),
        order_methods=order_methods,
        order_style=_order_style(code, order_methods),
        exit_style=_exit_style(code, order_methods),
        risk_guards=_risk_guards(code),
        warnings=warnings,
    )


def review_to_markdown(review: StrategyReview) -> str:
    lines = [
        f"# Strategy Review: {review.class_name or 'Unknown'}",
        "",
        f"- Path: {review.path or '(inline code)'}",
        f"- Namespace: {review.namespace or '(unknown)'}",
        f"- Base class: {review.base_class or '(unknown)'}",
        f"- Order style: {review.order_style}",
        f"- Exit style: {review.exit_style}",
        "",
        "## Lifecycle",
    ]
    lines.extend(f"- {method}" for method in review.lifecycle_methods or ["(none detected)"])
    lines.append("")
    lines.append("## Parameters")
    if review.parameters:
        for parameter in review.parameters:
            detail = ", ".join(
                part
                for part in [
                    parameter.type,
                    f"display={parameter.display_name}" if parameter.display_name else "",
                    f"group={parameter.group_name}" if parameter.group_name else "",
                    parameter.range_text,
                ]
                if part
            )
            lines.append(f"- {parameter.name}: {detail}")
    else:
        lines.append("- (none detected)")
    lines.append("")
    lines.append("## Indicators")
    lines.extend(f"- {indicator}" for indicator in review.indicators or ["(none detected)"])
    lines.append("")
    lines.append("## Order Methods")
    lines.extend(f"- {method}" for method in review.order_methods or ["(none detected)"])
    lines.append("")
    lines.append("## Risk Guards")
    lines.extend(f"- {guard}" for guard in review.risk_guards or ["(none detected)"])
    if review.warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in review.warnings)
    return "\n".join(lines) + "\n"


def _first_match(pattern: re.Pattern[str], code: str) -> str:
    match = pattern.search(code)
    return match.group(1) if match else ""


def _parameters(code: str) -> list[StrategyParameter]:
    parameters: list[StrategyParameter] = []
    for match in PROPERTY_RE.finditer(code):
        attributes = match.group("attributes")
        if "NinjaScriptProperty" not in attributes:
            continue
        parameters.append(
            StrategyParameter(
                name=match.group("name"),
                type=match.group("type"),
                display_name=_attribute_value(attributes, "Name"),
                group_name=_attribute_value(attributes, "GroupName"),
                range_text=_range_text(attributes),
            )
        )
    return parameters


def _attribute_value(attributes: str, key: str) -> str:
    match = re.search(rf"{re.escape(key)}\s*=\s*\"([^\"]+)\"", attributes)
    return match.group(1) if match else ""


def _range_text(attributes: str) -> str:
    match = re.search(r"\[Range\(([^\]]+)\)\]", attributes)
    return f"Range({match.group(1)})" if match else ""


def _indicators(code: str) -> list[str]:
    indicators = {
        match.group(2)
        for match in INDICATOR_ASSIGN_RE.finditer(code)
        if _looks_like_indicator_factory(match.group(2))
    }
    return sorted(indicators)


def _looks_like_indicator_factory(name: str) -> bool:
    return name not in {
            "DateTime",
            "Math",
            "Convert",
            "String",
            "TimeSpan",
            "ToTime",
        } and not name.startswith(("Get", "Evaluate", "Reset", "Print", "Escape"))


def _find_order_methods(code: str) -> list[str]:
    candidates = [
        "EnterLong",
        "EnterShort",
        "ExitLong",
        "ExitShort",
        "ExitLongStopMarket",
        "ExitShortStopMarket",
        "ExitLongLimit",
        "ExitShortLimit",
        "SetStopLoss",
        "SetProfitTarget",
        "SetTrailStop",
        "SubmitOrderUnmanaged",
        "ChangeOrder",
        "CancelOrder",
    ]
    return [name for name in candidates if re.search(rf"\b{re.escape(name)}\s*\(", code)]


def _order_style(code: str, order_methods: list[str]) -> str:
    if "SubmitOrderUnmanaged" in order_methods or "IsUnmanaged = true" in code:
        return "unmanaged"
    if any(method.startswith("Enter") or method.startswith("Exit") or method.startswith("Set") for method in order_methods):
        return "managed"
    return "unknown"


def _exit_style(code: str, order_methods: list[str]) -> str:
    set_methods = {"SetStopLoss", "SetProfitTarget", "SetTrailStop"} & set(order_methods)
    explicit_methods = {
        method
        for method in order_methods
        if method in {"ExitLongStopMarket", "ExitShortStopMarket", "ExitLongLimit", "ExitShortLimit"}
    }
    if set_methods and explicit_methods:
        return "mixed managed set-method and explicit exits"
    if set_methods:
        return "managed set-method exits"
    if explicit_methods:
        return "explicit managed exits"
    return "unknown"


def _risk_guards(code: str) -> list[str]:
    guards = []
    patterns = {
        "BarsInProgress guard": r"BarsInProgress\s*!=\s*0",
        "CurrentBar/BarsRequired guard": r"CurrentBar[s]?\s*(?:\[0\])?\s*<\s*(?:BarsRequiredToTrade|\d+)",
        "flat-position guard": r"Position\.MarketPosition\s*!=\s*MarketPosition\.Flat",
        "session reset": r"Bars\.IsFirstBarOfSession",
        "trade count limit": r"MaxTrades|tradesToday|tradeCount",
        "realized PnL lockout": r"CumProfit|GetSessionRealizedPnl|soft.*Pnl|Soft.*Stop",
        "unrealized PnL hard kill": r"GetUnrealizedProfitLoss|HardKill",
        "time window": r"ToTime\s*\(|StartTime|EndTime",
    }
    for label, pattern in patterns.items():
        if re.search(pattern, code, re.IGNORECASE):
            guards.append(label)
    return guards


def _warnings(code: str, class_name: str, base_class: str, methods: list[str], order_methods: list[str]) -> list[str]:
    warnings: list[str] = []
    if not class_name:
        warnings.append("No class declaration was detected.")
    if base_class and base_class != "Strategy":
        warnings.append(f"Class inherits from {base_class}, not Strategy.")
    if "OnBarUpdate" not in methods:
        warnings.append("No OnBarUpdate method was detected.")
    if "SetStopLoss" in order_methods and ("ExitLongStopMarket" in order_methods or "ExitShortStopMarket" in order_methods):
        warnings.append("SetStopLoss is mixed with explicit stop-market exits; review managed-order semantics carefully.")
    if "SubmitOrderUnmanaged" in order_methods and any(method.startswith("Enter") for method in order_methods):
        warnings.append("Unmanaged submit calls are mixed with managed Enter* methods.")
    if "NinjaScriptProperty" not in code:
        warnings.append("No NinjaScriptProperty parameters were detected.")
    return warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review a NinjaTrader strategy or indicator before repair.")
    parser.add_argument("path", help="Path to a .cs file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review = review_strategy_file(args.path)
    if args.json:
        print(json.dumps(asdict(review), indent=2))
    else:
        print(review_to_markdown(review))


if __name__ == "__main__":
    main()
