"""PySpark implementation of built-in checks"""

import re
import functools
from typing import cast, Any, Iterable, TypeVar, Union, List, Type
from pandera.api.pyspark.types import PysparkDataframeColumnObject, PysparkDefaultTypes
import pandera.strategies as st
from pandera.api.extensions import register_builtin_check
from pandera.typing.pyspark import PYSPARK_INSTALLED

from pyspark.sql import DataFrame
from pyspark.sql.functions import col
import pyspark.sql.types as pst

T = TypeVar("T")


# Todo Move to decorator.py
def register_input_datatypes(
    acceptable_datatypes: List[Type[PysparkDefaultTypes]] = None,
):
    """
    This decorator is used to register the input datatype for the check.
    The function would raise error if value other than the acceptable one is sent

    """

    def wrapper(func):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            breakpoint()
            pyspark_object = [a for a in args][0]
            validation_df = pyspark_object.dataframe
            validation_column = pyspark_object.column_name
            datatypes = [i.typeName for i in acceptable_datatypes]
            current_datatype = (
                validation_df.select(validation_column).schema[0].dataType.typeName
            )
            if current_datatype in datatypes:
                return func(*args, **kwargs)
            else:
                raise TypeError(
                    f"The function only accepts the following datatypes {acceptable_datatypes}"
                    f" but got {current_datatype}"
                )

        return _wrapper

    return wrapper


# Todo Move to decorator.py
def register_input_datatypes(
    acceptable_datatypes: List[Type[PysparkDefaultTypes]] = None,
):
    """
    This decorator is used to register the input datatype for the check.
    The function would raise error if value other than the acceptable one is sent

    """

    def wrapper(func):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            breakpoint()
            pyspark_object = [a for a in args][0]
            validation_df = pyspark_object.dataframe
            validation_column = pyspark_object.column_name
            datatypes = [i.typeName for i in acceptable_datatypes]
            current_datatype = (
                validation_df.select(validation_column).schema[0].dataType.typeName
            )
            if current_datatype in datatypes:
                return func(*args, **kwargs)
            else:
                raise TypeError(
                    f"The function only accepts the following datatypes {acceptable_datatypes}"
                    f" but got {current_datatype}"
                )

        return _wrapper

    return wrapper


@register_builtin_check(
    aliases=["eq"],
    error="equal_to({value})",
)
@register_input_datatypes(acceptable_datatypes=[pst.LongType, pst.IntegerType])
def equal_to(data: PysparkDataframeColumnObject, value: Any) -> bool:
    """Ensure all elements of a data container equal a certain value.

    :param value: values in this DataFrame data structure must be
        equal to this value.
    """
    breakpoint()
    # validate_datatypes(data, [pst.LongType, pst.IntegerType])
    cond = col(data.column_name) == value
    return data.dataframe.filter(~cond).limit(1).count() == 0


@register_builtin_check(
    aliases=["ne"],
    strategy=st.ne_strategy,
    error="not_equal_to({value})",
)
def not_equal_to(data: PysparkDataframeColumnObject, value: Any) -> bool:
    """Ensure no elements of a data container equals a certain value.

    :param value: This value must not occur in the checked
        :class:`pandas.Series`.
    """
    breakpoint()
    cond = col(data.column_name) != value
    return data.dataframe.filter(~cond).limit(1).count() == 0


@register_builtin_check(
    aliases=["gt"],
    error="greater_than({min_value})",
)
def greater_than(data: PysparkDataframeColumnObject, min_value: Any) -> bool:
    """
    Ensure values of a data container are strictly greater than a minimum
    value.

    :param min_value: Lower bound to be exceeded.
    """
    breakpoint()
    cond = col(data.column_name) > min_value
    return data.dataframe.filter(~cond).limit(1).count() == 0


@register_builtin_check(
    aliases=["ge"],
    strategy=st.ge_strategy,
    error="greater_than_or_equal_to({min_value})",
)
def greater_than_or_equal_to(
    data: PysparkDataframeColumnObject, min_value: Any
) -> bool:
    """Ensure all values are greater or equal a certain value.

    :param min_value: Allowed minimum value for values of a series. Must be
        a type comparable to the dtype of the :class:`pandas.Series` to be
        validated.
    """
    cond = col(data.column_name) >= min_value
    return data.dataframe.filter(~cond).limit(1).count() == 0


@register_builtin_check(
    aliases=["lt"],
    strategy=st.lt_strategy,
    error="less_than({max_value})",
)
def less_than(data: PysparkDataframeColumnObject, max_value: Any) -> bool:
    """Ensure values of a series are strictly below a maximum value.

    :param max_value: All elements of a series must be strictly smaller
        than this. Must be a type comparable to the dtype of the
        :class:`pandas.Series` to be validated.
    """
    if max_value is None:
        raise ValueError("max_value must not be None")
    cond = col(data.column_name) < max_value
    return data.dataframe.filter(~cond).limit(1).count() == 0


