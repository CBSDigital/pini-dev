"""General utilies for sanity check in maya."""

import collections
import logging

from maya import cmds

from pini import qt
from pini.dcc import export
from pini.tools import release
from pini.utils import single, wrap_fn, check_heart, to_list

from maya_pini import open_maya as pom, m_pipe
from maya_pini.utils import (
    to_unique, to_long, to_node, to_clean, to_parent, fix_dup_name)

from .. import core

_LOGGER = logging.getLogger(__name__)


def check_cacheable_set(set_, check):
    """Check a cacheable set.

    Args:
        set_ (str): name of cache_SET or CSET
        check (SCCheck): check to apply fails to
    """
    check.tfms = m_pipe.read_cache_set(set_=set_, mode='tfm')
    for _func in [
            _batch_check_for_basic_dup_names,
            _batch_check_for_cleaned_dup_names,
            _check_for_overlapping_nodes,
            _check_for_duplicate_names,
            _check_geo_shapes,
            _check_for_mutiple_top_nodes,
    ]:
        _func(set_=set_, check=check)
        if check.fails:
            return


def _fix_dup_name(geo, idxs=None, reject=None):
    """Fix node with duplicate name.

    Args:
        geo (str): node to fix
        idxs (dict): index of current suffix indices for each node name
        reject (set): names to reject

    Returns:
        (str): updated name
    """
    release.apply_deprecation('30/07/25', 'Use maya_pini.utils.fix_dup_name')
    _LOGGER.debug(' - GEO %s', geo)

    _idxs = idxs or {}
    _reject = reject or set()
    _root = to_clean(geo, strip_digits=True)
    _idx = _idxs.get(_root, 1)
    _LOGGER.debug('   - ROOT %s %d', _root, _idx)

    while True:
        check_heart()
        if _root.endswith('_'):
            _new_name = f'{_root}{_idx}'
        else:
            _new_name = f'{_root}_{_idx}'
        _idx += 1
        if _new_name in _reject:
            _LOGGER.debug('     - REJECTED IN USE %s', _new_name)
            continue
        if cmds.objExists(_new_name):
            _LOGGER.debug('     - REJECTED EXISTING %s', _new_name)
            continue
        break

    _LOGGER.debug('   - RENAME %s (FROM %s)', _new_name, geo)
    cmds.rename(geo, _new_name)
    _idxs[_root] = _idx + 1

    return _new_name


def _fix_basic_dup_names(tfms):
    """Fix basic dupicate names.

    Args:
        tfms (str list): nodes to fix
    """
    from pini.tools import sanity_check
    _idxs = {}
    _reject = {to_clean(_tfm) for _tfm in tfms}
    _progress = qt.progress_bar(
        reversed(tfms), 'Applying {:d} fixes', parent=sanity_check.DIALOG)
    _progress.raise_()
    for _tfm in _progress:
        fix_dup_name(_tfm, idxs=_idxs, reject=_reject)


def _batch_check_for_basic_dup_names(set_, check, threshold=20):
    """Batch check for basic duplicate names.

    This is a quick check for duplicate names which simply flags pipe
    characters in the node path - this is run before slower checks to
    provide a first pass rough clean of a complex scene without making
    sanity check hang - eg. forest created by duplicating nodes with 90k
    duplicate names.

    Args:
        set_ (str): cache set being checked
        check (SCCheck): sanity check
        threshold (int): ignore this check if the result count is
            less than this value
    """
    check.write_log('Applying batch basic duplicate name check %s', check)
    _bad_tfms = [_tfm for _tfm in check.tfms if '|' in str(_tfm)]
    if len(_bad_tfms) < threshold:
        return
    check.add_fail(
        f'Fix {len(_bad_tfms):d} duplicate names in "{set_}" flagged '
        'by basic check',
        fix=wrap_fn(_fix_basic_dup_names, _bad_tfms))


