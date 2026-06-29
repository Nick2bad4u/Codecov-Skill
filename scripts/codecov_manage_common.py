from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class CodecovCliError(RuntimeError):
    """Raised for recoverable CLI errors."""


def join_message(*parts: str) -> str:
    return " ".join(parts)


def parse_name_value_pairs(values: Iterable[str] | None, *, argument_name: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if values is None:
        return parsed

    for raw_value in values:
        key, separator, value = raw_value.partition("=")
        if not separator or not key.strip():
            raise CodecovCliError(f"--{argument_name} values must use key=value syntax: {raw_value}")
        parsed[key.strip()] = value.strip()

    return parsed


def resolve_csv_values(values: Iterable[str] | None, *, argument_name: str) -> list[str]:
    resolved: list[str] = []
    if values is None:
        return resolved

    for raw_value in values:
        for item in raw_value.split(","):
            value = item.strip()
            if value:
                resolved.append(value)

    if not resolved:
        raise CodecovCliError(f"--{argument_name} must include at least one non-empty value.")

    return resolved


def require_positive_integer(value: int, *, argument_name: str) -> int:
    if value < 1:
        raise CodecovCliError(f"--{argument_name} must be at least 1.")
    return value
