"""Utilities relating to functions."""

import functools
import types


def chain_fns(*args):
    """Build a function which executes a list of functions in sequence.

    Returns:
        (fn): chained function
    """

    # Catch args not funcs
    _fn_types = (types.FunctionType, types.MethodType,
                 types.BuiltinMethodType)
    for _arg in args:
        if not isinstance(_arg, _fn_types):
            raise TypeError('Arg is not function - {}'.format(_arg))

    def _chained_fn(*xargs):
        del xargs
        for _fn in args:
            _fn()

    return _chained_fn


def null_fn(*xargs, **xkwargs):
    """Function which does nothing.

    Placeholder for instance where callback is required, but no action
    is needed.
    """
    del xargs, xkwargs  # For linter


def wrap_fn(func, *args, **kwargs):
    """Provide a function which wraps the given args/kwargs to the given func.

    Args:
        func (str): function to wrap

    Returns:
        (func): wrapped function (which takes no args)
    """

    @functools.wraps(func)
    def _wrapped_fn(*xargs, **xkwargs):
        del xargs, xkwargs  # For linter
        return func(*args, **kwargs)

    return _wrapped_fn
