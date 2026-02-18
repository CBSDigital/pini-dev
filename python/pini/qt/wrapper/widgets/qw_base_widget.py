"""Tools for managing the base class for wrapped widgets."""

import logging

from pini import dcc
from pini.utils import basic_repr

from ... import q_utils

_LOGGER = logging.getLogger(__name__)


class CBaseWidget:
    """Virtual base class for wrapped widgets."""

    save_policy = q_utils.SavePolicy.DEFAULT

    _settings_key = None
    _data = None

    @property
    def settings_key(self):
        """Obtain scene settings key for this widget.

        This is the name by which this widget's setting can be stored in
        the current dcc scene if the save policy is set to SAVE_IN_SCENE.

        Returns:
            (str): settings key
        """
        _parent = self.parent().objectName()
        _widget = self.objectName()
        return self._settings_key or f'PiniQt.{_parent}.{_widget}'

    def apply_save_policy_on_change(self, settings):
        """Apply save policy on widget value changed.

        This callback is connected to the widget changed signal so that if the
        save policy is set to save on change, the settings are saved. This is
        applied like this so that the save policy can be change dynamically -
        ie. the widget can be built and then the save policy is applied.

        Args:
            settings (CSettings): parent widget settings
        """
        if self.save_policy == q_utils.SavePolicy.SAVE_ON_CHANGE:
            _LOGGER.debug('APPLY SAVE ON CHANGE %s %s', self, settings)
            settings.save_widget(self)
        elif self.save_policy == q_utils.SavePolicy.SAVE_IN_SCENE:
            _LOGGER.debug('APPLY SAVE IN SCENE %s', self)
            _val = self.get_val()
            _LOGGER.debug(' - SET SCENE DATA %s %s', self.settings_key, _val)
            dcc.set_scene_data(self.settings_key, _val)

    def get_scene_setting(self):
        """Read current setting (if any) for this widget from the current scene.

        Returns:
            (any): widget setting
        """
        return dcc.get_scene_data(self.settings_key)

    def get_val(self):
        """Read value of this widget."""
        raise NotImplementedError(self)

    def get_data(self):
        """Obtain data embedded in this widget.

        Returns:
            (any): embedded data
        """
        return self._data

    def has_scene_setting(self):
        """Test whether this widget has a scene setting currently applied.

        Returns:
            (bool): whether scene setting exists
        """
        return dcc.get_scene_data(self.settings_key) is not None

    def load_setting(self):
        """Apply value from settings."""
        _LOGGER.debug('LOAD SETTING %s', self)
        _val = self.read_setting()
        _LOGGER.debug(' - VAL %s', _val)
        if _val is not None:
            self.set_val(_val)

    def read_setting(self):
        """Read current setting for this widget.

        Returns:
            (any): widget setting
        """
        _LOGGER.debug('READ SETTING %s', self)
        _LOGGER.debug(' - SAVE POLICY %s', self.save_policy)
        _val = None
        if self.save_policy == q_utils.SavePolicy.SAVE_IN_SCENE:
            _val = dcc.get_scene_data(self.settings_key)
            _LOGGER.debug(' - READ SCENE DATA %s', _val)
        elif self.save_policy == q_utils.SavePolicy.NO_SAVE:
            pass
        else:
            _settings = getattr(self.to_dialog(), 'settings', None)
            if _settings:
                _key = f'widgets/{self.objectName()}'
                _val = _settings.value(_key)
            _LOGGER.debug(' - READ SETTINGS %s', _val)
        return _val

    def set_col(self, col):
        """Set text colour.

        Args:
            col (str): colour to apply
        """
        _pal = self.palette()
        _pal.setColor(self.foregroundRole(), col)
        self.setPalette(_pal)

        # self.setStyleSheet(f"color : {col}")

    def set_data(self, data):
        """Embed data in this widget.

        Args:
            data (any): data to embed
        """
        self._data = data

    def set_save_policy(self, policy):
        """Apply save policy to this widget.

        Args:
            policy (SavePolicy): save policy to apply
        """
        assert isinstance(policy, q_utils.SavePolicy)
        self.save_policy = policy

    def set_settings_key(self, key):
        """Override the default scene settings key for this widget.

        Args:
            key (str): settings key name to apply
        """
        assert key.startswith('PiniQt.')
        self._settings_key = key

    def set_val(self, val):
        """Apply value to this widget.

        Args:
            val (any): value to apply
        """
        raise NotImplementedError(self)

    def to_dialog(self):
        """Obtain parent dialog for this control.

        Returns:
            (CUiBase): dialog
        """
        from pini import qt
        _parent = self.parent()
        for _idx in range(10):
            if isinstance(_parent, qt.CUiBase):
                break
            if not _parent:
                break
            _parent = _parent.parent()
        return _parent

    def __repr__(self):
        return basic_repr(self, self.objectName())
