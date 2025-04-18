"""Miscellaneous utilities for maya."""

import logging

from maya import cmds, mel

from pini.utils import single, check_heart, abs_path

from .mu_dec import restore_ns

_LOGGER = logging.getLogger(__name__)

COLS = (
    "deepblue", "black", "darkgrey", "grey", "darkred", "darkblue", "blue",
    "darkgreen", "deepgrey", "magenta", "brown", "deepbrown", "redbrown",
    "red", "green", "fadedblue", "white", "yellow", "lightblue", "lightgreen",
    "pink", "orange", "lightyellow", "fadedgreen", "darktan", "tanyellow",
    "olivegreen", "woodgreen", "cyan", "greyblue", "purple", "crimson")

DEFAULT_NODES = [
    'defaultLightSet',
    'defaultObjectSet',
    'defaultRenderLayer',
    'defaultLayer',
    'initialParticleSE',
    'initialShadingGroup',
    'lambert1',
    'renderSetup',
]
for _cam in ['persp', 'top', 'side', 'front', 'back', 'left']:
    DEFAULT_NODES += [_cam, _cam + 'Shape']
DEFAULT_NODES = tuple(sorted(DEFAULT_NODES))


@restore_ns
def add_to_dlayer(obj, layer):
    """Add the given node to a display layer, creating the layer if needed.

    Args:
        obj (str): object to add
        layer (str): layer to add to
    """
    if not cmds.objExists(layer):
        cmds.namespace(setNamespace=':')
        cmds.createDisplayLayer(name=layer, number=True, empty=True)
    cmds.editDisplayLayerMembers(layer, obj, noRecurse=1)


@restore_ns
def add_to_grp(node, grp):
    """Add a node to a group, creating the group if needed.

    Args:
        node (str): node to add
        grp (str): name of group to add to
    """
    if to_parent(node) == grp:
        return grp
    cmds.namespace(setNamespace=':')
    if not cmds.objExists(grp):
        cmds.group(empty=True, name=grp)
    cmds.parent(node, grp)
    return grp


@restore_ns
def add_to_set(obj, set_):
    """Add the given node to an object set.

    Args:
        obj (str): object to add
        set_ (str): set to add to
    """
    if not cmds.objExists(set_):
        cmds.namespace(set=':')
        cmds.sets(name=set_, empty=True)
    cmds.sets(obj, addElement=set_)


def bake_results(
        chans, simulation=False, range_=None, euler_filter=True,
        add_offs=False):
    """Bake animation on the given channels.

    Args:
        chans (str list): channels (attributes) to bake
        simulation (bool): update timeline and viewport sequentially while
            caching (slower but more stable)
        range_ (tuple): override cache range
        euler_filter (bool): apply euler filter on cache
        add_offs (CNode): node to add anim offset/mult chans to
    """
    from pini import dcc
    from maya_pini import open_maya as pom

    # Execute bake
    _LOGGER.debug('BAKE RESULTS - %d CHANS', len(chans))
    _range = range_ or dcc.t_range(int)
    cmds.bakeResults(chans, time=_range, simulation=simulation)
    if euler_filter:
        cmds.filterCurve(chans)
    cmds.DeleteStaticChannels()

    if add_offs:
        _tfm = pom.CTransform(add_offs)
        _crvs = []
        for _chan in chans:
            _plug = pom.CPlug(_chan)
            _crv = _plug.anim
            if _crv:
                _crvs.append(_crv)
        pom.add_anim_offs(tfm=_tfm, anim=_crvs)


def create_attr(plug, value):
    """Create the given attribute.

    Args:
        plug (str): attribute name (eg. persp.test)
        value (any): attribute value - the type of the attribute
            determines the type of attribute to create

    Returns:
        (str): attribute created
    """
    _node, _attr = plug.split('.')
    _plug = f'{_node}.{_attr}'

    # Handle attr already exists
    if cmds.objExists(plug):
        assert cmds.getAttr(plug) == value
        return _plug

    # Gather args
    if isinstance(value, bool):
        _attr_type = 'bool'
        _def_val = True
    else:
        raise ValueError(value)

    # Create attr
    cmds.addAttr(
        _node, longName=_attr, shortName=_attr, attributeType=_attr_type,
        defaultValue=_def_val, keyable=True)

    return _plug


