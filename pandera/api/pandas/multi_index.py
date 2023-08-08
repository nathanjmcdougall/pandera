"""The pandas schema component for multi-indexes."""
# pylint: disable=unused-import
from __future__ import annotations

import warnings

import pandas as pd

import pandera.strategies as st
from pandera import errors
from pandera.api.pandas.column import Column
from pandera.api.pandas.index import Index
from pandera.api.pandas.schema import BaseDataFrameSchema


class MultiIndex(BaseDataFrameSchema):
    """Validate types and properties of a DataFrame MultiIndex.

    This class inherits from :class:`~pandera.api.pandas.container.DataFrameSchema` to
    leverage its validation logic.
    """

    def __init__(
        self,
        indexes: list[Index],
        coerce: bool = False,
        strict: bool = False,
        name: str = None,
        ordered: bool = True,
        unique: str | list[str] | None = None,
    ) -> None:
        """Create MultiIndex validator.

        :param indexes: list of Index validators for each level of the
            MultiIndex index.
        :param coerce: Whether or not to coerce the MultiIndex to the
            specified dtypes before validation
        :param strict: whether or not to accept columns in the MultiIndex that
            aren't defined in the ``indexes`` argument.
        :param name: name of schema component
        :param ordered: whether or not to validate the indexes order.
        :param unique: a list of index names that should be jointly unique.

        :example:

        >>> import pandas as pd
        >>> import pandera as pa
        >>>
        >>>
        >>> schema = pa.DataFrameSchema(
        ...     columns={"column": pa.Column(int)},
        ...     index=pa.MultiIndex([
        ...         pa.Index(str,
        ...               pa.Check(lambda s: s.isin(["foo", "bar"])),
        ...               name="index0"),
        ...         pa.Index(int, name="index1"),
        ...     ])
        ... )
        >>>
        >>> df = pd.DataFrame(
        ...     data={"column": [1, 2, 3]},
        ...     index=pd.MultiIndex.from_arrays(
        ...         [["foo", "bar", "foo"], [0, 1, 2]],
        ...         names=["index0", "index1"],
        ...     )
        ... )
        >>>
        >>> schema.validate(df)
                       column
        index0 index1
        foo    0            1
        bar    1            2
        foo    2            3

        See :ref:`here<multiindex>` for more usage details.

        """
        if any(not isinstance(i, Index) for i in indexes):
            raise errors.SchemaInitError(
                f"expected a list of Index objects, found {indexes} "
                f"of type {[type(x) for x in indexes]}"
            )
        self.indexes = indexes
        columns = {}
        for i, index in enumerate(indexes):
            if not ordered and index.name is None:
                # if the MultiIndex is not ordered, there's no way of
                # determining how to get the index level without an explicit
                # index name
                raise errors.SchemaInitError(
                    "You must specify index names if MultiIndex schema "
                    "component is not ordered."
                )
            columns[i if index.name is None else index.name] = Column(
                dtype=index._dtype,
                checks=index.checks,
                nullable=index.nullable,
                unique=index.unique,
            )
        super().__init__(
            columns=columns,
            coerce=coerce,
            strict=strict,
            name=name,
            ordered=ordered,
            unique=unique,
        )

    @property
    def names(self):
        """Get index names in the MultiIndex schema component."""
        return [index.name for index in self.indexes]

    @property
    def coerce(self):
        """Whether or not to coerce data types."""
        return self._coerce or any(index.coerce for index in self.indexes)

    @coerce.setter
    def coerce(self, value: bool) -> None:
        """Set coerce attribute."""
        self._coerce = value

    def validate(  # type: ignore
        self,
        check_obj: pd.DataFrame | pd.Series,
        head: int | None = None,
        tail: int | None = None,
        sample: int | None = None,
        random_state: int | None = None,
        lazy: bool = False,
        inplace: bool = False,
    ) -> pd.DataFrame | pd.Series:
        """Validate DataFrame or Series MultiIndex.

        :param check_obj: pandas DataFrame of Series to validate.
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

    def __repr__(self):
        return (
            f"<Schema {self.__class__.__name__}("
            f"indexes={self.indexes}, "
            f"coerce={self.coerce}, "
            f"strict={self.strict}, "
            f"name={self.name}, "
            f"ordered={self.ordered}"
            ")>"
        )

    def __str__(self):
        indent = " " * 4

        indexes_str = "[\n"
        for index in self.indexes:
            indexes_str += f"{indent * 2}{index}\n"
        indexes_str += f"{indent}]"

        return (
            f"<Schema {self.__class__.__name__}(\n"
            f"{indent}indexes={indexes_str}\n"
            f"{indent}coerce={self.coerce},\n"
            f"{indent}strict={self.strict},\n"
            f"{indent}name={self.name},\n"
            f"{indent}ordered={self.ordered}\n"
            ")>"
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    ###########################
    # Schema Strategy Methods #
    ###########################

    @st.strategy_import_error
    # NOTE: remove these ignore statements as part of
    # https://github.com/pandera-dev/pandera/issues/403
    # pylint: disable=arguments-differ
    def strategy(self, *, size=None):  # type: ignore
        return st.multiindex_strategy(indexes=self.indexes, size=size)

    # NOTE: remove these ignore statements as part of
    # https://github.com/pandera-dev/pandera/issues/403
    # pylint: disable=arguments-differ
    def example(self, size=None) -> pd.MultiIndex:  # type: ignore
        # pylint: disable=import-outside-toplevel,cyclic-import,import-error
        import hypothesis

        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore",
                category=hypothesis.errors.NonInteractiveExampleWarning,
            )
            return self.strategy(size=size).example()
