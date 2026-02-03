"""Token management helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass

READWISE_TOKEN_ENV = "READWISE_TOKEN"
READWISE_READER_TOKEN_ENV = "READWISE_READER_TOKEN"


class MissingTokenError(RuntimeError):
    """Raised when an API token is unavailable."""


@dataclass
class Token:
    value: str
    name: str


def _get_token(env_name: str, override: str | None) -> Token:
    token = override or os.getenv(env_name)
    if not token:
        raise MissingTokenError(f"Set {env_name} or pass --token explicitly.")
    return Token(value=token, name=env_name)


def get_readwise_token(override: str | None = None) -> Token:
    return _get_token(READWISE_TOKEN_ENV, override)


def get_reader_token(override: str | None = None) -> Token:
    return _get_token(READWISE_READER_TOKEN_ENV, override)
