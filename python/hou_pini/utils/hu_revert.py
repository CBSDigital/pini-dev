"""Tools for managing the hou pini revert decorator."""

import functools

import hou

from pini.utils import single


def revert(pwd=False, sel=False):
    """Decorator which reverts the scene to the state before exec.

    Args:
        pwd (bool): revert present working folder
        sel (bool): revert selection

    Returns:
        (fn): decorator
    """

    def _revert_dec(func):

        @functools.wraps(func)
        def _revert_func(*args, **kwargs):

            # Read state
            _pwd = _sel = None
            if pwd:
                _pwd = hou.pwd()
            if sel:
                _sel = single(hou.selectedNodes(), catch=True)

            # Exec func
            _result = func(*args, **kwargs)

            # Apply state
            if _pwd:
                hou.setPwd(_pwd)
            if _sel:
                _sel.setSelected(True)

            return _result

        return _revert_func

    return _revert_dec
