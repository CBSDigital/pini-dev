"""Tools for managing the pipeline root in a sg-based pipeline."""

from . import cp_root_base


class CPRootSG(cp_root_base.CPRootBase):
    """Represents a pipeline root in a sg-based pipeline."""

    def _read_job_dirs(self):
        """Read paths to jobs.

        Returns:
            (str list): job dir paths
        """
        from pini.pipe import shotgrid
        return [_job.path for _job in shotgrid.SGC.jobs]
