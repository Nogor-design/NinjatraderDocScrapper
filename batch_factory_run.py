from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategy_factory.factory import build_strategy_outputs
from strategy_factory.install_ninjatrader_outputs import DEFAULT_NT_DOCUMENTS, install_outputs


def batch_process_specs(
    input_folder: str | Path,
    output_base_dir: str | Path,
    nt_documents_dir: str | Path = DEFAULT_NT_DOCUMENTS,
    overwrite: bool = False,
) -> list[dict]:
    input_path = Path(input_folder)
    base_out = Path(output_base_dir)
    results = []

    if not input_path.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {input_path}")

    spec_files = list(input_path.glob("*.json"))
    print(f"Found {len(spec_files)} strategy specs in {input_path}")

    for spec_file in spec_files:
        try:
            print(f"Processing: {spec_file.name}")
            # Load spec to get strategy ID
            spec_data = json.loads(spec_file.read_text(encoding="utf-8"))
            strategy_id = spec_data.get("strategy", {}).get("id", spec_file.stem)
            
            # Generate outputs
            strategy_out_dir = base_out / strategy_id
            outputs = build_strategy_outputs(spec_file, strategy_out_dir)
            
            # Install to NinjaTrader
            installed = install_outputs(
                ninjascript_path=outputs["ninjascript"],
                template_path=outputs["ninjascript_template"],
                strategy_name=strategy_id,
                nt_documents_dir=nt_documents_dir,
                overwrite=overwrite
            )
            
            results.append({
                "spec": str(spec_file),
                "strategy_id": strategy_id,
                "status": "success",
                "installed": {k: str(v) for k, v in installed.items()}
            })
            print(f"  Successfully installed {strategy_id}")
            
        except Exception as exc:
            print(f"  Error processing {spec_file.name}: {exc}")
            results.append({
                "spec": str(spec_file),
                "status": "error",
                "error": str(exc)
            })

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch process strategy specs: generate outputs and install to NinjaTrader.")
    parser.add_argument("--input", required=True, help="Folder containing .json strategy specs.")
    parser.add_argument("--out-dir", required=True, help="Base directory for generated strategy outputs.")
    parser.add_argument(
        "--nt-documents-dir",
        default=str(DEFAULT_NT_DOCUMENTS),
        help="NinjaTrader documents folder.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace existing files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = batch_process_specs(
        input_folder=args.input,
        output_base_dir=args.out_dir,
        nt_documents_dir=args.nt_documents_dir,
        overwrite=args.overwrite
    )
    
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\nBatch processing complete. Success: {success_count}/{len(results)}")
    
    report_path = Path(args.out_dir) / "batch_report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Detailed report saved to {report_path}")


if __name__ == "__main__":
    main()
