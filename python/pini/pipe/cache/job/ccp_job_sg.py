"""Tools for managing cacheable jobs on a sg-based pipeline."""

# pylint: disable=no-member

import logging

from pini import qt
from pini.utils import single, check_heart

from ..ccp_utils import pipe_cache_result, pipe_cache_to_file
from . import ccp_job_base

_LOGGER = logging.getLogger(__name__)


class CCPJobSG(ccp_job_base.CCPJobBase):
    """Represents a cacheable job on a sg-based pipeline."""

    @pipe_cache_result
    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        return super().to_prefix()

    def find_assets(self, force=False, **kwargs):
        """Find assets in this job.

        Args:
            force (bool): force reread assets list from disk

        Returns:
            (CCPAsset list): matching assets
        """
        _LOGGER.log(9, 'FIND ASSETS force=%d', force)
        if force:
            self._read_assets(force=True)
        _assets = super().find_assets(**kwargs)
        return _assets

    @pipe_cache_result
    def _read_assets(self, class_=None, force=False):
        """Read assets from shotgrid.

        Args:
            class_ (class): override asset class
            force (bool): force reread from disk
        """
        from ... import cache
        _LOGGER.debug('READ ASSETS')
        return super()._read_assets(class_=class_ or cache.CCPAsset)

    @pipe_cache_result
    def read_shots(self, class_=None, filter_=None, force=False):
        """Read shots from shotgrid.

        Args:
            class_ (class): override shot class
            filter_ (str): apply name filter
            force (bool): force reread shots from disk

        Returns:
            (CCPShot list): shots
        """
        from ... import cache
        if filter_:
            raise RuntimeError('Filter not allowed to maintain cache integrity')
        _LOGGER.debug('READ SHOTS force=%d', force)
        return super().read_shots(class_=class_ or cache.CCPShot)

    @pipe_cache_to_file
    def _read_publishes(self, force=False):
        """Read publishes in this job.

        Args:
            force (bool): force rebuild disk cache

        Returns:
            (CPOutputGhost list): publishes
        """
        _LOGGER.info('READ PUBLISHES %s', self)
        _LOGGER.info(' - CACHE FMT %s', self.cache_fmt)
        _pubs = []
        for _asset in qt.progress_bar(
                self.assets,
                f'Reading {{:d}} {self.name} asset{{}}',
                show_delay=1, stack_key='ReadJobPublishes',
                col='SpringGreen'):
            check_heart()
            _pubs += _asset.find_publishes(force=force > 1)
        _c_types = sorted({_pub.content_type for _pub in _pubs})
        _LOGGER.info(' - FOUND %d CONTENT TYPES %s', len(_c_types), _c_types)
        _LOGGER.info(' - FOUND %d PUBS', len(_pubs))
        return _pubs

    def obt_work_dir(self, match, catch=False):
        """Obtain a work dir object within this job.

        Args:
            match (CPWorkDir): work dir to match
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): cached work dir
        """
        from pini import pipe
        if isinstance(match, pipe.CPWorkDir):
            _work_dirs = self._read_work_dirs()
            _matches = [
                _work_dir for _work_dir in _work_dirs
                if _work_dir == match]
            _result = single(
                _matches, error=f'Failed to match {match}',
                catch=catch)
            return _result
        raise NotImplementedError(match)
