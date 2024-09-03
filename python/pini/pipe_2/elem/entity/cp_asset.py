"""Tools for managing assets."""

# pylint: disable=too-many-instance-attributes

import logging

import lucidity

from pini import icons, dcc
from pini.utils import abs_path, assert_eq

from . import cp_ety

_LOGGER = logging.getLogger(__name__)


class CPAsset(cp_ety.CPEntity):
    """Represents an asset dir on disk.

    This is a dir containing all components of an asset, eg. model/rig etc.
    """

    profile = 'asset'
    is_asset = True
    is_shot = False

    def __init__(self, path, job=None):
        """Constructor.

        Args:
            path (str): path within the asset
            job (CPJob): override the parent job object
        """
        from pini import pipe

        _path = abs_path(path)

        # Set job
        if job:
            self.job = job
        else:
            _job = pipe.CPJob(_path)
            self.job = pipe.JOBS_ROOT.obt_job(_job.name)
            assert_eq(self.job, _job)
            assert _path.startswith(_job.path)

        # Crop path to asset depth
        self.template = self.job.find_template('entity_path', profile='asset')
        self.template = self.template.apply_data(job_path=self.job.path)
        _LOGGER.debug(' - TEMPLATE %s', self.template)
        _test_path = self.template.pattern.format(
            asset='NULL', asset_type='NULL')
        _depth = _test_path.count('/')
        _LOGGER.debug(' - TEST PATH %s depth=%d', _test_path, _depth)
        _LOGGER.debug(' - ABS PATH %s', _path)
        _path = '/'.join(_path.split('/')[:_depth+1])
        _LOGGER.debug(' - CROPPED PATH %s', _path)

        # Parse template to retrieve asset data
        try:
            self.data = self.template.parse(_path)
        except lucidity.ParseError:
            raise ValueError('lucidity rejected path '+_path)
        self.asset = self.data['asset']
        self.name = self.asset
        self.asset_type = self.data.get('asset_type')
        self.type_ = self.asset_type
        self.entity_type = self.asset_type

        self.label = '{}/{}.{}'.format(
            self.job.name, self.asset_type, self.name)

        super().__init__(_path)

    @property
    def _settings_parent(self):
        """Obtain settings parent object (job).

        Returns:
            (CPSettingsLevel): settings parent
        """
        return self.job

    def create(self, force=False, parent=None, shotgrid_=True):
        """Create this asset.

        Args:
            force (bool): create asset without warning dialogs
            parent (QDialog): parent for confirmation dialogs
            shotgrid_ (bool): register in shotgrid (if available)
        """
        from pini import qt

        _LOGGER.debug('CREATE ASSET %s', self)

        # Create asset type
        if self.asset_type not in self.job.find_asset_types():
            self.job.create_asset_type(
                self.asset_type, force=force, parent=parent)
        _LOGGER.debug(' - ASSET TYPE EXISTS %s', self.asset_type)

        # Confirm
        if not force and not self.exists():
            qt.ok_cancel(
                'Create new asset {} in {}?\n\n{}'.format(
                    self.name, self.job.name, self.path),
                icon=icons.find('Plus'), title='Create Asset',
                parent=parent)

        self.mkdir()

        super().create(
            force=True, parent=parent, shotgrid_=shotgrid_)


def cur_asset(catch=True):
    """Get the current asset (if any).

    Args:
        catch (bool): return None if no current asset

    Returns:
        (CPAsset): current asset
    """
    try:
        return CPAsset(dcc.cur_file())
    except ValueError:
        if catch:
            return None
        raise ValueError('No current asset')
