"""Tools for managing flame/pini interface."""

# pylint: disable=abstract-method,import-error

import logging

import flame

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class FlameDCC(BaseDCC):
    """Manages interactions with flame."""

    NAME = 'flame'

    def cur_file(self):
        """Obtain path to current scene.

        As flame doesn't seem to have this concept, the path to currently
        selected project's job is used.

        Returns:
            (str): current job path
        """
        from pini import pipe
        _job_name = flame.project.current_project.project_name
        return pipe.to_job(_job_name).path
