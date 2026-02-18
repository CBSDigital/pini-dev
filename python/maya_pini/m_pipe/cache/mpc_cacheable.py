"""Tools for manaing the base cacheable class."""

import logging

from pini.dcc import export
from pini.utils import basic_repr

from maya_pini.utils import save_abc

_LOGGER = logging.getLogger(__name__)


class CPCacheable(export.CCacheable):
    """Base class for any cacheable object."""

    attrs = ()

    def build_metadata(self):
        """Obtain metadata for this cacheable.

        Returns:
            (dict): metadata
        """
        _handler = type(self).__name__.strip('_')
        _data = export.build_metadata(
            handler=_handler,
            src_ref=self.src_ref.path if self.src_ref else None)
        return _data

    @property
    def task(self):
        """Obtain task for this cacheable (if any).

        Returns:
            (str|None): task
        """
        if not self.asset:
            return None
        return self.asset.task

    def pre_cache(self, extn='abc'):
        """Code to be executed before caching.

        Args:
            extn (str): output extension
        """

    def post_cache(self):
        """Code to be executed after caching."""

    def select_in_scene(self):
        """Select this reference in the current scene.

        (To be implemented in child class)
        """
        raise NotImplementedError

    def to_geo(self):
        """Obtain list of geo for this cacheable."""
        raise NotImplementedError

    def _to_icon(self):
        """Obtain icon for this cacheable."""
        raise NotImplementedError

    def to_job_arg(
            self, uv_write, world_space, format_, range_, check_geo=True,
            step=None, renderable_only=True):
        """Get AbcExport job arg for this cacheable.

        Args:
            uv_write (bool): apply uWrite flag
            world_space (bool): apply worldSpace flag
            format_ (str): abc format
            range_ (tuple): export range
            check_geo (bool): check geo exists on build job arg
            step (float): step size in frames
            renderable_only (bool): export only renderable (visible) geometry

        Returns:
            (str): job arg
        """
        _geo = self.to_geo()
        _LOGGER.debug(' - GEO %s', _geo)
        return save_abc(
            abc=self.output, geo=_geo, mode='job_arg', uv_write=uv_write,
            world_space=world_space, format_=format_, range_=range_,
            check_geo=check_geo, step=step, renderable_only=renderable_only,
            attrs=self.attrs)

    def __eq__(self, other):
        if isinstance(other, CPCacheable):
            return self.node == other.node
        return False

    def __lt__(self, other):
        return self.label.lower() < other.label.lower()

    def __repr__(self):
        return basic_repr(self, self.output_name, separator='|')
