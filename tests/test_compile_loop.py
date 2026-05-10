from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from strategy_factory.compile_loop.errors import (
    find_latest_compiler_error_file,
    normalize_compiler_errors,
    parse_compiler_errors_text,
)
from strategy_factory.compile_loop.installer import file_sha256, install_strategy_file
from strategy_factory.compile_loop.paths import ensure_compile_loop
from strategy_factory.install_ninjatrader_outputs import InstallError


class CompileLoopTests(unittest.TestCase):
    def test_ensure_compile_loop_creates_folder_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = ensure_compile_loop(tmp)

            self.assertTrue(paths.staging.is_dir())
            self.assertTrue(paths.installed.is_dir())
            self.assertTrue(paths.compiler_errors.is_dir())
            self.assertTrue(paths.iterations.is_dir())
            self.assertTrue(paths.final.is_dir())
            self.assertTrue(paths.logs.is_dir())

    def test_install_strategy_file_copies_to_staging_target_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "GeneratedStrategy.cs"
            source.write_text("namespace NinjaTrader.NinjaScript.Strategies { public class GeneratedStrategy {} }\n")
            nt_docs = root / "ntdocs"
            compile_root = root / "loop"

            manifest = install_strategy_file(
                source,
                compile_root=compile_root,
                nt_documents_dir=nt_docs,
                iteration_id="42",
                notes="smoke",
            )

            self.assertTrue(Path(manifest.staging_path).is_file())
            self.assertTrue(Path(manifest.target_path).is_file())
            self.assertTrue(Path(manifest.manifest_path).is_file())
            self.assertEqual(manifest.sha256, file_sha256(source))
            self.assertEqual(manifest.iteration_id, "42")

            payload = json.loads(Path(manifest.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["target_path"], manifest.target_path)

    def test_install_strategy_file_refuses_target_overwrite_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "GeneratedStrategy.cs"
            source.write_text("class A {}\n")
            nt_docs = root / "ntdocs"
            target = nt_docs / "bin" / "Custom" / "Strategies" / source.name
            target.parent.mkdir(parents=True)
            target.write_text("existing\n")

            with self.assertRaises(InstallError):
                install_strategy_file(source, compile_root=root / "loop", nt_documents_dir=nt_docs)

    def test_normalize_compiler_errors_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "errors.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["NinjaScript File", "Error", "Code", "Line", "Column"])
                writer.writeheader()
                writer.writerow(
                    {
                        "NinjaScript File": "GeneratedStrategy.cs",
                        "Error": "The name Foo does not exist in the current context",
                        "Code": "CS0103",
                        "Line": "12",
                        "Column": "9",
                    }
                )

            bundle = normalize_compiler_errors(path)

            self.assertEqual(bundle.count, 1)
            self.assertEqual(bundle.errors[0].file, "GeneratedStrategy.cs")
            self.assertEqual(bundle.errors[0].line, 12)
            self.assertEqual(bundle.errors[0].column, 9)
            self.assertEqual(bundle.errors[0].code, "CS0103")
            self.assertIn("GeneratedStrategy.cs(12,9) CS0103", bundle.text)
            self.assertEqual(len(bundle.signature), 64)

    def test_normalize_compiler_errors_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "errors.txt"
            path.write_text("GeneratedStrategy.cs(22,15) CS1002: ; expected\n", encoding="utf-8")

            errors = parse_compiler_errors_text(path)

            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].file, "GeneratedStrategy.cs")
            self.assertEqual(errors[0].line, 22)
            self.assertEqual(errors[0].column, 15)
            self.assertEqual(errors[0].code, "CS1002")

    def test_find_latest_compiler_error_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.csv"
            second = root / "second.csv"
            first.write_text("a\n", encoding="utf-8")
            second.write_text("b\n", encoding="utf-8")
            second.touch()

            self.assertEqual(find_latest_compiler_error_file(root, "*.csv"), second)


if __name__ == "__main__":
    unittest.main()