def cur_file():
    """Get path to current scene.

    Returns:
        (str|None): current scene path (if any)
    """
    _file = cmds.file(query=True, location=True)
    if _file == 'unknown':
        return None
    return str(_file)


def cycle_check():
    """Make sure cycle check is disabled."""
    if cmds.cycleCheck(query=True, evaluation=True):
        cmds.cycleCheck(evaluation=False)


def is_attr(token):
    """Test if the given token is an attibute.

    eg. pSphere1 -> False
        pSphere1.f[0] -> True

    Args:
        token (str): token (eg. pSphere1, pSphere1.f[0])

    Returns:
        (bool): whether token is an attribute
    """
    return '.' in token


def set_col(node, col, force=False):
    """Set viewport colour of the given node.

    Args:
        node (str): node to change colour of
        col (str): colour to apply
        force (bool): flush any display layer connections before apply
    """
    _LOGGER.debug('SET COL %s %s', node, col)
    from pini import qt
    from pini.qt import QtGui
    from maya_pini import open_maya as pom

    # Find colour or QColor
    _col = _q_col = None
    if isinstance(col, str):
        if col.lower() in COLS:
            _col = col.lower()
        else:
            _q_col = qt.to_col(col)
    elif isinstance(col, QtGui.QColor):
        _q_col = col
    else:
        raise ValueError(col)

    # Setup node
    _node = pom.to_node(node)
    if force:
        _node.plug['drawOverride'].break_conns()
    _node.plug['overrideEnabled'].set_val(True)

    # Apply index col
    if _col:
        _node.plug['overrideRGBColors'].set_val(0)  # Index
        _node.plug['overrideColor'].set_val(COLS.index(_col))
    elif _q_col:
        _LOGGER.debug(' - APPLY RGB COL %s', _q_col)
        _node.plug['overrideRGBColors'].set_val(1)  # RGB
        _node.plug['overrideColorRGB'].set_col(_q_col)
    else:
        raise RuntimeError


def set_enum(chan, value):
    """Set the given enum to a string value.

    Args:
        chan (str): attribute to set
        value (str): value to apply
    """
    _node, _attr = chan.split('.')
    _item_str = single(cmds.attributeQuery(_attr, node=_node, listEnum=True))
    _items = _item_str.split(":")
    _idx = _items.index(value)
    cmds.setAttr(chan, _idx)


def set_workspace(dir_):
    """Set current workspace to the given dir.

    Args:
        dir_ (Dir): path to apply
    """
    _LOGGER.debug('UPDATING WORKSPACE %s', dir_.path)
    cmds.workspace(create=dir_.path)
    cmds.workspace(dir_.path, openWorkspace=True)
    cmds.workspace(projectPath=dir_.path)
    cmds.workspace(directory=dir_.dir)


def to_audio(start=None, mode='wav/offset'):
    """Read scene audio.

    Args:
        start (float): override start frame
        mode (str): what to return (eg. node or wav/offset)

    Returns:
        (tuple): audio / offset from start frame (in secs)
    """
    from pini import dcc

    _ctrl = mel.eval('$tmpVar=$gPlayBackSlider')
    _node = cmds.timeControl(_ctrl, query=True, sound=True)
    if not _node:
        return None, None

    _start = start
    if _start is None:
        _start = dcc.t_start()

    _file = abs_path(cmds.getAttr(_node + '.filename'))
    _fps = dcc.get_fps()
    _offs = cmds.getAttr(_node + '.offset')

    if mode == 'wav/offset':
        return _file, (_offs - _start) / _fps
    if mode == 'node':
        return _node
    raise ValueError(mode)


