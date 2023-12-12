"""Tools for managing the base class for wrapped widgets."""

import logging

from ...q_utils import SavePolicy

_LOGGER = logging.getLogger(__name__)


class CBaseWidget(object):
    """Virtual base class for wrapped widgets."""

    disable_save_settings = False
    save_policy = SavePolicy.DEFAULT

    def apply_save_policy_on_change(self, settings):
        """Apply save policy on widget value changed.

        This callback is connected to the widget changed signal so that if the
        save policy is set to save on change, the settings are saved. This is
        applied like this so that the save policy can be change dynamically -
        ie. the widget can be built and then the save policy is applied.

        Args:
            settings (CSettings): parent widget settings
        """
        if self.save_policy == SavePolicy.SAVE_ON_CHANGE:
            _LOGGER.debug('APPLY SAVE ON CHANGE %s %s', self, settings)
            settings.save_widget(self)

    def __repr__(self):
        return '<{}:{}>'.format(type(self).__name__, self.objectName())
