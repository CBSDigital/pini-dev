"""Assertion tools.

These make an assertion and displays information about the failure
if it is not met.
"""


def assert_eq(item_a, item_b):
    """Assert two objects are equal.

    Args:
        item_a (any): first item
        item_b (any): second item
    """
    if item_a != item_b:
        raise AssertionError(
            'Item {} is not equal to {}'.format(item_a, item_b))
