"""Tools for adding functionilty to OpenMaya.MPlug object."""

import functools
import logging
import re

import six

from maya import cmds
from maya.api import OpenMaya as om

from pini import qt
from pini.utils import basic_repr, single, check_heart
from maya_pini.utils import set_enum

from . import pom_node
from .. import pom_utils

_LOGGER = logging.getLogger(__name__)


def _to_mplug(node, attr):
    """Build MPlug object from the given node/attr.

    Args:
        node (CNode): plug node
        attr (str): plug attribute name

    Returns:
        (MPlug): plug
    """
    _LOGGER.debug('TO MPLUG %s %s', node, attr)

    # Find nested attrs (eg. node.attr[0].attr[0].attr)
    if '.' in attr:

        # Find root plug
        _head, _tail = attr.split('.', 1)
        _LOGGER.debug(' - NESTED ATTR %s %s', _head, _tail)
        _parent = _to_mplug(node, _head)
        _LOGGER.debug(' - PARENT %s', _parent)

        # Find children one by one
        while _tail:
            check_heart()
            _head, _tail, _parent = _to_child_mplug(
                head=_head, tail=_tail, parent=_parent)

        _plug = _parent

    # Find indexed plugs (eg. node.attr[0])
    elif '[' in attr:  # handle indexed attrs
        _attr, _idx, _ = re.split(r'[\[\]]', attr)
        _idx = int(_idx)
        _LOGGER.debug(' - ATTR/IDX %s %d', _attr, _idx)
        _idx = int(_idx)
        _parent = node.findPlug(_attr, False)
        _plug = _parent.elementByLogicalIndex(_idx)

    # Find regular plugs (eg. node.attr)
    else:
        _plug = node.findPlug(attr, False)

    return _plug


def _to_child_mplug(head, tail, parent):
    """Obtain a nested child attribute plug.

    eg. colorEntryList[0].color

    Args:
        head (str): name of attribute to read (eg. colorEntryList[0])
        tail (str): name of subsequent child attrs (eg. color)
        parent (CPlug): parent attibute

    Returns:
        (CPlug): child plug
    """
    _head = head
    _tail = tail

    # Break into head (to find in this iter) + tail (to pass to next)
    if '.' in _tail:
        _head, _tail = _tail.split('.', 1)
    else:
        _head, _tail = _tail, None
    _LOGGER.debug(' - HEAD/TAIL %s %s', _head, _tail)

    # Check whether this is indexed
    if '[' in _head:
        _attr, _idx, _ = re.split(r'[\[\]]', _head)
        _idx = int(_idx)
    else:
        _attr, _idx = _head, None
    _LOGGER.debug(' - ATTR/IDX %s %s', _attr, _idx)

    # Find this attr on parent plug
    _LOGGER.debug(' - CHECKING %s FOR %s', parent.name(), _attr)
    for _jdx in range(parent.numChildren()):
        try:
            _child = parent.child(_jdx)
        except RuntimeError:
            _LOGGER.debug('   - FAILED TO READ CHILD %d', _jdx)
            continue
        _LOGGER.debug('   - TESTING CHILD %d %s', _jdx, _child.name())
        if _child.name().endswith('.'+_attr):
            break
    else:
        raise RuntimeError
    if _idx is not None:
        _child = _child.elementByLogicalIndex(_idx)

    _LOGGER.debug(' - FOUND CHILD %s', _child.name())

    return _head, _tail, _child


