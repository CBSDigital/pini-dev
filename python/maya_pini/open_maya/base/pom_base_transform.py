"""Base class to underlie all transform classes."""

# pylint: disable=invalid-name

import logging

from maya import cmds

from pini.utils import single, passes_filter

from . import pom_base_node

_LOGGER = logging.getLogger(__name__)


class CBaseTransform(pom_base_node.CBaseNode):  # pylint: disable=too-many-public-methods
    """Base class for any transform node."""

    @property
    def translate(self):
        """Obtain translate plug.

        Returns:
            (CPlug): translate
        """
        return self.plug['translate']

    @property
    def tx(self):
        """Obtain tx plug.

        Returns:
            (CPlug): tx
        """
        return self.plug['tx']

    @property
    def ty(self):
        """Obtain ty plug.

        Returns:
            (CPlug): ty
        """
        return self.plug['ty']

    @property
    def tz(self):
        """Obtain tz plug.

        Returns:
            (CPlug): tz
        """
        return self.plug['tz']

    @property
    def t_plugs(self):
        """Obtain translate plugs.

        Returns:
            (CPlug list): translate plugs
        """
        return [self.plug[_attr] for _attr in ('tx', 'ty', 'tz')]

    @property
    def rotate(self):
        """Obtain rotate plug.

        Returns:
            (CPlug): rotate
        """
        return self.plug['rotate']

    @property
    def rx(self):
        """Obtain rx plug.

        Returns:
            (CPlug): rx
        """
        return self.plug['rx']

    @property
    def ry(self):
        """Obtain ry plug.

        Returns:
            (CPlug): ry
        """
        return self.plug['ry']

    @property
    def rz(self):
        """Obtain rz plug.

        Returns:
            (CPlug): rz
        """
        return self.plug['rz']

    @property
    def r_plugs(self):
        """Obtain rotate plugs.

        Returns:
            (CPlug list): rotate plugs
        """
        return [self.plug[_attr] for _attr in ('rx', 'ry', 'rz')]

    @property
    def scale(self):
        """Obtain scale plug.

        Returns:
            (CPlug): scale
        """
        return self.plug['scale']

    @property
    def sx(self):
        """Obtain sx plug.

        Returns:
            (CPlug): sx
        """
        return self.plug['sx']

    @property
    def sy(self):
        """Obtain sy plug.

        Returns:
            (CPlug): sy
        """
        return self.plug['sy']

    @property
    def sz(self):
        """Obtain sz plug.

        Returns:
            (CPlug): sz
        """
        return self.plug['sz']

    @property
    def s_plugs(self):
        """Obtain scale plugs.

        Returns:
            (CPlug list): scale plugs
        """
        return [self.plug[_attr] for _attr in ('sx', 'sy', 'sz')]

    @property
    def tfm_plugs(self):
        """Obtain list of transform plugs.

        Returns:
            (CPlug list): transform plugs
        """
        return self.to_tfm_plugs()

    @property
    def visibility(self):
        """Obtain visibility plug.

        Returns:
            (CPlug): visibility
        """
        return self.plug['visibility']

    def find_children(
            self, type_=None, recursive=False, class_=None, filter_=None):
        """Find children of this node.

        Args:
            type_ (str): filter by type
            recursive (bool): recurve into children's children
            class_ (class): cast results to this node type, ignoring
                any which fail to cast
            filter_ (str): filter by child name

        Returns:
            (CNode list): children
        """
        _LOGGER.debug('FIND CHILDREN %s', self)

        _kwargs = {}
        if type_:
            _kwargs['type'] = type_

        _children = []
        for _child in self.cmds.listRelatives(
                children=True, path=True, **_kwargs):

            _LOGGER.debug(' - CHILD %s', _child)

            if filter_ and not passes_filter(str(_child), filter_):
                continue

            # Test if this result should be added
            _result = _child
            if class_:
                try:
                    _result = class_(str(_result))
                except ValueError:
                    _result = None
            if _result:
                _children.append(_result)

            # Apply recursion
            if recursive and isinstance(_child, CBaseTransform):
                _children += _child.find_children(
                    type_=type_, recursive=True, class_=class_)

        return _children

    def flush(self):
        """Flush this node's history and transformation.

        This resets the pivot to the origin, freezes transforms
        and deletes construction history.
        """
        self.set_pivot()
        self.freeze_tfms()
        self.delete_history()

    def fix_shp_name(self):
        """Make sure shape name matches transform name."""
        _LOGGER.debug('FIX SHP %s', self.shp)
        _name = str(self)+'Shape'
        _LOGGER.debug(' - NAME %s', _name)
        if _name != self.shp:
            _LOGGER.debug(' - APPLYING FIX')
            self.shp.rename(_name)

    def freeze_tfms(
            self, translate=True, rotate=True, scale=True, force=False):
        """Freeze transforms on this node.

        Args:
            translate (bool): freeze translation
            rotate (bool): freeze rotation
            scale (bool): freeze scale
            force (bool): break connections before freeze
        """
        _LOGGER.debug('FREEZE TFMS %s', self)
        if force:
            for _plug in self.tfm_plugs:
                _LOGGER.debug(' - BREAK CONNS %s', _plug)
                _plug.break_connections()
                _plug.unlock()
        cmds.makeIdentity(
            self, apply=True, translate=translate, rotate=rotate, scale=scale,
            normal=False, preserveNormals=True)

    def hide(self):
        """Hide this node."""
        self.set_visible(False)

    def is_visible(self):
        """Test whether this node is visible.

        Returns:
            (bool): whether visible
        """
        return self.visibility.get_val()

    def lock_tfms(self):
        """Lock transforms on this node."""
        for _axis in 'xyz':
            for _attr, _val in [('t', 0), ('r', 0), ('s', 1)]:
                self.plug[_attr+_axis].locked = True

    def move(self, *args):
        """Move this object relative to its current position."""
        if len(args) == 1:
            _vec = single(args)
            _args = [_vec.x, _vec.y, _vec.z, self]
        elif len(args) == 3:
            _args = [args[0], args[1], args[2], self]
        else:
            raise ValueError(args)
        cmds.move(*_args, relative=True)

    def orient_constraint(self, target, maintain_offset=False):
        """Build an orient constraint from this node to the given target.

        Args:
            target (CTransform): node to constrain
            maintain_offset (bool): maintain offset

        Returns:
            (CTransform): constraint
        """
        from maya_pini import open_maya as pom
        return pom.CMDS.orientConstraint(
            self, target, maintainOffset=maintain_offset)

    def parent_constraint(
            self, target, maintain_offset=False, name=None, force=False):
        """Build a parent constraint from this node to the given target.

        Args:
            target (CTransform): node to constrain
            maintain_offset (bool): maintain offset
            name (str): name for constraint node
            force (bool): break connections on target before apply constraint
                to avoid already connected error

        Returns:
            (CTransform): constraint
        """
        from maya_pini import open_maya as pom
        _trg = pom.CTransform(target)
        _LOGGER.info('PARENT CONSTRAINT %s -> %s', self, _trg)
        _kwargs = {}
        if name:
            _kwargs['name'] = name
        if force:
            for _plug in _trg.to_tfm_plugs(scale=False):
                _LOGGER.debug(' - BREAK CONNECT %s', _plug)
                _plug.break_connections()
        return pom.CMDS.parentConstraint(
            self, target, maintainOffset=maintain_offset, **_kwargs)

    def point_constraint(self, target, maintain_offset=False, skip=None):
        """Build a point constraint from this node to the given target.

        Args:
            target (CTransform): node to constrain
            maintain_offset (bool): maintain offset
            skip (str): axes to skip (eg. y)

        Returns:
            (CTransform): constraint
        """
        from maya_pini import open_maya as pom
        _kwargs = {}
        if skip is not None:
            _kwargs['skip'] = skip
        return pom.CMDS.pointConstraint(
            self, target, maintainOffset=maintain_offset, **_kwargs)

    def scale_constraint(self, target, maintain_offset=False):
        """Build a scale constraint from this node to the given target.

        Args:
            target (CTransform): node to constrain
            maintain_offset (bool): maintain offset

        Returns:
            (CTransform): constraint
        """
        from maya_pini import open_maya as pom
        return pom.CMDS.scaleConstraint(
            self, target, maintainOffset=maintain_offset)

    def reset_tfms(self, scale=True, break_connections=False):
        """Reset transforms on this node.

        Args:
            scale (bool): reset scale
            break_connections (bool): break connections on reset
        """
        _attrs = 'tr'
        if scale:
            _attrs += 's'
        for _axis in 'xyz':
            for _attr in _attrs:
                _val = {'s': 1, 't': 0, 'r': 0}[_attr]
                _plug = self.plug[_attr+_axis]
                if break_connections:
                    _plug.break_connections()
                _plug.set_val(_val)

    def set_p(self, pos):
        """Apply the given position to this node.

        Args:
            pos (CPoint): position to apply
        """
        pos.apply_to(self)

    def set_pivot(self, pos=None, scale=True, rotate=True):
        """Set pivot on this node.

        By default pivot is set to the origin.

        Args:
            pos (CPoint): pivot to apply
            scale (bool): apply to scale pivot
            rotate (bool): apply to rotate pivot
        """
        from maya_pini import open_maya as pom
        _pos = pos or pom.ORIGIN
        for _toggle, _plug in [
                (scale, self.plug['scalePivot']),
                (rotate, self.plug['rotatePivot'])]:
            if _toggle:
                cmds.move(_pos[0], _pos[1], _pos[2], _plug)

    def set_visible(self, visible=True, unlock=False):
        """Set this transform's visibility.

        Args:
            visible (bool): visibility to apply
            unlock (bool): also unlock attribute
        """
        self.visibility.set_val(visible, unlock=unlock)

    def solidify(self, col='Yellow'):
        """Solidify this transform.

        This locks and hides the transform channels and colours it in
        yellow in the outliner. It is used to mark this group as for
        organsation only (eg. for CHAR/PROP/GEO groups) and to avoid
        artists applying transforms to it, which could affect future
        imports using this group.

        Args:
            col (str): override group colour
        """
        self.set_outliner_col(col)
        for _plug in self.tfm_plugs:
            _plug.lock()
            _plug.hide()
            if _plug.get_val() != _plug.get_default():
                raise RuntimeError(
                    f'Failed to solidify non-default value {_plug}')

    def to_tfm_plugs(self, translate=True, rotate=True, scale=True):
        """Find transformation plugs.

        Args:
            translate (bool): include translate plugs
            rotate (bool): include rotate plugs
            scale (bool): include scale plugs

        Returns:
            (CPlug list): transformation plugs
        """
        _plugs = []
        if translate:
            _plugs += [self.tx, self.ty, self.tz]
        if rotate:
            _plugs += [self.rx, self.ry, self.rz]
        if scale:
            _plugs += [self.sx, self.sy, self.sz]
        return _plugs

    def unhide(self, unlock=False):
        """Unhide this node.

        Args:
            unlock (bool): unlock visibility if locked
        """
        return self.set_visible(unlock=unlock)

    def unlock_tfms(self):
        """Unlock transforms on this node."""
        _plugs = []
        for _attr in 'trs':
            _plug = f'{self}.{_attr}'
            _plugs.append(_plug)
            for _axis in 'xyz':
                _plug = f'{self}.{_attr}{_axis}'
                _plugs.append(_plug)
        for _plug in _plugs:
            cmds.setAttr(_plug, lock=False)

    def u_scale(self, scale):
        """Apply uniform scale to this noode.

        Args:
            scale (float): scale to apply
        """
        assert isinstance(scale, (float, int))
        for _plug in [self.sx, self.sy, self.sz]:
            _plug.set_val(scale)
