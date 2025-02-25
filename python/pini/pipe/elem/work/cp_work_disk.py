"""Tools for managing work files in a disk-based pipeline."""

import logging
import time

from . import cp_work_base

_LOGGER = logging.getLogger(__name__)


class CPWorkDisk(cp_work_base.CPWorkBase):
    """Represent a work file on a disk-based pipeline."""

    def _read_outputs_from_pipe(self):
        """Read outputs from disk.

        Returns:
            (CPOutput list): outputs
        """
        _outs = []

        # Add entity level outputs
        _start = time.time()
        _ety_outs = self.entity.find_outputs(
            task=self.task, ver_n=self.ver_n, tag=self.tag)
        _LOGGER.debug(
            ' - FOUND %d ENTITY OUTS IN %.01fs %s', len(_ety_outs),
            time.time() - _start, self.entity)
        _outs += _ety_outs

        _outs.sort()

        return _outs
