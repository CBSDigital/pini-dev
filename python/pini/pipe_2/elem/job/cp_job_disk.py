"""Tools for managing jobs in a disk-based pipeline."""

# pylint: disable=abstract-method

import logging
import time

import six

from pini.utils import EMPTY

from . import cp_job_base

_LOGGER = logging.getLogger(__name__)


class CPJobDisk(cp_job_base.CPJobBase):
    """Represents a job in a disk-based pipeline."""

    def find_assets(self, asset_type=None, filter_=None):
        """Find assets in this job.

        Args:
            asset_type (str): filter by type
            filter_ (str): apply path filter

        Returns:
            (CPAsset list): matching assets
        """
        _LOGGER.debug('FIND ASSETS')

        _types = [asset_type] if asset_type else self.find_asset_types()
        _LOGGER.debug(' - TYPES %s', _types)

        _assets = []
        for _type in _types:
            _assets += self.read_type_assets(asset_type=_type)

        return _assets

    def _read_all_asset_types(self):
        """Read all available asset types.

        Returns:
            (str list): asset type names
        """
        _tmpl = self.find_template(
            'entity_path', profile='asset', catch=True)
        _LOGGER.debug(' - TMPL (A) %s', _tmpl)
        if not _tmpl:
            return []
        _tmpl = _tmpl.apply_data(job_path=self.path)
        return _tmpl.glob_token('asset_type')

    def _read_type_asset_paths(self, asset_type):
        """Read asset paths in the given asset type dir.

        Args:
            asset_type (str): asset type (eg. char)

        Returns:
            (str list): asset type paths
        """
        from pini import pipe
        _tmpl = self.find_template('entity_path', profile='asset')
        _tmpl = _tmpl.apply_data(job_path=self.path, asset_type=asset_type)
        return pipe.glob_template(template=_tmpl, job=self)

    def _find_sequence_paths(self):
        """Find paths to all sequences.

        Returns:
            (str list): sequence path
        """
        _tmpl = self.find_template('sequence_path')
        _tmpl = _tmpl.apply_data(job_path=self.path)
        _LOGGER.debug(' - TMPL %s', _tmpl)
        _paths = _tmpl.glob_paths(job=self)
        return _paths

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

        assert asset is None or isinstance(asset, six.string_types)
        assert entity is None or isinstance(entity.CPEntity)

        _start = time.time()
        _pubs = []
        for _asset in self.find_assets(asset_type=asset_type):
            if asset and _asset.name != asset:
                continue
            if entity and _asset != entity:
                continue
            _pubs += _asset.find_publishes(
                ver_n=ver_n, task=task, output_name=output_name, extn=extn,
                extns=extns, tag=tag, versionless=versionless)
        _LOGGER.debug('FOUND %s %d PUBLISHES IN %.01fs', self, len(_pubs),
                      time.time() - _start)

        return _pubs
