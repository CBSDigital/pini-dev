"""Tools for managing the OpenMaya.MFnAnimCurve wrapper."""

import logging

from maya import cmds
from maya.api import OpenMayaAnim as oma

from pini.utils import single

from .. import base
from ..pom_utils import to_mobject

_LOGGER = logging.getLogger(__name__)


class CAnimCurve(base.CBaseNode, oma.MFnAnimCurve):
    """Represets an anim curve node."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): anim curve node name
        """
        super(CAnimCurve, self).__init__(node)
        _mobj = to_mobject(node)
        oma.MFnAnimCurve.__init__(self, _mobj)

    @property
    def input(self):
        """Obtain input plug.

        This controls anim curve time.

        Returns:
            (CPlug): input
        """
        return self.plug['input']

    @property
    def output(self):
        """Obtain output plug.

        Returns:
            (CPlug): output
        """
        return self.plug['output']

    @property
    def target(self):
        """Get this curve's animation target attribute.

        Returns:
            (CPlug): target
        """
        return single(self.output.find_outgoing())

    def connect(self, plug, force=False):
        """Connect this anim curve to the given plug.

        Args:
            plug (CPlug): plug to connect to
            force (bool): replace any existing conections
        """
        self.output.connect(plug, force=force)

    def delete_keys(self, range_):
        """Delete keys in the given frame range.

        Args:
            range_ (tuple): start/end frames
        """
        _LOGGER.debug('DELETE KEYS %s', self)
        cmds.cutKey(self, time=range_)

    def fix_name(self):
        """Fix name to match target channel.

        Returns:
            (CAnimCurve): updated node
        """
        _name = str(self.target).replace('.', '_')
        _LOGGER.debug('FIX NAME %s %s', self, _name)
        _node = self
        if self != _name:
            _node = self.rename(_name)
            _LOGGER.debug(' - FIXED NAME %s', _node)
        return _node

    def get_ktvs(self):
        """Read keyframe time/value list from this curve.

        Returns:
            (float/float list): frame/value data list
        """
        return cmds.getAttr(self.attr['keyTimeValue[:]'])

    def loop(self, offset=False):
        """Loop this animation curve.

        Args:
            offset (bool): apply cycle with offset
        """
        _mode = 'cycle' if not offset else 'cycleRelative'
        self.set_infinity(_mode)

    def set_infinity(self, mode):
        """Set pre and post infinity mode for this animation.

        Args:
            mode (str): mode to apply (eg. cycle/cycleOffset/linear)
        """
        self.target.set_infinity(mode)

    def set_tangents(self, type_):
        """Set tangents for this curve.

        Args:
            type_ (str): tangent type to apply
        """
        cmds.keyTangent(self, inTangentType=type_, outTangentType=type_)

    def t_dur(self):
        """Obtain this animation's timeline duration.

        Returns:
            (float): duration in frames
        """
        _start, _end = self.t_range()
        return _end - _start

    def t_offset(self, offset):
        """Apply time offset to this animation.

        Args:
            offset (float): offset to apply (in frames)
        """
        cmds.keyframe(
            self, edit=True, option='over', timeChange=offset,
            includeUpperBound=True, relative=True)

    def t_range(self, class_=None):
        """Obtain timeline range for this node.

        Args:
            class_ (type): override result class

        Returns:
            (tuple): start/end frames
        """
        _ktvs = self.get_ktvs()
        _ts = [_t for _t, _ in _ktvs]
        _start, _end = min(_ts), max(_ts)
        if class_ is float or class_ is None:
            pass
        elif class_ is int:
            _start = int(round(_start, 0))
            _end = int(round(_end, 0))
        else:
            raise ValueError(class_)

        return _start, _end


def find_anim():
    """Find anim curves in this scene.

    Returns:
        (CAnimCurve): anim curves
    """
    from maya_pini import open_maya as pom
    return pom.CMDS.ls(type='animCurve')
