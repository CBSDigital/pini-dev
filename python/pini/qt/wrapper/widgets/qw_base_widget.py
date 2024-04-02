"""Tools for managing the base class for wrapped widgets."""

import logging

from pini import dcc

from ... import q_utils

_LOGGER = logging.getLogger(__name__)


class CBaseWidget(object):
    """Virtual base class for wrapped widgets."""

    disable_save_settings = False
    save_policy = q_utils.SavePolicy.DEFAULT
    _settings_key = None

    @property
    def settings_key(self):
        """Obtain scene settings key for this widget.

        This is the name by which this widget's setting can be stored in
        the current dcc scene if the save policy is set to SAVE_IN_SCENE.

        Returns:
            (str): settings key
        """
        return self._settings_key or 'PiniQt.{parent}.{widget}'.format(
            parent=self.parent().objectName(), widget=self.objectName())

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
            _LOGGER.info('APPLY SAVE IN SCENE %s', self)
            _val = self.get_val()
            _LOGGER.info(' - SET SCENE DATA %s %s', self.settings_key, _val)
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

    def has_scene_setting(self):
        """Test whether this widget has a scene setting currently applied.

        Returns:
            (bool): whether scene setting exists
        """
        return dcc.get_scene_data(self.settings_key) is not None

    def load_setting(self):
        """Apply value from settings."""
        _val = self.read_setting()
        if _val is not None:
            self.set_val(_val)

    def read_setting(self):
        """Read current setting for this widget.

        Returns:
            (any): widget setting
        """
        _val = None
        if self.save_policy == q_utils.SavePolicy.SAVE_IN_SCENE:
            _val = dcc.get_scene_data(self.settings_key)
        else:
            _settings = getattr(self.parent(), 'settings', None)
            if _settings:
                _key = 'widgets/{}'.format(self.objectName())
                _val = _settings.value(_key)
        return _val

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

    def __repr__(self):
        return '<{}:{}>'.format(type(self).__name__, self.objectName())
