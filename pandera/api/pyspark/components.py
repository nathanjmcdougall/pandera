"""Core pandas schema component specifications."""

import warnings
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import pandera.strategies as st
from pandera import errors
from pandera.backends.pyspark.components import (
    ColumnBackend,
)
from pandera.api.pyspark.column_schema import ColumnSchema
from pandera.api.pyspark.container import DataFrameSchema
from pandera.api.pyspark.types import CheckList, PySparkDtypeInputTypes
from pandera.dtypes import UniqueSettings
import pyspark.sql as ps
from pandera.api.pyspark.error_handler import ErrorHandler


class Column(ColumnSchema):
    """Validate types and properties of DataFrame columns."""

    BACKEND = ColumnBackend()

    def __init__(
        self,
        dtype: PySparkDtypeInputTypes = None,
        checks: Optional[CheckList] = None,
        nullable: bool = False,
        coerce: bool = False,
        required: bool = True,
        name: Union[str, Tuple[str, ...], None] = None,
        regex: bool = False,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Create column validator object.

        :param dtype: datatype of the column. The datatype for type-checking
            a dataframe. If a string is specified, then assumes
            one of the valid pandas string values:
            http://pandas.pydata.org/pandas-docs/stable/basics.html#dtypes
        :param checks: checks to verify validity of the column
        :param nullable: Whether or not column can contain null values.
        :param coerce: If True, when schema.validate is called the column will
            be coerced into the specified dtype. This has no effect on columns
            where ``dtype=None``.
        :param required: Whether or not column is allowed to be missing
        :param name: column name in dataframe to validate.
        :param regex: whether the ``name`` attribute should be treated as a
            regex pattern to apply to multiple columns in a dataframe.
        :param title: A human-readable label for the column.
        :param description: An arbitrary textual description of the column.

        :raises SchemaInitError: if impossible to build schema from parameters

        :example:

        >>> import pandas as pd
        >>> import pandera as pa
        >>>
        >>>
        >>> schema = pa.DataFrameSchema({
        ...     "column": pa.Column(str)
        ... })
        >>>
        >>> schema.validate(pd.DataFrame({"column": ["foo", "bar"]}))
          column
        0    foo
        1    bar

        See :ref:`here<column>` for more usage details.
        """
        super().__init__(
            dtype=dtype,
            checks=checks,
            nullable=nullable,
            coerce=coerce,
            name=name,
            title=title,
            description=description,
        )
        if name is not None and not isinstance(name, str) and regex:
            raise ValueError(
                "You cannot specify a non-string name when setting regex=True"
            )
        self.required = required
        self.name = name
        self.regex = regex

    @property
    def _allow_groupby(self) -> bool:
        """Whether the schema or schema component allows groupby operations."""
        return True

    @property
    def properties(self) -> Dict[str, Any]:
        """Get column properties."""
        return {
            "dtype": self.dtype,
            "checks": self.checks,
            "nullable": self.nullable,
            "unique": self.unique,
            "report_duplicates": self.report_duplicates,
            "coerce": self.coerce,
            "required": self.required,
            "name": self.name,
            "regex": self.regex,
            "title": self.title,
            "description": self.description,
        }

    def set_name(self, name: str):
        """Used to set or modify the name of a column object.

        :param str name: the name of the column object

        """
        self.name = name
        return self

    def validate(
        self,
        check_obj: ps.DataFrame,
        head: Optional[int] = None,
        tail: Optional[int] = None,
        sample: Optional[int] = None,
        random_state: Optional[int] = None,
        lazy: bool = True,
        inplace: bool = False,
        error_handler: ErrorHandler = None,
    ) -> ps.DataFrame:
        """Validate a Column in a DataFrame object.

        :param check_obj: pandas DataFrame to validate.
        :param head: validate the first n rows. Rows overlapping with `tail` or
            `sample` are de-duplicated.
        :param tail: validate the last n rows. Rows overlapping with `head` or
            `sample` are de-duplicated.
        :param sample: validate a random sample of n rows. Rows overlapping
            with `head` or `tail` are de-duplicated.
        :param random_state: random seed for the ``sample`` argument.
        :param lazy: if True, lazily evaluates dataframe against all validation
            checks and raises a ``SchemaErrors``. Otherwise, raise
            ``SchemaError`` as soon as one occurs.
        :param inplace: if True, applies coercion to the object of validation,
            otherwise creates a copy of the data.
        :returns: validated DataFrame.
        """
        return self.BACKEND.validate(
            check_obj=check_obj,
            schema=self,
            head=head,
            tail=tail,
            sample=sample,
            random_state=random_state,
            lazy=lazy,
            inplace=inplace,
            error_handler=error_handler,
        )

    def get_regex_columns(self, columns: Any) -> Iterable:
        """Get matching column names based on regex column name pattern.

        :param columns: columns to regex pattern match
        :returns: matchin columns
        """
        return self.BACKEND.get_regex_columns(self, columns)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented

        def _compare_dict(obj):
            return {k: v if k != "_checks" else set(v) for k, v in obj.__dict__.items()}

        return _compare_dict(self) == _compare_dict(other)
