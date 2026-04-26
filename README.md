# NinjaTrader Docs RAG Plan

The best first version is RAG, not fine-tuning. Fine-tuning teaches style and repeated patterns, but it is a poor way to keep a model current with API docs. Use RAG for current NinjaTrader documentation, then add compile feedback from NinjaTrader as a second correction loop.

## Recommended Workflow

1. Scrape the official NinjaTrader Desktop SDK docs:

   ```powershell
   .\.venv\Scripts\python.exe .\scrape_ninjatrader_desktop_docs.py --output .\ninjatrader_docs
   ```

2. Build a local vector index from `ninjatrader_docs\chunks.jsonl`.

   Good Ollama embedding choices:

   - `nomic-embed-text` as the default for this corpus. It is more tolerant of longer documentation chunks.
   - `mxbai-embed-large` if you later re-chunk more aggressively and want to compare retrieval quality.

   Build the local SQLite index:

   ```powershell
   .\.venv\Scripts\python.exe .\build_ollama_index.py --chunks .\ninjatrader_docs\chunks.jsonl --db .\ninjatrader_docs\rag_index.sqlite --embed-model nomic-embed-text --reset
   ```

3. Use a strong coding model in Ollama.

   Good starting points:

   - `qwen3-coder:30b` if your machine can run it. It has a large context window and is designed for code-agent workflows.
   - `qwen2.5-coder:14b` or `qwen2.5-coder:32b` if those run better on your hardware.
   - `deepseek-coder-v2:16b` as another strong code-focused option.

4. At generation time, retrieve 6-12 relevant chunks and force the model to cite the docs it used before writing code.

   Generate NinjaScript from the local index:

   ```powershell
   .\.venv\Scripts\python.exe .\generate_ninjascript.py --db .\ninjatrader_docs\rag_index.sqlite --model qwen3-coder:30b --embed-model nomic-embed-text --task "Create a NinjaTrader 8 strategy that enters long when EMA(9) crosses above EMA(21), enters short on the opposite cross, uses a 20 tick stop loss, 40 tick profit target, and only trades between 8:30 AM and 11:30 AM Central."
   ```

   Write the generated NinjaScript directly to a `.cs` file:

   ```powershell
   .\.venv\Scripts\python.exe .\generate_ninjascript.py --db .\ninjatrader_docs\rag_index.sqlite --model qwen3-coder:30b --embed-model nomic-embed-text --task "Create a NinjaTrader 8 EMA crossover strategy with stop loss and profit target." -outpfile .\MyCoolStrat.cs
   ```

   Repair code with compiler feedback:

   ```powershell
   .\.venv\Scripts\python.exe .\generate_ninjascript.py --db .\ninjatrader_docs\rag_index.sqlite --model qwen3-coder:30b --embed-model nomic-embed-text --task "Fix this NinjaTrader strategy so it compiles and preserves the original behavior." --existing-code-file .\MyStrategy.cs --compiler-errors-file .\compile_errors.txt -outpfile .\MyStrategy.fixed.cs --output .\fixed_strategy.md
   ```

5. Put the generated `.cs` file into the correct NinjaTrader folder and compile inside NinjaTrader.

6. Feed compiler errors back into the model along with the generated code and the retrieved documentation chunks. This gives you a practical repair loop even though the model cannot compile NinjaScript directly.

## Web GUI

For iterative review, use the local web GUI:

```powershell
.\.venv\Scripts\python.exe .\webgui_server.py --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The GUI is designed for the workflow that matters here:

- keep a continuing session for one strategy
- paste compiler errors back into the same thread
- load compiler errors directly from NinjaTrader's CSV output
- point the GUI at a compiler-output folder and discover the newest CSV automatically
- repair directly from the newest compiler CSV in that folder
- optionally auto-watch the folder so fresh compiler errors appear without retyping paths
- trigger a repair pass straight from the compiler CSV
- save generated code directly to a `.cs` path
- compare two iterations with a code diff
- mark an iteration as `good` or `bad`
- store review artifacts under `iteration_artifacts\good\...` or `iteration_artifacts\bad\...`
- export labeled data into `training_exports\export_...\good_sft.jsonl` and `review_corpus.jsonl`

## Prompt Contract

Use a fixed system prompt for NinjaScript generation:

```text
You are writing NinjaTrader 8 NinjaScript C#.
Use only APIs supported by the retrieved NinjaTrader documentation.
Before code, list the retrieved docs you relied on.
When writing indicators or strategies:
- Use OnStateChange for lifecycle setup.
- Use State.SetDefaults only for defaults and UI-facing properties.
- Use State.Configure for AddDataSeries calls.
- Create indicators and other bars-dependent resources in State.DataLoaded.
- Guard BarsInProgress and CurrentBar/CurrentBars when using series.
- Do not invent NinjaTrader methods, properties, namespaces, or enum values.
- If the docs do not prove an API exists, say what is missing instead of guessing.
Return a complete compilable class, not a fragment.
```

## When Fine-Tuning Helps

Fine-tune only after the RAG loop is working. Use it for formatting preferences, common strategy skeletons, and examples that already compile. Do not fine-tune on scraped docs as if they were training data; keep docs in retrieval so they can be refreshed.

Good fine-tuning examples look like:

```jsonl
{"messages":[{"role":"user","content":"Create a NinjaTrader 8 EMA crossover strategy with stop loss and profit target."},{"role":"assistant","content":"<known-good compiling NinjaScript code>"}]}
```

## Full Scrape Notes

The scraper discovers the modern docs from `https://developer.ninjatrader.com/docs/desktop`, renders pages with Playwright, and writes:

- `pages\*.md`: readable Markdown pages.
- `manifest.jsonl`: one record per scraped page.
- `chunks.jsonl`: retrieval chunks with title, URL, section, parent, and text.
- `docs_index.json`: the discovered documentation index.
- `rag_index.sqlite`: local embedding index after running `build_ollama_index.py`.

For a small test run:

```powershell
.\.venv\Scripts\python.exe .\scrape_ninjatrader_desktop_docs.py --limit 10 --output .\ninjatrader_docs_test
```

For focused strategy and indicator material:

```powershell
.\.venv\Scripts\python.exe .\scrape_ninjatrader_desktop_docs.py --include "strategy|indicator|onbarupdate|adddataseries|order|position|managed|unmanaged" --output .\ninjatrader_docs_focus
```

## New Scripts

- `scrape_ninjatrader_desktop_docs.py`
  Scrapes the hydrated NinjaTrader Desktop SDK docs into Markdown and JSONL chunks.
- `build_ollama_index.py`
  Reads `chunks.jsonl`, requests embeddings from Ollama, and stores normalized vectors in SQLite.
- `generate_ninjascript.py`
  Embeds your task, retrieves the most relevant documentation chunks, and sends a constrained NinjaScript prompt to Ollama.
- `chat_ninjascript.py`
  Starts a continuing terminal chat backed by the same local NinjaTrader RAG index. Use `:save MyCoolStrat.cs` to save the latest code block.
- `webgui_server.py`
  Runs a local browser-based review UI with sessions, compiler-error feedback, direct file saves, and good/bad labeling.
- `ollama_rag.py`
  Shared helpers for Ollama HTTP calls, vector normalization, SQLite access, and source formatting.
