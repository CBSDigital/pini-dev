"""Tools for managing cacheable work dir objects in a sg-based pipeline."""

import logging

from . import ccp_work_dir_base

_LOGGER = logging.getLogger(__name__)


class CCPWorkDirSG(ccp_work_dir_base.CCPWorkDirBase):
    """Represents a cacheable work dir in a sg-based pipeline."""

    def _read_outputs(self, class_=None):
        """Read outputs from shotgrid.

        Args:
            class_ (class): provided for symmetry

        Returns:
            (CPOutput list):
        """
        return [_out for _out in self.entity.find_outputs()
                if _out.work_dir == self]
