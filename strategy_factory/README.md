# Strategy Factory

This package is the first controlled strategy-generation slice. It starts from a canonical JSON spec and emits both:

- a `ta_foundation` StrategyTemplate JSON for Python backtesting/research
- a deterministic NinjaTrader 8 managed-order strategy class
- a NinjaTrader 8 `StrategyTemplate` XML for parameter variants of the same class

The first supported path is intentionally narrow: one MA crossover entry with fixed tick stop/target, fixed sizing, a time window, max-trades-per-day guard, session PnL lockout, and optional hard-kill PnL lockout. Parameter differences such as EMA lookback, stop size, or risk thresholds should become template XML files, not new strategy class names.

## Risk Modules

The generated NinjaScript uses managed static stops/targets for fixed exits and keeps risk lockouts separate from entry logic:

- `modules/risk/session_pnl_lockout.md` documents the realized PnL and trade-count lockout pattern from `PantheonMasterBotV01TesterV2.cs`.
- `modules/risk/hard_kill_pnl_lockout.md` documents the intrabar realized-plus-unrealized hard-kill pattern.
- `modules/exits/managed_dynamic_stop.md` documents the managed-order pattern to use when stops need to move dynamically without mixing managed and unmanaged order styles.
- `modules/parity/indicator_parity.md` documents the EMA/SMA warmup and signal-ledger assumptions needed for Python/NinjaScript parity.

## Generate Both Targets

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.factory `
  --spec .\strategy_factory\specs\examples\ema_cross_fixed_stop_target.json `
  --out-dir .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target
```

Outputs:

- `manifest.json`
- `EmaCrossFixedStopTarget.strategy_spec.normalized.json`
- `EmaCrossFixedStopTarget.ta_template.json`
- `EmaCrossFixedStopTarget.cs`
- `EmaCrossFixedStopTargetTemplate.xml`

## Generate Individual Targets

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.generators.python_template_generator `
  --spec .\strategy_factory\specs\examples\ema_cross_fixed_stop_target.json `
  --out .\strategy_factory\generated\python_templates\ema_cross_fixed_stop_target.ta_template.json
```

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.generators.ninjascript_generator `
  --spec .\strategy_factory\specs\examples\ema_cross_fixed_stop_target.json `
  --out .\strategy_factory\generated\ninjascript\EmaCrossFixedStopTarget.cs
```

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.generators.ninjascript_template_generator `
  --spec .\strategy_factory\specs\examples\ema_cross_fixed_stop_target.json `
  --out .\strategy_factory\generated\ninjascript_templates\EmaCrossFixedStopTargetTemplate.xml
```

To install a generated template manually, place it under:

```text
C:\Users\Owner\Documents\NinjaTrader 8\templates\Strategy\EmaCrossFixedStopTarget\
```

Or install both generated NinjaTrader files with overwrite protection:

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.install_ninjatrader_outputs `
  --ninjascript .\strategy_factory\generated\ninjascript\EmaCrossFixedStopTarget.cs `
  --template .\strategy_factory\generated\ninjascript_templates\EmaCrossFixedStopTargetTemplate.xml `
  --strategy-name EmaCrossFixedStopTarget
```

## Parity Ledgers

Run the generated ta_foundation template on a bars CSV and emit both raw signals and a JSONL ledger:

```powershell
$env:PYTHONPATH = "D:\Backup\projects\PythonProject\ta_foundation\src"
D:\Backup\projects\PythonProject\ta_foundation\.venv\Scripts\python.exe -m strategy_factory.parity.run_ta_foundation_signals `
  --template .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\EmaCrossFixedStopTarget.ta_template.json `
  --bars .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\bars.csv `
  --signals-out .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\python_signals.csv `
  --ledger-out .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\python_ledger.jsonl
```

If a ta_foundation signal CSV already exists, convert it directly to JSONL:

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.parity.python_signals_to_jsonl `
  --input .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\python_signals.csv `
  --out .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\python_ledger.jsonl `
  --strategy-id EmaCrossFixedStopTarget `
  --reason entry_ema_9_21 `
  --stop-ticks 20 `
  --target-ticks 40 `
  --quantity 1
```

Generated NinjaScript writes ledger lines with the `SF_LEDGER` prefix from entries and risk lockouts. Save NinjaTrader Output-window lines to a text file, then convert them to JSONL:

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.parity.nt_print_to_jsonl `
  --input .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\nt_output.txt `
  --out .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\ninjascript_ledger.jsonl `
  --strategy-id EmaCrossFixedStopTarget
```

Compare a Python ledger against the NinjaScript ledger:

```powershell
.\.venv\Scripts\python.exe -m strategy_factory.parity.compare_ledgers `
  --left .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\python_ledger.jsonl `
  --right .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\ninjascript_ledger.jsonl `
  --price-tolerance 0
```

Or run the Python signals, convert NinjaScript output, and compare in one command:

```powershell
$env:PYTHONPATH = "D:\Backup\projects\PythonProject\ta_foundation\src"
D:\Backup\projects\PythonProject\ta_foundation\.venv\Scripts\python.exe -m strategy_factory.parity.run_signal_parity_check `
  --template .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\EmaCrossFixedStopTarget.ta_template.json `
  --bars .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\bars.csv `
  --nt-output .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\nt_output.txt `
  --out-dir .\strategy_factory\generated\sessions\ema_cross_fixed_stop_target\parity `
  --strategy-id EmaCrossFixedStopTarget `
  --price-tolerance 0
```

## Next Targets

- Add module cards for each supported entry/filter/exit.
- Add a dynamic managed-exit skeleton based on the documented `Exit*`/`OnOrderUpdate`/`OnExecutionUpdate` pattern.
- Emit Python signal ledgers from `ta_foundation` backtests.
- Parse generated NinjaScript diagnostic output into the same ledger format.
- Compare signal parity before attempting fill parity.
