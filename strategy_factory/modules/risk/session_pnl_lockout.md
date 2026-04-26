# Session PnL Lockout Risk Module

Use this module when a generated strategy should stop taking new entries after a session-level realized PnL threshold or trade-count threshold has been reached.

## Source Pattern

`C:\Users\Owner\Documents\NinjaTrader 8\bin\Custom\Strategies\PantheonMasterBotV01TesterV2.cs` uses a soft lockout pattern:

- Capture `SystemPerformance.AllTrades.Count` and `SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit` at the start of the session.
- Compare current cumulative realized PnL against the saved session baseline.
- Compare current trade count against the saved session baseline.
- Flatten the current strategy position and block further entries when profit, loss, or max-trade thresholds are reached.
- Reset the lockout on `Bars.IsFirstBarOfSession`.

## Generator Contract

The canonical spec fields are:

- `risk.max_trades_per_day`
- `risk.use_soft_pnl_lock`
- `risk.soft_profit_stop`
- `risk.soft_loss_stop`

Generated NinjaScript should emit:

- `priorTradesCount`
- `priorTradesCumProfit`
- `riskLocked`
- `ResetRiskSession()`
- `GetSessionTradeCount()`
- `GetSessionRealizedPnl()`
- `EvaluateSoftRiskLock()`
- `FlattenForRisk(string reason)`

## Preferred NinjaScript Shape

```csharp
if (Bars.IsFirstBarOfSession)
    ResetRiskSession();

if (riskLocked)
    return;

if (EvaluateSoftRiskLock())
    return;
```

`EvaluateSoftRiskLock()` should compare against session-relative values:

```csharp
double sessionPnl = GetSessionRealizedPnl();
int sessionTrades = GetSessionTradeCount();
```

## Notes

- Do not use total realtime trade count directly for a session limit. `SystemPerformance.RealTimeTrades.Count >= MaxTrades` can lock trading based on all realtime trades since the strategy started, not only the current session.
- Keep the soft lockout independent from entry logic. Entries should call a simple guard rather than duplicating risk checks.
- If a soft threshold is set to `0`, treat that side as disabled.
- This module is compatible with managed orders and static `SetStopLoss` / `SetProfitTarget` exits.
