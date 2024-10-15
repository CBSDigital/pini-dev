"""Tools for managing cacheable entities on a sg-based pipeline."""

import logging

from pini.utils import nice_id

from ..ccp_utils import pipe_cache_on_obj, pipe_cache_to_file
from . import ccp_ety_base

_LOGGER = logging.getLogger(__name__)


class CCPEntitySG(ccp_ety_base.CCPEntityBase):
    """Represents a cacheable entity on a sg-based pipeline."""

    def _update_outputs_cache(self, force=True):
        """Rebuild outputs cache on this entity.

        Args:
            force (bool): provided for symmetry
        """
        asdasd
        self.job.find_outputs(force=True)

    def _update_publishes_cache(self):
        """Rebuild published file cache."""
        asdasdasd
        self.job.find_publishes(force=True)

    def obt_work_dir(self, match, catch=False):
        """Find a work dir object within this entity.

        Args:
            match (CPWorkDir): work dir to find
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): matching work dir
        """
        from pini import pipe
        if isinstance(match, pipe.CPWorkDir):
            return self.job.obt_work_dir(match)
        raise NotImplementedError

    # def _read_work_dirs(self, class_=None, force=False):
    #     """Read all work dirs for this entity.

    #     Args:
    #         class_ (class): override work dir class
    #         force (bool): rebuild cache

    #     Returns:
    #         (CCPWorkDir): work dirs
    #     """
    #     if class_:
    #         raise NotImplementedError(class_=
    #     return super()._read_publishes(class
    #     _LOGGER.debug('READ WORK DIRS %s %s', nice_id(self), self)
    #     _work_dirs = sorted(
    #         self.job.find_work_dirs(entity=self, force=force))
    #     _LOGGER.debug(' - FOUND %d WORK DIRS %s', len(_work_dirs), _work_dirs)
    #     return _work_dirs

    @pipe_cache_on_obj
    def _read_outputs(self, force=False):
        _outs = []
        for _out in super()._read_outputs():
            _LOGGER.info(' - OUT %s', _out)
            
        asdasd

    def _read_publishes(self, force=False):
        """Read all publishes in this entity.

        Args:
            force (bool): rebuild disk cache

        Returns:
            (CPOutput list): all publishes
        """
        asdasdasd
        _pubs = self.job.find_publishes(force=force, entity=self)
        _LOGGER.debug('READ PUBLISHES %s n_pubs=%d', self.name, len(_pubs))
        return _pubs
