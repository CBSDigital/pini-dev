"""Tools for managing basic publishes."""

# pylint: disable=abstract-method

import logging

from pini import dcc
from pini.utils import find_callback

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CBasicPublish(eh_base.CExportHandler):
    """Manages a basic publish."""

    NAME = 'Basic Publish'

    TYPE = 'Publish'
    LABEL = 'Makes a copy of this scene in the publish directory'
    ACTION = 'BasicPublish'

    def build_metadata(self, **kwargs):
        """Obtain metadata for this publish.

        Args:
            work (CPWork): override workfile to read metadata from
            run_checks (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """
        _data = super().build_metadata(**kwargs)
        _data['publish_type'] = type(self).__name__
        _frame = dcc.t_frame(int)
        _data['range'] = (_frame, _frame)
        return _data

    def _update_pipe_cache(self):
        """Update pipeline cache."""
        _LOGGER.info('UPDATE PIPE CACHE')

        # Update publish cache
        _LOGGER.info(' - UPDATING PUBLISH CACHE')
        self.work.entity.find_publishes(force=True)
        self.work.job.find_publishes(force=True)

        super()._update_pipe_cache()

    def post_export(self, **kwargs):
        """Run post export scripts.

        For publish this allows any publish callback to be installed.

        Args:
            outs (CPOutput list): outputs which were generated
        """
        _LOGGER.info('POST EXPORT %s', self)

        super().post_export(**kwargs)

        # Execute post publish callback
        _callback = find_callback('Publish')
        _LOGGER.info(' - PUBLISH CALLBACK %s', _callback)
        if _callback:
            _callback(self.outputs)