class CPlug(om.MPlug):  # pylint: disable=too-many-public-methods
    """Wrapper for OpenMaya.MPlug object."""

    def __init__(self, name, verbose=1):
        """Constructor.

        Args:
            name (str): plug name (eg. persp.tx)
            verbose (int): print process data
        """
        _LOGGER.debug('INIT %s', name)
        _name = name
        if isinstance(_name, CPlug):
            _name = str(_name)
        self.name = _name

        self._node_s, self.attr = _name.split('.', 1)
        self._node_n = pom_node.CNode(self._node_s)
        self._node = None  # Container for property

        try:
            _plug = _to_mplug(self._node_n, self.attr)
        except RuntimeError as _exc:
            if verbose:
                _LOGGER.info(' - ERROR %s', _exc)
            if not cmds.objExists(name):
                _err = 'Attribute not found {}'.format(_name)
            else:
                _err = 'Failed to build mplug {}'.format(_name)
            raise RuntimeError(_err)

        super(CPlug, self).__init__(_plug)

    @property
    def anim(self):
        """Find this plugs's animation curve.

        Returns:
            (CAnimCurve|None): animation curve (if any)
        """
        return self.to_anim()

    @property
    def node(self):
        """Obtain this plug's node.

        Returns:
            (CBaseNode): node
        """
        if not self._node:
            self._node = self.to_node()
        return self._node

    def attribute_query(self, **kwargs):
        """Apply maya.cmds attributeQuery to this node.

        Returns:
            (str list): attibute query result
        """
        return cmds.attributeQuery(self.attr, node=self.node, **kwargs)

    def break_connections(self):
        """Break any incoming connection to this plug."""
        _LOGGER.debug('BREAK CONNECTIONS %s', self)
        _incoming = cmds.listConnections(
            self, destination=False, plugs=True, connections=True)
        _LOGGER.debug(' - INCOMING %s', _incoming)
        if not _incoming:
            return
        _dest, _src = _incoming
        cmds.disconnectAttr(_src, _dest)

    def connect(self, target, break_connections=False, force=False):
        """Connect this plug to another one.

        Args:
            target (str): plug to connect to
            break_connections (bool): break incoming connections to target
                before making connection (supressed already connected
                warning)
            force (bool): replace any existing connections
        """
        if break_connections:
            target.break_connections()
        cmds.connectAttr(self, target, force=force)

    def delete(self):
        """Delete this attribute."""
        cmds.deleteAttr(self)

    def divide(self, input_, output=None):
        """Build a divide node with this plug as first input.

        Args:
            input_ (CPlug): second input
            output (CPlug): output

        Returns:
            (CPlug): output connection
        """
        _out = self.multiply(input_, output)
        _out.node.plug['operation'].set_enum('Divide')
        return _out

    def get_col(self):
        """Read this plug as a colour.

        Returns:
            (CColor): colour
        """
        _val = single(self.get_val())
        return qt.to_col(_val)

    def get_default(self):
        """Get default value for this plug.

        Returns:
            (any): default value
        """
        _LOGGER.debug(
            'GET DEFAULT %s attr=%s node=%s', self, self.attr, self.node)
        _defs = self.attribute_query(listDefault=True)
        if not _defs:
            return None
        _LOGGER.debug(' - DEFAULTS %s', _defs)
        _def = single(_defs)
        _type = self.get_type()
        _map = {'bool': bool,
                'byte': int}
        if _type in _map:
            _def = _map[_type](_def)
        _LOGGER.debug(' - TYPE %s', _type)
        return _def

    def get_enum(self):
        """Read the string value of an enum attribute.

        Returns:
            (str): enum value
        """
        return self.get_val(as_string=True)

    def get_ktvs(self):
        """Get key time values list.

        Returns:
            (tuple list): list of key values/times
        """
        _anim = self.to_anim()
        if not _anim:
            return []
        return _anim.get_ktvs()

    def get_max(self):
        """Get maximum value for this plug (if any).

        Returns:
            (float|None): maximum
        """
        return single(self.attribute_query(maximum=True), catch=True)

    def get_min(self):
        """Get minimum value for this plug (if any).

        Returns:
            (float|None): minimum
        """
        return single(self.attribute_query(minimum=True), catch=True)

    def get_size(self):
        """Read number of child elements in array attribute.

        Returns:
            (int): element count
        """
        return self.numElements()

    def get_type(self):
        """Get type of this attribute.

        Returns:
            (str): type name
        """
        return self.attribute_query(attributeType=True)

    def get_val(self, as_string=False, frame=None, class_=None):
        """Get current value of this plug.

        Args:
            as_string (bool): pass asString kwarg to getAttr
            frame (float): frame to read value on
            class_ (class): override class of result

        Returns:
            (any): attribute value
        """
        from maya_pini import open_maya as pom

        # Obtain result
        _kwargs = {}
        if as_string:
            _kwargs['asString'] = True
        if frame is not None:
            _kwargs['time'] = frame
        _result = cmds.getAttr(self, **_kwargs)

        # Handle result as None
        if _result is None:
            _type = self.get_type()
            if _type == 'typed':  # eg. aiStandIn.dso
                _result = ''
            else:
                raise NotImplementedError(_type)

        # Apply type casting
        if class_:
            if issubclass(class_, pom.CArray3):
                _result = single(_result)
            _result = class_(_result)

        return _result

    @functools.wraps(pom_utils.find_connections)
    def find_connections(
            self, source=True, destination=True,
            connections=False, plugs=True, type_=None):
        """Search connections on this attribute.

        Args:
            source (bool): include source connections
            destination (bool): include destination connections
            connections (bool): return source/dest pairs
            plugs (bool): return plugs rather than nodes
            type_ (str): filter by node type

        Returns:
            (tuple list): connections
        """
        _LOGGER.debug('FIND CONNECTIONS plugs=%d', plugs)
        return pom_utils.find_connections(
            self, source=source, destination=destination, type_=type_,
            connections=connections, plugs=plugs)

    def find_incoming(self, connections=False, plugs=True, type_=None):
        """Find connection coming into this plug.

        Args:
            connections (bool): return just the source (False - default)
                or source and destination (True)
            plugs (bool): return plugs rather than nodes
            type_ (str): filter by node type

        Returns:
            (CPlug|None): incoming connections
        """
        _conns = self.find_connections(
            source=True, destination=False, connections=connections,
            plugs=plugs, type_=type_)
        return single(_conns, catch=True)

    def find_outgoing(self, connections=False, plugs=True, type_=None):
        """Find an outgoing connection from this plug.

        Args:
            connections (bool): return just the source (False - default)
                or source and destination (True)
            plugs (bool): disable to return nodes rather than plugs
            type_ (str): filter by node type

        Returns:
            (CPlug list): outgoing connection (if any)
        """
        return self.find_connections(
            source=False, destination=True, connections=connections,
            plugs=plugs, type_=type_)

    def hide(self):
        """Hide this plug in channel box."""
        cmds.setAttr(self, keyable=False)

    def is_locked(self):
        """Test whether this plug is locked.

        Returns:
            (bool): locked
        """
        return self.isLocked

    def list_enum(self):
        """Read list of options in an enum attribute.

        Returns:
            (str list): enum options
        """
        _data = str(single(
            cmds.attributeQuery(self.attr, node=self.node, listEnum=True)))
        return _data.split(':')

    def loop(self, offset=False):
        """Loop this plug's animation curve.

        Args:
            offset (bool): apply cycle with offset
        """
        _mode = 'cycle' if not offset else 'cycleRelative'
        self.set_infinity(_mode)

    def lock(self, hide=False):
        """Unlock this plug.

        Args:
            hide (bool): hide from channel box
        """
        self.isLocked = True  # pylint: disable=invalid-name,attribute-defined-outside-init
        if hide:
            self.hide()

    def minus(self, input_, output=None):
        """Build a minus node with this plug as the first input.

        Args:
            input_ (CPlug): second input
            output (CPlug): output

        Returns:
            (CPlug): output connection
        """
        return minus_plug(self, input_, output=output)

    def modulo(self, modulo, output=None):
        """Build a modulo node with this plug as input.

        Args:
            modulo (CPlug|float): right hand input for modulo operation
            output (CPlug): output

        Returns:
            ():
        """
        from maya_pini import open_maya as pom
        cmds.loadPlugin('modulo', quiet=True)

        _mod = pom.CMDS.createNode('modulo')
        _mod_in = _mod.plug['input']
        _mod_mod = _mod.plug['modulo']
        _mod_out = _mod.plug['output']

        self.connect(_mod_in)

        if isinstance(modulo, (int, float)):
            _mod_mod.set_val(modulo)
        elif isinstance(modulo, CPlug):
            modulo.connect(_mod_mod)
        else:
            raise ValueError(modulo)

        if output:
            _mod.plug['output'].connect(output)

        return _mod_out

    def multiply(self, input_, output=None, name='multiply', force=False):
        """Build a multiply node with this plug as first input.

        Args:
            input_ (CPlug): second input
            output (CPlug): output
            name (str): override node name
            force (bool): replace any existing connection on the output

        Returns:
            (CPlug): output connection
        """
        from maya_pini import open_maya as pom

        _mult = pom.CMDS.createNode('multiplyDivide', name=name)
        cmds.connectAttr(self, _mult.plug['input1X'])

        # Set/connect input
        _i2x = _mult.plug['input2X']
        if isinstance(input_, (int, float)):
            cmds.setAttr(_i2x, input_)
        else:
            cmds.connectAttr(input_, _i2x)

        _out = _mult.plug['outputX']
        if output:
            cmds.connectAttr(_out, output, force=force)

        return _out

    def plus(self, input_, output=None, name='plus', force=False):
        """Build a plus node in with this plug as the first input.

        Args:
            input_ (CPlug): second input
            output (CPlug): output
            name (str): override node name
            force (bool): replace any existing output connection

        Returns:
            (CPlug): output plug on add node
        """
        return plus_plug(self, input_, output=output, name=name, force=force)

    def reverse(self):
        """Build a reverse node and connect it to this node.

        Returns:
            (CPlug): reverse output
        """
        from maya_pini import open_maya as pom
        _reverse = pom.CMDS.createNode('reverse')
        self.connect(_reverse.plug['inputX'])
        return _reverse.plug['outputX']

    def set_col(self, col):
        """Apply colour value to this plug.

        Args:
            col (CColor|str): colour (eg. OliveGreen)
        """
        _col = qt.to_col(col)
        self.set_val(_col)

    def set_enum(self, val):
        """Apply an enum value by its string value.

        Args:
            val (str): value to apply
        """
        set_enum(str(self), val)

    def set_infinity(self, mode='linear'):
        """Set infinity behaviour of this plug's animation.

        Default is pre/post linear.

        Args:
            mode (str): infinity mode to apply
        """
        assert mode in ['cycle', 'cycleRelative', 'linear']
        cmds.setInfinity(self, preInfinite=mode, postInfinite=mode)

    def set_key(self, val=None, frame=None, tangents='spline'):
        """Set keyframe on this plug.

        Args:
            val (float): key value
            frame (float): key time
            tangents (str): tangent type (eg. spline)
        """
        _itt, _ott = tangents, tangents
        if tangents == 'step':
            _itt = 'flat'
        _kwargs = {}
        if val is not None:
            _kwargs['value'] = val
        if frame is not None:
            _kwargs['time'] = frame
        cmds.setKeyframe(
            self, inTangentType=_itt, outTangentType=_ott, **_kwargs)

    def set_locked(self, locked=True):
        """Set locked state of this plug.

        Args:
            locked (bool): locked state to apply
        """
        self.isLocked = locked  # pylint: disable=attribute-defined-outside-init

    def set_tangents(self, type_):
        """Set tangents for this plug's animation.

        Args:
            type_ (str): tangent type to apply (eg. spline)
        """
        self.to_anim().set_tangents(type_)

    def set_val(self, val, break_connections=False, unlock=False):
        """Set value of this attribute.

        Args:
            val (any): value to apply
            break_connections (bool): break connections on apply value
            unlock (bool): unlock attr before apply
        """
        _LOGGER.debug('SET VAL %s %s', self, val)
        from maya_pini import open_maya as pom

        if break_connections:
            self.break_connections()
        if unlock:
            self.unlock()

        # Apply value
        if isinstance(val, six.string_types):
            cmds.setAttr(self, val, type='string')
            return
        if isinstance(val, (pom.CArray3, qt.CColor)):
            cmds.setAttr(self, *val.to_tuple())
            return
        if isinstance(val, (tuple, list)) and len(val) == 3:
            cmds.setAttr(self, *val)
            return
        cmds.setAttr(str(self), val)

    def t_dur(self):
        """Obtain this plugs's animation duration on the timeline.

        Returns:
            (float|None): duration (if animated)
        """
        if not self.anim:
            return None
        return self.anim.t_dur()

    def t_offset(self, offset):
        """Apply time offset to this node's animation.

        Args:
            offset (float): offset to apply (in frames)
        """
        _anim = self.anim
        if not _anim:
            raise ValueError(self)
        _anim.t_offset(offset)

    def t_range(self, class_=float):
        """Obtain this plug's animation range.

        Args:
            class_ (class): override result class

        Returns:
            (tuple|None): start/end frames
        """
        _anim = self.anim
        if not _anim:
            raise ValueError(self)
        return _anim.t_range(class_=class_)

    def to_anim(self):
        """Find any anim curve attached to this plug.

        Returns:
            (CAnimCurve|None): anim curve (if any)
        """
        from maya_pini import open_maya as pom
        return single(pom.CMDS.listConnections(self, type='animCurve'),
                      catch=True)

    def to_node(self):
        """Obtain this plug's node.

        Returns:
            (CBaseNode): node
        """
        from maya_pini import open_maya as pom
        return pom.cast_node(self._node_s, maintain_shapes=True)

    def to_long(self):
        """Obtain this attribute's long name.

        Returns:
            (str): long name (eg. translateX)
        """
        return cmds.attributeQuery(self.attr, node=self.node, longName=True)

    def unlock(self):
        """Unlock this plug."""
        self.isLocked = False  # pylint: disable=invalid-name,attribute-defined-outside-init

    def __hash__(self):
        return hash(str(self))

    def __lt__(self, other):
        return str(self) < str(other)

    def __str__(self):
        return self.name

    def __repr__(self):
        return basic_repr(self, self.name, separator='|')


