# Exit_ManagedDynamicStop

Purpose: move protective stops in NinjaTrader 8 managed-order strategies without mixing managed and unmanaged order APIs.

Use when:
- A strategy needs trailing stops, break-even stops, stop-in-profit, or dynamically changed profit targets.
- The stop or target must be based on the actual fill price, not only the signal bar close.

Do not use with:
- `SetStopLoss()` or `SetProfitTarget()` for the same position after the entry fills.
- Unmanaged order methods in a managed-order strategy.

NinjaTrader pattern:
- Submit the entry with `EnterLong()` or `EnterShort()` from `OnBarUpdate`.
- Do not call `SetStopLoss()` for positions that will use explicit moving stops.
- In `OnExecutionUpdate`, detect the filled entry and compute the protective stop from `execution.Order.AverageFillPrice`.
- Submit the stop with `ExitLongStopMarket()` or `ExitShortStopMarket()` using `isLiveUntilCancelled=true`, a stable stop signal name, and the matching `fromEntrySignal`.
- Track stop and target `Order` references in `OnOrderUpdate` by matching `order.Name`.
- On transition to realtime, replace backtest order references with `GetRealtimeOrder()`.
- Null tracked references on terminal states: `Cancelled`, `Filled`, or `Rejected`.
- For trailing movement, only tighten the stop. Prefer `ChangeOrder(activeStopOrder, activeStopOrder.Quantity, 0, newStopPrice)` when a working order reference exists; otherwise resubmit the same `Exit*StopMarket` signal name as a replace fallback.

Common mistakes:
- Calling `SetStopLoss()` and also submitting `ExitLongStopMarket()` or `ExitShortStopMarket()` for the same position.
- Assigning the returned order object in `OnBarUpdate` and immediately relying on it.
- Moving a stop wider during trail updates.
- Calling `ChangeOrder()` on historical order references after the strategy transitions live.
- Omitting `isLiveUntilCancelled=true` on explicit exit orders that must persist across bars.

Compatible skeletons:
- Future `nt8_managed_dynamic_exit_strategy.cs.tmpl`

Reference implementation:
- `C:\Users\Owner\Documents\NinjaTrader 8\bin\Custom\Strategies\LargeCandleReversal.cs`