def to_clean(node, strip_digits=False):
    """Get clean node name for the given node, ie. strip namespace.

    eg. tmp:camera -> camera

    Args:
        node (str): node name to clean
        strip_digits (bool): remove trailing digits from node name

    Returns:
        (str): clean name
    """
    _clean = str(node).rsplit('|', 1)[-1].rsplit(':', 1)[-1]
    if strip_digits:
        while _clean[-1].isdigit():
            _clean = _clean[:-1]
    return _clean


def to_long(node):
    """Get full path of the given dag node.

    eg. perspShape -> |persp|perspShape

    Args:
        node (str): node to get dag path of

    Returns:
        (str): long name
    """
    _node = to_node(node, shorten=False)
    _ls = cmds.ls(_node, long=True)
    try:
        _long = single(_ls)
    except ValueError as _exc:
        raise ValueError(node, type(node)) from _exc
    return _long


def to_node(name, shorten=True, namespace=None, class_=None, clean=True):
    """Obtain a node from the given object.

    eg. to_node(CNode('persp')) -> 'persp'
        to_node('persp.tx') -> 'persp'
        to_node('persp|perspShape') -> 'perspShape'

    Args:
        name (str): object to convert
        shorten (bool): strip out path pipes from node name
        namespace (str): force namespace
        class_ (class): cast node to given type
        clean (bool): strip namespaces from name

    Returns:
        (str): node name
    """
    _node = str(name)
    if shorten:
        _node = _node.rsplit('|', 1)[-1]
    _node = _node.rsplit('->', 1)[-1]
    _node = _node.split('.', 1)[0]
    if namespace:
        _name = to_clean(_node) if clean else _node
        _node = f'{namespace}:{_name}'
    if class_:
        _node = class_(_node)
    return _node


def to_parent(node):
    """Obtain dag parent of the given node.

    Args:
        node (str): node to read

    Returns:
        (str): parent
    """
    _node = to_node(node, shorten=False)
    _parents = cmds.listRelatives(_node, parent=True, path=True) or []
    _parent = single(_parents, catch=True)
    if _parent:
        _parent = str(_parent)
    return _parent


def to_shp(node, catch=False, type_=None):
    """Obtain shape of the given node.

    Args:
        node (str): node to read
        catch (bool): no error if no shapes found
        type_ (str): apply type filter

    Returns:
        (str): shape
    """
    try:
        return single(to_shps(node, type_=type_), catch=catch)
    except ValueError as _exc:
        raise ValueError(f'Failed to find shape - {node}') from _exc


def to_shps(node, type_=None):
    """Obtain shapes of the given node.

    Args:
        node (str): node to read
        type_ (str): apply type filter

    Returns:
        (str list): shapes
    """
    if not isinstance(node, str):
        raise TypeError(f'Bad type {type(node)} - {node}')
    _kwargs = {}
    if type_:
        _kwargs['type'] = type_
    _shps = cmds.listRelatives(
        node, shapes=True, path=True, noIntermediate=True, **_kwargs) or []
    _result = sorted(set(_shps))
    _result = map(str, _result)
    return list(_result)


def to_unique(base, suffix='', ignore=()):
    """Find a unique node name.

        eg. persp -> persp1

    Args:
        base (str): node base
        suffix (str): required suffix (eg. _GEO)
        ignore (tuple): treat these names as if they are existing nodes
            in the scene

    Returns:
        (str): unique name
    """
    _base = base
    while _base[-1].isdigit():
        _base = _base[:-1]
    _ns = cmds.namespaceInfo(currentNamespace=True)

    _idx = 0
    while True:
        check_heart()
        _idx_str = str(_idx) if _idx else ''
        _suggestion = ''.join([_base, _idx_str, suffix])
        _idx += 1
        if _suggestion in ignore:
            continue
        if not cmds.objExists(_ns + ':' + _suggestion):
            return _suggestion
