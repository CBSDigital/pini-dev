"""Tools for managing shot sequences in a sg-based pipeline."""

import logging

from . import cp_sequence_base

_LOGGER = logging.getLogger(__name__)


class CPSequenceSG(cp_sequence_base.CPSequenceBase):
    """Represents a shot sequence in a sg-based pipeline."""

    def _read_shot_paths(self):
        """Get a list of shot paths in this sequence."""
        _paths = [_shot for _shot in self.job.read_shots()
                  if _shot.sequence == self.name]
        _LOGGER.debug(' - PATHS %s', _paths)
        return _paths