def plus_plug(input1, input2, output=None, name='plus', force=False):
    """Build a plus node in with the given values as inputs.

    Args:
        input1 (CPlug|float): first/left value
        input2 (CPlug|float): second/right value
        output (CPlug): output
        name (str): override node name
        force (bool): replace any existing output connection

    Returns:
        (CPlug): output plug on add node
    """
    _LOGGER.debug('PLUG PLUG')
    _add = cmds.createNode('plusMinusAverage', name=name)
    _connect_types = tuple(list(six.string_types)+[CPlug])

    # Determine attr size
    if isinstance(input1, CPlug):
        _type = input1.get_type()
    elif isinstance(input2, CPlug):
        _type = input2.get_type()
    else:
        raise ValueError(f'Unable to determine type {input1}/{input2}')
    _size = {
        'doubleLinear': 1,
        'double3': 3,
        'float': 1,
        'long': 1,
    }[_type]
    _LOGGER.debug(' - SIZE %d type=%s', _size, _type)

    # Connect/set input0
    _attr_0 = '{}.input{:d}D[0]'.format(_add, _size)
    _LOGGER.debug(' - ATTR 0 %s', _attr_0)
    if isinstance(input1, _connect_types):
        cmds.connectAttr(input1, _attr_0)
    else:
        cmds.setAttr(_attr_0, input1)

    # Connect/set input1
    _attr_1 = '{}.input{:d}D[1]'.format(_add, _size)
    _LOGGER.debug(' - ATTR 1 %s', _attr_1)
    if isinstance(input2, _connect_types):
        cmds.connectAttr(input2, _attr_1)
    else:
        cmds.setAttr(_attr_1, input2)

    # Connect output
    _output = '{}.output{:d}D'.format(_add, _size)
    _LOGGER.debug(' - OUTPUT %s', _output)
    if output:
        cmds.connectAttr(_output, output, force=force)

    return CPlug(_output)