@register_builtin_check(
    aliases=["le"],
    strategy=st.le_strategy,
    error="less_than_or_equal_to({max_value})",
)
def less_than_or_equal_to(data: PysparkDataframeColumnObject, max_value: Any) -> bool:
    """Ensure values of a series are strictly below a maximum value.

    :param max_value: Upper bound not to be exceeded. Must be a type
        comparable to the dtype of the :class:`pandas.Series` to be
        validated.
    """
    if max_value is None:
        raise ValueError("max_value must not be None")
    cond = col(data.column_name) <= max_value
    return data.dataframe.filter(~cond).limit(1).count() == 0


# Todo - Need to be discussed
@register_builtin_check(
    aliases=["between"],
    strategy=st.in_range_strategy,
    error="in_range({min_value}, {max_value})",
)
def in_range(
    data: PysparkDataframeColumnObject,
    min_value: T,
    max_value: T,
    include_min: bool = True,
    include_max: bool = True,
):
    """Ensure all values of a series are within an interval.

    Both endpoints must be a type comparable to the dtype of the
    :class:`pandas.Series` to be validated.

    :param min_value: Left / lower endpoint of the interval.
    :param max_value: Right / upper endpoint of the interval. Must not be
        smaller than min_value.
    :param include_min: Defines whether min_value is also an allowed value
        (the default) or whether all values must be strictly greater than
        min_value.
    :param include_max: Defines whether min_value is also an allowed value
        (the default) or whether all values must be strictly smaller than
        max_value.
    """
    # Using functions from operator module to keep conditions out of the
    # closure
    cond_right = (
        col(data.column_name) >= min_value
        if include_min
        else col(data.column_name) > min_value
    )
    cond_left = (
        col(data.column_name) <= max_value
        if include_max
        else col(data.column_name) < max_value
    )
    return data.dataframe.filter(~(cond_right & cond_left)).limit(1).count() == 0  # type: ignore


@register_builtin_check(
    strategy=st.isin_strategy,
    error="isin({allowed_values})",
)
def isin(data: PysparkDataframeColumnObject, allowed_values: Iterable) -> bool:
    """Ensure only allowed values occur within a series.

    This checks whether all elements of a :class:`pandas.Series`
    are part of the set of elements of allowed values. If allowed
    values is a string, the set of elements consists of all distinct
    characters of the string. Thus only single characters which occur
    in allowed_values at least once can meet this condition. If you
    want to check for substrings use :meth:`Check.str_contains`.

    :param allowed_values: The set of allowed values. May be any iterable.
    :param kwargs: key-word arguments passed into the `Check` initializer.
    """
    return (
        data.dataframe.filter(~col(data.column_name).isin(list(allowed_values)))
        .limit(1)
        .count()
        == 0
    )


@register_builtin_check(
    strategy=st.notin_strategy,
    error="notin({forbidden_values})",
)
def notin(data: PysparkDataframeColumnObject, forbidden_values: Iterable) -> bool:
    """Ensure some defined values don't occur within a series.

    Like :meth:`Check.isin` this check operates on single characters if
    it is applied on strings. If forbidden_values is a string, it is understood
    as set of prohibited characters. Any string of length > 1 can't be in it by
    design.

    :param forbidden_values: The set of values which should not occur. May
        be any iterable.
    :param raise_warning: if True, check raises UserWarning instead of
        SchemaError on validation.
    """
    return (
        data.dataframe.filter(col(data.column_name).isin(list(forbidden_values)))
        .limit(1)
        .count()
        == 0
    )


# TODO: expensive check
@register_builtin_check(
    strategy=st.str_contains_strategy,
    error="str_contains('{pattern}')",
)
def str_contains(
    data: PysparkDataframeColumnObject, pattern: Union[str, re.Pattern]
) -> bool:
    """Ensure that a pattern can be found within each row.

    :param pattern: Regular expression pattern to use for searching
    :param kwargs: key-word arguments passed into the `Check` initializer.
    """

    return (
        data.dataframe.filter(~col(data.column_name).rlike(pattern.pattern))
        .limit(1)
        .count()
        == 0
    )


@register_builtin_check(
    error="str_startswith('{string}')",
)
def str_startswith(data: PysparkDataframeColumnObject, string: str) -> bool:
    """Ensure that all values start with a certain string.

    :param string: String all values should start with
    :param kwargs: key-word arguments passed into the `Check` initializer.
    """
    cond = col(data.column_name).startswith(string)
    return data.dataframe.filter(~cond).limit(1).count() == 0


@register_builtin_check(
    strategy=st.str_endswith_strategy, error="str_endswith('{string}')"
)
def str_endswith(data: PysparkDataframeColumnObject, string: str) -> bool:
    """Ensure that all values end with a certain string.

    :param string: String all values should end with
    :param kwargs: key-word arguments passed into the `Check` initializer.
    """
    cond = col(data.column_name).endswith(string)
    return data.dataframe.filter(~cond).limit(1).count() == 0
