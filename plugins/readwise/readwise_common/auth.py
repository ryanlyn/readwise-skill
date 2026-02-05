"""Token management helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass

READWISE_TOKEN_ENV = "READWISE_TOKEN"


class MissingTokenError(RuntimeError):
    """Raised when an API token is unavailable."""


@dataclass
class Token:
    value: str
    name: str

    def __repr__(self) -> str:
        return f"Token(name={self.name!r}, value='***')"

    def __str__(self) -> str:
        return f"Token({self.name}=***)"


def get_token(override: str | None = None) -> Token:
    """Get Readwise API token from override or READWISE_TOKEN env var."""
    token = override or os.getenv(READWISE_TOKEN_ENV)
    if not token:
        raise MissingTokenError(f"Set {READWISE_TOKEN_ENV} or pass --token explicitly.")
    return Token(value=token, name=READWISE_TOKEN_ENV)


# Aliases for backwards compatibility
get_readwise_token = get_token
get_reader_token = get_token
