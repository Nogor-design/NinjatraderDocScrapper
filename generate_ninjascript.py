import argparse
import re
from pathlib import Path

from ollama_rag import (
    DEFAULT_OLLAMA_URL,
    dot,
    format_source_list,
    load_all_index_rows,
    normalize,
    ollama_chat,
    ollama_embed,
)
from strategy_factory.retrieval import format_retrieval_context, retrieve_local_context
from strategy_factory.review import review_strategy_code, review_to_markdown


SYSTEM_PROMPT = """You are writing NinjaTrader 8 NinjaScript C#.
Use only APIs that are supported by the retrieved NinjaTrader documentation.
Refer to LLM_DOCUMENTATION_GUIDE.md for detailed architectural and coding standards.
Before the code, briefly list the documentation pages you relied on.

When writing indicators or strategies:
- Use OnStateChange for lifecycle setup.
- Use State.SetDefaults only for defaults and UI-facing properties.
- Use State.Configure for AddDataSeries calls.
- Create indicator instances and other bars-dependent resources in State.DataLoaded unless the documentation for a specific API requires otherwise.
- For Optimization tasks (e.g. custom fitness), prioritize 'References Optimizer' and 'References Optimization Fitness' documentation.
- Prefer a minimal NinjaTrader strategy skeleton over decorative boilerplate.
- When using built-in indicators such as EMA, SMA, RSI, or ATR, include `using NinjaTrader.NinjaScript.Indicators;`.
- For user-editable strategy parameters, prefer `[NinjaScriptProperty]` plus `[Display(...)]`. Do not invent helper APIs such as `AddEntryFilter` or types such as `NinjaScriptParameterType`.
- Keep bar periods, indicator lengths, tick counts, and similar discrete settings as `int` unless the docs clearly show a different type.
- Use the documented overloads for `CrossAbove` and `CrossBelow`, typically `CrossAbove(series1, series2, lookBack)` and `CrossBelow(series1, series2, lookBack)`.
- Use documented property names exactly, for example `RealtimeErrorHandling.StopCancelClose` and `IsInstantiatedOnEachOptimizationIteration`.
- Do not call `AddDataSeries()` unless the task explicitly needs multiple time frames or instruments.
- Guard BarsInProgress and CurrentBar or CurrentBars when using extra series.
- Do not invent NinjaTrader methods, properties, namespaces, or enum values.
- If the documentation does not prove an API exists, say what is missing instead of guessing.
- Return a complete class, not a fragment.
- When revising existing code, preserve existing risk guards unless the user explicitly asks to change them.
- Do not mix managed SetStopLoss/SetProfitTarget exits with explicit stop/target orders unless the existing strategy already does and the repair requires preserving that design.
When compiler errors are supplied, fix them directly and explain the likely root cause briefly before the corrected code.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve NinjaTrader docs from a local Ollama-backed index and generate NinjaScript."
    )
    parser.add_argument("--db", default="ninjatrader_docs\\rag_index.sqlite", help="SQLite index path.")
    parser.add_argument("--model", default="qwen3-coder:30b", help="Ollama generation model.")
    parser.add_argument("--embed-model", default="nomic-embed-text", help="Embedding model used for retrieval.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL.")
    parser.add_argument("--task", default="", help="Prompt describing the indicator or strategy to build.")
    parser.add_argument("--task-file", default="", help="Optional text file containing the task.")
    parser.add_argument("--existing-code-file", default="", help="Optional NinjaScript file to revise.")
    parser.add_argument("--compiler-errors-file", default="", help="Optional compile error text.")
    parser.add_argument("--top-k", type=int, default=8, help="How many chunks to retrieve.")
    parser.add_argument("--local-top-k", type=int, default=6, help="How many local module/example documents to include.")
    parser.add_argument("--temperature", type=float, default=0.1, help="Generation temperature.")
    parser.add_argument("--output", default="", help="Optional file path for the generated answer.")
    parser.add_argument(
        "--out-file",
        "--outfile",
        "-outpfile",
        dest="out_file",
        default="",
        help="Optional file path for the generated code. If the path ends in .cs, save only the C# code block.",
    )
    return parser.parse_args()


def read_optional(path_value: str) -> str:
    if not path_value:
        return ""
    return Path(path_value).read_text(encoding="utf-8")


def build_task(args: argparse.Namespace) -> str:
    task = args.task.strip()
    if args.task_file:
        task = read_optional(args.task_file).strip()
    if not task:
        raise SystemExit("Provide --task or --task-file.")
    return task


def retrieve(args: argparse.Namespace, query_text: str) -> list[dict]:
    query_vector = normalize(ollama_embed(args.ollama_url, args.embed_model, query_text))
    rows = load_all_index_rows(args.db)
    if not rows:
        raise SystemExit(f"No indexed chunks found in {args.db}")

    scored = []
    for row in rows:
        score = dot(query_vector, row["vector"])
        scored.append({**row, "score": score})

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: args.top_k]


def build_user_prompt(
    task: str,
    results: list[dict],
    existing_code: str,
    compiler_errors: str,
    *,
    local_context: str = "",
    code_review: str = "",
) -> str:
    parts = [
        f"Task:\n{task}",
    ]

    if code_review.strip():
        parts.append(f"Static review of existing code:\n{code_review.strip()}")

    if local_context.strip():
        parts.append(f"Local Strategy Factory context:\n{local_context.strip()}")

    parts.extend(
        [
            f"Retrieved documentation sources:\n{format_source_list(results)}",
            "Retrieved documentation content:",
        ]
    )

    for index, item in enumerate(results, start=1):
        parts.append(
            "\n".join(
                [
                    f"[Source {index}] {item['title']}",
                    f"URL: {item['url']}",
                    item["text"],
                ]
            )
        )

    if existing_code.strip():
        parts.append(f"Existing NinjaScript code to revise:\n```csharp\n{existing_code.strip()}\n```")

    if compiler_errors.strip():
        parts.append(f"NinjaTrader compiler errors:\n```text\n{compiler_errors.strip()}\n```")

    return "\n\n".join(parts)


def extract_code_block(answer: str) -> str:
    match = re.search(r"```(?:csharp|cs|c#)?\s*\n(.*?)```", answer, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    return answer.strip() + "\n"


def build_local_context(query_text: str, *, top_k: int = 6) -> str:
    documents = retrieve_local_context(query_text, top_k=top_k)
    return format_retrieval_context(documents)


def build_code_review(existing_code: str, *, path: str = "") -> str:
    if not existing_code.strip():
        return ""
    return review_to_markdown(review_strategy_code(existing_code, path=path or "(existing code)"))


def main() -> None:
    args = parse_args()
    task = build_task(args)
    existing_code = read_optional(args.existing_code_file)
    compiler_errors = read_optional(args.compiler_errors_file)

    query_text = "\n\n".join(
        part for part in [task, existing_code[:3000], compiler_errors[:3000]] if part.strip()
    )
    results = retrieve(args, query_text)
    prompt = build_user_prompt(
        task,
        results,
        existing_code,
        compiler_errors,
        local_context=build_local_context(query_text, top_k=args.local_top_k),
        code_review=build_code_review(existing_code, path=args.existing_code_file),
    )

    answer = ollama_chat(
        args.ollama_url,
        args.model,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=args.temperature,
    )

    if args.out_file:
        out_path = Path(args.out_file)
        if out_path.suffix.lower() == ".cs":
            out_path.write_text(extract_code_block(answer), encoding="utf-8")
        else:
            out_path.write_text(answer, encoding="utf-8")
        print(f"Saved code output to {args.out_file}")
    else:
        print(answer)

    if args.output:
        Path(args.output).write_text(answer, encoding="utf-8")
        print(f"\nSaved output to {args.output}")


if __name__ == "__main__":
    main()
