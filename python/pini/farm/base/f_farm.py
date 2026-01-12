"""Tools for managing the base class for render farms."""

import logging
import pprint

from pini import pipe
from pini.utils import last, plural

_LOGGER = logging.getLogger(__name__)


class CFarm:
    """Base class for all render farms."""

    NAME = None
    ICON = None
    IS_AVAILABLE = True

    def find_jobs(self):
        """Find jobs currently on the farm.

        Returns:
            (CFarmJob): jobs
        """
        return self._read_jobs()

    def _read_jobs(self):
        """Read farm jobs.

        Returns:
            (CFarmJob): jobs
        """
        raise NotImplementedError

    def submit_job(self, job):
        """Submit a job to the farm.

        Args:
            job (CJob): job to submit
        """
        raise NotImplementedError

    def submit_jobs(self, jobs):
        """Submit jobs to the farm.

        Args:
            jobs (CJob list): jobs to submit
        """
        raise NotImplementedError

    def submit_maya_cache(
            self, cacheables, comment='', priority=50, machine_limit=0,
            save=True, checks_data=None, extn='abc', flags=None):
        """Submit maya cache job to the farm.

        Args:
            cacheables (CPCacheable list): cacheables to submit
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            save (bool): save scene on submit
            checks_data (dict): sanity check data
            extn (str): cache output format (abc/fbx)
            flags (dict): cache flags

        Returns:
            (str list): job ids
        """
        raise NotImplementedError

    def submit_maya_render(
            self, camera=None, comment='', priority=50, machine_limit=0,
            frames=None):
        """Submit maya render job to the farm.

        Args:
            camera (CCamera): render cam
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            frames (int list): frames to render
        """
        raise NotImplementedError

    def submit_maya_py(
            self, name, py, comment='', priority=50, machine_limit=0,
            error_limit=0, edit_py=False):
        """Submit mayapy job to farm.

        Args:
            name (str): job name
            py (str): python to execute
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            error_limit (int): job error limit
            edit_py (bool): edit tmp python file on submit
        """
        raise NotImplementedError

    def submit_py(
            self, name, py, comment='', priority=50, machine_limit=0,
            error_limit=0):
        """Submit python job to farm.

        Args:
            name (str): job name
            py (str): python to execute
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            error_limit (int): job error limit
        """
        raise NotImplementedError

    def update_cache(self, work, outputs, metadata):
        """Update outputs cache.

        Args:
            work (str): path to work file
            outputs (str list): outputs to register
            metadata (dict): metadata to apply to outputs
        """
        _LOGGER.info('UPDATE CACHE')
        _work = pipe.to_work(work)
        _outs = [pipe.to_output(_out) for _out in outputs]

        # Update metadata
        _LOGGER.info(" - UPDATE METADATA")
        _missing_outs = []
        for _last, _out in last(_outs):

            # Flag missing outputs (ignore missing cryptomatte)
            if not _out.exists():
                if '.Cryptomatte.' not in _out.path:
                    _missing_outs.append(_out)
                continue

            _out.set_metadata(metadata)
            if pipe.MASTER == 'shotgrid':
                from pini.pipe import shotgrid
                shotgrid.create_pub_file_from_output(
                    _out, force=True, update_cache=_last)

        # Update work outputs cache
        _LOGGER.info(" - UPDATE WORK OUTPUTS CACHE")
        _work_c = pipe.CACHE.obt(_work)
        _work_c.find_outputs(force=True)

        # Error on missing outputs
        if _missing_outs:
            _missing_s = ', '.join(_out.path for _out in _missing_outs)
            _LOGGER.error('MISSING OUTPUTS')
            pprint.pprint(_outs)
            raise RuntimeError(
                f'{len(_missing_outs)} output{plural(_missing_outs)} '
                f'missing: {_missing_s}')

        _LOGGER.info(" - UPDATE CACHE COMPLETE")
