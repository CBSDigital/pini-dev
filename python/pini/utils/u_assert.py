"""Assertion tools.

These make an assertion and displays information about the failure
if it is not met.
"""


def assert_eq(item_a, item_b, dp=None):  # pylint: disable=invalid-name
    """Assert two objects are equal.

    Args:
        item_a (any): first item
        item_b (any): second item
        dp (int): number of decimal places in accuracy
    """
    _item_a = item_a
    _item_b = item_b
    if dp is not None:
        _item_a = round(_item_a, dp)
        _item_b = round(_item_b, dp)
    if _item_a != _item_b:
        raise AssertionError(
            f'Item {item_a} is not equal to {item_b}')
