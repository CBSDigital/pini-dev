"""Tools for managing jobs in a sg-based pipeline."""

import copy
import logging
import os

import six

from pini.utils import EMPTY, passes_filter

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

    def find_outputs(
            self, type_=None, filter_=None, profile=None, entity=None,
            step=None, task=None, tag=EMPTY, ver_n=None, extns=None,
            progress=False):
        """Find outputs in this job.

        (Only applicable to shotgrid jobs)

        Args:
            type_ (str): filter by output type
            filter_ (str): apply path filter
            profile (str): filter by entity profile (asset/shot)
            entity (CPEntity): filter by entity
            step (str): apply step filter
            task (str): filter by task
            tag (str): filter by tag
            ver_n (int): filter by version number
            extns (str list): filter by output extensions
            progress (bool): show progress

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('FIND OUTPUTS %s', self)

        if not (entity is None or isinstance(entity, pipe.ENTITY_TYPES)):
            raise TypeError(entity)

        _all_outs = self._read_outputs(progress=progress)
        _all_outs, _ver_n = self._apply_latest_output_version_filter(
            ver_n=ver_n, outputs=_all_outs)

        _outs = []
        for _out in _all_outs:
            _LOGGER.debug(' - TESTING %s', _out)
            if filter_ and not passes_filter(_out.path, filter_):
                continue
            if type_ and _out.type_ != type_:
                continue
            if step and _out.step != step:
                continue
            if task and task not in (_out.task, _out.pini_task):
                continue
            if tag is not EMPTY and _out.tag != tag:
                continue
            if _ver_n and _out.ver_n != _ver_n:
                continue
            if profile and _out.entity.profile != profile:
                continue
            if entity and _out.entity != entity:
                _LOGGER.debug('   - REJECT ENTITY %s %s', _out.entity, entity)
                continue
            if extns and _out.extn not in extns:
                continue
            _outs.append(_out)

        _LOGGER.debug(' - FOUND %d OUTPUTS', len(_outs))
        return sorted(_outs)

    def _apply_latest_output_version_filter(self, outputs, ver_n):
        """Apply "latest" version filter.

        If the ver_n filter is "latest" then remove all non-latest
        versions from the list.

        Args:
            outputs (CPOutput list): outputs
            ver_n (int|str|None): version filter

        Returns:
            (tuple): outputs list, updated version filter
        """
        _outs = outputs
        _ver_n = ver_n
        if _ver_n == 'latest':
            _ver_n = None
            _n_outs = len(_outs)
            _outs = sorted({
                _to_out_stream_uid(_out): _out
                for _out in _outs}.values())
            _LOGGER.debug(
                ' - APPLY LATEST %d -> %d OUTS', _n_outs, len(_outs))
        else:
            assert _ver_n in (None, EMPTY) or isinstance(_ver_n, int)

        return _outs, _ver_n

    def _read_outputs(self, progress=False):
        """Read outputs in this job from shotgrid.

        Args:
            progress (bool): show progress

        Returns:
            (CPOutput list): outputs
        """
        raise NotImplementedError("Use cache")

    def find_publishes(
            self, task=None, entity=None, asset=None, asset_type=None,
            output_name=None, tag=EMPTY, ver_n=EMPTY, versionless=None,
            extn=EMPTY, extns=None):
        """Find asset publishes within this job.

        Args:
            task (str): filter by task
            entity (CPEntity): filter by entity
            asset (str): filter by asset name (eg. deadHorse)
            asset_type (str): filter by asset type name (eg. char)
            output_name (str): filter by output name
            tag (str): filter by tag
            ver_n (int): filter by version number
            versionless (bool): filter by versionless status
            extn (str): filter by publish extension
            extns (str list): filter by publish extensions

        Returns:
            (CPOutput list): publishes
        """
        _LOGGER.debug('FIND PUBLISHES')

        from pini import pipe

        assert asset is None or isinstance(asset, six.string_types)
        assert entity is None or isinstance(entity, pipe.CPEntity)

        assert not asset
        assert not asset_type
        assert not output_name
        assert not versionless
        assert extn is EMPTY
        _pubs = []
        for _type in ['publish', 'publish_seq']:
            _pubs += self.find_outputs(
                type_=_type, entity=entity, task=task, tag=tag, ver_n=ver_n,
                extns=extns, profile='asset')
        _pubs.sort()

        return _pubs


def _to_out_stream_uid(output):
    """Build a hashable uid for the given output's version stream.

    ie. build an uid that identifies all versions of an output stream.

    This could be achieved by using CPOutputFile.to_work(ver_n=0) but that is
    slow. Instead, the data dict with the version key removed is converted
    to a tuple.

    Args:
        output (CPOutput): output to read

    Returns:
        (tuple): uid
    """
    _data = copy.copy(output.data)
    _data.pop('ver')
    return tuple(_data.items())
