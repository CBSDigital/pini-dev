"""Tools for managing the base class for any node object."""

import functools
import logging

from maya import cmds, mel

from pini import qt
from pini.utils import (
    basic_repr, single, abs_path, File, cache_result, passes_filter)
from maya_pini.utils import (
    to_namespace, to_clean, to_shps, set_col, add_to_grp, to_long,
    add_to_set, add_to_dlayer)

from .. import pom_cmds, pom_utils

_LOGGER = logging.getLogger(__name__)


class CBaseNode:  # pylint: disable=too-many-public-methods
    """Base class for any node object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): node to build object from
        """
        _node = node
        if isinstance(_node, CBaseNode):
            _node = str(_node)
        if not isinstance(_node, str):
            raise ValueError(_node)
        self.node = _node

    @property
    def attr(self):
        """Obtain attribute mapper.

        This maps items to an attribute on this node:

        eg. CNode('persp').attr['tx'] -> 'persp.tx'

        Returns:
            (str): attribute path
        """
        return _AttrGetter(self)

    @property
    def cmds(self):
        """Mapper for any maya.cmds call as applied to this node.

        Returns:
            (CmdsMapper): maya.cmds mapper
        """
        return pom_cmds.CmdsMapper(node=self.node)

    @property
    def clean_name(self):
        """Obtain clean name of this node (ie. without namespace).

        eg. tmp:pSphere1 -> pSphere1

        Returns:
            (str): clean name
        """
        return to_clean(str(self))

    @property
    def namespace(self):
        """Obtain namespace of this node.

        eg. tmp:pSphere1 -> tmp
            pSphere1 -> None

        Returns:
            (str|None): namespace
        """
        return to_namespace(str(self))

    @property
    def plug(self):
        """Obtain plug mapper.

        This maps items to a plug on this node:

        eg. CNode('persp').attr['tx'] -> CPlug('persp.tx')

        Returns:
            (CPlug): plug
        """
        return _PlugGetter(self)

    @property
    def shp(self):
        """Obtain this node's shape (if any).

        Returns:
            (CNode|None): shape
        """
        return self.to_shp(catch=True)

    def add_attr(
            self, name, value, force=False, locked=False, min_val=None,
            max_val=None, keyable=True):
        """Add an attribute to this node.

        The attribute type is based on the type of the value provided.

        Args:
            name (str): attribute name
            value (any): attribute value
            force (bool): force apply value
            locked (bool): lock attribute on create
            min_val (float|int): set minimum value
            max_val (float|int): set maximum value
            keyable (bool): keyable + channel box status

        Returns:
            (CPlug): new attribute
        """
        _LOGGER.debug('ADD ATTR %s %s', name, value)
        _kwargs, _action, _children = self._add_attr_build_kwargs(
            value=value, min_val=min_val, max_val=max_val)

        # Handle exists
        if self.has_attr(name):
            return self._add_attr_update_existing(
                name, value=value, action=_action, force=force)

        # Create attr
        _LOGGER.debug(' - KWARGS %s', _kwargs)
        cmds.addAttr(
            self, shortName=name, longName=name, keyable=keyable,
            **_kwargs)
        for _child in _children:
            _c_name = name + _child
            _LOGGER.info(' - ADDING CHILD %s %s', _child, _c_name)
            cmds.addAttr(
                self, shortName=_c_name, longName=_c_name, parent=name,
                attributeType='float')

        # Apply value
        _plug = self.plug[name]
        if _action == 'set':
            _plug.set_val(value)
        elif _action == 'connect':
            value.plug['message'].connect(_plug)
        else:
            raise ValueError(_action)
        if locked:
            _plug.isLocked = True

        return _plug

    def _add_attr_update_existing(self, name, value, action, force):
        """Update existing attribute.

        Args:
            name (str): attribute name
            value (any): attribute value
            action (str): update action (set/connect)
            force (bool): force apply value

        Returns:
            (CPlug): new attribute
        """
        _plug = self.plug[name]

        if action == 'connect':
            value.plug['message'].connect(_plug, force=True)

        elif action == 'set':

            _val = _plug.get_val()

            # Check type
            _cur_type = type(_val)
            if _cur_type != type(value):  # pylint: disable=unidiomatic-typecheck
                raise NotImplementedError(
                    f'Type mismatch {_cur_type}/{type(value)}')

            # Update val
            if force and value != _val:
                _plug.set_val(value)

        else:
            raise ValueError(action)

        return _plug

    def _add_attr_build_kwargs(self, value, min_val, max_val):
        """Build addAttr kwargs dict.

        Args:
            value (any): attribute value
            min_val (float|int): set minimum value
            max_val (float|int): set maximum value

        Returns:
            (tuple): kwargs dict, apply value action
        """
        _kwargs = {}

        _action = 'set'
        _children = []
        if isinstance(value, float):
            _kwargs['attributeType'] = 'float'
        elif isinstance(value, bool):
            _kwargs['attributeType'] = 'bool'
        elif isinstance(value, int):
            _kwargs['attributeType'] = 'long'
        elif isinstance(value, str):
            _kwargs['dataType'] = 'string'
        elif isinstance(value, CBaseNode):
            _kwargs['attributeType'] = 'message'
            _action = 'connect'
        elif isinstance(value, qt.CColor):
            _kwargs['attributeType'] = 'float3'
            _kwargs['usedAsColor'] = True
            _children = 'RGB'
        else:
            raise ValueError(value)

        if min_val is not None:
            _kwargs['minValue'] = min_val
        if max_val is not None:
            _kwargs['maxValue'] = max_val

        return _kwargs, _action, _children

    def add_enum(self, name, opts, value=None):
        """Create an enum attribute.

        Args:
            name (str): attibute name
            opts (str list): enum options
            value (str): default value

        Returns:
            (CPlug): new plug
        """
        _val = value
        if self.has_attr(name):
            _plug = self.plug[name]
            if _plug.list_enum() == opts:
                return _plug
            _cur_val = _plug.get_enum()
            if not _val and _cur_val in opts:
                _val = _cur_val
            _plug.delete()
        _data = ':'.join(opts)
        cmds.addAttr(self, shortName=name, attributeType='enum',
                     enumName=_data, keyable=True)
        _plug = self.plug[name]
        if _val:
            _plug.set_val(opts.index(_val))
        return _plug

    def add_to_dlayer(self, layer):
        """Add this node to a display layer.

        Args:
            layer (str): name of layer to add to
        """
        add_to_dlayer(self, layer)

    def add_to_grp(self, grp, col=None):
        """Add this node to a group.

        Args:
            grp (str): name of group to add to
            col (str): outliner colour for group

        Returns:
            (CTransform): group
        """
        from maya_pini import open_maya as pom
        _grp = pom.CTransform(add_to_grp(node=self.node, grp=grp))
        if col:
            _grp.set_outliner_col(col)
        return _grp

    def add_to_set(self, set_):
        """Add this node to a set.

        Args:
            set_ (str): name of set to add to
        """
        _set = str(set_)
        add_to_set(self, _set)
        return pom_utils.cast_node(_set)

    def apply_shd(self, shd):
        """Apply shader to this node.

        Args:
            shd (str): shader to apply
        """
        from maya_pini import tex
        tex.to_shd(shd).apply_to(self)

    def break_conns(self):
        """Break incoming connections on this node."""
        _plugs = [_dest for _, _dest in self.find_incoming()]
        for _plug in _plugs:
            _plug.break_conns()

    def delete(self):
        """Delete this node."""
        self.cmds.delete(self.node)

    def delete_history(self):
        """Delete history on this node."""
        cmds.delete(self, constructionHistory=True)

    def duplicate(
            self, name=None, upstream_nodes=False, instance_leaf=False,
            return_roots_only=True, input_connections=False, class_=None):
        """Duplicate this node.

        Args:
            name (str): node name
            upstream_nodes (bool): duplicate upstream nodes
            instance_leaf (bool): duplicate as instance
            return_roots_only (bool): return root nodes
            input_connections (bool): duplicate input connections
            class_ (class): override node class

        Returns:
            (CBaseNode): duplicated node
        """
        _LOGGER.debug('DUPLICATE %s', self)
        _kwargs = {}
        if name:
            _kwargs['name'] = name
        _class = class_ or type(self)
        _results = cmds.duplicate(
            self, renameChildren=True, upstreamNodes=upstream_nodes,
            instanceLeaf=instance_leaf, returnRootsOnly=return_roots_only,
            inputConnections=input_connections, **_kwargs)
        _LOGGER.debug(' - RESULTS %s', _results)
        _dup = _results[0]
        _LOGGER.debug(' - RESULT %s %s', _dup, _class)
        _node = _class(_dup)
        _LOGGER.debug(' - NODE %s', _node)
        return _node

    def exists(self):
        """Test whether this node exists.

        NOTE: this would have to be a node that was created after the api
        object was constructed.

        Returns:
            (bool): whether exists
        """
        return cmds.objExists(self)

    @functools.wraps(pom_utils.find_connections)
    def find_connections(self, **kwargs):
        """Find connections to this node.

        Returns:
            (CPlug tuple list): src/dest pairs
        """
        return pom_utils.find_connections(self, **kwargs)

    def find_incoming(self, type_=None, connections=True, plugs=True):
        """Find incoming connections to this node.

        Args:
            type_ (str): filter by node type
            connections (bool): return src/dest pairs or just dests
            plugs (bool): return plugs rather than nodes

        Returns:
            (list): incoming connections
        """
        return self.find_connections(
            destination=False, type_=type_, connections=connections,
            plugs=plugs)

    def find_outgoing(self, type_=None, connections=True, plugs=True):
        """Find outgoing connections from this node.

        Args:
            type_ (str): filter by node type
            connections (bool): return src/dest pairs or just dests
            plugs (bool): return plugs rather than nodes

        Returns:
            (list): outgoing connections
        """
        return self.find_connections(
            source=False, type_=type_, connections=connections, plugs=plugs)

    def find_plugs(
            self, user_defined=False, keyable=None, head=None, filter_=None):
        """Find plugs on this node.

        Args:
            user_defined (bool): return only user defined attributes
            keyable (bool): return only keyable plugs
            head (str): filter by start of attribute name (eg. vray/ai)
            filter_ (str): apply attibute name filter

        Returns:
            (CPlug list): matching plugs
        """
        _plugs = []
        for _plug in self.list_attr(user_defined=user_defined, keyable=keyable):
            if head and not _plug.attr.startswith(head):
                continue
            if filter_ and not passes_filter(str(_plug.attr), filter_):
                continue
            _plugs.append(_plug)
        return _plugs

    def has_attr(self, attr):
        """Check whether this node has the given attribute.

        Args:
            attr (str): name of attr to check for

        Returns:
            (bool): whether attribute exists
        """
        return cmds.attributeQuery(attr, node=self, exists=True)

    def is_instanced(self):
        """Check if this node is an instanced shape node.

        Returns:
            (bool): whether instanced
        """
        _dag = pom_utils.to_mdagpath(str(self))
        return _dag.isInstanced()

    def is_referenced(self):
        """Check whether this node is referenced.

        Returns:
            (bool): whether referenced
        """
        return self.isFromReferencedFile  # pylint: disable=no-member

    def list_attr(self, keyable=False, user_defined=False):
        """Apply listAttr command to this node.

        Args:
            keyable (bool): return only keyable attributes
            user_defined (bool): return only user defined attributes

        Returns:
            (CPlug list): matching plugs
        """
        _plugs = []
        _attrs = cmds.listAttr(
            self, keyable=keyable, userDefined=user_defined) or []
        for _attr in sorted(_attrs):
            try:
                _plug = self.plug[_attr]
            except RuntimeError:
                _LOGGER.info(' - FAILED TO BUILD PLUG %s.%s', self, _attr)
                continue
            _plugs.append(_plug)
        return _plugs

    def object_type(self):
        """Read this node's object type.

        Returns:
            (str): object type
        """
        return cmds.objectType(self.node)

    def parent(self, parent=None, relative=None, world=None):
        """Set this node's parent.

        Args:
            parent (str): new parent
            relative (bool): maintain local transforms
            world (bool): parent to world
        """
        if world and not self.to_parent():
            return

        _args = [self]
        if parent:
            _args.append(parent)
        _kwargs = {}
        if relative is not None:
            _kwargs['relative'] = relative
        if world is not None:
            _kwargs['world'] = world

        _LOGGER.debug('PARENT %s %s', _args, _kwargs)
        cmds.parent(*_args, **_kwargs)

    def rename(self, name):
        """Rename this node.

        Args:
            name (str): new name to apply

        Returns:
            (CBaseNode): update node
        """
        _class = type(self)
        _result = cmds.rename(self.node, name)
        _result = _result.split('->')[-1]
        return _class(_result)

    def select(self):
        """Select this node."""
        cmds.select(self, replace=True)

    def set_col(self, col):
        """Set viewport colour of this node.

        Args:
            col (str): name of colour to apply
        """
        set_col(self.node, col)

    def set_key(self, frame=None):
        """Set keyframe on this node (ie. key all channels).

        Args:
            frame (float): frame to keyframe on
        """
        _kwargs = {}
        if frame is not None:
            _kwargs['time'] = frame
        cmds.setKeyframe(self, **_kwargs)

    def set_outliner_col(self, col):
        """Set outliner colour of this node.

        Args:
            col (str): colour to apply
        """
        self.plug['useOutlinerColor'].set_val(True)
        self.plug['outlinerColor'].set_col(col)

    def to_anim(self):
        """Find anim curves attached to this node.

        Returns:
            (CAnimCurve list): anim curves
        """
        from maya_pini import open_maya as pom
        _nodes = self.find_incoming(
            type_='animCurve', connections=False, plugs=False)
        return [pom.CAnimCurve(_node) for _node in _nodes]

    def to_attr(self, attr):
        """Get the path on an attribute on this node.

        Args:
            attr (str): attribute name

        Returns:
            (str): attribute path
        """
        return f'{self}.{attr}'

    def to_bbox(self):
        """Obtain this node's bounding box.

        Returns:
            (CBoundingBox): bounding box
        """
        from maya_pini import open_maya as pom
        return pom.to_bbox(self)

    def to_clean(self):
        """Obtain clean node name (ie. without namespaces).

        Returns:
            (str): clean name
        """
        return to_clean(self)

    def to_long(self):
        """Get full path of this node.

        Returns:
            (str): full path (eg. |persp|perspShape)
        """
        return to_long(self.node)

    def to_m(self, world_space=True):
        """Get transformation matrix for this node.

        Args:
            world_space (bool): read matrix in world or local space

        Returns:
            (CMatrix): matrix
        """
        from maya_pini import open_maya as pom
        _data = cmds.xform(
            self, query=True, matrix=True, worldSpace=world_space)
        return pom.CMatrix(_data)

    def to_p(self):
        """Get position of this node.

        Returns:
            (CPoint): global position
        """
        from maya_pini import open_maya as pom
        return pom.to_p(self)

    def to_parent(self):
        """Obtain this node's parent.

        Returns:
            (CTransform|None): parent (if any)
        """
        _LOGGER.debug('TO PARENT %s', self)
        _parents = self.cmds.listRelatives(parent=True, path=True) or []
        _LOGGER.debug(' - PARENTS %s', _parents)
        _parent = single(_parents, catch=True)
        return _parent

    def to_plug(self, name):
        """Obtain a plug (attribute) on this node.

        Args:
            name (str): attribute name (eg. tx)

        Returns:
            (CPlug): attribute plug
        """
        from maya_pini import open_maya as pom
        _name = name
        if isinstance(_name, pom.CPlug):
            _name = _name.attr
        return pom.CPlug(self.to_attr(_name))

    def to_reference(self):
        """Obtain this node's parent reference.

        Returns:
            (CReference|None): reference (if any)
        """
        from maya_pini import open_maya as pom
        try:
            _ref = cmds.referenceQuery(self, referenceNode=True)
        except RuntimeError:
            return None
        return pom.CReference(_ref)

    def to_shp(self, type_=None, catch=False):
        """Obtain this node's shape.

        Args:
            type_ (str): filter by type
            catch (bool): no error if no/mutiple shapes found

        Returns:
            (CNode|None): shape (if any)
        """
        _shps = self.to_shps(type_=type_)
        _err = f'{self} has {len(_shps):d} shapes'
        return single(_shps, error=_err, catch=catch)

    def to_shps(self, type_=None):
        """Read this node's shapes.

        Args:
            type_ (str): apply type filter

        Returns:
            (CNode list): shapes
        """
        from maya_pini import open_maya as pom
        return [pom.CNode(_node) for _node in to_shps(self.node, type_=type_)]

    def _to_preset_tmp(self, fmt):
        """Obtain present tmp file.

        Args:
            fmt (str): preset format (mpa/mpb)

        Returns:
            (File): tmp file for this node
        """
        _type = self.object_type()
        _presets_dir = abs_path(cmds.internalVar(userPresetsDir=True))
        if fmt == 'mpa':
            _file = f"{_presets_dir}/attrPresets/{_type}/tmp.mel"
        elif fmt == 'mpb':
            _file = f"{_presets_dir}/{_type}Preset_tmp.mel"
        else:
            raise ValueError(fmt)
        return File(_file)

    def load_preset(self, file_):
        """Load the given preset to this node.

        Args:
            file_ (str): path to preset file
        """
        _file = File(file_)
        assert _file.exists()
        _tmp_file = self._to_preset_tmp(fmt=_file.extn)
        if _tmp_file != _file:
            _file.copy_to(_tmp_file, force=True, verbose=0)

        if _file.extn == 'mpa':
            _cmd = f'{_get_load_preset_mel()} "{self}" "" "" "tmp" 1'
            mel.eval(_cmd)
        elif _file.extn == 'mpb':
            cmds.nodePreset(load=(self, "tmp"))
        else:
            raise ValueError(_file.path)

    def save_preset(self, file_=None, fmt='auto', force=False):
        """Save this node's settings to a preset file.

        Args:
            file_ (str): override preset file
            fmt (str): preset format
                mpa - mel format, can cause random crash
                mpb - python format
            force (bool): overwrite existing without confirmation

        Returns:
            (File): file which was saved
        """
        _LOGGER.debug('SAVE PRESET')

        _file = file_
        if _file:
            _file = File(file_)
            _file.delete(force=force, wording='Replace')
        _LOGGER.debug(' - FILE %s', _file)

        _fmt = fmt
        if _fmt == 'auto':
            if not _file:
                raise RuntimeError
            _fmt = _file.extn
        _LOGGER.debug(' - FMT %s', _fmt)

        _tmp_file = self._to_preset_tmp(_fmt)
        if _tmp_file.exists():
            _tmp_file.delete(force=True)

        if _fmt == 'mpa':
            # _file = self._save_mpa_preset(_file)
            mel.eval(f'saveAttrPreset "{self}" "tmp" false')
        elif _fmt == 'mpb':
            # _file = self._save_mpb_preset(_file)
            cmds.nodePreset(save=(self, "tmp"))
        else:
            raise NotImplementedError(_file)

        if not _tmp_file.exists():
            raise RuntimeError(f'Failed to save preset: {_tmp_file}')

        if _file:
            _tmp_file.copy_to(_file, verbose=0)

        return _file or _tmp_file

    def __eq__(self, other):
        if isinstance(other, CBaseNode):
            return self.node == other.node
        return self.node == other

    def __hash__(self):
        return hash(self.node)

    def __lt__(self, other):
        if isinstance(other, CBaseNode):
            return self.node < other.node
        return self.node < other

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return self.node

    def __repr__(self):
        return basic_repr(self, self.node, separator='|')


@cache_result
def _get_load_preset_mel():
    """Get mel for loading a preset.

    Certain mel proceedures need to be sourced, but this only needs
    to happen once (which is why the cache decorator is used).

    Returns:
        (str): mel code for loading a preset
    """
    mel.eval('source presetMenuForDir')
    mel.eval('source updateAE')
    return 'applyPresetToNode'


class _AttrGetter:
    """Item mapper for obtaining attributes on a node."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (CBaseNode): node to obtain attributes from
        """
        self.node = node

    def __getitem__(self, item):
        return self.node.to_attr(item)


class _PlugGetter:
    """Item mapper for obtaining plugs on a node."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (CBaseNode): node to obtain plugs from
        """
        self.node = node

    def __getitem__(self, item):
        return self.node.to_plug(item)
