"""Tools for managing curves ma/mb exports."""

import logging
import time

from maya import cmds

from pini import pipe, dcc, qt
from pini.dcc import export
from pini.utils import single

from maya_pini import open_maya as pom
from maya_pini.utils import (
    save_scene, reset_ns, set_namespace, del_namespace)

_LOGGER = logging.getLogger(__name__)


@reset_ns
def export_anim_curves(rigs, frames=None, force=False):
    """Export anim curves from given rigs.

    Args:
        rigs (CReference list): rigs to export
        frames (tuple): override frames
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): curves outputs
    """
    _work = pipe.CACHE.obt_cur_work()

    _outs = []
    for _rig in qt.progress_bar(
            rigs, 'Exporting {:d} rig{}', stack_key='CurvesExport'):
        _LOGGER.info(' - RIG %s', _rig)
        assert _rig.ctrls
        _out = _work.to_output('cache', output_name=_rig.namespace, extn='mb')
        _metadata = export.build_metadata('CMayaCurvesCache', src_ref=_rig.path)

        # Build tmp curves
        _tmp_ns = f':AnimTmp_{_rig.namespace}'
        set_namespace(_tmp_ns)
        _export_crvs = []
        for _plug in qt.progress_bar(
                _rig.plugs, f'Reading {{:d}} plug{{}} - {_rig.namespace}',
                stack_key='ReadPlugs'):
            _export_crv = _obt_export_crv(_plug, frames=frames)
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


def _obt_export_crv(plug, frames=None):
    """Obtain tmp export curve for the given plug.

    Args:
        plug (CPlug): plug to read anim from
        frames (tuple): frames to cache on (for connected plugs)

    Returns:
        (CAnimCurve): curve
    """
    _LOGGER.debug('OBT EXPORT CRV %s', plug)

    _src_crv = plug.to_anim()
    _LOGGER.debug(' - SRC CRV %s', _src_crv)
    _exp_crv = None

    # Try simple duplicate anim
    if _src_crv:
        _exp_crv = _src_crv.duplicate(return_roots_only=False)

    # Try simple add key for unconnected
    if not _exp_crv and not plug.find_incoming():
        _exp_crv = _build_exp_crv_for_unkeyed(plug)

    # Need to read anim
    if not _exp_crv:
        _exp_crv = _build_exp_crv_for_driven(plug, frames=frames)

    _LOGGER.debug(' - EXP CRV %s', _exp_crv)
    _exp_crv.add_attr('SrcNode', plug.to_node().to_clean())
    _exp_crv.add_attr('SrcAttr', plug.attr)

    _exp_crv.output.break_conns()

    return _exp_crv


def _build_exp_crv_for_unkeyed(plug):
    """Build export anim curve for unkeyed plug.

    ie. build a curve with one key.

    Args:
        plug (CPlug): unkeyed plug

    Returns:
        (CAnimCurve): export curve
    """
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

    return _crv


def _build_exp_crv_for_driven(plug, frames=None):
    """Build export curve for driven plug.

    Reads plug animation on every frame and creates anim curve.

    Args:
        plug (CPlug): plug to read
        frames (float list): frames to read values on

    Returns:
        (CAnimCurve): export curve
    """
    _LOGGER.debug(' - READ ANIM')
    _frames = frames or dcc.t_frames()

    # Build anim curve
    _plug_type = plug.get_type()
    _type_map = {
        'bool': 'animCurveTU',
        'double': 'animCurveTL',
        'doubleLinear': 'animCurveTL',
        'doubleAngle': 'animCurveTA',
    }
    if _plug_type not in _type_map:
        raise RuntimeError(f'Unmapped type {_plug_type} - {plug}')
    _crv_type = _type_map[_plug_type]
    _LOGGER.debug(' - ANIM TYPE %s', _crv_type)
    _name = f'{plug.node.to_clean()}_{plug.attr}'
    _exp_crv = pom.CMDS.createNode(_crv_type, name=_name)
    _exp_crv = pom.CAnimCurve(_exp_crv)
    _LOGGER.debug(' - EXP CRV %s', _exp_crv)

    # Apply anim
    _start = time.time()
    _ktvs = [
        (_frame, cmds.getAttr(plug, time=_frame))
        for _frame in _frames]
    _vals = {_val for _frame, _val in _ktvs}
    if len(_vals) == 1:
        _LOGGER.debug(' - CROPPING STATIC VALUE')
        _ktvs = [(dcc.t_start(), single(_vals))]
    _LOGGER.debug(' - KTVS %s', _ktvs)
    for _frame, _val in _ktvs:
        cmds.setKeyframe(
            _exp_crv, value=_val, time=_frame, inTangentType='spline',
            outTangentType='spline')
    _dur = time.time() - _start
    _LOGGER.debug(
        ' - READ/APPLIED %d VALS (%d KEYS) IN %.03fs', len(_frames),
        len(_ktvs), _dur)

    return _exp_crv
