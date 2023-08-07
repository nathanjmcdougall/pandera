"""Built-in check functions base implementation.

This module contains check function abstract definitions that correspond to
the pandera.api.base.checks.Check methods. These functions do not actually
implement any validation logic and serve as the entrypoint for dispatching
specific implementations based on the data object type, e.g.
`pandas.DataFrame`s.
"""
from __future__ import annotations

# pylint: disable=missing-function-docstring
import re
from typing import Any, Iterable, TypeVar, Union

from pandera.api.checks import Check

T = TypeVar("T")


@Check.register_builtin_check_fn
def equal_to(data: Any, value: Any) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def not_equal_to(data: Any, value: Any) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def greater_than(data: Any, min_value: Any) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def greater_than_or_equal_to(data: Any, min_value: Any) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def less_than(data: Any, max_value: Any) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def less_than_or_equal_to(data: Any, max_value: Any) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def in_range(
    data: Any,
    min_value: T,
    max_value: T,
    include_min: bool = True,
    include_max: bool = True,
) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def isin(data: Any, allowed_values: Iterable) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def notin(data: Any, forbidden_values: Iterable) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def str_matches(data: Any, pattern: Union[str, re.Pattern]) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def str_contains(data: Any, pattern: Union[str, re.Pattern]) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def str_startswith(data: Any, string: str) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def str_endswith(data: Any, string: str) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def str_length(data: Any, min_value: int = None, max_value: int = None) -> Any:
    raise NotImplementedError


@Check.register_builtin_check_fn
def unique_values_eq(data: Any, values: Iterable) -> Any:
    raise NotImplementedError
