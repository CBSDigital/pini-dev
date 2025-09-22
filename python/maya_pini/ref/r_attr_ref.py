"""Tools for managing attribute references.

eg. file texture path on a file node.
"""

import logging
import re

from maya import cmds

from pini.utils import (
    basic_repr, norm_path, File, split_base_index, is_abs, abs_path,
    file_to_seq, Seq, to_seq)
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
        self._node_type = node_type

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
    def node_type(self):
        """Obtain node type.

        Returns:
            (str): type
        """
        if self._node_type is None:
            self._node_type = cmds.objectType(self.attr)
        return self._node_type

    @property
    def path(self):
        """Obtain path to this reference.

        Returns:
            (File|Seq|None): path
        """
        _path = cmds.getAttr(self.attr)
        _LOGGER.debug('   - READ PATH %s %s', self, _path)
        if not _path:
            return None

        if is_abs(_path):
            _path = abs_path(_path)
        else:
            _path = norm_path(_path)
        _path = File(_path)
        _LOGGER.debug('     - UPDATED PATH %s', _path)

        _LOGGER.debug('     - UDIM TILES %d', self.has_udim_tiles)
        if self.has_udim_tiles:
            try:
                _path = file_to_seq(_path, safe=False, frame_expr='<UDIM>')
                _LOGGER.debug('     - TO SEQ %s', _path)
            except ValueError:
                _LOGGER.debug('     - FAILED TO READ UDIM %s', _path)

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

            _path = to_seq(_path)
            assert isinstance(self.path, Seq)

            # Maintain same frame (if applicable)
            _cur_path = abs_path(cmds.getAttr(self.attr))
            _f_str = re.split('[_.]', _cur_path)[-2]
            if _f_str.isdigit():
                _cur_frame = int(_f_str)
                if _cur_path != self.path[_cur_frame]:
                    _LOGGER.info(' - PATH       %s', self.path)
                    _LOGGER.info(
                        ' - FRAME %d %s', _cur_frame, self.path[_cur_frame])
                    _LOGGER.info(' - CUR PATH   %s', _cur_path)
                    raise RuntimeError(f'Bad cur path {_cur_path}')
                _path = _path[_cur_frame]

        cmds.setAttr(self.attr, _path, type='string')

    def __repr__(self):
        return basic_repr(self, self.attr)


def find_attr_refs(types=(), type_=None, referenced=None):
    """Find attribute references in the current scene.

    Args:
        types (tuple): limit the types of node returned
        type_ (str): return only nodes of this type
        referenced (bool): filter by referenced status

    Returns:
        (AttrRef list): attribute references
    """
    _LOGGER.debug('FIND ATTR REFS')

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

    _limit_types = []
    if type_:
        _limit_types += [type_]
    if types:
        _limit_types += list(types)

    # Check files
    _a_refs = []
    for _type, _attr in _types:

        if _limit_types and _type not in _limit_types:
            continue

        _nodes = cmds.ls(type=_type)
        _LOGGER.debug('CHECKING %s - %d %s', _type, len(_nodes), _nodes)
        for _node in _nodes:

            _LOGGER.debug(' - NODE %s', _node)

            # Obtain node
            _node = _node.split('->')[-1]  # Fix weird image planes
            if not cmds.objExists(_node):  # Ignore weird missing image planes
                continue
            _LOGGER.debug('   - NODE (B) %s', _node)

            # Apply referenced filter
            if referenced is not None and referenced != cmds.referenceQuery(
                    _node, isNodeReferenced=True):
                continue

            # Build AttrRef object
            _chan = f'{_node}.{_attr}'
            _LOGGER.debug('   - CHAN %s', _chan)
            _a_ref = AttrRef(_chan, node_type=_type)
            _LOGGER.debug('   - CHECKING NODE %s %s', _chan, _a_ref.path)
            if not _a_ref.path:
                continue

            _a_refs.append(_a_ref)

    return _a_refs
