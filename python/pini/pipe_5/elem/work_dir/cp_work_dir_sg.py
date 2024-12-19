"""Tools for managing work directory objects in a shotgrid-based pipeline."""

import logging

from . import cp_work_dir_base

_LOGGER = logging.getLogger(__name__)


class CPWorkDirSG(cp_work_dir_base.CPWorkDir):
    """Represents a work directory in a shotgrid-based pipeline."""

    _sg_task = None

    @property
    def sg_task(self):
        """Obtain shotgrid task object for this work dir.

        Returns:
            (SGCTask): shotgrid task
        """
        if not self._sg_task:
            self._sg_task = self.entity.sg_entity.find_task(
                task=self.task, step=self.step)
        return self._sg_task

    def _read_outputs(self, class_=None):
        """Read outputs from shotgrid.

        Args:
            class_ (class): provided for symmetry

        Returns:
            (CPOutput list): outputs
        """
        return self.entity.find_outputs(task=self.task, step=self.step)
