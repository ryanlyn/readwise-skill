from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
READWISE_PROJECT = REPO_ROOT / "plugins/readwise"
READWISE_CLI = REPO_ROOT / "plugins/readwise/skills/readwise/scripts/readwise_client.py"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
READWISE_MCP_HIGHLIGHTS_URL = "https://readwise.io/api/mcp/highlights"


@dataclass(slots=True)
class Scenario:
    scenario_id: str
    prompt: str


class TokenCounter:
    def __init__(self, model: str):
        self._mode = "approx"
        self._encoder = None
        try:
            import tiktoken  # type: ignore

            try:
                self._encoder = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoder = tiktoken.get_encoding("o200k_base")
            self._mode = "tiktoken"
        except Exception:
            self._mode = "approx"

    @property
    def mode(self) -> str:
        return self._mode

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        return max(1, len(text) // 4)


def _json_post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int = 60) -> dict[str, Any]:
    retryable_codes = {408, 409, 429, 500, 502, 503, 504}
    attempt = 0
    last_error: Exception | None = None
    while attempt < 3:
        attempt += 1
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in retryable_codes and attempt < 3:
                time.sleep(1.5 * attempt)
                last_error = RuntimeError(f"HTTP {exc.code} from {url}: {body}")
                continue
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
        except Exception as exc:  # noqa: BLE001
            if attempt < 3:
                time.sleep(1.5 * attempt)
                last_error = exc
                continue
            raise
    raise RuntimeError(f"POST failed after retries: {url}: {last_error}")


def _readwise_token() -> str:
    token = os.getenv("READWISE_API_TOKEN") or os.getenv("READWISE_TOKEN")
    if not token:
        raise RuntimeError("Missing Readwise token. Set READWISE_API_TOKEN or READWISE_TOKEN.")
    return token


def _openai_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY.")
    return key


def _run_readwise_cli(args: list[str]) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.setdefault("READWISE_TOKEN", _readwise_token())
    command = [
        "uv",
        "run",
        "--project",
        str(READWISE_PROJECT),
        "python",
        str(READWISE_CLI),
        *args,
    ]
    result = subprocess.run(command, capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _compact_text(value: Any, max_len: int = 220) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1]}..."


def _render_books_compact(books: list[dict[str, Any]]) -> str:
    if not books:
        return "No books found."
    lines = []
    for book in books:
        lines.append(
            "- "
            f"id={book.get('id')} | "
            f"title={_compact_text(book.get('title'), 80)} | "
            f"author={_compact_text(book.get('author'), 60)} | "
            f"category={book.get('category')} | "
            f"num_highlights={book.get('num_highlights')}"
        )
    return "\n".join(lines)


def _render_highlights_compact(highlights: list[dict[str, Any]], *, limit: int = 20) -> str:
    if not highlights:
        return "No highlights found."
    lines = []
    for item in highlights[:limit]:
        title = item.get("title") or item.get("book_title") or item.get("document_title")
        lines.append(
            "- "
            f"id={item.get('id')} | "
            f"title={_compact_text(title, 70)} | "
            f"text={_compact_text(item.get('text') or item.get('highlighted_at') or item.get('highlight_plaintext'), 180)} | "
            f"note={_compact_text(item.get('note') or item.get('highlight_note'), 100)}"
        )
    if len(highlights) > limit:
        lines.append(f"... ({len(highlights) - limit} more)")
    return "\n".join(lines)


def _skill_books_search(args: dict[str, Any]) -> str:
    title = args.get("title")
    author = args.get("author")
    limit = int(args.get("limit", 10))
    cli_args = ["--raw", "books", "--limit", str(max(1, min(limit, 100)))]
    if title:
        cli_args.extend(["--title", str(title)])
    if author:
        cli_args.extend(["--author", str(author)])
    rc, stdout, stderr = _run_readwise_cli(cli_args)
    if rc != 0:
        return f"ERROR: books search failed (exit={rc})\n{stderr or stdout}"
    try:
        parsed = json.loads(stdout) if stdout else []
    except json.JSONDecodeError:
        return stdout or "No output"
    if not isinstance(parsed, list):
        return json.dumps(parsed, ensure_ascii=False)
    return _render_books_compact(parsed)


