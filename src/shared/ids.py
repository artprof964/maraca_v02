"""Stable identifier helpers shared across partitions."""

from __future__ import annotations

import hashlib


def stable_id(prefix: str, *parts: str) -> str:
    """Return a deterministic ID using the project-wide stable hash format."""

    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


__all__ = ["stable_id"]
