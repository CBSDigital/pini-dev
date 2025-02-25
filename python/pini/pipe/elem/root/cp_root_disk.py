"""Tools for managing the pipeline root in a disk-based pipeline."""

from . import cp_root_base


class CPRootDisk(cp_root_base.CPRootBase):
    """Represents a pipeline root in a disk-based pipeline."""

    def _read_job_dirs(self):
        """Read paths to jobs.

        Returns:
            (str list): job dir paths
        """
        return self.find(depth=1, type_='d', catch_missing=True)