def _skill_search_highlights(args: dict[str, Any]) -> str:
    tag = args.get("tag")
    category = args.get("category")
    book_id = args.get("book_id")
    updated_after = args.get("updated_after")
    updated_before = args.get("updated_before")
    keyword = args.get("keyword")
    limit = int(args.get("limit", 50))
    fetch_limit = limit
    if keyword:
        fetch_limit = max(limit, 200)

    cli_args = ["--raw", "highlights", "list", "--limit", str(max(1, min(fetch_limit, 500)))]
    if tag:
        cli_args.extend(["--tag", str(tag)])
    if category:
        cli_args.extend(["--category", str(category)])
    if book_id is not None:
        cli_args.extend(["--book-id", str(book_id)])
    if updated_after:
        cli_args.extend(["--updated-after", str(updated_after)])
    if updated_before:
        cli_args.extend(["--updated-before", str(updated_before)])

    rc, stdout, stderr = _run_readwise_cli(cli_args)
    if rc != 0:
        return f"ERROR: highlight search failed (exit={rc})\n{stderr or stdout}"
    try:
        parsed = json.loads(stdout) if stdout else []
    except json.JSONDecodeError:
        return stdout or "No output"

    if not isinstance(parsed, list):
        return json.dumps(parsed, ensure_ascii=False)

    if keyword:
        key = str(keyword).lower().strip()
        variants = {key}
        if key.endswith("ing") and len(key) > 4:
            variants.add(key[:-3])
            variants.add(f"{key[:-3]}e")
        if key.endswith("s") and len(key) > 3:
            variants.add(key[:-1])

        def _matches(item: dict[str, Any]) -> bool:
            hay = " ".join(
                [
                    str(item.get("text") or ""),
                    str(item.get("note") or ""),
                    str(item.get("title") or ""),
                    str(item.get("author") or ""),
                ]
            ).lower()
            return any(variant and variant in hay for variant in variants)

        parsed = [item for item in parsed if isinstance(item, dict) and _matches(item)]

    return _render_highlights_compact([i for i in parsed if isinstance(i, dict)], limit=min(limit, 40))


def _mcp_search_highlights(args: dict[str, Any]) -> str:
    vector_search_term = str(args.get("vector_search_term", "")).strip()
    full_text_queries = args.get("full_text_queries", [])
    if not isinstance(full_text_queries, list):
        full_text_queries = []
    if not vector_search_term:
        for item in full_text_queries:
            if isinstance(item, dict):
                candidate = str(item.get("search_term", "")).strip()
                if candidate:
                    vector_search_term = candidate
                    break
    if not vector_search_term:
        vector_search_term = "highlights"
    payload = {
        "vector_search_term": vector_search_term,
        "full_text_queries": full_text_queries[:8],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Access-Token": _readwise_token(),
    }
    response = _json_post(READWISE_MCP_HIGHLIGHTS_URL, payload, headers, timeout_seconds=60)
    return json.dumps(response.get("results", []), ensure_ascii=False)


def _skill_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "books_search",
                "description": "Search Readwise books by title/author and return compact rows with ids.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "author": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_highlights",
                "description": (
                    "List highlights with server-side filters. Optionally apply keyword filtering in text/note/title/author. "
                    "Returns compact formatted output."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "book_id": {"type": "integer"},
                        "tag": {"type": "string"},
                        "category": {"type": "string"},
                        "updated_after": {"type": "string", "description": "ISO date/datetime"},
                        "updated_before": {"type": "string", "description": "ISO date/datetime"},
                        "keyword": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                    },
                },
            },
        },
    ]


def _mcp_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_readwise_highlights",
                "description": "Search highlights using Readwise MCP query contract and return raw JSON array text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vector_search_term": {"type": "string"},
                        "full_text_queries": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field_name": {
                                        "type": "string",
                                        "enum": [
                                            "document_author",
                                            "document_title",
                                            "highlight_note",
                                            "highlight_plaintext",
                                            "highlight_tags",
                                        ],
                                    },
                                    "search_term": {"type": "string"},
                                },
                                "required": ["field_name", "search_term"],
                            },
                        },
                    },
                    "required": ["vector_search_term", "full_text_queries"],
                },
            },
        }
    ]


