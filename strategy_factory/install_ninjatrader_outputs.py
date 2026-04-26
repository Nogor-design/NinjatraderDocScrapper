from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DEFAULT_NT_DOCUMENTS = Path.home() / "Documents" / "NinjaTrader 8"


class InstallError(RuntimeError):
    """Raised when generated NinjaTrader outputs cannot be installed safely."""


def install_outputs(
    *,
    ninjascript_path: str | Path,
    template_path: str | Path,
    strategy_name: str,
    nt_documents_dir: str | Path = DEFAULT_NT_DOCUMENTS,
    overwrite: bool = False,
) -> dict[str, Path]:
    nt_dir = Path(nt_documents_dir)
    strategy_source = Path(ninjascript_path)
    template_source = Path(template_path)
    if not strategy_source.is_file():
        raise InstallError(f"NinjaScript source does not exist: {strategy_source}")
    if not template_source.is_file():
        raise InstallError(f"Strategy template source does not exist: {template_source}")

    strategy_target = nt_dir / "bin" / "Custom" / "Strategies" / strategy_source.name
    template_target_dir = nt_dir / "templates" / "Strategy" / strategy_name
    template_target = template_target_dir / template_source.name

    _copy_file(strategy_source, strategy_target, overwrite=overwrite)
    _copy_file(template_source, template_target, overwrite=overwrite)
    return {
        "ninjascript": strategy_target,
        "template": template_target,
    }


def _copy_file(source: Path, target: Path, *, overwrite: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise InstallError(f"Target already exists; pass --overwrite to replace it: {target}")
    shutil.copy2(source, target)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install generated NinjaScript and StrategyTemplate XML into NinjaTrader.")
    parser.add_argument("--ninjascript", required=True, help="Generated .cs strategy path.")
    parser.add_argument("--template", required=True, help="Generated StrategyTemplate .xml path.")
    parser.add_argument("--strategy-name", required=True, help="NinjaTrader strategy/template folder name.")
    parser.add_argument(
        "--nt-documents-dir",
        default=str(DEFAULT_NT_DOCUMENTS),
        help="NinjaTrader documents folder. Defaults to the current user's Documents/NinjaTrader 8.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace existing target files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    installed = install_outputs(
        ninjascript_path=args.ninjascript,
        template_path=args.template,
        strategy_name=args.strategy_name,
        nt_documents_dir=args.nt_documents_dir,
        overwrite=args.overwrite,
    )
    print("Installed NinjaTrader outputs:")
    for name, path in installed.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
