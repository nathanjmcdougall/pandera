"""Base classes for parsing, validation, and error Reporting Backends.

These classes implement a common interface of operations needed for
data validation. These operations are exposed as methods that are composed
together to implement the pandera schema specification.
"""
from __future__ import annotations

from abc import ABC

from pandera.backends.base.backends import BaseCheckBackend, BaseSchemaBackend
from pandera.backends.base.core_results import (
    CoreCheckResult,
    CoreParserResult,
)
from pandera.errors import SchemaError, SchemaErrorReason
