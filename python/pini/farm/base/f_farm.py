"""Tools for managing the base class for render farms."""


class CFarm(object):
    """Base class for all render farms."""

    NAME = None
    ICON = None
    IS_AVAILABLE = True

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
            save=True, checks_data=None, flags=None):
        """Submit maya cache job to the farm.

        Args:
            cacheables (CPCacheable list): cacheables to submit
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            save (bool): save scene on submit
            checks_data (dict): sanity check data
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
