"""Core pandas dataframe container specification."""
# pylint: disable=unused-import
from __future__ import annotations

import copy
from typing import Any, cast

from pandera import errors
from pandera import strategies as st
from pandera.api.base.schema import inferred_schema_guard
from pandera.api.pandas.column import Column
from pandera.api.pandas.index import Index
from pandera.api.pandas.multi_index import MultiIndex
from pandera.api.pandas.schema import BaseDataFrameSchema
from pandera.api.pandas.types import PandasDtypeInputTypes
from pandera.dtypes import DataType
from pandera.engines import pandas_engine


class DataFrameSchema(BaseDataFrameSchema):
    """A light-weight pandas DataFrame validator."""

    # pylint: disable=too-many-public-methods

    def set_index(
        self, keys: list[str], drop: bool = True, append: bool = False
    ) -> DataFrameSchema:
        """
        A method for setting the :class:`Index` of a :class:`DataFrameSchema`,
        via an existing :class:`Column` or list of columns.

        :param keys: list of labels
        :param drop: bool, default True
        :param append: bool, default False
        :return: a new :class:`DataFrameSchema` with specified column(s) in the
            index.
        :raises: :class:`~pandera.errors.SchemaInitError` if column not in the
            schema.

        :examples:

        Just as you would set the index in a ``pandas`` DataFrame from an
        existing column, you can set an index within the schema from an
        existing column in the schema.

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema({
        ...     "category" : pa.Column(str),
        ...     "probability": pa.Column(float)})
        >>>
        >>> print(example_schema.set_index(['category']))
        <Schema DataFrameSchema(
            columns={
                'probability': <Schema Column(name=probability, type=DataType(float64))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=<Schema Index(name=category, type=DataType(str))>,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        If you have an existing index in your schema, and you would like to
        append a new column as an index to it (yielding a :class:`Multiindex`),
        just use set_index as you would in pandas.

        >>> example_schema = pa.DataFrameSchema(
        ...     {
        ...         "column1": pa.Column(str),
        ...         "column2": pa.Column(int)
        ...     },
        ...     index=pa.Index(name = "column3", dtype = int)
        ... )
        >>>
        >>> print(example_schema.set_index(["column2"], append = True))
        <Schema DataFrameSchema(
            columns={
                'column1': <Schema Column(name=column1, type=DataType(str))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=<Schema MultiIndex(
                indexes=[
                    <Schema Index(name=column3, type=DataType(int64))>
                    <Schema Index(name=column2, type=DataType(int64))>
                ]
                coerce=False,
                strict=False,
                name=None,
                ordered=True
            )>,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. seealso:: :func:`reset_index`

        """
        new_schema = copy.deepcopy(self)

        keys_temp: list = (
            list(set(keys)) if not isinstance(keys, list) else keys
        )

        # ensure all specified keys are present in the columns
        not_in_cols: list[str] = [
            x for x in keys_temp if x not in new_schema.columns.keys()
        ]
        if not_in_cols:
            raise errors.SchemaInitError(
                f"Keys {not_in_cols} not found in schema columns!"
            )

        # if there is already an index, append or replace according to
        # parameters
        ind_list: list = (
            []
            if new_schema.index is None or not append
            else list(new_schema.index.indexes)
            if isinstance(new_schema.index, MultiIndex) and append
            else [new_schema.index]
        )

        for col in keys_temp:
            ind_list.append(
                Index(
                    dtype=new_schema.columns[col].dtype,
                    name=col,
                    checks=new_schema.columns[col].checks,
                    nullable=new_schema.columns[col].nullable,
                    unique=new_schema.columns[col].unique,
                    coerce=new_schema.columns[col].coerce,
                )
            )

        new_schema.index = (
            ind_list[0] if len(ind_list) == 1 else MultiIndex(ind_list)
        )

        # if drop is True as defaulted, drop the columns moved into the index
        if drop:
            new_schema = new_schema.remove_columns(keys_temp)

        return cast(DataFrameSchema, new_schema)

    def reset_index(
        self, level: list[str] = None, drop: bool = False
    ) -> DataFrameSchema:
        """
        A method for resetting the :class:`Index` of a :class:`DataFrameSchema`

        :param level: list of labels
        :param drop: bool, default True
        :return: a new :class:`DataFrameSchema` with specified column(s) in the
            index.
        :raises: :class:`~pandera.errors.SchemaInitError` if no index set in
            schema.
        :examples:

        Similar to the ``pandas`` reset_index method on a pandas DataFrame,
        this method can be used to to fully or partially reset indices of a
        schema.

        To remove the entire index from the schema, just call the reset_index
        method with default parameters.

        >>> import pandera as pa
        >>>
        >>> example_schema = pa.DataFrameSchema(
        ...     {"probability" : pa.Column(float)},
        ...     index = pa.Index(name="unique_id", dtype=int)
        ... )
        >>>
        >>> print(example_schema.reset_index())
        <Schema DataFrameSchema(
            columns={
                'probability': <Schema Column(name=probability, type=DataType(float64))>
                'unique_id': <Schema Column(name=unique_id, type=DataType(int64))>
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

        This reclassifies an index (or indices) as a column (or columns).

        Similarly, to partially alter the index, pass the name of the column
        you would like to be removed to the ``level`` parameter, and you may
        also decide whether to drop the levels with the ``drop`` parameter.

        >>> example_schema = pa.DataFrameSchema({
        ...     "category" : pa.Column(str)},
        ...     index = pa.MultiIndex([
        ...         pa.Index(name="unique_id1", dtype=int),
        ...         pa.Index(name="unique_id2", dtype=str)
        ...         ]
        ...     )
        ... )
        >>> print(example_schema.reset_index(level = ["unique_id1"]))
        <Schema DataFrameSchema(
            columns={
                'category': <Schema Column(name=category, type=DataType(str))>
                'unique_id1': <Schema Column(name=unique_id1, type=DataType(int64))>
            },
            checks=[],
            coerce=False,
            dtype=None,
            index=<Schema Index(name=unique_id2, type=DataType(str))>,
            strict=False,
            name=None,
            ordered=False,
            unique_column_names=False,
            metadata=None,
            add_missing_columns=False
        )>

        .. seealso:: :func:`set_index`

        """

        # explcit check for an empty list
        if level == []:
            return self

        new_schema = copy.deepcopy(self)

        if new_schema.index is None:
            raise errors.SchemaInitError(
                "There is currently no index set for this schema."
            )

        # ensure no duplicates
        level_temp: list[Any] | list[str] = (
            new_schema.index.names if level is None else list(set(level))
        )

        # ensure all specified keys are present in the index
        level_not_in_index: list[Any] | list[str] | None = (
            [x for x in level_temp if x not in new_schema.index.names]
            if isinstance(new_schema.index, MultiIndex) and level_temp
            else []
            if isinstance(new_schema.index, Index)
            and (level_temp == [new_schema.index.name])
            else level_temp
        )
        if level_not_in_index:
            raise errors.SchemaInitError(
                f"Keys {level_not_in_index} not found in schema columns!"
            )

        new_index = (
            None
            if not level_temp or isinstance(new_schema.index, Index)
            else new_schema.index.remove_columns(level_temp)
        )
        new_index = (
            new_index
            if new_index is None
            else Index(
                dtype=new_index.columns[list(new_index.columns)[0]].dtype,
                checks=new_index.columns[list(new_index.columns)[0]].checks,
                nullable=new_index.columns[
                    list(new_index.columns)[0]
                ].nullable,
                unique=new_index.columns[list(new_index.columns)[0]].unique,
                coerce=new_index.columns[list(new_index.columns)[0]].coerce,
                name=new_index.columns[list(new_index.columns)[0]].name,
            )
            if (len(list(new_index.columns)) == 1) and (new_index is not None)
            else None
            if (len(list(new_index.columns)) == 0) and (new_index is not None)
            else new_index
        )

        if not drop:
            additional_columns: dict[str, Any] = (
                {col: new_schema.index.columns.get(col) for col in level_temp}
                if isinstance(new_schema.index, MultiIndex)
                else {new_schema.index.name: new_schema.index}
            )
            new_schema = new_schema.add_columns(
                {
                    k: Column(
                        dtype=v.dtype,
                        checks=v.checks,
                        nullable=v.nullable,
                        unique=v.unique,
                        coerce=v.coerce,
                        name=v.name,
                    )
                    for (k, v) in additional_columns.items()
                }
            )

        new_schema.index = new_index

        return new_schema