def _system_prompt_for(approach: str) -> str:
    if approach == "skill":
        return (
            "You are executing a benchmark task using Readwise skill tools. "
            "Always call at least one tool before giving a final answer. "
            "Keep the final answer concise and include caveats if data is sparse."
        )
    return (
        "You are executing a benchmark task using the official Readwise MCP tool. "
        "Always call the tool at least once before final answer. "
        "Keep the final answer concise and mention limitations when filters are unsupported."
    )


def _tool_dispatch(approach: str, tool_name: str, tool_args: dict[str, Any]) -> str:
    if approach == "skill":
        if tool_name == "books_search":
            return _skill_books_search(tool_args)
        if tool_name == "search_highlights":
            return _skill_search_highlights(tool_args)
    elif approach == "mcp":
        if tool_name == "search_readwise_highlights":
            return _mcp_search_highlights(tool_args)
    return f"ERROR: unknown tool {tool_name} for approach {approach}"


def _chat_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    temperature: float,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {_openai_key()}",
        "Content-Type": "application/json",
    }
    return _json_post(OPENAI_CHAT_COMPLETIONS_URL, payload, headers, timeout_seconds=90)


def collect_trace(
    *,
    scenario: Scenario,
    approach: str,
    model: str,
    run_index: int,
    max_steps: int = 8,
    temperature: float = 0.0,
) -> dict[str, Any]:
    if approach not in {"skill", "mcp"}:
        raise ValueError(f"Unsupported approach: {approach}")

    token_counter = TokenCounter(model)
    tools = _skill_tools_schema() if approach == "skill" else _mcp_tools_schema()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt_for(approach)},
        {"role": "user", "content": scenario.prompt},
    ]

    tool_records: list[dict[str, Any]] = []
    final_answer = ""

    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    reasoning_tokens = 0
    tool_input_tokens = 0
    tool_output_tokens = 0
    total_turns = 0
    tool_calls_count = 0

    status = "failed"
    error: str | None = None

    for step in range(1, max_steps + 1):
        try:
            response = _chat_completion(model=model, messages=messages, tools=tools, temperature=temperature)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            break

        usage = response.get("usage") or {}
        total_tokens += int(usage.get("total_tokens", 0) or 0)
        prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        completion_details = usage.get("completion_tokens_details") or {}
        reasoning_tokens += int(completion_details.get("reasoning_tokens", 0) or 0)

        choices = response.get("choices") or []
        if not choices:
            error = "No choices returned by model"
            break

        message = choices[0].get("message") or {}
        assistant_content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        assistant_message: dict[str, Any] = {"role": "assistant", "content": assistant_content}
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls
        messages.append(assistant_message)

        if not tool_calls:
            final_answer = assistant_content
            if final_answer.strip() and tool_calls_count > 0:
                status = "success"
            else:
                status = "failed"
            break

        total_turns += 1

        for call in tool_calls:
            tool_calls_count += 1
            call_id = call.get("id") or ""
            fn = (call.get("function") or {}).get("name") or ""
            arg_text = (call.get("function") or {}).get("arguments") or "{}"
            tool_input_tokens += token_counter.count(arg_text)

            try:
                parsed_args = json.loads(arg_text)
                if not isinstance(parsed_args, dict):
                    parsed_args = {}
            except json.JSONDecodeError:
                parsed_args = {}

            try:
                output_text = _tool_dispatch(approach, fn, parsed_args)
            except Exception as exc:  # noqa: BLE001
                output_text = f"ERROR: tool execution failed for {fn}: {exc}"
            tool_output_tokens += token_counter.count(output_text)

            tool_records.append(
                {
                    "step": step,
                    "tool_call_id": call_id,
                    "tool_name": fn,
                    "arguments": parsed_args,
                    "output": output_text,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": output_text,
                }
            )

    else:
        status = "failed"
        if error is None:
            error = f"Reached max_steps={max_steps} before final answer"

    trace = {
        "scenario_id": scenario.scenario_id,
        "prompt": scenario.prompt,
        "approach": approach,
        "run_index": run_index,
        "model": model,
        "status": status,
        "error": error,
        "final_answer": final_answer,
        "token_counter_mode": token_counter.mode,
        "metrics": {
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
            "tool_input_tokens": tool_input_tokens,
            "tool_output_tokens": tool_output_tokens,
            "total_turns": total_turns,
            "tool_calls": tool_calls_count,
        },
        "tool_calls": tool_records,
    }
    return trace
