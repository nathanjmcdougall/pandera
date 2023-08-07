"""Base module for `hypothesis`-based strategies for data synthesis."""
from __future__ import annotations

from typing import Callable, Dict, Tuple, Type

# This strategy registry maps (check_name, data_type) -> strategy_function
# For example: ("greater_than", pd.DataFrame) -> (<function gt_strategy>)
STRATEGY_DISPATCHER: Dict[Tuple[str, Type], Callable] = {}
