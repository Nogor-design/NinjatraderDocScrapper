from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from strategy_factory.compile_loop.paths import DEFAULT_COMPILE_LOOP_ROOT, ensure_compile_loop
from strategy_factory.install_ninjatrader_outputs import DEFAULT_NT_DOCUMENTS, InstallError


@dataclass(frozen=True)
class InstallManifest:
    installed_at: str
    source_path: str
    staging_path: str
    target_path: str
    manifest_path: str
    sha256: str
    bytes: int
    overwrite: bool
    iteration_id: str = ""
    notes: str = ""

    def as_serializable_dict(self) -> dict:
        return asdict(self)


def install_strategy_file(
    source_path: str | Path,
    *,
    compile_root: str | Path = DEFAULT_COMPILE_LOOP_ROOT,
    nt_documents_dir: str | Path = DEFAULT_NT_DOCUMENTS,
    overwrite: bool = False,
    iteration_id: str = "",
    notes: str = "",
) -> InstallManifest:
    source = Path(source_path)
    if not source.is_file():
        raise InstallError(f"NinjaScript source does not exist: {source}")
    if source.suffix.lower() != ".cs":
        raise InstallError(f"NinjaScript source must be a .cs file: {source}")

    paths = ensure_compile_loop(compile_root)
    nt_dir = Path(nt_documents_dir)
    target = nt_dir / "bin" / "Custom" / "Strategies" / source.name
    staging = paths.staging / source.name
    digest = file_sha256(source)
    installed_at = datetime.now().isoformat(timespec="seconds")

    _copy_file(source, staging, overwrite=True)
    _copy_file(source, target, overwrite=overwrite)

    # Automatically detect and install matching StrategyTemplate XML if present
    template_name = f"{source.stem}Template.xml"
    template_source = source.parent / template_name
    template_target_path = ""
    if template_source.is_file():
        # Install to StrategyAnalyzer folder so it appears in the Strategy Analyzer template dialog
        template_target_dir = nt_dir / "templates" / "StrategyAnalyzer" / source.stem
        template_target = template_target_dir / template_name
        _copy_file(template_source, template_target, overwrite=overwrite)
        template_target_path = str(template_target.resolve())

    manifest_path = paths.installed / f"{_manifest_stamp(installed_at)}_{source.stem}.install.json"
    manifest = InstallManifest(
        installed_at=installed_at,
        source_path=str(source.resolve()),
        staging_path=str(staging.resolve()),
        target_path=str(target.resolve()),
        manifest_path=str(manifest_path.resolve()),
        sha256=digest,
        bytes=source.stat().st_size,
        overwrite=overwrite,
        iteration_id=iteration_id,
        notes=notes + (f" (including template: {template_target_path})" if template_target_path else ""),
    )
    manifest_path.write_text(json.dumps(manifest.as_serializable_dict(), indent=2) + "\n", encoding="utf-8")
    return manifest


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(source: Path, target: Path, *, overwrite: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise InstallError(f"Target already exists; pass --overwrite to replace it: {target}")
    shutil.copy2(source, target)


def _manifest_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("T", "_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install a NinjaScript strategy into the compile loop and NT8 folder.")
    parser.add_argument("--source", required=True, help="Generated or repaired .cs file.")
    parser.add_argument("--compile-root", default=str(DEFAULT_COMPILE_LOOP_ROOT), help="Compile-loop root folder.")
    parser.add_argument(
        "--nt-documents-dir",
        default=str(DEFAULT_NT_DOCUMENTS),
        help="NinjaTrader Documents folder.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing NinjaTrader strategy file.")
    parser.add_argument("--iteration-id", default="", help="Optional Iteration Lab id or external id.")
    parser.add_argument("--notes", default="", help="Optional manifest note.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = install_strategy_file(
        args.source,
        compile_root=args.compile_root,
        nt_documents_dir=args.nt_documents_dir,
        overwrite=args.overwrite,
        iteration_id=args.iteration_id,
        notes=args.notes,
    )
    print(json.dumps(manifest.as_serializable_dict(), indent=2))


if __name__ == "__main__":
    main()
