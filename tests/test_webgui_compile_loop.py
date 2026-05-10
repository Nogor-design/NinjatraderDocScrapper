from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from webgui_server import compile_loop_install_payload, compile_loop_status, load_compiler_errors_csv


class WebGuiCompileLoopTests(unittest.TestCase):
    def test_load_compiler_errors_csv_returns_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "errors.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["File", "Message", "Code", "Line", "Column"])
                writer.writeheader()
                writer.writerow(
                    {
                        "File": "Demo.cs",
                        "Message": "The name Foo does not exist",
                        "Code": "CS0103",
                        "Line": "7",
                        "Column": "13",
                    }
                )

            loaded = load_compiler_errors_csv(str(path))

            self.assertEqual(loaded["count"], 1)
            self.assertEqual(len(loaded["signature"]), 64)
            self.assertIn("Demo.cs(7,13) CS0103", loaded["text"])

    def test_compile_loop_status_reports_latest_manifest_and_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "loop"
            nt_docs = Path(tmp) / "ntdocs"
            source = Path(tmp) / "DemoStrategy.cs"
            source.write_text("class DemoStrategy {}\n", encoding="utf-8")

            compile_loop_install_payload(
                {
                    "source": str(source),
                    "compile_root": str(root),
                    "nt_documents_dir": str(nt_docs),
                    "overwrite": False,
                    "iteration_id": "99",
                }
            )
            errors_dir = root / "compiler_errors"
            error_file = errors_dir / "errors.csv"
            with error_file.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["File", "Error", "Code", "Line", "Column"])
                writer.writeheader()
                writer.writerow({"File": "DemoStrategy.cs", "Error": "; expected", "Code": "CS1002", "Line": "2", "Column": "1"})

            status = compile_loop_status(str(root), "*.csv")

            self.assertEqual(status["latest_manifest"]["iteration_id"], "99")
            self.assertEqual(status["latest_errors"]["count"], 1)
            self.assertEqual(status["latest_errors"]["errors"][0]["code"], "CS1002")


if __name__ == "__main__":
    unittest.main()
