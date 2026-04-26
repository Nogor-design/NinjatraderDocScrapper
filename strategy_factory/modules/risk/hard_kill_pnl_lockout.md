# Hard Kill PnL Lockout Risk Module

Use this module when a generated strategy needs a faster intrabar risk stop that includes open-position PnL, not just closed-trade PnL.

## Source Pattern

`C:\Users\Owner\Documents\NinjaTrader 8\bin\Custom\Strategies\PantheonMasterBotV01TesterV2.cs` uses `OnMarketData()` to combine realized session PnL with unrealized PnL. When the combined value is above a profit kill or below a loss kill, it disables trading and exits the current position.

The useful concept is the two-tier risk model:

- Soft session lockout: realized PnL and trade count, checked before entries.
- Hard kill: realized plus unrealized PnL, checked from market data so it can flatten faster than an on-bar-close strategy.

## Generator Contract

The canonical spec fields are:

- `risk.use_hard_kill`
- `risk.hard_kill_profit`
- `risk.hard_kill_loss`

Generated NinjaScript should emit:

- `UseHardKill`
- `HardKillProfit`
- `HardKillLoss`
- `EvaluateHardKill(double lastPrice)`
- `OnMarketData(MarketDataEventArgs marketDataUpdate)`

## Preferred NinjaScript Shape

```csharp
protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
{
    if (State == State.Historical || marketDataUpdate.MarketDataType != MarketDataType.Last)
        return;

    EvaluateHardKill(marketDataUpdate.Price);
}
```

For generated strategy-level risk, prefer strategy position PnL:

```csharp
double unrealizedPnl = Position.MarketPosition == MarketPosition.Flat
    ? 0
    : Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, lastPrice);
double currentPnl = GetSessionRealizedPnl() + unrealizedPnl;
```

## Notes

- Avoid scanning `Account.All` on every tick in generated code. It is slower and can unintentionally measure account-level PnL instead of the strategy's position.
- Account-level hard kills can be useful, but they should be an explicit module because they affect positions outside the generated strategy.
- If a hard-kill threshold is set to `0`, treat that side as disabled.
- The hard kill should set the same `riskLocked` flag used by the soft lockout so no later entry block can reopen the strategy in the same session.
