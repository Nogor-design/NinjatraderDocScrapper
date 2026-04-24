import argparse
from pathlib import Path

from generate_ninjascript import SYSTEM_PROMPT, build_user_prompt, extract_code_block, retrieve
from ollama_rag import DEFAULT_OLLAMA_URL, ollama_chat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive NinjaTrader chat with local RAG retrieval and Ollama."
    )
    parser.add_argument("--db", default="ninjatrader_docs\\rag_index.sqlite", help="SQLite index path.")
    parser.add_argument("--model", default="qwen3-coder:30b", help="Ollama generation model.")
    parser.add_argument("--embed-model", default="nomic-embed-text", help="Embedding model used for retrieval.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL.")
    parser.add_argument("--top-k", type=int, default=8, help="How many chunks to retrieve per turn.")
    parser.add_argument("--temperature", type=float, default=0.1, help="Generation temperature.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    history: list[dict] = []
    last_answer = ""

    print("NinjaTrader chat is ready.")
    print("Commands: :quit, :save path.cs, :savefull path.md")

    while True:
        user_text = input("\nYou> ").strip()
        if not user_text:
            continue

        if user_text in {":quit", ":exit"}:
            break

        if user_text.startswith(":save "):
            if not last_answer:
                print("No answer available to save yet.")
                continue
            out_path = Path(user_text[6:].strip())
            payload = extract_code_block(last_answer) if out_path.suffix.lower() == ".cs" else last_answer
            out_path.write_text(payload, encoding="utf-8")
            print(f"Saved to {out_path}")
            continue

        if user_text.startswith(":savefull "):
            if not last_answer:
                print("No answer available to save yet.")
                continue
            out_path = Path(user_text[10:].strip())
            out_path.write_text(last_answer, encoding="utf-8")
            print(f"Saved full response to {out_path}")
            continue

        query_text = "\n\n".join(
            [message["content"] for message in history[-4:] if message["role"] == "user"] + [user_text]
        )
        results = retrieve(args, query_text)
        rag_message = build_user_prompt(user_text, results, "", "")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": rag_message})

        answer = ollama_chat(
            args.ollama_url,
            args.model,
            messages,
            temperature=args.temperature,
        )

        print(f"\nAssistant>\n{answer}")
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": answer})
        last_answer = answer


if __name__ == "__main__":
    main()
