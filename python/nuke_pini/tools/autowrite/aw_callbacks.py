"""Tools for managing autowrite 2.0 callbacks."""

import logging

import nuke

from pini import pipe

from nuke_pini.utils import (
    flush_knob_changed_callback, add_knob_changed_callback,
    flush_script_save_callback, add_script_save_callback,
    flush_script_load_callback, add_script_load_callback)

from . import aw_node

_LOGGER = logging.getLogger(__name__)
_DISABLE_KNOB_CHANGED = False


def flush_callbacks():
    """Remove all callbacks."""
    flush_script_load_callback(_safe_update_all)
    flush_script_save_callback(_safe_update_all)
    flush_knob_changed_callback(_safe_knob_changed_callback, node_class='Write')


def install_callbacks():
    """Remove all callbacks."""
    _LOGGER.info('INSTALL CALLBACKS')
    add_script_save_callback(_safe_update_all)
    add_script_load_callback(_safe_update_all)
    add_knob_changed_callback(_safe_knob_changed_callback, node_class='Write')
    _LOGGER.info(' - INSTALL CALLBACKS COMPLETE')


def _safe_update_all():
    """Update all autowrite nodes without erroring."""
    try:
        update_all()
    except Exception as _exc:  # pylint: disable=broad-except
        _LOGGER.warning('UPDATE AUTOWRITES FAILED %s', _exc)


def update_all():
    """Update all autowrite nodes."""

    # Find autowrite2 nodes
    _aw2s = []
    for _grp in nuke.allNodes('Write'):
        try:
            _aw2 = aw_node.CAutowrite(_grp)
        except ValueError:
            continue
        _aw2s.append(_aw2)
    if not _aw2s:
        return

    _LOGGER.info('AUTOWRITE2 UPDATE ALL')

    global _DISABLE_KNOB_CHANGED
    _DISABLE_KNOB_CHANGED = True

    # Check pipe cache is up to date - may not have been updated yet
    # if this is triggered by save callback
    _cur_work = pipe.cur_work()
    _LOGGER.debug(' - CUR WORK %s', _cur_work)
    if (
            _cur_work and
            pipe.cur_work() not in pipe.CACHE.cur_work_dir.works):
        _cur_work.touch()  # Save callback happens before work created
        _LOGGER.debug(' - UPDATE PIPE CACHE NEEDED')
        _LOGGER.debug(' - CUR WORK DIR %s', pipe.CACHE.cur_work_dir)
        assert pipe.CACHE.cur_work_dir
        pipe.CACHE.cur_work_dir.find_works(force=True)
        _LOGGER.debug(' - CUR WORK exists=%d %s', pipe.cur_work().exists(),
                      pipe.CACHE.cur_work)
        assert pipe.CACHE.cur_work
        _LOGGER.debug(' - UPDATED PIPE CACHE')

    _LOGGER.debug(' - FOUND %d AUTOWRITE2S %s', len(_aw2s), _aw2s)
    _LOGGER.debug(' - WORK (c) %s', pipe.CACHE.cur_work)
    _LOGGER.debug(' - WORK (l) %s', pipe.cur_work())

    for _aw2 in _aw2s:
        _aw2.update()

    _DISABLE_KNOB_CHANGED = False


def _safe_knob_changed_callback():
    """Update all autowrite nodes without erroring."""
    try:
        knob_changed_callback()
    except Exception as _exc:  # pylint: disable=broad-except
        _LOGGER.warning('AUTOWRITE KNOB CHANGED FAILED %s', _exc)


def knob_changed_callback(knob=None, node=None):
    """Callback triggered by knob changed.

    Args:
        knob (Knob): override knob
        node (Nde): override node
    """
    global _DISABLE_KNOB_CHANGED

    _LOGGER.debug('KNOB CHANGED CALLBACK disabled=%d', _DISABLE_KNOB_CHANGED)
    if _DISABLE_KNOB_CHANGED:
        return

    _knob = knob or nuke.thisKnob()
    _node = node or nuke.thisNode()

    # Ignore attrs by name
    _name = _knob.name()
    _LOGGER.debug(' - KNOB %s', _knob.fullyQualifiedName())
    if _name in [
            'hidePanel', 'showPanel', 'frame_mode',
            'selected',
            'xpos', 'ypos',
    ]:
        return

    # Update if autowrite
    try:
        _auto = aw_node.CAutowrite(_node)
    except ValueError:
        return
    _LOGGER.info('AUTO2 KNOB CHANGED %s.%s', _node.name(), _knob.name())
    _DISABLE_KNOB_CHANGED = True
    _auto.knob_changed_callback(_knob)
    _DISABLE_KNOB_CHANGED = False
