from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


TEXT_ERROR_RE = re.compile(
    r"^(?P<file>.*?)(?:\((?P<line>\d+)\s*,\s*(?P<column>\d+)\))?\s*"
    r"(?P<code>CS\d{4})\s*:\s*(?P<message>.+)$"
)


@dataclass(frozen=True)
class CompilerError:
    file: str
    line: int | None
    column: int | None
    code: str
    message: str
    raw: str
    source: str = ""

    def formatted(self) -> str:
        location = self.file
        if self.line is not None or self.column is not None:
            location += f"({self.line or 0},{self.column or 0})"
        return f"{location} {self.code}: {self.message}".strip()


@dataclass(frozen=True)
class CompilerErrorBundle:
    path: str
    parsed_at: str
    count: int
    signature: str
    errors: list[CompilerError]
    text: str

    def as_serializable_dict(self) -> dict:
        payload = asdict(self)
        payload["errors"] = [asdict(error) for error in self.errors]
        return payload


def normalize_compiler_errors(path: str | Path) -> CompilerErrorBundle:
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Compiler error file not found: {source_path}")
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        errors = parse_compiler_errors_csv(source_path)
    else:
        errors = parse_compiler_errors_text(source_path)
    return build_error_bundle(source_path, errors)


def parse_compiler_errors_csv(path: str | Path) -> list[CompilerError]:
    source_path = Path(path)
    errors: list[CompilerError] = []
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not any((value or "").strip() for value in row.values()):
                continue
            raw = _csv_raw_text(row)
            errors.append(
                CompilerError(
                    file=_first_present(row, ["NinjaScript File", "File", "Filename", "Source", "Path"]),
                    line=_int_or_none(_first_present(row, ["Line", "Line Number"])),
                    column=_int_or_none(_first_present(row, ["Column", "Column Number"])),
                    code=_first_present(row, ["Code", "Error Code"]),
                    message=_first_present(row, ["Error", "Message", "Description"]),
                    raw=raw,
                    source=str(source_path),
                )
            )
    return errors


def parse_compiler_errors_text(path: str | Path) -> list[CompilerError]:
    source_path = Path(path)
    errors: list[CompilerError] = []
    for raw in source_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = TEXT_ERROR_RE.match(line)
        if match:
            errors.append(
                CompilerError(
                    file=(match.group("file") or "").strip(),
                    line=_int_or_none(match.group("line")),
                    column=_int_or_none(match.group("column")),
                    code=match.group("code"),
                    message=match.group("message").strip(),
                    raw=line,
                    source=str(source_path),
                )
            )
        else:
            errors.append(
                CompilerError(
                    file="",
                    line=None,
                    column=None,
                    code="",
                    message=line,
                    raw=line,
                    source=str(source_path),
                )
            )
    return errors


def build_error_bundle(path: str | Path, errors: Iterable[CompilerError]) -> CompilerErrorBundle:
    items = list(errors)
    text = "\n".join(error.formatted() for error in items)
    return CompilerErrorBundle(
        path=str(Path(path)),
        parsed_at=datetime.now().isoformat(timespec="seconds"),
        count=len(items),
        signature=compiler_error_signature(items),
        errors=items,
        text=text,
    )


def compiler_error_signature(errors: Iterable[CompilerError]) -> str:
    normalized = "\n".join(
        "|".join(
            [
                error.file.lower(),
                "" if error.line is None else str(error.line),
                "" if error.column is None else str(error.column),
                error.code,
                error.message.strip(),
            ]
        )
        for error in errors
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_latest_compiler_error_file(folder: str | Path, pattern: str = "*.csv") -> Path:
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"Compiler error folder is not a directory: {root}")
    candidates = [path for path in root.rglob(pattern or "*.csv") if path.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No compiler error files matched {pattern!r} in {root}")
    return max(candidates, key=lambda item: (item.stat().st_mtime, str(item).lower()))


def _first_present(row: dict[str, str], keys: list[str]) -> str:
    lower_map = {key.lower(): value for key, value in row.items()}
    for key in keys:
        value = row.get(key)
        if value is None:
            value = lower_map.get(key.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _csv_raw_text(row: dict[str, str]) -> str:
    return " | ".join(f"{key}={value}" for key, value in row.items() if str(value or "").strip())


def _int_or_none(value: str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(float(str(value).strip()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize NinjaTrader compiler errors.")
    parser.add_argument("--path", default="", help="CSV or text compiler-error file.")
    parser.add_argument("--latest-folder", default="", help="Find the newest compiler-error file in this folder.")
    parser.add_argument("--pattern", default="*.csv", help="Pattern used with --latest-folder.")
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.path) if args.path else find_latest_compiler_error_file(args.latest_folder, args.pattern)
    bundle = normalize_compiler_errors(path)
    payload = bundle.as_serializable_dict()
    text = json.dumps(payload, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"Saved normalized compiler errors to {out_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