def _batch_check_for_cleaned_dup_names(set_, check, threshold=20):
    """Slower check for duplicate names using clean name.

    This runs after the basic check to batch flag large numbers of duplicate
    names, although this check uses the cleaned (namespace strippped) name.
    These are batched together as a single fail, in case there are a huge
    number of duplicate nodes, which would grid the sanity check ui to a halt.

    Args:
        set_ (str): cache set being checked
        check (SCCheck): sanity check
        threshold (int): ignore this check if the result count is
            less than this value
    """
    check.write_log('Applying batch cleaned duplicate name fix %s', set_)

    _names = collections.defaultdict(list)
    for _tfm in check.tfms:
        _name = to_clean(_tfm)
        _names[_name].append(_tfm)
    _names = dict(_names)
    _to_fix = [
        (_name, _tfms) for _name, _tfms in _names.items() if len(_tfms) > 1]
    if len(_to_fix) < threshold:
        return

    _LOGGER.debug(' - FOUND %d NAMES TO FIX', len(_to_fix))
    _count = sum(len(_tfms) for _, _tfms in _to_fix)

    check.add_fail(
        f'Fix {_count:d} duplicate names in "{set_}" flagged '
        'by clean name check', fix=wrap_fn(
            _fix_cleaned_dup_names, to_fix=_to_fix, reject=_names.keys()))


def _fix_cleaned_dup_names(to_fix, reject):
    """Fix duplicate names taking account of cleaned names.

    Args:
        to_fix (tuple): list of items to fix
        reject (str): names to reject
    """
    from pini.tools import sanity_check
    _LOGGER.debug('FIX CLEANED DUP NAMES')

    _idxs = {}
    for _name, _tfms in qt.progress_bar(
            to_fix, 'Applying {:d} by name fixes', parent=sanity_check.DIALOG):
        _LOGGER.debug('FIX TFMS %s %s', _name, _tfms)
        try:
            _tfms.sort(key=to_long, reverse=True)
        except ValueError:
            _LOGGER.info(' - FAILED TO SORT %s', _tfms)
            continue
        for _tfm in _tfms[1:]:
            fix_dup_name(_tfm, idxs=_idxs, reject=reject)


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
    _pub_refs_mode = export.get_pub_refs_mode()

    _names = collections.defaultdict(list)
    for _node in check.tfms:
        if _pub_refs_mode == export.PubRefsMode.IMPORT_USING_UNDERSCORES:
            _name = str(_node).replace(':', '_')
        else:
            _name = to_clean(_node)
        _names[_name].append(_node)

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
                _fix = wrap_fn(fix_dup_name, _node)
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

    _msg = (
        f'Cache set should contain one single node to avoid '
        f'abcs with multiple top nodes - cache_SET contains '
        f'{len(_top_nodes):d} top nodes')
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
            if _long.startswith(_o_long + '|'):
                _overlaps.append((_long, _o_long))
    for _node, _parent in _overlaps:
        _fix = wrap_fn(cmds.sets, _node, remove=set_)
        check.add_fail(
            f'In set "{set_}" the top node "{to_node(_node)}" is inside '
            f'top node "{to_node(_parent)}" which will cause abc export '
            f'to error', node=_node, fix=_fix)


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


def find_cache_set():
    """Find cache set in the current scene.

    If reference mode is set to "import references into root namespace" then a
    referenced cache set is valid.

    Returns:
        (CNode|None): cache set (if any)
    """
    release.apply_deprecation('05/05/25', 'Use maya_pipe.m_pipe.find_cache_set')

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
        _msg = (f'Referenced {type_} {_node} does not have "{suffix}" '
                f'suffix')
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
        f'{type_.capitalize()} "{node}" does not have "{suffix}" suffix '
        f'(suggestion: "{_suggestion}")')
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
    _set = m_pipe.find_cache_set()
    _include_referenced = True
    if apply_pub_refs_mode:
        _refs_mode = export.get_pub_refs_mode()
        _include_referenced = _refs_mode in (
            export.PubRefsMode.LEAVE_INTACT,
            export.PubRefsMode.IMPORT_TO_ROOT)
    return m_pipe.read_cache_set(
        mode='geo', include_referenced=_include_referenced, set_=_set,
        filter_=filter_)


def safe_delete(nodes):
    """Delete the given node or nodes.

    If they are locked then they are unlocked. If they have already been
    deleted (eg. in a previous fix operation) then this is ignored.

    Args:
        nodes (str|str list): node/nodes to delete
    """
    for _node in to_list(nodes):
        if cmds.objExists(_node):
            cmds.lockNode(_node, lock=False)
            cmds.delete(_node)


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
