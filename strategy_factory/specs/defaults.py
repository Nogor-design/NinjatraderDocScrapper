from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_SPEC_VALUES: dict[str, Any] = {
    "schema_version": "0.1",
    "data": {
        "calculation": "on_bar_close",
        "lookback_bars": 50,
    },
    "filters": [],
    "exits": {
        "max_hold_bars": 20,
        "flatten_on_session_end": True,
        "partial": {
            "enabled": False,
        },
        "runner": {
            "enabled": False,
        },
    },
    "sizing": {
        "type": "fixed_contracts",
        "contracts": 1,
        "max_contracts": 1,
    },
    "risk": {
        "max_trades_per_day": 3,
        "use_soft_pnl_lock": False,
        "soft_profit_stop": 0.0,
        "soft_loss_stop": 0.0,
        "use_hard_kill": False,
        "hard_kill_profit": 0.0,
        "hard_kill_loss": 0.0,
        "max_consecutive_losses": 2,
        "cooldown_bars_after_loss": 5,
    },
    "execution": {
        "python_bridge": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8766,
        },
        "ninjascript": {
            "order_mode": "managed",
            "calculate": "OnBarClose",
        },
    },
    "metadata": {},
}


def deep_merge_defaults(spec: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a copy of spec with nested default values filled in."""
    base = deepcopy(defaults or DEFAULT_SPEC_VALUES)
    return _merge(base, deepcopy(spec))


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge(base[key], value)
        else:
            base[key] = value
    return base
