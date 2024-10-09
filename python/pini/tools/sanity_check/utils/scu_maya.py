"""General utilies for sanity check in maya."""

import logging

from maya import cmds

from pini.dcc import export_handler
from pini.utils import single, wrap_fn

from maya_pini import open_maya as pom, m_pipe
from maya_pini.utils import to_unique, to_long, to_node

_LOGGER = logging.getLogger(__name__)


def check_set_for_overlapping_nodes(set_, check):
    """Check set for overlapping top nodes.

    If AbcExport is passed a set which contains two nodes which
    are in the same parenting hierarchy then it will error.

    eg. you cannot use |MDL and |MDL|geom in the same cache set.

    Args:
        set_ (str): set node to check
        check (SCCheck): sanity check to add fails to
    """
    _top_nodes = m_pipe.read_cache_set(set_=set_, mode='top')
    _longs = sorted([to_long(_node) for _node in _top_nodes])
    _overlaps = []
    check.write_log(' - longs %s', _longs)
    for _idx, _long in enumerate(_longs[1:], start=1):
        for _o_long in _longs[:_idx]:
            if _long.startswith(_o_long+'|'):
                _overlaps.append((_long, _o_long))
    for _node, _parent in _overlaps:
        _fix = wrap_fn(cmds.sets, _node, remove=set_)
        check.add_fail(
            'In set "{}" the top node "{}" is inside top node "{}" '
            'which will cause abc export to error'.format(
                set_, to_node(_node), to_node(_parent)),
            node=_node, fix=_fix)


def find_cache_set():
    """Find cache set in the current scene.

    If reference mode is set to "import references into root namespace" then a
    referenced cache set is valid.

    Returns:
        (CNode|None): cache set (if any)
    """
    if cmds.objExists('cache_SET'):
        return pom.CNode('cache_SET')
    _refs_mode = export_handler.get_publish_references_mode()
    if _refs_mode is export_handler.ReferencesMode.IMPORT_INTO_ROOT_NAMESPACE:
        _sets = pom.find_nodes(
            type_='objectSet', default=False, clean_name='cache_SET')
        _set = single(_sets, catch=True)
        if _set:
            return _set
    return None


def find_top_level_nodes():
    """Find non-default dag nodes with no parents.

    Returns:
        (str list): top nodes
    """
    return pom.find_nodes(top_node=True, default=False, filter_='-JUNK')


def fix_node_suffix(node, suffix, type_, alts=(), ignore=(), base=None):
    """Provide fix for node suffix fail.

    Args:
        node (str): node with bad suffix
        suffix (str): required suffix (eg. _GEO)
        type_ (str): node type (for fail message - eg. geo)
        alts (tuple): possible altertives values to strip (eg. _Geo, _geo)
        ignore (tuple): suggestions to ignore
        base (str): apply name base/prefix

    Returns:
        (str, fn, str): fail message, fix, name suggestion
    """
    _LOGGER.debug("FIX NODE SUFFIX %s", node)

    _node = pom.cast_node(str(node))
    if _node.is_referenced():
        _msg = ('Referenced {} {} does not have "{}" '
                'suffix'.format(type_, _node, suffix))
        return _msg, None, None

    # Determine base
    _base = base
    if not _base:
        _splitters = [suffix] + list(alts)
        _LOGGER.debug(' - SPLITTERS %s', _splitters)
        for _splitter in _splitters:
            if _splitter in str(_node):
                _new_base = str(_node).rsplit(_splitter, 1)[0]
                if _new_base:
                    _base = _new_base
                    _LOGGER.debug(' - UPDATED BASE %s', _base)
                    break
        else:
            _base = str(_node)
        while _base[-1].isdigit():
            _base = _base[:-1]
    _LOGGER.debug(' - BASE %s', _base)

    # Build suggestion
    _suggestion = to_unique(base=_base, suffix=suffix, ignore=ignore)
    _LOGGER.debug(' - SUGGESTION %s', _suggestion)
    _msg = (
        '{} "{}" does not have "{}" suffix (suggestion: '
        '"{}")'.format(type_.capitalize(), node, suffix, _suggestion))
    _fix = wrap_fn(_node.rename, _suggestion)

    return _msg, _fix, _suggestion


