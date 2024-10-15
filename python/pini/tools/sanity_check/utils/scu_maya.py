"""General utilies for sanity check in maya."""

import collections
import logging
import re

from maya import cmds

from pini.dcc import export
from pini.utils import single, wrap_fn, check_heart

from maya_pini import open_maya as pom, m_pipe
from maya_pini.utils import to_unique, to_long, to_node, to_clean, to_parent

from .. import core

_LOGGER = logging.getLogger(__name__)


def check_cacheable_set(set_, check):
    """Check a cacheable set.

    Args:
        set_ (str): name of cache_SET or CSET
        check (SCCheck): check to apply fails to
    """
    for _func in [
            _check_for_overlapping_nodes,
            _check_for_duplicate_names,
            _check_geo_shapes,
            _check_for_mutiple_top_nodes,
    ]:
        _func(set_=set_, check=check)
        if check.fails:
            return


def _check_geo_shapes(set_, check):
    """Check shapes nodes match transforms.

    Args:
        set_ (str): name of cache_SET or CSET
        check (SCCheck): check to apply fails to
    """
    check.write_log('Checking shapes %s', set_)
    _geos = m_pipe.read_cache_set(set_=set_, mode='geo')
    for _geo in _geos:
        check.write_log(' - geo %s', _geo)
        check.check_shp(_geo)


def _check_for_duplicate_names(set_, check):
    """Check for duplicate names in set.

    Args:
        set_ (str): name of cache_SET or CSET
        check (SCCheck): check to apply fails to
    """
    _names = collections.defaultdict(list)

    for _node in m_pipe.read_cache_set(set_=set_, mode='transforms'):
        _names[to_clean(_node)].append(_node)

    for _name, _nodes in _names.items():
        if len(_nodes) == 1:
            continue
        for _node in _nodes[1:]:
            _msg = (
                f'Duplicate name "{_name}" in "{set_}". This will '
                'cause errors on abc export.')
            _fix = None
            _fixable = bool([
                _node for _node in _nodes if not _node.is_referenced()])
            if _fixable:
                _fix = wrap_fn(
                    _fix_duplicate_node, node=_node, set_=set_)
            _fail = core.SCFail(_msg, fix=_fix)
            _fail.add_action('Select nodes', wrap_fn(cmds.select, _nodes))
            check.add_fail(_fail)


def _check_for_mutiple_top_nodes(set_, check):
    """Make sure cache set geo has a single top node.

    Args:
        set_ (str): name of cache_SET or CSET
        check (SCCheck): check to apply fails to
    """
    _top_nodes = cmds.sets(set_, query=True) or []
    if len(_top_nodes) == 1:
        return

    _msg = ('Cache set should contain one single node to avoid '
            'abcs with multiple top nodes - cache_SET contains {:d} '
            'top nodes').format(len(_top_nodes))
    _fix = None
    _shared_parent = single(
        {to_parent(_node) for _node in _top_nodes}, catch=True)
    check.write_log('shared parent %s', _shared_parent)
    if _shared_parent:

        # Check if we can existing group or create one
        _grp = 'ABC'
        _can_use_grp = False
        if not cmds.objExists(_grp):
            _can_use_grp = True
        elif _shared_parent == _grp:
            _children = tuple(sorted(
                cmds.listRelatives('ABC', children=True)))
            check.write_log('children %s', _children)
            _top_nodes = tuple(sorted(
                str(_node) for _node in _top_nodes))
            check.write_log('top nodes %s', _top_nodes)
            if _children == _top_nodes:
                _can_use_grp = True
        check.write_log('can use grp %d', _can_use_grp)

        if _can_use_grp:
            _fix = wrap_fn(
                _fix_shared_parent, parent=_shared_parent, nodes=_top_nodes,
                set_=set_, grp=_grp)

    check.add_fail(_msg, fix=_fix)


def _check_for_overlapping_nodes(set_, check):
    """Check set for overlapping top nodes.

    If AbcExport is passed a set which contains two nodes which
    are in the same parenting hierarchy then it will error.

    eg. you cannot use |MDL and |MDL|geom in the same cache set.

    Args:
        set_ (str): name of cache_SET or CSET
        check (SCCheck): check to apply fails to
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


def _fix_shared_parent(parent, nodes, set_, grp):
    """Fix cache set with two nodes sharing the same parent.

    Args:
        parent (str): parent node
        nodes (str): nodes sharing parent
        set_ (str): name of cache_SET or CSET
        grp (str): name of intermediate node to create
    """
    if not cmds.objExists(grp):
        _grp = pom.CMDS.group(name=grp, empty=True)
        _grp.add_to_grp(parent)
    else:
        _grp = pom.CTransform(grp)
    _grp.add_to_set(set_)
    for _node in nodes:
        cmds.sets(_node, remove=set_)
        pom.CTransform(_node).add_to_grp(grp)


def _fix_duplicate_node(node, set_):
    """Rename a duplicate node so that it has a unique name.

    Args:
        node (str): node to fix (eg. lightsGrp)
        set_ (str): name of cache_SET or CSET
    """
    _LOGGER.info('FIX DUP NODE %s', node)

    _tfms = m_pipe.read_cache_set(set_=set_, mode='transforms')
    _names = {to_clean(_tfm) for _tfm in _tfms}
    _LOGGER.info(' - FOUND %d NAMES', len(_names))

    _base = re.split('[|:]', str(node))[-1]
    while _base and _base[-1].isdigit():
        check_heart()
        _base = _base[:-1]
    _LOGGER.info(' - BASE %s', _base)

    # Find next base
    _idx = 1
    _name = _base
    _LOGGER.info(' - CHECK NAME %s', _name)
    while cmds.objExists(_name) or _name in _names:
        check_heart()
        _name = f'{_base}{_idx:d}'
        _LOGGER.info(' - CHECK NAME %s', _name)
        _idx += 1
    _LOGGER.info(' - RENAME %s -> %s', node, _name)
    cmds.rename(node, _name)


def find_cache_set():
    """Find cache set in the current scene.

    If reference mode is set to "import references into root namespace" then a
    referenced cache set is valid.

    Returns:
        (CNode|None): cache set (if any)
    """
    if cmds.objExists('cache_SET'):
        return pom.CNode('cache_SET')
    _refs_mode = export.get_pub_refs_mode()
    if _refs_mode is export.PubRefsMode.IMPORT_TO_ROOT:
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


def read_cache_set_geo(filter_=None, apply_pub_refs_mode=False):
    """Read cache_SET contents.

    Based on publish references mode, this can contain different values,
    namely whether to include referenced nodes.

    Args:
        filter_ (str): apply filter to list
        apply_pub_refs_mode (bool): apply publish references mode filtering
            (ie. if publish references is set to remove then ignore
            referenced nodes)

    Returns:
        (CBaseTransform list): cache set nodes
    """
    _set = find_cache_set()
    _include_referenced = True
    if apply_pub_refs_mode:
        _refs_mode = export.get_pub_refs_mode()
        _include_referenced = _refs_mode in (
            export.PubRefsMode.LEAVE_INTACT,
            export.PubRefsMode.IMPORT_TO_ROOT)
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
