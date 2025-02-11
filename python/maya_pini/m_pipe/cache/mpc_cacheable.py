"""Tools for manaing the base cacheable class."""

import logging

from pini import pipe
from pini.dcc import export
from pini.utils import basic_repr

from maya_pini.utils import save_abc

_LOGGER = logging.getLogger(__name__)


class CPCacheable:
    """Base class for any cacheable object."""

    asset = None
    label = None
    path = None
    output_type = None
    output_name = None
    attrs = ()

    def build_metadata(self):
        """Obtain metadata for this cacheable.

        Returns:
            (dict): metadata
        """
        _handler = type(self).__name__.strip('_')
        _src_ref = self.path
        _data = export.build_metadata(handler=_handler, src_ref=_src_ref)

        # Legacy 18/10/24
        _data['asset'] = _src_ref
        _data['type'] = _handler

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

    def rename(self, name):
        """Rename this cacheable.

        Args:
            name (str): new name to apply
        """
        raise NotImplementedError

    def select_in_scene(self):
        """Select this reference in the current scene.

        (To be implemented in child class)
        """
        raise NotImplementedError

    def to_output(self, extn='abc'):
        """Get an output based on this camera.

        Args:
            extn (str): output extension

        Returns:
            (CPOutput): output abc
        """
        _work = pipe.cur_work()
        if not _work:
            return None
        _tmpl = _work.find_template('cache', has_key={'output_name': True})
        _abc = _work.to_output(
            _tmpl, extn=extn, output_type=self.output_type,
            output_name=self.output_name, task=_work.task)
        return _abc

    def to_geo(self):
        """Obtain list of geo for this cacheable."""
        raise NotImplementedError

    def to_icon(self):
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
        _abc = self.to_output()
        _geo = self.to_geo()
        _LOGGER.debug(' - GEO %s', _geo)
        return save_abc(
            abc=_abc, geo=_geo, mode='job_arg', uv_write=uv_write,
            world_space=world_space, format_=format_, range_=range_,
            check_geo=check_geo, step=step, renderable_only=renderable_only,
            attrs=self.attrs)

    def __lt__(self, other):
        return self.label.lower() < other.label.lower()

    def __repr__(self):
        return basic_repr(self, self.output_name, separator='|')
