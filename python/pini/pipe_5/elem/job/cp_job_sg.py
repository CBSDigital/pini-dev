"""Tools for managing jobs in a sg-based pipeline."""

import logging
import os

from pini.utils import passes_filter

from . import cp_job_base

_LOGGER = logging.getLogger(__name__)


class CPJobSG(cp_job_base.CPJobBase):
    """Represents a job in a sg-based pipeline."""

    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        from ... import shotgrid
        return shotgrid.SGC.find_job(self).prefix

    def find_assets(self, asset_type=None, filter_=None):
        """Find assets in this job.

        Args:
            asset_type (str): filter by type
            filter_ (str): apply path filter

        Returns:
            (CPAsset list): matching assets
        """
        _LOGGER.debug('FIND ASSETS')

        _assets = []
        for _asset in self._read_assets():
            if asset_type and _asset.type_ != asset_type:
                continue
            if filter_ and not passes_filter(_asset.path, filter_):
                continue
            _assets.append(_asset)

        _LOGGER.debug(' - FOUND %d ASSETS', len(_assets))

        return _assets

    def _read_all_asset_types(self):
        """Read all available asset types.

        Returns:
            (str list): asset type names
        """
        _assets = self._read_assets()
        return sorted({_asset.asset_type for _asset in _assets})

    def _read_assets(self, class_=None):
        """Read assets from shotgrid.

        Args:
            class_ (class): override asset class

        Returns:
            (CPAsset list): assets
        """
        from pini import pipe
        from pini.pipe import shotgrid

        _sg_assets = shotgrid.SGC.find_assets(job=self)
        _class = class_ or pipe.CPAsset
        _assets = [_class(_sg_asset.path, job=self) for _sg_asset in _sg_assets]

        return _assets

    def _read_type_asset_paths(self, asset_type):
        """Read asset paths in the given asset type dir.

        Args:
            asset_type (str): asset type (eg. char)

        Returns:
            (str list): asset type paths
        """
        return [
            _asset for _asset in self._read_assets()
            if _asset.asset_type == asset_type]

    def _find_sequence_paths(self):
        """Find paths to all sequences.

        Returns:
            (str list): sequence path
        """
        from pini import pipe
        _paths = sorted({
            pipe.CPSequence(_shot, job=self)
            for _shot in self.read_shots()})
        _LOGGER.debug(' - SEQ PATHS %s', _paths)
        return _paths

    def read_shots(self, class_=None):
        """Read shots from shotgrid.

        Args:
            class_ (class): override shot class

        Returns:
            (CPShot list): shots
        """
        from pini import pipe
        from pini.pipe import shotgrid
        _LOGGER.debug('READ SHOTS SG')
        _class = class_ or pipe.CPShot
        _has_3d = True if self.settings['shotgrid']['only_3d'] else None
        _whitelist = os.environ.get('PINI_PIPE_SHOTS_WHITELIST', '').split(',')
        _sg_shots = shotgrid.SGC.find_shots(
            job=self, has_3d=_has_3d, whitelist=_whitelist)
        _sg_shots = [
            _sg_shot for _sg_shot in _sg_shots
            if _sg_shot.status not in ('omt', )]
        _shots = [_class(_sg_shot.path, job=self) for _sg_shot in _sg_shots]
        _LOGGER.debug(' - MAPPED %d SHOTS', len(_shots))
        assert len(_sg_shots) == len(_shots)
        return _shots
