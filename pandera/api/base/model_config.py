"""Class-based dataframe model API configuration."""
from __future__ import annotations

from typing import Any


class BaseModelConfig:  # pylint:disable=R0903
    """Model configuration base class."""

    #: datatype of the data container. This overrides the data types specified
    #: in any of the fields.
    dtype: Any | None = None

    name: str | None = None  #: name of schema
    title: str | None = None  #: human-readable label for schema
    description: str | None = None  #: arbitrary textual description
    coerce: bool = False  #: coerce types of all schema components
