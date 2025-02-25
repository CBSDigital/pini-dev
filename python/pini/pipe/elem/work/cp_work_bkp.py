"""Tools for managing work file backups."""

import logging
import time

from pini.utils import File, cache_property, to_time_f

_LOGGER = logging.getLogger(__name__)

BKP_TSTAMP_FMT = '%y%m%d_%H%M%S'


class CPWorkBkp(File):
    """Represents a work backup file."""

    def mtime(self):
        """Obtain backup time by parsing filename.

        Returns:
            (float): mtime
        """
        return to_time_f(time.strptime(self.base, BKP_TSTAMP_FMT))

    @cache_property
    def metadata(self):
        """Obtain backup metadata.

        Returns:
            (dict): metadata
        """
        return self.yml.read_yml()

    @property
    def reason(self):
        """Obtain backup reason (eg. save over, cache).

        Returns:
            (str): reason
        """
        return self.metadata['reason']

    @property
    def yml(self):
        """Obtain this backup file's yml file.

        Returns:
            (File): yml file
        """
        return self.to_file(extn='yml')
