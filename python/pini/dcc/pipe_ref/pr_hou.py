"""Tools for managing pipelined references in houdini."""

import logging

import hou

from pini.utils import abs_path, File, single, check_heart

from . import pr_base

_LOGGER = logging.getLogger(__name__)


class CHouAbcGeometryRef(pr_base.CPipeRef):
    """Represents a geometry abc referenced into houdini via an alembic sop."""

    def __init__(self, node, namespace=None):
        """Constructor.

        Args:
            node (Node): alembic sop
            namespace (str): override node namespace
        """
        self.node = node
        _file = abs_path(node.parm('fileName').eval())
        _ns = namespace or node.parent().name()
        super(CHouAbcGeometryRef, self).__init__(path=_file, namespace=_ns)

    def delete(self, force=False):
        """Delete this reference from the current scene.

        Args:
            force (bool): remove without confirmation
        """
        if not force:
            raise NotImplementedError
        _parent = self.node.parent()
        assert len(_parent.children()) == 2
        _parent.destroy()

    def update(self, out):
        """Update this abc to another path.

        Args:
            out (str): abc to update to
        """
        _file = File(out)
        self.node.parm('fileName').set(_file.path)
        self.path = _file.path


class CHouAbcArchiveRef(CHouAbcGeometryRef):
    """Represents an abc archive referenced into houdini.

    Geometry is referenced via an alembicarchive object node.
    """

    def __init__(self, node):
        """Constructor.

        Args:
            node (Node): alembicarchive object node
        """
        super(CHouAbcArchiveRef, self).__init__(
            node=node, namespace=node.name())

    def delete(self, force=False):
        """Delete this reference from the current scene.

        Args:
            force (bool): remove without confirmation
        """
        if not force:
            raise NotImplementedError
        self.node.destroy()

    def update(self, out):
        """Update this abc to another path.

        Args:
            out (str): abc to update to
        """
        super(CHouAbcArchiveRef, self).update(out)
        self.node.parm('buildHierarchy').pressButton()
        self.update_res()

    def update_res(self):
        """Update camera resolution.

        This should be stored in the camera abc's metadata on export. It's
        applied to the resolutiuon field on the camera shape node.
        """

        # Update res
        _res = self.output.metadata.get('res')
        if not _res:
            _LOGGER.info('NO RES FOUND IN METADATA %s', self.output)
            return
        _width, _height = _res
        _LOGGER.info('APPLY RES %s %s %d %d', self, _res, _width, _height)

        _cam = single([
            _node for _node in self.node.recursiveGlob('*')
            if _node.type().name() == 'cam'])
        _LOGGER.info(' - CAM %s', _cam)
        _cam.parmTuple('res').set(_res)


def find_pipe_refs(selected=False):
    """Find pipe refs in the current scene.

    Args:
        selected (bool): return only selected refs

    Returns:
        (CHouAbcGeometryRef): ref list
    """
    _LOGGER.debug('READ PIPE REFS')
    _refs = []
    for _cat, _type, _class in [
            (hou.objNodeTypeCategory, 'alembicarchive', CHouAbcArchiveRef),
            (hou.sopNodeTypeCategory, 'alembic', CHouAbcGeometryRef),
    ]:
        for _node in _cat().nodeType(_type).instances():

            _LOGGER.debug('CHECKING NODE %s', _node)

            # Check if node references pipeline output
            try:
                _ref = _class(_node)
            except ValueError:
                continue

            _refs.append(_ref)

    # Remove nodes inside other nodes
    _paths = sorted([_ref.node.path() for _ref in _refs])
    _reject_paths = []
    while _paths:
        _path = _paths.pop(0)
        while _paths and _paths[0].startswith(_path):
            _LOGGER.debug(' - REMOVING %s', _paths[0])
            check_heart()
            _reject_paths.append(_paths.pop(0))
    if _reject_paths:
        _LOGGER.debug(' - REMOVING NESTED NODES %s', _reject_paths)
        _refs = [
            _ref for _ref in _refs if _ref.node.path() not in _reject_paths]

    # Apply selected filter
    if selected:
        _refs = [_ref for _ref in _refs if _ref_is_selected(_ref)]

    return _refs


def _ref_is_selected(ref):
    """Test whether the given reference is selected.

    Args:
        ref (CHouAbcGeometryRef): reference to test

    Returns:
        (bool): whether reference is selected
    """
    _root = ref.node
    while _root.parent() != hou.node('/obj'):
        check_heart()
        _root = _root.parent()
    _sel = _root in hou.selectedNodes()
    return _sel
