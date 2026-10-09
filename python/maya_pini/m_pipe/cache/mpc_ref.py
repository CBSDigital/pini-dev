"""Tools for managing caching of pipelined references (eg. rigs, models)."""

import logging

from maya import cmds

from pini import pipe
from maya_pini.utils import to_namespace

from . import mpc_cacheable

_LOGGER = logging.getLogger(__name__)


class CPCacheableRef(mpc_cacheable.CPCacheable):
    """A reference that can be cached (eg. rig/model publish)."""

    def __init__(self, ref, exporter, extn='abc'):
        """Constructor.

        Args:
            ref (CReference): reference node
            exporter (CExporter): exporter running this cache operation
            extn (str): cache output extension
        """
        _src_ref = pipe.CACHE.obt_output(ref.path, catch=True)
        if not _src_ref:
            raise ValueError(_src_ref)
        if _src_ref.type_ != 'publish':
            raise ValueError(_src_ref)
        self.ref = ref
        self.extn = extn
        if not self.to_geo():
            raise ValueError('No export geo')

        super().__init__(
            node=self.ref, src_ref=_src_ref, extn=extn, top_node=ref.top_node,
            ref=ref, output_type=extn,
            exporter=exporter, content_type=f'Pipe{extn.capitalize()}')

    @property
    def label(self):
        """Obtain label for this cacheable.

        Returns:
            (str): label
        """
        if self.output_name != self.ref.namespace:
            return f'{self.output_name} ({to_namespace(self.ref.namespace)})'
        return self.output_name

    @property
    def output_name(self):
        """Obtain output name for this cacheable.

        Returns:
            (str): output name
        """
        return self.ref.namespace.split(':')[-1]

    def _set_name(self, name):
        """Rename this cacheable.

        Args:
            name (str): new name to apply
        """
        self.ref.set_namespace(name)

    def select_in_scene(self):
        """Select this reference in scene (top node)."""
        cmds.select(self.find_top_nodes())

    def to_nodes(self, mode='geo'):
        """Read nodes in the cache set.

        Args:
            mode (str): which nodes to read

        Returns:
            (CNode list): nodes
        """
        from maya_pini import m_pipe
        return m_pipe.read_cache_set(
            set_=self.ref.to_node('cache_SET'), mode=mode)

    def to_geo(self):
        """Get list of geo to cache from this reference.

        Returns:
            (str list): geo nodes
        """
        if self.extn == 'abc':
            _cache_set = self.ref.to_node('cache_SET', fmt='str')
            if not cmds.objExists(_cache_set):
                return []
            return cmds.sets(_cache_set, query=True)
        if self.extn == 'fbx':
            return self.ref.top_node
        raise NotImplementedError

    def _to_icon(self):
        """Get this cacheable's icon.

        Returns:
            (str): path to icon
        """
        from pini.tools import helper
        return helper.output_to_icon(
            self.output, allow_missing=True, entity=self.src_ref.entity,
            content_type=f'Pipe{self.extn.capitalize()}',
            src_ref=self.src_ref)
