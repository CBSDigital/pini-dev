"""Tools for managing cacheable job roots in a sg-based pipeline."""

import logging

from . import ccp_root_base

_LOGGER = logging.getLogger(__name__)


class CCPRootSG(ccp_root_base.CCPRootBase):
    """Represents a cacheable jobs root in a sg-based pipeline."""

    def _obt_work_dir_cacheable(self, work_dir, catch=False):
        """Obtain cacheable work dir from work dir object.

        Args:
            work_dir (CPWorkDir): work dir to read
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): cacheable work dir
        """
        _job = self.obt_job(work_dir.job)
        return _job.obt_work_dir(work_dir, catch=catch)
