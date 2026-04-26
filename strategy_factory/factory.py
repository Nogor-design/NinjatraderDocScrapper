from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategy_factory.generators.ninjascript_generator import generate_ninjascript_strategy
from strategy_factory.generators.ninjascript_template_generator import generate_ninjascript_template_xml
from strategy_factory.generators.python_template_generator import generate_ta_foundation_template
from strategy_factory.specs.validator import load_strategy_spec


def build_strategy_outputs(spec_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
    """Generate all currently supported strategy targets from one canonical spec."""
    spec = load_strategy_spec(spec_path)
    strategy_id = spec["strategy"]["id"]
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    normalized_spec_path = out_dir / f"{strategy_id}.strategy_spec.normalized.json"
    python_template_path = out_dir / f"{strategy_id}.ta_template.json"
    ninjascript_path = out_dir / f"{strategy_id}.cs"
    ninjascript_template_path = out_dir / f"{strategy_id}Template.xml"

    normalized_spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    python_template_path.write_text(
        json.dumps(generate_ta_foundation_template(spec), indent=2) + "\n",
        encoding="utf-8",
    )
    ninjascript_path.write_text(generate_ninjascript_strategy(spec), encoding="utf-8")
    ninjascript_template_path.write_text(generate_ninjascript_template_xml(spec), encoding="utf-8")

    manifest = {
        "strategy_id": strategy_id,
        "source_spec": str(Path(spec_path)),
        "outputs": {
            "normalized_spec": str(normalized_spec_path),
            "ta_foundation_template": str(python_template_path),
            "ninjascript": str(ninjascript_path),
            "ninjascript_template": str(ninjascript_template_path),
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "manifest": manifest_path,
        "normalized_spec": normalized_spec_path,
        "ta_foundation_template": python_template_path,
        "ninjascript": ninjascript_path,
        "ninjascript_template": ninjascript_template_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build all supported outputs from a canonical strategy spec.")
    parser.add_argument("--spec", required=True, help="Path to canonical Strategy Factory spec JSON.")
    parser.add_argument("--out-dir", required=True, help="Directory for generated outputs and manifest.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = build_strategy_outputs(args.spec, args.out_dir)
    print("Generated strategy outputs:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
