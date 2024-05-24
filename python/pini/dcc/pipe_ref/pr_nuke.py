"""Tools for managing pipelined references (read nodes) in nuke."""

import functools
import logging

import nuke

from pini.utils import Seq, File, Video

from . import pr_base

_LOGGER = logging.getLogger(__name__)


class _CNukePipeRef(pr_base.CPipeRef):
    """Base class for any pipelined file reference in nuke."""

    update = pr_base.CPipeRef.update

    def __init__(self, path, node):
        """Constructor.

        Args:
            path (str): node reference path
            node (Node): read node
        """
        super(_CNukePipeRef, self).__init__(
            path=path, namespace=node.name())
        self.node = node

    def delete(self, force=False):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
        """
        if not force:
            raise NotImplementedError
        nuke.delete(self.node)


class CNukeAbcRef(_CNukePipeRef):
    """Represents an abc reference in a ReadGeo node."""

    def update(self, out):
        """Update this node to a new path.

        Args:
            out (str): path to apply
        """
        _file = File(out)  # In case path is File
        self.node['file'].setValue(_file.path)


class CNukeCamAbcRef(CNukeAbcRef):
    """Represents a camera abc reference in a Camera node."""

    @functools.wraps(_CNukePipeRef.__init__)
    def __init__(self, *args, **kwargs):
        """Constructor."""
        super(CNukeCamAbcRef, self).__init__(*args, **kwargs)

    def update(self, out):
        """Update this node to a new path.

        Args:
            out (str): path to apply
        """
        self.node['read_from_file'].setValue(False)
        super(CNukeCamAbcRef, self).update(out)
        self.node['read_from_file'].setValue(True)


class CNukeReadRef(_CNukePipeRef):
    """Pipelined nuke read node."""

    def update(self, out):
        """Update this node to a new path.

        Args:
            out (str): path to apply
        """
        try:
            _path = Seq(out).path  # In case path is Seq
        except ValueError:
            _path = Video(out).path
        self.node['file'].setValue(_path)
