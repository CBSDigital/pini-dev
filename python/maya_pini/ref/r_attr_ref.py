"""Tools for managing attribute references.

eg. file texture path on a file node.
"""

import logging

from maya import cmds

from pini.utils import (
    basic_repr, norm_path, File, split_base_index, is_abs, abs_path,
    to_seq, Seq)
from maya_pini.utils import to_node, to_namespace

from . import r_path_ref

_LOGGER = logging.getLogger(__name__)


class AttrRef(r_path_ref.PathRef):
    """Represents a path reference stored in an attribute."""

    def __init__(self, attr, node_type=None):
        """Constructor.

        Args:
            attr (str): attribute
            node_type (str): attribute node type
        """
        self.attr = attr
        self.node_type = node_type

        _node, _attr = self.attr.split('.', 1)
        _base, _idx = split_base_index(_node)
        self.cmp_key = _base, _idx, _attr

    @property
    def has_udim_tiles(self):
        """Test whether this reference uses udim tiles.

        Returns:
            (bool): whether udim tiles
        """
        if self.node_type != 'file':
            return False
        _tiling_mode = cmds.getAttr(
            f'{self.node}.uvTilingMode', asString=True)
        return _tiling_mode == 'UDIM (Mari)'

    @property
    def namespace(self):
        """Obtain namespace for this attribute's node.

        Returns:
            (str): namespace
        """
        return to_namespace(self.attr)

    @property
    def node(self):
        """Obtain this attribute reference's node.

        Returns:
            (str): node
        """
        return to_node(self.attr)

    @property
    def path(self):
        """Obtain path to this reference.

        Returns:
            (str): path
        """
        _path = cmds.getAttr(self.attr)
        if _path:
            if is_abs(_path):
                _path = abs_path(_path)
            else:
                _path = norm_path(_path)
        _path = File(_path)

        if self.has_udim_tiles:
            _path = to_seq(_path)

        return _path

    def exists(self):
        """Test whether this path being referenced exists.

        Returns:
            (bool): whether path exists
        """
        return self.path.exists()

    def update(self, path):
        """Update this reference.

        Args:
            path (str): path to update to
        """
        _path = path
        if self.has_udim_tiles:
            assert isinstance(self.path, Seq)
            _cur_path = abs_path(cmds.getAttr(self.attr))
            if _cur_path != self.path[1001]:
                _LOGGER.info(' - PATH       %s', self.path)
                _LOGGER.info(' - FRAME 1001 %s', self.path[1001])
                _LOGGER.info(' - CUR PATH   %s', _cur_path)
                raise RuntimeError(f'Bad cur path {_cur_path}')
            _path = path[1001]
        cmds.setAttr(self.attr, _path, type='string')

    def __repr__(self):
        return basic_repr(self, self.attr)


def find_attr_refs(types=(), referenced=None):
    """Find attribute references in the current scene.

    Args:
        types (tuple): limit the types of node returned
        referenced (bool): filter by referenced status

    Returns:
        (AttrRef list): attribute references
    """

    # Build list of types to check
    _types = [
        ('file', 'fileTextureName'),
        ('imagePlane', 'imageName'),
        ('audio', 'filename')]
    if cmds.pluginInfo('mtoa', query=True, loaded=True):
        _types += [
            ('aiImage', 'filename'),
            ('aiStandIn', 'dso')]
    if cmds.pluginInfo('redshift4maya', query=True, loaded=True):
        _types += [
            ('RedshiftProxyMesh', 'fileName'),
            ('RedshiftSprite', 'tex0')]

    # Check files
    _a_refs = []
    for _type, _attr in _types:

        if types and _type not in types:
            continue

        for _node in cmds.ls(type=_type):

            # Obtain node
            _node = _node.split('->')[-1]  # Fix weird image planes
            if not cmds.objExists(_node):  # Ignore weird missing image planes
                continue

            # Apply referenced filter
            if referenced is not None and referenced != cmds.referenceQuery(
                    _node, isNodeReferenced=True):
                continue

            # Build AttrRef object
            _a_ref = AttrRef(f'{_node}.{_attr}', node_type=_type)
            if not _a_ref.path:
                continue

            _a_refs.append(_a_ref)

    return _a_refs
