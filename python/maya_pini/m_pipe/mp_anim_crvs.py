"""Tools for managing curves ma/mb exports."""

import logging

from maya import cmds

from pini import pipe
from pini.dcc import export

from maya_pini.utils import (
    save_scene, reset_ns, set_namespace, del_namespace)

_LOGGER = logging.getLogger(__name__)


@reset_ns
def export_anim_curves(rigs, range_=None, force=False):
    """Export anim curves from given rigs.

    Args:
        rigs (CReference list): rigs to export
        range_ (tuple): override export range
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): curves outputs
    """
    _work = pipe.CACHE.obt_cur_work()

    if range_:
        raise NotImplementedError

    _outs = []
    for _rig in rigs:
        _LOGGER.info(' - RIG %s', _rig)
        assert _rig.ctrls
        _out = _work.to_output('cache', output_name=_rig.namespace, extn='mb')
        _metadata = export.build_metadata('CMayaCurvesCache', src_ref=_rig.path)

        # Build tmp curves
        _tmp_ns = f':AnimTmp_{_rig.namespace}'
        set_namespace(_tmp_ns)
        _export_crvs = []
        for _plug in _rig.plugs:
            _export_crv = _obt_export_crv(_plug)
            if _export_crv:
                _export_crvs.append(_export_crv)
        _LOGGER.info(' - BUILD %d EXPORT CRVS', len(_export_crvs))

        # Save to disk
        cmds.select(_export_crvs)
        save_scene(_out, selection=True, force=force)
        del_namespace(_tmp_ns, force=True)
        _LOGGER.info(' - WROTE %s', _out)
        _outs.append(_out)

    return _outs


def _obt_export_crv(plug):
    """Obtain tmp export curve for the given plug.

    Args:
        plug (CPlug): plug to read anim from

    Returns:
        (CAnimCurve): curve
    """
    _LOGGER.debug('OBT EXPORT CRV %s', plug)

    _anim = plug.to_anim()
    _LOGGER.debug(' - ANIM %s', _anim)
    if _anim:
        _crv = _anim.duplicate(return_roots_only=False)
    else:
        _lock = False
        if plug.is_locked():
            _lock = True
            plug.unlock()
        plug.set_key()
        _crv = plug.to_anim()
        if not _crv:
            _type = plug.get_type()
            _LOGGER.debug(' - NO CURVE type=%s', _type)
            if _type in ('message', ):
                return None
            raise RuntimeError(f'Missing curve {plug} ({_type})')
        _LOGGER.debug(' - SET KEY %s', _crv)
        plug.break_conns()
        assert _crv.exists()
        if _lock:
            plug.set_locked(True)

        # _crv.
        # asdasd
    _LOGGER.debug(' - CRV %s', _crv)
    # assert to_clean(_crv) == to_clean(plug)
    _crv.add_attr('SrcNode', plug.to_node().to_clean())
    _crv.add_attr('SrcAttr', plug.attr)

    _crv.output.break_conns()

    return _crv
