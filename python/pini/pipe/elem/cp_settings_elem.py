"""Tools for managing the basic settings level object.

This is a base class which allow shared functionality to be applied to
job/sequence/shot object.
"""

import logging
import os

from pini.utils import (
    cache_on_obj, Dir, single, File, cache_result, merge_dicts, find_callback)

_LOGGER = logging.getLogger(__name__)
_DEFAULT_SETTINGS = {
    'col': None,
    'fps': None,
    'icon': None,
    'apply_ocio': False,
    'maya': {
        'pub_refs_mode': 'Import'},
    'res': None,
    'sanity_check': {
        'ExampleCheck': {
            'enabled': True}},
    'shotgrid': {
        'disable': False,
        'only_3d': False},
}


@cache_result
def _obt_default_settings(force=False):
    """Obtain default settings.

    If $PINI_PIPE_DEFAULT_SETTINGS is set, then this file is read as
    yaml and used to update the default settings.

    Args:
        force (bool): force reread from disk

    Returns:
        (dict): default settings
    """
    _settings = {}
    _settings.update(_DEFAULT_SETTINGS)

    # Add $PINI_PIPE_DEFAULT_SETTINGS yml
    _file = os.environ.get('PINI_PIPE_DEFAULT_SETTINGS')
    if _file:
        _file = File(_file)
        _LOGGER.debug(
            'READING $PINI_DEFAULT_PIPE_SETTINGS %s', _file.path)
        assert _file.extn == 'yml'
        _def_data = _file.read_yml(catch=True) or {}
        _settings = merge_dicts(_settings, _def_data)

    return _settings


class CPSettingsLevel(Dir):
    """Base class for any directory which can store settings."""

    _settings_parent = None

    @property
    def settings_file(self):
        """Obtain settings file for this job.

        Returns:
            (File): setting file
        """
        return self.to_file('.pini/settings.yml')

    @property
    def settings(self):
        """Obtain settings at this level.

        Settings are inherited from the settings parent and then
        updated with any settings applied at this level.

        Returns:
            (dict): settings
        """
        _LOGGER.debug('READ SETTINGS %s', self)

        _settings = {}

        # Add parent settings
        _parent_settings = None
        if self._settings_parent:
            _parent_settings = self._settings_parent.settings
        else:
            _parent_settings = _obt_default_settings()
        for _key in ('icon', ):  # Some keys don't pass down
            _parent_settings[_key] = None
        _settings = merge_dicts(_settings, _parent_settings)
        _LOGGER.debug(' - ADDED PARENT %s', _parent_settings)

        # Add settings from this level
        _this_settings = self._read_this_settings()
        _settings = merge_dicts(_settings, _this_settings)
        _LOGGER.debug(' - ADDED THIS %s', _settings)

        return _settings

    def del_setting(self, key):
        """Remove the given setting at this level.

        Args:
            key (str): name of setting to remove
        """
        _LOGGER.debug('DEL SETTING %s %s', key, self)

        # Update dict
        _this = self.settings_file.read_yml(catch=True) or {}
        if key not in _this:
            return
        del _this[key]

        self._update_settings(_this)

    def flush_settings_bkps(self, force=False):
        """Delete all settings backup files.

        Args:
            force (bool): delete files without confirmation
        """
        if not force:
            raise NotImplementedError
        _bkps = self.to_subdir('.pini/.bkp').find(
            depth=1, type_='f', extn='yml', head='settings_', class_=True,
            catch_missing=True)
        for _bkp in _bkps:
            _bkp.delete(force=True)

    @cache_on_obj
    def _read_this_settings(self, force=False):
        """Read settings at this level.

        NOTE: these are cached on first read.

        Args:
            force (bool): reread from disk

        Returns:
            (dict): setting at this level
        """
        _settings = self.settings_file.read_yml(catch=True) or {}
        _callback = find_callback('ReadSettings')
        if _callback:
            _cb_settings = _callback(self)
            if _cb_settings:
                _settings = merge_dicts(_settings, _cb_settings)
        return _settings

    def set_setting(self, **kwargs):
        """Set the value of the given setting at this level.

        Args:
            key (str): name of setting to apply
            val (str): value to apply
        """
        assert len(kwargs) == 1
        _key, _val = single(list(kwargs.items()))
        assert isinstance(_key, str)

        # Update dict
        _this = self.settings_file.read_yml(catch=True) or {}
        if (
                isinstance(_val, dict) and
                _key in _this and
                isinstance(_this[_key], dict)):
            _this[_key] = merge_dicts(_this[_key], _val)
        else:
            _this[_key] = _val

        self._update_settings(_this)

    def _update_settings(self, this):
        """Apply a settings update.

        The both the memory cache and the disk yaml file are updated.

        Args:
            this (dict): settings to save at this level
        """
        _LOGGER.debug('UPDATE SETTINGS %s', self)
        _LOGGER.debug(' - THIS %s', this)

        self.settings_file.write_yml(this, force=True)

        _bkp = self.settings_file.to_bkp()
        self.settings_file.copy_to(_bkp, force=True)

        self._read_this_settings(force=True)
