"""Tools for managing caching of pipelined references (eg. rigs, models)."""

import logging

from maya import cmds

from pini import pipe
from maya_pini.utils import to_namespace

from . import mpc_cacheable

_LOGGER = logging.getLogger(__name__)


class CPCacheableRef(mpc_cacheable.CPCacheable):
    """A reference that can be cached (eg. rig/model publish)."""

    def __init__(self, ref, extn='abc'):
        """Constructor.

        Args:
            ref (CReference): reference node
            extn (str): cache output extension
        """
        _src_ref = pipe.CPOutputFile(ref.path)
        if not _src_ref:
            raise ValueError(_src_ref)
        if _src_ref.type_ != 'publish':
            raise ValueError(_src_ref)
        self.ref = ref
        if not self.to_geo():
            raise ValueError('No export geo')
        _output_name = ref.namespace.split(':')[-1]

        if _output_name != ref.namespace:
            _label = f'{_output_name} ({to_namespace(ref.namespace)})'
        else:
            _label = _output_name

        super().__init__(
            node=self.ref, src_ref=_src_ref, extn=extn, top_node=ref.top_node,
            output_name=_output_name, label=_label, ref=ref)

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

    def to_geo(self, extn='abc'):  # pylint: disable=unused-argument
        """Get list of geo to cache from this reference.

        Args:
            extn (str): output extension

        Returns:
            (str list): geo nodes
        """
        if extn == 'abc':
            _cache_set = self.ref.to_node('cache_SET', fmt='str')
            if not cmds.objExists(_cache_set):
                return []
            return cmds.sets(_cache_set, query=True)
        if extn == 'fbx':
            return self.node.top_node
        raise NotImplementedError

    def _to_icon(self):
        """Get this cacheable's icon.

        Returns:
            (str): path to icon
        """
        from pini.tools import helper
        return helper.output_to_icon(self.src_ref)