def minus_plug(input1, input2, output=None, force=False):
    """Build a minus node with the given values as inputs.

    Args:
        input1 (CPlug|float): first/left value
        input2 (CPlug|float): second/right value
        output (CPlug): output
        force (bool): replace any existing output connection

    Returns:
        (CPlug): output plug on add node
    """
    _out = plus_plug(input1, input2, output=output, force=force)
    _out.node.plug['operation'].set_enum('Subtract')
    return _out


def selected_plug():
    """Obtain currently selected plug in channel box.

    Returns:
        (CPlug): select plug
    """
    return single(selected_plugs())


def selected_plugs():
    """Get list of plugs selected in channel box.

    Returns:
        (CPlug list): selected plugs
    """
    from maya_pini import open_maya as pom
    _plugs = []
    _attrs = cmds.channelBox(
        "mainChannelBox", query=True, selectedMainAttributes=True) or []
    for _node in pom.get_selected(multi=True):
        for _attr in _attrs:
            _plug = _node.plug[_attr]
            _plugs.append(_plug)
    return _plugs


def to_plug(attr):
    """Obtain a plug object for the given attribute.

    Args:
        attr (str): attribute (eg. persp.tx)

    Returns:
        (CPlug|None): plug (if any)
    """
    try:
        return CPlug(attr, verbose=0)
    except RuntimeError:
        return None
