"""Tools for managing attribute references.

eg. file texture path on a file node.
"""

from maya import cmds

from pini.utils import basic_repr, norm_path
from maya_pini.utils import to_node, to_namespace

from . import r_path_ref


class AttrRef(r_path_ref.PathRef):
    """Represents a path reference stored in an attribute."""

    def __init__(self, attr):
        """Constructor.

        Args:
            attr (str): attribute
        """
        self.attr = attr
        self.cmp_str = self.attr

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
        return norm_path(_path) if _path else None

    def update(self, path):
        """Update this reference.

        Args:
            path (str): path to update to
        """
        cmds.setAttr(self.attr, path, type='string')

    def __repr__(self):
        return basic_repr(self, self.attr)


def find_attr_refs(types=()):
    """Find attribute references in the current scene.

    Args:
        types (tuple): limit the types of node returned

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
            _node = _node.split('->')[-1]  # Fix weird image planes
            if not cmds.objExists(_node):  # Ignore weird missing image planes
                continue
            _a_ref = AttrRef(f'{_node}.{_attr}')
            if not _a_ref.path:
                continue
            _a_refs.append(_a_ref)

    return _a_refs
