"""Pandas backend utilities."""
from __future__ import annotations


from pandera.dtypes import UniqueSettings


def convert_uniquesettings(unique: UniqueSettings) -> bool | str:
    """
    Converts UniqueSettings object to string that can be passed onto pandas .duplicated() call
    """
    # Default `keep` argument for pandas .duplicated() function
    keep_argument: bool | str
    if unique == "exclude_first":
        keep_argument = "first"
    elif unique == "exclude_last":
        keep_argument = "last"
    elif unique == "all":
        keep_argument = False
    else:
        raise ValueError(
            str(unique) + " is not a recognized report_duplicates value"
        )
    return keep_argument
