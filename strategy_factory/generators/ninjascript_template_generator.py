from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

from strategy_factory.generators.ninjascript_generator import _class_name, _session_time, _single_entry
from strategy_factory.specs.validator import load_strategy_spec, normalize_strategy_spec


class NinjaScriptTemplateGenerationError(ValueError):
    """Raised when a spec cannot be mapped to a NinjaTrader StrategyTemplate XML."""


PARAMETER_TYPE_INT = "System.Int32, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"
PARAMETER_TYPE_DOUBLE = "System.Double, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"
PARAMETER_TYPE_BOOL = "System.Boolean, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"


def generate_ninjascript_template_xml(spec: dict[str, Any], *, template_name: str | None = None) -> str:
    """Generate a NinjaTrader 8 StrategyTemplate XML for the generated strategy class."""
    normalized = normalize_strategy_spec(spec)
    entry = _single_entry(normalized)
    params = entry["params"]
    class_name = _class_name(normalized["strategy"]["id"])
    name = template_name or _template_name(normalized)
    instrument = _instrument_name(normalized)
    timeframe_value = _timeframe_value(normalized["market"]["timeframe"])
    risk = normalized["risk"]
    strategy_params = {
        "FastPeriod": int(params["fast_period"]),
        "SlowPeriod": int(params["slow_period"]),
        "StopTicks": int(normalized["exits"]["stop"]["ticks"]),
        "TargetTicks": int(normalized["exits"]["target"]["ticks"]),
        "Quantity": int(normalized["sizing"].get("contracts", 1)),
        "MaxTradesPerDay": int(risk.get("max_trades_per_day", 3)),
        "UseSoftPnlLock": bool(risk.get("use_soft_pnl_lock", False)),
        "SoftProfitStop": float(risk.get("soft_profit_stop", 0.0)),
        "SoftLossStop": float(risk.get("soft_loss_stop", 0.0)),
        "UseHardKill": bool(risk.get("use_hard_kill", False)),
        "HardKillProfit": float(risk.get("hard_kill_profit", 0.0)),
        "HardKillLoss": float(risk.get("hard_kill_loss", 0.0)),
        "StartTime": int(_session_time(normalized.get("filters", []), "session_start", "083000")),
        "EndTime": int(_session_time(normalized.get("filters", []), "session_end", "113000")),
    }

    optimization_parameters = "\n".join(
        _optimization_parameter_xml(param_name, value) for param_name, value in strategy_params.items()
    )
    strategy_parameter_elements = "\n".join(
        f"      <{param_name}>{html.escape(_value_text(value))}</{param_name}>"
        for param_name, value in strategy_params.items()
    )

    return f"""<?xml version="1.0" encoding="utf-8"?>
<StrategyTemplate>
  <StrategyType>NinjaTrader.NinjaScript.Strategies.{class_name}</StrategyType>
  <OptimizerType>NinjaTrader.NinjaScript.Optimizers.DefaultOptimizer</OptimizerType>
  <OptimizerParameters>
    <ArrayOfParameterWrapper xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <ParameterWrapper>
        <DisplayName>IsStrategyGenerator</DisplayName>
        <Name>IsStrategyGenerator</Name>
        <Value xsi:type="xsd:boolean">false</Value>
      </ParameterWrapper>
      <ParameterWrapper>
        <DisplayName>Keep best # results</DisplayName>
        <Name>KeepBestResults</Name>
        <Value xsi:type="xsd:int">10</Value>
      </ParameterWrapper>
      <ParameterWrapper>
        <DisplayName>LogTypeName</DisplayName>
        <Name>LogTypeName</Name>
        <Value xsi:type="xsd:string">Optimizer</Value>
      </ParameterWrapper>
      <ParameterWrapper>
        <DisplayName>Visible</DisplayName>
        <Name>IsVisible</Name>
        <Value xsi:type="xsd:boolean">true</Value>
      </ParameterWrapper>
      <ParameterWrapper>
        <DisplayName>Name</DisplayName>
        <Name>Name</Name>
        <Value xsi:type="xsd:string">{html.escape(name)}</Value>
      </ParameterWrapper>
    </ArrayOfParameterWrapper>
  </OptimizerParameters>
  <OptimizationFitness>NinjaTrader.NinjaScript.OptimizationFitnesses.MaxProfitFactor</OptimizationFitness>
  <OptimizationParameters>
    <ArrayOfParameter xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
{optimization_parameters}
    </ArrayOfParameter>
  </OptimizationParameters>
  <Strategy>
    <{class_name} xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <IsVisible>true</IsVisible>
      <calculate2>OnBarClose</calculate2>
      <AreLinesConfigurable>true</AreLinesConfigurable>
      <ArePlotsConfigurable>true</ArePlotsConfigurable>
      <BarsPeriodSerializable>
        <BarsPeriodTypeSerialize>4</BarsPeriodTypeSerialize>
        <BaseBarsPeriodType>Minute</BaseBarsPeriodType>
        <BaseBarsPeriodValue>{timeframe_value}</BaseBarsPeriodValue>
        <VolumetricDeltaType>BidAsk</VolumetricDeltaType>
        <MarketDataType>Last</MarketDataType>
        <PointAndFigurePriceType>Close</PointAndFigurePriceType>
        <ReversalType>Tick</ReversalType>
        <Value>2</Value>
        <Value2>1</Value2>
      </BarsPeriodSerializable>
      <BarsToLoad>0</BarsToLoad>
      <Calculate>OnBarClose</Calculate>
      <Displacement>0</Displacement>
      <DisplayInDataBox>true</DisplayInDataBox>
      <From>2026-04-20T00:00:00</From>
      <IsAutoScale>true</IsAutoScale>
      <Lines />
      <MaximumBarsLookBack>TwoHundredFiftySix</MaximumBarsLookBack>
      <Name>{class_name}</Name>
      <Panel>-1</Panel>
      <Plots />
      <ScaleJustification>Right</ScaleJustification>
      <ShowTransparentPlotsInDataBox>false</ShowTransparentPlotsInDataBox>
      <To>2026-04-25T00:00:00</To>
      <IsDataSeriesRequired>true</IsDataSeriesRequired>
      <IsOverlay>true</IsOverlay>
      <SelectedValueSeries>0</SelectedValueSeries>
      <Gtd>1800-01-01T00:00:00</Gtd>
      <Template>{html.escape(name)}</Template>
      <TimeInForce>Gtc</TimeInForce>
      <BarsPeriodParameter>
        <Increment>1</Increment>
        <Max xsi:type="xsd:int">0</Max>
        <Min xsi:type="xsd:int">0</Min>
        <Name />
        <ParameterTypeSerializable>{PARAMETER_TYPE_INT}</ParameterTypeSerializable>
        <ValueSerializable>0</ValueSerializable>
      </BarsPeriodParameter>
      <BarsRequiredToTrade>{max(int(params["fast_period"]), int(params["slow_period"]), int(normalized["data"]["lookback_bars"]))}</BarsRequiredToTrade>
      <Category>NinjaScript</Category>
      <ConnectionLossHandling>Recalculate</ConnectionLossHandling>
      <DaysToLoad>5</DaysToLoad>
      <DefaultQuantity>{strategy_params["Quantity"]}</DefaultQuantity>
      <DisconnectDelaySeconds>10</DisconnectDelaySeconds>
      <EntriesPerDirection>1</EntriesPerDirection>
      <EntryHandling>AllEntries</EntryHandling>
      <ExitOnSessionCloseSeconds>30</ExitOnSessionCloseSeconds>
      <IncludeCommission>false</IncludeCommission>
      <InstrumentOrInstrumentList>{html.escape(instrument)}</InstrumentOrInstrumentList>
      <IsAggregated>false</IsAggregated>
      <IsExitOnSessionCloseStrategy>true</IsExitOnSessionCloseStrategy>
      <IsFillLimitOnTouch>false</IsFillLimitOnTouch>
      <IsOptimizeDataSeries>false</IsOptimizeDataSeries>
      <IsStableSession>true</IsStableSession>
      <IsTickReplay>false</IsTickReplay>
      <IsTradingHoursBreakLineVisible>true</IsTradingHoursBreakLineVisible>
      <IsWaitUntilFlat>false</IsWaitUntilFlat>
      <NumberRestartAttempts>4</NumberRestartAttempts>
      <OptimizationPeriod>10</OptimizationPeriod>
      <OrderFillResolution>Standard</OrderFillResolution>
      <OrderFillResolutionType>Minute</OrderFillResolutionType>
      <OrderFillResolutionValue>1</OrderFillResolutionValue>
      <RestartsWithinMinutes>5</RestartsWithinMinutes>
      <SetOrderQuantity>Strategy</SetOrderQuantity>
      <Slippage>0</Slippage>
      <StartBehavior>WaitUntilFlat</StartBehavior>
      <StopTargetHandling>PerEntryExecution</StopTargetHandling>
      <SupportsOptimizationGraph>true</SupportsOptimizationGraph>
      <TestPeriod>28</TestPeriod>
      <TradingHoursSerializable />
      <DrawOnPricePanel>false</DrawOnPricePanel>
      <ZOrder>-2147483648</ZOrder>
{strategy_parameter_elements}
    </{class_name}>
  </Strategy>
</StrategyTemplate>
"""


