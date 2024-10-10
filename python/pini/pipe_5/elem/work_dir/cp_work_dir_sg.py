"""Tools for managing work directory objects in a shotgrid-based pipeline."""

import logging

from . import cp_work_dir_base

_LOGGER = logging.getLogger(__name__)


class CPWorkDirSG(cp_work_dir_base.CPWorkDir):
    """Represents a work directory in a shotgrid-based pipeline."""

    def _read_outputs(self, class_=None):
        """Read outputs from shotgrid.

        Args:
            class_ (class): provided for symmetry

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        from pini.pipe import shotgrid
        _outs = []
        for _sg_pub in shotgrid.SGC.find_pub_files(work_dir=self):
            _out = pipe.to_output(_sg_pub.path, work_dir=self)
            _outs.append(_out)
        return _outs
