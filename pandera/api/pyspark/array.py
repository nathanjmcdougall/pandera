"""Core pandas array specification."""

import copy
import warnings
from typing import Any, List, Optional, TypeVar, Union, cast

import pandas as pd

from pandera import errors
from pandera import strategies as st
from pandera.backends.pandas.array import (
    ArraySchemaBackend,
    SeriesSchemaBackend,
)
from pandera.api.base.schema import BaseSchema, inferred_schema_guard
from pandera.api.checks import Check
from pandera.api.hypotheses import Hypothesis
from pandera.api.pyspark.types import (
    CheckList,
    PySparkDtypeInputTypes,
)
from pandera.dtypes import DataType, UniqueSettings
from pandera.engines import pandas_engine

TArraySchemaBase = TypeVar("TArraySchemaBase", bound="ArraySchema")


class ArraySchema(BaseSchema):
    """Base array validator object."""

    BACKEND = ArraySchemaBackend()

    def __init__(
        self,
        dtype: Optional[PySparkDtypeInputTypes] = None,
        checks: Optional[CheckList] = None,
        nullable: bool = False,
        unique: bool = False,
        report_duplicates: UniqueSettings = "all",
        coerce: bool = False,
        name: Any = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Initialize array schema.

        :param dtype: datatype of the column. If a string is specified,
            then assumes one of the valid pandas string values:
            http://pandas.pydata.org/pandas-docs/stable/basics.html#dtypes
        :param checks: If element_wise is True, then callable signature should
            be:

            ``Callable[Any, bool]`` where the ``Any`` input is a scalar element
            in the column. Otherwise, the input is assumed to be a
            pandas.Series object.
        :param nullable: Whether or not column can contain null values.
        :param unique: Whether or not column can contain duplicate
            values.
        :param report_duplicates: how to report unique errors
            - `exclude_first`: report all duplicates except first occurence
            - `exclude_last`: report all duplicates except last occurence
            - `all`: (default) report all duplicates
        :param coerce: If True, when schema.validate is called the column will
            be coerced into the specified dtype. This has no effect on columns
            where ``dtype=None``.
        :param name: column name in dataframe to validate.
        :param title: A human-readable label for the series.
        :param description: An arbitrary textual description of the series.
        :type nullable: bool
        """

        super().__init__(
            dtype=dtype,
            checks=checks,
            coerce=coerce,
            name=name,
            title=title,
            description=description,
        )

        if checks is None:
            checks = []
        if isinstance(checks, (Check, Hypothesis)):
            checks = [checks]

        self.checks = checks
        self.nullable = nullable
        self.unique = unique
        self.report_duplicates = report_duplicates
        self.title = title
        self.description = description

        for check in self.checks:
            if check.groupby is not None and not self._allow_groupby:
                raise errors.SchemaInitError(
                    f"Cannot use groupby checks with type {type(self)}"
                )

        # this attribute is not meant to be accessed by users and is explicitly
        # set to True in the case that a schema is created by infer_schema.
        self._IS_INFERRED = False

        if isinstance(self.dtype, pandas_engine.PydanticModel):
            raise errors.SchemaInitError(
                "PydanticModel dtype can only be specified as a "
                "DataFrameSchema dtype."
            )

    # the _is_inferred getter and setter methods are not public
    @property
    def _is_inferred(self):
        return self._IS_INFERRED

    @_is_inferred.setter
    def _is_inferred(self, value: bool):
        self._IS_INFERRED = value

    @property
    def _allow_groupby(self):
        """Whether the schema or schema component allows groupby operations."""
        raise NotImplementedError(  # pragma: no cover
            "The _allow_groupby property must be implemented by subclasses "
            "of SeriesSchemaBase"
        )

    @property
    def dtype(self) -> DataType:
        """Get the pandas dtype"""
        return self._dtype  # type: ignore

    @dtype.setter
    def dtype(self, value: Optional[PySparkDtypeInputTypes]) -> None:
        """Set the pandas dtype"""
        self._dtype = pandas_engine.Engine.dtype(value) if value else None

    def coerce_dtype(
        self,
        check_obj: Union[pd.Series, pd.Index],
    ) -> Union[pd.Series, pd.Index]:
        """Coerce type of a pd.Series by type specified in dtype.

        :param pd.Series series: One-dimensional ndarray with axis labels
            (including time series).
        :returns: ``Series`` with coerced data type
        """
        return self.BACKEND.coerce_dtype(check_obj, schema=self)

    def validate(
        self,
        check_obj,
        head: Optional[int] = None,
        tail: Optional[int] = None,
        sample: Optional[int] = None,
        random_state: Optional[int] = None,
        lazy: bool = False,
        inplace: bool = False,
    ):
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Validate a series or specific column in dataframe.

        :check_obj: pandas DataFrame or Series to validate.
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
        :returns: validated DataFrame or Series.

        """
        return self.BACKEND.validate(
            check_obj,
            schema=self,
            head=head,
            tail=tail,
            sample=sample,
            random_state=random_state,
            lazy=lazy,
            inplace=inplace,
        )

    def __call__(
        self,
        check_obj: Union[pd.DataFrame, pd.Series],
        head: Optional[int] = None,
        tail: Optional[int] = None,
        sample: Optional[int] = None,
        random_state: Optional[int] = None,
        lazy: bool = False,
        inplace: bool = False,
    ) -> Union[pd.DataFrame, pd.Series]:
        """Alias for ``validate`` method."""
        return self.validate(
            check_obj, head, tail, sample, random_state, lazy, inplace
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    @classmethod
    def __get_validators__(cls):
        yield cls._pydantic_validate

    @classmethod
    def _pydantic_validate(  # type: ignore
        cls: TArraySchemaBase, schema: Any
    ) -> TArraySchemaBase:
        """Verify that the input is a compatible Schema."""
        if not isinstance(schema, cls):  # type: ignore
            raise TypeError(f"{schema} is not a {cls}.")

        return cast(TArraySchemaBase, schema)

    #############################
    # Schema Transforms Methods #
    #############################

    @inferred_schema_guard
    def update_checks(self, checks: List[Check]):
        """Create a new SeriesSchema with a new set of Checks

        :param checks: checks to set on the new schema
        :returns: a new SeriesSchema with a new set of checks
        """
        schema_copy = cast(ArraySchema, copy.deepcopy(self))
        schema_copy.checks = checks
        return schema_copy

    def set_checks(self, checks: CheckList):
        """Create a new SeriesSchema with a new set of Checks

        .. caution::
           This method will be deprecated in favor of ``update_checks`` in
           v0.15.0

        :param checks: checks to set on the new schema
        :returns: a new SeriesSchema with a new set of checks
        """
        return self.update_checks(checks)

    ###########################
    # Schema Strategy Methods #
    ###########################

    @st.strategy_import_error
    def strategy(self, *, size=None):
        """Create a ``hypothesis`` strategy for generating a Series.

        :param size: number of elements to generate
        :returns: a strategy that generates pandas Series objects.
        """
        return st.series_strategy(
            self.dtype,
            checks=self.checks,
            nullable=self.nullable,
            unique=self.unique,
            name=self.name,
            size=size,
        )

    def example(self, size=None) -> Union[pd.Series, pd.Index, pd.DataFrame]:
        """Generate an example of a particular size.

        :param size: number of elements in the generated array.
        :returns: array object.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,import-error
        import hypothesis

        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore",
                category=hypothesis.errors.NonInteractiveExampleWarning,
            )
            return self.strategy(size=size).example()

    def __repr__(self):
        return (
            f"<Schema {self.__class__.__name__}"
            f"(name={self.name}, type={self.dtype!r})>"
        )
