"""Utilities relating to functions."""

import functools
import types


def chain_fns(*args):
    """Build a function which executes a list of functions in sequence.

    Returns:
        (fn): chained function
    """
    _args = args
    if len(_args) == 1 and isinstance(_args[0], (list, tuple)):
        _args = _args[0]

    # Catch args not funcs
    _fn_types = (
        types.FunctionType, types.MethodType, types.BuiltinMethodType)
    for _arg in _args:
        if not isinstance(_arg, _fn_types):
            raise TypeError(f'Arg is not function - {_arg}')

    def _chained_fn(*xargs):
        del xargs
        for _fn in _args:
            _fn()

    return _chained_fn


def null_fn(*xargs, **xkwargs):  # pylint: disable=unused-argument
    """Function which does nothing.

    Placeholder for instance where callback is required, but no action
    is needed.
    """


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
