"""Tools for managing cacheable work dir objects in a disk-based pipeline."""

import logging

from ..ccp_utils import pipe_cache_on_obj
from . import ccp_work_dir_base

_LOGGER = logging.getLogger(__name__)


class CCPWorkDirDisk(ccp_work_dir_base.CCPWorkDirBase):
    """Represents a cacheable work dir in a disk-based pipeline."""

    def find_outputs(self, force=False, **kwargs):
        """Find outputs within this work dir.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)

        # Apply force
        if force and pipe.MASTER == 'disk':
            self._read_outputs(force=True)
            _LOGGER.debug(' - UPDATED CACHE %s', self)

        return super().find_outputs(**kwargs)

    @pipe_cache_on_obj
    def _read_outputs(self, class_=None, force=False):
        """Read outputs within this work dir from disk.

        Args:
            class_ (class): override work dir class
            force (bool): force reread from disk

        Returns:
            (CPOutput list): outputs
        """
        from pini.pipe import cache
        assert not class_
        _LOGGER.debug('READ OUTPUTS force=%d class=%s %s', force, class_, self)
        return super()._read_outputs(
            class_=class_ or cache.CCPOutput)
