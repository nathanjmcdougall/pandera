"""Storage classes for parsing, validation, and error Reporting Backends.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from pandera.api.checks import BaseCheck
from pandera.errors import SchemaError, SchemaErrorReason


class CoreCheckResult(NamedTuple):
    """Namedtuple for holding results of core checks."""

    passed: bool
    check: str | BaseCheck
    check_index: int | None = None
    check_output: Any | None = None
    reason_code: SchemaErrorReason | None = None
    message: str | None = None
    failure_cases: Any | None = None
    schema_error: SchemaError | None = None
    original_exc: Exception | None = None
    original_exc: Exception | None = None


class CoreParserResult(NamedTuple):
    """Namedtuple for holding core parser results."""
