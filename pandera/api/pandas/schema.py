"""An abstract base class for a validator schema for DataFrame-like objects."""
from __future__ import annotations

import copy
import os
import warnings
from pathlib import Path
from typing import Any, cast, overload

import pandas as pd
from typing_extensions import Self

from pandera import errors
from pandera import strategies as st
from pandera.api.base.schema import BaseSchema, inferred_schema_guard
from pandera.api.checks import Check
from pandera.api.hypotheses import Hypothesis
from pandera.api.pandas.column import Column
from pandera.api.pandas.types import (
    CheckList,
    PandasDtypeInputTypes,
    StrictType,
)
from pandera.dtypes import DataType, UniqueSettings
from pandera.engines import pandas_engine

N_INDENT_SPACES = 4


class BaseDataFrameSchema(BaseSchema):
    """Base class for a DataFrame-like schema, i.e. DataFrame and MultiIndex."""

    # pylint: disable=too-many-public-methods,too-many-locals
    def __init__(
        self,
        columns: dict[Any, Column] | None = None,
        checks: CheckList | None = None,
        index=None,
        dtype: PandasDtypeInputTypes = None,
        coerce: bool = False,
        strict: StrictType = False,
        name: str | None = None,
        ordered: bool = False,
        unique: str | list[str] | None = None,
        report_duplicates: UniqueSettings = "all",
        unique_column_names: bool = False,
        add_missing_columns: bool = False,
        title: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
        drop_invalid_rows: bool = False,
    ) -> None:
        """Initialize DataFrameSchema validator.

        :param columns: a dict where keys are column names and values are
            Column objects specifying the datatypes and properties of a
            particular column.
        :type columns: mapping of column names and column schema component.
        :param checks: dataframe-wide checks.
        :param index: specify the datatypes and properties of the index.
        :param dtype: datatype of the dataframe. This overrides the data
            types specified in any of the columns. If a string is specified,
            then assumes one of the valid pandas string values:
            http://pandas.pydata.org/pandas-docs/stable/basics.html#dtypes.
        :param coerce: whether or not to coerce all of the columns on
            validation. This has no effect on columns where
            ``dtype=None``
        :param strict: ensure that all and only the columns defined in the
            schema are present in the dataframe. If set to 'filter',
            only the columns in the schema will be passed to the validated
            dataframe. If set to filter and columns defined in the schema
            are not present in the dataframe, will throw an error.
        :param name: name of the schema.
        :param ordered: whether or not to validate the columns order.
        :param unique: a list of columns that should be jointly unique.
        :param report_duplicates: how to report unique errors
            - `exclude_first`: report all duplicates except first occurence
            - `exclude_last`: report all duplicates except last occurence
            - `all`: (default) report all duplicates
        :param unique_column_names: whether or not column names must be unique.
        :param add_missing_columns: add missing column names with either default
            value, if specified in column schema, or NaN if column is nullable.
        :param title: A human-readable label for the schema.
        :param description: An arbitrary textual description of the schema.
        :param metadata: An optional key-value data.
        :param drop_invalid_rows: if True, drop invalid rows on validation.

        :raises SchemaInitError: if impossible to build schema from parameters

        :examples:

        >>> import pandera as pa
        >>>
        >>> schema = pa.DataFrameSchema({
        ...     "str_column": pa.Column(str),
        ...     "float_column": pa.Column(float),
        ...     "int_column": pa.Column(int),
        ...     "date_column": pa.Column(pa.DateTime),
        ... })

        Use the pandas API to define checks, which takes a function with
        the signature: ``pd.Series -> Union[bool, pd.Series]`` where the
        output series contains boolean values.

        >>> schema_withchecks = pa.DataFrameSchema({
        ...     "probability": pa.Column(
        ...         float, pa.Check(lambda s: (s >= 0) & (s <= 1))),
        ...
        ...     # check that the "category" column contains a few discrete
        ...     # values, and the majority of the entries are dogs.
        ...     "category": pa.Column(
        ...         str, [
        ...             pa.Check(lambda s: s.isin(["dog", "cat", "duck"])),
        ...             pa.Check(lambda s: (s == "dog").mean() > 0.5),
        ...         ]),
        ... })

        See :ref:`here<DataFrameSchemas>` for more usage details.

        """
        if columns is None:
            columns = {}

        _validate_columns(columns)
        columns = _columns_renamed(columns)

        if checks is None:
            checks = []
        if isinstance(checks, (Check, Hypothesis)):
            checks = [checks]

        super().__init__(
            dtype=dtype,
            checks=checks,
            name=name,
            title=title,
            description=description,
            metadata=metadata,
        )

        self.columns: dict[Any, Column] = (  # type: ignore [name-defined]
            {} if columns is None else columns
        )

        if strict not in (
            False,
            True,
            "filter",
        ):
            raise errors.SchemaInitError(
                "strict parameter must equal either `True`, `False`, "
                "or `'filter'`."
            )

        self.index = index
        self.strict: bool | str = strict
        self._coerce = coerce
        self.ordered = ordered
        self._unique = unique
        self.report_duplicates = report_duplicates
        self.unique_column_names = unique_column_names
        self.add_missing_columns = add_missing_columns
        self.drop_invalid_rows = drop_invalid_rows

        # this attribute is not meant to be accessed by users and is explicitly
        # set to True in the case that a schema is created by infer_schema.
        self._IS_INFERRED = False
        self.metadata = metadata
        self.metadata = metadata

    def __call__(
        self,
        dataframe: pd.DataFrame,
        head: int | None = None,
        tail: int | None = None,
        sample: int | None = None,
        random_state: int | None = None,
        lazy: bool = False,
        inplace: bool = False,
    ):
        """Alias for :func:`DataFrameSchema.validate` method.

        :param pd.DataFrame dataframe: the dataframe to be validated.
        :param head: validate the first n rows. Rows overlapping with `tail` or
            `sample` are de-duplicated.
        :type head: int
        :param tail: validate the last n rows. Rows overlapping with `head` or
            `sample` are de-duplicated.
        :type tail: int
        :param sample: validate a random sample of n rows. Rows overlapping
            with `head` or `tail` are de-duplicated.
        :param random_state: random seed for the ``sample`` argument.
        :param lazy: if True, lazily evaluates dataframe against all validation
            checks and raises a ``SchemaErrors``. Otherwise, raise
            ``SchemaError`` as soon as one occurs.
        :param inplace: if True, applies coercion to the object of validation,
            otherwise creates a copy of the data.
        """
        return self.validate(
            dataframe, head, tail, sample, random_state, lazy, inplace
        )

    @property
    def coerce(self) -> bool:
        """Whether to coerce series to specified type."""
        if isinstance(self.dtype, DataType):
            return self.dtype.auto_coerce or self._coerce
        return self._coerce

    @coerce.setter
    def coerce(self, value: bool) -> None:
        """Set coerce attribute"""
        self._coerce = value

    @property
    def unique(self):
        """List of columns that should be jointly unique."""
        return self._unique

    @unique.setter
    def unique(self, value: str | list[str] | None) -> None:
        """Set unique attribute."""
        self._unique = [value] if isinstance(value, str) else value

    # the _is_inferred getter and setter methods are not public
    @property
    def _is_inferred(self) -> bool:
        return self._IS_INFERRED

    @_is_inferred.setter
    def _is_inferred(self, value: bool) -> None:
        self._IS_INFERRED = value

    @property
    def dtypes(self) -> dict[str, DataType]:
        # pylint:disable=anomalous-backslash-in-string
        """
        A dict where the keys are column names and values are
        :class:`~pandera.dtypes.DataType` s for the column. Excludes columns
        where `regex=True`.

        :returns: dictionary of columns and their associated dtypes.
        """
        regex_columns = [
            name for name, col in self.columns.items() if col.regex
        ]
        if regex_columns:
            warnings.warn(
                "Schema has columns specified as regex column names: "
                f"{regex_columns}. Use the `get_dtypes` to get the datatypes "
                "for these columns.",
                UserWarning,
            )
        return {n: c.dtype for n, c in self.columns.items() if not c.regex}

    def get_metadata(self) -> dict | None:
        """Provide metadata for columns and schema level"""
        res: dict[Any, Any] = {"columns": {}}
        for k in self.columns.keys():
            res["columns"][k] = self.columns[k].properties["metadata"]

        res["dataframe"] = self.metadata

        meta = {}
        meta[self.name] = res
        return meta

    def get_dtypes(self, dataframe: pd.DataFrame) -> dict[str, DataType]:
        """
        Same as the ``dtype`` property, but expands columns where
        ``regex == True`` based on the supplied dataframe.

        :returns: dictionary of columns and their associated dtypes.
        """
        regex_dtype = {}
        for _, column in self.columns.items():
            if column.regex:
                regex_dtype.update(
                    {
                        c: column.dtype
                        for c in column.get_backend(
                            dataframe
                        ).get_regex_columns(
                            column,
                            dataframe.columns,
                        )
                    }
                )
        return {
            **{n: c.dtype for n, c in self.columns.items() if not c.regex},
            **regex_dtype,
        }

    @property
    def dtype(
        self,
    ) -> DataType:
        """Get the dtype property."""
        return self._dtype  # type: ignore

    @dtype.setter
    def dtype(self, value: PandasDtypeInputTypes) -> None:
        """Set the pandas dtype property."""
        self._dtype = pandas_engine.Engine.dtype(value) if value else None

    def coerce_dtype(self, check_obj: pd.DataFrame) -> pd.DataFrame:
        return self.get_backend(check_obj).coerce_dtype(check_obj, schema=self)

    def validate(
        self,
        check_obj: pd.DataFrame,
        head: int | None = None,
        tail: int | None = None,
        sample: int | None = None,
        random_state: int | None = None,
        lazy: bool = False,
        inplace: bool = False,
    ) -> pd.DataFrame:
        """Check if all columns in a dataframe have a column in the Schema.

        :param pd.DataFrame check_obj: the dataframe to be validated.
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
        :returns: validated ``DataFrame``

        :raises SchemaError: when ``DataFrame`` violates built-in or custom
            checks.

        :example:

        Calling ``schema.validate`` returns the dataframe.

        >>> import pandas as pd
        >>> import pandera as pa
        >>>
        >>> df = pd.DataFrame({
        ...     "probability": [0.1, 0.4, 0.52, 0.23, 0.8, 0.76],
        ...     "category": ["dog", "dog", "cat", "duck", "dog", "dog"]
        ... })
        >>>
        >>> schema_withchecks = pa.DataFrameSchema({
        ...     "probability": pa.Column(
        ...         float, pa.Check(lambda s: (s >= 0) & (s <= 1))),
        ...
        ...     # check that the "category" column contains a few discrete
        ...     # values, and the majority of the entries are dogs.
        ...     "category": pa.Column(
        ...         str, [
        ...             pa.Check(lambda s: s.isin(["dog", "cat", "duck"])),
        ...             pa.Check(lambda s: (s == "dog").mean() > 0.5),
        ...         ]),
        ... })
        >>>
        >>> schema_withchecks.validate(df)[["probability", "category"]]
           probability category
        0         0.10      dog
        1         0.40      dog
        2         0.52      cat
        3         0.23     duck
        4         0.80      dog
        5         0.76      dog
        """
        # NOTE: Move this into its own schema-backend variant. This is where
        # the benefits of separating the schema spec from the backend
        # implementation comes in.

        if hasattr(check_obj, "dask"):
            # special case for dask dataframes
            if inplace:
                check_obj = check_obj.pandera.add_schema(self)
            else:
                check_obj = check_obj.copy()

            check_obj = check_obj.map_partitions(  # type: ignore [operator]
                self._validate,
                head=head,
                tail=tail,
                sample=sample,
                random_state=random_state,
                lazy=lazy,
                inplace=inplace,
                meta=check_obj,
            )
            return check_obj.pandera.add_schema(self)

        return self._validate(
            check_obj=check_obj,
            head=head,
            tail=tail,
            sample=sample,
            random_state=random_state,
            lazy=lazy,
            inplace=inplace,
        )

    def _validate(
        self,
        check_obj: pd.DataFrame,
        head: int | None = None,
        tail: int | None = None,
        sample: int | None = None,
        random_state: int | None = None,
        lazy: bool = False,
        inplace: bool = False,
    ) -> pd.DataFrame:
        if self._is_inferred:
            warnings.warn(
                f"This {type(self)} is an inferred schema that hasn't been "
                "modified. It's recommended that you refine the schema "
                "by calling `add_columns`, `remove_columns`, or "
                "`update_columns` before using it to validate data.",
                UserWarning,
            )

        return self.get_backend(check_obj).validate(
            check_obj,
            schema=self,
            head=head,
            tail=tail,
            sample=sample,
            random_state=random_state,
            lazy=lazy,
            inplace=inplace,
        )

    def __repr__(self) -> str:
        """Represent string for logging."""
        return (
            f"<Schema {self.__class__.__name__}("
            f"columns={self.columns}, "
            f"checks={self.checks}, "
            f"index={self.index.__repr__()}, "
            f"coerce={self.coerce}, "
            f"dtype={self._dtype}, "
            f"strict={self.strict}, "
            f"name={self.name}, "
            f"ordered={self.ordered}, "
            f"unique_column_names={self.unique_column_names}"
            f"metadata='{self.metadata}, "
            f"unique_column_names={self.unique_column_names}, "
            f"add_missing_columns={self.add_missing_columns}"
            ")>"
        )

    def __str__(self) -> str:
        """Represent string for user inspection."""

        def _format_multiline(json_str, arg):
            return "\n".join(
                f"{indent}{line}" if i != 0 else f"{indent}{arg}={line}"
                for i, line in enumerate(json_str.split("\n"))
            )

        indent = " " * N_INDENT_SPACES
        if self.columns:
            columns_str = f"{indent}columns={{\n"
            for colname, col in self.columns.items():
                columns_str += f"{indent * 2}'{colname}': {col}\n"
            columns_str += f"{indent}}}"
        else:
            columns_str = f"{indent}columns={{}}"

        if self.checks:
            checks_str = f"{indent}checks=[\n"
            for check in self.checks:
                checks_str += f"{indent * 2}{check}\n"
            checks_str += f"{indent}]"
        else:
            checks_str = f"{indent}checks=[]"

        # add additional indents
        index_ = str(self.index).split("\n")
        if len(index_) == 1:
            index = str(self.index)
        else:
            index = "\n".join(
                x if i == 0 else f"{indent}{x}" for i, x in enumerate(index_)
            )

        return (
            f"<Schema {self.__class__.__name__}(\n"
            f"{columns_str},\n"
            f"{checks_str},\n"
            f"{indent}coerce={self.coerce},\n"
            f"{indent}dtype={self._dtype},\n"
            f"{indent}index={index},\n"
            f"{indent}strict={self.strict},\n"
            f"{indent}name={self.name},\n"
            f"{indent}ordered={self.ordered},\n"
            f"{indent}unique_column_names={self.unique_column_names},\n"
            f"{indent}metadata={self.metadata}, \n"
            f"{indent}add_missing_columns={self.add_missing_columns}\n"
            ")>"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented

        def _compare_dict(obj):
            return {
                k: v for k, v in obj.__dict__.items() if k != "_IS_INFERRED"
            }

        return _compare_dict(self) == _compare_dict(other)

    @classmethod
    def __get_validators__(cls):
        yield cls._pydantic_validate

    @classmethod
    def _pydantic_validate(cls, schema: Any) -> Self:
        """Verify that the input is a compatible DataFrameSchema."""
        if not isinstance(schema, cls):  # type: ignore
            raise TypeError(f"{schema} is not a {cls}.")

        return cast(cls, schema)

    #################################
    # Schema Transformation Methods #
    #################################

    @inferred_schema_guard
    def add_columns(self, extra_schema_cols: dict[str, Any]) -> Self:
        """Create a copy of the :class:`DataFrameSchema` with extra columns.

        :param extra_schema_cols: Additional columns of the format
        :type extra_schema_cols: DataFrameSchema
        :returns: a new :class:`DataFrameSchema` with the extra_schema_cols
            added.

        :example:

        To add columns to the schema, pass a dictionary with column name and
        ``Column`` instance key-value pairs.

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema(
        ...    {
        ...        "category": pa.Column(str),
        ...        "probability": pa.Column(float),
        ...    }
        ... )
        >>> print(
        ...     example_schema.add_columns({"even_number": pa.Column(pa.Bool)})
        ... )
        <Schema DataFrameSchema(
            columns={
                'category': <Schema Column(name=category, type=DataType(str))>
                'probability': <Schema Column(name=probability, type=DataType(float64))>
                'even_number': <Schema Column(name=even_number, type=DataType(bool))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=None,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. seealso:: :func:`remove_columns`

        """
        schema_copy = copy.deepcopy(self)
        schema_copy.columns = {
            **schema_copy.columns,
            **self.__class__(extra_schema_cols).columns,
        }
        return cast(type(self), schema_copy)

    @inferred_schema_guard
    def remove_columns(self, cols_to_remove: list[str]) -> Self:
        """Removes columns from a :class:`DataFrameSchema` and returns a new
        copy.

        :param cols_to_remove: Columns to be removed from the
            ``DataFrameSchema``
        :type cols_to_remove: List
        :returns: a new :class:`DataFrameSchema` without the cols_to_remove
        :raises: :class:`~pandera.errors.SchemaInitError`: if column not in
            schema.

        :example:

        To remove a column or set of columns from a schema, pass a list of
        columns to be removed:

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema(
        ...     {
        ...         "category" : pa.Column(str),
        ...         "probability": pa.Column(float)
        ...     }
        ... )
        >>>
        >>> print(example_schema.remove_columns(["category"]))
        <Schema DataFrameSchema(
            columns={
                'probability': <Schema Column(name=probability, type=DataType(float64))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=None,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. seealso:: :func:`add_columns`

        """
        schema_copy = copy.deepcopy(self)

        # ensure all specified keys are present in the columns
        not_in_cols: list[str] = [
            x for x in cols_to_remove if x not in schema_copy.columns.keys()
        ]
        if not_in_cols:
            raise errors.SchemaInitError(
                f"Keys {not_in_cols} not found in schema columns!"
            )

        for col in cols_to_remove:
            schema_copy.columns.pop(col)

        return cast(type(self), schema_copy)

    @inferred_schema_guard
    def update_column(self, column_name: str, **kwargs) -> Self:
        """Create copy of a :class:`DataFrameSchema` with updated column
        properties.

        :param column_name:
        :param kwargs: key-word arguments supplied to
            :class:`~pandera.api.pandas.components.Column`
        :returns: a new :class:`DataFrameSchema` with updated column
        :raises: :class:`~pandera.errors.SchemaInitError`: if column not in
            schema or you try to change the name.

        :example:

        Calling ``schema.1`` returns the :class:`DataFrameSchema`
        with the updated column.

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema({
        ...     "category" : pa.Column(str),
        ...     "probability": pa.Column(float)
        ... })
        >>> print(
        ...     example_schema.update_column(
        ...         'category', dtype=pa.Category
        ...     )
        ... )
        <Schema DataFrameSchema(
            columns={
                'category': <Schema Column(name=category, type=DataType(category))>
                'probability': <Schema Column(name=probability, type=DataType(float64))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=None,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. seealso:: :func:`rename_columns`

        """
        # check that columns exist in schema

        schema = self
        if "name" in kwargs:
            raise ValueError("cannot update 'name' of the column.")
        if column_name not in schema.columns:
            raise ValueError(f"column '{column_name}' not in {schema}")
        schema_copy = copy.deepcopy(schema)
        column_copy = copy.deepcopy(schema.columns[column_name])
        new_column = column_copy.__class__(
            **{**column_copy.properties, **kwargs}
        )
        schema_copy.columns.update({column_name: new_column})
        return cast(type(self), schema_copy)

    def update_columns(
        self,
        update_dict: dict[str, dict[str, Any]],
    ) -> Self:
        """
        Create copy of a :class:`DataFrameSchema` with updated column
        properties.

        :param update_dict:
        :return: a new :class:`DataFrameSchema` with updated columns
        :raises: :class:`~pandera.errors.SchemaInitError`: if column not in
            schema or you try to change the name.

        :example:

        Calling ``schema.update_columns`` returns the :class:`DataFrameSchema`
        with the updated columns.

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema({
        ...     "category" : pa.Column(str),
        ...     "probability": pa.Column(float)
        ... })
        >>>
        >>> print(
        ...     example_schema.update_columns(
        ...         {"category": {"dtype":pa.Category}}
        ...     )
        ... )
        <Schema DataFrameSchema(
            columns={
                'category': <Schema Column(name=category, type=DataType(category))>
                'probability': <Schema Column(name=probability, type=DataType(float64))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=None,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        """
        # pylint: disable=import-outside-toplevel,import-outside-toplevel

        new_schema = copy.deepcopy(self)

        # ensure all specified keys are present in the columns
        not_in_cols: list[str] = [
            x for x in update_dict.keys() if x not in new_schema.columns.keys()
        ]
        if not_in_cols:
            raise errors.SchemaInitError(
                f"Keys {not_in_cols} not found in schema columns!"
            )

        new_columns: dict[str, Column] = {}
        for col in new_schema.columns:
            # check
            if update_dict.get(col):
                if update_dict[col].get("name"):
                    raise errors.SchemaInitError(
                        "cannot update 'name' \
                                             property of the column."
                    )
            original_properties = new_schema.columns[col].properties
            if update_dict.get(col):
                new_properties = copy.deepcopy(original_properties)
                new_properties.update(update_dict[col])
                new_columns[col] = new_schema.columns[col].__class__(
                    **new_properties
                )
            else:
                new_columns[col] = new_schema.columns[col].__class__(
                    **original_properties
                )

        new_schema.columns = new_columns

        return cast(type(self), new_schema)

    def rename_columns(self, rename_dict: dict[str, str]) -> Self:
        """Rename columns using a dictionary of key-value pairs.

        :param rename_dict: dictionary of 'old_name': 'new_name' key-value
            pairs.
        :returns: :class:`DataFrameSchema` (copy of original)
        :raises: :class:`~pandera.errors.SchemaInitError` if column not in the
            schema.

        :example:

        To rename a column or set of columns, pass a dictionary of old column
        names and new column names, similar to the pandas DataFrame method.

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema({
        ...     "category" : pa.Column(str),
        ...     "probability": pa.Column(float)
        ... })
        >>>
        >>> print(
        ...     example_schema.rename_columns({
        ...         "category": "categories",
        ...         "probability": "probabilities"
        ...     })
        ... )
        <Schema DataFrameSchema(
            columns={
                'categories': <Schema Column(name=categories, type=DataType(str))>
                'probabilities': <Schema Column(name=probabilities, type=DataType(float64))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=None,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. seealso:: :func:`update_column`

        """
        new_schema = copy.deepcopy(self)

        # ensure all specified keys are present in the columns
        not_in_cols: list[str] = [
            x for x in rename_dict.keys() if x not in new_schema.columns.keys()
        ]
        if not_in_cols:
            raise errors.SchemaInitError(
                f"Keys {not_in_cols} not found in schema columns!"
            )

        # remove any mapping to itself as this is a no-op
        rename_dict = {k: v for k, v in rename_dict.items() if k != v}

        # ensure all new keys are not present in the current column names
        already_in_columns: list[str] = [
            x for x in rename_dict.values() if x in new_schema.columns.keys()
        ]
        if already_in_columns:
            raise errors.SchemaInitError(
                f"Keys {already_in_columns} already found in schema columns!"
            )

        # We iterate over the existing columns dict and replace those keys
        # that exist in the rename_dict

        new_columns = {
            (rename_dict[col_name] if col_name in rename_dict else col_name): (
                col_attrs.set_name(rename_dict[col_name])
                if col_name in rename_dict
                else col_attrs
            )
            for col_name, col_attrs in new_schema.columns.items()
        }

        new_schema.columns = new_columns
        return cast(type(self), new_schema)

    def select_columns(self, columns: list[Any]) -> Self:
        """Select subset of columns in the schema.

        *New in version 0.4.5*

        :param columns: list of column names to select.
        :returns:  :class:`DataFrameSchema` (copy of original) with only
            the selected columns.
        :raises: :class:`~pandera.errors.SchemaInitError` if column not in the
            schema.

        :example:

        To subset a schema by column, and return a new schema:

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema({
        ...     "category" : pa.Column(str),
        ...     "probability": pa.Column(float)
        ... })
        >>>
        >>> print(example_schema.select_columns(['category']))
        <Schema DataFrameSchema(
            columns={
                'category': <Schema Column(name=category, type=DataType(str))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=None,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. note:: If an index is present in the schema, it will also be
            included in the new schema.

        """

        new_schema = copy.deepcopy(self)

        # ensure all specified keys are present in the columns
        not_in_cols: list[str] = [
            x for x in columns if x not in new_schema.columns.keys()
        ]
        if not_in_cols:
            raise errors.SchemaInitError(
                f"Keys {not_in_cols} not found in schema columns!"
            )

        new_columns = {
            col_name: column
            for col_name, column in self.columns.items()
            if col_name in columns
        }
        new_schema.columns = new_columns
        return cast(type(self), new_schema)

    #####################
    # Schema IO Methods #
    #####################

    def to_script(self, fp: str | Path = None) -> Self:
        """Write DataFrameSchema to python script.

        :param path: str, Path to write script
        :returns: dataframe schema.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,redefined-outer-name
        import pandera.io

        return pandera.io.to_script(self, fp)

    @classmethod
    def from_yaml(cls, yaml_schema) -> Self:
        """Create DataFrameSchema from yaml file.

        :param yaml_schema: str, Path to yaml schema, or serialized yaml
            string.
        :returns: dataframe schema.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,redefined-outer-name
        import pandera.io

        return pandera.io.from_yaml(yaml_schema)

    @overload
    def to_yaml(self, stream: None = None) -> str:  # pragma: no cover
        ...

    @overload
    def to_yaml(self, stream: os.PathLike) -> None:  # pragma: no cover
        ...

    def to_yaml(self, stream: os.PathLike | None = None) -> str | None:
        """Write DataFrameSchema to yaml file.

        :param stream: file stream to write to. If None, dumps to string.
        :returns: yaml string if stream is None, otherwise returns None.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,redefined-outer-name
        import pandera.io

        return pandera.io.to_yaml(self, stream=stream)

    @classmethod
    def from_json(cls, source) -> Self:
        """Create DataFrameSchema from json file.

        :param source: str, Path to json schema, or serialized yaml
            string.
        :returns: dataframe schema.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,redefined-outer-name
        import pandera.io

        return pandera.io.from_json(source)

    @overload
    def to_json(
        self, target: None = None, **kwargs
    ) -> str:  # pragma: no cover
        ...

    @overload
    def to_json(
        self, target: os.PathLike, **kwargs
    ) -> None:  # pragma: no cover
        ...

    def to_json(
        self, target: os.PathLike | None = None, **kwargs
    ) -> str | None:
        """Write DataFrameSchema to json file.

        :param target: file target to write to. If None, dumps to string.
        :returns: json string if target is None, otherwise returns None.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,redefined-outer-name
        import pandera.io

        return pandera.io.to_json(self, target, **kwargs)

    ###########################
    # Schema Strategy Methods #
    ###########################

    @st.strategy_import_error
    def strategy(self, *, size: int | None = None, n_regex_columns: int = 1):
        """Create a ``hypothesis`` strategy for generating a DataFrame.

        :param size: number of elements to generate
        :param n_regex_columns: number of regex columns to generate.
        :returns: a strategy that generates pandas DataFrame objects.
        """
        return st.dataframe_strategy(
            self.dtype,
            columns=self.columns,
            checks=self.checks,
            unique=self.unique,
            index=self.index,
            size=size,
            n_regex_columns=n_regex_columns,
        )

    def example(
        self, size: int | None = None, n_regex_columns: int = 1
    ) -> pd.DataFrame:
        """Generate an example of a particular size.

        :param size: number of elements in the generated DataFrame.
        :returns: pandas DataFrame object.
        """
        # pylint: disable=import-outside-toplevel,cyclic-import,import-error
        import hypothesis

        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore",
                category=hypothesis.errors.NonInteractiveExampleWarning,
            )
            return self.strategy(
                size=size, n_regex_columns=n_regex_columns
            ).example()


def _validate_columns(
    column_dict: dict[Any, Column],  # type: ignore [name-defined]
) -> None:
    for column_name, column in column_dict.items():
        for check in column.checks:
            if check.groupby is None or callable(check.groupby):
                continue
            nonexistent_groupby_columns = [
                c for c in check.groupby if c not in column_dict
            ]
            if nonexistent_groupby_columns:
                raise errors.SchemaInitError(
                    f"groupby argument {nonexistent_groupby_columns} in "
                    f"Check for Column {column_name} not "
                    "specified in the DataFrameSchema."
                )


def _columns_renamed(
    columns: dict[Any, Column],  # type: ignore [name-defined]
) -> dict[Any, Column]:  # type: ignore [name-defined]
    def renamed(column, new_name):
        column = copy.deepcopy(column)
        column.set_name(new_name)
        return column

    return {
        column_name: renamed(column, column_name)
        for column_name, column in columns.items()
    }
