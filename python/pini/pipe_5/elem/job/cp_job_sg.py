"""Tools for managing jobs in a sg-based pipeline."""

import logging

from . import cp_job_base

_LOGGER = logging.getLogger(__name__)


class CPJobSG(cp_job_base.CPJobBase):
    """Represents a job in a sg-based pipeline."""

    _sg_proj = None

    @property
    def id_(self):
        """Obtain shotgrid project id.

        Returns:
            (int): project id
        """
        return self.sg_proj.id_

    @property
    def sg_proj(self):
        """Obtain shotgrid cache project for this job.

        Returns:
            (SGCProj): shotgrid cache project
        """
        from pini.pipe import shotgrid
        if not self._sg_proj:
            self._sg_proj = shotgrid.SGC.find_proj(self)
        return self._sg_proj

    def find_assets(self, **kwargs):
        """Find assets in this job.

        Args:
            asset_type (str): filter by type
            filter_ (str): apply path filter

        Returns:
            (CPAsset list): matching assets
        """
        from pini import pipe
        _LOGGER.debug('FIND ASSETS')
        _assets = []
        for _asset in self._read_assets():
            if not pipe.passes_filters(_asset, **kwargs):
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

        # _sg_assets = shotgrid.SGC.find_assets(job=self)
        _class = class_ or pipe.CPAsset
        _tmpl = self.find_template('entity_path', profile='asset')

        _assets = []
        for _sg_asset in self.sg_proj.assets:
            if not (_sg_asset.asset_type and _sg_asset.asset):
                continue
            _path = _tmpl.format(
                job_path=self.path, asset=_sg_asset.asset,
                asset_type=_sg_asset.asset_type)
            _asset = _class(_path, job=self)
            if not _asset.sg_entity:
                _LOGGER.warning(
                    ' - FAILED TO FIND SG ENTITY %s (%s)', _asset.path,
                    _sg_asset.to_url())
                continue
            _assets.append(_asset)

        return _assets

    def _read_type_asset_paths(self, asset_type):
        """Read asset paths in the given asset type dir.

        Args:
            asset_type (str): asset type (eg. char)

        Returns:
            (str list): asset type paths
        """
        _tmpl = self.find_template('entity_path', profile='asset')
        _tmpl = _tmpl.crop_to_token('asset_type', name='asset_type')
        _names = sorted({_asset.asset_type for _asset in self.sg_proj.assets})
        return [
            _tmpl.format(job_path=self.path, asset_type=_name)
            for _name in _names]

    def _find_sequence_paths(self):
        """Find paths to all sequences.

        Returns:
            (str list): sequence path
        """
        _tmpl = self.find_template('entity_path', profile='shot')
        _tmpl = _tmpl.crop_to_token('sequence', name='sequence')
        _LOGGER.debug(' - TMPL %s', _tmpl)

        _names = sorted({_shot.sequence for _shot in self.sg_proj.shots})
        _LOGGER.debug(' - SEQS %s', _names)
        return [
            _tmpl.format(job_path=self.path, sequence=_name)
            for _name in _names]

    def find_shot(self, match, sequence=None, catch=False):
        """Find shot within this job.

        Args:
            match (str): match by shot name
            sequence (str): filter by sequence
            catch (bool): no error if shot not found

        Returns:
            (CPShot): matching shot
        """
        _LOGGER.debug('FIND SHOT %s', match)
        _match = match
        _seq = sequence
        if not _seq:
            _sg_shot = self.sg_proj.find_shot(match, catch=catch)
            if not _sg_shot:
                return None
            _LOGGER.debug(' - SG SHOT %s', _sg_shot)
            _seq = _sg_shot.sequence
            _match = _sg_shot.name
        return super().find_shot(match=_match, sequence=_seq, catch=catch)

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
        _tmpl = self.find_template('entity_path', profile='shot')
        _shots = []
        for _sg_shot in shotgrid.SGC.find_shots(job=self):
            _path = _tmpl.format(
                job_path=self.path, sequence=_sg_shot.sequence,
                shot=_sg_shot.shot)
            try:
                _shot = _class(_path, job=self)
            except ValueError:
                continue
            _shots.append(_shot)

        _LOGGER.debug(' - MAPPED %d SHOTS', len(_shots))

        return _shots

    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        return self.sg_proj.prefix
