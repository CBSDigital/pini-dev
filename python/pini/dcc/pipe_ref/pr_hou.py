"""Tools for managing pipelined references in houdini."""

import logging

from pini.utils import abs_path, File, single

from . import pr_base

_LOGGER = logging.getLogger(__name__)


class CHouAbcRef(pr_base.CPipeRef):
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
        super(CHouAbcRef, self).__init__(path=_file, namespace=_ns)

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

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

    def update(self, out):
        """Update this abc to another path.

        Args:
            out (str): abc to update to
        """
        _file = File(out)
        self.node.parm('fileName').set(_file.path)
        self.path = _file.path


class CHouAbcCamRef(CHouAbcRef):
    """Represents a camera abc referenced into houdini.

    Cameras are referenced via an alembicarchive object node.
    """

    def __init__(self, node):
        """Constructor.

        Args:
            node (Node): alembicarchive object node
        """
        super(CHouAbcCamRef, self).__init__(node=node, namespace=node.name())

    def delete(self, force=False):
        """Delete this reference from the current scene.

        Args:
            force (bool): remove without confirmation
        """
        if not force:
            raise NotImplementedError
        self.node.destroy()

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

    def update(self, out):
        """Update this abc to another path.

        Args:
            out (str): abc to update to
        """
        super(CHouAbcCamRef, self).update(out)
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
