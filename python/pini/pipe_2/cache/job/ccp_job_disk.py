"""Tools for managing cacheable jobs on a disk-based pipeline."""

import logging
import operator

from pini.utils import apply_filter

from . import ccp_job_base

_LOGGER = logging.getLogger(__name__)


class CCPJobDisk(ccp_job_base.CCPJobBase):
    """Represents a cacheable job on a disk-based pipeline."""

    def find_assets(self, asset_type=None, filter_=None, force=False):
        """Find assets in this job.

        Args:
            asset_type (str): filter by asset type
            filter_ (str): filter by path
            force (bool): force reread assets list from disk

        Returns:
            (CCPAsset list): matching assets
        """
        _LOGGER.log(9, 'FIND ASSETS force=%d', force)

        _types = [asset_type] if asset_type else self.asset_types
        _LOGGER.debug(' - TYPES %s', _types)
        _assets = []
        for _type in _types:
            _type_assets = self.read_type_assets(
                asset_type=_type, force=force)
            _LOGGER.debug(' - FOUND type=%s %s', _type, _type_assets)
            _assets += _type_assets

        if filter_:
            _assets = apply_filter(
                _assets, filter_, key=operator.attrgetter('path'))

        return _assets

    def _update_publishes_cache(self):
        """Rebuild publishes cache."""
        from pini import qt
        for _asset in qt.progress_bar(
                self.assets, 'Reading {:d} asset{}'):
            _asset.find_publishes(force=True)

    def obt_work_dir(self, match):
        """Obtain a work dir object within this job.

        Args:
            match (CPWorkDir): work dir to match

        Returns:
            (CCPWorkDir): cached work dir
        """
        raise NotImplementedError
