"""Output helpers for CLI commands."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping


def _coerce_mapping(item: Any) -> Mapping[str, Any]:
    if isinstance(item, Mapping):
        return item
    if hasattr(item, "_asdict"):
        return item._asdict()
    if hasattr(item, "__dict__"):
        return vars(item)
    return {"value": item}


def _render_markdown(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, Mapping):
        rows = [f"- **{key}**: {value}" for key, value in data.items()]
        return "\n".join(rows)
    if isinstance(data, Iterable):
        lines = []
        for item in data:
            mapping = _coerce_mapping(item)
            summary = ", ".join(f"{k}={v}" for k, v in mapping.items())
            lines.append(f"- {summary}")
        return "\n".join(lines)
    return str(data)


def _render_plain(data: Any) -> str:
    if isinstance(data, (str, bytes)):
        return data if isinstance(data, str) else data.decode()
    if isinstance(data, Iterable) and not isinstance(data, Mapping):
        return "\n".join(_render_plain(item) for item in data)
    return json.dumps(data, ensure_ascii=False)


def render_output(data: Any, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if fmt == "markdown":
        return _render_markdown(data)
    return _render_plain(data)
