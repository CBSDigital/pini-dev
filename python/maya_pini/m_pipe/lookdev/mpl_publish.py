"""Tools for managing lookdev publishes."""

import collections
import logging
import re

from maya import cmds

from maya_pini import open_maya as pom
from maya_pini.utils import to_clean, to_long, to_namespace, to_parent

_LOGGER = logging.getLogger(__name__)


def read_ai_override_sets(crop_namespace=True):
    """Read ai override sets.

    This is any set contained in override_SET.

    Args:
        crop_namespace (bool): remove namespace from geos

    Returns:
        (dict): set/geos
    """
    _data = {}

    if cmds.objExists('overrides_SET'):

        # Read sets to export
        _over_set = pom.CNode('overrides_SET')
        _sets = [_over_set]
        for _item in pom.CMDS.sets(_over_set, query=True):
            if _item.object_type() == 'objectSet':
                _sets.append(_item)

        for _set in _sets:
            _geos = set()
            for _item in pom.CMDS.sets(_set, query=True):
                if _item.object_type() != 'objectSet':
                    _geos.add(_item.clean_name if crop_namespace else _item)
            if not _geos:
                continue
            _data[str(_set)] = sorted(_geos)

    return _data


def _read_clean_shd_assignments():
    """Read relevant shaders from the current scene assignments.

    Returns:
        (dict): {shader: shading engine/geos} assignment data
    """
    _shds = {}
    for _shd, _data in read_shader_assignments().items():
        _data['geos'] = [to_clean(_geo) for _geo in _data['geos']]
        _shds[_shd] = _data
    return _shds


def _read_custom_aovs(sgs):
    """Read custom aovs set up in this scene.

    There are connected to the indexed aiCustomAOVs attribute on the
    shading group, each one having a name (aovName) and colour connection
    (aovInput). On reference, maya will automatically rebuild these
    connections if the aov exists in the current scene.

    However since, since they are stored as indexes, the reference
    edits can get confused, and end up being connected to the wrong
    aov name. To avoid this, the input connection and aov name are
    stored on lookdev publish.

    Args:
        sgs (str list): shading groups to check

    Returns:
        (tuple list): plug/name list
    """
    _LOGGER.debug('READ CUSTOM AOVS')
    _custom_aovs = []
    for _sg in sgs:
        _sg = pom.CNode(_sg)
        _LOGGER.debug(' - CHECKING SG %s', _sg)
        _conn = _sg.plug['aiCustomAOVs'].find_incoming(connections=True)
        if _conn:
            _src, _dest = _conn
            _, _idx, _ = re.split(r'[\[\]]', str(_dest))
            _idx = int(_idx)
            _name = _sg.attr['aiCustomAOVs[{:d}].aovName'.format(_idx)]
            _aov = str(cmds.getAttr(_name))
            _custom_aovs.append((str(_src), str(_aov)))
    return _custom_aovs


def _read_geo_settings():
    """Read attribute setting overrides to apply to lighting scenes.

    Returns:
        (dict): settings data
    """
    _LOGGER.debug('READ SETTINGS')

    _settings = collections.defaultdict(dict)

    # Find shapes
    _shds = read_shader_assignments()
    _geos = sum([_data['geos'] for _data in _shds.values()], [])
    for _geo in _geos:

        _LOGGER.debug(' - CHECKING GEO %s', _geo)
        try:
            _geo = pom.CMesh(_geo)
        except ValueError:
            _LOGGER.debug('   - FAILED TO BUILD MESH')
            continue
        _LOGGER.debug('   - MESH %s %s', _geo, _geo.shp)
        if not _geo.shp:
            continue

        # Read non-default settings
        for _attr in [
                'aiOpaque',
                'aiSubdivIterations',
                'aiSubdivType',
        ]:
            _plug = _geo.shp.plug[_attr]
            _def = _plug.get_default()
            _val = _plug.get_val()
            if _val != _def:
                _settings[str(_geo)][_attr] = _val

    _settings = dict(_settings)
    return _settings


def read_publish_metadata():
    """Read all shading data to save to yml file.

    This includes shader assignments and settings overrides.

    Returns:
        (dict): shading data
    """
    _shds = _read_clean_shd_assignments()
    _sgs = [_shd_data['shadingEngine'] for _shd_data in _shds.values()]

    # Gather data
    _data = {}
    _data['shds'] = _shds
    _data['settings'] = _read_geo_settings()
    _data['custom_aovs'] = _read_custom_aovs(sgs=_sgs)
    _data['ai_override_sets'] = read_ai_override_sets()

    return _data


def read_shader_assignments(
        allow_face_assign=False, allow_referenced=False, catch=True):
    """Read shader assignments data.

    This data relates to the current scene. Namespaces are removed
    before it's written to disk.

    Args:
        allow_face_assign (bool): do not ignore face assignments (eg. for
            speed tree assets)
        allow_referenced (bool): include referenced shaders
        catch (bool): no error if no shaders found

    Returns:
        (dict): shader assignments
    """
    _LOGGER.debug('READ SHD ASSIGNMENTS')
    _data = {}
    _ses = pom.find_nodes(type_='shadingEngine')
    for _se in _ses:

        _LOGGER.debug('SHADING ENGINE %s', _se)
        _shd_data = {'shadingEngine': str(_se)}

        # Read shader
        _shd = _se.plug['surfaceShader'].find_incoming(plugs=False)
        _LOGGER.debug(' - SHD %s %d', _shd, bool(_shd))
        if not _shd:
            _LOGGER.debug(' - NO SHADER')
            continue
        if not allow_referenced and _shd.is_referenced():
            _LOGGER.debug(' - IGNORING REFERENCED')
            continue

        # Find geos
        _geo_ss = cmds.sets(_se, query=True) or []
        _LOGGER.debug(' - GEO SHPS (A) %d %s', len(_geo_ss), _geo_ss)
        _geo_ss = sorted(set(
            _geo_s for _geo_s in _geo_ss
            if not to_namespace(_geo_s) == 'lookdevRig' and  # Ignore lookdev
            not to_long(_geo_s).startswith('|JUNK|')  # Ignore junk
        ))
        _LOGGER.debug(' - GEO SHPS (B) %d %s', len(_geo_ss), _geo_ss)
        if not allow_face_assign:
            _geo_ss = [_geo_s for _geo_s in _geo_ss if '.' not in _geo_s]
            _LOGGER.debug(' - GEO SHPS (C) %d %s', len(_geo_ss), _geo_ss)
        _geos = [to_parent(_geo_s) for _geo_s in _geo_ss]
        _LOGGER.debug(' - GEOS (X) %s', _geos)
        if not _geos:
            continue
        _shd_data['geos'] = _geos

        # Read ai surface shader
        _ai_ss = _se.plug['aiSurfaceShader'].find_incoming(plugs=False)
        _shd_data['ai_shd'] = str(_ai_ss) if _ai_ss else None

        _data[str(_shd)] = _shd_data

    if not catch and not _data:
        raise RuntimeError('No shader assignments found')

    return _data