def write_ninjascript_template_xml(
    spec_path: str | Path,
    output_path: str | Path,
    *,
    template_name: str | None = None,
) -> Path:
    spec = load_strategy_spec(spec_path)
    xml = generate_ninjascript_template_xml(spec, template_name=template_name)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml, encoding="utf-8")
    return out_path


def _template_name(spec: dict[str, Any]) -> str:
    value = (spec.get("metadata") or {}).get("template_name")
    if value:
        return str(value)
    return f"{_class_name(spec['strategy']['id'])}Template"


def _instrument_name(spec: dict[str, Any]) -> str:
    instrument = str(spec["market"]["instrument"]).strip()
    contract = str(spec["market"].get("contract") or "").strip()
    return f"{instrument} {contract}".strip()


def _timeframe_value(timeframe: str) -> int:
    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    if timeframe == "1h":
        return 60
    raise NinjaScriptTemplateGenerationError(f"Unsupported NinjaTrader template timeframe: {timeframe}")


def _optimization_parameter_xml(name: str, value: int | float | bool) -> str:
    escaped_name = html.escape(name)
    escaped_value = html.escape(_value_text(value))
    xsd_type = _xsd_type(value)
    parameter_type = _parameter_type(value)
    increment = "1" if isinstance(value, int) and not isinstance(value, bool) else "0"
    return f"""      <Parameter>
        <EnumValuesSerializable />
        <Increment>{increment}</Increment>
        <Max xsi:type="{xsd_type}">{escaped_value}</Max>
        <Min xsi:type="{xsd_type}">{escaped_value}</Min>
        <Name>{escaped_name}</Name>
        <ParameterTypeSerializable>{parameter_type}</ParameterTypeSerializable>
        <ValueSerializable>{escaped_value}</ValueSerializable>
      </Parameter>"""


def _value_text(value: int | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.10g}"
        return text if "." in text else f"{text}.0"
    return str(value)


def _xsd_type(value: int | float | bool) -> str:
    if isinstance(value, bool):
        return "xsd:boolean"
    if isinstance(value, float):
        return "xsd:double"
    return "xsd:int"


def _parameter_type(value: int | float | bool) -> str:
    if isinstance(value, bool):
        return PARAMETER_TYPE_BOOL
    if isinstance(value, float):
        return PARAMETER_TYPE_DOUBLE
    return PARAMETER_TYPE_INT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a NinjaTrader 8 StrategyTemplate XML from a canonical spec.")
    parser.add_argument("--spec", required=True, help="Path to canonical Strategy Factory spec JSON.")
    parser.add_argument("--out", required=True, help="Output path for generated StrategyTemplate XML.")
    parser.add_argument("--template-name", default="", help="Optional NinjaTrader template name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = write_ninjascript_template_xml(
        args.spec,
        args.out,
        template_name=args.template_name or None,
    )
    print(f"Saved NinjaTrader strategy template to {out_path}")


if __name__ == "__main__":
    main()
