"""General utils relating to scene callbacks."""

import copy
import logging

import nuke

_LOGGER = logging.getLogger(__name__)


def add_knob_changed_callback(callback, node_class):
    """Add a knob changed callback.

    Any existing callbacks with the same name are replaced.

    Args:
        callback (fn): callback to add
        node_class (str): node class which callback applies to
    """
    flush_knob_changed_callback(callback, node_class=node_class)
    nuke.addKnobChanged(callback, nodeClass=node_class)


def add_script_load_callback(callback):
    """Add a script load callback.

    Any existing instance of this callback are replaced.

    Args:
        callback (fn): callback to add
    """
    flush_script_load_callback(callback)
    nuke.addOnScriptLoad(callback)


def add_script_save_callback(callback):
    """Add a script save callback.

    Any existing instance of this callback are replaced.

    Args:
        callback (fn): callback to add
    """
    flush_script_save_callback(callback)
    nuke.addOnScriptSave(callback)


def flush_knob_changed_callback(callback, node_class):
    """Remove instances the given knob changed callback.

    Args:
        callback (fn): callback to remove
        node_class (str): node class which callback applies to
    """
    _callbacks = nuke.callbacks.knobChangeds.get(node_class, [])
    for _item in copy.copy(_callbacks):
        _func, _, _, _ = _item
        if _func.__name__ == callback.__name__:
            _callbacks.remove(_item)
            _LOGGER.debug(' - REMOVE EXISTING KNOB CHANGED')


def flush_script_load_callback(callback):
    """Remove any instances of the given script load callback.

    Args:
        callback (str): callback to remove
    """
    _on_loads = nuke.callbacks.onScriptLoads.get('Root', [])
    for _item in copy.copy(_on_loads):
        _func, _, _, _ = _item
        if _func.__name__ == callback.__name__:
            _on_loads.remove(_item)
            _LOGGER.debug(' - REMOVE EXISTING ON LOAD')


def flush_script_save_callback(callback):
    """Remove any instances of the given script save callback.

    Args:
        callback (str): callback to remove
    """
    _on_saves = nuke.callbacks.onScriptSaves.get('Root', [])
    for _item in copy.copy(_on_saves):
        _func, _, _, _ = _item
        if _func.__name__ == callback.__name__:
            _on_saves.remove(_item)
            _LOGGER.debug(' - REMOVE EXISTING ON SAVE')
