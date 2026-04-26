# Indicator Parity Module

Use this module when a strategy relies on indicators in both ta_foundation/Python and NinjaTrader.

## Current EMA/SMA Source

The current ta_foundation strategy composer implements:

```python
SMA = close.rolling(period, min_periods=period).mean()
EMA = close.ewm(span=period, adjust=False, min_periods=period).mean()
```

The generated NinjaScript strategy currently uses native NinjaTrader indicators:

```csharp
fastMa = EMA(FastPeriod);
slowMa = EMA(SlowPeriod);
```

This can compile and run correctly while still producing occasional signal drift if warmup, seed values, missing bars, or session boundaries differ.

## Generator Contract

For parity work, every generated strategy should define:

- `data.lookback_bars`
- indicator type and period
- bar timestamp convention
- calculation mode (`OnBarClose` first)
- price basis (`close` first)
- session filter convention

Signal parity should compare:

- strategy id
- timestamp
- event
- entry reason
- bar index
- stop/target ticks
- quantity
- price basis

## Practical Rules

- Start parity comparisons after `BarsRequiredToTrade`, not from the first available row.
- Preserve source bar indexes in Python signals before ta_foundation resets DataFrame indexes.
- Use the exact same bars CSV that NinjaTrader exported whenever possible.
- Treat price mismatches separately from event mismatches; a timestamp match with a different price is a different class of bug.
- If EMA cross drift appears, export fast/slow indicator values from NinjaTrader and compare them to Python before changing entry logic.

## Next Implementation Step

Add optional diagnostic fields to generated `SF_LEDGER` lines:

- `fast_ma`
- `slow_ma`
- `close`

Then extend the ledger parser to keep extra key/value fields in event metadata. This should be optional so normal parity reports stay compact.
