"""Tools for managing caching of pipelined references (eg. rigs, models)."""

import logging

from maya import cmds

from pini import pipe
from maya_pini import ref, open_maya as pom
from maya_pini.utils import to_namespace

from . import mpc_cacheable

_LOGGER = logging.getLogger(__name__)


class CPCacheableRef(ref.FileRef, mpc_cacheable.CPCacheable):
    """A reference that can be cached (eg. rig/model publish)."""

    __lt__ = mpc_cacheable.CPCacheable.__lt__

    def __init__(self, ref_node):
        """Constructor.

        Args:
            ref_node (str): reference node
        """
        super(CPCacheableRef, self).__init__(ref_node)
        self.node = pom.CReference(ref_node)

        self.asset = pipe.CPOutputFile(self.path)
        if self.asset.type_ != 'publish':
            raise ValueError
        if not self.to_geo():
            raise ValueError('No export geo')
        self.output_name = self.namespace.split(':')[-1]

        if self.output_name != self.namespace:
            self.label = '{} ({})'.format(
                self.output_name, to_namespace(self.namespace))
        else:
            self.label = self.output_name

    def rename(self, name):
        """Rename this cacheable.

        Args:
            name (str): new name to apply
        """
        raise NotImplementedError

    def select_in_scene(self):
        """Select this reference in scene (top node)."""
        cmds.select(self.find_top_nodes())

    def to_output(self, extn='abc'):
        """Get an output based on this reference.

        Args:
            extn (str): output extension

        Returns:
            (CPOutput): output abc
        """
        _LOGGER.debug('TO ABC')
        _work = pipe.cur_work()
        _pub = pipe.CPOutputFile(self.path)
        _tmpl = _work.find_template('cache', has_key={'output_name': True})
        _LOGGER.debug(' - TMPL %s', _tmpl)
        _abc = _work.to_output(
            _tmpl, extn=extn, output_type=_pub.asset_type or 'geo',
            output_name=self.output_name, task=_work.task)
        return _abc

    def to_geo(self, extn='abc'):  # pylint: disable=unused-argument
        """Get list of geo to cache from this reference.

        Args:
            extn (str): output extension

        Returns:
            (str list): geo nodes
        """
        if extn == 'abc':
            _cache_set = self.to_node('cache_SET')
            if not cmds.objExists(_cache_set):
                return []
            return cmds.sets(_cache_set, query=True)
        if extn == 'fbx':
            return self.node.top_node
        raise NotImplementedError

    def to_icon(self):
        """Get this cacheable's icon.

        Returns:
            (str): path to icon
        """
        from pini.tools import helper
        return helper.output_to_icon(self.asset)
