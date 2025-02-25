"""Tools for managing shot sequences in a disk-based pipeline."""

import logging

from . import cp_sequence_base

_LOGGER = logging.getLogger(__name__)


class CPSequenceDisk(cp_sequence_base.CPSequenceBase):
    """Represents a shot sequence in a disk-based pipeline."""

    def _read_shot_paths(self):
        """Get a list of shot paths in this sequence."""
        from pini import pipe
        _tmpl = self.job.find_template('entity_path', profile='shot')
        _tmpl = _tmpl.apply_data(job_path=self.job.path, sequence=self.name)
        _LOGGER.debug(' - TEMPLATE %s path_type=%s', _tmpl, _tmpl.path_type)
        _paths = pipe.glob_template(template=_tmpl, job=self.job)
        return _paths
