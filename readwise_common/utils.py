"""Misc helpers shared across skills."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence


def parse_tags(raw: str | None) -> List[str]:
    if not raw:
        return []
    tags: List[str] = []
    for part in raw.split(","):
        tag = part.strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def build_tags(existing: Sequence[str] | None, generated: bool) -> List[str]:
    tags = list(existing) if existing else []
    if generated and ".generated" not in tags:
        tags.append(".generated")
    return tags


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
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
