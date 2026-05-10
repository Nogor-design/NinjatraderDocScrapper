# Filter_MovingAverageTrend

Purpose: require price to be on the configured side of a trend moving average before allowing an entry.

Use when:
- A momentum or crossover strategy should only trade with a broader trend regime.
- The canonical spec contains a `moving_average_trend` or `trend` filter.

Canonical spec shape:

```json
{
  "type": "moving_average_trend",
  "params": {
    "indicator": "ema",
    "period": 50,
    "condition": "price_above"
  }
}
```

Supported NinjaScript v1 conditions:

- `price_above`: block entries unless `Close[0] > trendMa[0]`
- `price_below`: block entries unless `Close[0] < trendMa[0]`

Generator contract:

- Declare a trend indicator field such as `private EMA trendMa1;`.
- Add a `TrendPeriod1` `[NinjaScriptProperty]` so StrategyTemplate XML can vary it.
- Initialize the indicator in `State.DataLoaded`.
- Apply the guard after session/risk checks and before trade-count/position-entry checks.
- Include the trend period in `BarsRequiredToTrade`.

Notes:

- Start with `EMA` and `SMA` only. Do not invent generic moving average APIs.
- Direction-aware trend filters should be a future explicit module; this module only supports absolute `price_above` and `price_below`.
