"""Tools for managing pipelined references."""

import functools

from pini import pipe
from pini.utils import six_cmp, File, split_base_index


class CPipeRef(object):
    """Represents a pipeline output referenced into a dcc."""

    node = None

    path = None
    extn = None
    _out = None
    _out_c = None

    def __init__(self, path, namespace):
        """Constructor.

        Args:
            path (str): path to reference
            namespace (str): namespace for node
        """
        self.namespace = namespace
        self.cmp_str = to_cmp_str(self.namespace)
        self._init_path_attrs(path)

    def _init_path_attrs(self, path):
        """Initiate/update path attributes.

        Args:
            path (str): reference file path
        """
        _file = File(path)
        self.path = _file.path
        self.extn = _file.extn

        # Setup outputs (uncached/cached)
        self._out = pipe.to_output(self.path, catch=True)
        if not self._out:
            raise ValueError('Failed to map path to output '+self.path)
        self._out_c = pipe.CACHE.obt_output(self._out, catch=True)

    @property
    def asset_type(self):
        """Obtain this reference's output's asset type (eg. char/prop).

        Returns:
            (str): asset type
        """
        return self.output.asset_type

    @property
    def is_loaded(self):
        """Test whether this reference is loaded.

        Returns:
            (bool): whether loaded
        """
        return True

    @property
    def output(self):
        """Obtain this reference's output from the pipeline cache.

        A pipe ref will always have an output path which follows pipeline
        naming conventions. However, if the output isn't found in the cache
        that means that either a) the cache needs updating, or b) that the
        output being referenced doesn't exist (eg. it's been deleted or
        hasn't been generated yet).

        We don't want to automate re-reading the cache as this could be slow
        or inefficient (eg. in a nuke script with references to deleted
        renders), so outputs missing from the cache should be flagged to the
        user so that they can decide to re-cache manually.

        Returns:
            (CCPOutput): output
        """
        return self.to_output()

    @property
    def tag(self):
        """Obtain this reference's output's tag.

        Returns:
            (str): tag name
        """
        return self.output.tag if self.output else None

    @property
    def task(self):
        """Obtain this reference's output's task.

        Returns:
            (str): task name
        """
        return self.output.task if self.output else None

    def delete(self, force=False):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
        """
        raise NotImplementedError(self)

    @functools.wraps(pipe.CPOutputBase.find_rep)
    def find_rep(self, **kwargs):
        """Find an alternative representation of this reference.

        Returns:
            (CPOutput): alternative representation
        """
        return self.output.find_rep(**kwargs)

    @functools.wraps(pipe.CPOutputBase.find_reps)
    def find_reps(self, **kwargs):
        """Find alternative representations of this reference.

        Returns:
            (CPOutput list): alternative representations
        """
        return self.output.find_reps(**kwargs)

    def is_latest(self):
        """Test whether reference this is using latest version.

        Returns:
            (bool): whether using latest version
        """
        return self.output.is_latest()

    def rename(self, namespace):
        """Update this reference's namespace.

        Args:
            namespace (str): new namespace
        """
        self.node.setName(namespace)

    def rename_using_dialog(self, parent=None):
        """Rename this node using an dialog.

        Args:
            parent (QDialog): parent dialog
        """
        from pini import qt
        _ns = qt.input_dialog(
            title='Rename',
            msg='Enter new name for {}:'.format(self.namespace),
            default=self.namespace, parent=parent)
        self.rename(_ns)

    def select_in_scene(self):
        """Select this reference in the current scene."""
        from pini import dcc
        dcc.select_node(self.node)

    def swap_rep(self, output):
        """Swap this reference for a different representation.

        Args:
            output (CPOutput): representation to swap to
        """
        raise NotImplementedError

    def to_output(self, cache=True):
        """Obtain this pipe ref's output.

        Normally we want the output from the pipeline cache, but to accommodate
        for situations where a valid output is being referenced which is not
        currently in the cache, we can also request the uncached output.

        Args:
            cache (bool): disable to retrieve the uncached output

        Returns:
            (CPOutput): associated pipeline output
        """
        return self._out_c if cache else self._out

    def update(self, out):
        """Apply a new out to this reference.

        Args:
            out (str): out to apply
        """
        raise NotImplementedError

    def __cmp__(self, other):
        return six_cmp(self.cmp_str, other.cmp_str)

    def __eq__(self, other):
        return self.cmp_str == other.cmp_str

    def __hash__(self):
        return hash(self.cmp_str)

    def __lt__(self, other):
        return self.cmp_str < other.cmp_str

    def __repr__(self):
        return '<{}|{}>'.format(
            type(self).__name__.strip('_'), self.namespace)


def to_cmp_str(namespace):
    """Break a namespace into base and index and then pad the index.

    This allows for more logical sorting.

    eg. blah20 -> blah00020

    Args:
        namespace (str): namespace to parse

    Returns:
        (str): comparison string
    """
    _base, _idx = split_base_index(namespace)
    return '{}{:05d}'.format(_base, _idx)
