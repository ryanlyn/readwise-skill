"""Output helpers for CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from readwise_common.schemas import DISPLAY_FIELDS


def _to_plain(data: Any) -> Any:
    """Convert Pydantic models (and lists of them) to plain dicts."""
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, list):
        return [item.model_dump() if isinstance(item, BaseModel) else item for item in data]
    return data


def _is_displayable(value: Any) -> bool:
    return value is not None and value not in ("", [], {})


def _coerce_mapping(item: Any) -> Mapping[str, Any]:
    if isinstance(item, BaseModel):
        return item.model_dump()
    if isinstance(item, Mapping):
        return item
    if hasattr(item, "_asdict"):
        return item._asdict()
    if hasattr(item, "__dict__"):
        return vars(item)
    return {"value": item}


def _format_tags(tags: Any) -> str:
    if not tags:
        return ""
    if isinstance(tags, dict):
        return ", ".join(tags.keys())
    if isinstance(tags, list):
        names = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in tags]
        return ", ".join(names)
    return str(tags)


def render_highlights(highlights: Any) -> str:
    """Render highlights in a reading-optimized format.

    Blockquoted text with note/tags shown only when non-empty.
    """
    if not isinstance(highlights, list) or not highlights:
        return _render_markdown(highlights)

    blocks = []
    for h in highlights:
        if not isinstance(h, dict):
            blocks.append(str(h))
            continue

        text = h.get("text", "")
        lines = [f"> {text}"]

        note = h.get("note")
        if note:
            lines.append(f"  Note: {note}")

        tag_str = _format_tags(h.get("tags"))
        if tag_str:
            lines.append(f"  Tags: {tag_str}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _render_markdown(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, Mapping):
        rows = [f"- **{key}**: {value}" for key, value in data.items() if _is_displayable(value)]
        return "\n".join(rows)
    if isinstance(data, Iterable):
        lines = []
        for item in data:
            mapping = _coerce_mapping(item)
            summary = ", ".join(f"{k}={v}" for k, v in mapping.items() if _is_displayable(v))
            lines.append(f"- {summary}")
        return "\n".join(lines)
    return str(data)


def _render_plain(data: Any) -> str:
    if isinstance(data, (str, bytes)):
        return data if isinstance(data, str) else data.decode()
    if isinstance(data, Iterable) and not isinstance(data, Mapping):
        return "\n".join(_render_plain(item) for item in data)
    return json.dumps(data, ensure_ascii=False)


def select_fields(data: Any, fields: list[str]) -> Any:
    """Project dicts to only the specified fields."""
    allowed = set(fields)
    if isinstance(data, list):
        return [{k: v for k, v in item.items() if k in allowed} if isinstance(item, dict) else item for item in data]
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in allowed}
    return data


def render_output(data: Any, fmt: str) -> str:
    data = _to_plain(data)
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if fmt == "markdown":
        return _render_markdown(data)
    return _render_plain(data)


def print_result(
    result: Any,
    *,
    entity: str,
    raw: bool,
    dry_run: bool,
    renderer: Callable[[Any], str] | None = None,
) -> None:
    """Format and print CLI output, applying field selection when appropriate."""
    result = _to_plain(result)
    if raw:
        print(render_output(result, "json"))
        return
    if not dry_run:
        fields = DISPLAY_FIELDS.get(entity)
        if fields:
            result = select_fields(result, fields)
        if renderer:
            print(renderer(result))
            return
    print(render_output(result, "markdown"))
