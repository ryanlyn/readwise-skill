"""Misc helpers shared across skills."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    tags: list[str] = []
    for part in raw.split(","):
        tag = part.strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def build_tags(existing: Sequence[str] | None, generated: bool) -> list[str]:
    tags = list(existing) if existing else []
    if generated and ".generated" not in tags:
        tags.append(".generated")
    return tags


def format_inline_tags(tags: list[str], note: str | None = None) -> str:
    """Convert tags to Readwise inline notation and prepend to note.

    Readwise processes `.tagname` at the start of the note field as tags.
    Multiple tags: `.tag1 .tag2`. Tag + note: `.tag1 .tag2\\nNote text`.
    """
    if not tags:
        return note or ""
    inline = " ".join(tag if tag.startswith(".") else f".{tag}" for tag in tags)
    if note:
        return f"{inline}\n{note}"
    return inline


def resolve_highlight_text(text: str | None, text_file: str | None) -> str:
    if text:
        return text
    if text_file:
        return Path(text_file).read_text(encoding="utf-8").strip()
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return data
    raise ValueError("Provide --text, --text-file, or pipe content via stdin.")


def build_location_payload(location: str | None, location_type: str | None, generated: bool) -> dict:
    payload: dict[str, str] = {}
    if generated:
        if location or location_type:
            # Respect explicit inputs even for generated quotes, but default to none.
            pass
        else:
            payload["location_type"] = "none"
            return payload
    if location:
        payload["location"] = str(location)
        payload["location_type"] = location_type or "order"
    elif location_type:
        raise ValueError("--location-type requires --location")
    return payload


def load_bulk_payloads(path: str) -> Iterable[dict]:
    file_path = Path(path)
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        yield json.loads(stripped)


def parse_iso_datetime(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("Date value cannot be empty")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Invalid date/time: {value}") from exc
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
