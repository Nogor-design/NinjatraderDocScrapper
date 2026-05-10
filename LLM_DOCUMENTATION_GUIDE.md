# NinjaTrader LLM Documentation Guide

This document instructs Large Language Models (LLMs) on how to effectively interpret and utilize the documentation and codebase context provided via the project's Retrieval-Augmented Generation (RAG) system.

## 1. Context Sources Overview

When generating or modifying NinjaScript, you will be provided with context from two primary sources:
1.  **Official NinjaTrader Documentation:** Chunks of the official web documentation.
2.  **Local Strategy Factory Context:** Internal project guidelines, templates, and pre-built modules.

You must synthesize both sources. If the local context provides a specific "Module Card" or "Skeleton", it takes precedence for architectural design, while the Official Documentation governs the exact API signatures and built-in methods.

## 2. Utilizing Official NinjaTrader Documentation

You will receive snippets of the official documentation. Follow these strict rules:

*   **Zero Hallucination:** Use **only** the APIs, methods, properties, and enumerations explicitly supported by the retrieved documentation. If a needed API is missing from your context, state what is missing instead of guessing its signature.
*   **Exact Naming:** Use documented property names exactly as they appear (e.g., `RealtimeErrorHandling.StopCancelClose`, `IsInstantiatedOnEachOptimizationIteration`).
*   **Optimization Specifics:** When tasked with building or modifying Optimization logic (such as custom fitness functions), you must prioritize documentation from **References Optimizer** and **References Optimization Fitness**. If this specific documentation is not in your retrieved context, you must alert the user or formulate a query to retrieve it before attempting to generate optimization code.
*   **Built-in Indicators:** Use the documented overloads (e.g., `CrossAbove(series1, series2, lookBack)`). Ensure you include `using NinjaTrader.NinjaScript.Indicators;` when using built-ins like EMA, SMA, RSI, etc.

## 3. Utilizing Local Strategy Factory Context

The Strategy Factory contains reusable patterns and historical artifacts. When provided, adhere to them strictly:

*   **Module Cards (`strategy_factory/modules/`):** These define pre-approved logic patterns (e.g., risk management lockouts, specific exit strategies). 
    *   *Source Pattern:* Follow the structural approach described.
    *   *Generator Contract:* Ensure your generated code fulfills the required inputs/outputs and state variables.
    *   *Preferred Shape:* Use the exact C# syntax patterns shown in the module card.
*   **Skeletons (`strategy_factory/skeletons/`):** Use these as the foundational boilerplate. Do not invent your own structure or add decorative boilerplate.
*   **Examples & Artifacts:** Use `spec_example` JSON files and `known_good_code` as authoritative examples of how the final output should look and function.

## 4. Core NinjaScript Coding Rules

Regardless of the specific task, all generated NinjaScript must adhere to these project-wide rules:

*   **Lifecycle Management:**
    *   Use `OnStateChange` for all lifecycle setup.
    *   `State.SetDefaults`: Use **only** for default values and UI-facing properties.
    *   `State.Configure`: Use for `AddDataSeries` calls. Do not call `AddDataSeries` unless explicitly required for multi-timeframe/instrument logic.
    *   `State.DataLoaded`: Create indicator instances and bars-dependent resources here (unless specific docs state otherwise).
*   **Data Series Safety:** Always guard `BarsInProgress` and `CurrentBar` (or `CurrentBars`) when processing multiple series.
*   **Properties & Parameters:**
    *   Use `[NinjaScriptProperty]` and `[Display(...)]` for user-editable parameters. Do not invent helper APIs (like `AddEntryFilter`).
    *   Keep discrete settings (bar periods, lengths, tick counts) as `int` unless docs explicitly show a different type.
*   **Risk & Exits:** 
    *   When revising existing code, **preserve existing risk guards** unless explicitly instructed to change them.
    *   Do not mix managed `SetStopLoss`/`SetProfitTarget` exits with explicit stop/target orders unless the existing strategy already does and the repair requires preserving that design.
*   **Compiler Errors:** When provided with compiler errors, fix them directly and provide a brief explanation of the likely root cause before supplying the corrected code.
*   **Completeness:** Always return a complete, compilable class, never a fragment.
