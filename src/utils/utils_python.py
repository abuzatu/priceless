"""Python module for utils in python in general."""

# python modules
from typing import List


def get_quarter_of_of_list(my_list: List[str], quarter: int) -> List[str]:
    """Get a specific quarter of the list of strings.

    Args:
        quarter (int): The quarter to retrieve (1, 2, 3, or 4).

    Returns:
        List[str]: The specified quarter of the list of strings.
    """
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("Quarter must be 1, 2, 3, or 4.")

    total_strategies = len(my_list)
    quarter_size = total_strategies // 4

    if quarter == 1:
        return my_list[:quarter_size]
    elif quarter == 2:
        return my_list[quarter_size : 2 * quarter_size]
    elif quarter == 3:
        return my_list[2 * quarter_size : 3 * quarter_size]
    elif quarter == 4:
        return my_list[3 * quarter_size :]
    else:
        raise ValueError("Quarter must be 1, 2, 3, or 4.")
