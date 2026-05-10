from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_COMPILE_LOOP_ROOT = Path(r"C:\ta_foundation\nt_compile_loop")


@dataclass(frozen=True)
class CompileLoopPaths:
    root: Path
    staging: Path
    installed: Path
    compiler_errors: Path
    iterations: Path
    final: Path
    logs: Path

    def as_serializable_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def compile_loop_paths(root: str | Path = DEFAULT_COMPILE_LOOP_ROOT) -> CompileLoopPaths:
    base = Path(root)
    return CompileLoopPaths(
        root=base,
        staging=base / "staging",
        installed=base / "installed",
        compiler_errors=base / "compiler_errors",
        iterations=base / "iterations",
        final=base / "final",
        logs=base / "logs",
    )


def ensure_compile_loop(root: str | Path = DEFAULT_COMPILE_LOOP_ROOT) -> CompileLoopPaths:
    paths = compile_loop_paths(root)
    for path in asdict(paths).values():
        Path(path).mkdir(parents=True, exist_ok=True)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or inspect the NinjaTrader compile-loop folder contract.")
    parser.add_argument("--root", default=str(DEFAULT_COMPILE_LOOP_ROOT), help="Compile-loop root folder.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a readable list.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = ensure_compile_loop(args.root)
    payload = paths.as_serializable_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("NinjaTrader compile-loop folders:")
        for name, path in payload.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
