"""Tools for managing cacheable job roots in a disk-based pipeline."""

import logging

from pini.utils import single

from . import ccp_root_base

_LOGGER = logging.getLogger(__name__)


class CCPRootDisk(ccp_root_base.CCPRootBase):
    """Represents a cacheable jobs root in a disk-based pipeline."""

    def _obt_work_dir_cacheable(self, work_dir, catch=False):
        """Obtain cacheable work dir from work dir object.

        Args:
            work_dir (CPWorkDir): work dir to read
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): cacheable work dir
        """
        from ... import cache
        _ety = self.obt_entity(work_dir.entity)
        assert isinstance(_ety, cache.CCPEntity)
        return single([
            _work_dir for _work_dir in _ety.work_dirs
            if _work_dir == work_dir], catch=catch)
