"""General maya utility decorators."""

import functools
import logging

from maya import cmds

_LOGGER = logging.getLogger(__name__)


def disable_scanner_callbacks(func):
    """Disable maya scanner callbacks.

    These sometimes seem to cause maya to segfault on import reference,
    so this decorater can be used to temporarily disable them.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _scanner_disable_func(*args, **kwargs):
        cmds.unloadPlugin('MayaScannerCB')
        _result = func(*args, **kwargs)
        cmds.loadPlugin('MayaScannerCB')
        return _result

    return _scanner_disable_func


def get_ns_cleaner(namespace, delete=False):
    """Build a decorator which runs a function in a namespace.

    The namespace is flushed before execution.

    Args:
        namespace (str): namespace to apply
        delete (bool): remove namespace after use

    Returns:
        (fn): namespace cleaner
    """

    def _ns_cleaner(func):

        @functools.wraps(func)
        def _ns_clean_fn(*args, **kwargs):
            from .mu_namespace import set_namespace, del_namespace
            set_namespace(namespace, clean=True)
            try:
                _result = func(*args, **kwargs)
            finally:
                set_namespace(":")
            if delete:
                del_namespace(namespace, force=True)
            return _result

        return _ns_clean_fn

    return _ns_cleaner


def hide_img_planes(func):
    """Decorator which temporarily hides images planes on function execute.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _hide_img_planes_func(*args, **kwargs):

        from maya_pini import open_maya as pom
        _LOGGER.debug('HIDE IMAGE PLANES')

        _hidden = []
        for _img in pom.find_nodes(type_='imagePlane'):
            _tfm = _img.to_parent()
            if _tfm.visibility.get_val():
                _hidden.append(_tfm)
                _tfm.visibility.set_val(False)
        _LOGGER.debug(' - HID %d IMAGE PLANES', len(_hidden))

        try:
            _result = func(*args, **kwargs)
        finally:
            _LOGGER.debug(' - UNHIDING %d IMAGE PLANES', len(_hidden))
            for _tfm in _hidden:
                _tfm.visibility.set_val(True)

        return _result

    return _hide_img_planes_func


def pause_viewport(func):
    """Decorator which pauses viewports during function execution.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _pause_viewport_func(*args, **kwargs):
        _paused = cmds.ogs(query=True, pause=True)
        if not _paused:
            cmds.ogs(pause=True)
        try:
            return func(*args, **kwargs)
        finally:
            if not _paused:
                cmds.ogs(pause=True)

    return _pause_viewport_func


def reset_ns(func):
    """Restore the root namespace after executing a function.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _reset_ns_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            cmds.namespace(set=':')

    return _reset_ns_func


def reset_sel(func):
    """Clear selection after executing a function.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _reset_sel_func(*args, **kwargs):
        _result = func(*args, **kwargs)
        cmds.select(clear=True)
        return _result

    return _reset_sel_func


def restore_ns(func):
    """Restore the current namespace after executing the function.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _restore_ns_func(*args, **kwargs):
        _ns = ':'+cmds.namespaceInfo(currentNamespace=True)
        try:
            return func(*args, **kwargs)
        finally:
            if cmds.namespace(exists=_ns):
                cmds.namespace(set=_ns)

    return _restore_ns_func


def restore_frame(func):
    """Restore the current frame after executing the function.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _restore_frame_func(*args, **kwargs):
        _frame = cmds.currentTime(query=True)
        _result = func(*args, **kwargs)
        cmds.currentTime(_frame)
        return _result

    return _restore_frame_func


def restore_sel(func):
    """Restore current selection after executing function.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    @functools.wraps(func)
    def _restore_sel_fn(*args, **kwargs):
        _sel = cmds.ls(selection=True)
        _result = func(*args, **kwargs)
        _sel = [_node for _node in _sel if cmds.objExists(_node)]
        if _sel:
            cmds.select(_sel)
        return _result

    return _restore_sel_fn


def use_tmp_ns(func):
    """Execute the given function in :tmp namespace.

    The namespace is flushed before use.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """
    return get_ns_cleaner(':tmp')(func)