def fix_uvs(geo):
    """Clean up sets.

    All unused uvs sets are deleted and the current one is renamed to map1.

    Args:
        geo (str): geometry to clean
    """
    _LOGGER.debug('FIX UVS %s', geo)

    _cur = single(cmds.polyUVSet(geo, query=True, currentUVSet=True))
    _LOGGER.debug(' - CUR %s', _cur)

    # Make sure current is map1
    if _cur != 'map1':
        _LOGGER.debug(' - COPY CURRENT SET %s -> map1', _cur)
        cmds.polyUVSet(geo, uvSet=_cur, newUVSet='map1', copy=True)
        cmds.polyUVSet(geo, uvSet='map1', currentUVSet=True)
        _cur = single(cmds.polyUVSet(geo, query=True, currentUVSet=True))
    assert _cur == 'map1'

    _sets = cmds.polyUVSet(geo, query=True, allUVSets=True)
    _LOGGER.debug(' - SETS %s', _sets)

    # Make sure current set has values (area)
    if not cmds.polyEvaluate(geo, uvArea=True, uvSetName='map1'):
        _set = single([
            _set for _set in _sets
            if cmds.polyEvaluate(geo, uvArea=True, uvSetName=_set)],
            catch=True)
        if _set:
            _LOGGER.debug(' - SET map1 HAS NO AREA -> USING %s', _set)
            cmds.polyUVSet(geo, uvSet=_set, newUVSet='map1', copy=True)

    # Make sure default (first) set is map1
    if len(_sets) > 1 and not _sets[0] == 'map1':
        cmds.polyUVSet(geo, reorder=True, uvSet='map1', newUVSet=_sets[0])
        _sets = cmds.polyUVSet(geo, query=True, allUVSets=True)
        _LOGGER.debug(' - REORDERED %s', _sets)
    assert _sets[0] == 'map1'

    # Remove unused
    if len(_sets) > 1:
        for _set in _sets:
            if _set == 'map1':
                continue
            _LOGGER.debug(' - REMOVE UNUSED %s', _set)
            try:
                cmds.polyUVSet(geo, delete=True, uvSet=_set)
            except RuntimeError as _exc:
                _LOGGER.error(
                    ' - FAILED TO REMOVE %s (error=%s)', _set,
                    str(_exc).strip())
        _sets = cmds.polyUVSet(geo, query=True, allUVSets=True)
        _LOGGER.debug(' - REMOVED UNUSED remaining=%s', _sets)


def import_referenced_shader(shd):
    """Import referenced shader and apply the imported shader to the geometry.

    Args:
        shd (Shader): shader to import
    """
    _LOGGER.debug('IMPORT SHADER %s', shd)
    _dup = shd.duplicate()
    _LOGGER.debug(' - DUPLICATE SHADER %s', _dup)
    _geos = shd.to_geo()
    _LOGGER.debug(' - APPLY TO %s', _geos)
    _dup.assign_to(_geos)


def is_display_points(node):
    """Test whether the given node is a display points node.

    These nodes are listed as dag nodes but do not appear in outliner
    or have parents.

    Args:
        node (str): node to test

    Returns:
        (bool): whether display points
    """
    _node = pom.CTransform(node)
    if not _node.shp:
        return False
    return _node.shp.object_type() == 'displayPoints'


def read_cache_set_geo(filter_=None):
    """Read cache_SET contents.

    Based on publish references mode, this can contain different values,
    namely whether to include referenced nodes.

    Args:
        filter_ (str): apply filter to list

    Returns:
        (CBaseTransform list): cache set nodes
    """
    _set = find_cache_set()
    _refs_mode = export_handler.get_publish_references_mode()
    _include_referenced = _refs_mode in (
        export_handler.ReferencesMode.LEAVE_INTACT,
        export_handler.ReferencesMode.IMPORT_INTO_ROOT_NAMESPACE)
    return m_pipe.read_cache_set(
        mode='geo', include_referenced=_include_referenced, set_=_set,
        filter_=filter_)


def shd_is_arnold(engine, type_):
    """Test whether the given shader is arnold.

    Args:
        engine (str): shading engine
        type_ (str): shader type

    Returns:
        (bool): whether arnold
    """
    _ai_ss_plug = pom.CNode(engine).plug['aiSurfaceShader']
    _ai_ss = _ai_ss_plug.find_incoming(plugs=False)
    if _ai_ss:
        return False
    return not type_.startswith('ai')
